# Step 1 - ceiling sensitivity of exp15's baseline component G3_orig

_POST-HOC sensitivity analysis (thresholds frozen in protocol_eval.yaml); can downgrade, cannot confirm_

**Verdict: CEILING-ARTEFACT.** exp15's baseline component is 'CEILING-ARTEFACT': 1 flip(s) move it inside the margin (G3_orig -1.17; 4 flip(s) reach zero; the probability-scale DiD is -0.7 pp, 95% CI [-3.3, 1.7]; J1's pooled unedited error rates imply about 15.6 mislabelled items across the four lambda-0 cells).

## Lambda-0 counts (J1 raw, R coding; smoke test vs analysis.json steps_R)

| cell | k refuse / n | rate | Hautus logit |
|---|---|---|---|
| gemma_en | 294 / 300 | 0.9800 | 3.813 |
| gemma_sl | 299 / 300 | 0.9967 | 5.297 |
| gams_en | 289 / 300 | 0.9633 | 3.226 |
| gams_sl | 292 / 300 | 0.9733 | 3.538 |

M0_Gemma 1.48317, M0_GaMS 0.31259, G3_orig -1.17058 (saved -1.17058; smoke PASS).

## 1a Fragility index (exact enumeration of single-label flips)

FI_m = **1** (flips to bring G3_orig inside (-0.675, +0.675)), FI_0 = **4** (flips to reach zero, i.e. a sign change).

| flips | best reachable G3_orig | cheapest deltas |
|---|---|---|
| 0 | -1.171 | {'gemma_en': 0, 'gemma_sl': 0, 'gams_en': 0, 'gams_sl': 0} |
| 1 | -0.656 | {'gemma_en': 0, 'gemma_sl': -1, 'gams_en': 0, 'gams_sl': 0} |
| 2 | -0.317 | {'gemma_en': 0, 'gemma_sl': -2, 'gams_en': 0, 'gams_sl': 0} |
| 3 | -0.062 | {'gemma_en': 0, 'gemma_sl': -3, 'gams_en': 0, 'gams_sl': 0} |
| 4 | 0.142 | {'gemma_en': 0, 'gemma_sl': -4, 'gams_en': 0, 'gams_sl': 0} |
| 5 | 0.313 | {'gemma_en': 0, 'gemma_sl': -5, 'gams_en': 0, 'gams_sl': 0} |

Other estimators: laplace: G3_orig -0.972, FI_m 1, FI_0 4; half_n: G3_orig -1.480, FI_m 2, FI_0 4; jeffreys_logit_mean: G3_orig -1.445, FI_m 2, FI_0 4

## 1b Paired exact view (same 300 items in both arms)

| model | b (SL refuse, EN not) | c (EN refuse, SL not) | McNemar exact p | SL-EN pp [Newcombe 95%] | ln(b/c) [exact 95%] |
|---|---|---|---|---|---|
| gemma_it | 6 | 1 | 0.125 | 1.67 [-0.21, 3.98] | 1.79 [-0.32, 5.62] |
| gams3_it | 7 | 4 | 0.549 | 1.00 [-1.45, 3.62] | 0.56 [-0.81, 2.10] |

Probability-scale DiD = -0.67 pp, item-bootstrap 95% CI [-3.33, 1.67].

## 1c Leave-k-items (items removed from both models and arms)

| k | mode | min | p05 | p50 | p95 | max | share inside m | worst case (drop Gemma discordant-b items) |
|---|---|---|---|---|---|---|---|---|
| 1 | exhaustive | -2.144 | -1.171 | -1.171 | -1.171 | -0.872 | 0.0000 | -1.000 |
| 2 | exhaustive | -2.238 | -1.171 | -1.171 | -1.095 | -0.615 | 0.0001 | -0.891 |
| 3 | random_20000 | -2.238 | -1.265 | -1.171 | -1.042 | -0.615 | 0.0003 | -0.611 |
| 4 | random_20000 | -2.342 | -1.265 | -1.171 | -1.000 | -0.615 | 0.0004 | -0.124 |
| 5 | random_20000 | -2.342 | -1.265 | -1.171 | -1.000 | -0.554 | 0.0008 | 0.390 |

## 1d/1e Genuinely different extreme-proportion estimators (item bootstrap B=2000)

_Hautus log-linear, the Jeffreys posterior MEAN of p and the Haldane-Anscombe empirical logit give the SAME logit ln((k+.5)/(n-k+.5)); they are one estimator, not three._

| estimator | G3_orig point | bootstrap 95% CI | share of draws inside m |
|---|---|---|---|
| i_hautus_loglinear | -1.171 | [-2.86, 0.28] | 0.22 |
| ii_laplace_add1 | -0.972 | [-2.22, 0.30] | 0.28 |
| iii_half_n_rule_extreme_cells_only | -1.480 | [-2.80, 0.32] | 0.16 |
| iv_jeffreys_posterior_mean_of_logit | -1.445 | [-4.07, 0.29] | 0.15 |
| v_paired_conditional_logit_diff | -1.232 | [-2.94, 0.69] | 0.27 |
| vi_probability_scale_pp | -0.667 | [-3.33, 1.67] | NA |

Jeffreys posterior of G3_orig (200000 draws): mean -1.445, 95% CrI [-3.98, 0.58], P(G3_orig < -m) = 0.742, P(G3_orig < 0) = 0.911.

Model-label permutation (within item, 5000 draws): null mean 0.012, sd 0.625, two-sided p = 0.0760.

## 1f Expected judge-error count vs fragility (Walsh-style comparison)

Pooled unedited J1 validation (author-model adjudication, NOT human): Se 1.00 (n+ 35), Sp 0.40 (n- 5, Wilson [0.12, 0.77]). Expected mislabels over the four lambda-0 cells: 15.6 vs FI_m = 1.

_Unedited-cell specificity rests on only 1-2 adjudicated NON-refusals per cell (Sp CI spans most of [0,1]); the expected-mislabel count is therefore an order-of-magnitude comparison, not an estimate._

## 1g Extension to every eval3 body (lambda 0; smoke-tested against eval3 recompute.json)

| body | label column | k/n (GemmaEN, GemmaSL, GaMSEN, GaMSSL) | G3_orig | FI_m | FI_0 | estimator range | prob DiD pp [95%] | verdict |
|---|---|---|---|---|---|---|---|---|
| exp9_lambda | gemini_raw_prim3 | 268/299, 299/300, 275/298, 287/300 | -2.557 | 9 | 13 | [-2.93, -2.30] | -6.65 [-10.4, -2.9] | ROBUST-OFFSET |
| exp9_lambda | gpt41mini_sec3 | 19/21, 41/41, 24/24, 48/52 | -3.879 | 4 | 4 | [-6.09, -2.78] | -17.22 [-33.4, -4.2] | FRAGILE |
| exp9_lambda | ttj3 | 98/101, 100/100, 142/147, 98/100 | -1.547 | 1 | 2 | [-2.55, -1.08] | -1.57 [-5.3, 1.8] | CEILING-ARTEFACT |
| exp9_lambda | arch_j1 | 283/300, 300/300, 279/300, 286/300 | -3.195 | 6 | 12 | [-4.43, -2.54] | -3.33 [-6.7, 0.0] | FRAGILE |
| exp9_lambda | arch_j2 | 46/50, 48/50, 45/50, 49/50 | 0.754 | 1 | 2 | [0.63, 0.96] | 4.00 [-7.8, 16.4] | NOT-OUTSIDE-MARGIN |
| exp9_lambda | arch_lex | 295/300, 299/300, 279/300, 286/300 | -0.894 | 1 | 3 | [-1.19, -0.70] | 1.00 [-1.7, 3.7] | CEILING-ARTEFACT |
| exp11_final | gemini_raw_prim3 | 192/200, 198/200, 193/200, 194/200 | -1.106 | 2 | 5 | [-1.26, -0.99] | -2.50 [-5.0, 0.0] | CEILING-ARTEFACT |
| exp11_final | gpt41mini_sec3 | 52/56, 60/60, 63/66, 91/91 | -0.028 | 0 | 1 | [-0.06, -0.00] | -2.60 [-10.5, 4.2] | NOT-OUTSIDE-MARGIN |
| exp11_final | ttj3 | 192/200, 199/200, 193/200, 197/200 | -0.988 | 1 | 3 | [-1.25, -0.83] | -1.50 [-4.0, 1.0] | CEILING-ARTEFACT |
| exp11_final | arch_q14 | 196/200, 198/200, 194/200, 193/200 | -0.746 | 1 | 3 | [-0.86, -0.66] | -1.50 [-5.0, 1.0] | CEILING-ARTEFACT |
| exp11_final | arch_lex | 199/200, 198/200, 192/200, 191/200 | 0.399 | 0 | 1 | [0.30, 0.58] | 0.00 [-3.0, 3.5] | NOT-OUTSIDE-MARGIN |
| exp8_A1 | gemini_raw_prim3 | 191/199, 199/200, 184/199, 192/200 | -1.132 | 1 | 4 | [-1.45, -0.93] | 0.02 [-3.5, 3.5] | CEILING-ARTEFACT |
| exp8_A1 | gpt41mini_sec3 | 27/28, 64/64, 53/57, 120/124 | -1.139 | 1 | 2 | [-2.05, -0.73] | 0.22 [-9.6, 9.4] | CEILING-ARTEFACT |
| exp8_A1 | arch_q14 | 193/200, 199/200, 193/200, 193/200 | -1.640 | 3 | 6 | [-1.98, -1.42] | -3.00 [-6.5, 0.5] | FRAGILE |
| exp8_A1 | arch_llama8b | 123/146, 33/37, 166/182, 119/120 | 1.718 | 3 | 4 | [1.53, 2.01] | 3.02 [-8.0, 15.9] | NOT-OUTSIDE-MARGIN |
| exp8_A1 | arch_lex | 197/200, 199/200, 188/200, 189/200 | -0.769 | 1 | 2 | [-1.02, -0.62] | -0.50 [-4.0, 3.0] | CEILING-ARTEFACT |
| exp10_op | gemini_raw_prim3 | 158/160, 159/160, 153/159, 159/160 | 0.988 | 1 | 1 | [0.88, 1.13] | 2.52 [-0.6, 6.3] | NOT-OUTSIDE-MARGIN |
| exp10_op | gpt41mini_sec3 | 61/62, 80/81, 74/76, 107/110 | -0.239 | 0 | 1 | [-0.31, -0.19] | -0.47 [-4.9, 3.3] | NOT-OUTSIDE-MARGIN |
| exp10_op | arch_lex | 147/160, 159/160, 149/160, 153/160 | -1.822 | 4 | 7 | [-2.16, -1.59] | -5.00 [-10.6, 0.6] | FRAGILE |
| exp8_B | gemini_raw_prim3 | 95/99, 100/100, 89/99, 96/100 | -1.326 | 1 | 2 | [-2.41, -0.80] | 2.06 [-3.9, 8.1] | CEILING-ARTEFACT |
| exp8_B | arch_q14 | 96/100, 100/100, 95/100, 96/100 | -2.027 | 2 | 4 | [-3.16, -1.46] | -3.00 [-9.0, 3.0] | CEILING-ARTEFACT |
| exp8_B | arch_lex | 99/100, 100/100, 92/100, 95/100 | -0.641 | 0 | 1 | [-1.51, -0.20] | 2.00 [-3.0, 8.0] | NOT-OUTSIDE-MARGIN |

Note: gpt41mini_sec3 counts use the IPW-sampled second-reader subset unweighted (descriptive only).
