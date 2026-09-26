#!/usr/bin/env python3
"""STEP 3: per-model GPU pass. NF4 4-bit (double quant, bf16 compute), empty system turn, greedy, 160 new tokens,
left-padded length-sorted batches. One model load per model: smoke -> throughput ladder (+cut decision on Gemma)
-> batch check -> DEV generation -> FINAL generation (SEALED: nothing reads FINAL responses before the addendum).

Usage: python gen.py --model gemma_it|gams3_it [--phases smoke,ladder,batchcheck,dev,final]
All generation outputs are append-only and resumable (keys already present are skipped).
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.pop("TRANSFORMERS_CACHE", None)

import torch  # noqa: E402

from common import disable_torch_native_triton  # noqa: E402

NATIVE_STATUS = disable_torch_native_triton()
from loguru import logger  # noqa: E402

from common import (DATA, MAX_NEW, MODELS, OUT_DEV, OUT_FINAL, PROTO, SEED, read_jsonl, setup_logging,  # noqa: E402
                    sha1_int, sha256_file, truncate)

GPU_BUDGET_H = float(os.environ.get("AII_GPU_BUDGET_H", "3.3"))


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------------ model
def load_model(mkey: str):
    from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    spec = MODELS[mkey]
    cfg = AutoConfig.from_pretrained(spec["repo"], revision=spec["revision"])
    arch = (cfg.architectures or ["?"])[0]
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             llm_int8_skip_modules=["vision_tower", "multi_modal_projector", "lm_head"])
    kw = dict(revision=spec["revision"], quantization_config=bnb, dtype=torch.bfloat16, device_map="cuda:0",
              attn_implementation="eager")
    t0 = time.time()
    if "ConditionalGeneration" in arch:
        from transformers import Gemma3ForConditionalGeneration
        model = Gemma3ForConditionalGeneration.from_pretrained(spec["repo"], **kw)
    else:
        model = AutoModelForCausalLM.from_pretrained(spec["repo"], **kw)
    model.eval()
    tok = AutoTokenizer.from_pretrained(spec["repo"], revision=spec["revision"])
    tok.padding_side = "left"
    info = {"arch": arch, "load_s": round(time.time() - t0, 1), "vram_gb": round(torch.cuda.memory_allocated() / 1e9, 2),
            "native_triton": NATIVE_STATUS, "torch": torch.__version__}
    logger.info(f"loaded {mkey} {info}")
    return model, tok, info


def render(tok, text: str) -> str:
    return tok.apply_chat_template([{"role": "user", "content": text}], add_generation_prompt=True, tokenize=False)


def eos_ids(tok) -> list[int]:
    return sorted({tok.eos_token_id, tok.convert_tokens_to_ids("<end_of_turn>")})


@torch.inference_mode()
def generate_batch(model, tok, texts: list[str], max_new: int = MAX_NEW) -> list[dict]:
    enc = [tok(render(tok, t), add_special_tokens=False).input_ids for t in texts]
    Lm = max(len(x) for x in enc)
    pad = tok.pad_token_id if tok.pad_token_id is not None else 0
    inp = torch.tensor([[pad] * (Lm - len(x)) + x for x in enc], device="cuda:0")
    att = torch.tensor([[0] * (Lm - len(x)) + [1] * len(x) for x in enc], device="cuda:0")
    eids = eos_ids(tok)
    out = model.generate(input_ids=inp, attention_mask=att, do_sample=False, max_new_tokens=max_new,
                         eos_token_id=eids, pad_token_id=pad, top_p=None, top_k=None, temperature=None,
                         disable_compile=True)
    res = []
    for i, seq in enumerate(out[:, Lm:].tolist()):
        cut, hit = [], False
        for t in seq:
            if t in eids:
                hit = True
                break
            cut.append(t)
        raw = tok.decode(cut, skip_special_tokens=False)
        res.append({"response": tok.decode(cut, skip_special_tokens=True), "n_new_tokens": len(cut), "hit_eos": hit,
                    "prompt_len": len(enc[i]), "template_leak": ("<start_of_turn>" in raw) or ("<end_of_turn>" in raw)})
    return res


def run_items(model, tok, mkey: str, items: list[dict], out_path: Path, bs: int, tag: str,
              deadline: float | None = None) -> dict:
    """items: manifest rows (gid,...). Appends rows to out_path; resumable. Keeps the given ORDER of chunks but sorts
    by prompt length inside each chunk of 8*bs to reduce padding."""
    done = {r["key"] for r in read_jsonl(out_path)}
    todo = [it for it in items if f"{it['gid']}|{mkey}" not in done]
    logger.info(f"[{tag}] {mkey}: {len(todo)} to generate ({len(items) - len(todo)} done) bs={bs}")
    t0, n = time.time(), 0
    chunk = 8 * bs
    sha = MODELS[mkey]["revision"]
    for c0 in range(0, len(todo), chunk):
        ch = sorted(todo[c0:c0 + chunk], key=lambda r: len(r["text"]))
        queue = [ch[i:i + bs] for i in range(0, len(ch), bs)]
        while queue:
            b = queue.pop(0)
            tb = time.time()
            try:
                gens = generate_batch(model, tok, [x["text"] for x in b])
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                if len(b) == 1:
                    raise
                h = len(b) // 2
                logger.warning(f"OOM at bs={len(b)} -> halving (F4)")
                queue = [b[:h], b[h:]] + queue
                continue
            dt = time.time() - tb
            with out_path.open("a") as f:
                for x, g in zip(b, gens):
                    row = {"key": f"{x['gid']}|{mkey}", "gid": x["gid"], "item_id": x["item_id"],
                           "pair_id": x["pair_id"], "set": x["set"], "arm": x["arm"], "split": x["split"],
                           "model": mkey, "prompt_lang": x["prompt_lang"], "prompt_text": x["text"], **g,
                           "batch_size": len(b), "t_gen": utc(), "batch_s": round(dt, 2), "model_sha": sha}
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += len(b)
        el = time.time() - t0
        logger.info(f"[{tag}] {mkey}: {n}/{len(todo)} {el:.0f}s ({n / max(el, 1e-9):.2f}/s) "
                    f"ETA {(len(todo) - n) / max(n / max(el, 1e-9), 1e-9) / 60:.1f} min")
        if deadline and time.time() > deadline:
            logger.warning(f"[{tag}] deadline hit after {n}; resumable")
            break
    return {"n": n, "s": round(time.time() - t0, 1), "rate": round(n / max(time.time() - t0, 1e-9), 3)}


# ------------------------------------------------------------------ item sets
def manifest(name: str) -> list[dict]:
    return read_jsonl(DATA / f"{name}.jsonl")


def dev_items() -> list[dict]:
    rows = []
    for s in ("identity", "refuseu_nat", "refuseu_x", "hard"):
        rows += [r for r in manifest(s) if r["split"] == "DEV"]
    return rows


def final_items(cuts: dict) -> list[dict]:
    """Pre-registered FINAL order: identity -> RefusEU nat EN+SL -> RefusEU SL_MT -> HARD (SL_MT, EN_BT, EN_orig) for
    XSTest, then ORB-toxic, then ORB-hard -> RefusEU EN_BT -> HARD XSTest SL_NLLB (optional)."""
    ident = [r for r in manifest("identity") if r["split"] == "FINAL"]
    nat = [r for r in manifest("refuseu_nat") if r["split"] == "FINAL"]
    x = [r for r in manifest("refuseu_x") if r["split"] == "FINAL"]
    hard = [r for r in manifest("hard") if r["split"] == "FINAL"]
    keep_orbhard = set(cuts.get("orbhard_keep_ids") or [])
    order = ident + nat + [r for r in x if r["arm"] == "SL_MT"]
    for src in ("xstest", "orbench_toxic", "orbench_hard1k"):
        for arm in ("SL_MT", "EN_BT", "EN_orig"):
            sel = [r for r in hard if r["source"] == src and r["arm"] == arm]
            if src == "orbench_hard1k" and keep_orbhard:
                sel = [r for r in sel if r["item_id"] in keep_orbhard]
            if arm == "EN_orig" and src != "xstest" and cuts.get("cut3"):
                sel = []
            order += sel
    if not cuts.get("cut2"):
        order += [r for r in x if r["arm"] == "EN_BT"]
    if not cuts.get("cut_nllb"):
        order += [r for r in hard if r["arm"] == "SL_NLLB"]
    return order


# ------------------------------------------------------------------ phases
def smoke(model, tok, mkey: str, info: dict) -> None:
    nat = [r for r in manifest("refuseu_nat") if r["split"] == "DEV"]
    hard = [r for r in manifest("hard") if r["split"] == "DEV" and not r["is_harmful"] and r["arm"] == "SL_MT"]
    ident = [r for r in manifest("identity") if r["split"] == "DEV" and r["kind"] == "identity" and r["arm"] == "SL"]
    sel = ([r for r in nat if r["arm"] == "EN_nat"][:2] + [r for r in nat if r["arm"] == "SL_nat"][:2] + hard[:2]
           + ident[:2])
    rendered = render(tok, "HELLO")
    out = {"model": mkey, "rendered_template_HELLO": rendered, "has_system_block": "system" in rendered.lower(),
           "load_info": info, "eos_ids": eos_ids(tok), "rows": []}
    for r in sel:
        g = generate_batch(model, tok, [r["text"]])[0]
        out["rows"].append({"gid": r["gid"], "prompt": truncate(r["text"], 150), **g})
        logger.info(f"SMOKE {r['gid']}: eos={g['hit_eos']} n={g['n_new_tokens']} leak={g['template_leak']} :: "
                    f"{truncate(g['response'], 160)!r}")
    assert not any(x["template_leak"] for x in out["rows"]), "template token leak"
    (OUT_DEV / f"smoke_{mkey}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))


def ladder(model, tok, mkey: str) -> int:
    nat = [r for r in manifest("refuseu_nat") if r["split"] == "DEV"]
    rng_sorted = sorted(nat, key=lambda r: sha1_int(r["gid"] + str(SEED)))[:96]
    res = {}
    best, best_rate = 16, 0.0
    free = torch.cuda.get_device_properties(0).total_memory
    for bs in (32, 64, 96):
        torch.cuda.reset_peak_memory_stats()
        t0 = time.time()
        try:
            n = 0
            for i in range(0, len(rng_sorted), bs):
                generate_batch(model, tok, [x["text"] for x in rng_sorted[i:i + bs]])
                n += len(rng_sorted[i:i + bs])
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            res[bs] = {"oom": True}
            logger.warning(f"ladder bs={bs} OOM")
            break
        dt = time.time() - t0
        peak = torch.cuda.max_memory_allocated()
        res[bs] = {"items": n, "s": round(dt, 1), "rate": round(n / dt, 3), "peak_vram_frac": round(peak / free, 3)}
        logger.info(f"ladder bs={bs}: {res[bs]}")
        if n / dt > best_rate and peak / free < 0.90:
            best, best_rate = bs, n / dt
    (OUT_DEV / f"ladder_{mkey}.json").write_text(json.dumps({"results": res, "chosen_bs": best,
                                                              "rate": best_rate}, indent=1))
    return best


def decide_cuts(rate: float) -> dict:
    """Pre-registered cut order, decided on the Gemma ladder and applied identically to GaMS."""
    n_dev = len(dev_items())
    cuts = {"cut1": False, "cut2": False, "cut3": False, "cut_nllb": False, "orbhard_keep_ids": None}
    budget_s = GPU_BUDGET_H * 3600

    def total(c):
        return 2 * (n_dev + len(final_items(c))) / rate

    log = [("none", total(cuts) / 3600)]
    if total(cuts) > budget_s:
        cuts["cut_nllb"] = True
        log.append(("drop optional SL_NLLB", total(cuts) / 3600))
    if total(cuts) > budget_s:
        ids = sorted({r["item_id"] for r in manifest("hard") if r["split"] == "FINAL" and r["source"] == "orbench_hard1k"},
                     key=lambda i: sha1_int(i + str(SEED)))[:400]
        cuts["cut1"], cuts["orbhard_keep_ids"] = True, ids
        log.append(("cut1 ORB-hard->400", total(cuts) / 3600))
    if total(cuts) > budget_s:
        cuts["cut2"] = True
        log.append(("cut2 drop RefusEU EN_BT", total(cuts) / 3600))
    if total(cuts) > GPU_BUDGET_H * 1.09 * 3600:
        cuts["cut3"] = True
        log.append(("cut3 HARD EN_orig XSTest only", total(cuts) / 3600))
    cuts.update({"rate_items_per_s": rate, "budget_h": GPU_BUDGET_H, "projected_h_log": log, "decided_utc": utc(),
                 "n_final_per_model": len(final_items(cuts)), "n_dev_per_model": n_dev})
    return cuts


def batchcheck(model, tok, mkey: str, bs: int) -> None:
    nat = [r for r in manifest("refuseu_nat") if r["split"] == "DEV"]
    en = sorted([r for r in nat if r["arm"] == "EN_nat"], key=lambda r: sha1_int(r["gid"]))[:16]
    sl = sorted([r for r in nat if r["arm"] == "SL_nat"], key=lambda r: sha1_int(r["gid"]))[:16]
    sel = en + sl
    p = OUT_DEV / f"batchcheck_{mkey}.jsonl"
    if len(read_jsonl(p)) >= 64:
        return
    # batched: pad the check items with other DEV items to the chosen batch size (real batch context)
    filler = [r for r in nat if r not in sel][: max(0, bs - len(sel))]
    batched = generate_batch(model, tok, [r["text"] for r in sel + filler])[: len(sel)]
    single = [generate_batch(model, tok, [r["text"]])[0] for r in sel]
    with p.open("w") as f:
        for r, a, b in zip(sel, single, batched):
            for mode, g in (("bs1", a), (f"bs{bs}", b)):
                f.write(json.dumps({"key": f"{r['gid']}|{mkey}|{mode}", "gid": r["gid"], "mode": mode, "model": mkey,
                                    "prompt_lang": r["prompt_lang"], "prompt_text": r["text"], **g},
                                   ensure_ascii=False) + "\n")
    same_text = sum(a["response"] == b["response"] for a, b in zip(single, batched))
    logger.info(f"batchcheck {mkey}: identical text {same_text}/32 (outcome agreement judged later)")


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=list(MODELS))
    ap.add_argument("--phases", default="smoke,ladder,batchcheck,dev,final")
    ap.add_argument("--bs", type=int, default=0)
    ap.add_argument("--deadline_min", type=float, default=0.0, help="wall-clock cap for FINAL generation")
    args = ap.parse_args()
    setup_logging(f"gen_{args.model}")
    torch.cuda.set_per_process_memory_fraction(0.95)
    phases = args.phases.split(",")
    status_p = OUT_DEV / f"gpu_status_{args.model}.json"
    status = json.loads(status_p.read_text()) if status_p.exists() else {}
    model, tok, info = load_model(args.model)
    status["load"] = info
    if "smoke" in phases:
        smoke(model, tok, args.model, info)
    bs = args.bs or status.get("bs") or 0
    if "ladder" in phases and not bs:
        bs = ladder(model, tok, args.model)
    bs = bs or 64
    status["bs"] = bs
    cuts_p = DATA / "cuts.json"
    if not cuts_p.exists():
        lad = json.loads((OUT_DEV / f"ladder_{args.model}.json").read_text())
        cuts = decide_cuts(lad["rate"])
        cuts_p.write_text(json.dumps(cuts, indent=1))
        logger.info(f"cuts decided: { {k: v for k, v in cuts.items() if k != 'orbhard_keep_ids'} }")
    cuts = json.loads(cuts_p.read_text())
    status_p.write_text(json.dumps(status, indent=1))
    if "batchcheck" in phases:
        batchcheck(model, tok, args.model, bs)
    if "dev" in phases:
        items = dev_items()
        # T3 scale-up inside DEV: mini(16) -> 50 -> 200 -> rest, timing logged at each stage
        p = OUT_DEV / f"gen_{args.model}.jsonl"
        for stage, upto in (("mini", 16), ("50", 50), ("200", 200), ("all", len(items))):
            st = run_items(model, tok, args.model, items[:upto], p, bs, f"dev-{stage}")
            status[f"dev_{stage}"] = st
        status_p.write_text(json.dumps(status, indent=1))
    if "final" in phases:
        t_wait = time.time()
        while not (PROTO / "protocol.sha256").exists() and time.time() - t_wait < 3600:
            logger.info("waiting for protocol freeze before FINAL generation ...")
            time.sleep(30)
        assert (PROTO / "protocol.sha256").exists(), "protocol must be frozen before FINAL generation"
        assert sha256_file(PROTO / "protocol.json") == (PROTO / "protocol.sha256").read_text().split()[0]
        items = final_items(cuts)
        deadline = time.time() + args.deadline_min * 60 if args.deadline_min else None
        if "first_final_gen_utc" not in status:
            status["first_final_gen_utc"] = utc()
            status_p.write_text(json.dumps(status, indent=1))
        st = run_items(model, tok, args.model, items, OUT_FINAL / f"gen_{args.model}.jsonl", bs, "final", deadline)
        status["final"] = st
        status["final_done_utc"] = utc()
        status["n_final_expected"] = len(items)
        status_p.write_text(json.dumps(status, indent=1))
    del model
    gc.collect()
    torch.cuda.empty_cache()
    logger.info("GPU pass finished; model evicted")


if __name__ == "__main__":
    main()
