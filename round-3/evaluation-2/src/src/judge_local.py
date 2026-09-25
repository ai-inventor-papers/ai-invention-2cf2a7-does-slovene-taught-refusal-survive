#!/usr/bin/env python3
"""Local open-weight refusal judges (MODE L primary / third family; $0): Qwen3-14B and Mistral-Small-24B-Instruct-2501,
NF4 (bitsandbytes, double quant, bf16 compute), frozen exp8 P1 prompt verbatim as the user turn (Qwen: no system turn,
thinking off; Mistral: explicit EMPTY system turn as in exp7), first-token argmax over REFUSE/PARTIAL/COMPLY (asserted
distinct), probabilities stored. Resumable append-only output labels/<judge>.jsonl keyed (row_key, trunc).

Usage: python src/judge_local.py --judge qwen3_14b --sets calib,adjudication [--limit N] [--bs 16] [--time-budget S]
Sets: calib, adjudication, sample25, B_all, A1_native, origharm_native, A1_64, orig_64, (any comma list, in order).
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import time

os.environ.setdefault("HF_HUB_OFFLINE", "1")
import pandas as pd  # noqa: E402
import torch  # noqa: E402


def disable_torch_native_triton() -> str:
    """torch>=2.14 routes some eager ops to Triton kernels that need a C compiler (iter-2 trap); de-register them."""
    try:
        from torch._native import registry as _nr
        _nr.deregister_op_overrides(disable_dsl_names=["triton", "cutedsl", "helion", "nvmath"])
        return "deregistered"
    except (ImportError, AttributeError, RuntimeError, ValueError) as e:
        return f"not_deregistered:{e}"


NATIVE = disable_torch_native_triton()
from common import JUDGE_PROMPT, JUDGE_PROMPT_SHA, LAB3, LABELS, LOCAL_JUDGES, WORK, append_jsonl, read_jsonl, setup_logger  # noqa: E402


def job_rows(d: pd.DataFrame, frames: dict, name: str) -> list[dict]:
    """rows for one set; trunc='native' uses the saved response, '64' the first 64 Gemma-3 tokens."""
    if name == "calib":
        s, tr = d[d.row_key.isin(set(frames["calib"]))], "native"
    elif name == "adjudication":
        s, tr = d[d.row_key.isin(set(frames["adjudication"]))], "native"
    elif name == "sample25":
        s, tr = d[d.row_key.isin(set(frames["sample25"]))], "native"
    elif name == "B_all":
        s, tr = d[(d.curve == "trial") & d.arm.isin(["en_bt", "sl_mt"])], "native"
    elif name == "A1_native":
        s, tr = d[(d.curve == "lambda")], "native"
    elif name == "origharm_native":
        s, tr = d[d.curve.isin(["orig", "harmless_lambda"])], "native"
    elif name == "A1_64":
        s, tr = d[(d.curve == "lambda") & (d.trunc_differs == 1) & d.arm.isin(["en_bt", "sl_mt"])], "64"
    elif name == "orig_64":
        s, tr = d[(d.curve == "orig") & (d.trunc_differs == 1)], "64"
    elif name == "e7H":
        s, tr = pd.read_parquet(WORK / "e7_hard.parquet"), "native"
    else:
        raise ValueError(name)
    out = []
    for r in s[["row_key", "request", "response", "resp64"]].to_dict("records"):
        out.append({"row_key": r["row_key"], "trunc": tr, "set": name,
                    "content": JUDGE_PROMPT.format(req=r["request"], resp=r["response"] if tr == "native" else r["resp64"])})
    return out


def load(judge: str):
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    cfg = LOCAL_JUDGES[judge]
    kw = {"fix_mistral_regex": True} if "mistral" in judge else {}
    tok = AutoTokenizer.from_pretrained(cfg["repo"], revision=cfg["revision"], **kw)
    tok.padding_side = "left"
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                             bnb_4bit_compute_dtype=torch.bfloat16, llm_int8_skip_modules=["lm_head"])
    m = AutoModelForCausalLM.from_pretrained(cfg["repo"], revision=cfg["revision"], quantization_config=bnb,
                                             dtype=torch.bfloat16, device_map="cuda:0", attn_implementation="sdpa").eval()
    return m, tok


def render(tok, judge: str, content: str) -> str:
    sysmsg = LOCAL_JUDGES[judge]["system"]
    msgs = ([] if sysmsg is None else [{"role": "system", "content": sysmsg}]) + [{"role": "user", "content": content}]
    kw = {"enable_thinking": False} if "qwen" in judge else {}
    return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, **kw)


@torch.inference_mode()
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", required=True, choices=list(LOCAL_JUDGES))
    ap.add_argument("--sets", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--bs", type=int, default=16)
    ap.add_argument("--time-budget", type=float, default=1e9, help="seconds; stop submitting new batches after this")
    a = ap.parse_args()
    logger = setup_logger(f"judge_{a.judge}")
    torch.cuda.set_per_process_memory_fraction(0.92)
    out_p = LABELS / f"{a.judge}.jsonl"
    done = {(r["row_key"], r["trunc"]) for r in read_jsonl(out_p)}
    d = pd.read_parquet(WORK / "master.parquet", columns=["row_key", "request", "response", "resp64", "curve", "arm",
                                                          "trunc_differs"])
    frames = json.loads((WORK / "frames.json").read_text())
    t_start = time.time()
    model = tok = None
    for name in a.sets.split(","):
        rows = [r for r in job_rows(d, frames, name) if (r["row_key"], r["trunc"]) not in done]
        if a.limit:
            rows = rows[: a.limit]
        logger.info(f"[{a.judge}] set {name}: {len(rows)} to do (native={NATIVE})")
        if not rows:
            continue
        if model is None:
            t0 = time.time()
            model, tok = load(a.judge)
            lab_ids = [tok.encode(lab, add_special_tokens=False)[0] for lab in LAB3]
            assert len(set(lab_ids)) == 3, f"label first tokens collide: {lab_ids}"
            logger.info(f"loaded {a.judge} in {time.time() - t0:.0f}s vram={torch.cuda.memory_allocated() / 1e9:.1f}GB; "
                        f"label toks {[tok.decode([i]) for i in lab_ids]}")
        for r in rows:
            r["_txt"] = render(tok, a.judge, r["content"])
            r["_len"] = len(r["_txt"])
        rows.sort(key=lambda r: r["_len"])
        logger.info(f"example render: {rows[0]['_txt'][:300]!r}")
        i, bs, t0, n = 0, a.bs, time.time(), 0
        while i < len(rows):
            if time.time() - t_start > a.time_budget:
                logger.warning(f"time budget reached in set {name} at {i}/{len(rows)}")
                return
            b = rows[i:i + bs]
            enc = tok([r["_txt"] for r in b], return_tensors="pt", padding=True, add_special_tokens=False).to("cuda:0")
            try:
                logits = model(**enc, logits_to_keep=1).logits[:, -1, :].float()
            except torch.cuda.OutOfMemoryError:
                del enc
                gc.collect()
                torch.cuda.empty_cache()
                bs = max(1, bs // 2)
                logger.warning(f"OOM -> bs {bs}")
                continue
            top1 = logits.argmax(-1).tolist()
            probs = torch.softmax(logits[:, lab_ids], -1).tolist()
            recs = []
            for r, p, t1 in zip(b, probs, top1):
                recs.append({"row_key": r["row_key"], "trunc": r["trunc"], "set": name, "judge": a.judge,
                             "revision": LOCAL_JUDGES[a.judge]["revision"], "label": LAB3[max(range(3), key=lambda j: p[j])],
                             "p": [round(x, 5) for x in p], "top1_is_label": t1 in lab_ids, "prompt_sha": JUDGE_PROMPT_SHA})
            append_jsonl(out_p, recs)
            i += len(b)
            n += len(b)
            del enc, logits
            if (i // max(1, bs)) % 20 == 0:
                el = time.time() - t0
                logger.info(f"  {name} {i}/{len(rows)} {el:.0f}s ({n / max(el, 1e-9):.2f} rows/s)")
        el = time.time() - t0
        logger.info(f"[{a.judge}] set {name} done: {n} rows in {el:.0f}s ({n / max(el, 1e-9):.2f}/s)")
        done |= {(r["row_key"], r["trunc"]) for r in rows}


if __name__ == "__main__":
    main()
