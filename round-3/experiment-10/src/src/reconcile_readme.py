#!/usr/bin/env python3
"""Every headline number quoted in README.md, recomputed from results/analysis.json.
Fails loudly if the prose and the saved results ever diverge. -> results/reconcile_readme.json"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RESULTS  # noqa: E402

J = "surrogate/gemini|R"


def main() -> int:
    A = json.loads((RESULTS / "analysis.json").read_text())
    ag, asv = A["addon"][f"{J}|gemma_it"], A["addon"][f"{J}|gams3_it"]
    ig = A["induction"][f"{J}|gemma_it|exclude"]
    isv = A["induction"][f"{J}|gams3_it|exclude"]
    G, jv = A["geometry"], A["judge_validity"]["adjudication_error_matrix"]
    rq = json.loads((RESULTS / "rq4.json").read_text())
    c = G["contrast_gemma_minus_gams"]
    claims = {
        "Gemma Lag(E0) = 1.98 [1.41, 2.73]": (round(ag["criteria"]["Lag_E0"], 2), 1.98),
        "Gemma E0 R_EN = 0.64": (round(ag["conds"]["E0"]["R_EN_test160"], 2), 0.64),
        "Gemma E0 R_SL = 0.93": (round(ag["conds"]["E0"]["R_SL_test160"], 2), 0.93),
        "GaMS Lag(E0) = -0.33": (round(asv["criteria"]["Lag_E0"], 2), -0.33),
        "G3_op = -2.30": (round(A["G3_op"][J]["G3_op_gams_minus_gemma"], 2), -2.30),
        "G3_op lexicon proxy = -2.31": (round(A["G3_op"]["proxy/lexicon|R"]["G3_op_gams_minus_gemma"], 2), -2.31),
        "f contrast (Gemma-GaMS) = +0.010": (round(c["f"]["own_Lstar"], 3), 0.010),
        "Gemma cos(rEN,rSL) = 0.99": (round(G["gemma_it"]["at_Lstar"]["cos_EN_SL"], 2), 0.99),
        "GaMS cos(rEN,rSL) = 0.99": (round(G["gams3_it"]["at_Lstar"]["cos_EN_SL"], 2), 0.99),
        "Gemma perp_share = 0.13": (round(G["gemma_it"]["at_Lstar"]["perp_share"], 2), 0.13),
        "Gemma L* = 20": (A["dev_decisions"]["gemma_it"]["layer"]["L_star"], 20),
        "u_lang SL alpha50 = 0.65": (round(ig["curves"]["u_lang|sl"]["alpha50"], 2), 0.65),
        "u_lang R_lang = 4.64": (round(ig["criteria"]["u_lang"]["R_lang"], 2), 4.64),
        "u_lang SL refusal at K=1 is 1.00": (round(ig["curves"]["u_lang|sl"]["rate"][ig["levels"].index(1.0)], 2), 1.00),
        "u_SLperp SL censored": (ig["curves"]["u_SLperp|sl"]["censored"], True),
        "u_SLperp EN censored": (ig["curves"]["u_SLperp|en"]["censored"], True),
        "u_SLperp SL AUC = 0.18": (round(ig["curves"]["u_SLperp|sl"]["auc"], 2), 0.18),
        "rEN EN alpha50 = 0.91 (positive control)": (round(ig["curves"]["rEN|en"]["alpha50"], 2), 0.91),
        "GaMS u_lang R_lang = 1.66": (round(isv["criteria"]["u_lang"]["R_lang"], 2), 1.66),
        "A_perp s1.0 cut-random = 0.17": (round(ag["criteria"]["A_perp_s1.0"]["cut_minus_random"], 2), 0.17),
        "A_perp s1.5 cut-random = 0.62": (round(ag["criteria"]["A_perp_s1.5"]["cut_minus_random"], 2), 0.62),
        "A_perp s1.5 EN change = -18.1pp": (round(ag["conds"]["A_perp_s1.5"]["dR_EN_vs_E0_pp"], 1), -18.1),
        "A_perp s1.5 BenignExcess = 1.79": (round(ag["conds"]["A_perp_s1.5"]["BenignExcess"], 2), 1.79),
        "A_perp Lag dose 2.69/1.34/0.45": ([round(ag["conds"][f"A_perp_s{s}"]["Lag"], 2) for s in (0.5, 1.0, 1.5)], [2.69, 1.34, 0.45]),
        "A_SLfull cut-random = 3.97": (round(ag["criteria"]["A_SLfull"]["cut_minus_random"], 2), 3.97),
        "A_SLfull SL refusal = 0.00": (round(ag["conds"]["A_SLfull"]["R_SL_test160"], 2), 0.00),
        "A_SLfull degeneracy = 0.50": (round(ag["conds"]["A_SLfull"]["degenerate_test160"], 2), 0.50),
        "A_SLfull KL ratio = 19x": (round(ag["conds"]["A_SLfull"]["kl_ratio_en_vs_E0"]), 19),
        "A_lang EN refusal = 0.02": (round(ag["conds"]["A_lang"]["R_EN_test160"], 2), 0.02),
        "A_lang KL ratio = 49x": (round(ag["conds"]["A_lang"]["kl_ratio_en_vs_E0"]), 49),
        "surrogate Gemma EN spec = 0.68": (round(jv["gemma_it|en"]["j1"]["spec"], 2), 0.68),
        "surrogate Gemma SL kappa = 0.85": (round(jv["gemma_it|sl"]["j1"]["kappa"], 2), 0.85),
        "surrogate GaMS EN spec = 0.57": (round(jv["gams3_it|en"]["j1"]["spec"], 2), 0.57),
        "surrogate GaMS EN kappa = 0.25": (round(jv["gams3_it|en"]["j1"]["kappa"], 2), 0.25),
        "RQ4 Gemma Estar SL AUROC = 1.00": (round(rq["gemma_it"]["at_Lstar"]["Estar|post"]["sl_mt"]["auroc"], 2), 1.00),
        "RQ4 Gemma EN->SL transfer = 1.00": (round(rq["gemma_it"]["at_Lstar"]["O|post"]["transfer"]["en_bt->sl_mt"], 2), 1.00),
        "RQ4 Gemma SL fixed-probe d' 1.35 -> 0.26": ([round(rq["gemma_it"]["at_Lstar"][f"{s}|post"]["sl_mt"]["dprime_fixed_probe"], 2) for s in ("O", "E1")], [1.35, 0.26]),
        "verdict = neither / neither": (A["final_verdict"], {"gemma_it": "neither", "gams3_it": "neither"}),
    }
    rows = [{"claim": k, "recomputed": got, "in_readme": want, "match": got == want} for k, (got, want) in claims.items()]
    out = {"n": len(rows), "n_match": sum(r["match"] for r in rows), "rows": rows}
    (RESULTS / "reconcile_readme.json").write_text(json.dumps(out, indent=1, default=str))
    for r in rows:
        if not r["match"]:
            print("MISMATCH", r)
    print(f"reconcile: {out['n_match']}/{out['n']} README numbers match results/analysis.json")
    return 0 if out["n_match"] == out["n"] else 1


if __name__ == "__main__":
    sys.exit(main())
