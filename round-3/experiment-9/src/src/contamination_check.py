#!/usr/bin/env python3
"""Post-hoc contamination audit of the FINAL probe (P200) against the RESERVED dependency sets.

The dependency dataset art_EG6OpEkGvysx (iter-1 gen_art_dataset_1/full_data_out.json) is read ONLY as an exclusion
reference: its refuseu_eval / refuseu_x_mt / refuseu_gold_calib blocks are never generated on or scored here. For each P200
item we record exact normalised-text matches and the max 8-gram (word) shingle overlap with those blocks, and flag items
with >= 50% 8-gram overlap; analysis.py reports G3 with the flagged items dropped as a sensitivity check.
Writes data/contamination_P200.json.
"""
from __future__ import annotations

import json

from common import DATA, ITER1_DATASET, norm_text, read_jsonl


def grams(t: str, n: int = 8) -> set:
    w = norm_text(t).replace('"', " ").split()
    return {tuple(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}


def main():
    full = json.loads((ITER1_DATASET / "full_data_out.json").read_text())
    ref = {}
    for ds in full["datasets"]:
        if ds["dataset"] not in ("refuseu_eval", "refuseu_x_mt", "refuseu_gold_calib"):
            continue
        for ex in ds["examples"]:
            texts = [ex["input"]] + ([ex["metadata_source_prompt_en"]] if ex.get("metadata_source_prompt_en") else [])
            for t in texts:
                ref.setdefault(ds["dataset"], []).append(t)
    del full
    exact = {k: {norm_text(t).strip('" ') for t in v} for k, v in ref.items()}
    shingles = {}
    for k, v in ref.items():
        for t in v:
            for g in grams(t):
                shingles.setdefault(g, set()).add(k)
    out = {"reference_blocks": {k: len(v) for k, v in ref.items()}, "items": {}}
    for it in read_jsonl(DATA / "probe_P200.jsonl"):
        for arm in ("en_orig", "sl_mt"):
            t = it[arm]
            g = grams(t)
            hit = {k: 0 for k in ref}
            for x in g:
                for k in shingles.get(x, ()):
                    hit[k] += 1
            frac = {k: (v / len(g) if g else 0.0) for k, v in hit.items()}
            ex = [k for k, s in exact.items() if norm_text(t).strip('" ') in s]
            rec = out["items"].setdefault(it["item_id"], {})
            rec[arm] = {"exact_in": ex, "max_8gram_frac": max(frac.values()) if frac else 0.0, "frac_by_block": frac}
    reserved = ("refuseu_eval", "refuseu_x_mt")  # gold_calib = RefusEU train/test gold rows = our own source pool (expected)
    flagged = sorted(i for i, r in out["items"].items()
                     if any(set(r[a]["exact_in"]) & set(reserved) or max(r[a]["frac_by_block"][b] for b in reserved) >= 0.5
                            for a in r))
    out["overlap_with_gold_calib_exact"] = sorted(i for i, r in out["items"].items()
                                                  if any("refuseu_gold_calib" in r[a]["exact_in"] for a in r))
    out["note"] = ("flags = exact or >=50% 8-gram overlap with the RESERVED blocks (refuseu_eval, refuseu_x_mt). Exact hits in "
                   "refuseu_gold_calib are expected: those are RefusEU train/test gold rows, the same pool P200 was drawn from.")
    out["flagged_ge50pct_or_exact"] = flagged
    out["n_flagged"] = len(flagged)
    (DATA / "contamination_P200.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({"n_flagged_reserved": len(flagged), "n_gold_calib_exact": len(out["overlap_with_gold_calib_exact"]),
                      "blocks": out["reference_blocks"]}))


if __name__ == "__main__":
    main()
