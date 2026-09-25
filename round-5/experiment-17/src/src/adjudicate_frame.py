#!/usr/bin/env python3
"""Phase 4 frame: draw the 240-row blind adjudication frame BEFORE any adjudication label exists.

Per model x language: 50 edit@1.0 rows, 25 with ASR_row = 1 and 25 with ASR_row = 0 (simple random sampling within
stratum; if a stratum has < 25 rows all are taken and the shortfall is filled from the other stratum), plus 10 orig
rows (SRS). Inclusion weights w = N_stratum / n_stratum are stored in adjudication/_key_<model>.json.
R0 changes (frozen before any label): the frame uses edit@1.0 rows (not lambda_gate) and is drawn PER MODEL
(--model; per-cell RNG seeded by sha1(seed|model|lang)) so the Gemma half can be labelled while GaMS generates.
Blind file adjudication/blind_<model>.jsonl: aid, prompt, response only (order shuffled within model). Condition, dose
and every machine label are hidden in _key_<model>.json; the model identity of a batch is known to the adjudicator."""
from __future__ import annotations

import argparse
import json
import random

from loguru import logger

from common import ADJ, GENS, RESULTS, SEED, dump, read_gens, setup_logging, sha1_int, write_jsonl


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=["gemma_it", "gams3_it"])
    a = ap.parse_args()
    setup_logging("adjudicate_frame")
    m = a.model
    if (ADJ / f"_key_{m}.json").exists():
        raise SystemExit("frame for this model already drawn; frozen")
    rows_all = json.loads((RESULTS / "rows_final_asr_only.json").read_text())  # key -> {model, lang, cond, lambda, asr}
    gens = {r["key"]: r for r in read_gens(GENS / f"{m}.jsonl")}
    frame, key = [], {}
    for L in ("en", "sl"):
        rng = random.Random(sha1_int(f"{SEED}|{m}|{L}"))
        ed = [k for k, v in rows_all.items() if v["model"] == m and v["lang"] == L and v["cond"] == "edit"
              and v["lambda"] == 1.0 and v["max_new"] == 128 and v["asr"] is not None]
        pos = sorted(k for k in ed if rows_all[k]["asr"] == 1)
        neg = sorted(k for k in ed if rows_all[k]["asr"] == 0)
        npos = min(25, len(pos))
        nneg = min(50 - npos, len(neg))
        npos = min(50 - nneg, len(pos))
        sp, sn = rng.sample(pos, npos), rng.sample(neg, nneg)
        orig = sorted(k for k, v in rows_all.items() if v["model"] == m and v["lang"] == L and v["cond"] == "orig"
                      and v["max_new"] == 128 and v["asr"] is not None)
        so = rng.sample(orig, 10)
        for ks, stratum, N in ((sp, "edit_asr1", len(pos)), (sn, "edit_asr0", len(neg)), (so, "orig", len(orig))):
            for k in ks:
                key[k] = {"model": m, "lang": L, "cond": rows_all[k]["cond"], "lambda": rows_all[k]["lambda"],
                          "stratum": stratum, "N_stratum": N, "n_stratum": len(ks), "weight": N / max(1, len(ks))}
                frame.append(k)
    rng = random.Random(sha1_int(f"{SEED}|{m}|shuffle"))
    rng.shuffle(frame)
    blind, amap = [], {}
    pre = "g" if m == "gemma_it" else "m"
    for i, k in enumerate(frame):
        aid = f"{pre}{i:03d}"
        amap[aid] = k
        blind.append({"aid": aid, "prompt": gens[k]["prompt"], "response": gens[k]["response"]})
    write_jsonl(ADJ / f"blind_{m}.jsonl", blind)
    dump(ADJ / f"_key_{m}.json", {"aid_to_key": amap, "frame": key, "seed": SEED,
                                   "rule": "see module docstring; drawn before any adjudication label"})
    logger.info(f"frame {m}: {len(frame)} rows written")


if __name__ == "__main__":
    main()
