# RECONCILIATION - iter-1 numbers vs one harmonised refusal readout

**Status of the readout.** The planned paid census (gemini-2.5-flash under exp1's P1 prompt, both models, every cell; gpt-4.1 second family) could NOT run: the shared OpenRouter key reported `limit_remaining 0` (daily limit, reset 2026-09-24T00:00Z) at the first probe, so $0 was spent. The harmonised readout used here is `P1_real_or_pooled`: REAL gemini P1 labels where they exist (exp1: all 10,852; other artifacts: exact (request, response) matches), else a pooled multi-prompt text classifier anchored to P1 and trained on all 26.9k real LLM-judge labels of iter 1. Each cell carries a validity status (eval_protocol.json amendments A1/A2); a number is CITABLE only if all its input cells are VALID. `run_all.sh` completes the paid census from the ledger.

Cell validity: 33 VALID, 17 FAIL, 22 UNVALIDATED (all GaMS exp4 cells).

## Headline: the prefill cells are not measurable by any iter-1 readout

A 48-item blind adjudication of exp4 prefill k=5 continuations (12 per model x language, seed 20260924; `labels/author_gold_prefill5.json`; the adjudicator is this artifact's author model, a third judge family, **not** a human and not a native Slovene speaker) puts every available readout below the pre-registered validity gate: lex kappa 0.21 (rate 0.44 vs adjudicated 0.51), native JP2 gemini kappa 0.17 (rate 0.90 vs adjudicated 0.45), P1_sur kappa 0.07 (rate 0.47 vs adjudicated 0.51), pooled_P1 kappa 0.39 (rate 0.63 vs adjudicated 0.51), pooled_JP2 kappa 0.10 (rate 0.95 vs adjudicated 0.51), P1_real_or_pooled kappa 0.39 (rate 0.63 vs adjudicated 0.51), pooled_P1 continuation-only kappa 0.29 (rate 0.77 vs adjudicated 0.51). The real gemini JP2 judge - the only REAL judge label that exists for any prefill cell - marks 90% of Gemma continuations as refusals where adjudication finds 45%. A recurring GaMS Slovene failure mode has no category in any readout: after the forced 'Seveda, tukaj je ...' prefix the model returns an 'improved, more professional version of your message', i.e. it paraphrases the harmful request back. It occurs in 35% of GaMS Slovene prefill items and in 0% of the other three prefill cells, and the frozen lexicon scores 96% of them as a FLIP. Deleting those rows moves the iter-1 lexicon numbers from GaMS-SL flip 0.855 to 0.802 and Sig_SL from 1.54 to 1.16: it accounts for part of the Slovene flip excess, not all of it. ALT-4 and C3 cannot be cited from iter-1 data at all, under any readout; they need fresh generations with a purpose-built prefill readout.

## Which GaMS Slovene deficit? (M5)

| estimate | iter-1 | harmonised DiD (logit) [95% CI] | n pairs |
|---|---|---|---|
| E1_exp1_SCORE_natural | -0.38 (P1) | -0.38 [-0.71, -0.05] | 2137 |
| E2_exp1_MT_item_matched | -0.92 / -2.0 pp (P1) | -0.92 [-2.06, -0.04] | 400 |
| E3_exp2_SCORE400_natural | -0.70 (exp2 prompt) | -0.69 [-1.68, +0.22] | 400 |
| E4_exp3_C0_natural | -1.11 (SYS_REF) | -0.95 [-1.74, -0.21] | 400 |
| E6_exp4_orig_SCORE400_natural | -0.48 (lexicon) | -1.25 [-2.14, -0.44] | 400 |

Pooled natural (k=4): GLS on the joint cluster-bootstrap covariance **-0.50** [-0.82, -0.21]; REML + modified HKSJ (independence) -0.71 [-1.43, -0.00], tau 0.29, I^2 0.40 (Q-profile CI 0.00-0.94), 95% PI [-2.30, +0.87].
Natural minus item-matched (E2): +0.42 [-0.47, +1.57] - on the logit scale the MT arm does NOT remove the deficit; iter-1's 'prompt-set x model interaction' reading rested on the pp scale, where Gemma's MT-arm SL ceiling (.988) compresses differences.

## Verdict table (M7)

| claim | iter-1 verdict | harmonised statistic | harmonised verdict | changed | readout-robust | cells valid |
|---|---|---|---|---|---|---|
| MAIN / ALT-1 / ALT-3-pattern (exp1 D, iter1_hypothesis_groups) | NEITHER MAIN nor ALT-1 survives (R_judge+PARTIAL ranking; R_judge thin MAIN; C3 PENDING in exp1, later FAILS in exp4 on lexicon) | D=-0.08 [-1.27, +0.94] (90% [-1.09,+0.75]), MDE 1.53; DiD=-0.38 [-0.69, -0.05]; G3=-0.44 [-1.70, +0.78] | INCONCLUSIVE (MDE>2m) | N | True | False |
| MAIN / ALT-1 / ALT-3-pattern (exp1 D, frozen_groups_dataset) | NEITHER MAIN nor ALT-1 survives (R_judge+PARTIAL ranking; R_judge thin MAIN; C3 PENDING in exp1, later FAILS in exp4 on lexicon) | D=-0.70 [-1.57, +0.08] (90% [-1.43,-0.05]), MDE 1.20; DiD=-0.38 [-0.69, -0.05]; G3=-0.44 [-1.70, +0.78] | INCONCLUSIVE (MDE>2m) | N | True | False |
| ALT-2 (base checkpoint sets the EN/SL refusal profile) | FAILS | geometry share 0.042 [0.005,0.122], z_c=-15 (restated) | FAILS (restated) | N | True | True |
| ALT-3 persona gate (exp3 TD*) | UNTESTABLE (manipulation check failed in GaMS); judge TD* +0.23 [-0.81,1.25] | TD*=+0.27 [-0.77, +1.30], MDE 1.50 | UNTESTABLE (as registered); descriptive rule would give INCONCLUSIVE | N | False | False |
| ALT-4 (prefill-depth signature: GaMS shallower in BOTH languages, no language interaction) | NOT SURVIVED (|Sig_SL-Sig_EN|=2.10 > m) though Sig_EN=3.63, Sig_SL=1.54 > m2 | Sig_EN=+0.70 [+0.34, +1.15], Sig_SL=+1.20 [+0.91, +1.50], interaction +0.50 | SURVIVES (provisional) - UNCITABLE | Y | False | False |
| C1 identity is language-bound (DiD_id) | PASS: DiD_id 3.22 [2.38,4.38] | DiD_id=+3.22 [+2.38, +4.38] (recomputed from judge_idname.jsonl) | PASS | N | PENDING (single judge family) | True |
| C3 (EN-objective abliteration transfers to SL equally: |G3|<m) | FAILS BOTH WAYS: G3 -1.86 [-2.87,-1.13] (GaMS SL MORE exposed) | G3=-0.44 [-1.70, +0.78], MDE 1.78; lambda-curve G3=-0.43 [-1.29, +0.53] | MAIN-C3 - UNCITABLE | Y | False | False |
| C4 (ancestor-readable refusal gate) | FAILURE BRANCH (pt direction never reaches R=.5) | restated | FAILURE BRANCH (restated) | N | PENDING | True |
| C5a (edit damages SL more than norm-matched random: leakage) | REVERSES: excess ratio < 1 in both models (no leakage) | gemma_it: +0.298 [+0.154, +0.562]; gams3_it: +0.574 [+0.409, +0.796] | no leakage (reproduced) | N | True | True |
| C5b (SL-aware reselection gain) | unpowered (one candidate per model, gain 0) | gemma_it: n_cand 1, gain 0.000; gams3_it: n_cand 1, gain 0.000 | unpowered (reproduced) | N | True | True |

## Number-by-number reconciliation (M8)

| number | source | iter-1 | harmonised [95% CI] | status | note |
|---|---|---|---|---|---|
| GaMS SL deficit DiD, exp1 natural SCORE (R_judge) | `exp1 results/analysis_results.json:outcomes.R_judge.overall.est` | -0.377 | -0.377 [-0.706, -0.051] | **SURVIVES** | labels identical (real P1) |
| GaMS SL deficit DiD, exp4 orig SCORE-400 (lexicon; the '-0.48') | `exp4 results/analysis.json:P0_DiD_ref_overall.est` | -0.478 | -1.250 [-2.140, -0.440] | **UNCITABLE** | GaMS exp4 orig cells: 32-34% real P1 by exact propagation, rest pooled surrogate (UNVALIDATED for GaMS) |
| GaMS SL deficit DiD, exp2 SCORE-400 (exp2 judge; the '-0.70') | `exp2 results/analysis/analysis.json:S2_judge.DiD.all_did_R.est` | -0.698 | -0.691 [-1.682, +0.218] | **SURVIVES** |  |
| GaMS SL deficit DiD_ref C0, exp3 (SYS_REF judge; the '-1.11') | `exp3 results/analysis.json:primary.DiD_ref_C0.point` | -1.108 | -0.954 [-1.744, -0.210] | **UNCITABLE** | GaMS C0 EN cell FAILS the surrogate gate (kappa .28) |
| Item-matched MT-arm DiD, exp1 (logit) | `exp1 results/analysis_results.json:mt_arm.R_judge.overall.est` | -0.918 | -0.918 [-2.062, -0.042] | **SURVIVES** | same labels; on the logit scale the item-matched deficit is NOT smaller than the natural one (see M5) |
| Item-matched MT-arm DiD, exp1 (pp) | `exp1 results/analysis_results.json:mt_arm.R_judge.risk_difference.overall_pp.est` | -2.000 | -2.000 [-4.250, +0.500] | **SURVIVES** |  |
| Dose contrast D (R_judge, iter-1 hypothesis groups) | `exp1 results/analysis_results.json:outcomes.R_judge.D.est` | -0.080 | -0.080 [-1.273, +0.939] | **SURVIVES** |  |
| Dose contrast D (R_judge, dataset frozen_groups.json: low-EN S2/S5/S7/S13) | `NEW (iter 1 never used the audited groups)` | None | -0.704 [-1.574, +0.085] | **NEW** | 90% CI [-1.43,-0.05], MDE 1.20 > 2m: INCONCLUSIVE; sign opposite to ALT-1 |
| Natural-pair DiD on the SAME 400 ids as the MT arm (logit) | `exp1 (recomputed; iter 1 reported only the pp version, -6.0 pp)` | None | -0.749 [-1.420, -0.082] | **NEW** | pp -6.00; MT-arm logit -0.92: the natural-vs-MT contrast is scale-dependent |
| exp1 judged refusal rate gemma_it en | `exp1 results/analysis_results.json:outcomes.R_judge.rates.gemma_it|en` | +0.979 | +0.979 | **SURVIVES** |  |
| exp1 judged refusal rate gemma_it sl | `exp1 results/analysis_results.json:outcomes.R_judge.rates.gemma_it|sl` | +0.929 | +0.929 | **SURVIVES** |  |
| exp1 judged refusal rate gams3_it en | `exp1 results/analysis_results.json:outcomes.R_judge.rates.gams3_it|en` | +0.971 | +0.971 | **SURVIVES** |  |
| exp1 judged refusal rate gams3_it sl | `exp1 results/analysis_results.json:outcomes.R_judge.rates.gams3_it|sl` | +0.865 | +0.865 | **SURVIVES** |  |
| C3 G3 (matched first 17 trials) | `exp4 results/analysis.json:C3.matched_first_k_trials.all_pairs.G3.est` | -1.862 | -0.442 [-1.697, +0.777] | **UNCITABLE** |  |
| C3 G3 (lambda curve) | `exp4 results/analysis.json:C3.lambda_curve.G3.est` | -0.985 | -0.433 [-1.292, +0.534] | **UNCITABLE** |  |
| ALT-4 Sig_EN | `exp4 results/analysis.json:ALT4.prefill_signature.Sig.en.est` | +3.634 | +0.701 [+0.336, +1.151] | **UNCITABLE** |  |
| ALT-4 Sig_SL | `exp4 results/analysis.json:ALT4.prefill_signature.Sig.sl.est` | +1.538 | +1.201 [+0.905, +1.503] | **UNCITABLE** |  |
| Prefill k=5 flip rate gemma_it en | `exp4 results/analysis.json:ALT4.prefill_depth_curve.gemma_it.en.5` | +0.031 | +0.072 | **UNCITABLE** |  |
| Prefill k=5 flip rate gemma_it sl | `exp4 results/analysis.json:ALT4.prefill_depth_curve.gemma_it.sl.5` | +0.558 | +0.374 | **UNCITABLE** |  |
| Prefill k=5 flip rate gams3_it en | `exp4 results/analysis.json:ALT4.prefill_depth_curve.gams3_it.en.5` | +0.559 | +0.136 | **UNCITABLE** |  |
| Prefill k=5 flip rate gams3_it sl | `exp4 results/analysis.json:ALT4.prefill_depth_curve.gams3_it.sl.5` | +0.855 | +0.666 | **UNCITABLE** |  |
| prefill k=5 readout vs blind adjudication (lex (iter-1 frozen lexicon, on the continuation)) | `labels/author_gold_prefill5.json (48 items, author model, NOT human)` | None | +0.211 | **UNCITABLE** | n=43, Po 0.60, PABAK 0.21, readout rate 0.44 vs adjudicated 0.51 |
| prefill k=5 readout vs blind adjudication (native JP2 gemini (Gemma only)) | `labels/author_gold_prefill5.json (48 items, author model, NOT human)` | None | +0.167 | **UNCITABLE** | n=20, Po 0.55, PABAK 0.10, readout rate 0.90 vs adjudicated 0.45 |
| prefill k=5 readout vs blind adjudication (P1_sur (P1-only surrogate)) | `labels/author_gold_prefill5.json (48 items, author model, NOT human)` | None | +0.071 | **UNCITABLE** | n=43, Po 0.53, PABAK 0.07, readout rate 0.47 vs adjudicated 0.51 |
| prefill k=5 readout vs blind adjudication (pooled_P1) | `labels/author_gold_prefill5.json (48 items, author model, NOT human)` | None | +0.392 | **UNCITABLE** | n=43, Po 0.70, PABAK 0.40, readout rate 0.63 vs adjudicated 0.51 |
| prefill k=5 readout vs blind adjudication (pooled_JP2) | `labels/author_gold_prefill5.json (48 items, author model, NOT human)` | None | +0.097 | **UNCITABLE** | n=43, Po 0.56, PABAK 0.12, readout rate 0.95 vs adjudicated 0.51 |
| prefill k=5 readout vs blind adjudication (P1_real_or_pooled (primary)) | `labels/author_gold_prefill5.json (48 items, author model, NOT human)` | None | +0.392 | **UNCITABLE** | n=43, Po 0.70, PABAK 0.40, readout rate 0.63 vs adjudicated 0.51 |
| prefill k=5 readout vs blind adjudication (pooled_P1 continuation-only) | `labels/author_gold_prefill5.json (48 items, author model, NOT human)` | None | +0.294 | **UNCITABLE** | n=43, Po 0.65, PABAK 0.30, readout rate 0.77 vs adjudicated 0.51 |
| Gemma prefill k=5 flip SL (REAL JP2 judge, only real judged depth evidence) | `exp4 results/judge.jsonl (JP2) via this artifact` | +0.558 | +0.143 [+0.111, +0.182] | **SHRINKS** | real judge (not P1): lexicon over-counts Gemma SL flips ~4x |
| ALT-3 TD* (judge) | `exp3 results/analysis.json:primary.TDstar.point` | +0.230 | +0.271 [-0.774, +1.298] | **UNCITABLE** |  |
| exp3 GaMS SL refusal C0 | `exp3 results/analysis.json:primary.rates.gams|C0|sl` | +0.882 | +0.890 | **UNCITABLE** |  |
| exp3 GaMS SL refusal C1 (late persona ablation) | `exp3 results/analysis.json:primary.rates.gams|C1|sl` | +0.853 | +0.865 | **UNCITABLE** |  |
| C1 DiD_id | `exp1 results/analysis_results.json:identity.DiD_id` | +3.219 | +3.219 [+2.384, +4.384] | **SURVIVES** |  |
| C5a excess KL ratio gemma_it | `exp4 results/analysis.json:C5a.gemma_it.norm_matched.excess.est` | +0.298 | +0.298 [+0.154, +0.562] | **SURVIVES** | judge-free |
| C5a excess KL ratio gams3_it | `exp4 results/analysis.json:C5a.gams3_it.norm_matched.excess.est` | +0.574 | +0.574 [+0.409, +0.796] | **SURVIVES** | judge-free |
| Pareto hypervolume ratio GaMS/Gemma | `exp4 results/analysis.json:ALT4.pareto_hv_ratio_gams_over_gemma.est` | +2.292 | +2.292 [+2.014, +3.359] | **SURVIVES** | judge-free (Heretic objective values) |
| second-family agreement gemini-P1 vs gpt-4.1-mini-P1 (en) | `exp1 outputs/judge_gpt41mini.jsonl` | None | +0.623 | **SURVIVES** | Po 0.983, PABAK 0.966, AC1 0.982, n 829 |
| second-family agreement gemini-P1 vs gpt-4.1-mini-P1 (sl+slmt) | `exp1 outputs/judge_gpt41mini.jsonl` | None | +0.724 | **SURVIVES** | Po 0.936, PABAK 0.873, AC1 0.918, n 881 |

Status key: SURVIVES = same sign/verdict and CI covers the iter-1 point; SHRINKS/GROWS = CI excludes the iter-1 point, verdict unchanged; REVERSES = sign or verdict flips; UNCITABLE = at least one input cell is not readout-valid (value shown is provisional). No human annotation was performed; all labels are LLM-judge or surrogate readouts.
