#!/usr/bin/env python3
"""Render every markdown table / paste-ready insert and the figures FROM THE RESULTS JSON ONLY (no hand-typed numbers).
Re-runnable after the iteration-5 experiments finish (the verdict table's PENDING rows refresh via src/owed.py)."""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from loguru import logger  # noqa: E402

from common import FIG, M, RES, read_json, setup_logging  # noqa: E402

plt.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42, "font.size": 9})


def f(x, nd=2):
    if x is None:
        return "NA"
    if isinstance(x, (list, tuple)):
        return "[" + ", ".join(f(v, nd) for v in x) + "]"
    if isinstance(x, bool):
        return str(x)
    return f"{x:.{nd}f}" if isinstance(x, float) else str(x)


def ceiling_md(c: dict) -> str:
    s, fi, pv, ls, es, bt = c["smoke"], c["fragility_index"], c["paired_exact"], c["leave_k_items"], c["estimators"], c["bootstrap"]
    L = ["# Step 1 - ceiling sensitivity of exp15's baseline component G3_orig\n",
         f"_{c['post_hoc_label']}_\n", f"**Verdict: {c['verdict']}.** {c['paper_sentence']}\n",
         "## Lambda-0 counts (J1 raw, R coding; smoke test vs analysis.json steps_R)\n",
         "| cell | k refuse / n | rate | Hautus logit |", "|---|---|---|---|"]
    from common import hautus_logit
    for cell in ("gemma_en", "gemma_sl", "gams_en", "gams_sl"):
        k, n = s["counts_rows_final"][cell], s["n_rows_final"][cell]
        L.append(f"| {cell} | {k:.0f} / {n:.0f} | {k / n:.4f} | {float(hautus_logit(k, n)):.3f} |")
    L.append(f"\nM0_Gemma {s['M0_gemma']:.5f}, M0_GaMS {s['M0_gams']:.5f}, G3_orig {s['G3_orig']:.5f} (saved {s['G3_orig_saved']:.5f}; "
             f"smoke {'PASS' if s['pass'] else 'FAIL'}).\n")
    L.append("## 1a Fragility index (exact enumeration of single-label flips)\n")
    L.append(f"FI_m = **{fi['FI_m']}** (flips to bring G3_orig inside (-{M}, +{M})), FI_0 = **{fi['FI_0']}** (flips to reach zero, i.e. a sign change).\n")
    L.append("| flips | best reachable G3_orig | cheapest deltas |\n|---|---|---|")
    for t in fi["trajectory"]:
        L.append(f"| {t['flips']} | {t['best_G3_orig']:.3f} | {t['deltas']} |")
    L.append("\nOther estimators: " + "; ".join(f"{k}: G3_orig {v['G3_orig']:.3f}, FI_m {v['FI_m']}, FI_0 {v['FI_0']}"
                                                for k, v in c["fragility_other_estimators"].items()))
    L.append("\n## 1b Paired exact view (same 300 items in both arms)\n")
    L.append("| model | b (SL refuse, EN not) | c (EN refuse, SL not) | McNemar exact p | SL-EN pp [Newcombe 95%] | ln(b/c) [exact 95%] |")
    L.append("|---|---|---|---|---|---|")
    for m, v in pv.items():
        L.append(f"| {m} | {v['b_SLrefuse_ENnot']} | {v['c_ENrefuse_SLnot']} | {v['mcnemar_exact_p']:.3f} | {v['pp_SL_minus_EN']:.2f} "
                 f"{f(v['newcombe_paired_ci_pp'])} | {v['cond_logit_ln_b_over_c']:.2f} {f(v['cond_logit_exact_ci'])} |")
    L.append(f"\nProbability-scale DiD = {es['point']['vi_probability_scale_pp']:.2f} pp, item-bootstrap 95% CI {f(bt['prob_did_pp']['ci95'])}.\n")
    L.append("## 1c Leave-k-items (items removed from both models and arms)\n")
    L.append("| k | mode | min | p05 | p50 | p95 | max | share inside m | worst case (drop Gemma discordant-b items) |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for k, v in ls.items():
        L.append(f"| {k} | {v['mode']} | {v['min']:.3f} | {v['p05']:.3f} | {v['p50']:.3f} | {v['p95']:.3f} | {v['max']:.3f} | "
                 f"{v['share_inside_m']:.4f} | {f(v['worst_case_remove_gemma_discordant_b'], 3)} |")
    L.append("\n## 1d/1e Genuinely different extreme-proportion estimators (item bootstrap B=2000)\n")
    L.append(f"_{es['identity_note']}_\n")
    L.append("| estimator | G3_orig point | bootstrap 95% CI | share of draws inside m |\n|---|---|---|---|")
    bmap = {"i_hautus_loglinear": "hautus", "ii_laplace_add1": "laplace", "iii_half_n_rule_extreme_cells_only": "half_n",
            "iv_jeffreys_posterior_mean_of_logit": "jeffreys_logit_mean", "v_paired_conditional_logit_diff": "cond_logit_diff",
            "vi_probability_scale_pp": "prob_did_pp"}
    for k, v in es["point"].items():
        b = bt.get(bmap[k], {})
        L.append(f"| {k} | {v:.3f} | {f(b.get('ci95'))} | {f(b.get('share_draws_inside_m'))} |")
    jp = es["jeffreys_posterior"]
    L.append(f"\nJeffreys posterior of G3_orig ({jp['n_draws']} draws): mean {jp['mean']:.3f}, 95% CrI {f(jp['cri95'])}, "
             f"P(G3_orig < -m) = {jp['P_lt_minus_m']:.3f}, P(G3_orig < 0) = {jp['P_lt_0']:.3f}.")
    p = c["permutation_model_label"]
    L.append(f"\nModel-label permutation (within item, {p['n_perm']} draws): null mean {p['null_mean']:.3f}, sd {p['null_sd']:.3f}, "
             f"two-sided p = {p['p_two_sided']:.4f}.\n")
    je = c["judge_error"]
    L.append("## 1f Expected judge-error count vs fragility (Walsh-style comparison)\n")
    if je.get("pooled_unedited"):
        pu = je["pooled_unedited"]
        L.append(f"Pooled unedited J1 validation (author-model adjudication, NOT human): Se {pu['Se']:.2f} (n+ {pu['n_pos']}), "
                 f"Sp {pu['Sp']:.2f} (n- {pu['n_neg']}, Wilson {f(pu['Sp_ci_wilson'])}). Expected mislabels over the four lambda-0 "
                 f"cells: {pu['expected_mislabels_total_4cells']:.1f} vs FI_m = {fi['FI_m']}.")
    L.append(f"\n_{je['caveat']}_\n")
    L.append("## 1g Extension to every eval3 body (lambda 0; smoke-tested against eval3 recompute.json)\n")
    L.append("| body | label column | k/n (GemmaEN, GemmaSL, GaMSEN, GaMSSL) | G3_orig | FI_m | FI_0 | estimator range | prob DiD pp [95%] | verdict |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for body, v in c["extension_eval3_bodies"].items():
        if not isinstance(v, dict):
            continue
        for lab, r in v.get("by_label", {}).items():
            kn = ", ".join(f"{r['counts_k'][x]:.0f}/{r['counts_n'][x]:.0f}" for x in ("gemma_en", "gemma_sl", "gams_en", "gams_sl"))
            L.append(f"| {body} | {lab} | {kn} | {r['G3_orig_hautus']:.3f} | {r['FI_m']} | {r['FI_0']} | {f(r['estimator_range'])} | "
                     f"{r['prob_did_pp']:.2f} {f(r.get('prob_did_pp_ci95_item_boot_1000'), 1)} | {r['verdict']} |")
    L.append("\nNote: gpt41mini_sec3 counts use the IPW-sampled second-reader subset unweighted (descriptive only).")
    return "\n".join(L) + "\n"


def kl_md(k: dict) -> str:
    L = ["# Step 2 - C5a excess first-token KL ratio (SL/EN, edit vs norm-matched random)\n", f"Estimator: {k['estimator']}\n",
         f"_{k['post_hoc_label']}_\n", "## 2a exp15 points (saved means only)\n",
         "| model | lambda | E ratio SL/EN | pooled random ratio | excess (pooled) | per-seed excess | excess on medians |", "|---|---|---|---|---|---|---|"]
    for m in ("gemma_it", "gams3_it"):
        for r in k["exp15"][m]["per_lambda"]:
            L.append(f"| {m} | {r['lambda']} | {r['E_ratio']:.3f} | {r['rand_ratio_pooled']:.3f} | {r['excess_pooled']:.3f} | "
                     + ", ".join(f"{s}: {v:.3f}" for s, v in r["excess_per_seed"].items()) + f" | {f(r.get('excess_pooled_median'), 3)} |")
        e = k["exp15"][m]
        L.append(f"| {m} | range | | | {f(e['sensitivity_range_seed_and_dose'], 3)} | {e['range_label']} | |")
    g = k["exp15"]["gemma_it"]["top_dose"]
    L.append(f"\nRaw KL for the real edit at Gemma's top dose: SL {g['raw_E_sl']:.3f} vs EN {g['raw_E_en']:.3f}.\n")
    L.append("## 2b Item bootstrap on bodies that saved per-item KL\n")
    L.append("| body | model | statistic | point | 95% CI (pct) | 95% CI (BCa) | leave-one-item-out range | verdict |")
    L.append("|---|---|---|---|---|---|---|---|")
    for body in ("exp9", "exp14"):
        for m, v in k[body].items():
            if "mean" not in v:
                continue
            for st in ("mean", "trim10", "median") + (("mean_items_and_seeds",) if body == "exp9" else ()):
                x = v[st]
                L.append(f"| {body} | {m} | {st} | {f(x['point'], 3)} | {f(x['ci95_pct'], 3)} | {f(x['ci95_bca'], 3)} | "
                         f"{f(x['leave_one_item_out_range'], 3)} | {v['verdict'] if st == 'mean' else ''} |")
            pl = v["placebo_language_shuffle"]
            L.append(f"| {body} | {m} | language-shuffle placebo | median {pl['median_excess']:.3f} | log sd {pl['log_sd']:.3f} | | | centred={pl['centred_at_1']} |")
    L.append(f"\n## 2c GPU recompute\n\n{k['gpu_status']['status']}\n")
    g = k.get("gpu_recompute_gate")
    if g:
        L.append(f"Reproduction gate: {'PASSED' if g['pass'] else 'FAILED'}.\n")
        L.append("| model | lambda | recomputed excess | item-bootstrap 95% CI (pct) | BCa 95% | trimmed-10% excess |\n|---|---|---|---|---|---|")
        for m, v in g["per_model"].items():
            for r in v.get("per_lambda", []):
                L.append(f"| {m} | {r['lambda']} | {r['excess_recomputed']:.3f} | {f(r['ci95_pct'], 3)} | {f(r['ci95_bca'], 3)} | {f(r['trim10'], 3)} |")
            L.append(f"\n{m}: top-dose gate {json.dumps({l: round(x['rel_diff'], 5) for l, x in v['gate_top_dose_E_exp9'].items()})}; verdict {v['verdict']}\n")
    L.append("## 2d Reconciliation across bodies\n")
    L.append("| body | model | point | 95% CI | CI type | prompt set | horizon | lambda | verdict |\n|---|---|---|---|---|---|---|---|---|")
    for r in k["reconciliation"]["rows"]:
        if "point" not in r:
            L.append(f"| {r.get('body')} | | | | {r.get('status')} | | | | |")
            continue
        L.append(f"| {r['body']} | {r['model']} | {r['point']:.3f} | {f(r.get('ci95'), 3)} | {r['ci_type'][:60]} | {r['prompt_set']} | "
                 f"{r['horizon']} | {r['lambda']} | {r['verdict']} |")
    L.append(f"\n**{k['reconciliation']['sentence']}**")
    return "\n".join(L) + "\n"


def decomp_md(d: dict) -> str:
    L = ["# Step 3 - G3 / G3_orig / G3_edit / slope decomposition (every body x readout)\n", f"Rule: {d['rule']}\n",
         f"Status counts: {d['status_counts']}; G3_edit range over valid R rows: {f(d['G3_edit_range_R_valid_rows'])}\n",
         f"Edit-induced rows by direction: {d.get('edit_induced_by_direction')}\n", f"_{d.get('note_rg', '')}_\n",
         "| body | readout | coding | G3 [95%] | G3_orig [95%] | G3_edit [95%] | G3_edit 90% | MDE(G3) | b_Gemma | b_GaMS | b_diff | status | ceiling (G3_orig) | flag |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in d["rows"]:
        if "G3" not in r:
            L.append(f"| {r.get('body')} | {r.get('readout')} | {r.get('coding')} | {r.get('status_note', r.get('status'))} | | | | | | | | | | |")
            continue
        g, o, e = r["G3"], r["G3_orig"], r["G3_edit"]
        L.append(f"| {r['body']} | {r['readout']} | {r['coding']} | {f(g.get('point'))} {f(g.get('ci95'))} | {f(o.get('point'))} {f(o.get('ci95'))} | "
                 f"{f(e.get('point'))} {f(e.get('ci95'))} | {f(e.get('ci90'))} | {f(g.get('mde'))} | {f(r['b_Gemma'].get('point'))} "
                 f"{f(r['b_Gemma'].get('ci95'))} | {f(r['b_GaMS'].get('point'))} {f(r['b_GaMS'].get('ci95'))} | {f(r['b_diff'].get('point'))} | "
                 f"{r.get('decomposition_status')} | {r.get('ceiling_verdict_G3_orig') or ''} | {r.get('flag', '')} |")
    c = d["corrections"]
    L.append(f"\n**Correction (parallel curves):** {c['parallel_curves_claim']['replacement']}; b_Gemma "
             f"{f(c['parallel_curves_claim']['verified']['b_Gemma']['point'])} {f(c['parallel_curves_claim']['verified']['b_Gemma']['ci95'])}, "
             f"b_GaMS {f(c['parallel_curves_claim']['verified']['b_GaMS']['point'])} {f(c['parallel_curves_claim']['verified']['b_GaMS']['ci95'])}.")
    L.append(f"\n**Correction (MDE attribution):** MDE {c['mde_attribution']['verified_MDE_G3']:.3f} belongs to G3; G3_edit's MDE is "
             f"{c['mde_attribution']['verified_MDE_G3_edit']:.3f} and its 90% bound |G3_edit| < {c['mde_attribution']['verified_abs_G3_edit_bound_90']:.3f}.")
    return "\n".join(L) + "\n"


def ledger_md(lg: dict) -> str:
    L = ["# Step 5 - correction ledger summary\n", f"Tokens audited: {lg['n_tokens']}; pointer claims: {lg['n_pointers']}.\n",
         f"Counts by status: {lg['counts_by_status']}\n", f"Counts by match method: {lg['counts_by_method']}\n",
         f"Placebo (tokens shifted by 7-13 units of their last digit): auto-match rate {lg['placebo_auto_match_rate']:.3f} "
         f"({lg['placebo_shifted_tokens_match_methods']}). _{lg['caveat']}_\n",
         f"Attribution errors: {lg['attribution_errors']}\n", f"Claim-level reversals: {lg['claim_level_reversals']}\n",
         "## Pointer rows (headline and review-named numbers)\n",
         "| claim | line | paper value | verified | CI | status | claim status | attribution ok | source :: path | note |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for p in lg["pointers"]:
        L.append(f"| {p['claim_id']} | {p['line']} | {p['paper_token']} | {f(p.get('verified_value'), 3)} | {f(p.get('verified_ci95'))} | "
                 f"{p['status']} | {p.get('claim_status', '')} | {p.get('attribution_ok')} | {p.get('source_file')} :: {p.get('json_path')} | {p.get('note', '')} |")
    return "\n".join(L) + "\n"


def figures(c: dict, k: dict, d: dict) -> None:
    fig, ax = plt.subplots(figsize=(6, 3.6))
    t = c["fragility_index"]["trajectory"]
    ax.plot([x["flips"] for x in t], [x["best_G3_orig"] for x in t], "o-", lw=2, label="exp15 (J1)")
    for body, v in c["extension_eval3_bodies"].items():
        r = v.get("by_label", {}).get("gemini_raw_prim3") if isinstance(v, dict) else None
        if r and r["G3_orig_hautus"] < 0:
            ax.plot([0, r["FI_m"], r["FI_0"]], [r["G3_orig_hautus"], -M, 0], ".--", alpha=.7, label=f"{body} (gemini): FI_m {r['FI_m']}, FI_0 {r['FI_0']}")
    ax.axhspan(-M, M, color="grey", alpha=.2, label="margin +-m")
    ax.axhline(0, color="k", lw=.6)
    ax.set_xlabel("minimum number of lambda-0 label flips")
    ax.set_ylabel("G3_orig (Hautus logit)")
    ax.set_title("Fragility of the baseline component G3_orig")
    ax.legend(fontsize=6.5, loc="lower right")
    fig.tight_layout()
    fig.savefig(FIG / "fig_fragility.pdf")
    fig.savefig(FIG / "fig_fragility.png", dpi=160)
    plt.close(fig)
    rows = [r for r in k["reconciliation"]["rows"] if "point" in r]
    fig, ax = plt.subplots(figsize=(6, 0.35 * len(rows) + 1))
    for i, r in enumerate(rows):
        ci = r.get("ci95")
        if ci:
            ax.plot(ci, [i, i], "-", color="C0")
        else:
            sr = r.get("sensitivity_range")
            if sr:
                ax.plot(sr, [i, i], ":", color="C3")
        ax.plot(r["point"], i, "o" if ci else "s", color="C0" if ci else "C3")
    ax.axvline(1, color="k", lw=.7)
    ax.set_xscale("log")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([f"{r['body']} {r['model'].split('_')[0]}" for r in rows], fontsize=7)
    ax.set_xlabel("C5a excess ratio (log scale; <1 = less SL collateral than random)")
    ax.set_title("KL excess by body (solid = sampling CI; dotted red = sensitivity range, not a CI)", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "fig_kl_excess_forest.pdf")
    fig.savefig(FIG / "fig_kl_excess_forest.png", dpi=160)
    plt.close(fig)
    sel = [r for r in d["rows"] if r.get("coding") == "R" and r.get("G3_edit", {}).get("ci95") and r.get("readout") in
           ("raw_primary", "RAW", "raw_R", "PPI", "ttj", "TTJ") and not r.get("flag")]
    fig, ax = plt.subplots(figsize=(6, 0.3 * len(sel) + 1))
    for i, r in enumerate(sel):
        ax.plot(r["G3_edit"]["ci95"], [i, i], "-", color="C1")
        ax.plot(r["G3_edit"]["point"], i, "o", color="C1")
    ax.axvspan(-M / 2, M / 2, color="grey", alpha=.15)
    ax.axvline(0, color="k", lw=.6)
    ax.set_yticks(range(len(sel)))
    ax.set_yticklabels([f"{r['body']} | {r['readout']} {r.get('cell', '')}" for r in sel], fontsize=6)
    ax.set_xlabel("G3_edit (logit), 95% CI")
    ax.set_title("Edit-induced component by body and readout (compliance-valid rows)", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "fig_decomposition_forest.pdf")
    fig.savefig(FIG / "fig_decomposition_forest.png", dpi=160)
    plt.close(fig)


def paper_inserts(c, k, d, lg, s6, v) -> str:
    fi = c["fragility_index"]
    pu = c["judge_error"].get("pooled_unedited", {})
    ext = c["extension_eval3_bodies"]
    L = ["# PAPER_INSERTS (rendered from results/*.json; paste-ready)\n",
         "All numbers below are generated by src/make_tables.py from this artifact's JSON. Post-hoc sensitivity analyses are labelled as such.\n",
         "## Baseline component (R-BASE) - ceiling sensitivity\n",
         f"- {c['paper_sentence']}",
         f"- The Gemma lambda-0 cells are {c['smoke']['counts_rows_final']['gemma_en']:.0f}/300 (EN) and {c['smoke']['counts_rows_final']['gemma_sl']:.0f}/300 (SL) "
         f"refusals; one Slovene flip moves G3_orig from {fi['trajectory'][0]['best_G3_orig']:.2f} to {fi['trajectory'][1]['best_G3_orig']:.2f}. "
         f"McNemar exact p for Gemma's SL-vs-EN difference is {c['paired_exact']['gemma_it']['mcnemar_exact_p']:.3f} "
         f"(b={c['paired_exact']['gemma_it']['b_SLrefuse_ENnot']}, c={c['paired_exact']['gemma_it']['c_ENrefuse_SLnot']}).",
         f"- Jeffreys posterior: P(G3_orig < -m) = {c['estimators']['jeffreys_posterior']['P_lt_minus_m']:.2f}, 95% CrI "
         f"{f(c['estimators']['jeffreys_posterior']['cri95'])}; the pooled unedited J1 error rates (author-model adjudication, "
         f"n- = {pu.get('n_neg')}) imply about {pu.get('expected_mislabels_total_4cells', float('nan')):.0f} mislabelled items across the "
         f"four lambda-0 cells, far more than FI_m = {fi['FI_m']}.",
         "- Across eval3 bodies (paid gemini readout): " + "; ".join(
             f"{b} G3_orig {v_['by_label']['gemini_raw_prim3']['G3_orig_hautus']:.2f}, FI_m {v_['by_label']['gemini_raw_prim3']['FI_m']} "
             f"-> {v_['by_label']['gemini_raw_prim3']['verdict']}" for b, v_ in ext.items()
             if isinstance(v_, dict) and "gemini_raw_prim3" in v_.get("by_label", {})) + ".",
         "\n## C5a leakage\n", f"- {k['reconciliation']['sentence']}",
         f"- exp15 (saved means only): Gemma excess {k['exp15']['gemma_it']['point_excess_top_dose']:.3f}, GaMS3 "
         f"{k['exp15']['gams3_it']['point_excess_top_dose']:.3f} at the top random-matched dose; seed/dose sensitivity ranges "
         f"{f(k['exp15']['gemma_it']['sensitivity_range_seed_and_dose'])} / {f(k['exp15']['gams3_it']['sensitivity_range_seed_and_dose'])} "
         "(NOT sampling intervals).",
         f"- GPU recompute: {k['gpu_status']['status']}",
         *([f"- Gated GPU re-measurement of exp15's 40 prompts (code copied from exp15 src/gen.py; gate = saved kl_mean reproduced "
            f"within 5%): gate {'PASSED' if k['gpu_recompute_gate']['pass'] else 'FAILED'}; "
            + "; ".join(f"{m} max relative difference {max(x['rel_diff'] for x in v['gate_top_dose_E_exp9'].values()):.4f}, "
                        f"item-bootstrap 95% CI of the top-dose excess {f(v['top_dose_ci95'])} -> {v['verdict']}"
                        for m, v in k['gpu_recompute_gate']['per_model'].items())] if k.get("gpu_recompute_gate") else []),
         "\n## Decomposition\n",
         f"- Across {d['n_rows']} body x readout rows, decomposition status counts are {d['status_counts']}; replace 'parallel curves' "
         f"with the slopes b_Gemma {f(d['corrections']['parallel_curves_claim']['verified']['b_Gemma']['point'])} "
         f"{f(d['corrections']['parallel_curves_claim']['verified']['b_Gemma']['ci95'])} and b_GaMS "
         f"{f(d['corrections']['parallel_curves_claim']['verified']['b_GaMS']['point'])} {f(d['corrections']['parallel_curves_claim']['verified']['b_GaMS']['ci95'])}.",
         f"- MDE {d['corrections']['mde_attribution']['verified_MDE_G3']:.2f} is G3's; G3_edit's 90% bound is "
         f"{d['corrections']['mde_attribution']['verified_abs_G3_edit_bound_90']:.2f}.",
         "\n## Criterion shift\n", f"- {s6['criterion_shift']['like_for_like_sentence']}", f"- {s6['criterion_shift']['compliance_valid_sentence']}",
         f"- Frozen all-rows rule (reported for transparency): {s6['criterion_shift']['sentence'].split(':')[0]}; the rule was frozen before "
         "the compliance gate was applied to these rows (post-hoc validity refinement).",
         "\n## exp13 record\n",
         f"- Pool overlap with exp14 recomputed: B {s6['exp13']['recomputed']['B_overlap']}, C {s6['exp13']['recomputed']['C_overlap']}; "
         f"never generated {s6['exp13']['recomputed']['never_generated_total']} ({s6['exp13']['recomputed']['never_B']} B + "
         f"{s6['exp13']['recomputed']['never_C']} C); prior values reproduced: {all(s6['exp13']['prior_match'].values())}.",
         "\n## Ledger\n", f"- {lg['n_tokens']} numeric tokens + {lg['n_pointers']} pointer claims; statuses {lg['counts_by_status']}; "
         f"auto-match rate on shifted placebo tokens {lg['placebo_auto_match_rate']:.2f} (so auto-matches are weak evidence; pointer rows carry the audit).",
         f"- Claim-level reversals: {lg['claim_level_reversals']}; attribution errors: {lg['attribution_errors']}.",
         "\n## Verification\n", f"- verify.py: {v.get('n_pass')}/{v.get('n_checks')} independent checks pass." if v else "- verify.py not run"]
    return "\n".join(L) + "\n"


def main() -> None:
    setup_logging("make_tables")
    c, k, d = read_json(RES / "ceiling_sensitivity.json"), read_json(RES / "kl_excess.json"), read_json(RES / "decomposition_table.json")
    lg, s6 = read_json(RES / "correction_ledger.json"), read_json(RES / "step6.json")
    v = read_json(RES / "verify.json") if (RES / "verify.json").exists() else {}
    (RES / "ceiling_sensitivity.md").write_text(ceiling_md(c))
    (RES / "kl_excess.md").write_text(kl_md(k))
    (RES / "decomposition_table.md").write_text(decomp_md(d))
    (RES / "ledger_summary.md").write_text(ledger_md(lg))
    figures(c, k, d)
    from common import WS
    (WS / "PAPER_INSERTS.md").write_text(paper_inserts(c, k, d, lg, s6, v))
    logger.info("rendered markdown, figures and PAPER_INSERTS.md from JSON")


if __name__ == "__main__":
    main()
