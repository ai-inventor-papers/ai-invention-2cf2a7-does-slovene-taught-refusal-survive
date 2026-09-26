#!/usr/bin/env python3
"""Third blind-adjudication sample (amendment 9). Population: D300 FINAL rows of {N5, P5} x {SL-MT, EN-BT} x both models,
stratified on the FROZEN LEXICON hit (judge-independent, known for every row, so the strata have known weights).
N5: 8 rows per stratum; P5: 6 more rows per stratum; rows already adjudicated are excluded. Model identity and all judge
labels are hidden and the order is shuffled by sha1 before the adjudicator sees it.

  python make_adjudication3.py            # writes results/adjudication/sample3.jsonl
  python make_adjudication3.py --show A B # prints rows with adj_id in [A, B) for the adjudicator (prompt + response only)
"""
import hashlib
import sys

from common import RESULTS, read_jsonl, write_jsonl

N_PER_STRATUM = {"N5": 8, "P5": 6}
ADJ = RESULTS / "adjudication"
OUT = ADJ / "sample3.jsonl"


def build() -> None:
    old = {r["key"] for f in ("sample.jsonl", "sample2.jsonl") for r in read_jsonl(ADJ / f)}
    d300 = {it["item_id"] for it in read_jsonl(RESULTS.parent / "data" / "depth600.jsonl") if it.get("in_d300")}
    out = []
    for m in ("gemma_it", "gams3_it"):
        rows = [r for r in read_jsonl(RESULTS / m / "final_gen.jsonl")
                if r["cond"] in N_PER_STRATUM and r["arm"] in ("sl_mt", "en_bt") and r["item_id"] in d300]
        for cond, n in N_PER_STRATUM.items():
            for arm in ("sl_mt", "en_bt"):
                for lex in (1, 0):
                    pop = [r for r in rows if r["cond"] == cond and r["arm"] == arm and r["lex_hit"] == lex]
                    c = sorted([r for r in pop if r["key"] not in old],
                               key=lambda r: hashlib.sha1((r["key"] + "adj3").encode()).hexdigest())
                    for r in c[:n]:
                        out.append({"key": r["key"], "model": m, "arm": arm, "cond": cond, "lex_stratum": lex,
                                    "n_stratum_pop_d300": len(pop), "prompt": r["prompt_text"],
                                    "response": (r["prefix_text"] or "") + r["continuation"]})
    out.sort(key=lambda r: hashlib.sha1((r["key"] + "order3").encode()).hexdigest())
    for i, r in enumerate(out):
        r["adj_id"] = 2000 + i
    write_jsonl(OUT, out)
    print(len(out), "rows")


def show(a: int, b: int) -> None:
    for r in read_jsonl(OUT):
        if a <= r["adj_id"] < b:
            print(f"=== #{r['adj_id']}\nPROMPT: {r['prompt'][:300]}\nRESPONSE: {r['response'][:1200]}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--show":
        show(int(sys.argv[2]), int(sys.argv[3]))
    else:
        build()
