#!/usr/bin/env python3
"""RESULTS.md rendered by code from results/analysis.json (+ gate files, audit.json). No hand-typed numbers.
Sections: completed confirmatory findings / descriptive / exploratory / not executed."""
from __future__ import annotations

import json

from common import MKEYS, RESULTS, ROOT

MN = {"gemma_it": "Gemma-3-12B-it", "gams3_it": "GaMS3-12B-Instruct"}
RN = {"asr": "ASR_row", "asr_loose": "ASR_row (Q3G loose)", "sr05": "SR-ft>=0.5", "pgr": "PG refusal",
      "q3r": "Q3G refusal", "lg": "LG unsafe", "pg": "PG harmful", "q3g": "Q3G unsafe", "sr_mean": "SR-ft mean"}


def p3(x):
    return "NA" if x is None else f"{x:.3f}"


def pv(x):
    return "NA" if x is None else (f"{x:.2e}" if x < 1e-3 else f"{x:.3f}")


def ci(c):
    return "NA" if not c or c[0] is None else f"[{c[0]:.3f}, {c[1]:.3f}]"


def main() -> None:
    A = json.loads((RESULTS / "analysis.json").read_text())
    audit = json.loads((RESULTS / "audit.json").read_text()) if (RESULTS / "audit.json").exists() else None
    L = []
    w = L.append
    w("# RESULTS: What does one English-only de-censoring edit buy on RefusEU's own prompts?\n")
    w("All numbers below are rendered by `src/make_report.py` from `results/analysis.json`. "
      "Protocol: `protocol.yaml` (sha256 in `protocol.sha256`). Gold labels = blind **author-model (LLM, NOT human)** "
      "adjudication. **R0:** the OpenRouter run budget was exhausted, so the gpt-4o-mini adjudicator, the gemini "
      "StrongREJECT rubric and the P1 judge were replaced by local pinned substitutes (Qwen3Guard-Gen-8B, the official "
      "StrongREJECT fine-tuned evaluator, PolyGuard refusal flag); see `deviations.md`.\n")
    w(f"Rows analysed: {A['n_rows']}; condition tags: {', '.join(A['ctags'])}.\n")
    # gate
    w("## 1. Completed findings (CONFIRMATORY)\n")
    w("### S2 - manipulation check (DEV gate, PolyGuard refusal on 100 DEV EN prompts)\n")
    w("| model | gate status | lambda_gate | R(0) | relative cut at lambda 1.0 |\n|---|---|---|---|---|")
    for m in MKEYS:
        s = A["statements"]["S2"][m]
        g = A["gates"].get(m, {})
        w(f"| {MN[m]} | {s['status_gate']} | {s['lambda_gate']} | {p3(g.get('R0'))} | {p3(s['rel_cut_at_1'])} |")
    w("\n### S1 - does the edit raise benchmark-protocol ASR? (orig -> edit@1.0, exact McNemar, Holm over 4 cells)\n")
    w("| model | lang | ASR orig | ASR edit | delta [95% paired bootstrap] | b (0->1) | c (1->0) | Holm p | SR05 holds | RG CI>0 | verdict |")
    w("|---|---|---|---|---|---|---|---|---|---|---|")
    effs = {(e["model"], e["lang"], e["readout"], e["contrast"]): e for e in A["edit_effects"]}
    for s in A["statements"]["S1"]:
        e = effs.get((s["model"], s["lang"], "asr", "orig->edit1"))
        if not e or not e.get("n"):
            w(f"| {MN[s['model']]} | {s['lang']} | NA | NA | NA | NA | NA | NA | NA | NA | NOT_EXECUTED |")
            continue
        w(f"| {MN[s['model']]} | {s['lang']} | {p3(e['p0'])} | {p3(e['p1'])} | {p3(e['delta'])} {ci(e['delta_ci'])} | "
          f"{e['b_0to1']} | {e['c_1to0']} | {pv(e['p_holm'])} | {s['sr05_holds']} | {s['rg_corrected_ci_gt0']} | "
          f"**{s['verdict']}** |")
    w("\n## 2. Descriptive results\n")
    w("### Paired edit effects on every readout\n")
    w("| contrast | model | lang | readout | n | orig | edited | delta [95% CI] | McNemar p | Holm p |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    for e in A["edit_effects"]:
        if not e.get("n"):
            continue
        w(f"| {e['contrast']} | {MN[e['model']]} | {e['lang']} | {RN.get(e['readout'], e['readout'])} | {e['n']} | "
          f"{p3(e['p0'])} | {p3(e['p1'])} | {p3(e['delta'])} {ci(e['delta_ci'])} | "
          f"{pv(e.get('p_mcnemar', e.get('p_wilcoxon')))} | {pv(e.get('p_holm'))} |")
    w("\n### Corrected ASR (Rogan-Gladen + Lang-Reiczigel; adjudicator-agreement-corrected, author-model gold)\n")
    w("| model | lang | ctag | readout | p_obs | Se | Sp | p_RG [LR 95% CI] | unidentifiable | readout validated |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    for c in A["corrected_rates"]:
        if "model" not in c:
            w("| NOT_EXECUTED | | | | | | | | | |")
            break
        w(f"| {MN[c['model']]} | {c['lang']} | {c['ctag']} | {RN[c['readout']]} | {p3(c['p_obs'])} | {p3(c['se'])} | "
          f"{p3(c['sp'])} | {p3(c['p_rg'])} {ci(c['ci_lr'])} | {c['unidentifiable']} | {c['readout_validated']} |")
    if A.get("corrected_deltas"):
        w("\nRG-corrected ASR deltas (bootstrap over prompts and adjudicated rows):\n")
        for c in A["corrected_deltas"]:
            w(f"- {MN[c['model']]} {c['lang']} {c['contrast']}: delta_RG = {p3(c['delta_rg'])} {ci(c['ci'])} "
              f"(Se {p3(c['se'])}, Sp {p3(c['sp'])})")
    w("\n### Adjudicated validity of each readout (weighted Se/Sp vs author-model HARMFUL / refusal gold)\n")
    adj = A.get("adjudication", {})
    if adj.get("cells"):
        w(f"Adjudicated rows: {adj['n_labelled']} ({adj['who']}).\n")
        w("| cell | readout | Se (w) | Sp (w) | n gold+ | n gold- | validated (Sp>=0.80, Se>=0.60) |")
        w("|---|---|---|---|---|---|---|")
        for k, cell in adj["cells"].items():
            for ro in ("asr", "asr_loose", "lg", "pg", "q3g", "sr05", "pgr", "q3r"):
                v = cell[ro]
                w(f"| {k} | {RN[ro]} | {p3(v['se_w'])} | {p3(v['sp_w'])} | {v['n_pos']} | {v['n_neg']} | {v['validated']} |")
    else:
        w("NOT_EXECUTED\n")
    w("\n### S3 / cross-model difference of edit effects (DESCRIPTIVE; not dose-matched; closed C-LAG line)\n")
    w("| contrast | lang | readout | n | delta Gemma | delta GaMS | DiD [95% CI] | DiD log-odds [CI] | perm p |")
    w("|---|---|---|---|---|---|---|---|---|")
    for d in A["did"]:
        if not d.get("n"):
            continue
        w(f"| {d['contrast']} | {d['lang']} | {RN[d['readout']]} | {d['n']} | {p3(d['delta_gemma'])} | "
          f"{p3(d['delta_gams'])} | {p3(d['did'])} {ci(d['did_ci'])} | {p3(d['did_logodds'])} {ci(d['did_logodds_ci'])} | "
          f"{pv(d['p_perm'])} |")
    for s in A["statements"]["S3"]:
        w(f"- S3 {s['lang']}: {s['verdict']}")
    w("\n### NOT INTERPRETABLE AS A LANGUAGE EFFECT - EN and SL are different natural prompts (LaBSE 0.55)\n")
    w("| contrast | model | readout | subset LaBSE>=0.70 & pure | n EN | n SL | delta EN | delta SL | SL - EN [CI] |")
    w("|---|---|---|---|---|---|---|---|---|")
    for c in A["language_contrast"]:
        if c.get("status") == "NOT_EXECUTED":
            continue
        w(f"| {c['contrast']} | {MN[c['model']]} | {RN[c['readout']]} | {c['subset_labse070_pure']} | {c['n_en']} | "
          f"{c['n_sl']} | {p3(c['delta_en'])} | {p3(c['delta_sl'])} | {p3(c['sl_minus_en'])} {ci(c['ci'])} |")
    w("\n### Controls, placebos, sensitivities\n")
    for r in A["controls"]["rand1"]:
        if r["readout"] == "asr":
            w(f"- rand_1@1.0 control, {MN[r['model']]} {r['lang']}: ASR {p3(r['p_orig'])} -> {p3(r['p_rand1'])} "
              f"(delta {p3(r['delta'])}, b={r['b']}, c={r['c']}, McNemar p {pv(r['p_mcnemar'])}, n={r['n']})")
    for r in A["controls"]["sens256"]:
        w(f"- 256-token sensitivity, {MN[r['model']]} {r['lang']} (n={r['n']}): SR-ft mean {p3(r['sr_mean_128'])} "
          f"(128) vs {p3(r['sr_mean_256'])} (256), delta {p3(r['delta_sr_mean'])} {ci(r['delta_sr_mean_ci'])}; "
          f"ASR {p3(r['asr_128'])} vs {p3(r['asr_256'])}")
    pl = A["placebos"]
    w(f"- placebo orig/edit swap: mean delta {[x['mean_delta'] for x in pl['swap_orig_edit']]} "
      f"(pass {[x['pass'] for x in pl['swap_orig_edit']]}); model-swap DiD {[x['mean_did'] for x in pl['model_swap_did']]}; "
      f"shuffled-guard kappa {[x['mean_kappa'] for x in pl['shuffled_guard_kappa']]}")
    for s in A["sensitivity_subsets"]:
        w(f"- sensitivity {s['subset']}: {MN[s['model']]} {s['lang']} ASR delta {p3(s['delta'])} {ci(s['delta_ci'])} (n={s['n']})")
    w("\n### Per-cell rates and compliance\n")
    w("| model | lang | ctag | n | ASR | ASR loose | SR-ft mean | SR05 | PG refusal | Q3G refusal | LG | PG | Q3G | LG/PG kappa | "
      "adjudicator share | lang consistency | degenerate | empty | hit max tokens |")
    w("|" + "---|" * 19)
    for r in A["rates"]:
        w(f"| {MN[r['model']]} | {r['lang']} | {r['ctag']} | {r['n_rows']} | {p3(r['asr']['p'])} | {p3(r['asr_loose']['p'])} | "
          f"{p3((r.get('sr_mean') or {}).get('mean'))} | {p3(r['sr05']['p'])} | {p3(r['pgr']['p'])} | {p3(r['q3r']['p'])} | "
          f"{p3(r['lg']['p'])} | {p3(r['pg']['p'])} | {p3(r['q3g']['p'])} | {p3(r['lg_pg_kappa'])} | "
          f"{p3(r['adjudicator_share'])} | {p3(r['lang_consistency'])} | {p3(r['degenerate'])} | {p3(r['empty'])} | "
          f"{p3(r['hit_max_tokens'])} |")
    w("\n## 3. Exploratory\n")
    w("Hazard-category / item-group ASR deltas (orig -> edit@1.0; Wilson CIs; no tests) are in `results/analysis.json` "
      "under `hazard`. PPI sensitivity:")
    for p in A.get("ppi", []):
        w(f"- PPI {MN[p['model']]} {p['lang']} {p['ctag']}: {p3(p['ppi'])} {ci(p['ci'])} (n_eff {p['n_eff']})")
    for c in A.get("sr_imputation_audit", []):
        if c["flag_gt_5pct"]:
            w(f"- certified-refusal audit {MN[c['model']]} {c['lang']} {c['ctag']}: {c['n_sr_ge_05']}/{c['n_certified']} "
              f"guard-certified refusals have SR-ft >= 0.5")
    if A.get("ranking_vs_threshold"):
        w("\n### Ranking vs thresholding (added analysis; does a guard fail Slovene by ranking or by calibration?)\n")
        w("| model | lang | score | n | weighted AUROC vs author-model HARMFUL | best threshold | weighted acc at best |")
        w("|---|---|---|---|---|---|---|")
        for x in A["ranking_vs_threshold"]:
            w(f"| {MN[x['model']]} | {x['lang']} | {x['score']} | {x['n']} | {p3(x['auroc_weighted'])} | "
              f"{p3(x['best_threshold'])} | {p3(x['weighted_acc_at_best'])} |")
        w("\nA high AUROC beside a failing specificity means the guard ranks harmful above harmless but its shipped "
          "decision threshold is misplaced for that language; a low AUROC means the score itself does not separate.\n")
    w("\n## 4. Not executed\n")
    w("- P1 3-way refusal judge (gemini) and its gpt-4.1-mini second family: OpenRouter budget exhausted (R0).")
    w("- gpt-4o-mini adjudication of guard disagreements (the RefusEU adjudicator): replaced by Qwen3Guard-Gen-8B (R0).")
    w("- gemini-2.5-flash StrongREJECT rubric: replaced by the official fine-tuned StrongREJECT evaluator (R0).")
    w(f"- Secondary correction from artifact 3 error matrices: {A['secondary_correction']['note']}.")
    w("- Fresh frozen-core Heretic search at tool defaults (unpaid debt, deviation a).")
    w("- Native-speaker (human) audit of the adjudication frame: requested in `results/human_audit_request.json`, not performed.")
    if audit:
        w(f"\nAudit: `src/rederive.py` re-derived {audit['n_checks']} statistics independently; failures: {audit['n_fail']}.")
    (ROOT / "RESULTS.md").write_text("\n".join(L) + "\n")
    print("RESULTS.md written")


if __name__ == "__main__":
    main()
