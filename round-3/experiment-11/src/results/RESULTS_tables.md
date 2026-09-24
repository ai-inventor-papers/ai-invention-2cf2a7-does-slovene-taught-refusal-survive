# Auto-generated result tables (src/make_report.py from results/analysis.json)

Protocol sha256: `c1b0a2b9e55898467a95ef668fe6afcaccdc6c1665a8e87611160a2353a226e5`; rows: 27264. Primary judge Q = Qwen3-14B (local, NF4); second family M = Mistral-Small-24B (local, NF4, pre-registered sample). R = REFUSE; RP = REFUSE or PARTIAL. No human adjudication; the adjudicator is the executor LLM.

## Judge gate: qwen3_14b vs archived gemini labels

| cell | n | kappa R | kappa 3-way | agree R | rate gold R | rate judge R |
|---|---|---|---|---|---|---|
| ALL | 586 | 0.55 | 0.31 | 0.77 | 0.47 | 0.68 |
| ALL_edited | 245 | 0.39 | 0.19 | 0.69 | 0.48 | 0.74 |
| gams3_it|en|orig | 147 | 0.51 | 0.29 | 0.74 | 0.34 | 0.60 |
| gams3_it|sl|orig | 134 | 0.69 | 0.40 | 0.84 | 0.37 | 0.53 |
| gemma_it|en|edited | 140 | 0.27 | 0.10 | 0.59 | 0.32 | 0.69 |
| gemma_it|en|orig | 40 | 1.00 | 0.49 | 1.00 | 0.97 | 0.97 |
| gemma_it|sl|edited | 105 | 0.56 | 0.36 | 0.83 | 0.69 | 0.80 |
| gemma_it|sl|orig | 20 | nan | nan | 1.00 | 1.00 | 1.00 |

## Judge gate: mistral24b vs archived gemini labels

| cell | n | kappa R | kappa 3-way | agree R | rate gold R | rate judge R |
|---|---|---|---|---|---|---|
| ALL | 586 | 0.42 | 0.38 | 0.70 | 0.47 | 0.72 |
| ALL_edited | 245 | 0.26 | 0.27 | 0.62 | 0.48 | 0.79 |
| gams3_it|en|orig | 147 | 0.37 | 0.32 | 0.65 | 0.34 | 0.66 |
| gams3_it|sl|orig | 134 | 0.58 | 0.49 | 0.78 | 0.37 | 0.56 |
| gemma_it|en|edited | 140 | 0.16 | 0.20 | 0.51 | 0.32 | 0.74 |
| gemma_it|en|orig | 40 | 1.00 | 0.49 | 1.00 | 0.97 | 0.97 |
| gemma_it|sl|edited | 105 | 0.38 | 0.35 | 0.77 | 0.69 | 0.86 |
| gemma_it|sl|orig | 20 | nan | nan | 1.00 | 1.00 | 1.00 |

## Judge retest: qwen3_14b vs archived exp5 Qwen3 (160 tok) labels

| cell | n | kappa R | kappa 3-way | agree R | rate gold R | rate judge R |
|---|---|---|---|---|---|---|
| ALL | 300 | 0.89 | 0.82 | 0.95 | 0.72 | 0.71 |
| gams3_it|en|orig | 65 | 0.82 | 0.73 | 0.92 | 0.71 | 0.69 |
| gams3_it|sl|orig | 85 | 0.85 | 0.73 | 0.93 | 0.65 | 0.62 |
| gemma_it|en|orig | 78 | 0.97 | 0.94 | 0.99 | 0.70 | 0.72 |
| gemma_it|sl|orig | 72 | 0.90 | 0.90 | 0.97 | 0.83 | 0.83 |

## C-LAG FINAL: G3 = a_GaMS - a_Gemma (SL-MT log-odds at EN-BT refusal = 50%)

| readout | G3 | 95% CI | 90% CI | BCa 95% | SE | MDE | a_Gemma | a_GaMS | support Gemma | support GaMS | perm p |
|---|---|---|---|---|---|---|---|---|---|---|---|
| q_R | -0.60 | [-1.31, 0.40] | [-1.20, 0.27] | [-1.32, 0.40] | 0.44 | 1.44 | -0.10 | -0.70 | [0, 4] | [0, 5] | 0.0918 |
| q_RP | 8.74 | [-1.51, 14.05] | [-0.55, 12.97] | [2.25, 17.90] | 4.31 | 13.98 | -7.89 | 0.86 | [0, 0] | [0, 0] | 0.0399 |
| q_R_incl_orig | -0.68 | [-1.37, 0.37] | [-1.31, 0.17] | [-1.43, 0.25] | 0.45 | 1.45 | 0.05 | -0.63 | [0, 4] | [0, 5] | – |
| q_R_excl_chrf50 | -0.58 | [-1.30, 0.37] | [-1.22, 0.16] | [-1.25, 0.57] | 0.45 | 1.45 | -0.14 | -0.71 | [0, 4] | [0, 4] | – |

Verdict (pre-registered mapping): {'R': 'ESTIMATE (support rule failed)', 'RP': 'ESTIMATE (support rule failed)'}

### Per-step Hautus rates (Q, R) on the CURVE items

| model | λ=0.1 | λ=0.2 | λ=0.3 | λ=0.4 | λ=0.5 | λ=0.6 | λ=0.8 | λ=1 |
|---|---|---|---|---|---|---|---|---|
| Gemma-3-12B-IT EN-BT | 0.94 | 0.92 | 0.87 | 0.83 | 0.79 | 0.75 | 0.68 | 0.64 |
| Gemma-3-12B-IT SL-MT | 0.98 | 0.98 | 0.97 | 0.95 | 0.94 | 0.90 | 0.81 | 0.68 |
| GaMS3-12B-Instruct EN-BT | 0.96 | 0.89 | 0.83 | 0.80 | 0.73 | 0.69 | 0.66 | 0.60 |
| GaMS3-12B-Instruct SL-MT | 0.97 | 0.89 | 0.87 | 0.75 | 0.66 | 0.63 | 0.53 | 0.47 |

| model | a | b | SL−EN pp at EN 50% | isotonic SL log-odds at EN 50% | EN range |
|---|---|---|---|---|---|
| Gemma-3-12B-IT | -0.10 | 1.89 | -2.5 | 0.75 | [0.64, 0.94] |
| GaMS3-12B-Instruct | -0.70 | 1.40 | -16.8 | -0.14 | [0.60, 0.96] |

## RQ2: orig → λ=1 (exact McNemar; Q, R)

| model | set | harmful | arm | n | rate orig | rate λ=1 | Δ pp | b (0→1) | c (1→0) | p | relative cut |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Gemma-3-12B-IT | refuseu_x | True | EN_BT | 200 | 0.980 | 0.645 | -33.5 | 0 | 67 | 0.0000 | 0.34 |
| Gemma-3-12B-IT | refuseu_x | True | SL_MT | 200 | 0.990 | 0.680 | -31.0 | 0 | 62 | 0.0000 | 0.31 |
| Gemma-3-12B-IT | refuseu_x | True | L3_MT | 247 | 0.984 | 0.696 | -28.7 | 0 | 71 | 0.0000 | 0.29 |
| Gemma-3-12B-IT | hard | True | SL_MT | 11 | 0.909 | 0.182 | -72.7 | 0 | 8 | 0.0078 | 0.80 |
| Gemma-3-12B-IT | hard | True | L3_MT | 100 | 0.910 | 0.430 | -48.0 | 2 | 50 | 0.0000 | 0.53 |
| Gemma-3-12B-IT | hard | False | EN_BT | 56 | 0.429 | 0.125 | -30.4 | 3 | 20 | 0.0005 | 0.71 |
| Gemma-3-12B-IT | hard | False | SL_MT | 54 | 0.537 | 0.074 | -46.3 | 2 | 27 | 0.0000 | 0.86 |
| Gemma-3-12B-IT | hard | False | L3_MT | 100 | 0.450 | 0.060 | -39.0 | 2 | 41 | 0.0000 | 0.87 |
| GaMS3-12B-Instruct | refuseu_x | True | EN_BT | 1101 | 0.974 | 0.583 | -39.1 | 2 | 432 | 0.0000 | 0.40 |
| GaMS3-12B-Instruct | refuseu_x | True | SL_MT | 652 | 0.971 | 0.459 | -51.2 | 2 | 336 | 0.0000 | 0.53 |
| GaMS3-12B-Instruct | refuseu_x | True | L3_MT | 250 | 0.980 | 0.604 | -37.6 | 2 | 96 | 0.0000 | 0.38 |
| GaMS3-12B-Instruct | hard | True | EN_BT | 12 | 1.000 | 0.250 | -75.0 | 0 | 9 | 0.0039 | 0.75 |
| GaMS3-12B-Instruct | hard | True | L3_MT | 60 | 0.883 | 0.317 | -56.7 | 0 | 34 | 0.0000 | 0.64 |
| GaMS3-12B-Instruct | hard | False | EN_BT | 56 | 0.286 | 0.107 | -17.9 | 3 | 13 | 0.0213 | 0.62 |
| GaMS3-12B-Instruct | hard | False | SL_MT | 54 | 0.278 | 0.056 | -22.2 | 1 | 13 | 0.0018 | 0.80 |
| GaMS3-12B-Instruct | hard | False | L3_MT | 60 | 0.350 | 0.033 | -31.7 | 1 | 20 | 0.0000 | 0.90 |

## C-MECH: SDT along the curve (Q, R): mean over steps with EN-BT H in [0.3, 0.7]

| model | mean Δc | 95% CI | mean Δd′ | 95% CI | signature |
|---|---|---|---|---|---|
| Gemma-3-12B-IT | 0.08 | [-0.21, 0.36] | -0.37 | [-0.89, 0.17] | M-a (sensitivity) |
| GaMS3-12B-Instruct | -0.30 | [-0.62, -0.03] | -0.04 | [-0.74, 0.52] | control-like (both < 0.3) |

### HARD SDT at orig and λ=1 (all 349 unsafe vs HARDSAFE subset; Q, R)

| condition | model | arm | H | FA | d′ | c |
|---|---|---|---|---|---|---|
| orig | Gemma-3-12B-IT | EN_BT | 0.89 | 0.36 | 1.57 | -0.44 |
| orig | Gemma-3-12B-IT | SL_MT | 0.94 | 0.57 | 1.39 | -0.87 |
| orig | Gemma-3-12B-IT | L3_MT | 0.91 | 0.45 | 1.44 | -0.60 |
| orig | GaMS3-12B-Instruct | EN_BT | 0.90 | 0.27 | 1.86 | -0.33 |
| orig | GaMS3-12B-Instruct | SL_MT | 0.86 | 0.27 | 1.68 | -0.23 |
| orig | GaMS3-12B-Instruct | L3_MT | 0.88 | 0.35 | 1.54 | -0.39 |
| orig | DiD_c (GaMS − Gemma of c_EN − c_SL) | | | | | -0.52 [-0.68, -0.37] |
| edit | Gemma-3-12B-IT | EN_BT | 0.44 | 0.12 | 0.99 | 0.62 |
| edit | Gemma-3-12B-IT | SL_MT | 0.18 | 0.07 | 0.58 | 1.10 |
| edit | Gemma-3-12B-IT | L3_MT | 0.43 | 0.06 | 1.34 | 0.85 |
| edit | GaMS3-12B-Instruct | EN_BT | 0.25 | 0.11 | 0.59 | 0.91 |
| edit | GaMS3-12B-Instruct | SL_MT | 0.12 | 0.06 | 0.56 | 1.25 |
| edit | GaMS3-12B-Instruct | L3_MT | 0.32 | 0.03 | 1.27 | 1.10 |
| edit | DiD_c (GaMS − Gemma of c_EN − c_SL) | | | | | 0.14 [-0.78, 1.12] |

## C-MOD (reduced two-point; F2-iii): language lag = logit(p_L) − logit(p_EN-BT) on L3 items

| readout | language | n items | Gemma lag orig | Gemma lag λ1 | GaMS lag orig | GaMS lag λ1 | G3_2pt | 95% CI | MDE |
|---|---|---|---|---|---|---|---|---|---|
| q_R | L3 | 122 | 0.52 | 0.48 | 0.26 | -0.23 | -0.46 | [-2.21, 1.44] | 2.96 |
| q_R | SL_on_L3_items | 200 | 0.60 | 0.16 | -0.15 | -0.54 | 0.05 | [-1.49, 2.02] | 2.92 |
| q_RP | L3 | 122 | 0.00 | 0.00 | 0.00 | -0.26 | -0.26 | [-2.44, 1.89] | 3.65 |
| q_RP | SL_on_L3_items | 200 | 0.00 | -1.11 | 0.00 | -0.20 | 0.91 | [-0.86, 2.82] | 3.04 |

Verdict C-MOD: ESTIMATE (reduced two-point version, F2-iii)

## C-EXT: public checkpoints (PUB items; Q, R)

| model | n | EN-BT | SL-MT | L3-MT | SL−EN pp [95% CI] | L3−EN pp [95% CI] | HARD Δc(SL) | Δd′(SL) | c-share |
|---|---|---|---|---|---|---|---|---|---|
| Gemma-3-12B-IT (orig reference) | 400 | 0.97 | 0.99 | 0.99 | 1.2 [-0.2, 3.0] | 1.5 [0.0, 3.2] | 0.32 | 0.34 | 0.65 |

Prediction SL−EN > 5 pp in ≥ 2 checkpoints: {'n_checkpoints': 0, 'n_meeting': 0, 'met': None}

## Judge agreement Q vs M (binary R)

| cell | n | κ R | κ 3-way | rate Q | rate M | ≥0.6 |
|---|---|---|---|---|---|---|

## Blind adjudication (executor LLM, NOT human) vs judges

```
{
 "gams3_it|en": {
  "n": 36,
  "q": {
   "n": 36,
   "kappa_R_vs_adj": 0.333,
   "kappa_3way_vs_adj": 0.129,
   "Se": 1.0,
   "Sp": 0.333,
   "identifiable": false,
   "rate_adj": 0.5,
   "rate_judge": 0.833
  }
 },
 "gams3_it|sl": {
  "n": 36,
  "q": {
   "n": 36,
   "kappa_R_vs_adj": 0.618,
   "kappa_3way_vs_adj": 0.319,
   "Se": 1.0,
   "Sp": 0.708,
   "identifiable": true,
   "rate_adj": 0.333,
   "rate_judge": 0.528
  }
 },
 "gemma_it|en": {
  "n": 36,
  "q": {
   "n": 31,
   "kappa_R_vs_adj": 0.23,
   "kappa_3way_vs_adj": 0.203,
   "Se": 0.833,
   "Sp": 0.385,
   "identifiable": false,
   "rate_adj": 0.581,
   "rate_judge": 0.742
  }
 },
 "gemma_it|hu": {
  "n": 18,
  "q": {
   "n": 18,
   "kappa_R_vs_adj": 0.0,
   "kappa_3way_vs_adj": -0.085,
   "Se": 0.0,
   "Sp": 0.778,
   "identifiable": false,
   "rate_adj": 0.0,
   "rate_judge": 0.222
  }
 },
 "gemma_it|sl": {
  "n": 36,
  "q": {
   "n": 31,
   "kappa_R_vs_adj": 0.289,
   "kappa_3way_vs_adj": 0.192,
   "Se": 1.0,
   "Sp": 0.222,
   "identifiable": false,
   "rate_adj": 0.71,
   "rate_judge": 0.935
  }
 }
}
```

## Competence covariates (DESCRIPTIVE)

```
{
 "catastrophic_gate": {
  "gemma_it|en": {
   "acc_orig": 0.93,
   "acc_edit": 0.93,
   "headroom_change": 0.0,
   "catastrophic": false,
   "nll_orig": 0.58574,
   "nll_edit": 0.58548
  },
  "gemma_it|sl": {
   "acc_orig": 0.885,
   "acc_edit": 0.885,
   "headroom_change": 0.0,
   "catastrophic": false,
   "nll_orig": 0.79773,
   "nll_edit": 0.79831
  },
  "gemma_it|hu": {
   "acc_orig": 0.88,
   "acc_edit": 0.88,
   "headroom_change": 0.0,
   "catastrophic": false,
   "nll_orig": 0.75212,
   "nll_edit": 0.75188
  },
  "gams3_it|en": {
   "acc_orig": 0.905,
   "acc_edit": 0.91,
   "headroom_change": 0.0076,
   "catastrophic": false,
   "nll_orig": 0.51152,
   "nll_edit": 0.51182
  },
  "gams3_it|sl": {
   "acc_orig": 0.875,
   "acc_edit": 0.87,
   "headroom_change": -0.008,
   "catastrophic": false,
   "nll_orig": 0.59724,
   "nll_edit": 0.59806
  },
  "gams3_it|hu": {
   "acc_orig": 0.87,
   "acc_edit": 0.825,
   "headroom_change": -0.0726,
   "catastrophic": false,
   "nll_orig": 0.60607,
   "nll_edit": 0.60646
  }
 },
 "scatter_cells": [
  {
   "model": "gemma_it",
   "lang": "sl",
   "belebele_acc": 0.885,
   "nll_per_byte": 0.79773,
   "lag_lam1": 0.15567595938365697
  },
  {
   "model": "gemma_it",
   "lang": "hu",
   "belebele_acc": 0.88,
   "nll_per_byte": 0.75212,
   "lag_lam1": 0.48485475821060964
  },
  {
   "model": "gams3_it",
   "lang": "sl",
   "belebele_acc": 0.875,
   "nll_per_byte": 0.59724,
   "lag_lam1": -0.5429219797792681
  },
  {
   "model": "gams3_it",
   "lang": "hu",
   "belebele_acc": 0.87,
   "nll_per_byte": 0.60607,
   "lag_lam1": -0.2347699016154022
  }
 ],
 "spearman_acc_vs_lag_DESCRIPTIVE": 0.6000000000000001
}
```

## MT-noise (EN-BT vs EN-orig at λ=1) and mixed models

```
{
 "mt_noise_lam1": {
  "gemma_it": {
   "note": "EN_orig at lambda=1 not generated (job J6 not reached)"
  },
  "gams3_it": {
   "note": "EN_orig at lambda=1 not generated (job J6 not reached)"
  }
 },
 "mixed": {
  "n": 7337,
  "gee": {
   "Intercept": {
    "coef": 3.6447375608840082,
    "se": 0.17633716551098289,
    "p": 6.567605904155034e-95
   },
   "gams": {
    "coef": -0.08938949939460039,
    "se": 0.19083805381787775,
    "p": 0.6394949901248652
   },
   "sl": {
    "coef": 1.57097429299985,
    "se": 0.3749532898152733,
    "p": 2.7921684088147304e-05
   },
   "gams:sl": {
    "coef": -1.729898251579763,
    "se": 0.41689858026543974,
    "p": 3.3328052791501026e-05
   },
   "edit": {
    "coef": -3.0479975951986837,
    "se": 0.22053453303297652,
    "p": 1.9052845841405895e-43
   },
   "gams:edit": {
    "coef": -0.17562054017440798,
    "se": 0.2411676854628953,
    "p": 0.4664855022775021
   },
   "sl:edit": {
    "coef": -1.41434514778968,
    "se": 0.4193100533837492,
    "p": 0.0007434600741108505
   },
   "gams:sl:edit": {
    "coef": 1.0573492157289484,
    "se": 0.46318467100889665,
    "p": 0.022443265428905228
   }
  },
  "bayes_items": 400,
  "bayes_mixed_vb": {
   "Intercept": {
    "post_mean": 5.233758210960802,
    "post_sd": 0.0820440955225668
   },
   "gams": {
    "post_mean": -0.027269780877558953,
    "post_sd": 0.09041177196706972
   },
   "sl": {
    "post_mean": 1.3997705474551214,
    "post_sd": 0.12970015907648558
   },
   "gams:sl": {
    "post_mean": -1.8306166737408196,
    "post_sd": 0.14364512743447766
   },
   "edit": {
    "post_mean": -4.037746769856978,
    "post_sd": 0.08953090957244347
   },
   "gams:edit": {
    "post_mean": -0.7487873227973431,
    "post_sd": 0.09676777396662599
   },
   "sl:edit": {
    "post_mean": -1.4616540220359433,
    "post_sd": 0.1436892951392227
   },
   "gams:sl:edit": {
    "post_mean": 1.0434618543987069,
    "post_sd": 0.1593240733308186
   },
   "note": "vc {item, item:language} approximates (1+language|item); variational Bayes posterior means/SDs; fitted on <= 400 seeded items that have both orig and lambda=1 rows (runtime cap; the GEE path uses all items)"
  }
 }
}
```

## Audit (src/rederive.py): 25/25 checks pass; all_pass = True

```
{
 "model_swap_G3_mean": -0.013520131964158555,
 "model_swap_G3_sd": 0.3622611497100796,
 "model_swap_pass": true,
 "lang_swap_mean_logodds_gap": {
  "gemma_it": 0.032989928031667545,
  "gams3_it": 0.013988527841882321
 },
 "lang_swap_sd": {
  "gemma_it": 0.0998190579286888,
  "gams3_it": 0.07189741057897668
 },
 "lang_swap_pass": true
}
```
