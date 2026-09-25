#!/usr/bin/env python3
"""P3/P4 (GPU): base-model last-token residuals at all 49 hidden_states layers for every screen prompt
(plain text + BOS, no template), saved as a fp16 array in scratch/ (regenerable). All statistics are computed
on CPU by base_stats.py so the GPU can move on to the next checkpoint.
Usage: python src/base_geometry.py --model pt|gb [--limit N] [--tag smoke]"""
from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np
import torch
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

ROOT = C.ROOT


def screen_rows(limit: int | None = None) -> list[dict]:
    pairs = C.read_jsonl(ROOT / "data/refuseu_pairs.jsonl")
    alp = [r for r in C.read_jsonl(ROOT / "data/alpaca_harmless.jsonl") if r["role"] in ("CONSTRUCT", "SCORE")]
    rows = []
    for p in pairs:
        for lang in ["en", "sl"]:
            rows.append({"uid": f"h|{p['pair_id']}|{lang}", "kind": "harm", "item": p["pair_id"], "lang": lang,
                         "role": p["role"], "text": p[lang], "category": p["category"]})
    for a in alp:
        for lang in ["en", "sl"]:
            rows.append({"uid": f"b|{a['hid']}|{lang}", "kind": "harmless", "item": a["hid"], "lang": lang,
                         "role": a["role"], "text": a[lang], "category": "harmless"})
    if limit:
        # stratified small subset for smoke / mini runs
        sel = []
        for kind in ["harm", "harmless"]:
            for role in ["CONSTRUCT", "SCORE"]:
                for lang in ["en", "sl"]:
                    sel += [r for r in rows if r["kind"] == kind and r["role"] == role and r["lang"] == lang][:limit]
        rows = sel
    return rows


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--tag", default="")
    ap.add_argument("--bs", type=int, default=32)
    ap.add_argument("--pool", default="last", choices=["last", "mean"])
    a = ap.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (120 * 1024**3, 120 * 1024**3))
    out_dir = ROOT / f"results/base_{a.model}{a.tag}"
    out_dir.mkdir(parents=True, exist_ok=True)
    logger.add(ROOT / f"logs/base_geometry_{a.model}{a.tag}.log", rotation="30 MB", level="DEBUG")
    rows = screen_rows(a.limit)
    model, tok = C.load_model(a.model)
    for r in rows:
        r["ids"] = C.plain_ids(tok, r["text"])
    n_layers = len(C.decoder_layers(model))
    logger.info(f"{len(rows)} prompts; {n_layers} decoder layers; max len {max(len(r['ids']) for r in rows)}")
    t0 = time.time()
    # mini-run for throughput
    res, _ = C.residuals_all_layers(model, rows[:64], max_bs=a.bs, pool=a.pool)
    logger.info(f"mini 64 prompts {time.time()-t0:.1f}s")
    t0 = time.time()
    res, _ = C.residuals_all_layers(model, rows, max_bs=a.bs, pool=a.pool)
    logger.info(f"residuals for {len(rows)} prompts in {time.time()-t0:.0f}s")
    X = np.stack([res[r["uid"]] for r in rows])  # [N, L+1, d] fp32 (fp16 overflows on Gemma-3 residuals)
    assert X.shape[1] == n_layers + 1
    scratch = ROOT / f"scratch/resid_{a.model}{a.tag}.npy"
    scratch.parent.mkdir(exist_ok=True)
    np.save(scratch, X)
    meta = [{k: r[k] for k in ["uid", "kind", "item", "lang", "role", "category"]} | {"n_tok": len(r["ids"])} for r in rows]
    C.write_jsonl(out_dir / "resid_index.jsonl", meta)
    # first-token greedy predictions on 20 fixed prompts (quant check / mirror comparisons)
    fixed = [r for r in rows if r["kind"] == "harm" and r["role"] == "CONSTRUCT" and r["lang"] == "en"][:10] + \
            [r for r in rows if r["kind"] == "harm" and r["role"] == "CONSTRUCT" and r["lang"] == "sl"][:10]
    with torch.inference_mode():
        ft = []
        for r in fixed:
            ids = torch.tensor([r["ids"]], device="cuda")
            lg = model(input_ids=ids, logits_to_keep=1).logits[0, -1].float()
            top = torch.topk(lg, 5)
            ft.append({"uid": r["uid"], "top5": top.indices.tolist(), "top5_logit": [round(x, 3) for x in top.values.tolist()]})
    (out_dir / "first_token_fixed20_nf4.json").write_text(json.dumps(ft))
    logger.info(f"saved {scratch} {X.shape} ({X.nbytes/1e9:.2f} GB)")
    C.unload(model)


if __name__ == "__main__":
    main()
