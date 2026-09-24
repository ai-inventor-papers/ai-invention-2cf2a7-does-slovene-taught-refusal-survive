#!/usr/bin/env python3
"""Render results/analysis.json + gates + audit into results/RESULTS_tables.md (auto-generated tables; the narrative
RESULTS.md at the workspace root cites these numbers)."""
from __future__ import annotations

import json

from common import LABELS, RESULTS

NAME = {"gemma_it": "Gemma-3-12B-IT", "gams3_it": "GaMS3-12B-Instruct", "pew_heretic": "p-e-w/gemma-3-12b-it-heretic",
        "huihui": "huihui-ai/gemma-3-12b-it-abliterated", "mlabonne_v2": "mlabonne/gemma-3-12b-it-abliterated-v2"}


def f(x, n=2):
    if x is None:
        return "–"
    if isinstance(x, (list, tuple)):
        return "[" + ", ".join(f(v, n) for v in x) + "]"
    try:
        return f"{x:.{n}f}"
    except (TypeError, ValueError):
        return str(x)


def main() -> None:
    A = json.loads((RESULTS / "analysis.json").read_text())
    L = ["# Auto-generated result tables (src/make_report.py from results/analysis.json)", "",
         f"Protocol sha256: `{A['protocol_sha256']}`; rows: {A['n_rows']}. Primary judge Q = Qwen3-14B (local, NF4); "
         "second family M = Mistral-Small-24B (local, NF4, pre-registered sample). R = REFUSE; RP = REFUSE or PARTIAL. "
         "No human adjudication; the adjudicator is the executor LLM.", ""]
    for gate in ("gate", "retest"):
        for j in ("qwen3_14b", "mistral24b"):
            p = LABELS / f"{gate}_report_{j}.json"
            if p.exists():
                g = json.loads(p.read_text())
                L += [f"## Judge {gate}: {j} vs archived {'gemini' if gate == 'gate' else 'exp5 Qwen3 (160 tok)'} labels", "",
                      "| cell | n | kappa R | kappa 3-way | agree R | rate gold R | rate judge R |", "|---|---|---|---|---|---|---|"]
                for c, v in g.items():
                    L.append(f"| {c} | {v['n']} | {f(v['kappa_R'])} | {f(v['kappa_3way'])} | {f(v['agree_R'])} | "
                             f"{f(v['rate_gold_R'])} | {f(v['rate_judge_R'])} |")
                L.append("")
    L += ["## C-LAG FINAL: G3 = a_GaMS - a_Gemma (SL-MT log-odds at EN-BT refusal = 50%)", "",
          "| readout | G3 | 95% CI | 90% CI | BCa 95% | SE | MDE | a_Gemma | a_GaMS | support Gemma | support GaMS | perm p |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, g in A.get("G3", {}).items():
        if "G3" not in g:
            continue
        pm = g["per_model"]
        L.append(f"| {k} | {f(g['G3'])} | {f(g['ci95'])} | {f(g['ci90'])} | {f(g.get('bca95'))} | {f(g['se'])} | "
                 f"{f(g['mde'])} | {f(pm['gemma_it']['a'])} | {f(pm['gams3_it']['a'])} | {pm['gemma_it']['support']} | "
                 f"{pm['gams3_it']['support']} | {f(g.get('perm', {}).get('p_two_sided'), 4)} |")
    L += ["", f"Verdict (pre-registered mapping): {A.get('verdict_C_LAG')}", ""]
    g = A.get("G3", {}).get("q_R")
    if g:
        L += ["### Per-step Hautus rates (Q, R) on the CURVE items", "", "| model | " + " | ".join(f"λ={s:g}" for s in g["steps"]) + " |",
              "|---|" + "---|" * len(g["steps"])]
        for m in ("gemma_it", "gams3_it"):
            pm = g["per_model"][m]
            L.append(f"| {NAME[m]} EN-BT | " + " | ".join(f(x) for x in pm["p_en"]) + " |")
            L.append(f"| {NAME[m]} SL-MT | " + " | ".join(f(x) for x in pm["p_L"]) + " |")
        L += ["", "| model | a | b | SL−EN pp at EN 50% | isotonic SL log-odds at EN 50% | EN range |", "|---|---|---|---|---|---|"]
        for m in ("gemma_it", "gams3_it"):
            pm = g["per_model"][m]
            L.append(f"| {NAME[m]} | {f(pm['a'])} | {f(pm['b'])} | {f(pm['L_minus_EN_pp_at_EN50'], 1)} | "
                     f"{f(pm['isotonic_L_logodds_at_EN50'])} | {f(pm['EN_range'])} |")
        L.append("")
    L += ["## RQ2: orig → λ=1 (exact McNemar; Q, R)", "",
          "| model | set | harmful | arm | n | rate orig | rate λ=1 | Δ pp | b (0→1) | c (1→0) | p | relative cut |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in A["mcnemar"].get("q_R", []):
        L.append(f"| {NAME[r['model']]} | {r['set']} | {r['harmful']} | {r['arm']} | {r['n']} | {f(r['rate_orig'], 3)} | "
                 f"{f(r['rate_lam1'], 3)} | {f(r['delta_pp'], 1)} | {r['b_0to1']} | {r['c_1to0']} | {f(r['p_exact'], 4)} | "
                 f"{f(r['rel_cut'], 2)} |")
    L += ["", "## C-MECH: SDT along the curve (Q, R): mean over steps with EN-BT H in [0.3, 0.7]", "",
          "| model | mean Δc | 95% CI | mean Δd′ | 95% CI | signature |", "|---|---|---|---|---|---|"]
    for m, v in A["sdt_curve"]["q_R"].items():
        L.append(f"| {NAME[m]} | {f(v.get('mean_delta_c_mid'))} | {f(v.get('delta_c_ci95'))} | "
                 f"{f(v.get('mean_delta_d_mid'))} | {f(v.get('delta_d_ci95'))} | {v.get('signature', v.get('note'))} |")
    L += ["", "### HARD SDT at orig and λ=1 (all 349 unsafe vs HARDSAFE subset; Q, R)", "",
          "| condition | model | arm | H | FA | d′ | c |", "|---|---|---|---|---|---|---|"]
    for cond, res in A["sdt_lambda1"]["q_R"].items():
        for m in ("gemma_it", "gams3_it"):
            for arm in ("EN_BT", "SL_MT", "L3_MT"):
                v = res.get(m, {}).get(arm)
                if v:
                    L.append(f"| {cond} | {NAME[m]} | {arm} | {f(v['H'])} | {f(v['FA'])} | {f(v['d'])} | {f(v['c'])} |")
        if "DiD_c_SL" in res:
            L.append(f"| {cond} | DiD_c (GaMS − Gemma of c_EN − c_SL) | | | | | {f(res['DiD_c_SL']['est'])} {f(res['DiD_c_SL']['ci95'])} |")
    L += ["", "## C-MOD (reduced two-point; F2-iii): language lag = logit(p_L) − logit(p_EN-BT) on L3 items", "",
          "| readout | language | n items | Gemma lag orig | Gemma lag λ1 | GaMS lag orig | GaMS lag λ1 | G3_2pt | 95% CI | MDE |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in A["two_point"].items():
        for lang, t in v.items():
            if "lags" not in t:
                continue
            L.append(f"| {k} | {lang} | {t['n_items']} | {f(t['lags']['gemma_it']['orig'])} | {f(t['lags']['gemma_it']['edit'])} | "
                     f"{f(t['lags']['gams3_it']['orig'])} | {f(t['lags']['gams3_it']['edit'])} | {f(t['G3_2pt'])} | "
                     f"{f(t['G3_2pt_ci95'])} | {f(t['mde'])} |")
    L += ["", f"Verdict C-MOD: {A.get('verdict_C_MOD')}", "", "## C-EXT: public checkpoints (PUB items; Q, R)", "",
          "| model | n | EN-BT | SL-MT | L3-MT | SL−EN pp [95% CI] | L3−EN pp [95% CI] | HARD Δc(SL) | Δd′(SL) | c-share |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for m, v in A["public"]["q_R"].items():
        if not isinstance(v, dict) or "n_items" not in v:
            continue
        sd = v.get("hard_sdt", {})
        L.append(f"| {NAME.get(m, m)}{' (orig reference)' if m == 'gemma_it' else ''} | {v['n_items']} | "
                 f"{f(v.get('rate_EN_BT'))} | {f(v.get('rate_SL_MT'))} | {f(v.get('rate_L3_MT'))} | "
                 f"{f(v.get('SL_minus_EN_pp'), 1)} {f(v.get('SL_minus_EN_ci95'), 1)} | "
                 f"{f(v.get('L3_minus_EN_pp'), 1)} {f(v.get('L3_minus_EN_ci95'), 1)} | {f(sd.get('delta_c_SL'))} | "
                 f"{f(sd.get('delta_d_SL'))} | {f(sd.get('c_share_SL'))} |")
    L += ["", f"Prediction SL−EN > 5 pp in ≥ 2 checkpoints: {A['public']['q_R'].get('prediction_SL_minus_EN_gt5pp')}", "",
          "## Judge agreement Q vs M (binary R)", "", "| cell | n | κ R | κ 3-way | rate Q | rate M | ≥0.6 |", "|---|---|---|---|---|---|---|"]
    for c, v in A["judge_agreement"].items():
        L.append(f"| {c} | {v['n']} | {f(v['kappa_R'])} | {f(v['kappa_3way'])} | {f(v['rate_q'])} | {f(v['rate_m'])} | {v['pass_0.6']} |")
    L += ["", "## Blind adjudication (executor LLM, NOT human) vs judges", "", "```", json.dumps(A["adjudication"], indent=1), "```",
          "", "## Competence covariates (DESCRIPTIVE)", "", "```",
          json.dumps({k: A["competence"].get(k) for k in ("catastrophic_gate", "scatter_cells", "spearman_acc_vs_lag_DESCRIPTIVE")}, indent=1),
          "```", "", "## MT-noise (EN-BT vs EN-orig at λ=1) and mixed models", "", "```",
          json.dumps({"mt_noise_lam1": A.get("mt_noise_lam1"), "mixed": A.get("mixed")}, indent=1, default=str)[:6000], "```"]
    au = RESULTS / "audit.json"
    if au.exists():
        a = json.loads(au.read_text())
        L += ["", f"## Audit (src/rederive.py): {a['n_pass']}/{a['n_checks']} checks pass; all_pass = {a['all_pass']}", "",
              "```", json.dumps(a["placebos"], indent=1), "```"]
    (RESULTS / "RESULTS_tables.md").write_text("\n".join(L) + "\n")
    print("wrote results/RESULTS_tables.md")


if __name__ == "__main__":
    main()
