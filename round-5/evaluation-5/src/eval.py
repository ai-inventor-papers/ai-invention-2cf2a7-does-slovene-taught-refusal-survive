#!/usr/bin/env python3
"""Orchestrator for the analysis-only audit (no new generations, no paid judge; OpenRouter spend $0).

Runs Steps 0-7 in order (each module is also runnable on its own from src/), then writes eval_out.json in the
exp_eval_sol_out schema: metrics_agg = headline numbers; datasets = one example per ledger row (plus the ceiling,
KL and decomposition rows), each carrying the verified value, status, source file and JSON path.

Usage:  .venv/bin/python eval.py [--skip-steps]      (--skip-steps only rebuilds eval_out.json from results/*.json)
"""
from __future__ import annotations

import argparse
import json
import resource
import subprocess
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent
sys.path.insert(0, str(WS / "src"))

from loguru import logger  # noqa: E402

import ceiling  # noqa: E402
import check_inputs  # noqa: E402
import decomposition  # noqa: E402
import exp14_tables  # noqa: E402
import kl_excess  # noqa: E402
import ledger  # noqa: E402
import make_tables  # noqa: E402
import owed  # noqa: E402
from common import RES, read_json, rel, setup_logging  # noqa: E402

resource.setrlimit(resource.RLIMIT_AS, (60 * 1024 ** 3, 60 * 1024 ** 3))  # rows_final + readout frame fit well below this

STATUS_CODE = {"SURVIVES": 1.0, "SHRINKS": 2.0, "REVERSES": 3.0, "UNTRACEABLE": 0.0}


def fnum(x):
    return None if x is None else float(x)


def s(x, nd=4):
    if x is None:
        return "NA"
    if isinstance(x, (list, tuple)):
        return "[" + ", ".join(s(v, nd) for v in x) + "]"
    return f"{x:.{nd}f}" if isinstance(x, float) else str(x)


def build_eval_out() -> dict:
    c, k, d = read_json(RES / "ceiling_sensitivity.json"), read_json(RES / "kl_excess.json"), read_json(RES / "decomposition_table.json")
    lg, s6, v = read_json(RES / "correction_ledger.json"), read_json(RES / "step6.json"), read_json(RES / "verify.json")
    e14 = read_json(RES / "exp14_tables_regenerated.json")
    fi = c["fragility_index"]
    pu = c["judge_error"].get("pooled_unedited", {})
    ma = {
        "exp15_G3_orig": c["smoke"]["G3_orig"], "exp15_FI_m": fi["FI_m"], "exp15_FI_0": fi["FI_0"],
        "exp15_prob_did_pp": c["estimators"]["point"]["vi_probability_scale_pp"],
        "exp15_prob_did_pp_ci95_lo": c["bootstrap"]["prob_did_pp"]["ci95"][0], "exp15_prob_did_pp_ci95_hi": c["bootstrap"]["prob_did_pp"]["ci95"][1],
        "exp15_G3_orig_boot_ci95_lo": c["bootstrap"]["hautus"]["ci95"][0], "exp15_G3_orig_boot_ci95_hi": c["bootstrap"]["hautus"]["ci95"][1],
        "exp15_jeffreys_P_G3orig_lt_minus_m": c["estimators"]["jeffreys_posterior"]["P_lt_minus_m"],
        "exp15_jeffreys_P_G3orig_lt_0": c["estimators"]["jeffreys_posterior"]["P_lt_0"],
        "exp15_estimator_min": min(c["estimators"]["point"][x] for x in ("i_hautus_loglinear", "ii_laplace_add1", "iii_half_n_rule_extreme_cells_only", "iv_jeffreys_posterior_mean_of_logit")),
        "exp15_estimator_max": max(c["estimators"]["point"][x] for x in ("i_hautus_loglinear", "ii_laplace_add1", "iii_half_n_rule_extreme_cells_only", "iv_jeffreys_posterior_mean_of_logit")),
        "exp15_gemma_mcnemar_p": c["paired_exact"]["gemma_it"]["mcnemar_exact_p"],
        "exp15_model_perm_p": c["permutation_model_label"]["p_two_sided"],
        "exp15_leave1_max": c["leave_k_items"]["1"]["max"], "exp15_leave3_worst_case": c["leave_k_items"]["3"]["worst_case_remove_gemma_discordant_b"],
        "exp15_expected_mislabels_4cells": pu.get("expected_mislabels_total_4cells", -1),
        "exp15_ceiling_artefact": float(c["verdict"] == "CEILING-ARTEFACT"),
        "kl_exp15_gemma_excess": k["exp15"]["gemma_it"]["point_excess_top_dose"], "kl_exp15_gams_excess": k["exp15"]["gams3_it"]["point_excess_top_dose"],
        "kl_exp14_gemma_excess": k["exp14"]["gemma_it"]["mean"]["point"], "kl_exp14_gemma_ci95_lo": k["exp14"]["gemma_it"]["mean"]["ci95_pct"][0],
        "kl_exp14_gemma_ci95_hi": k["exp14"]["gemma_it"]["mean"]["ci95_pct"][1],
        "kl_exp14_gams_excess": k["exp14"]["gams3_it"]["mean"]["point"], "kl_exp14_gams_ci95_hi": k["exp14"]["gams3_it"]["mean"]["ci95_pct"][1],
        "kl_exp9_gemma_excess": k["exp9"]["gemma_it"]["recomputed_point"], "kl_exp9_gams_excess": k["exp9"]["gams3_it"]["recomputed_point"],
        "kl_rows_no_leakage": sum(1 for r in k["reconciliation"]["rows"] if r.get("verdict") == "NO-LEAKAGE"),
        "kl_rows_undetermined": sum(1 for r in k["reconciliation"]["rows"] if r.get("verdict") == "UNDETERMINED"),
        "kl_rows_point_only": sum(1 for r in k["reconciliation"]["rows"] if r.get("verdict") == "POINT-ONLY"),
        "decomp_rows": d["n_rows"], "decomp_edit_induced": d["status_counts"]["edit-induced"],
        "decomp_baseline": d["status_counts"]["baseline"], "decomp_underdetermined": d["status_counts"]["underdetermined"],
        "exp14_crosscheck_mismatches": e14["crosscheck"]["n_mismatch"],
        "exp14_paper_tables_28_29_values_compared": e14.get("paper_table_diff", {}).get("n_cells_compared"),
        "exp14_paper_tables_28_29_values_differ": e14.get("paper_table_diff", {}).get("n_differ"),
        "crit_rows_total": len(s6["criterion_shift"]["rows"]),
        "crit_rows_invalid_manipulation": sum(1 for r in s6["criterion_shift"]["rows"] if not r.get("manipulation_valid", True)),
        "crit_valid_rows_ci_below_0": sum(1 for r in s6["criterion_shift"]["rows"] if r.get("manipulation_valid", True)
                                          and r.get("harmonised_ci95") and r["harmonised_ci95"][1] < 0),
        "crit_valid_rows_ci_above_0": sum(1 for r in s6["criterion_shift"]["rows"] if r.get("manipulation_valid", True)
                                          and r.get("harmonised_ci95") and r["harmonised_ci95"][0] > 0),
        "ledger_tokens": lg["n_tokens"], "ledger_pointers": lg["n_pointers"],
        "ledger_survives": lg["counts_by_status"].get("SURVIVES", 0), "ledger_shrinks": lg["counts_by_status"].get("SHRINKS", 0),
        "ledger_reverses": lg["counts_by_status"].get("REVERSES", 0), "ledger_untraceable": lg["counts_by_status"].get("UNTRACEABLE", 0),
        "ledger_claim_level_reversals": len(lg["claim_level_reversals"]), "ledger_attribution_errors": len(lg["attribution_errors"]),
        "ledger_placebo_auto_match_rate": lg["placebo_auto_match_rate"],
        "exp13_B_overlap": s6["exp13"]["recomputed"]["B_overlap"], "exp13_C_overlap": s6["exp13"]["recomputed"]["C_overlap"],
        "exp13_never_generated": s6["exp13"]["recomputed"]["never_generated_total"],
        "verify_pass_rate": v["pass_rate"], "verify_n_checks": v["n_checks"], "openrouter_spend_usd": 0.0,
    }
    for body, x in c["extension_eval3_bodies"].items():
        g = x.get("by_label", {}).get("gemini_raw_prim3") if isinstance(x, dict) else None
        if g:
            ma[f"eval3_{body}_G3_orig_gemini"] = g["G3_orig_hautus"]
            ma[f"eval3_{body}_FI_m_gemini"] = g["FI_m"]
    gs = k.get("gpu_recompute_gate")
    if gs:
        ma["kl_gpu_gate_pass"] = float(bool(gs.get("pass")))
    ma = {kk: float(vv) for kk, vv in ma.items() if vv is not None}

    ex_ledger = []
    for p in lg["pointers"]:
        st = p["status"].split(" ")[0]
        ex_ledger.append({
            "input": f"[paper line {p['line']}, cites {p['cited_artifact']}] {p.get('paper_sentence', '')[:600]} || audited number: {p['paper_token']}",
            "output": f"verified {s(p.get('verified_value'))} CI {s(p.get('verified_ci95'))} from {p.get('source_file')} :: {p.get('json_path')}",
            "metadata_claim_id": p["claim_id"], "metadata_match_method": "pointer", "metadata_eval_status": st,
            "metadata_claim_status": p.get("claim_status", ""), "metadata_eval_source_file": p.get("source_file") or "",
            "metadata_eval_json_path": p.get("json_path") or "", "metadata_note": p.get("note", ""),
            "predict_paper_value": p["paper_token"], "predict_verified_value": s(p.get("verified_value")),
            "eval_status_code": STATUS_CODE.get(st, 0.0), "eval_attribution_ok": 1.0 if p.get("attribution_ok") else 0.0,
            "eval_abs_diff": abs(p["paper_value"] - p["verified_value"]) if p.get("verified_value") is not None else -1.0})
    for r in lg["rows"]:
        ex_ledger.append({
            "input": f"[paper line {r['line']}, section '{r['section'][:80]}', cites {r['cited_artifact']}] {r['sentence'][:500]} || audited number: {r['token']}",
            "output": (f"verified {s(r.get('verified_value'))} from {r.get('source_file')} :: {r.get('json_path')}" if r.get("verified_value") is not None
                       else f"UNTRACEABLE ({r['match_method']}; {r.get('n_candidates', 0)} candidate leaves)"),
            "metadata_claim_id": r["claim_id"], "metadata_match_method": r["match_method"], "metadata_eval_status": r["status"],
            "metadata_eval_source_file": r.get("source_file") or "", "metadata_eval_json_path": r.get("json_path") or "",
            "metadata_token_kind": r["kind"], "metadata_superseded_by_pointer": r.get("superseded_by_pointer", ""),
            "predict_paper_value": r["token"], "predict_verified_value": s(r.get("verified_value")),
            "eval_status_code": STATUS_CODE.get(r["status"], 0.0),
            "eval_attribution_ok": 1.0 if r.get("attribution_ok") else 0.0,
            "eval_n_candidates": float(r.get("n_candidates", 0))})
    ex_ceiling = [{
        "input": f"exp15 lambda-0 G3_orig (J1 raw): counts {c['smoke']['counts_rows_final']} of {c['smoke']['n_rows_final']}",
        "output": c["paper_sentence"], "metadata_body": "exp15_ladder", "metadata_label": "J1 raw (local)", "metadata_verdict": c["verdict"],
        "predict_G3_orig": s(c["smoke"]["G3_orig"]), "eval_G3_orig": c["smoke"]["G3_orig"], "eval_FI_m": float(fi["FI_m"]), "eval_FI_0": float(fi["FI_0"])}]
    for body, x in c["extension_eval3_bodies"].items():
        for lab, r in (x.get("by_label", {}) if isinstance(x, dict) else {}).items():
            ex_ceiling.append({"input": f"{body} lambda-0 counts k={r['counts_k']} n={r['counts_n']} under label column {lab}",
                               "output": f"G3_orig {r['G3_orig_hautus']:.3f}; FI_m {r['FI_m']}; FI_0 {r['FI_0']}; verdict {r['verdict']}",
                               "metadata_body": body, "metadata_label": lab, "metadata_verdict": r["verdict"],
                               "predict_G3_orig": s(r["G3_orig_hautus"]), "eval_G3_orig": r["G3_orig_hautus"],
                               "eval_FI_m": float(r["FI_m"]) if r["FI_m"] is not None else -1.0,
                               "eval_FI_0": float(r["FI_0"]) if r["FI_0"] is not None else -1.0})
    ex_kl = []
    for r in k["reconciliation"]["rows"]:
        if "point" not in r:
            continue
        ex_kl.append({"input": f"C5a excess ratio, {r['body']} {r['model']} ({r['prompt_set']}; {r['horizon']}; lambda {r['lambda']}; {r['edit']})",
                      "output": f"excess {r['point']:.3f} CI {s(r.get('ci95'), 3)} -> {r['verdict']}",
                      "metadata_ci_type": r["ci_type"], "metadata_verdict": r["verdict"], "metadata_eval_source_file": r["source"],
                      "predict_excess": s(r["point"]), "eval_excess": r["point"],
                      "eval_ci95_lo": r["ci95"][0] if r.get("ci95") else -1.0, "eval_ci95_hi": r["ci95"][1] if r.get("ci95") else -1.0})
    ex_dec = []
    for r in d["rows"]:
        if "G3" not in r:
            continue
        ge = r["G3_edit"]
        ex_dec.append({"input": f"{r['body']} | readout {r['readout']} | coding {r['coding']} | {r.get('statistic', '')} {r.get('cell', '')}",
                       "output": f"G3 {s(r['G3'].get('point'), 3)} {s(r['G3'].get('ci95'), 3)}; G3_orig {s(r['G3_orig'].get('point'), 3)} "
                                 f"{s(r['G3_orig'].get('ci95'), 3)}; G3_edit {s(ge.get('point'), 3)} {s(ge.get('ci95'), 3)}; status {r.get('decomposition_status')}",
                       "metadata_status": r.get("decomposition_status") or "NA", "metadata_flag": r.get("flag", ""),
                       "metadata_eval_source_file": r["source_file"], "metadata_eval_json_path": r["json_path"],
                       "predict_G3_edit": s(ge.get("point")),
                       "eval_G3_edit": ge["point"] if ge.get("point") is not None else -999.0})
    out = {"metadata": {"evaluation_name": "Tracing every paper number to saved results (iteration-5 audit)",
                        "description": "Analysis-only audit: ceiling fragility of G3_orig, C5a KL excess with intervals, full decomposition, "
                                       "exp14 table regeneration, correction ledger, owed tables, criterion-shift harmonisation, exp13 record, "
                                       "coverage and verdict tables. No new generations except an optional gated GPU KL re-measurement; $0 paid spend.",
                        "protocol": "protocol_eval.yaml (committed before Step 1/2)", "judges": "no judge called; every re-used number names its judge",
                        "human_labels": "none (all adjudication re-used here is author-model, NOT human)",
                        "status_code_map": STATUS_CODE},
           "metrics_agg": ma,
           "datasets": [{"dataset": "iter4_paper_correction_ledger", "examples": ex_ledger},
                        {"dataset": "ceiling_fragility_G3_orig", "examples": ex_ceiling},
                        {"dataset": "c5a_kl_excess_reconciliation", "examples": ex_kl},
                        {"dataset": "g3_decomposition_table", "examples": ex_dec}]}
    return out


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-steps", action="store_true")
    a = ap.parse_args()
    setup_logging("eval")
    if not a.skip_steps:
        check_inputs.main()
        c = ceiling.main()
        k = kl_excess.main()
        decomposition.main(c)
        exp14_tables.main()
        lg = ledger.main(c)
        owed.main(c, k, lg)
        r = subprocess.run([sys.executable, str(WS / "verify/verify.py")], capture_output=True, text=True, timeout=1800)
        logger.info(f"verify: {r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-500:]}")
        make_tables.main()
    out = build_eval_out()
    (WS / "eval_out.json").write_text(json.dumps(out, indent=1))
    logger.info(f"wrote eval_out.json: {len(out['metrics_agg'])} metrics, "
                f"{sum(len(dd['examples']) for dd in out['datasets'])} examples ({rel(WS / 'eval_out.json')})")


if __name__ == "__main__":
    main()
