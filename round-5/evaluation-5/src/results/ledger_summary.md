# Step 5 - correction ledger summary

Tokens audited: 1176; pointer claims: 22.

Counts by status: {'SURVIVES': 332, 'UNTRACEABLE': 844, 'REVERSES': 2, 'SHRINKS': 1}

Counts by match method: {'auto-context': 141, 'ambiguous': 842, 'auto-context (duplicate paths, same value)': 100, 'auto-unique': 72, 'unmatched': 2, 'pointer': 22}

Placebo (tokens shifted by 7-13 units of their last digit): auto-match rate 0.153 ({'auto-context': 132, 'ambiguous': 969, 'auto-unique': 48, 'unmatched': 27}). _auto-match equality is necessary, not sufficient: a SURVIVES by auto-unique/auto-context means a JSON leaf in the cited artifact holds the same number to the shown precision; ambiguous and unmatched tokens are UNTRACEABLE by default; claim-level verdicts are assessed only for pointer rows_

Attribution errors: ['exp15_pooled_kappa_051', 'exp14_BPB_attrib']

Claim-level reversals: ['exp15_b_gams', 'exp15_best_validation_claim', 'eval3_exp10_G3_op_edit', 'eval3_qwen_positive']

## Pointer rows (headline and review-named numbers)

| claim | line | paper value | verified | CI | status | claim status | attribution ok | source :: path | note |
|---|---|---|---|---|---|---|---|---|---|
| exp15_G3 | 1181 | -0.70 | -0.701 | [-1.01, -0.42] | SURVIVES |  | True | RUN/round-4/experiment-15/src/results/analysis.json :: headline/R/RAW/G3/point |  |
| exp15_G3_orig | 1181 | -1.17 | -1.171 | [-2.83, 0.22] | SURVIVES | SHRINKS | True | RUN/round-4/experiment-15/src/results/analysis.json :: headline/R/RAW/G3_orig/point | value reproduces; the 'baseline offset' reading is CEILING-ARTEFACT (FI_m=1) |
| exp15_G3_edit | 1181 | +0.47 | 0.470 | [-0.96, 2.14] | SURVIVES |  | True | RUN/round-4/experiment-15/src/results/analysis.json :: headline/R/RAW/G3_edit/point |  |
| exp15_MDE_attrib | 1181 | 0.42 | 0.422 | NA | SURVIVES |  | True | RUN/round-4/experiment-15/src/results/analysis.json :: headline/R/RAW/G3/mde | 0.42 is the MDE of G3, not of G3_edit (G3_edit MDE is headline/R/RAW/G3_edit/mde; 90% bound verdict/abs_G3_edit_bound_90) | this sentence attributes MDE 0.42 to G3 (correct); G3_edit's own MDE is 2.32 and its 90% bound 1.91 |
| exp15_b_gemma | 1183 | 0.94 | 0.938 | [0.75, 1.17] | SURVIVES |  | True | RUN/round-4/experiment-15/src/results/analysis.json :: headline/R/per_model/gemma_it/b/point |  |
| exp15_b_gams | 1183 | 0.80 | 0.797 | [0.63, 0.95] | REVERSES |  | True | RUN/round-4/experiment-15/src/results/analysis.json :: headline/R/per_model/gams3_it/b/point | 'parallel-curve geometry' is not established: b_GaMS CI95 [0.63, 0.95] excludes 1 and no b_diff CI was saved; replace with the two slope CIs |
| exp15_pooled_kappa_051 | 1203 | 0.51 | 0.508 | NA | SURVIVES |  | False | RUN/round-4/experiment-14/src/results/analysis.json :: judge_validity/L_primary|R/_pooled_edited/kappa3 | the 0.51 pooled edited kappa is exp14's (judge_validity/L_primary|R/_pooled_edited/kappa3), not exp15's |
| exp15_best_validation_claim | 1203 | 0.62 | 0.615 | NA | REVERSES |  | True | RUN/round-4/experiment-15/src/results/analysis.json :: judge_validity/cells/gams3_it|sl|edited/primary_R/Sp | 'best validation numbers in the study' is false: exp14 GaMS-SL edited Sp 0.81 > 0.62 |
| exp14_gams_sl_sp | 1141 | 0.81 | 0.811 | NA | SURVIVES |  | True | RUN/round-4/experiment-14/src/results/analysis.json :: judge_validity/L_primary|R/gams3_it|sl|edited/Sp |  |
| exp14_pooled_kappa | 1139 | 0.51 | 0.508 | NA | SURVIVES |  | True | RUN/round-4/experiment-14/src/results/analysis.json :: judge_validity/L_primary|R/_pooled_edited/kappa3 |  |
| exp14_OUT_SL | 1079 | 1.14 | 1.135 | [0.60, 1.56] | SURVIVES |  | True | RUN/round-4/experiment-14/src/results/analysis.json :: readouts/raw_R/OUT_SL|gemma_it/est |  |
| exp14_G3edit_slsl | 1095 | -1.84 | -1.838 | [-2.80, -0.78] | SURVIVES |  | True | RUN/round-4/experiment-14/src/results/analysis.json :: readouts/raw_R/G3edit|slsl/est |  |
| exp14_G3edit_husl | 1095 | -2.15 | -2.151 | [-3.16, -0.46] | SURVIVES |  | True | RUN/round-4/experiment-14/src/results/analysis.json :: readouts/raw_R/G3edit|husl/est |  |
| exp14_G3edit_ensl | 1079 | -1.26 | -1.257 | [-2.17, 0.20] | SURVIVES |  | True | RUN/round-4/experiment-14/src/results/analysis.json :: readouts/raw_R/G3edit|ensl/est |  |
| exp14_BPB_attrib | 1156 | 1.20 | 1.199 | NA | SURVIVES |  | False | RUN/round-3/experiment-12/src/results/competence_covariates.json :: gemma_it/sl/orig_bpb | BPB comes from exp12 competence_covariates.json (resolved by value search inside that file) |
| eval3_pooled_G3 | 950 | -1.17 | -1.170 | [-1.84, -0.50] | SURVIVES |  | True | RUN/round-4/evaluation-3/src/results/recompute.json :: pooling/primary|raw_primary|G3/REML_HKSJ/est |  |
| eval3_exp10_G3_op_edit | 969 | -3.40 | -3.403 | [-6.09, -1.30] | SURVIVES | REVERSES | True | RUN/round-4/evaluation-3/src/results/recompute.json :: curves/exp10_op|raw_primary|R/G3_op_edit/est | value survives; the paper's blanket claim that G3_edit spans zero everywhere REVERSES (this CI excludes 0) |
| eval3_exp9_G3_edit | 971 | 1.43 | 1.434 | [0.29, 2.98] | SURVIVES |  | True | RUN/round-4/evaluation-3/src/results/recompute.json :: curves/exp9_lambda|raw_primary|R/G3_edit/est |  |
| exp10_u_lang_alpha50 | 839 | 2.96 | 1.785 | NA | SHRINKS |  | True | RUN/round-3/experiment-10/src/results/analysis.json :: induction/surrogate/gemini|R|gams3_it|exclude/curves/u_lang|sl/alpha50 | GaMS3 u_lang alpha50 for SLOVENE refusal is 1.78; 2.96 is not the SL value |
| exp4_C3_matched17 | 211 | -1.86 | -1.862 | NA | SURVIVES |  | True | RUN/round-1/experiment-4/src/results/analysis.json :: C3/matched_first_k_trials/all_pairs/G3/est |  |
| eval2_RG_IG | 0 | -5.10 | -5.105 | NA | SURVIVES |  | True | RUN/round-3/evaluation-2/src/results/eval_results.json :: step3_lag/B/primary_R_RG/G3_50/est | review: eval2 RG-corrected IG curve B -5.10 [-11.17, 5.60] |
| eval3_qwen_positive | 0 | 1.57 | 1.574 | NA | SURVIVES | REVERSES | True | RUN/round-4/evaluation-3/src/results/recompute.json :: curves/exp8_A1|archived_arch_q14|R/G3/est | 'negative under every judge' REVERSES: the archived Qwen3-14B G3 on exp8_A1 is positive |
