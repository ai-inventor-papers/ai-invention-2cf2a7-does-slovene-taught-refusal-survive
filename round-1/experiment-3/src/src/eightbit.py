#!/usr/bin/env python3
"""Tier-2 precision sanity check (spec (2)): greedy FIRST-token agreement NF4 vs LLM.int8 on 20 fixed prompts
(10 EN + 10 SL CONSTRUCT-200 prompts), batch-1, plus s agreement. Writes results/eightbit_{model}.json."""
from __future__ import annotations

import argparse
import gc
import json

import numpy as np
import torch
from loguru import logger

from common import DATA, RES, read_jsonl, setup_logging
from engine import Engine


def first_tokens(E: Engine, items) -> tuple[list[str], list[float]]:
    toks, ss = [], []
    for p, lg in items:
        ids = E.encode_prompt(p)[0]
        t, _, si = E.run_batch([ids], lg, 1, True)
        toks.append(t[0]); ss.append(float(si["s"][0]))
    return toks, ss


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    a = ap.parse_args()
    setup_logging(f"eightbit_{a.model}")
    c = read_jsonl(DATA / "construct200.jsonl")
    items = [(p["prompt_en"], "en") for p in c[100:110]] + [(p["prompt_sl"], "sl") for p in c[100:110]]
    out = {}
    for q in ("nf4", "int8"):
        E = Engine(a.model, quant=q)
        out[q] = first_tokens(E, items)
        E.close(); del E; gc.collect(); torch.cuda.empty_cache()
    agree = [x == y for x, y in zip(out["nf4"][0], out["int8"][0])]
    res = {"model": a.model, "n": len(items), "first_token_agree": int(sum(agree)),
           "s_mean_abs_diff": float(np.mean(np.abs(np.array(out["nf4"][1]) - np.array(out["int8"][1])))),
           "s_corr": float(np.corrcoef(out["nf4"][1], out["int8"][1])[0, 1]),
           "nf4_first": out["nf4"][0], "int8_first": out["int8"][0]}
    (RES / f"eightbit_{a.model}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    logger.info(f"8-bit check {a.model}: {res['first_token_agree']}/20 first tokens agree; s corr {res['s_corr']:.3f}")


if __name__ == "__main__":
    main()
