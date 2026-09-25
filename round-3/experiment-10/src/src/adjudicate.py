#!/usr/bin/env python3
"""Blind adjudication sample (plan S8): 40 rows per model x language (160 total), stratified 50/50 by the PRIMARY judge
label (REFUSE vs not), 70% drawn from edited/steered rows (induction alpha > 0, add-on E0/A_*/R_*), 30% from original
rows. The blind file shows ONLY adj_id, prompt and response (order shuffled); condition, alpha, model and judge labels
are in a separate key file that the adjudicator does not read before writing results/adjudication_blind.jsonl.
The adjudicator is the executor agent (author model), NOT a human.

Usage: .venv/bin/python src/adjudicate.py --sample
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import MODEL_ORDER, RESULTS, read_jsonl, row_key, sha1_unit, write_jsonl  # noqa: E402

J1 = "surrogate/gemini"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--model", required=True)
    a = ap.parse_args()
    lab = {r["row_key"]: r["label"] for r in read_jsonl(RESULTS / "judge_labels.jsonl") if r["judge"] == J1}
    import judge as J
    req = J.req_map()
    blind, key = [], []
    for M in [a.model]:
        rows = []
        for f in ("induce.jsonl", "addon.jsonl"):
            rows += [r for r in read_jsonl(RESULTS / "test" / M / f) if r["arm"] != "en_orig" and row_key(r) in lab]
        for lang in ("en", "sl"):
            pool = [r for r in rows if r["lang"] == lang]
            picked = []
            for edited, n_tot in ((True, 28), (False, 12)):
                sub = [r for r in pool if ((r["cond"] not in ("O", "baseline")) == edited)]
                for want_ref in (True, False):
                    cand = sorted([r for r in sub if (lab[row_key(r)] == "REFUSE") == want_ref],
                                  key=lambda r: sha1_unit(row_key(r) + "|adj"))
                    picked += cand[:n_tot // 2]
            for r in picked:
                aid = f"adj{sha1_unit(row_key(r) + 'id'):.12f}"[5:]
                blind.append({"adj_id": aid, "prompt": req[(r["item_id"], r["arm"])], "response": r["response"]})
                key.append({"adj_id": aid, "row_key": row_key(r), "model": M, "lang": lang, "cond": r["cond"],
                            "step": r["step"], "block": r["block"], "j1": lab[row_key(r)]})
    import random
    random.Random(len(blind)).shuffle(blind)  # order shuffled (languages / conditions interleaved)
    write_jsonl(RESULTS / f"adjudication_items_blind_{a.model}.jsonl", blind)
    write_jsonl(RESULTS / f"adjudication_key_{a.model}.jsonl", key)
    print(f"blind items: {len(blind)}")


if __name__ == "__main__":
    main()
