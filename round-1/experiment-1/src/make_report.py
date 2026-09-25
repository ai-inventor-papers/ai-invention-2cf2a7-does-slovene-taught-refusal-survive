#!/usr/bin/env python3
"""Render results/RESULTS.md from results/analysis_results.json (+ rederive.json, audit.json) so every number in the
README results section is generated, never hand-copied. README.md includes RESULTS.md between markers."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RES = ROOT / "results"


def f(x, d=2):
    if x is None:
        return "n/a"
    if isinstance(x, bool):
        return str(x)
    if isinstance(x, (list, tuple)):
        return "[" + ", ".join(f(v, d) for v in x) + "]"
    try:
        return f"{float(x):.{d}f}"
    except (TypeError, ValueError):
        return str(x)


def main() -> None:
    r = json.loads((RES / "analysis_results.json").read_text())
    L = []
    a = L.append
    a(f"Analysis set: **{r['analysis_set']['n_pairs']}** SCORE pairs with all 4 cells "
      f"(planned {r['analysis_set']['n_planned_score_pairs']}). p0 (pooled R_lex) = {f(r['p0_pooled_R_lex'], 3)}, "
      f"m = {f(r['m'], 3)} log-odds. Ceiling flag (any cell R_lex > 0.95): **{r['ceiling_flag']}**.\n")
    a("### Refusal rates (SCORE analysis set)\n")
    a("| outcome | Gemma EN | Gemma SL | GaMS EN | GaMS SL |")
    a("|---|---|---|---|---|")
    for o in ("R_lex", "R_lex_tr", "R_lex_sym_posthoc", "R_judge", "R_judge_partial", "guard_unsafe"):
        b = r["outcomes"].get(o)
        if not b or "rates" not in b:
            continue
        rt = b["rates"]
        a(f"| {o} (n={b['n_pairs']}) | " + " | ".join(
            f(rt[k]["rate"], 3) for k in ("gemma_it|en", "gemma_it|sl", "gams3_it|en", "gams3_it|sl")) + " |")
    a("\n### DiD = [GaMS(SL-EN)] - [Gemma(SL-EN)] and dose contrast D (log-odds; 95% pair-bootstrap CI)\n")
    a("| outcome | overall DiD [95% CI] | DiD low-EN | DiD high-EN | D [95% CI] | D 90% CI | MDE(D) | D_catmean |")
    a("|---|---|---|---|---|---|---|---|")
    for o in ("R_lex", "R_lex_tr", "R_lex_sym_posthoc", "R_judge", "R_judge_partial", "R_spec_kappa_substituted"):
        b = r["outcomes"].get(o)
        if not b or "D" not in b:
            continue
        a(f"| {o} | {f(b['overall']['est'])} {f(b['overall']['ci95'])} | {f(b['DiD_low']['est'])} | "
          f"{f(b['DiD_high']['est'])} | {f(b['D']['est'])} {f(b['D']['ci95'])} | {f(b['D']['ci90'])} | "
          f"{f(b['D']['MDE'])} | {f(b['D_catmean']['est'])} |")
    for o in ("R_lex", "R_judge", "R_judge_partial"):
        b = r["outcomes"].get(o)
        if b and "D_leave_one_category_out" in b:
            a(f"- D leave-one-category-out ({o}): " + ", ".join(f"-{c}: {f(v)}" for c, v in b["D_leave_one_category_out"].items()))
    a("\n**Risk-difference scale (percentage points; not ceiling-sensitive):**\n")
    for o in ("R_lex", "R_lex_tr", "R_lex_sym_posthoc", "R_judge", "R_judge_partial", "R_spec_kappa_substituted"):
        b = r["outcomes"].get(o)
        if b and "risk_difference" in b:
            rd = b["risk_difference"]
            a(f"- {o}: DiD_pp {f(rd['overall_pp']['est'], 1)} {f(rd['overall_pp']['ci95'], 1)}; D_pp "
              f"{f(rd['D_pp']['est'], 1)} {f(rd['D_pp']['ci95'], 1)} (MDE {f(rd['D_pp']['MDE'], 1)} pp)")
    a("")
    s = r.get("s_outcome")
    if s:
        a(f"| s (prefix log-odds) | {f(s['overall']['est'])} {f(s['overall']['ci95'])} | {f(s['low']['est'])} | "
          f"{f(s['high']['est'])} | {f(s['D']['est'])} {f(s['D']['ci95'])} | {f(s['D']['ci90'])} | {f(s['D']['MDE'])} | - |")
        a(f"\nm_s = {f(s.get('m_s'))} (calibration: {s['m_s_calibration']['source']}, slope "
          f"{f(s['m_s_calibration']['slope_logodds_per_s'], 3)} log-odds per unit s). Cell mean s: "
          + ", ".join(f"{k} {f(v)}" for k, v in s["cell_mean_s"].items()))
    mt = r.get("mt_arm")
    if mt:
        a("\n### Item-matched MT-parallel arm (SCORE-400 EN prompts machine-translated to SL; EN side identical)\n")
        a("| outcome | n | rates G-EN / G-SLmt / GaMS-EN / GaMS-SLmt | DiD [95% CI] | D [95% CI] | natural-pair DiD on same ids |")
        a("|---|---|---|---|---|---|")
        for o, b in mt.items():
            a(f"| {o} | {b['n_pairs']} | " + " / ".join(f(v, 3) for v in b["rates"].values()) +
              f" | {f(b['overall']['est'])} {f(b['overall']['ci95'])} | {f(b['D']['est'])} {f(b['D']['ci95'])} | "
              f"{f(b['natural_pairs_same_ids']['overall']['est'])} {f(b['natural_pairs_same_ids']['overall']['ci95'])} |")
        for o, b in mt.items():
            a(f"- {o} risk-difference: MT DiD_pp {f(b['risk_difference']['overall_pp']['est'], 1)} "
              f"{f(b['risk_difference']['overall_pp']['ci95'], 1)} vs natural pairs (same ids) "
              f"{f(b['natural_pairs_risk_difference']['overall_pp']['est'], 1)} "
              f"{f(b['natural_pairs_risk_difference']['overall_pp']['ci95'], 1)}; within-model item-matched McNemar "
              f"{json.dumps(b['mcnemar_item_matched'])}")
    a("\n### Per-category DiD (R_lex | R_judge), ordered by category\n")
    a("| cat | n | DiD R_lex [95% CI] | DiD R_judge [95% CI] | Gemma EN/SL, GaMS EN/SL raw R_judge |")
    a("|---|---|---|---|---|")
    pl, pj = r["outcomes"]["R_lex"]["per_category"], r["outcomes"].get("R_judge", {}).get("per_category", {})
    for c in sorted(pl, key=lambda c: int(c[1:])):
        tag = " (low-EN)" if c in ("S5", "S7", "S8", "S13") else (" (high-EN)" if c in (
            "S2", "S3", "S4", "S9", "S10", "S11", "S14") else "")
        jj = pj.get(c, {})
        a(f"| {c}{tag} | {pl[c]['n']} | {f(pl[c]['est'])} {f(pl[c]['ci95'])} | {f(jj.get('est'))} {f(jj.get('ci95'))} | "
          f"{f(jj.get('raw_rates'))} |")
    for o in ("R_lex", "R_judge"):
        b = r["outcomes"].get(o)
        if not b:
            continue
        dm = b["dose_models"]
        a(f"\n### Dose models ({o})\n")
        a(f"- corr(zEN, zSL) over 14 categories = {f(dm['corr_zEN_zSL'])}, VIF = {f(dm['VIF'])}")
        mr = dm["b_meta_regression_zEN_zSL"]
        a(f"- (b) DL meta-regression DiD_c ~ zEN + zSL: zEN {f(mr['coef']['zEN']['est'])} KH95 "
          f"{f(mr['coef']['zEN']['ci95_kh'])}, cat-bootstrap {f(mr.get('cat_bootstrap_ci95', {}).get('zEN'))}; "
          f"zSL {f(mr['coef']['zSL']['est'])} KH95 {f(mr['coef']['zSL']['ci95_kh'])}; tau2 {f(mr['tau2'], 3)}")
        m1 = dm["b_meta_regression_zEN_only"]["coef"]["zEN"]
        a(f"- (b') zEN-only: {f(m1['est'])} KH95 {f(m1['ci95_kh'])}")
        sl = dm["c_ols_slope_DiD_on_log2EN"]
        a(f"- (c) OLS slope of DiD_c on log2(EN+1): {f(sl['est'])} {f(sl['ci95'])}")
        if "a_bayes_mixed_glm_vb" in dm:
            t = dm["a_bayes_mixed_glm_vb"].get("terms", {})
            a(f"- (a) item-level BinomialBayesMixedGLM (VB; overstates precision on a 14-level regressor): "
              + "; ".join(f"{k} {f(v['post_mean'])} {f(v['ci95'])}" for k, v in t.items() if k.startswith("gams:sl")))
        dr = b.get("dose_models_relabelled_sensitivity")
        if dr:
            mr2 = dr["b_meta_regression_zEN_zSL"]["coef"]
            a(f"- SENSITIVITY with the DATASET artifact's re-labelled dose: corr(zEN,zSL) {f(dr['corr_zEN_zSL'])}; "
              f"meta-reg zEN {f(mr2['zEN']['est'])} {f(mr2['zEN']['ci95_kh'])}, zSL {f(mr2['zSL']['est'])} "
              f"{f(mr2['zSL']['ci95_kh'])}; zEN-only {f(dr['b_meta_regression_zEN_only']['coef']['zEN']['est'])} "
              f"{f(dr['b_meta_regression_zEN_only']['coef']['zEN']['ci95_kh'])}; item GLMM gams:sl:zEN "
              f"{f(dr.get('a_bayes_mixed_glm_vb', {}).get('terms', {}).get('gams:sl:zEN', {}).get('post_mean'))} "
              f"{f(dr.get('a_bayes_mixed_glm_vb', {}).get('terms', {}).get('gams:sl:zEN', {}).get('ci95'))}")
        if "a_gee_category_clustered" in dm:
            t = dm["a_gee_category_clustered"].get("terms", {})
            a(f"- (a') GEE clustered on category (bias-reduced SE): "
              + "; ".join(f"{k} {f(v['est'])} {f(v['ci95'])}" for k, v in t.items()))
    idr = r.get("identity", {})
    if idr.get("n_question_pairs"):
        a("\n### Identity calibration C1\n")
        a(f"- own-name rates: GaMS EN {f(idr['gams_own_rate_en'])}, GaMS SL {f(idr['gams_own_rate_sl'])}, "
          f"Gemma EN {f(idr['gemma_own_rate_en'])}, Gemma SL {f(idr['gemma_own_rate_sl'])} (n={idr['n_question_pairs']} "
          f"question pairs; source {idr['own_name_source']})")
        a(f"- DiD_id = {f(idr['DiD_id'])} {f(idr['ci95'])}, m_id = {f(idr['m_id'])}, C1_pass = **{idr['C1_pass']}**, "
          f"evaluable = {idr['evaluable']} {idr.get('note', '')}")
        if idr.get("sensitivity_excluding_reserved_collisions"):
            a(f"- sensitivity excluding identity items that collide verbatim with the DATASET artifact's reserved set: "
              f"{json.dumps(idr['sensitivity_excluding_reserved_collisions'], default=str)}")
        a(f"- name distribution (identity items): {json.dumps(idr['identity_name_distribution'])}")
        a(f"- control items, any-name regex rate: {json.dumps(idr['control_regex_any_name_rate'])}")
        a(f"- maker mentions on identity items (regex): {json.dumps(idr.get('identity_maker_mention_rates'))}")
    a("\n### Scorer validity\n")
    a("| cell | kappa(lex,judge) all | kappa strat-150 | judge-judge kappa (bin / 3-way, n) | AUROC s->R_lex | AUROC s->R_judge | same-language rate |")
    a("|---|---|---|---|---|---|---|")
    for k, v in r["kappa"].items():
        va, lc = r["validity_auroc"][k], r["language_consistency"][k]
        a(f"| {k} | {f(v.get('kappa_lex_judge_all'))} | {f(v.get('kappa_lex_judge_strat150'))} | "
          f"{f(v.get('kappa_judge_judge_binary'))} / {f(v.get('kappa_judge_judge_3way'))} ({v.get('n_judge_judge', 0)}) | "
          f"{f(va.get('auroc_s_R_lex'))} | {f(va.get('auroc_s_R_judge'))} | {f(lc['same_lang_rate'], 3)} |")
    a(f"\nCells using R_judge for the spec statistic (kappa < 0.7): {r.get('spec_R_substitution', {}).get('cells_using_R_judge')}")
    a("\n### Surface forms of lexicon-refusals (opening)\n")
    for k, v in r["surface_forms"].items():
        a(f"- {k}: {json.dumps(v)}")
    pc = r.get("pair_correspondence")
    if pc:
        a(f"\n### Natural EN/SL pair correspondence (LaBSE cosine): median {f(pc['labse_median'])} "
          f"(IQR {f(pc['labse_q25'])}-{f(pc['labse_q75'])})")
        for h in ("high_corr", "low_corr"):
            if h in pc:
                a(f"- {h} half (n={pc[h]['n']}): overall DiD {f(pc[h]['overall']['est'])} {f(pc[h]['overall']['ci95'])}, "
                  f"D {f(pc[h]['D']['est'])} {f(pc[h]['D']['ci95'])}")
    a("\n### Pre-registered selection rule\n")
    a("```json\n" + json.dumps(r["selection"], indent=1, default=str) + "\n```")
    for fn, title in (("rederive.json", "Independent re-derivation + placebo tests"),
                      ("rederive2.json", "Independent re-derivation of identity C1 and MT arm + placebos"),
                      ("audit.json", "Audit"),
                      ("unit_tests.json", "Unit tests (T1/T4)"), ("synthetic_T8.json", "Synthetic dry run (T8)")):
        p = RES / fn
        if p.exists():
            d = json.loads(p.read_text())
            if fn == "audit.json":
                d = {"n_checks": d["n_checks"], "n_failed": d["n_failed"]}
            if fn == "unit_tests.json":
                d = {"all_ok": d["all_ok"]}
            a(f"\n### {title}\n\n```json\n{json.dumps(d, indent=1, default=str)[:3000]}\n```")
    (RES / "RESULTS.md").write_text("\n".join(L) + "\n")
    print("\n".join(L)[:6000])


if __name__ == "__main__":
    main()
