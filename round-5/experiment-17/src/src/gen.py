#!/usr/bin/env python3
"""Phases 1/2 GPU block for ONE study model per invocation (one 12B snapshot in memory at a time).

NF4 (double quant, bf16 compute), greedy, 128 new tokens, empty system turn (single user turn), left padding,
length-sorted token-budget batches, generate(disable_compile=True), OOM halving.
Edit = iter-3 exp9 selected Heretic LoRA (r=3, alpha=3 -> scaling 1) applied as a scaled forward hook
out += lambda * B(A(x)) on o_proj/down_proj (hook code copied from iter_3 exp11 src/gen.py _hook/attach_adapter/
set_lambda; exp15 verified it reproduces exp9's saved lambda 1.00/0.50 adapters). lambda = 0 skips the hook.
A second hook set (exp9 adapters/<m>/rand_1, norm-matched random direction) is attached for the control arm.

Stages (in order, each resumable by key item_id|model|cond|lambda|max_new):
  checks   lambda-0 identity vs hooks removed (assert max|dlogit| == 0), lambda-1 changes logits, template sha1
  mini     8 DEV EN + 8 DEV SL x {0, 1.0}; batch-size / throughput probe
  dev      100 DEV EN x lambda grid {0,1,1.15,1.3,1.45,1.6,1.8,2.0}; DEV SL x {0, 1.0}
  final    (requires frozen protocol) orig, edit@1.0 on all FINAL rows; then rand_1@1.0 on the 400 control
           rows; then the 256-token sensitivity rows at lambda 1.0.
  gate     (second session, after the guard pass on DEV rows decided amendment A1
           results/amendments/lambda_gate_<model>.json) edit@lambda_gate on the FINAL pairs A1 names + DEV SL.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

os.environ.pop("TRANSFORMERS_CACHE", None)
import torch  # noqa: E402

from common import disable_torch_native_triton  # noqa: E402

NATIVE = disable_torch_native_triton()
from loguru import logger  # noqa: E402

from common import (ADAPTER_DIR, DATA, GENS, MAX_NEW, MODELS, RANDOM_DIR, RESULTS, append_jsonl, degenerate,  # noqa
                    dump, guard_final, lingua_lang, read_jsonl, setup_logging, sha1_file, sha256_file)

TOKEN_BUDGET = int(os.environ.get("AII_TOKEN_BUDGET", "24000"))
MAX_BS = int(os.environ.get("AII_MAX_BS", "160"))
# The gate rule needs {0, 1.0} unless rel_cut(1.0) < 0.5, and then the doses above 1.0 in order. AII_DEV_GRID lets a
# session run the short grid first (wall-cut amendment A0_gams3_it); dev_gate.py reports whatever doses exist.
DEV_GRID = [float(x) for x in os.environ.get("AII_DEV_GRID", "0,1.0,1.15,1.3,1.45,1.6,1.8,2.0").split(",")]
AMEND = RESULTS / "amendments"
AMEND.mkdir(parents=True, exist_ok=True)


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_model(mkey: str):
    from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    spec = MODELS[mkey]
    cfg = AutoConfig.from_pretrained(spec["repo"], revision=spec["revision"])
    arch = (cfg.architectures or ["?"])[0]
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             llm_int8_skip_modules=["vision_tower", "multi_modal_projector", "lm_head"])
    kw = dict(revision=spec["revision"], quantization_config=bnb, dtype=torch.bfloat16, device_map="cuda:0",
              attn_implementation="sdpa")
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
            "native_triton": NATIVE, "torch": torch.__version__, "repo": spec["repo"], "revision": spec["revision"]}
    logger.info(f"loaded {mkey} {info}")
    return model, tok, info


# ------------------------------------------------------------------ hooks (exp11 _hook, generalised to 2 sets)
_LORA: dict = {"lam": 0.0, "active": "edit", "handles": []}


def _hook(A: torch.Tensor, B: torch.Tensor, tag: str):
    def fn(mod, args, out):
        lam = _LORA["lam"]
        if lam == 0.0 or _LORA["active"] != tag:
            return out
        x = args[0]
        return out + lam * ((x.to(A.dtype) @ A.t()) @ B.t()).to(out.dtype)
    return fn


def attach(model, ad: Path, tag: str) -> dict:
    from safetensors.torch import load_file
    cfg = json.loads((ad / "adapter_config.json").read_text())
    assert cfg["r"] == cfg["lora_alpha"], cfg
    sd = load_file(str(ad / "adapter_model.safetensors"))
    mods = dict(model.named_modules())
    pairs: dict = {}
    for k, v in sd.items():
        name = k.replace("base_model.model.", "", 1).rsplit(".lora_", 1)[0]
        pairs.setdefault(name, {})["A" if ".lora_A." in k else "B"] = v
    missing = [n for n in pairs if n not in mods]
    assert not missing, f"adapter targets not in model: {missing[:4]}"
    for name, ab in pairs.items():
        A = ab["A"].to("cuda:0", torch.bfloat16)
        B = ab["B"].to("cuda:0", torch.bfloat16)
        _LORA["handles"].append(mods[name].register_forward_hook(_hook(A, B, tag)))
    info = {"tag": tag, "adapter_dir": str(ad).split("3_invention_loop/")[-1],
            "adapter_sha256": sha256_file(ad / "adapter_model.safetensors"),
            "adapter_sha1": sha1_file(ad / "adapter_model.safetensors"), "n_tensors": len(sd),
            "n_lora_modules": len(pairs), "impl": "forward hooks, bf16, scaling = lambda",
            "r": cfg["r"], "target_modules": cfg.get("target_modules")}
    logger.info(f"adapter attached {info}")
    return info


def set_lambda(lam: float, active: str = "edit") -> None:
    _LORA["lam"] = float(lam)
    _LORA["active"] = active


# ------------------------------------------------------------------ generation
def render(tok, text: str) -> str:
    return tok.apply_chat_template([{"role": "user", "content": text}], add_generation_prompt=True, tokenize=False)


def eos_ids(tok) -> list[int]:
    return sorted({tok.eos_token_id, tok.convert_tokens_to_ids("<end_of_turn>")})


@torch.inference_mode()
def generate_batch(model, tok, encs: list[list[int]], max_new: int) -> list[dict]:
    Lm = max(len(x) for x in encs)
    pad = tok.pad_token_id if tok.pad_token_id is not None else 0
    inp = torch.tensor([[pad] * (Lm - len(x)) + x for x in encs], device="cuda:0")
    att = torch.tensor([[0] * (Lm - len(x)) + [1] * len(x) for x in encs], device="cuda:0")
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
        res.append({"response": tok.decode(cut, skip_special_tokens=True), "n_new_tokens": len(cut),
                    "finish_reason": "eos" if hit else "length", "prompt_len": len(encs[i]),
                    "template_leak": ("<start_of_turn>" in raw) or ("<end_of_turn>" in raw)})
    del out, inp, att
    return res


class Runner:
    def __init__(self, model, tok, mkey: str, deadline: float | None):
        self.model, self.tok, self.mkey, self.deadline = model, tok, mkey, deadline
        self.budget = TOKEN_BUDGET

    def out_of_time(self) -> bool:
        f = RESULTS / f"deadline_{self.mkey}.txt"
        if f.exists():
            try:
                self.deadline = float(f.read_text().split()[0])
            except (ValueError, IndexError):
                pass
        return bool(self.deadline and time.time() > self.deadline)

    def run(self, items: list[dict], out_path: Path, cond: str, lam: float, tag: str, max_new: int = MAX_NEW) -> dict:
        keyf = lambda it: f"{it['item_id']}|{self.mkey}|{cond}|{lam:g}|{max_new}"  # noqa: E731
        done = {r["key"] for r in read_jsonl(out_path)}
        todo = [it for it in items if keyf(it) not in done]
        logger.info(f"[{tag}] {self.mkey} {cond} lam={lam:g} max_new={max_new}: {len(todo)} to generate "
                    f"({len(items) - len(todo)} done)")
        if not todo:
            return {"n": 0}
        set_lambda(lam, "rand" if cond.startswith("rand") else "edit")
        fb = RESULTS / "token_budget.txt"
        if fb.exists():
            try:
                self.budget = int(fb.read_text().split()[0])
            except (ValueError, IndexError):
                pass
        for x in todo:
            enc = self.tok(render(self.tok, x["prompt"]), add_special_tokens=False).input_ids
            x["_trunc"] = 0
            if len(enc) > 3000:  # left-truncate the user content, flagged (plan 0.2)
                enc = enc[:2] + enc[-2998:]
                x["_trunc"] = 1
            x["_enc"] = enc
        todo = sorted(todo, key=lambda r: len(r["_enc"]))
        queue, cur = [], []
        for x in todo:
            if cur and ((len(cur) + 1) * (len(x["_enc"]) + max_new) > self.budget or len(cur) >= MAX_BS):
                queue.append(cur)
                cur = []
            cur.append(x)
        if cur:
            queue.append(cur)
        t0, n, degen = time.time(), 0, 0
        while queue:
            if self.out_of_time():
                logger.warning(f"[{tag}] deadline hit after {n}; resumable")
                break
            b = queue.pop(0)
            tb = time.time()
            try:
                gens = generate_batch(self.model, self.tok, [x["_enc"] for x in b], max_new)
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                if len(b) == 1:
                    raise
                h = len(b) // 2
                logger.warning(f"OOM at bs={len(b)} -> halving")
                queue = [b[:h], b[h:]] + queue
                continue
            dt = time.time() - tb
            rows = []
            for x, g in zip(b, gens):
                dg = degenerate(g["response"])
                degen += dg
                ll, lc = lingua_lang(g["response"])
                rows.append({"key": keyf(x), "item_id": x["item_id"], "pair_id": x["pair_id"], "lang": x["lang"],
                             "fold": x["fold"], "model": self.mkey, "cond": cond, "lambda": lam, "max_new": max_new,
                             "prompt": x["prompt"], **g, "degenerate": dg, "empty": int(not g["response"].strip()),
                             "prompt_truncated": x["_trunc"], "lingua_lang": ll, "lingua_conf": lc,
                             "batch_size": len(b), "model_sha": MODELS[self.mkey]["revision"], "t_gen": utc(),
                             "batch_s": round(dt, 2), "tag": tag})
            append_jsonl(out_path, rows)
            n += len(b)
            el = time.time() - t0
            logger.info(f"[{tag}] {n}/{len(todo)} bs={len(b)} {el:.0f}s ({n / max(el, 1e-9):.2f}/s) "
                        f"degen {degen / n:.3f} ETA {(len(todo) - n) / max(n / max(el, 1e-9), 1e-9) / 60:.1f} min")
        return {"n": n, "s": round(time.time() - t0, 1), "rate": round(n / max(time.time() - t0, 1e-9), 3)}


@torch.inference_mode()
def checks(model, tok, mkey: str, dev: list[dict]) -> dict:
    """lambda-0 identity vs all hooks removed, lambda-1 changes logits (T2)."""
    texts = [r["prompt"] for r in dev[:8]]
    encs = [tok(render(tok, t), add_special_tokens=False).input_ids for t in texts]

    def logits_now() -> torch.Tensor:
        out = []
        for e in encs:
            ids = torch.tensor([e], device="cuda:0")
            out.append(model(input_ids=ids).logits[0, -1].float().cpu())
        return torch.stack(out)

    handles = _LORA["handles"]
    for h in handles:
        h.remove()
    base = logits_now()
    # re-attach
    _LORA["handles"] = []
    attach(model, ADAPTER_DIR[mkey], "edit")
    if RANDOM_DIR[mkey].exists():
        attach(model, RANDOM_DIR[mkey], "rand")
    set_lambda(0.0)
    l0 = logits_now()
    set_lambda(1.0)
    l1 = logits_now()
    set_lambda(1.0, "rand")
    lr = logits_now()
    set_lambda(0.0)
    d0 = float((l0 - base).abs().max())
    d1 = float((l1 - base).abs().max())
    dr = float((lr - base).abs().max())
    tmpl = render(tok, "{{USER}}")
    res = {"lambda0_max_abs_dlogit": d0, "lambda1_max_abs_dlogit": d1, "rand1_max_abs_dlogit": dr,
           "argmax_changed_lambda1": int((l1.argmax(-1) != base.argmax(-1)).sum()),
           "template_render": tmpl, "template_sha1": hashlib.sha1(tmpl.encode()).hexdigest(),
           "chat_template_sha1": hashlib.sha1((tok.chat_template or "").encode()).hexdigest(),
           "n_prompts": len(texts)}
    logger.info(f"checks {mkey}: {res}")
    assert d0 == 0.0, f"lambda-0 identity FAILED max|dlogit|={d0}"
    assert d1 > 0.0, "lambda 1 does not change logits"
    return res


def wait_for(path: Path, what: str, poll: int = 20, max_wait: int = 5400) -> bool:
    t0 = time.time()
    while not path.exists():
        if time.time() - t0 > max_wait:
            logger.error(f"gave up waiting for {what}")
            return False
        time.sleep(poll)
    return True


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=list(MODELS))
    ap.add_argument("--stages", default="checks,mini,dev,final")  # or "gate"
    ap.add_argument("--deadline", type=float, default=None)
    a = ap.parse_args()
    setup_logging(f"gen_{a.model}")
    torch.cuda.set_per_process_memory_fraction(0.92)
    stages = a.stages.split(",")
    dev = read_jsonl(DATA / "items_dev.jsonl")
    fin = read_jsonl(DATA / "items_final.jsonl")
    dev_en = [r for r in dev if r["lang"] == "en"]
    dev_sl = [r for r in dev if r["lang"] == "sl"]
    model, tok, info = load_model(a.model)
    ad = [attach(model, ADAPTER_DIR[a.model], "edit")]
    if RANDOM_DIR[a.model].exists():
        ad.append(attach(model, RANDOM_DIR[a.model], "rand"))
    else:
        logger.warning("rand_1 adapter missing -> random-control arm skipped")
    run = Runner(model, tok, a.model, a.deadline)
    dev_out = GENS / f"dev_{a.model}.jsonl"
    fin_out = GENS / f"{a.model}.jsonl"
    meta = {"load": info, "adapters": ad, "token_budget": TOKEN_BUDGET, "max_bs": MAX_BS, "stages": {}}
    if "gate" in stages and stages != ["gate"]:
        raise SystemExit("run the gate stage alone")
    if "checks" in stages:
        meta["checks"] = checks(model, tok, a.model, dev_en)
    if "mini" in stages:
        mini = dev_en[:8] + dev_sl[:8]
        for lam in (0.0, 1.0):
            meta["stages"][f"mini_{lam:g}"] = run.run(mini, dev_out, "orig" if lam == 0 else "edit", lam, "mini")
        for r in read_jsonl(dev_out)[:32]:
            logger.info(f"MINI {r['lang']} lam={r['lambda']} :: {r['response'][:160]!r}")
    if "dev" in stages:
        for lam in DEV_GRID:
            meta["stages"][f"dev_en_{lam:g}"] = run.run(dev_en, dev_out, "orig" if lam == 0 else "edit", lam, "dev")
        for lam in (0.0, 1.0):
            meta["stages"][f"dev_sl_{lam:g}"] = run.run(dev_sl, dev_out, "orig" if lam == 0 else "edit", lam, "dev")
    if stages != ["gate"]:
        dump(RESULTS / f"gen_meta_{a.model}.json", meta)
    if "final" in stages:
        if not wait_for(RESULTS.parent / "protocol.sha256", "protocol freeze", max_wait=3600):
            raise RuntimeError("protocol never frozen")
        guard_final(f"FINAL generation {a.model}")
        meta["stages"]["final_orig"] = run.run(fin, fin_out, "orig", 0.0, "final")
        meta["stages"]["final_edit1"] = run.run(fin, fin_out, "edit", 1.0, "final")
        dump(RESULTS / f"gen_meta_{a.model}.json", meta)
        cuts = json.loads((AMEND / "cuts.json").read_text()) if (AMEND / "cuts.json").exists() else {}
        if not cuts.get("drop_rand") and RANDOM_DIR[a.model].exists():
            meta["stages"]["rand"] = run.run([r for r in fin if r["rand_ctrl"]], fin_out, "rand1", 1.0, "rand")
        n256 = int(cuts.get("sens256_pairs", 100))
        if n256 > 0:
            sub = [r for r in fin if r["sens256"]]
            if n256 < 100:  # cut 2: keep the first n256 sens256 pairs in the frozen sens256 hash order
                from common import sha1 as _sha1
                keep = set(sorted({r["pair_id"] for r in sub}, key=lambda q: _sha1("256|20260925|" + q))[:n256])
                sub = [r for r in sub if r["pair_id"] in keep]
            meta["stages"]["sens256"] = run.run(sub, fin_out, "edit", 1.0, "sens256", max_new=256)
        dump(RESULTS / f"gen_meta_{a.model}.json", meta)
    if "gate" in stages:
        guard_final(f"FINAL gate generation {a.model}")
        gate_f = AMEND / f"lambda_gate_{a.model}.json"
        if wait_for(gate_f, "amendment A1", max_wait=1800):
            g = json.loads(gate_f.read_text())
            logger.info(f"A1 {a.model}: {g.get('status')} lambda_gate={g.get('lambda_gate')} n_pairs={g.get('n_pairs')}")
            if g.get("lambda_gate") and g["lambda_gate"] != 1.0:
                lg = float(g["lambda_gate"])
                meta["stages"]["dev_sl_gate"] = run.run(dev_sl, dev_out, "edit", lg, "dev_sl_gate")
                npairs = int(g.get("n_pairs", 1300))
                sub = [r for r in fin if r["hash_rank"] < npairs]
                meta["stages"]["final_gate"] = run.run(sub, fin_out, "edit", lg, "final_gate")
        dump(RESULTS / f"gen_meta_{a.model}_gate.json", meta)
    del model
    gc.collect()
    torch.cuda.empty_cache()
    logger.info("done")


if __name__ == "__main__":
    main()
