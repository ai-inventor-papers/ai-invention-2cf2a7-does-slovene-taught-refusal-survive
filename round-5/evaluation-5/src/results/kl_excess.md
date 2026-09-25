# Step 2 - C5a excess first-token KL ratio (SL/EN, edit vs norm-matched random)

Estimator: excess = [KL_E(SL)/KL_E(EN)] / [mean_s KL_R_s(SL) / mean_s KL_R_s(EN)]

_POST-HOC sensitivity analysis on already-seen data_

## 2a exp15 points (saved means only)

| model | lambda | E ratio SL/EN | pooled random ratio | excess (pooled) | per-seed excess | excess on medians |
|---|---|---|---|---|---|---|
| gemma_it | 0.7695 | 2.191 | 1.681 | 1.303 | rand_1: 1.421, rand_2: 1.170 | 0.526 |
| gemma_it | 1.1551 | 1.878 | 2.923 | 0.642 | rand_1: 0.643, rand_2: 0.641 | 1.111 |
| gemma_it | 1.5603 | 1.884 | 2.592 | 0.727 | rand_1: 0.532, rand_2: 0.986 | 0.654 |
| gemma_it | 2.0 | 1.934 | 2.016 | 0.959 | rand_1: 0.812, rand_2: 1.106 | 0.464 |
| gemma_it | range | | | [0.532, 1.421] | sensitivity range, NOT a sampling interval: exp15 src/gen.py phase_kl stores only kl_mean, kl_median and n per (model, edit, lambda, language); per-item KL was not saved | |
| gams3_it | 0.3013 | 0.616 | 1.381 | 0.446 | rand_1: 0.428, rand_2: 0.462 | 0.337 |
| gams3_it | 0.6313 | 0.672 | 1.256 | 0.535 | rand_1: 0.650, rand_2: 0.443 | 0.293 |
| gams3_it | 0.978 | 0.683 | 1.002 | 0.682 | rand_1: 0.783, rand_2: 0.581 | 0.409 |
| gams3_it | 1.5375 | 0.731 | 0.918 | 0.796 | rand_1: 0.631, rand_2: 0.952 | 0.471 |
| gams3_it | range | | | [0.428, 0.952] | sensitivity range, NOT a sampling interval: exp15 src/gen.py phase_kl stores only kl_mean, kl_median and n per (model, edit, lambda, language); per-item KL was not saved | |

Raw KL for the real edit at Gemma's top dose: SL 0.735 vs EN 0.380.

## 2b Item bootstrap on bodies that saved per-item KL

| body | model | statistic | point | 95% CI (pct) | 95% CI (BCa) | leave-one-item-out range | verdict |
|---|---|---|---|---|---|---|---|
| exp9 | gemma_it | mean | 0.324 | [0.175, 0.583] | [0.177, 0.606] | [0.284, 0.356] | NO-LEAKAGE |
| exp9 | gemma_it | trim10 | 0.198 | [0.075, 0.456] | [0.072, 0.438] | [0.158, 0.214] |  |
| exp9 | gemma_it | median | 0.041 | [0.009, 0.194] | [0.006, 0.132] | [0.036, 0.050] |  |
| exp9 | gemma_it | mean_items_and_seeds | 0.324 | [0.151, 0.615] | [0.156, 0.641] | [0.284, 0.356] |  |
| exp9 | gemma_it | language-shuffle placebo | median 0.996 | log sd 0.397 | | | centred=True |
| exp9 | gams3_it | mean | 0.618 | [0.450, 0.830] | [0.451, 0.832] | [0.583, 0.658] | NO-LEAKAGE |
| exp9 | gams3_it | trim10 | 0.483 | [0.368, 0.638] | [0.360, 0.623] | [0.469, 0.506] |  |
| exp9 | gams3_it | median | 0.359 | [0.245, 0.537] | [0.235, 0.510] | [0.346, 0.374] |  |
| exp9 | gams3_it | mean_items_and_seeds | 0.618 | [0.424, 0.870] | [0.420, 0.859] | [0.583, 0.658] |  |
| exp9 | gams3_it | language-shuffle placebo | median 0.997 | log sd 0.154 | | | centred=True |
| exp14 | gemma_it | mean | 0.767 | [0.156, 2.035] | [0.189, 2.269] | [0.437, 0.969] | UNDETERMINED |
| exp14 | gemma_it | trim10 | 0.603 | [0.045, 3.547] | [0.030, 3.130] | [0.358, 1.193] |  |
| exp14 | gemma_it | median | NA | [0.063, 6.690] | [NA, NA] | [NA, NA] |  |
| exp14 | gemma_it | language-shuffle placebo | median 0.983 | log sd 0.555 | | | centred=True |
| exp14 | gams3_it | mean | 0.566 | [0.303, 0.947] | [0.327, 0.999] | [0.487, 0.648] | NO-LEAKAGE |
| exp14 | gams3_it | trim10 | 0.406 | [0.235, 0.858] | [0.217, 0.720] | [0.357, 0.450] |  |
| exp14 | gams3_it | median | 0.427 | [0.182, 1.705] | [0.152, 1.259] | [0.365, 0.502] |  |
| exp14 | gams3_it | language-shuffle placebo | median 1.002 | log sd 0.302 | | | centred=True |

## 2c GPU recompute

preconditions met; recompute ran (see gpu_recompute_gate)

Reproduction gate: PASSED.

| model | lambda | recomputed excess | item-bootstrap 95% CI (pct) | BCa 95% | trimmed-10% excess |
|---|---|---|---|---|---|
| gemma_it | 0.7695 | 1.303 | [0.455, 5.019] | [0.466, 5.397] | 2.195 |
| gemma_it | 1.1551 | 0.642 | [0.280, 2.152] | [0.237, 1.658] | 1.278 |
| gemma_it | 1.5603 | 0.727 | [0.294, 2.480] | [0.226, 1.783] | 1.710 |
| gemma_it | 2.0 | 0.959 | [0.414, 2.886] | [0.286, 2.198] | 1.821 |

gemma_it: top-dose gate {"en": 0.0, "sl": 0.0}; verdict UNDETERMINED

| gams3_it | 0.3013 | 0.446 | [0.281, 0.694] | [0.280, 0.687] | 0.398 |
| gams3_it | 0.6313 | 0.535 | [0.344, 0.881] | [0.364, 0.968] | 0.483 |
| gams3_it | 0.978 | 0.682 | [0.449, 1.038] | [0.475, 1.112] | 0.554 |
| gams3_it | 1.5375 | 0.796 | [0.506, 1.278] | [0.545, 1.395] | 0.629 |

gams3_it: top-dose gate {"en": 0.0, "sl": 0.0}; verdict UNDETERMINED

## 2d Reconciliation across bodies

| body | model | point | 95% CI | CI type | prompt set | horizon | lambda | verdict |
|---|---|---|---|---|---|---|---|---|
| exp4 (iter 1) | gemma_it | 0.298 | [0.154, 0.562] | saved (item bootstrap) | exp4 KL stems | first token | 1.0 | NO-LEAKAGE |
| exp4 (iter 1) | gams3_it | 0.574 | [0.409, 0.796] | saved (item bootstrap) | exp4 KL stems | first token | 1.0 | NO-LEAKAGE |
| exp9 (iter 3) | gemma_it | 0.324 | [0.175, 0.583] | item bootstrap (this artifact) | exp8 eval_kl stems (100 items) | first token | 1.0 | NO-LEAKAGE |
| exp9 (iter 3) | gams3_it | 0.618 | [0.450, 0.830] | item bootstrap (this artifact) | exp8 eval_kl stems (100 items) | first token | 1.0 | NO-LEAKAGE |
| exp12 (iter 3, first-token) | gemma_it | 0.628 | [0.337, 1.169] | saved (item bootstrap) | exp12 200 items (EN-BT vs SL-MT) | first token | 1.0 | UNDETERMINED |
| exp12 (iter 3, multi-token) | gemma_it | 0.294 | [0.237, 0.366] | saved (item bootstrap) | exp12 200 items (EN-BT vs SL-MT) | 32-token (multi) | 1.0 | NO-LEAKAGE |
| exp12 (iter 3, first-token) | gams3_it | 0.466 | [0.379, 0.597] | saved (item bootstrap) | exp12 200 items (EN-BT vs SL-MT) | first token | 1.0 | NO-LEAKAGE |
| exp12 (iter 3, multi-token) | gams3_it | 0.566 | [0.494, 0.658] | saved (item bootstrap) | exp12 200 items (EN-BT vs SL-MT) | 32-token (multi) | 1.0 | NO-LEAKAGE |
| exp14 (iter 4) | gemma_it | 0.767 | [0.156, 2.035] | stem bootstrap (this artifact) | exp14 32 KL stems | first token | 1.0 | UNDETERMINED |
| exp14 (iter 4) | gams3_it | 0.566 | [0.303, 0.947] | stem bootstrap (this artifact) | exp14 32 KL stems | first token | 0.625 | NO-LEAKAGE |
| exp15 (iter 4) | gemma_it | 0.959 | [0.414, 2.886] | item bootstrap on the gated GPU re-measurement of the same 4 | exp9 data/gate_harmless40.jsonl (EN-BT vs SL-MT) | first token | 2.0 | UNDETERMINED |
| exp15 (iter 4) | gams3_it | 0.796 | [0.506, 1.278] | item bootstrap on the gated GPU re-measurement of the same 4 | exp9 data/gate_harmless40.jsonl (EN-BT vs SL-MT) | first token | 1.5375 | UNDETERMINED |

**'No Slovene-specific leakage' is supported only in the bodies whose excess-ratio CI lies below 1 (8 of 12 rows with a CI); UNDETERMINED in exp12 (iter 3, first-token) gemma_it, exp14 (iter 4) gemma_it, exp15 (iter 4) gemma_it, exp15 (iter 4) gams3_it.**
