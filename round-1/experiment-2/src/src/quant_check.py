#!/usr/bin/env python3
"""Quantisation sanity check (cut order (1): run only where time allows): greedy first-token agreement between the
NF4 run (first_tok saved in r_score400.jsonl) and an 8-bit (LLM.int8) reload on 20 fixed prompts (first 10 EN + 10 SL
SCORE-400 pairs by pair_id), same template. Usage: python src/quant_check.py --model gams"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    a = ap.parse_args()
    out = C.ROOT / f"results/inst_{a.model}"
    r4 = C.read_jsonl(out / "r_score400.jsonl")
    pairs = {p["pair_id"]: p for p in C.read_jsonl(C.ROOT / "data/refuseu_pairs.jsonl")}
    ids_sorted = sorted({r["pair_id"] for r in r4})[:10]
    nf4 = {(r["pair_id"], r["lang"]): r["first_tok"] for r in r4}
    model, tok = C.load_model(a.model, bits=8)
    res = []
    with torch.inference_mode():
        for pid in ids_sorted:
            for lang in ["en", "sl"]:
                ids = torch.tensor([C.chat_ids(tok, pairs[pid][lang])], device="cuda")
                t8 = int(model(input_ids=ids, logits_to_keep=1).logits[0, -1].argmax())
                res.append({"pair_id": pid, "lang": lang, "nf4": nf4[(pid, lang)], "int8": t8, "agree": nf4[(pid, lang)] == t8,
                            "nf4_tok": tok.decode([nf4[(pid, lang)]]), "int8_tok": tok.decode([t8])})
    agree = sum(r["agree"] for r in res)
    (out / "quant_check.json").write_text(json.dumps({"agree": agree, "n": len(res), "pass_17of20": agree >= 17, "rows": res}, indent=1))
    print(f"{a.model}: NF4 vs int8 first-token agreement {agree}/{len(res)}")
    C.unload(model)


if __name__ == "__main__":
    main()
