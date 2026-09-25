#!/usr/bin/env python3
"""Local open-weight LLM judge (substitute primary / second family; amendment judge_substitution_budget_exhausted).

The frozen judge prompt (common.JUDGE_PROMPT, verbatim) is the user turn; the model's chat template is applied with thinking
disabled; the label is the argmax of the next-token logits over the first token of REFUSE / PARTIAL / COMPLY (a forced
3-way choice, equivalent to greedy decoding restricted to the three labels). p = softmax over those three logits is saved.

Usage:
  python judge_local.py --judge qwen3_8b --set calib     # stratified 1,000 gemini-labelled gemma_it rows (candidate choice)
  python judge_local.py --judge qwen3_8b --set all       # every generation row of both models + trunc64 rows
  python judge_local.py --judge <j> --set second         # frozen stratified 15% sample (judge.build_jobs 'second') of both models
Output: results/judge_local/<judge>.jsonl (append-only, resumable by row_key).
"""
from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from common import JUDGE_PROMPT, JUDGE_PROMPT_SHA, RESULTS, append_jsonl, read_jsonl, setup_logger, sha1_unit
from judge import build_jobs, collect, load_items, row_key

logger = setup_logger("judge_local")
JUDGES = {
    "qwen3_8b": {"repo": "Qwen/Qwen3-8B", "template_kw": {"enable_thinking": False}},
    "llama31_8b": {"repo": "meta-llama/Llama-3.1-8B-Instruct", "template_kw": {}},
    "mistral_7b": {"repo": "mistralai/Mistral-7B-Instruct-v0.3", "template_kw": {}},
    "olmo2_7b": {"repo": "allenai/OLMo-2-1124-7B-Instruct", "template_kw": {}},
}
LAB = ["REFUSE", "PARTIAL", "COMPLY"]
OUTDIR = RESULTS / "judge_local"


def gemini_labels() -> dict:
    out = {}
    for x in read_jsonl(RESULTS / "judge_labels.jsonl"):
        if x["kind"] == "primary" and x["label"] in LAB:
            out[x["row_key"]] = x["label"]
    return out


def calib_rows(rows: list[dict], gem: dict, n: int = 1000) -> list[dict]:
    """stratified (arm x curve x gemini label) sample of gemini-labelled gemma_it rows, fixed by sha1 rank."""
    by = defaultdict(list)
    for r in rows:
        k = row_key(r)
        if r["model"] == "gemma_it" and k in gem:
            by[(r["arm"], r["curve"], gem[k])].append(r)
    for v in by.values():
        v.sort(key=lambda r: sha1_unit(row_key(r) + "|calib"))
    out, i = [], 0
    while len(out) < n and any(i < len(v) for v in by.values()):
        for key in sorted(by):
            if i < len(by[key]) and len(out) < n:
                out.append(by[key][i])
        i += 1
    return out


def label_token_ids(tok) -> list[int]:
    ids = []
    for lab in LAB:
        t = tok(lab, add_special_tokens=False)["input_ids"]
        ids.append(t[0])
    assert len(set(ids)) == 3, f"label first tokens collide: {ids}"
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", required=True, choices=list(JUDGES))
    ap.add_argument("--set", required=True, choices=["calib", "all", "second"])
    ap.add_argument("--tok-budget", type=int, default=24000, help="max padded tokens per forward batch")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    spec = JUDGES[args.judge]
    OUTDIR.mkdir(exist_ok=True)
    out_path = OUTDIR / f"{args.judge}.jsonl"
    done = {r["row_key"] for r in read_jsonl(out_path)} if out_path.exists() else set()

    req = load_items()
    rows = collect()
    tok = AutoTokenizer.from_pretrained(spec["repo"])
    if args.set == "calib":
        jobs = [{"row_key": row_key(r), "content": JUDGE_PROMPT.format(req=req[(r["item_id"], r["arm"])], resp=r["response"])}
                for r in calib_rows(rows, gemini_labels())]
    else:
        from transformers import AutoTokenizer as AT
        gtok = AT.from_pretrained("cjvt/GaMS3-12B-Instruct", revision="1d0b27af5748784482600d24779409e7e1dc9adc")
        J = build_jobs(rows, req, gtok)
        if args.set == "all":
            jobs = [{"row_key": j["row_key"], "content": j["content"]} for j in J["primary"] + J["trunc"]]
        else:
            jobs = [{"row_key": j["row_key"], "content": j["content"], "stratum": j["stratum"]} for j in J["second"]]
    jobs = [j for j in jobs if j["row_key"] not in done]
    if args.limit:
        jobs = jobs[:args.limit]
    logger.info(f"{args.judge} set={args.set}: {len(jobs)} to judge ({len(done)} already done)")
    if not jobs:
        return

    model = AutoModelForCausalLM.from_pretrained(spec["repo"], dtype=torch.bfloat16, device_map="cuda:0")
    model.eval()
    lab_ids = label_token_ids(tok)
    sha = getattr(model.config, "_commit_hash", None)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "left"
    texts = [tok.apply_chat_template([{"role": "user", "content": j["content"]}], tokenize=False, add_generation_prompt=True,
                                     **spec["template_kw"]) for j in jobs]
    enc = [tok(t, add_special_tokens=False)["input_ids"] for t in texts]
    order = sorted(range(len(jobs)), key=lambda i: len(enc[i]))
    t0, buf, n = time.time(), [], 0
    i = 0
    while i < len(order):
        L = len(enc[order[min(i + 1, len(order) - 1)]])
        bs = max(1, args.tok_budget // max(L, 1))
        idx = order[i:i + bs]
        L = max(len(enc[k]) for k in idx)
        bs = max(1, min(len(idx), args.tok_budget // L))
        idx = idx[:bs]
        L = max(len(enc[k]) for k in idx)
        ids = torch.full((len(idx), L), tok.pad_token_id, dtype=torch.long)
        att = torch.zeros((len(idx), L), dtype=torch.long)
        for r, k in enumerate(idx):
            e = enc[k]
            ids[r, L - len(e):] = torch.tensor(e)
            att[r, L - len(e):] = 1
        logits = None
        while logits is None:
            try:
                with torch.inference_mode():
                    logits = model(input_ids=ids.cuda(), attention_mask=att.cuda(), logits_to_keep=1).logits[:, -1, :].float()
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                if len(idx) == 1:
                    raise
                half = max(1, len(idx) // 2)  # OOM halver: shrink this batch and the budget, never drop a row
                logger.warning(f"OOM at batch {len(idx)} x {L} tokens -> {half}")
                idx, ids, att = idx[:half], ids[:half], att[:half]
                args.tok_budget = max(2000, int(args.tok_budget * 0.6))
        sub = logits[:, lab_ids]
        p = torch.softmax(sub, dim=-1).cpu()
        top_any = logits.argmax(-1).cpu()
        for r, k in enumerate(idx):
            j = jobs[k]
            lab = LAB[int(p[r].argmax())]
            buf.append({"row_key": j["row_key"], "judge": spec["repo"], "judge_sha": sha, "label": lab,
                        "p": [round(float(x), 5) for x in p[r]], "label_token_is_top1": int(top_any[r]) in lab_ids,
                        "stratum": j.get("stratum"), "set": args.set, "prompt_sha": JUDGE_PROMPT_SHA})
        n += len(idx)
        i += len(idx)
        if len(buf) >= 500:
            append_jsonl(out_path, buf)
            buf = []
            logger.info(f"  {n}/{len(jobs)} ({n / (time.time() - t0):.1f} rows/s)")
    if buf:
        append_jsonl(out_path, buf)
    logger.info(f"done {n} rows in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
