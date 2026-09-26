#!/usr/bin/env python3
"""STEPS 1+4: GPU passes.

  --model nllb           : NLLB-200-distilled-1.3B back-translation of H sl_mt -> en_bt (beam 4, max 256) + chrF vs en_orig
  --model gams|gemma|q14 : NF4 greedy generation (empty system turn, 160 new tokens, left padding, length-sorted batches with
                           OOM halving) on H x {en_orig, sl_mt, en_bt}, R x {en_orig, sl_mt, en_bt}, ID x {en, sl};
                           T4 prefill on R200 x {en_orig, sl_mt} x {pre_comply5, pre_neutral} (96 new tokens);
                           32-item batch-vs-single outcome check.
  --phase pilot          : a small subset into gens/pilot/ (never pooled into analysis files)
All outputs are appended per item (resumable: existing keys are skipped).
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.pop("TRANSFORMERS_CACHE", None)

import torch  # noqa: E402

from common import disable_torch_native_triton  # noqa: E402

NATIVE_STATUS = disable_torch_native_triton()

from common import (DATA, GENS, LOCAL_MODELS, MAX_NEW_TOKENS, NEUTRAL_PREFIX, PREFILL_K, PREFILL_MAX_NEW,  # noqa: E402
                    PREFILL_SOURCE, RESULTS, read_jsonl, row_key, setup_logging, sha1, truncate)

logger = None


# ------------------------------------------------------------------ model loading (iter-1 gpu_pass.load_model, NF4)
def load_model(mkey: str):
    from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    spec = LOCAL_MODELS[mkey]
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
    logger.info(f"loaded {mkey} arch={arch} in {time.time() - t0:.0f}s; vram={torch.cuda.memory_allocated() / 1e9:.1f}GB")
    return model, tok, arch


def render(tok, mkey: str, prompt: str) -> str:
    msgs = [{"role": "user", "content": prompt}]
    if LOCAL_MODELS[mkey]["family"] == "qwen":
        s = tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False, enable_thinking=False)
        assert "<think>\n\n</think>" in s, "Qwen3 render lacks the empty think block"
        assert "<|im_start|>system" not in s, "Qwen3 render contains a system turn"
        return s
    s = tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
    assert "system" not in s.split("<start_of_turn>user")[0], "Gemma-family render contains a system turn"
    return s


def prefill_strings() -> dict:
    """C_lang = decoded first 5 Gemma-tokenizer tokens of the shared iter-2 compliant prefix; same STRING for all models."""
    p = DATA / "prefill_strings.json"
    if p.exists():
        return json.loads(p.read_text())
    from transformers import AutoTokenizer
    g = LOCAL_MODELS["gemma"]
    tok = AutoTokenizer.from_pretrained(g["repo"], revision=g["revision"])
    out = {}
    for lang, s in PREFILL_SOURCE.items():
        ids = tok(s, add_special_tokens=False).input_ids[:PREFILL_K]
        out[lang] = {"pre_comply5": tok.decode(ids), "pre_neutral": NEUTRAL_PREFIX[lang], "source": s,
                     "gemma_ids": ids}
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out


# ------------------------------------------------------------------ job construction
def build_jobs(mkey: str, phase: str) -> list[dict]:
    items = read_jsonl(DATA / "items.jsonl")
    bt = {r["item_id"]: r["en_bt"] for r in read_jsonl(DATA / "h_en_bt.jsonl")}
    pre = prefill_strings()
    H = [i for i in items if i["set"] == "H"]
    R = [i for i in items if i["set"] == "R"]
    ID = [i for i in items if i["set"] == "ID"]
    if phase == "pilot":
        H = sorted(H, key=lambda x: sha1("pilot" + x["item_id"]))[:32]
        R = sorted(R, key=lambda x: sha1("pilot" + x["item_id"]))[:16]
        ID = sorted(ID, key=lambda x: sha1("pilot" + x["item_id"]))[:8]
    jobs = []

    def add(it, arm, cond, text, prefix=""):
        jobs.append({"key": row_key(it["item_id"], mkey, arm, cond), "item_id": it["item_id"], "set": it["set"],
                     "lang_arm": arm, "condition": cond, "system": mkey, "prompt": text, "prefix": prefix})

    for it in H:
        add(it, "en_orig", "k0", it["arms"]["en_orig"])
        add(it, "sl_mt", "k0", it["arms"]["sl_mt"])
        if it["item_id"] in bt and phase != "pilot":
            add(it, "en_bt", "k0", bt[it["item_id"]])
    for it in R:
        for arm in (("en_orig", "sl_mt") if phase == "pilot" else ("en_orig", "sl_mt", "en_bt")):
            add(it, arm, "k0", it["arms"][arm])
    for it in ID:
        add(it, "en", "k0", it["arms"]["en"])
        add(it, "sl", "k0", it["arms"]["sl"])
    Rp = [i for i in R if i.get("r200")] if phase != "pilot" else R[:8]
    for it in Rp:
        for arm, lang in (("en_orig", "en"), ("sl_mt", "sl")):
            for cond in ("pre_comply5", "pre_neutral"):
                add(it, arm, cond, it["arms"][arm], prefix=pre[lang][cond])
    return jobs


# ------------------------------------------------------------------ generation
def eos_ids(tok, model) -> set[int]:
    ids = set()
    ge = getattr(model, "generation_config", None)
    e = getattr(ge, "eos_token_id", None)
    if isinstance(e, int):
        ids.add(e)
    elif isinstance(e, list):
        ids.update(e)
    for t in ("<end_of_turn>", "<eos>", "<|im_end|>", "<|endoftext|>"):
        i = tok.convert_tokens_to_ids(t)
        if isinstance(i, int) and i != tok.unk_token_id:
            ids.add(i)
    if tok.eos_token_id is not None:
        ids.add(tok.eos_token_id)
    return ids


@torch.inference_mode()
def generate_batch(model, tok, ids_list: list[list[int]], max_new: int, eos: set[int]) -> list[tuple[list[int], str]]:
    L = max(len(x) for x in ids_list)
    pad = tok.pad_token_id if tok.pad_token_id is not None else 0
    inp = torch.tensor([[pad] * (L - len(x)) + x for x in ids_list], device="cuda:0")
    att = torch.tensor([[0] * (L - len(x)) + [1] * len(x) for x in ids_list], device="cuda:0")
    out = model.generate(input_ids=inp, attention_mask=att, do_sample=False, max_new_tokens=max_new,
                         pad_token_id=pad, eos_token_id=sorted(eos), top_p=None, top_k=None, temperature=None,
                         disable_compile=True)
    res = []
    for seq in out[:, L:].tolist():
        cut, fin = [], "length"
        for t in seq:
            if t in eos:
                fin = "stop"
                break
            cut.append(t)
        res.append((cut, fin))
    return res


def run_jobs(model, tok, mkey: str, jobs: list[dict], out_path: Path, max_bs: int, model_sha: str) -> dict:
    done = {r["key"] for r in read_jsonl(out_path)}
    todo = [j for j in jobs if j["key"] not in done]
    logger.info(f"{mkey}: {len(todo)} to generate -> {out_path.name} ({len(jobs) - len(todo)} done)")
    if not todo:
        return {"n": 0, "secs": 0.0}
    eos = eos_ids(tok, model)
    for j in todo:
        rendered = render(tok, mkey, j["prompt"]) + j["prefix"]
        j["_rendered_sha1"] = sha1(rendered)
        j["_ids"] = tok(rendered, add_special_tokens=False).input_ids
        j["_max_new"] = PREFILL_MAX_NEW if j["prefix"] else MAX_NEW_TOKENS
    t0, n = time.time(), 0
    for max_new in sorted({j["_max_new"] for j in todo}):
        grp = sorted([j for j in todo if j["_max_new"] == max_new], key=lambda j: len(j["_ids"]))
        batches = [grp[i:i + max_bs] for i in range(0, len(grp), max_bs)]
        queue = list(batches)
        while queue:
            b = queue.pop(0)
            try:
                gens = generate_batch(model, tok, [x["_ids"] for x in b], max_new, eos)
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                if len(b) == 1:
                    raise
                h = len(b) // 2
                logger.warning(f"OOM at bs={len(b)} (L={len(b[-1]['_ids'])}) -> halving")
                queue = [b[:h], b[h:]] + queue
                continue
            with out_path.open("a") as f:
                for x, (g, fin) in zip(b, gens):
                    cont = tok.decode(g, skip_special_tokens=True)
                    row = {k: v for k, v in x.items() if not k.startswith("_") and k != "prompt"}
                    row.update({"prompt_sha1": sha1(x["prompt"]), "prompt_rendered_sha1": x["_rendered_sha1"],
                                "response": x["prefix"] + cont, "continuation": cont, "n_new_tokens": len(g),
                                "finish_reason": fin, "prompt_len": len(x["_ids"]), "model_sha": model_sha,
                                "batch_size": len(b)})
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += len(b)
            if n % 240 < len(b):
                el = time.time() - t0
                logger.info(f"{mkey}: {n}/{len(todo)} in {el:.0f}s ({n / el:.2f} items/s); last: "
                            f"{truncate(b[0]['prefix'] + tok.decode(gens[0][0], skip_special_tokens=True), 120)!r}")
    secs = time.time() - t0
    logger.info(f"{mkey}: generated {n} in {secs:.0f}s ({n / max(secs, 1e-9):.2f} items/s)")
    return {"n": n, "secs": secs, "items_per_s": n / max(secs, 1e-9)}


def batch_vs_single(model, tok, mkey: str, jobs: list[dict], out_path: Path, model_sha: str, n: int = 32) -> None:
    """n-item batch-1 regeneration of the first n H en_orig k0 items (outcome-level check, CONFIRM-SPEC 3d).
    Batch-1 NF4 decoding runs at ~14 s/item on the 4090, so the full pass uses n=16 (GaMS: pilot n=32 reused)."""
    sel = [dict(j, key=j["key"].replace("|k0", "|k0_bs1"), condition="k0_bs1") for j in jobs
           if j["set"] == "H" and j["lang_arm"] == "en_orig" and j["condition"] == "k0"][:n]
    run_jobs(model, tok, mkey, sel, out_path, max_bs=1, model_sha=model_sha)


# ------------------------------------------------------------------ NLLB back-translation
@torch.inference_mode()
def run_nllb() -> None:
    from sacrebleu.metrics import CHRF
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    out_p = DATA / "h_en_bt.jsonl"
    items = [i for i in read_jsonl(DATA / "items.jsonl") if i["set"] == "H"]
    done = {r["item_id"] for r in read_jsonl(out_p)}
    todo = [i for i in items if i["item_id"] not in done]
    logger.info(f"NLLB BT: {len(todo)} to translate")
    if not todo:
        return
    name = "facebook/nllb-200-distilled-1.3B"
    tok = AutoTokenizer.from_pretrained(name, src_lang="slv_Latn")
    model = AutoModelForSeq2SeqLM.from_pretrained(name, dtype=torch.bfloat16).to("cuda:0").eval()
    chrf = CHRF()
    tgt = tok.convert_tokens_to_ids("eng_Latn")
    t0 = time.time()
    todo = sorted(todo, key=lambda x: len(x["arms"]["sl_mt"]))
    with out_p.open("a") as f:
        for i in range(0, len(todo), 32):
            b = todo[i:i + 32]
            enc = tok([x["arms"]["sl_mt"] for x in b], return_tensors="pt", padding=True, truncation=True,
                      max_length=256).to("cuda:0")
            gen = model.generate(**enc, forced_bos_token_id=tgt, num_beams=4, max_length=256)
            outs = tok.batch_decode(gen, skip_special_tokens=True)
            for x, o in zip(b, outs):
                f.write(json.dumps({"item_id": x["item_id"], "en_bt": o,
                                    "chrf_bt_vs_en": round(chrf.sentence_score(o, [x["arms"]["en_orig"]]).score, 2)},
                                   ensure_ascii=False) + "\n")
    logger.info(f"NLLB BT done in {time.time() - t0:.0f}s")
    del model
    gc.collect()
    torch.cuda.empty_cache()


def main() -> None:
    global logger
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=["nllb", *LOCAL_MODELS])
    ap.add_argument("--phase", default="full", choices=["pilot", "full"])
    ap.add_argument("--bs", type=int, default=32)
    ap.add_argument("--limit", type=int, default=0, help="scaling stage: only the first N jobs (0 = all)")
    ap.add_argument("--skip-bvs", action="store_true")
    ap.add_argument("--bvs-n", type=int, default=32)
    args = ap.parse_args()
    logger = setup_logging(f"gpu_{args.model}_{args.phase}")
    logger.info(f"torch native status: {NATIVE_STATUS}; torch {torch.__version__}")
    free, total = torch.cuda.mem_get_info(0)
    torch.cuda.set_per_process_memory_fraction(0.92)
    logger.info(f"GPU {torch.cuda.get_device_name(0)} free {free / 1e9:.1f}/{total / 1e9:.1f} GB")
    try:
        if args.model == "nllb":
            run_nllb()
            return
        jobs = build_jobs(args.model, args.phase)
        if args.limit:
            # staged scale-up: keep a stratified slice (every arm/condition represented)
            jobs = jobs[: args.limit]
        model, tok, arch = load_model(args.model)
        sha = LOCAL_MODELS[args.model]["revision"]
        # template audit
        ex = render(tok, args.model, "Hello")
        (RESULTS / f"template_{args.model}.txt").write_text(ex + "\n----- prefill render en:\n" +
                                                         ex + prefill_strings()["en"]["pre_comply5"])
        pre = prefill_strings()
        counts = {lang: {c: len(tok(pre[lang][c], add_special_tokens=False).input_ids)
                         for c in ("pre_comply5", "pre_neutral")} for lang in pre}
        (RESULTS / f"prefix_token_counts_{args.model}.json").write_text(json.dumps(counts))
        out = (GENS / "pilot" if args.phase == "pilot" else GENS) / f"{args.model}.jsonl"
        stats = run_jobs(model, tok, args.model, jobs, out, args.bs, sha)
        if not args.skip_bvs:
            batch_vs_single(model, tok, args.model, jobs, (GENS / "pilot" if args.phase == "pilot" else GENS) /
                            f"{args.model}_bs1.jsonl", sha, n=args.bvs_n)
        tp = RESULTS / "throughput.jsonl"
        with tp.open("a") as f:
            f.write(json.dumps({"model": args.model, "phase": args.phase, "limit": args.limit, "arch": arch,
                                "bs": args.bs, **stats, "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}) + "\n")
        del model
        gc.collect()
        torch.cuda.empty_cache()
    except Exception:
        logger.exception("gpu_gen failed")
        raise


if __name__ == "__main__":
    main()
