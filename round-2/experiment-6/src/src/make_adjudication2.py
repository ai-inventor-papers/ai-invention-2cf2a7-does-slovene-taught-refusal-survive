#!/usr/bin/env python3
"""Second blind-adjudication sample (amendment 8). Same design as sample.jsonl: FINAL P5 rows of the primary cells
(model x {SL-MT, EN-BT}), stratified on the FROZEN LEXICON hit, which is judge-independent and available for every row,
so the strata have known population weights. Excludes rows already adjudicated. Model identity is hidden and the order
is shuffled by sha1 before the adjudicator sees it."""
import hashlib
import json

from common import RESULTS, read_jsonl, write_jsonl

N_PER_STRATUM = 8
old = {r["key"] for r in read_jsonl(RESULTS / "adjudication" / "sample.jsonl")}
d300 = {it["item_id"] for it in read_jsonl(RESULTS.parent / "data" / "depth600.jsonl") if it.get("in_d300")}
out = []
for m in ("gemma_it", "gams3_it"):
    rows = [r for r in read_jsonl(RESULTS / m / "final_gen.jsonl")
            if r["cond"] == "P5" and r["arm"] in ("sl_mt", "en_bt") and r["item_id"] in d300]
    for arm in ("sl_mt", "en_bt"):
        for lex in (1, 0):
            c = [r for r in rows if r["arm"] == arm and r["lex_hit"] == lex and r["key"] not in old]
            c.sort(key=lambda r: hashlib.sha1((r["key"] + "adj2").encode()).hexdigest())
            for r in c[:N_PER_STRATUM]:
                out.append({"key": r["key"], "model": m, "arm": arm, "cond": "P5", "lex_stratum": lex,
                            "n_stratum_pop": len(c) + sum(1 for k in old if k.startswith(r["item_id"] + "|" + m)),
                            "n_stratum_pop_d300": len(c), "prompt": r["prompt_text"],
                            "response": (r["prefix_text"] or "") + r["continuation"]})
out.sort(key=lambda r: hashlib.sha1((r["key"] + "order2").encode()).hexdigest())
for i, r in enumerate(out):
    r["adj_id"] = 1000 + i
write_jsonl(RESULTS / "adjudication" / "sample2.jsonl", out)
print(len(out), "rows")
with open("/tmp/adj2_view.txt", "w") as f:
    for r in out:
        f.write(f"=== #{r['adj_id']}\nPROMPT: {r['prompt'][:260]}\nRESPONSE: {r['response'][:1100]}\n\n")
