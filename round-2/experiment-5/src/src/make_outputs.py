#!/usr/bin/env python3
"""STEP 9: method_out.json (exp_gen_sol_out schema) + results/RESULTS.md + figures.

method_out.json: one dataset block per item set (refuseu_nat, refuseu_x, hard, identity). One example per FINAL
prompt (item x arm): input = prompt text, output = item-level reference (hazard category / is_harmful / identity kind),
predict_gemma_it / predict_gams3_it = primary judge label (REFUSE|PARTIAL|COMPLY; identity: NAME|MAKER),
metadata_* = arm, language, group, R_lex, detected language, truncated responses (300 chars). All statistics,
verdicts, margins and MDEs are in the top-level metadata.
"""
from __future__ import annotations

import json
from collections import defaultdict

from loguru import logger

from common import MODEL_ORDER, PROTO, RESULTS, ROOT, read_jsonl, setup_logging


def fmt(x, d=3):
    return "NA" if x is None else (f"{x:.{d}f}" if isinstance(x, (int, float)) else str(x))


def ci(s, key="ci95"):
    return f"[{fmt(s[key][0])}, {fmt(s[key][1])}]" if s and s.get(key) else "NA"


def build_method_out(rows, A, add) -> dict:
    by = defaultdict(dict)
    for r in rows:
        by[r["gid"]][r["model"]] = r
    blocks = defaultdict(list)
    for gid in sorted(by):
        d = by[gid]
        r0 = d.get("gemma_it") or d.get("gams3_it")
        s = r0["set"]
        if s == "hard":
            out = f"{'unsafe' if r0['is_harmful'] else 'safe'}|{r0['category']}"
        elif s == "identity":
            out = r0["kind"]
        else:
            out = r0["label"] or "NA"
        ex = {"input": r0["prompt_text"], "output": out}
        for mk in MODEL_ORDER:
            r = d.get(mk)
            if r is None:
                continue
            if s == "identity":
                ex[f"predict_{mk}"] = f"{r.get('id_name')}|{r.get('id_maker')}"
            else:
                ex[f"predict_{mk}"] = str(r.get("judge_primary"))
            ex[f"metadata_response_{mk}"] = (r["response"] or "")[:300]
            ex[f"metadata_lang_detected_{mk}"] = r.get("lang_detected")
            ex[f"metadata_R_lex_{mk}"] = r.get("R_lex")
            ex[f"metadata_judge_gpt41_{mk}"] = r.get("judge_gpt41") if s != "identity" else r.get("id_name_gpt41")
            if s != "identity":
                ex[f"metadata_judge_qwen3_local_{mk}"] = r.get("judge_qwen3")
                ex[f"metadata_judge_gemini_{mk}"] = r.get("judge_gemini")
            else:
                ex[f"predict_{mk}"] = (str(r.get("regex_self_name")) if A.get("substitute_mode")
                                       else ex[f"predict_{mk}"])
            ex[f"metadata_hit_eos_{mk}"] = r.get("hit_eos")
        ex.update({"metadata_item_id": r0["item_id"], "metadata_pair_id": r0["pair_id"], "metadata_arm": r0["arm"],
                   "metadata_lang": r0["prompt_lang"], "metadata_group": r0.get("group"),
                   "metadata_split": r0["split"]})
        if s == "hard":
            ex.update({"metadata_source": r0["source"], "metadata_is_harmful": r0["is_harmful"],
                       "metadata_mt_fragile": r0["mt_fragile"], "metadata_xstest_type": r0.get("xstest_type")})
        if s == "refuseu_nat":
            ex["metadata_pure"] = r0.get("pure")
            ex["metadata_balanced_label"] = r0.get("balanced")
        if s == "identity":
            ex["metadata_facet"] = r0.get("facet")
        blocks[s].append(ex)
    meta = {
        "method_name": "CONFIRM-SPEC v2 confirmation run: GaMS3-12B-Instruct vs Gemma-3-12B-IT (control), EN/SL refusal",
        "baseline": "gemma_it (Gemma-3-12B-IT, identical decoding/template/precision) = control model of the DiD",
        "our_method": "gams3_it (GaMS3-12B-Instruct, Slovene-SFT sibling)",
        "predict_semantics": ("PRIMARY judge label REFUSE|PARTIAL|COMPLY. Under deviation D5/D6 (the run's OpenRouter "
                              "budget was exhausted mid-FINAL) the FINAL primary is the local Qwen3-14B judge "
                              "(same frozen prompt, logits); metadata_judge_gemini_* holds gemini-2.5-flash labels "
                              "where they exist. Identity: regex self-name detector NAME (gemini NAME|MAKER unavailable "
                              "on FINAL)." if A.get("substitute_mode") else
                              "judge label (gemini-2.5-flash primary; gpt-4.1 when gemini content-blocked); identity: "
                              "NAME|MAKER; metadata_judge_qwen3_local_* = deviation-D1 local third-family label"),
        "protocol_sha256": (PROTO / "protocol.sha256").read_text().split()[0],
        "addendum_sha256": (PROTO / "addendum_dev.sha256").read_text().split()[0],
        "margins_and_mde": {k: add[k] for k in ("p0", "m", "m_partial", "p_id", "m_id", "H0", "F0", "m_dprime", "m_c",
                                                "ceiling_fires", "mde")},
        "analysis": {k: v for k, v in A.items() if k != "_extra"},
        "exploratory_and_robustness": A.get("_extra", {}),
        "workspace": str(ROOT),
    }
    return {"metadata": meta, "datasets": [{"dataset": k, "examples": v} for k, v in blocks.items()]}


def results_md(A, add, audit, spend, jl) -> str:
    c2, s, h = A["C2_refuseu"], A["C2_refuseu_sensitivities"], A["C2_hard_sdt"]["primary_SLMT_vs_ENBT"]
    L = ["# RESULTS (FINAL, sealed-outcome confirmation run)", ""]
    L.append(f"Margins from DEV (addendum): m={fmt(add['m'])} (p0={fmt(add['p0'])}), m_partial={fmt(add['m_partial'])}, "
             f"m_id={fmt(add['m_id'])} (p_id={fmt(add['p_id'])}), m_d'={fmt(add['m_dprime'])}, m_c={fmt(add['m_c'])}; "
             f"ceiling fires: {add['ceiling_fires']}.")
    L.append("")
    L.append("## Verdicts")
    L.append(f"- **C1 identity**: PASS={A['C1']['C1_pass']}; DiD_id={fmt(A['C1']['identity']['DiD_id']['est'])} "
             f"95% CI {ci(A['C1']['identity']['DiD_id'])}; control-item DiD="
             f"{fmt(A['C1']['control'].get('DiD_id', {}).get('est'))} {ci(A['C1']['control'].get('DiD_id'))}")
    L.append(f"- **C2 RefusEU (natural pairs)**: {A['C2_refuseu_verdict']['verdict']} — {A['C2_refuseu_verdict']['why']}; "
             f"ungated mapping: {A['C2_refuseu_verdict'].get('ungated_mapping_descriptive')}")
    L.append(f"  - D={fmt(c2['D']['est'])} 90% {ci(c2['D'], 'ci90')} 95% {ci(c2['D'])} BCa95 {ci(c2['D'], 'bca95')}; "
             f"DiD_ref={fmt(c2['DiD_overall']['est'])} 90% {ci(c2['DiD_overall'], 'ci90')} 95% {ci(c2['DiD_overall'])}")
    L.append(f"- **C2 co-primary HARD SDT (SL_MT vs EN_BT)**: {A['C2_hard_verdict']['verdict']}; tags="
             f"{A['C2_hard_verdict'].get('tags') or A['C2_hard_verdict'].get('tags_descriptive')}; criterion reading="
             f"{A['C2_hard_verdict'].get('criterion_reading')}")
    L.append(f"  - DiD_d'={fmt(h['DiD_dprime']['est'])} 90% {ci(h['DiD_dprime'], 'ci90')}; DiD_c={fmt(h['DiD_c']['est'])} "
             f"95% {ci(h['DiD_c'])}; D_d'={fmt(h['D_dprime']['est'])} 95% {ci(h['D_dprime'])}")
    L.append(f"- **Joint C2**: {A['joint_C2_statement']['statement']}")
    L.append(f"- Holm (one-sided ALT-1 tests): {A['holm_ALT1_one_sided']}")
    L.append("")
    L.append("## MDE (DEV-based, FINAL sizes)")
    for k, v in add["mde"].items():
        L.append(f"- {k}: MDE={fmt(v['mde'])} vs 2*margin={fmt(2 * v['margin'])} -> {'UNDERPOWERED' if v['mde_gt_2m'] else 'ok'}")
    L.append("")
    L.append("## Sensitivities (RefusEU)")
    for k in ("pure_only", "balanced_groups", "Rp_coding", "gemini_only_labels", "lang_consistent_only",
              "lexicon_R_lex_diagnostic"):
        v = s.get(k)
        if v and "D" in v:
            L.append(f"- {k}: D={fmt(v['D']['est'])} {ci(v['D'])}; DiD_ref={fmt(v['DiD_overall']['est'])} "
                     f"{ci(v['DiD_overall'])}; n={v.get('n_pairs')}")
    mt = s["item_matched_MT_ENBT"]
    L.append(f"- item-matched MT arm (SL_MT vs EN_BT): DiD_ref^MT={fmt(mt['DiD_overall']['est'])} {ci(mt['DiD_overall'])}; "
             f"D^MT={fmt(mt['D']['est'])} {ci(mt['D'])}; n={mt['n_items']}")
    mt2 = s["item_matched_MT_vs_ENnat"]
    L.append(f"- SL_MT vs natural EN original: DiD={fmt(mt2['DiD_overall']['est'])} {ci(mt2['DiD_overall'])}")
    mc = s.get("misclassification_corrected", {})
    if "D_corr" in mc:
        L.append(f"- misclassification-corrected D={fmt(mc['D_corr'])} {ci(mc['D_corr_summary'])} "
                 f"(identifiable={mc['identifiable']}; cond EN/SL={fmt(mc['cond_Q_en'], 1)}/{fmt(mc['cond_Q_sl'], 1)})")
    pi = s.get("pooled_with_iter1", {})
    if "pooled_D" in pi:
        L.append(f"- pooled with iter-1 (secondary): D={fmt(pi['pooled_D'])} [{fmt(pi['pooled_ci95'][0])}, "
                 f"{fmt(pi['pooled_ci95'][1])}], Cochran Q={fmt(pi['cochran_Q'])} (p={fmt(pi['Q_p'])})")
    pc = s.get("per_category_dose", {})
    if pc:
        L.append(f"- per-category DiD_ref vs log2 EN dose: WLS slope={fmt(pc['wls_slope'])} {pc['slope_ci95']}")
    g = s.get("gee", {})
    L.append(f"- GEE interaction={fmt(g.get('interaction'))} CI {g.get('ci95')}")
    L.append("")
    L.append("## HARD secondary contrasts")
    for k, v in A["C2_hard_sdt"].items():
        if v.get("n_unsafe"):
            L.append(f"- {k}: DiD_d'={fmt(v['DiD_dprime']['est'])} {ci(v['DiD_dprime'])}; DiD_c={fmt(v['DiD_c']['est'])} "
                     f"{ci(v['DiD_c'])}; H={[round(x, 3) for x in v['cells']['H']]}; F={[round(x, 3) for x in v['cells']['F']]} "
                     f"(n_u={v['n_unsafe']}, n_s={v['n_safe']})")
    L.append("")
    L.append("## Refusal rates per model x set x arm (primary judge; Wilson 95%)")
    L.append("| cell | n | REFUSE | 95% CI | PARTIAL | COMPLY | lang-consistent | truncated@160 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for c, v in A["descriptives"].items():
        if "|identity|" in c:
            continue
        L.append(f"| {c} | {v['n']} | {fmt(v['refusal_rate'])} | [{fmt(v['refusal_wilson95'][0])}, "
                 f"{fmt(v['refusal_wilson95'][1])}] | {fmt(v['partial_rate'])} | {fmt(v['comply_rate'])} | "
                 f"{fmt(v['language_consistency'])} | {fmt(v['truncated_rate'])} |")
    L.append("")
    JR = A.get("judge_family_robustness_qwen3")
    if JR:
        L.append("## Judge-family robustness (deviation D1: local Qwen3-14B labels, same frozen prompt)")
        a, b = JR["C2_refuseu_R_qwen3"], JR["item_matched_MT_ENBT_R_qwen3"]
        L.append(f"- RefusEU natural: DiD_ref={fmt(a['DiD_overall']['est'])} {ci(a['DiD_overall'])}; D={fmt(a['D']['est'])} "
                 f"{ci(a['D'])}; ungated mapping={JR['verdict_mapping_R_qwen3'].get('ungated_mapping_descriptive')}")
        L.append(f"- item-matched MT: DiD_ref^MT={fmt(b['DiD_overall']['est'])} {ci(b['DiD_overall'])}")
        hq = JR["hard_primary_R_qwen3"]
        if hq.get("n_unsafe"):
            L.append(f"- HARD: DiD_d'={fmt(hq['DiD_dprime']['est'])} {ci(hq['DiD_dprime'])}; DiD_c={fmt(hq['DiD_c']['est'])} "
                     f"{ci(hq['DiD_c'])}")
        L.append("")
    GR = A.get("judge_family_robustness_gemini_subset")
    if GR:
        L.append("## Judge-family robustness: gemini-2.5-flash subset (items with all 4 cells gemini-labelled)")
        a, b, hq = GR["C2_refuseu_R_gemini"], GR["item_matched_MT_ENBT_R_gemini"], GR["hard_primary_R_gemini"]
        L.append(f"- coverage (labelled/total rows): {GR['coverage']}")
        if a.get("n_pairs"):
            L.append(f"- RefusEU natural: n_pairs={a['n_pairs']}; DiD_ref={fmt(a['DiD_overall']['est'])} "
                     f"{ci(a['DiD_overall'])}; D={fmt(a['D']['est'])} {ci(a['D'])}")
        if b.get("n_items"):
            L.append(f"- item-matched MT: n={b['n_items']}; DiD_ref^MT={fmt(b['DiD_overall']['est'])} {ci(b['DiD_overall'])}")
        if hq.get("n_unsafe"):
            L.append(f"- HARD: n_u={hq['n_unsafe']}, n_s={hq['n_safe']}; DiD_d'={fmt(hq['DiD_dprime']['est'])} "
                     f"{ci(hq['DiD_dprime'])}; DiD_c={fmt(hq['DiD_c']['est'])} {ci(hq['DiD_c'])}")
        L.append("")
    VQ = A.get("verdicts_under_qwen3_dev_margins")
    if VQ:
        L.append(f"## Verdicts under Qwen3-DEV-derived margins (D6 sensitivity): m={fmt(VQ['m'])}, m_d'={fmt(VQ['m_dprime'])}")
        L.append(f"- C2 RefusEU: {VQ['C2_refuseu']['verdict']} ({VQ['C2_refuseu']['why']}); ungated: "
                 f"{VQ['C2_refuseu'].get('ungated_mapping_descriptive')}")
        L.append(f"- C2 HARD: {VQ['C2_hard']['verdict']}; criterion reading: {VQ['C2_hard'].get('criterion_reading')}")
        L.append("")
    st = A.get("exploratory_refusal_style")
    if st:
        L.append("## EXPLORATORY: refusal style among primary-REFUSE responses")
        L.append("| cell | n | median tokens | EOS rate | top-1 opening share | top-5 share | top opening |")
        L.append("|---|---|---|---|---|---|---|")
        for c, v in st.items():
            L.append(f"| {c} | {v['n_refuse']} | {fmt(v['median_new_tokens'], 0)} | {fmt(v['eos_rate'])} | "
                     f"{fmt(v['top1_opening_share'])} | {fmt(v['top5_opening_share'])} | {v['top5_openings'][0][0]} |")
        L.append("")
    X = A.get("_extra", {})
    dj = X.get("dev_judge_compare")
    if dj:
        L.append("## DEV cross-judge replication (same DEV items; gemini = planned primary vs Qwen3 = FINAL substitute)")
        L.append("| contrast | gemini (DEV) | Qwen3 (DEV) |")
        L.append("|---|---|---|")
        for k in ("DiD_ref", "D", "DiD_ref_MT", "DiD_dprime", "DiD_c"):
            g, q = dj["gemini"].get(k), dj["qwen3"].get(k)
            if g and q:
                L.append(f"| {k} | {fmt(g['est'])} [{fmt(g['ci95'][0])}, {fmt(g['ci95'][1])}] | {fmt(q['est'])} "
                         f"[{fmt(q['ci95'][0])}, {fmt(q['ci95'][1])}] |")
        L.append("")
    jc = X.get("judge_calibrated_final")
    if jc:
        q = jc["qwen3_corrected_to_gemini_scale"]
        L.append("## EXPLORATORY: FINAL estimates corrected to the gemini scale (DEV per-cell judge calibration)")
        L.append(f"- DiD_ref (natural) = {fmt(q['DiD_ref_natural']['est'])} {ci(q['DiD_ref_natural'])}")
        L.append(f"- DiD_ref^MT = {fmt(q['DiD_ref_MT']['est'])} {ci(q['DiD_ref_MT'])}")
        for k in ("HARD_SLMT_vs_ENBT", "HARD_SLMT_vs_ENorig"):
            h2 = q[k]
            L.append(f"- {k}: DiD_d'={fmt(h2['DiD_dprime']['est'])} {ci(h2['DiD_dprime'])}; DiD_c={fmt(h2['DiD_c']['est'])} "
                     f"{ci(h2['DiD_c'])}; F={[round(x, 3) for x in h2['F']]}; H={[round(x, 3) for x in h2['H']]}; "
                     f"Gemma c_SL-c_EN={fmt(h2['gemma_c_SL_minus_EN'])} {h2['gemma_c_SL_minus_EN_ci95']}; "
                     f"GaMS c_SL-c_EN={fmt(h2['gams_c_SL_minus_EN'])} {h2['gams_c_SL_minus_EN_ci95']}")
        L.append("")
    L.append(f"## Judge-language check (V5): {json.dumps(jl) if jl else 'not run'}")
    L.append(f"## Audit: {audit.get('n_pass')}/{audit.get('n_checks')} checks pass")
    L.append(f"## Spend: ${fmt(spend.get('total_usd'), 3)}")
    return "\n".join(L) + "\n"


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("make_outputs")
    rows = read_jsonl(RESULTS / "items_final.jsonl")
    A = json.loads((RESULTS / "analysis_final.json").read_text())
    add = json.loads((PROTO / "addendum_dev.json").read_text())
    audit = json.loads((RESULTS / "audit.json").read_text()) if (RESULTS / "audit.json").exists() else {}
    spend = json.loads((RESULTS / "spend.json").read_text()) if (RESULTS / "spend.json").exists() else {}
    jl = json.loads((RESULTS / "judge_lang_check.json").read_text()) if (RESULTS / "judge_lang_check.json").exists() else None
    A["audit_summary"] = {"n_checks": audit.get("n_checks"), "n_pass": audit.get("n_pass")}
    A["spend_usd"] = spend.get("total_usd")
    A["judge_language_check"] = jl
    extra = {}
    for name in ("dev_judge_compare", "judge_calibrated_final", "judge_calibrated_dev"):
        pth = RESULTS / f"{name}.json"
        if pth.exists():
            extra[name] = json.loads(pth.read_text())
    if (RESULTS / "analysis_dev.json").exists():
        ad = json.loads((RESULTS / "analysis_dev.json").read_text())
        extra["dev_gemini_judged_summary"] = {k: ad.get(k) for k in ("C2_refuseu_verdict", "C2_hard_verdict")}
        extra["dev_gemini_judged_summary"]["C2_refuseu"] = {k: ad["C2_refuseu"][k] for k in ("DiD_overall", "D", "cells")}
        extra["dev_gemini_judged_summary"]["hard_primary"] = {
            k: ad["C2_hard_sdt"]["primary_SLMT_vs_ENBT"][k] for k in ("DiD_dprime", "DiD_c", "cells", "own_delta")}
    A["_extra"] = extra
    mo = build_method_out(rows, A, add)
    (ROOT / "method_out.json").write_text(json.dumps(mo, ensure_ascii=False))
    (RESULTS / "RESULTS.md").write_text(results_md(A, add, audit, spend, jl))
    logger.info(f"method_out.json: {sum(len(b['examples']) for b in mo['datasets'])} examples in "
                f"{len(mo['datasets'])} blocks")


if __name__ == "__main__":
    main()
