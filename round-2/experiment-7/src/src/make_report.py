#!/usr/bin/env python3
"""results/RESULTS.md: every number read from results/analysis.json (+ audit.json, ledger spend)."""
from __future__ import annotations

import json

from common import RESULTS
from orclient import total_spent

S = {"gams": "GaMS3", "gemma": "Gemma-3", "q14": "Qwen3-14B", "q235": "Qwen3-235B", "out": "Llama-3.3-70B"}


def f(x, d=3):
    return "n/a" if x is None or (isinstance(x, float) and x != x) else f"{x:.{d}f}"


def ci(s):
    if not s:
        return "n/a"
    return f"{f(s['est'])} [{f(s['ci_lo'])}, {f(s['ci_hi'])}]"


def wil(w):
    return f"{w['p']:.3f} [{w['lo']:.3f}, {w['hi']:.3f}] (n={w['n']})" if w and w.get("n") else "n/a"


def main() -> None:
    A = json.loads((RESULTS / "analysis.json").read_text())
    au = json.loads((RESULTS / "audit.json").read_text()) if (RESULTS / "audit.json").exists() else {}
    L = ["# RESULTS — ALT-5 teacher-inheritance screen (exploratory, HARD-DEV / SCORE-400, non-reserved)", "",
         f"Readout: {A['readout']}; paired item bootstrap {A['n_boot']} resamples, seed {A['seed']}. "
         f"OpenRouter spend (all ledgers): ${total_spent():.2f}. Audit: {au.get('n_agree')}/{au.get('n_checks')} "
         f"independent re-derivations agree.", "", "## Verdicts", ""]
    for k, v in A["verdicts"].items():
        L.append(f"- **{k}**: {v.get('verdict', v.get('verdict_en'))}" + (f" / SL: {v['verdict_sl']}" if 'verdict_sl' in v else ""))
    L += ["", "## Execution status and the readout substitution", "",
          "The pre-registered readout (gemini-2.5-flash) labelled only the three LOCAL systems before the run-level "
          "AI-Inventor OpenRouter budget ($7.00 for the whole run's 'Test idea' phase, shared by all its artifacts) was "
          "exhausted at 00:33 UTC (HTTP 403 `aii_run_budget_exhausted`, non-retryable; this artifact's own ledgers: "
          f"${total_spent():.2f}). Teacher (Q235) generation finished for H EN/SL, R EN/SL, ID and the retest items (the "
          "EN back-translation arm only partly: 72 H + 60 R items); the outgroup (Llama) finished for a sha1-random "
          "~80% of H EN/SL and ID, and not at all for R. Neither model has a free endpoint. Headline numbers below "
          "therefore use a SUBSTITUTE local judge (Mistral-Small-24B-Instruct-2501, NF4) that applies the SAME frozen P1 "
          "prompt to ALL five systems (readout harmony) and is validated against gemini (section 'Judge validity'). "
          "This substitution is a post-freeze deviation from protocol.json. The gemini-only analysis is in "
          "`results/analysis_gemini_partial.json`; a lexical readout is in `results/analysis_regex.json`.",
          "",
          "A re-probe at 02:58 UTC on Sep 24 (`results/key_reprobe.json`) found the run budget still exhausted. The "
          "org-wide free-model daily limit was also used up until 00:00 UTC on Sep 25, so no API readout was possible in the "
          "resumed session. The pre-registered readout stays PENDING, and `./finalize.sh` will add it once the budget is raised.",
          ""]
    V0 = A["validity"]
    if A.get("readout_key") == "local":
        L += ["## Judge validity: substitute (Mistral) vs primary (gemini), binary REFUSE kappa", "",
              "| cell | n | kappa (REFUSE vs not) | raw agreement | kappa (PARTIAL=refuse) | 3-way kappa | refusal gemini | refusal substitute |",
              "|---|---|---|---|---|---|---|---|"]
        for src, J in (("full", V0["judge_kappa"]), ("pilot", V0.get("judge_kappa_pilot", {}))):
            for k, v in J.items():
                if k.startswith("ALL") or v["n"] < 16:
                    continue
                kb = v.get("kappa_binary")
                L.append(f"| {src}: {k} | {v['n']} | {f(kb)} | {f(v.get('agree_binary'))} | "
                         f"{f(v.get('kappa_binary_partial_as_refusal', v.get('kappa_3way')))} | {f(v.get('kappa_3way'))} | "
                         f"{f(v.get('refusal_rate_validation', v.get('refusal_gemini')))} | "
                         f"{f(v.get('refusal_rate_readout', v.get('refusal_local')))} |")
        L.append("")
    L += ["## T1 family (decision agreement, refuse vs not)", "",
          "n_core = items with GaMS, Gemma, Q14 and Q235 labelled (dk, FP-cal); n_out = subset that also has the outgroup (T1b).", "",
          "| block | n_core | FP-cal k(Q14,Q235)-k(Q14,Gemma) | T1 dk = k(GaMS,Q235)-k(GaMS,Gemma) | n_out | T1b k(GaMS,Q235)-k(GaMS,Llama) | d raw agreement |",
          "|---|---|---|---|---|---|---|"]
    for blk, T in A["T1"].items():
        if isinstance(T, dict) and "dk" in T:
            L.append(f"| {blk} | {T['n_core']} | {ci(T['fpcal_dk'])} | {ci(T['dk'])} | {T.get('n')} | "
                     f"{ci(T.get('t1b_dk_q235_minus_out'))} | {ci(T['d_agree'])} |")
        elif isinstance(T, dict) and "n_core" in T:
            L.append(f"| {blk} | {T['n_core']} | PENDING | PENDING | - | - | - |")
    h = A["T1"]["H_en_orig"]
    if "pairwise_core" in h:
        L += ["", "Core pairwise kappas (EN orig, n_core): " + ", ".join(
            f"{S[k.split('~')[0]]}~{S[k.split('~')[1]]} {f(v['kappa'])}" for k, v in h["pairwise_core"].items()),
            "Core refusal rates: " + ", ".join(f"{S[k]} {f(v)}" for k, v in h["refusal_rate_core"].items())]
    # readout robustness: local-only kappas under every available readout
    L += ["", "### Readout robustness: agreement among the three LOCAL systems under each readout", "",
          "| readout | arm | n | k(GaMS,Gemma) | k(GaMS,Q14) | k(Q14,Gemma) | k(GaMS,Q14)-k(GaMS,Gemma) | refusal GaMS / Gemma / Q14 |",
          "|---|---|---|---|---|---|---|---|"]
    for name in ("analysis_gemini_partial.json", "analysis.json", "analysis_regex.json"):
        pth = RESULTS / name
        if not pth.exists():
            continue
        B_ = json.loads(pth.read_text())
        for arm, v in B_["T1"].get("local_only_kappas", {}).items():
            pw = v["pairwise"]
            rr = v["refusal_rate"]
            L.append(f"| {B_['readout_key']} | {arm} | {v['n']} | {f(pw['gams~gemma']['kappa'])} | {f(pw['gams~q14']['kappa'])} | "
                     f"{f(pw['gemma~q14']['kappa'])} | {ci(v['k_gams_q14_minus_k_gams_gemma'])} | "
                     f"{f(rr['gams'])} / {f(rr['gemma'])} / {f(rr['q14'])} |")
    rx = RESULTS / "analysis_regex.json"
    if rx.exists():
        B_ = json.loads(rx.read_text())["T1"]["H_en_orig"]
        if "dk" in B_:
            L += ["", f"Lexical-readout T1 (H EN orig, n_core={B_['n_core']}): FP-cal {ci(B_['fpcal_dk'])}; dk {ci(B_['dk'])}; "
                      f"T1b {ci(B_.get('t1b_dk_q235_minus_out'))} (regex readout; robustness only)"]
    h = A["T1"]["H_en_orig"]
    if "pairwise" in h:
        L += ["", "### Pairwise agreement, HARD-DEV EN original", "", "| pair | kappa | raw agreement | PABAK |", "|---|---|---|---|"]
        for k, v in h["pairwise"].items():
            a, b = k.split("~")
            L.append(f"| {S[a]} ~ {S[b]} | {f(v['kappa'])} | {f(v['agree'])} | {f(v['pabak'])} |")
        L += ["", "Refusal rates (EN orig, judge REFUSE): " + ", ".join(f"{S[s]} {f(r)}" for s, r in h["refusal_rate"].items())]
        fp = h.get("t1c_fingerprint", {})
        if fp:
            L += ["", f"T1c fingerprint partial r: " + ", ".join(f"{S[k]} {f(v)}" for k, v in fp["r"].items()) +
                  f"; r_Q235 - r_Gemma = {ci(fp['dr_q235_minus_gemma'])}; r_Q235 - r_Llama = {ci(fp['dr_q235_minus_out'])}"]
        jl = h.get("t1c_joint_logit", {})
        if "beta_q_minus_g" in jl:
            L += [f"Joint L2 logistic: beta_Q235 {f(jl['beta_q235'])}, beta_Gemma {f(jl['beta_gemma'])}, beta_Llama "
                  f"{f(jl['beta_out'])}; beta_Q - beta_G = {ci(jl['beta_q_minus_g'])}"]
        st = h.get("t1d_side_taking", {})
        if st:
            L += [f"T1d side-taking on {st['n_discordant']} items where Q235 != Gemma: P(GaMS sides with Q235) "
                  f"{f(st['p_gams_sides_q235'])}, P(Llama sides with Q235) {f(st['p_out_sides_q235'])}, P(Q14 sides with Q235) "
                  f"{f(st['p_q14_sides_q235'])}; GaMS - Llama = {ci(st['gams_minus_out'])}; Q14 - Llama = {ci(st['q14_minus_out'])}"]
    rt = A["T1"].get("retest_q235", {})
    L += ["", f"Teacher test-retest (100 H EN items): kappa {f(rt.get('kappa'))}, agreement {f(rt.get('agree'))} "
          f"(identical text share {f(A['T1'].get('retest_q235_text', {}).get('identical_text_share'))})"]
    pl = A["T1"].get("placebo", {})
    for k, v in pl.items():
        L.append(f"Placebo swap {k}: observed {f(v['observed'])}, permutation mean {f(v['perm_mean'])} "
                 f"(95% {f(v['perm_q025'])}..{f(v['perm_q975'])}), p={f(v['p_two_sided'])}")
    t2 = A["T2"]["H"]
    L += ["", "## T2 language interaction (HARD-DEV, items paired across arms)", "",
          f"- n paired EN/SL = {t2.get('n_paired_en_sl')}; n paired with EN-BT = {t2.get('n_paired_all_arms')} "
          f"(teacher EN-BT rows only partly generated before the budget blocker)",
          f"- DiffGap dk(EN orig) - dk(SL MT) = {ci(t2.get('diffgap_en_minus_sl'))}",
          f"- MT noise dk(EN-BT) - dk(EN orig) = {ci(t2.get('mt_noise_enbt_minus_en'))}",
          f"- language effect dk(EN-BT) - dk(SL MT) = {ci(t2.get('language_enbt_minus_sl'))}"]
    for s, v in t2.get("refusal_sl_minus_en", {}).items():
        L.append(f"- refusal rate SL-MT minus EN orig, {S[s]}: {ci(v)}")
    for s, v in t2.get("refusal_sl_minus_enbt", {}).items():
        L.append(f"- refusal rate SL-MT minus EN-BT, {S[s]}: {ci(v)}")
    for arm, v in t2.get("per_arm", {}).items():
        L.append(f"- per arm {arm}: n={v.get('n')} dk={ci(v.get('dk'))} FP-cal={ci(v.get('fpcal'))} T1b={ci(v.get('t1b'))}")
    L += ["", "### Refusal rates by stratum (Wilson 95%)", "", "| system | arm | safe | unsafe |", "|---|---|---|---|"]
    for k, v in sorted(A["rates"].items()):
        s, set_, arm = k.split("|")
        if set_ == "H":
            L.append(f"| {S[s]} | {arm} | {wil(v.get('safe'))} | {wil(v.get('unsafe'))} |")
    L += ["", "RefusEU SCORE-400 (all unsafe):", ""]
    for k, v in sorted(A["rates"].items()):
        s, set_, arm = k.split("|")
        if set_ == "R":
            L.append(f"- {S[s]} {arm}: {wil(v.get('all'))}")
    T3 = A["T3"]
    L += ["", "## T3 wording (REFUSE-labelled responses)", "", "Formula shares:", ""]
    for k, v in sorted(T3["formula_share"].items()):
        L.append(f"- {k}: {wil(v)}")
    L += ["", "Opening-trigram Jensen-Shannon distances (key contrasts):", ""]
    for k, v in T3["jsd"].items():
        if k.startswith("contrast") or "gams~" in k or "~gams" in k or "q14~q235" in k or "q235~q14" in k:
            L.append(f"- {k}: {ci(v)}")
    L += ["", "4-gram opening overlap: " + ", ".join(f"{k} {f(v)}" for k, v in T3["ngram4_overlap"].items() if v is not None)]
    for k, v in T3.get("first_sentence_in_ref_sft", {}).items():
        L.append(f"- first sentence verbatim in GaMS SFT refusals, {k}: {wil(v)}")
    for l, c in T3["classifier"].items():
        L.append(f"- source classifier {l}: " + json.dumps({k: (v if not isinstance(v, dict) else
                                                          {kk: (round(vv['p'], 3) if isinstance(vv, dict) and 'p' in vv else vv)
                                                           for kk, vv in v.items()}) for k, v in c.items()
                                                      if k != "cv_acc_folds"}, default=str))
    L += ["", "## T4 depth (R200 common refused set)", ""]
    for arm, R in A["T4"].items():
        L.append(f"### {arm}: CR n = {R['n_CR']}")
        for s in ("gams", "gemma", "q14"):
            L.append(f"- {S[s]}: flip compliant-prefix {wil(R.get(f'flip|{s}|pre_comply5|primary'))}; neutral "
                     f"{wil(R.get(f'flip|{s}|pre_neutral|primary'))}; COMPLY-only compliant {wil(R.get(f'flip|{s}|pre_comply5|comply_only'))};"
                     f" net logit {f(R.get(f'net_flip_logit|{s}'))}; own-refused-set flip {wil(R.get(f'own_refused_flip|{s}'))}")
        for k in ("logit_flip_q14_minus_gemma", "logit_flip_q14_minus_gams", "logit_flip_gams_minus_gemma"):
            if k in R:
                L.append(f"- {k}: {ci(R[k])}; McNemar {R.get('mcnemar_' + k[11:].replace('_minus_', '_vs_'))}")
        L.append(f"- teacher family also shallow (pre-registered, m_depth={f(R.get('m_depth'))}): {R.get('teacher_family_shallow')}")
    L += ["", "### T4 descriptive flip rates (share NOT refused among all labelled R200 prefill rows)", "",
          "The substitute judge is not valid on prefill rows (see verdict), so the primary gemini readout on its labelled "
          "random subset is the only validated depth evidence; CR-conditioned numbers above are substitute-readout only.", ""]
    for name in ("analysis_gemini_partial.json", "analysis.json"):
        pth = RESULTS / name
        if pth.exists():
            U = json.loads(pth.read_text()).get("T4_unconditional_descriptive", {})
            L.append(f"- {name}: " + "; ".join(f"{k} {wil(v)}" for k, v in U.items()))
    pv = RESULTS / "prefill_v2_validation.json"
    if pv.exists():
        P = json.loads(pv.read_text())
        d, g = P["decision"], P["pre_comply5|heldout_gate_set"]
        aa = P["agent_adjudication_agreement"]
        L += ["", "### Post-hoc attempt to rescue the local prefill readout (REJECTED)", "",
              "A prefill-specific prompt for the same substitute judge (`src/local_judge.py --variant prefill_v2`) grades "
              "only the continuation after the forced start. It was checked against gemini and against a blind binary "
              "adjudication of 50 prefill rows by the executing agent (Claude; not a human) in "
              "`labels/prefill_adjudication_agent.json`.", "",
              f"- The pre-declared held-out gate passes numerically: kappa {f(g['prefill_v2']['kappa'])} (n={g['prefill_v2']['n']}). "
              f"It is degenerate, though: the old P1 prompt scores {f(g['P1']['kappa'])} on the same rows, because those rows exclude "
              "every P1-vs-gemini disagreement.",
              f"- On the {P['p1_vs_gemini_disagreements']['n']} disagreement rows, prefill_v2 matches gemini on "
              f"{P['p1_vs_gemini_disagreements']['prefill_v2_matches_gemini']}.",
              f"- Agreement with the agent adjudication: gemini {aa['gemini']['agree']}/50, P1 {aa['P1']['agree']}/50, prefill_v2 "
              f"{aa['prefill_v2']['agree']}/50. prefill_v2 still calls {P['prefill_v2_refuse_share_pre_comply5']:.0%} of "
              "compliant-prefix rows REFUSE.",
              f"- Decision: {d['reason']}", ""]
    L += ["", "## T4-api (optional): real teacher / outgroup under the same assistant prefill", "",
          "NOT RUN: it needed paid teacher/outgroup calls after the k0 labels existed; the run budget was exhausted first.", ""]
    for arm, R in A.get("T4_api_optional", {}).items():
        L.append(f"### {arm}: CR n = {R['n_CR']}; paired with Q235 n = {R.get('n_paired_with_q235')}")
        for s in ("q235", "out"):
            L.append(f"- {S[s]} (own-refused CR n={R.get(f'n_CR_own_refused|{s}')}): flip compliant "
                     f"{wil(R.get(f'flip|{s}|pre_comply5'))} (restarts excluded "
                     f"{(R.get(f'flip|{s}|pre_comply5') or {}).get('n_restart_excluded')}); neutral "
                     f"{wil(R.get(f'flip|{s}|pre_neutral'))}")
        if "paired_flip_rates" in R:
            L.append("- paired flip rates (same items): " + ", ".join(f"{S[k]} {v:.3f}" for k, v in
                                                                    R["paired_flip_rates"].items()))
        for k in ("logit_flip_q235_minus_gemma", "logit_flip_q235_minus_gams", "logit_flip_q235_minus_q14",
                  "logit_flip_gams_minus_gemma"):
            if k in R:
                L.append(f"- {k}: {ci(R[k])}")
    T5 = A["T5"]
    L += ["", "## T5 identity", ""]
    for k, v in T5["qwen_alibaba_mention_identity_items"].items():
        L.append(f"- Qwen/Alibaba mention on identity items, {k}: {wil(v)}")
    for k, v in T5["names"].items():
        top = sorted(v.items(), key=lambda x: -x[1]["p"])[:4]
        L.append(f"- self-name {k}: " + ", ".join(f"{a} {b['p']:.2f}" for a, b in top))
    for k, v in T5.items():
        if k.startswith("chrf"):
            L.append(f"- {k}: {v}")
    V = A["validity"]
    L += ["", "## Validity", "", "Judge agreement gemini vs gpt-4.1 (binary kappa per cell; flag < 0.6):", ""]
    for k, v in V["judge_kappa"].items():
        L.append(f"- {k}: n={v['n']} kappa_bin={f(v['kappa_binary'])} kappa3={f(v['kappa_3way'])}"
                 f"{'  **FLAG**' if v['flag_lt_0.6'] else ''}")
    L += ["", "Language consistency (share of responses in the prompt language):", ""]
    for k, v in V["lang_consistency"].items():
        L.append(f"- {k}: {f(v['share_expected'])}{'  **FLAG**' if v['flag_lt_95'] else ''}")
    L += ["", f"64-vs-160 token label agreement: {json.dumps(V['token64_vs_160'])}",
          f"Batch-vs-single outcome: {json.dumps(V['batch_vs_single'])}",
          f"Parse / block counts: {json.dumps(V['parse_rates'])}", ""]
    (RESULTS / "RESULTS.md").write_text("\n".join(L) + "\n")
    print("\n".join(L)[:6000])


if __name__ == "__main__":
    main()
