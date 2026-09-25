#!/usr/bin/env python3
"""STEP 3 - full G3 / G3_orig / G3_edit / slope decomposition table: one row per (body, readout), each value pulled
from its own saved file (never re-estimated here); NA where a readout does not exist; no invented CIs."""
from __future__ import annotations

import numpy as np
from loguru import logger

from common import EVAL3, EXP14, EXP15, M, RES, read_json, rel, setup_logging, write_json

NA = None


def _eval3_stat(d: dict | None) -> dict:
    if not d or "est" not in d:
        return {"point": NA, "ci95": NA, "ci90": NA, "mde": NA, "verdict": NA}
    return {"point": d.get("est"), "ci95": d.get("CI95"), "ci90": d.get("CI90"), "mde": d.get("MDE"), "verdict": d.get("verdict")}


def _e15_stat(d: dict | None) -> dict:
    if not d or "point" not in d:
        return {"point": NA, "ci95": NA, "ci90": NA, "mde": NA, "verdict": NA}
    return {"point": d["point"], "ci95": d.get("ci95"), "ci90": d.get("ci90"), "mde": d.get("mde"), "verdict": NA}


def _e14_stat(d: dict | None) -> dict:
    if not d or "est" not in d:
        return {"point": NA, "ci95": NA, "ci90": NA, "mde": NA, "verdict": NA}
    return {"point": d["est"], "ci95": d.get("ci95"), "ci90": d.get("ci90"), "mde": d.get("mde"), "verdict": NA}


def status(g3o: dict, g3e: dict) -> str:
    e95, e90, o95 = g3e.get("ci95"), g3e.get("ci90"), g3o.get("ci95")
    if e95 and g3e["point"] is not None and (e95[0] > 0 or e95[1] < 0) and abs(g3e["point"]) >= M / 2:
        return "edit-induced"
    if o95 and e90 and (o95[0] > 0 or o95[1] < 0) and -M < e90[0] and e90[1] < M:
        return "baseline"
    return "underdetermined"


def eval3_rows() -> list[dict]:
    p = EVAL3 / "results/recompute.json"
    if not p.exists():
        return [{"body": "eval3 bodies", "status": "UNTRACEABLE: recompute.json missing"}]
    cv = read_json(p)["curves"]
    rows = []
    for key, c in cv.items():
        if key.startswith("_") or not isinstance(c, dict):
            continue
        body, readout, coding = key.split("|")
        if body == "exp10_op":
            g3, g3o, g3e = (_eval3_stat(c.get(k)) for k in ("G3_op", "G3_op_orig", "G3_op_edit"))
            stat_name = "G3_op (operating point)"
        else:
            g3, g3o, g3e = (_eval3_stat(c.get(k)) for k in ("G3", "G3_orig", "G3_edit"))
            stat_name = "G3 (curve)"
        if g3["point"] is None and g3o["point"] is None:
            rows.append({"body": body, "readout": readout, "coding": coding, "status_note": c.get("status", "no estimate saved"),
                         "source_file": rel(p), "json_path": f"curves/{key}"})
            continue
        bg, bs = _eval3_stat(c.get("b_gemma_it")), _eval3_stat(c.get("b_gams3_it"))
        rows.append({"body": body, "readout": readout, "coding": coding, "statistic": stat_name, "G3": g3, "G3_orig": g3o,
                     "G3_edit": g3e, "b_Gemma": bg, "b_GaMS": bs,
                     "b_diff": {"point": (bs["point"] - bg["point"]) if bs["point"] is not None and bg["point"] is not None else NA,
                                "ci95": NA, "note": "CI NA: per-draw slopes were not saved (work/boot_draws.npz holds G3/G3_orig/G3_edit/IG only)"},
                     "judge": {"raw_primary": "paid gemini-2.5-flash (P1)", "RG": "gemini + Rogan-Gladen (author-model adjudication)",
                               "PPI": "gemini + PPI++ (author-model adjudication)", "second_gpt41mini_IPW": "paid gpt-4.1-mini (IPW sample)",
                               "ttj": "translate-then-judge (J1 on NLLB English, AM2)", "asr_noharm": "StrongREJECT-style ASR (gemini)"}
                     .get(readout, readout.replace("archived_arch_", "archived local judge: ")),
                     "source_file": rel(p), "json_path": f"curves/{key}"})
    return rows


def exp15_rows(an: dict) -> list[dict]:
    rows = []
    src = rel(EXP15 / "results/analysis.json")
    for coding in ("R", "RP"):
        h = an["headline"].get(coding, {})
        pm = h.get("per_model", {})
        for rd in ("RAW", "RG", "PPI", "second_family_IPW"):
            if rd not in h:
                continue
            x = h[rd]
            g3, g3o, g3e = (_e15_stat(x.get(k)) for k in ("G3", "G3_orig", "G3_edit"))
            bg = _e15_stat(pm.get("gemma_it", {}).get("b")) if rd == "RAW" else {"point": NA, "ci95": NA}
            bs = _e15_stat(pm.get("gams3_it", {}).get("b")) if rd == "RAW" else {"point": NA, "ci95": NA}
            rows.append({"body": "exp15_ladder", "readout": rd, "coding": coding, "statistic": "G3 (curve)", "G3": g3,
                         "G3_orig": g3o, "G3_edit": g3e, "b_Gemma": bg, "b_GaMS": bs,
                         "b_diff": {"point": (bs["point"] - bg["point"]) if bs.get("point") is not None and bg.get("point") is not None else NA,
                                    "ci95": NA, "note": "CI NA: slope draws not saved jointly"},
                         "judge": {"RAW": "local J1 (mdeberta distilled from gemini; fallback readout)", "RG": "J1 + Rogan-Gladen",
                                   "PPI": "J1 + PPI", "second_family_IPW": "paid gemini-2.5-flash second reader (IPW)"}[rd],
                         "source_file": src, "json_path": f"headline/{coding}/{rd}",
                         "notes": "RP == R (J1 emits no PARTIAL)" if coding == "RP" else ""})
    t = an.get("ttj", {}).get("R", {})
    if t.get("available"):
        rows.append({"body": "exp15_ladder", "readout": "TTJ", "coding": "R", "statistic": "G3 (curve)",
                     "G3": {"point": t["G3"], "ci95": t.get("G3_ci95"), "ci90": NA, "mde": NA, "verdict": NA},
                     "G3_orig": {"point": t["G3_orig"], "ci95": t.get("G3_orig_ci95"), "ci90": NA, "mde": NA, "verdict": NA},
                     "G3_edit": {"point": t["G3_edit"], "ci95": t.get("G3_edit_ci95"), "ci90": NA, "mde": NA, "verdict": NA},
                     "b_Gemma": {"point": t["per_model"]["gemma_it"]["b"], "ci95": NA},
                     "b_GaMS": {"point": t["per_model"]["gams3_it"]["b"], "ci95": NA},
                     "b_diff": {"point": t["per_model"]["gams3_it"]["b"] - t["per_model"]["gemma_it"]["b"], "ci95": NA},
                     "judge": "translate-then-judge (J1 on NLLB English)", "source_file": src, "json_path": "ttj/R"})
    ra = an.get("random_arm", {})
    for rk, v in ra.get("by_rank", {}).items():
        rows.append({"body": "exp15_random_arm", "readout": f"rank{rk} random vs Heretic at matched lambda", "coding": "R",
                     "statistic": "G3_edit_rand vs G3_edit_heretic_lambda_matched",
                     "G3": {"point": NA}, "G3_orig": {"point": NA},
                     "G3_edit": {"point": v.get("G3_edit_heretic_lambda_matched"), "ci95": v.get("G3_edit_heretic_ci95"), "ci90": NA},
                     "G3_edit_random": {"point": v.get("G3_edit_rand"), "ci95": v.get("G3_edit_rand_ci95")},
                     "lambdas": {m: v["per_model"][m]["lambda"] for m in v.get("per_model", {})},
                     "b_Gemma": {"point": NA}, "b_GaMS": {"point": NA}, "b_diff": {"point": NA},
                     "judge": "local J1", "source_file": src, "json_path": f"random_arm/by_rank/{rk}"})
    return rows


def exp14_rows() -> list[dict]:
    p = EXP14 / "results/analysis.json"
    if not p.exists():
        return [{"body": "exp14", "status": "UNTRACEABLE"}]
    an = read_json(p)
    comp = an.get("compliance_gate", {})
    rows = []
    for rd, R in an.get("readouts", {}).items():
        for cell in ("slsl", "ensl", "husl", "enen", "slen", "enhu", "huhu", "slhu", "huen"):
            g3 = R.get(f"G3|{cell}")
            g3e = R.get(f"G3edit|{cell}")
            if g3 is None and g3e is None:
                continue
            s3, se = _e14_stat(g3), _e14_stat(g3e)
            g3o = {"point": (s3["point"] - se["point"]) if s3["point"] is not None and se["point"] is not None else NA,
                   "ci95": NA, "ci90": NA, "note": "derived G3 - G3_edit (point only; not saved)"}
            cg = comp.get(f"gams3_it|{cell}", {})
            flag = "" if cg.get("pass90", True) else "INVALID-MANIPULATION (GaMS output-language compliance < 0.90)"
            rows.append({"body": "exp14_grid", "readout": rd, "coding": rd.split("_")[-1], "statistic": f"G3 at L* ({cell})",
                         "cell": cell, "G3": s3, "G3_orig": g3o, "G3_edit": se,
                         "b_Gemma": {"point": NA}, "b_GaMS": {"point": NA}, "b_diff": {"point": NA},
                         "gams_compliance": cg.get("compliance"), "flag": flag,
                         "judge": {"raw_R": "local J1", "raw_RP": "local J1 (RP)", "ttj_R": "translate-then-judge",
                                   "second_R": "second reader", "rg_R": "J1 + RG (degenerate)", "ppi_R": "J1 + PPI++"}.get(rd, rd),
                         "source_file": rel(p), "json_path": f"readouts/{rd}/G3|{cell} ; readouts/{rd}/G3edit|{cell}"})
    return rows


def main(ceiling: dict | None = None) -> dict:
    setup_logging("decomposition")
    an15 = read_json(EXP15 / "results/analysis.json")
    rows = eval3_rows() + exp15_rows(an15) + exp14_rows()
    cver = {}
    if ceiling:
        cver["exp15_ladder"] = ceiling.get("verdict")
        for body, v in ceiling.get("extension_eval3_bodies", {}).items():
            if isinstance(v, dict):
                g = v.get("by_label", {}).get("gemini_raw_prim3", {})
                cver[body] = g.get("verdict")
    for r in rows:
        if "G3_edit" in r and "G3_orig" in r and r["G3_edit"].get("point") is not None:
            r["decomposition_status"] = status(r["G3_orig"], r["G3_edit"])
        else:
            r["decomposition_status"] = NA
        r["ceiling_verdict_G3_orig"] = cver.get(r.get("body"))
        if r["decomposition_status"] == "edit-induced":
            r["edit_direction"] = ("lag direction (G3_edit < 0: the edit removes MORE Slovene refusal in GaMS3)"
                                   if r["G3_edit"]["point"] < 0 else "anti-lag direction (G3_edit > 0)")
    ge = [r["G3_edit"]["point"] for r in rows if r.get("G3_edit", {}).get("point") is not None
          and r.get("coding") in ("R",) and not r.get("flag")]
    v15 = an15["verdict"]
    corrections = {
        "parallel_curves_claim": {"paper_said": "parallel curves (both slopes ~1)",
                                  "verified": {"b_Gemma": an15["headline"]["R"]["per_model"]["gemma_it"]["b"],
                                               "b_GaMS": an15["headline"]["R"]["per_model"]["gams3_it"]["b"]},
                                  "replacement": "report both slopes with CIs; b_diff CI not saved -> no 'parallel' claim"},
        "mde_attribution": {"paper_said": "MDE 0.42 for G3_edit",
                            "verified_MDE_G3": an15["headline"]["R"]["RAW"]["G3"]["mde"],
                            "verified_MDE_G3_edit": an15["headline"]["R"]["RAW"]["G3_edit"]["mde"],
                            "verified_abs_G3_edit_bound_90": v15.get("abs_G3_edit_bound_90"),
                            "source": rel(EXP15 / "results/analysis.json") + " :: headline/R/RAW/*/mde ; verdict/abs_G3_edit_bound_90"}}
    res = {"rows": rows, "n_rows": len(rows),
           "G3_edit_range_R_valid_rows": [min(ge), max(ge)] if ge else None,
           "status_counts": {s: sum(1 for r in rows if r.get("decomposition_status") == s)
                             for s in ("edit-induced", "baseline", "underdetermined")},
           "edit_induced_by_direction": {
               "lag_valid_manipulation": [f"{r['body']}|{r['readout']}|{r['coding']}|{r.get('cell', '')}" for r in rows
                                          if r.get("edit_direction", "").startswith("lag") and not r.get("flag")],
               "lag_invalid_manipulation": [f"{r['body']}|{r['readout']}|{r['coding']}|{r.get('cell', '')}" for r in rows
                                            if r.get("edit_direction", "").startswith("lag") and r.get("flag")],
               "anti_lag": [f"{r['body']}|{r['readout']}|{r['coding']}|{r.get('cell', '')}" for r in rows
                            if r.get("edit_direction", "").startswith("anti")]},
           "note_rg": "exp14 rg_R rows are numerically degenerate (exp14 rg_stability.degenerate = True); do not cite",
           "corrections": corrections,
           "rule": "edit-induced: G3_edit CI95 excl 0 & |G3_edit|>=m/2; baseline: G3_orig CI95 excl 0 & G3_edit CI90 within +-m; else underdetermined"}
    logger.info(f"decomposition rows {len(rows)} status {res['status_counts']} G3_edit range {res['G3_edit_range_R_valid_rows']}")
    write_json(RES / "decomposition_table.json", res)
    return res


if __name__ == "__main__":
    import sys
    c = read_json(RES / "ceiling_sensitivity.json") if (RES / "ceiling_sensitivity.json").exists() else None
    main(c)
    sys.exit(0)
