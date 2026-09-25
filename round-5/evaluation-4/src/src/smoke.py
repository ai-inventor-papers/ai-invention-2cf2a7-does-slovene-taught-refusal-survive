#!/usr/bin/env python3
"""Step 0.3-0.4: input existence check + row-count assertions + smoke tests that reproduce archived raw values
(exp14 OUT_SL Gemma 1.14, dOUT_SL -1.58, SDT DiD_c hi|SLoutput -1.56 / zero -0.76; exp15 G3_R -0.70) from the saved
rows with this repo's own code. Any mismatch > 0.01 -> exit 1 (no paid call on an unreproduced frame)."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import E13, E14, E15, EV2, EV3, INVALID_CELLS, RESULTS, dump, load_e14_rows, read_jsonl, setup_logging, sha256_file
from stats_lib import glm_fit, hautus, logit, sdt

INPUTS = {
    "exp14_rows": E14 / "results/rows_final.jsonl", "exp14_ttj": E14 / "results/labels/ttj_translations.jsonl",
    "exp14_labels": E14 / "results/labels/labels.jsonl", "exp14_compliance": E14 / "results/cells_compliance.json",
    "exp14_analysis": E14 / "results/analysis.json", "exp14_tables": E14 / "results/RESULTS_tables.md",
    "exp14_judge_validity": E14 / "results/judge_validity.json", "exp14_items": E14 / "data/items.jsonl",
    "exp14_sr_templates": E14 / "data/strongreject_judge_templates.json",
    "exp14_human_audit": E14 / "results/human_audit_request.json",
    "exp14_adj_frame_g": E14 / "adjudication/frame_g.json", "exp14_adj_key_g": E14 / "adjudication/_key_g.json",
    "exp14_adj_labels_g": E14 / "adjudication/author_labels_g.json",
    "exp14_stats_core": E14 / "src/stats_core.py",
    "exp15_rows": E15 / "results/rows_final.jsonl", "exp15_ttj": E15 / "results/ttj.jsonl",
    "exp15_analysis": E15 / "results/analysis.json", "exp15_headline": E15 / "results/headline_flat.json",
    "exp15_items": E15 / "data/items.jsonl",
    "eval3_matrices": EV3 / "results/judge_error_matrices_v2.json", "eval3_readout": EV3 / "labels/readout_rows.jsonl.gz",
    "eval3_rubric_v2": EV3 / "prompts/adjudication_rubric_v2.md", "exp13_tier_table": E13 / "results/tier_table.json",
    "eval2_matrices": EV2 / "judge_error_matrices.json",
}
FALLBACK = {"eval2_matrices": "not appended; eval3 v2 records carry the earlier instruments",
            "exp13_tier_table": "exp13 numbers quoted from the plan text only"}
DOSE_CELLS = [("en", "en"), ("en", "sl"), ("en", "hu"), ("sl", "en"), ("sl", "sl"), ("sl", "hu"), ("hu", "en"),
              ("hu", "sl"), ("hu", "hu")]


def inputs_check() -> dict:
    out = {}
    for k, p in INPUTS.items():
        if p.exists():
            out[k] = {"path": str(p).split("3_invention_loop/")[-1], "exists": True, "bytes": p.stat().st_size,
                      "sha256": sha256_file(p)}
        else:
            out[k] = {"path": str(p).split("3_invention_loop/")[-1], "exists": False, "fallback": FALLBACK.get(k, "none")}
    return out


def e14_lag_point(rows: list[dict]) -> dict:
    """exp14 estimator (analysis.py lag_stats) at the point: a = y at x = 0 interpolated between lo and hi; L* = a - b
    with b = y0 - x0; OUT_SL = 0.5[(L*(en,sl) - L*(en,en)) + (L*(sl,sl) - L*(sl,en))]; Hautus rates, logit clip 1e-6."""
    k = Counter()
    n = Counter()
    for r in rows:
        if r["kind"] != "harmful" or r["cond"] != "edit" or r.get("L_primary") is None:
            continue
        key = (r["model"], r["dose"], r["in_lang"], r["out_lang"])
        n[key] += 1
        k[key] += r["L_primary"] == "REFUSE"
    Y = {key: float(logit(hautus(k[key], n[key]))) for key in n}
    out = {}
    for m in ("gemma_it", "gams3_it"):
        x0, xl, xh = Y[(m, "zero", "en", "en")], Y[(m, "lo", "en", "en")], Y[(m, "hi", "en", "en")]
        Ls = {}
        for (i, o) in DOSE_CELLS:
            yl, yh, y0 = Y[(m, "lo", i, o)], Y[(m, "hi", i, o)], Y[(m, "zero", i, o)]
            a = yl + (0 - xl) * (yh - yl) / (xh - xl)
            Ls[(i, o)] = a - (y0 - x0)
        out[f"OUT_SL|{m}"] = 0.5 * ((Ls[("en", "sl")] - Ls[("en", "en")]) + (Ls[("sl", "sl")] - Ls[("sl", "en")]))
        out[f"IN_SL|{m}"] = 0.5 * ((Ls[("sl", "en")] - Ls[("en", "en")]) + (Ls[("sl", "sl")] - Ls[("en", "sl")]))
    out["dOUT_SL"] = out["OUT_SL|gams3_it"] - out["OUT_SL|gemma_it"]
    return out


def e14_sdt_did(rows: list[dict]) -> dict:
    k = Counter()
    n = Counter()
    for r in rows:
        if r["cond"] != "edit" or r.get("L_primary") is None:
            continue
        key = (r["kind"], r["model"], r["dose"], r["in_lang"], r["out_lang"])
        n[key] += 1
        k[key] += r["L_primary"] == "REFUSE"
    out = {}
    for d in ("zero", "hi"):
        per = {}
        for m in ("gemma_it", "gams3_it"):
            c = {}
            for cell in (("en", "sl"), ("en", "en")):
                h = ("harmful", m, d, *cell)
                b = ("benign", m, d, *cell)
                c[cell] = sdt(k[h], n[h], k[b], n[b])
            per[m] = (c[("en", "sl")][0] - c[("en", "en")][0], c[("en", "sl")][1] - c[("en", "en")][1])
        out[f"DiD_c|{d}|SLoutput"] = float(per["gemma_it"][1] - per["gams3_it"][1])
        out[f"DiD_d|{d}|SLoutput"] = float(per["gemma_it"][0] - per["gams3_it"][0])
    return out


def e15_g3() -> float:
    rows = read_jsonl(E15 / "results/rows_final.jsonl")
    sel = [r for r in rows if r["set"] == "BODY" and r["edit"] == "E_exp9" and r["block"] in ("ladder", "fillin")
           and r["arm"] in ("EN_BT", "SL_MT") and r.get("label_primary") is not None]
    a = {}
    for m in ("gemma_it", "gams3_it"):
        k = Counter()
        n = Counter()
        for r in sel:
            if r["model"] != m:
                continue
            key = (r["arm"], round(float(r["lambda"]), 4))
            n[key] += 1
            k[key] += r["label_primary"] == "REFUSE"
        lams = sorted({l for _, l in n if l > 0})
        pe = hautus([k[("EN_BT", l)] for l in lams], [n[("EN_BT", l)] for l in lams])
        a[m] = glm_fit([k[("SL_MT", l)] for l in lams], [n[("SL_MT", l)] for l in lams], pe)[0]
    return a["gams3_it"] - a["gemma_it"]


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("smoke")
    ic = inputs_check()
    dump(ic, RESULTS / "inputs_check.json")
    missing = [k for k, v in ic.items() if not v["exists"]]
    logger.info(f"inputs: {len(ic) - len(missing)}/{len(ic)} present; missing {missing}")
    rows = load_e14_rows()
    c = Counter((r["kind"], r["cond"]) for r in rows)
    harm_items = {r["item_id"] for r in rows if r["kind"] == "harmful"}
    ben_items = {r["item_id"] for r in rows if r["kind"] == "benign"}
    checks = {"n_rows": len(rows) == 18700, "harmful_items_200": len(harm_items) == 200,
              "benign_items_100": len(ben_items) == 100,
              "harmful_edit_10800": c[("harmful", "edit")] == 10800,
              "pew_ext_600x3": c[("harmful", "ext")] == 1800, "rand_800": c[("harmful", "rand")] == 800,
              "mtnoise_800": c[("harmful", "mtnoise")] == 800}
    comp = json.loads((E14 / "results/cells_compliance.json").read_text())
    invalid = sorted(k for k, v in comp.items() if not v.get("pass90"))
    checks["invalid_cells_match_plan"] = sorted(f"{m}|{i}{o}" for m, i, o in INVALID_CELLS) == invalid
    ref = json.loads((E14 / "results/analysis.json").read_text())
    ro = ref["readouts"]
    raw = ro.get("raw") or ro[list(ro)[0]]
    lag = e14_lag_point(rows)
    sd = e14_sdt_did(rows)
    g3 = e15_g3()
    target = {"OUT_SL|gemma_it": 1.1353498544769614, "dOUT_SL": -1.58, "IN_SL|gemma_it": -0.60,
              "DiD_c|hi|SLoutput": -1.56, "DiD_c|zero|SLoutput": -0.76, "exp15_G3_R": -0.70}
    got = {"OUT_SL|gemma_it": lag["OUT_SL|gemma_it"], "dOUT_SL": lag["dOUT_SL"], "IN_SL|gemma_it": lag["IN_SL|gemma_it"],
           "DiD_c|hi|SLoutput": sd["DiD_c|hi|SLoutput"], "DiD_c|zero|SLoutput": sd["DiD_c|zero|SLoutput"],
           "exp15_G3_R": g3}
    # the archived values are rounded to 2 dp in the tables -> compare at 0.01 (+ rounding half-step)
    smoke = {k: {"target": target[k], "got": got[k], "pass": abs(round(got[k], 2) - round(target[k], 2)) <= 0.01}
             for k in target}
    arch_sdt = ref["sdt"]["DiD"]
    smoke["archived_json_DiD_c_hi"] = {"archived": arch_sdt["hi|SLoutput"]["c"]["DiD_gemma_minus_gams"],
                                       "got": sd["DiD_c|hi|SLoutput"]}
    out = {"row_checks": checks, "invalid_cells": invalid, "smoke": smoke, "extra": {**lag, **sd},
           "all_pass": all(checks.values()) and all(v["pass"] for k, v in smoke.items() if "pass" in v)}
    dump(out, RESULTS / "smoke_tests.json")
    logger.info(json.dumps(out, indent=1, default=float))
    if not out["all_pass"]:
        logger.error("SMOKE TESTS FAILED -> STOP")
        sys.exit(1)


if __name__ == "__main__":
    main()
