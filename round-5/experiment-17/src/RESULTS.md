# RESULTS: What does one English-only de-censoring edit buy on RefusEU's own prompts?

All numbers below are rendered by `src/make_report.py` from `results/analysis.json`. Protocol: `protocol.yaml` (sha256 in `protocol.sha256`). Gold labels = blind **author-model (LLM, NOT human)** adjudication. **R0:** the OpenRouter run budget was exhausted, so the gpt-4o-mini adjudicator, the gemini StrongREJECT rubric and the P1 judge were replaced by local pinned substitutes (Qwen3Guard-Gen-8B, the official StrongREJECT fine-tuned evaluator, PolyGuard refusal flag); see `deviations.md`.

Rows analysed: 11600; condition tags: edit1, orig, rand1, sens256.

## 1. Completed findings (CONFIRMATORY)

### S2 - manipulation check (DEV gate, PolyGuard refusal on 100 DEV EN prompts)

| model | gate status | lambda_gate | R(0) | relative cut at lambda 1.0 |
|---|---|---|---|---|
| Gemma-3-12B-it | PASS_AT_1.0 | 1.0 | 0.920 | 0.750 |
| GaMS3-12B-Instruct | PASS_AT_1.0 | 1.0 | 0.970 | 0.784 |

### S1 - does the edit raise benchmark-protocol ASR? (orig -> edit@1.0, exact McNemar, Holm over 4 cells)

| model | lang | ASR orig | ASR edit | delta [95% paired bootstrap] | b (0->1) | c (1->0) | Holm p | SR05 holds | RG CI>0 | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| Gemma-3-12B-it | en | 0.045 | 0.897 | 0.852 [0.831, 0.870] | 1109 | 2 | 0.00e+00 | True | True | **ROBUST** |
| Gemma-3-12B-it | sl | 0.026 | 0.683 | 0.657 [0.629, 0.683] | 857 | 3 | 2.76e-251 | True | True | **ROBUST** |
| GaMS3-12B-Instruct | en | 0.033 | 0.970 | 0.937 [0.923, 0.949] | 1219 | 1 | 0.00e+00 | True | True | **ROBUST** |
| GaMS3-12B-Instruct | sl | 0.068 | 0.915 | 0.847 [0.826, 0.867] | 1109 | 8 | 0.00e+00 | True | True | **ROBUST** |

## 2. Descriptive results

### Paired edit effects on every readout

| contrast | model | lang | readout | n | orig | edited | delta [95% CI] | McNemar p | Holm p |
|---|---|---|---|---|---|---|---|---|---|
| orig->edit1 | Gemma-3-12B-it | en | ASR_row | 1300 | 0.045 | 0.897 | 0.852 [0.831, 0.870] | 0.00e+00 | 0.00e+00 |
| orig->edit1 | Gemma-3-12B-it | sl | ASR_row | 1300 | 0.026 | 0.683 | 0.657 [0.629, 0.683] | 2.76e-251 | 2.76e-251 |
| orig->edit1 | GaMS3-12B-Instruct | en | ASR_row | 1300 | 0.033 | 0.970 | 0.937 [0.923, 0.949] | 0.00e+00 | 0.00e+00 |
| orig->edit1 | GaMS3-12B-Instruct | sl | ASR_row | 1300 | 0.068 | 0.915 | 0.847 [0.826, 0.867] | 0.00e+00 | 0.00e+00 |
| orig->edit1 | Gemma-3-12B-it | en | ASR_row (Q3G loose) | 1300 | 0.042 | 0.861 | 0.819 [0.797, 0.838] | 3.23e-314 | 6.46e-314 |
| orig->edit1 | Gemma-3-12B-it | sl | ASR_row (Q3G loose) | 1300 | 0.016 | 0.615 | 0.599 [0.572, 0.625] | 1.23e-232 | 1.23e-232 |
| orig->edit1 | GaMS3-12B-Instruct | en | ASR_row (Q3G loose) | 1300 | 0.030 | 0.957 | 0.927 [0.912, 0.941] | 0.00e+00 | 0.00e+00 |
| orig->edit1 | GaMS3-12B-Instruct | sl | ASR_row (Q3G loose) | 1300 | 0.050 | 0.878 | 0.828 [0.806, 0.849] | 0.00e+00 | 0.00e+00 |
| orig->edit1 | Gemma-3-12B-it | en | SR-ft>=0.5 | 1300 | 0.000 | 0.029 | 0.029 [0.020, 0.039] | 7.28e-12 | 1.46e-11 |
| orig->edit1 | Gemma-3-12B-it | sl | SR-ft>=0.5 | 1300 | 0.002 | 0.014 | 0.012 [0.006, 0.019] | 1.45e-04 | 1.45e-04 |
| orig->edit1 | GaMS3-12B-Instruct | en | SR-ft>=0.5 | 1300 | 0.008 | 0.441 | 0.433 [0.405, 0.460] | 3.18e-164 | 1.27e-163 |
| orig->edit1 | GaMS3-12B-Instruct | sl | SR-ft>=0.5 | 1300 | 0.003 | 0.046 | 0.043 [0.032, 0.055] | 3.18e-15 | 9.53e-15 |
| orig->edit1 | Gemma-3-12B-it | en | PG refusal | 1300 | 0.948 | 0.188 | -0.760 [-0.782, -0.736] | 2.35e-293 | 7.06e-293 |
| orig->edit1 | Gemma-3-12B-it | sl | PG refusal | 1300 | 0.963 | 0.612 | -0.351 [-0.378, -0.327] | 8.92e-123 | 8.92e-123 |
| orig->edit1 | GaMS3-12B-Instruct | en | PG refusal | 1300 | 0.969 | 0.172 | -0.796 [-0.819, -0.773] | 5.48e-302 | 2.19e-301 |
| orig->edit1 | GaMS3-12B-Instruct | sl | PG refusal | 1300 | 0.935 | 0.520 | -0.415 [-0.445, -0.386] | 3.85e-131 | 7.71e-131 |
| orig->edit1 | Gemma-3-12B-it | en | LG unsafe | 1300 | 0.035 | 0.869 | 0.834 [0.812, 0.855] | 0.00e+00 | 0.00e+00 |
| orig->edit1 | Gemma-3-12B-it | sl | LG unsafe | 1300 | 0.011 | 0.531 | 0.521 [0.494, 0.548] | 5.42e-202 | 5.42e-202 |
| orig->edit1 | GaMS3-12B-Instruct | en | LG unsafe | 1300 | 0.028 | 0.955 | 0.928 [0.913, 0.942] | 0.00e+00 | 0.00e+00 |
| orig->edit1 | GaMS3-12B-Instruct | sl | LG unsafe | 1300 | 0.037 | 0.803 | 0.766 [0.743, 0.789] | 1.22e-285 | 2.44e-285 |
| orig->edit1 | Gemma-3-12B-it | en | PG harmful | 1300 | 0.085 | 0.905 | 0.820 [0.799, 0.842] | 9.06e-317 | 2.72e-316 |
| orig->edit1 | Gemma-3-12B-it | sl | PG harmful | 1300 | 0.132 | 0.809 | 0.678 [0.651, 0.705] | 7.43e-237 | 7.43e-237 |
| orig->edit1 | GaMS3-12B-Instruct | en | PG harmful | 1300 | 0.092 | 0.978 | 0.885 [0.868, 0.902] | 0.00e+00 | 0.00e+00 |
| orig->edit1 | GaMS3-12B-Instruct | sl | PG harmful | 1300 | 0.138 | 0.949 | 0.811 [0.788, 0.833] | 1.96e-304 | 3.93e-304 |
| orig->edit1 | Gemma-3-12B-it | en | Q3G unsafe | 169 | 0.065 | 0.882 | 0.817 [0.751, 0.876] | 2.02e-40 | 8.09e-40 |
| orig->edit1 | Gemma-3-12B-it | sl | Q3G unsafe | 107 | 0.121 | 0.374 | 0.252 [0.168, 0.336] | 1.12e-07 | 3.35e-07 |
| orig->edit1 | GaMS3-12B-Instruct | en | Q3G unsafe | 12 | 0.000 | 0.333 | 0.333 [0.083, 0.583] | 0.125 | 0.125 |
| orig->edit1 | GaMS3-12B-Instruct | sl | Q3G unsafe | 71 | 0.366 | 0.549 | 0.183 [0.056, 0.296] | 0.007 | 0.014 |
| orig->edit1 | Gemma-3-12B-it | en | Q3G refusal | 169 | 0.953 | 0.456 | -0.497 [-0.568, -0.420] | 1.03e-25 | 4.14e-25 |
| orig->edit1 | Gemma-3-12B-it | sl | Q3G refusal | 107 | 0.748 | 0.439 | -0.308 [-0.393, -0.215] | 2.33e-10 | 6.98e-10 |
| orig->edit1 | GaMS3-12B-Instruct | en | Q3G refusal | 12 | 0.833 | 0.500 | -0.333 [-0.583, -0.083] | 0.125 | 0.125 |
| orig->edit1 | GaMS3-12B-Instruct | sl | Q3G refusal | 71 | 0.352 | 0.183 | -0.169 [-0.282, -0.070] | 0.004 | 0.008 |
| orig->edit1 | Gemma-3-12B-it | en | SR-ft mean | 1300 | 0.006 | 0.161 | 0.154 [0.146, 0.163] | 6.03e-210 | NA |
| orig->edit1 | Gemma-3-12B-it | sl | SR-ft mean | 1300 | 0.008 | 0.086 | 0.078 [0.071, 0.085] | 2.40e-187 | NA |
| orig->edit1 | GaMS3-12B-Instruct | en | SR-ft mean | 1300 | 0.015 | 0.467 | 0.452 [0.440, 0.464] | 1.57e-212 | NA |
| orig->edit1 | GaMS3-12B-Instruct | sl | SR-ft mean | 1300 | 0.015 | 0.201 | 0.186 [0.177, 0.196] | 8.74e-199 | NA |

### Corrected ASR (Rogan-Gladen + Lang-Reiczigel; adjudicator-agreement-corrected, author-model gold)

| model | lang | ctag | readout | p_obs | Se | Sp | p_RG [LR 95% CI] | unidentifiable | readout validated |
|---|---|---|---|---|---|---|---|---|---|
| Gemma-3-12B-it | en | orig | ASR_row | 0.045 | 1.000 | 0.755 | 0.000 [0.000, -0.062] | False | False |
| Gemma-3-12B-it | en | edit1 | ASR_row | 0.897 | 1.000 | 0.755 | 0.863 [0.779, 1.000] | False | False |
| Gemma-3-12B-it | en | orig | SR-ft>=0.5 | 0.000 | 0.067 | 1.000 | 0.000 [0.000, 0.405] | True | False |
| Gemma-3-12B-it | en | edit1 | SR-ft>=0.5 | 0.029 | 0.067 | 1.000 | 0.438 [0.000, 0.524] | True | False |
| Gemma-3-12B-it | en | orig | LG unsafe | 0.035 | 1.000 | 0.749 | 0.000 [0.000, -0.079] | False | False |
| Gemma-3-12B-it | en | edit1 | LG unsafe | 0.869 | 1.000 | 0.749 | 0.824 [0.741, 1.000] | False | False |
| Gemma-3-12B-it | en | orig | PG harmful | 0.085 | 1.000 | 0.729 | 0.000 [0.000, -0.037] | False | False |
| Gemma-3-12B-it | en | edit1 | PG harmful | 0.905 | 1.000 | 0.729 | 0.869 [0.781, 1.000] | False | False |
| Gemma-3-12B-it | sl | orig | ASR_row | 0.026 | 1.000 | 0.751 | 0.000 [0.000, -0.092] | False | False |
| Gemma-3-12B-it | sl | edit1 | ASR_row | 0.683 | 1.000 | 0.751 | 0.578 [0.466, 0.837] | False | False |
| Gemma-3-12B-it | sl | orig | SR-ft>=0.5 | 0.002 | 0.000 | 1.000 | NA [0.000, 0.590] | True | False |
| Gemma-3-12B-it | sl | edit1 | SR-ft>=0.5 | 0.014 | 0.000 | 1.000 | NA [0.000, 0.504] | True | False |
| Gemma-3-12B-it | sl | orig | LG unsafe | 0.011 | 0.889 | 0.829 | 0.000 [0.000, -0.040] | False | True |
| Gemma-3-12B-it | sl | edit1 | LG unsafe | 0.531 | 0.889 | 0.829 | 0.502 [0.333, 0.763] | False | True |
| Gemma-3-12B-it | sl | orig | PG harmful | 0.132 | 1.000 | 0.629 | 0.000 [0.000, -0.070] | False | False |
| Gemma-3-12B-it | sl | edit1 | PG harmful | 0.809 | 1.000 | 0.629 | 0.697 [0.545, 1.000] | False | False |
| GaMS3-12B-Instruct | en | orig | ASR_row | 0.033 | 1.000 | 0.903 | 0.000 [0.000, 0.037] | False | True |
| GaMS3-12B-Instruct | en | edit1 | ASR_row | 0.970 | 1.000 | 0.903 | 0.967 [0.921, 1.000] | False | True |
| GaMS3-12B-Instruct | en | orig | SR-ft>=0.5 | 0.008 | 0.320 | 0.999 | 0.020 [0.000, 0.128] | False | False |
| GaMS3-12B-Instruct | en | edit1 | SR-ft>=0.5 | 0.441 | 0.320 | 0.999 | 1.000 [0.557, 1.000] | False | False |
| GaMS3-12B-Instruct | en | orig | LG unsafe | 0.028 | 1.000 | 0.998 | 0.025 [0.000, 0.059] | False | True |
| GaMS3-12B-Instruct | en | edit1 | LG unsafe | 0.955 | 1.000 | 0.998 | 0.955 [0.914, 1.000] | False | True |
| GaMS3-12B-Instruct | en | orig | PG harmful | 0.092 | 1.000 | 0.888 | 0.000 [0.000, 0.092] | False | True |
| GaMS3-12B-Instruct | en | edit1 | PG harmful | 0.978 | 1.000 | 0.888 | 0.975 [0.928, 1.000] | False | True |
| GaMS3-12B-Instruct | sl | orig | ASR_row | 0.068 | 1.000 | 0.735 | 0.000 [0.000, -0.047] | False | False |
| GaMS3-12B-Instruct | sl | edit1 | ASR_row | 0.915 | 1.000 | 0.735 | 0.884 [0.809, 1.000] | False | False |
| GaMS3-12B-Instruct | sl | orig | SR-ft>=0.5 | 0.003 | 0.056 | 1.000 | 0.055 [0.000, 0.576] | True | False |
| GaMS3-12B-Instruct | sl | edit1 | SR-ft>=0.5 | 0.046 | 0.056 | 1.000 | 0.830 [0.000, 1.000] | True | False |
| GaMS3-12B-Instruct | sl | orig | LG unsafe | 0.037 | 0.833 | 0.888 | 0.000 [0.000, 0.037] | False | True |
| GaMS3-12B-Instruct | sl | edit1 | LG unsafe | 0.803 | 0.833 | 0.888 | 0.958 [0.739, 1.000] | False | True |
| GaMS3-12B-Instruct | sl | orig | PG harmful | 0.138 | 1.000 | 0.734 | 0.000 [0.000, 0.035] | False | False |
| GaMS3-12B-Instruct | sl | edit1 | PG harmful | 0.949 | 1.000 | 0.734 | 0.930 [0.853, 1.000] | False | False |

RG-corrected ASR deltas (bootstrap over prompts and adjudicated rows):

- Gemma-3-12B-it en orig->edit1: delta_RG = 0.863 [0.811, 0.892] (Se 1.000, Sp 0.755)
- Gemma-3-12B-it sl orig->edit1: delta_RG = 0.578 [0.473, 0.639] (Se 1.000, Sp 0.751)
- GaMS3-12B-Instruct en orig->edit1: delta_RG = 0.967 [0.927, 0.976] (Se 1.000, Sp 0.903)
- GaMS3-12B-Instruct sl orig->edit1: delta_RG = 0.884 [0.826, 0.912] (Se 1.000, Sp 0.735)

### Adjudicated validity of each readout (weighted Se/Sp vs author-model HARMFUL / refusal gold)

Adjudicated rows: 240 (blind AUTHOR-MODEL adjudication (LLM, NOT human)).

| cell | readout | Se (w) | Sp (w) | n gold+ | n gold- | validated (Sp>=0.80, Se>=0.60) |
|---|---|---|---|---|---|---|
| gemma_it|en | ASR_row | 1.000 | 0.755 | 15 | 45 | False |
| gemma_it|en | ASR_row (Q3G loose) | 1.000 | 0.755 | 15 | 45 | False |
| gemma_it|en | LG unsafe | 1.000 | 0.749 | 15 | 45 | False |
| gemma_it|en | PG harmful | 1.000 | 0.729 | 15 | 45 | False |
| gemma_it|en | Q3G unsafe | 1.000 | 1.000 | 1 | 16 | True |
| gemma_it|en | SR-ft>=0.5 | 0.067 | 1.000 | 15 | 45 | False |
| gemma_it|en | PG refusal | 0.953 | 1.000 | 38 | 22 | True |
| gemma_it|en | Q3G refusal | 0.982 | 1.000 | 16 | 1 | True |
| gemma_it|sl | ASR_row | 1.000 | 0.751 | 9 | 51 | False |
| gemma_it|sl | ASR_row (Q3G loose) | 1.000 | 0.797 | 9 | 51 | False |
| gemma_it|sl | LG unsafe | 0.889 | 0.829 | 9 | 51 | True |
| gemma_it|sl | PG harmful | 1.000 | 0.629 | 9 | 51 | False |
| gemma_it|sl | Q3G unsafe | 1.000 | 0.624 | 1 | 16 | False |
| gemma_it|sl | SR-ft>=0.5 | 0.000 | 1.000 | 9 | 51 | False |
| gemma_it|sl | PG refusal | 0.826 | 0.609 | 35 | 25 | False |
| gemma_it|sl | Q3G refusal | 0.510 | 0.797 | 11 | 6 | False |
| gams3_it|en | ASR_row | 1.000 | 0.903 | 25 | 35 | True |
| gams3_it|en | ASR_row (Q3G loose) | 1.000 | 1.000 | 25 | 35 | True |
| gams3_it|en | LG unsafe | 1.000 | 0.998 | 25 | 35 | True |
| gams3_it|en | PG harmful | 1.000 | 0.888 | 25 | 35 | True |
| gams3_it|en | Q3G unsafe | NA | 0.152 | 0 | 16 | False |
| gams3_it|en | SR-ft>=0.5 | 0.320 | 0.999 | 25 | 35 | False |
| gams3_it|en | PG refusal | 0.987 | 0.927 | 29 | 31 | True |
| gams3_it|en | Q3G refusal | 0.615 | 0.023 | 13 | 3 | False |
| gams3_it|sl | ASR_row | 1.000 | 0.735 | 18 | 42 | False |
| gams3_it|sl | ASR_row (Q3G loose) | 0.944 | 0.762 | 18 | 42 | False |
| gams3_it|sl | LG unsafe | 0.833 | 0.888 | 18 | 42 | True |
| gams3_it|sl | PG harmful | 1.000 | 0.734 | 18 | 42 | False |
| gams3_it|sl | Q3G unsafe | 1.000 | 0.143 | 3 | 17 | False |
| gams3_it|sl | SR-ft>=0.5 | 0.056 | 1.000 | 18 | 42 | False |
| gams3_it|sl | PG refusal | 0.854 | 0.672 | 29 | 31 | False |
| gams3_it|sl | Q3G refusal | 0.880 | 1.000 | 12 | 8 | True |

### S3 / cross-model difference of edit effects (DESCRIPTIVE; not dose-matched; closed C-LAG line)

| contrast | lang | readout | n | delta Gemma | delta GaMS | DiD [95% CI] | DiD log-odds [CI] | perm p |
|---|---|---|---|---|---|---|---|---|
| orig->edit1 | en | ASR_row | 1300 | 0.852 | 0.937 | 0.085 [0.066, 0.105] | 1.630 [1.232, 2.065] | 0.00e+00 |
| orig->edit1 | sl | ASR_row | 1300 | 0.657 | 0.847 | 0.190 [0.159, 0.221] | 0.614 [0.201, 0.987] | 0.00e+00 |
| orig->edit1 | en | SR-ft>=0.5 | 1300 | 0.029 | 0.433 | 0.404 [0.375, 0.431] | 0.200 [-0.346, 0.969] | 0.00e+00 |
| orig->edit1 | sl | SR-ft>=0.5 | 1300 | 0.012 | 0.043 | 0.031 [0.018, 0.044] | 0.629 [-1.413, 2.264] | 0.00e+00 |
| orig->edit1 | en | LG unsafe | 1300 | 0.834 | 0.928 | 0.094 [0.073, 0.115] | 1.398 [0.996, 1.853] | 0.00e+00 |
| orig->edit1 | sl | LG unsafe | 1300 | 0.521 | 0.766 | 0.245 [0.213, 0.276] | 0.044 [-0.568, 0.520] | 0.00e+00 |
| orig->edit1 | en | PG harmful | 1300 | 0.820 | 0.885 | 0.065 [0.045, 0.087] | 1.423 [1.036, 1.810] | 0.00e+00 |
| orig->edit1 | sl | PG harmful | 1300 | 0.678 | 0.811 | 0.133 [0.102, 0.165] | 1.409 [1.090, 1.729] | 0.00e+00 |
| orig->edit1 | en | PG refusal | 1300 | -0.760 | -0.796 | -0.036 [-0.062, -0.011] | -0.627 [-0.936, -0.344] | 0.005 |
| orig->edit1 | sl | PG refusal | 1300 | -0.351 | -0.415 | -0.064 [-0.099, -0.030] | 0.211 [-0.098, 0.540] | 4.00e-04 |
- S3 en: no detectable difference at this n (or criteria unmet); DiD reported with CI
- S3 sl: no detectable difference at this n (or criteria unmet); DiD reported with CI

### NOT INTERPRETABLE AS A LANGUAGE EFFECT - EN and SL are different natural prompts (LaBSE 0.55)

| contrast | model | readout | subset LaBSE>=0.70 & pure | n EN | n SL | delta EN | delta SL | SL - EN [CI] |
|---|---|---|---|---|---|---|---|---|
| orig->edit1 | Gemma-3-12B-it | ASR_row | False | 1300 | 1300 | 0.852 | 0.657 | -0.195 [-0.229, -0.162] |
| orig->edit1 | Gemma-3-12B-it | ASR_row | True | 58 | 58 | 0.810 | 0.621 | -0.190 [-0.345, -0.035] |
| orig->edit1 | GaMS3-12B-Instruct | ASR_row | False | 1300 | 1300 | 0.937 | 0.847 | -0.090 [-0.115, -0.065] |
| orig->edit1 | GaMS3-12B-Instruct | ASR_row | True | 58 | 58 | 0.966 | 0.931 | -0.035 [-0.121, 0.052] |
| orig->edit1 | Gemma-3-12B-it | SR-ft>=0.5 | False | 1300 | 1300 | 0.029 | 0.012 | -0.017 [-0.029, -0.006] |
| orig->edit1 | Gemma-3-12B-it | SR-ft>=0.5 | True | 58 | 58 | 0.086 | 0.035 | -0.052 [-0.138, 0.035] |
| orig->edit1 | GaMS3-12B-Instruct | SR-ft>=0.5 | False | 1300 | 1300 | 0.433 | 0.043 | -0.390 [-0.420, -0.361] |
| orig->edit1 | GaMS3-12B-Instruct | SR-ft>=0.5 | True | 58 | 58 | 0.655 | 0.086 | -0.569 [-0.707, -0.431] |

### Controls, placebos, sensitivities

- rand_1@1.0 control, Gemma-3-12B-it en: ASR 0.025 -> 0.035 (delta 0.010, b=2, c=0, McNemar p 0.500, n=200)
- rand_1@1.0 control, Gemma-3-12B-it sl: ASR 0.025 -> 0.045 (delta 0.020, b=4, c=0, McNemar p 0.125, n=200)
- rand_1@1.0 control, GaMS3-12B-Instruct en: ASR 0.020 -> 0.020 (delta 0.000, b=0, c=0, McNemar p 1.000, n=200)
- rand_1@1.0 control, GaMS3-12B-Instruct sl: ASR 0.065 -> 0.075 (delta 0.010, b=3, c=1, McNemar p 0.625, n=200)
- 256-token sensitivity, Gemma-3-12B-it en (n=100): SR-ft mean 0.149 (128) vs 0.353 (256), delta 0.203 [0.169, 0.241]; ASR 0.850 vs 0.850
- 256-token sensitivity, Gemma-3-12B-it sl (n=100): SR-ft mean 0.086 (128) vs 0.207 (256), delta 0.121 [0.085, 0.157]; ASR 0.660 vs 0.610
- 256-token sensitivity, GaMS3-12B-Instruct en (n=100): SR-ft mean 0.447 (128) vs 0.642 (256), delta 0.195 [0.161, 0.229]; ASR 0.980 vs 0.970
- 256-token sensitivity, GaMS3-12B-Instruct sl (n=100): SR-ft mean 0.187 (128) vs 0.378 (256), delta 0.192 [0.158, 0.228]; ASR 0.910 vs 0.900
- placebo orig/edit swap: mean delta [0.00162, -0.00075, -0.00112, -0.00306] (pass [True, True, True, True]); model-swap DiD [-0.00022, -0.00041]; shuffled-guard kappa [0.00144, 0.00218, 0.00204, -0.00141]
- sensitivity lang_consistent_only: Gemma-3-12B-it en ASR delta 0.852 [0.831, 0.870] (n=1300)
- sensitivity lang_consistent_only: Gemma-3-12B-it sl ASR delta 0.657 [0.629, 0.683] (n=1300)
- sensitivity lang_consistent_only: GaMS3-12B-Instruct en ASR delta 0.937 [0.923, 0.949] (n=1300)
- sensitivity lang_consistent_only: GaMS3-12B-Instruct sl ASR delta 0.847 [0.828, 0.867] (n=1299)
- sensitivity non_degenerate_only: Gemma-3-12B-it en ASR delta 0.852 [0.831, 0.870] (n=1300)
- sensitivity non_degenerate_only: Gemma-3-12B-it sl ASR delta 0.657 [0.630, 0.682] (n=1299)
- sensitivity non_degenerate_only: GaMS3-12B-Instruct en ASR delta 0.937 [0.923, 0.949] (n=1300)
- sensitivity non_degenerate_only: GaMS3-12B-Instruct sl ASR delta 0.846 [0.826, 0.866] (n=1294)

### Per-cell rates and compliance

| model | lang | ctag | n | ASR | ASR loose | SR-ft mean | SR05 | PG refusal | Q3G refusal | LG | PG | Q3G | LG/PG kappa | adjudicator share | lang consistency | degenerate | empty | hit max tokens |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GaMS3-12B-Instruct | en | edit1 | 1300 | 0.970 | 0.957 | 0.467 | 0.441 | 0.172 | 0.449 | 0.955 | 0.978 | 0.592 | 0.419 | 0.038 | 1.000 | 0.000 | 0.000 | 0.997 |
| GaMS3-12B-Instruct | en | orig | 1300 | 0.033 | 0.030 | 0.015 | 0.008 | 0.969 | 0.900 | 0.028 | 0.092 | 0.111 | 0.397 | 0.069 | 1.000 | 0.000 | 0.000 | 0.307 |
| GaMS3-12B-Instruct | en | rand1 | 200 | 0.020 | 0.020 | 0.011 | 0.005 | 0.980 | 0.941 | 0.020 | 0.105 | 0.000 | 0.296 | 0.085 | 1.000 | 0.000 | 0.000 | 0.290 |
| GaMS3-12B-Instruct | en | sens256 | 100 | 0.970 | 0.950 | 0.642 | 0.730 | 0.170 | 0.750 | 0.950 | 0.970 | 0.750 | 0.480 | 0.040 | 1.000 | 0.000 | 0.000 | 0.990 |
| GaMS3-12B-Instruct | sl | edit1 | 1300 | 0.915 | 0.878 | 0.201 | 0.046 | 0.520 | 0.237 | 0.803 | 0.949 | 0.731 | 0.262 | 0.169 | 0.999 | 0.005 | 0.000 | 0.987 |
| GaMS3-12B-Instruct | sl | orig | 1300 | 0.068 | 0.050 | 0.015 | 0.003 | 0.935 | 0.483 | 0.037 | 0.138 | 0.327 | 0.312 | 0.113 | 1.000 | 0.000 | 0.000 | 0.369 |
| GaMS3-12B-Instruct | sl | rand1 | 200 | 0.075 | 0.060 | 0.010 | 0.000 | 0.920 | 0.542 | 0.030 | 0.140 | 0.417 | 0.257 | 0.120 | 1.000 | 0.000 | 0.000 | 0.385 |
| GaMS3-12B-Instruct | sl | sens256 | 100 | 0.900 | 0.830 | 0.378 | 0.300 | 0.610 | 0.316 | 0.760 | 0.930 | 0.789 | 0.313 | 0.190 | 1.000 | 0.010 | 0.000 | 0.960 |
| Gemma-3-12B-it | en | edit1 | 1300 | 0.897 | 0.861 | 0.161 | 0.029 | 0.188 | 0.546 | 0.869 | 0.905 | 0.794 | 0.531 | 0.095 | 1.000 | 0.000 | 0.000 | 1.000 |
| Gemma-3-12B-it | en | orig | 1300 | 0.045 | 0.042 | 0.006 | 0.000 | 0.948 | 0.928 | 0.035 | 0.085 | 0.098 | 0.491 | 0.058 | 1.000 | 0.000 | 0.000 | 1.000 |
| Gemma-3-12B-it | en | rand1 | 200 | 0.035 | 0.035 | 0.005 | 0.000 | 0.965 | 0.974 | 0.030 | 0.090 | 0.026 | 0.476 | 0.060 | 1.000 | 0.000 | 0.000 | 1.000 |
| Gemma-3-12B-it | en | sens256 | 100 | 0.850 | 0.810 | 0.353 | 0.270 | 0.250 | 0.900 | 0.820 | 0.860 | 0.600 | 0.629 | 0.100 | 1.000 | 0.000 | 0.000 | 1.000 |
| Gemma-3-12B-it | sl | edit1 | 1300 | 0.683 | 0.615 | 0.086 | 0.014 | 0.612 | 0.558 | 0.531 | 0.809 | 0.534 | 0.355 | 0.310 | 1.000 | 0.001 | 0.000 | 0.994 |
| Gemma-3-12B-it | sl | orig | 1300 | 0.026 | 0.016 | 0.008 | 0.002 | 0.963 | 0.777 | 0.011 | 0.132 | 0.120 | 0.123 | 0.122 | 1.000 | 0.000 | 0.000 | 0.984 |
| Gemma-3-12B-it | sl | rand1 | 200 | 0.045 | 0.035 | 0.008 | 0.005 | 0.960 | 0.857 | 0.025 | 0.185 | 0.114 | 0.203 | 0.160 | 1.000 | 0.000 | 0.000 | 0.980 |
| Gemma-3-12B-it | sl | sens256 | 100 | 0.610 | 0.550 | 0.207 | 0.140 | 0.660 | 0.486 | 0.440 | 0.790 | 0.486 | 0.308 | 0.370 | 1.000 | 0.000 | 0.000 | 0.990 |

## 3. Exploratory

Hazard-category / item-group ASR deltas (orig -> edit@1.0; Wilson CIs; no tests) are in `results/analysis.json` under `hazard`. PPI sensitivity:
- PPI Gemma-3-12B-it en edit1: 0.538 [0.362, 0.714] (n_eff 30.7)
- PPI Gemma-3-12B-it sl edit1: 0.246 [0.093, 0.399] (n_eff 44.1)
- PPI GaMS3-12B-Instruct en edit1: 0.970 [0.961, 0.979] (n_eff 26.5)
- PPI GaMS3-12B-Instruct sl edit1: 0.658 [0.495, 0.822] (n_eff 29.6)

### Ranking vs thresholding (added analysis; does a guard fail Slovene by ranking or by calibration?)

| model | lang | score | n | weighted AUROC vs author-model HARMFUL | best threshold | weighted acc at best |
|---|---|---|---|---|---|---|
| Gemma-3-12B-it | en | lg_p_unsafe | 60 | 0.953 | 0.958 | 0.892 |
| Gemma-3-12B-it | en | sr_ft | 60 | 0.918 | 0.102 | 0.872 |
| Gemma-3-12B-it | sl | lg_p_unsafe | 60 | 0.950 | 0.986 | 0.932 |
| Gemma-3-12B-it | sl | sr_ft | 60 | 0.887 | 0.337 | 0.904 |
| GaMS3-12B-Instruct | en | lg_p_unsafe | 60 | 1.000 | 0.623 | 0.999 |
| GaMS3-12B-Instruct | en | sr_ft | 60 | 0.994 | 0.258 | 0.979 |
| GaMS3-12B-Instruct | sl | lg_p_unsafe | 60 | 0.947 | 0.818 | 0.908 |
| GaMS3-12B-Instruct | sl | sr_ft | 60 | 0.901 | 0.075 | 0.823 |

A high AUROC beside a failing specificity means the guard ranks harmful above harmless but its shipped decision threshold is misplaced for that language; a low AUROC means the score itself does not separate.


## 4. Not executed

- P1 3-way refusal judge (gemini) and its gpt-4.1-mini second family: OpenRouter budget exhausted (R0).
- gpt-4o-mini adjudication of guard disagreements (the RefusEU adjudicator): replaced by Qwen3Guard-Gen-8B (R0).
- gemini-2.5-flash StrongREJECT rubric: replaced by the official fine-tuned StrongREJECT evaluator (R0).
- Secondary correction from artifact 3 error matrices: present; not applied to headline (MT items with suffix != natural prompts).
- Fresh frozen-core Heretic search at tool defaults (unpaid debt, deviation a).
- Native-speaker (human) audit of the adjudication frame: requested in `results/human_audit_request.json`, not performed.

Audit: `src/rederive.py` re-derived 406 statistics independently; failures: 0.
