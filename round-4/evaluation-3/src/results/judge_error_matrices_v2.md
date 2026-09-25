# Judge error matrices v2 — AUTHOR-MODEL ADJUDICATION, NOT HUMAN

HT-weighted Se/Sp vs a blind 4-class adjudication under `prompts/adjudication_rubric_v2.md` (OFF_TASK -> REFUSE); Wilson 95% CI on Kish effective n. Adjudicators: anthropic/claude-sonnet-4.5 (285 rows) and the executing Claude Opus 5 agent (195 rows the platform key limit blocked, AM2); 40-row overlap, inter-adjudicator kappa_R 0.69. NOT HUMAN.

## gams3_it|en|edited (n_adj=60, prevalence R=0.25, OFF_TASK share=0.00)

| instrument | n | Se [CI] | Sp [CI] | kappa vs adj |
|---|---|---|---|---|
| primary_gemini|R | 60 | 0.92 [0.59, 0.99] | 0.81 [0.62, 0.92] | 0.49 |
| primary_gemini|RP | 60 | 0.89 [0.64, 0.98] | 0.65 [0.43, 0.82] | 0.54 |
| second_gpt41mini|R | 16 | 1.00 [0.38, 1.00] | 0.26 [0.08, 0.58] | 0.10 |
| second_gpt41mini|RP | 16 | 1.00 [0.56, 1.00] | 0.00 [0.00, 0.36] | 0.00 |
| ttj_J1_english|R | 41 | 0.85 [0.45, 0.98] | 0.72 [0.50, 0.87] | 0.45 |
| ttj_J1_english|RP | 41 | 0.85 [0.56, 0.96] | 0.61 [0.36, 0.81] | 0.56 |
| direct_J1_same_instrument|R | 22 | 0.97 [0.54, 1.00] | 0.47 [0.21, 0.74] | 0.24 |
| direct_J1_same_instrument|RP | 22 | 0.84 [0.52, 0.96] | 0.57 [0.22, 0.87] | 0.31 |
| arch_j1_mdeberta|R | 19 | 0.82 [0.38, 0.97] | 0.92 [0.58, 0.99] | 0.52 |
| arch_j1_mdeberta|RP | 19 | 0.43 [0.14, 0.79] | 1.00 [0.59, 1.00] | 0.60 |
| arch_j2_llama8b_exp9|R | 12 | 0.74 [0.32, 0.94] | 0.62 [0.23, 0.90] | 0.21 |
| arch_j2_llama8b_exp9|RP | 12 | 0.66 [0.33, 0.88] | 0.67 [0.21, 0.94] | 0.40 |
| arch_qwen3_14b|R | 41 | 1.00 [0.65, 1.00] | 0.27 [0.12, 0.51] | 0.21 |
| arch_qwen3_14b|RP | 29 | 1.00 [0.64, 1.00] | 0.09 [0.02, 0.34] | 0.09 |
| arch_llama8b_exp8|R | 10 | 0.67 [0.21, 0.94] | 0.61 [0.22, 0.90] | 0.35 |
| arch_llama8b_exp8|RP | 10 | 0.20 [0.02, 0.73] | 0.35 [0.06, 0.81] | 0.00 |
| lexicon|R | 60 | 0.66 [0.35, 0.88] | 0.60 [0.41, 0.77] | 0.38 |
| lexicon|RP | 60 | 0.72 [0.46, 0.89] | 0.76 [0.54, 0.89] | 0.60 |

## gams3_it|en|orig (n_adj=15, prevalence R=0.93, OFF_TASK share=0.00)

| instrument | n | Se [CI] | Sp [CI] | kappa vs adj |
|---|---|---|---|---|
| primary_gemini|R | 15 | 1.00 [0.78, 1.00] | 0.00 [0.00, 0.79] | 0.00 |
| primary_gemini|RP | 15 | 1.00 [0.80, 1.00] | n/a | nan |
| second_gpt41mini|R | 7 | 1.00 [0.65, 1.00] | n/a | nan |
| second_gpt41mini|RP | 7 | 1.00 [0.65, 1.00] | n/a | nan |
| ttj_J1_english|R | 15 | 1.00 [0.78, 1.00] | 0.00 [0.00, 0.79] | 0.00 |
| ttj_J1_english|RP | 15 | 1.00 [0.80, 1.00] | n/a | nan |
| direct_J1_same_instrument|R | 15 | 1.00 [0.78, 1.00] | 0.00 [0.00, 0.79] | 0.00 |
| direct_J1_same_instrument|RP | 15 | 1.00 [0.80, 1.00] | n/a | nan |
| arch_j1_mdeberta|R | 5 | 1.00 [0.51, 1.00] | 0.00 [0.00, 0.79] | 0.00 |
| arch_j1_mdeberta|RP | 5 | 1.00 [0.57, 1.00] | n/a | nan |
| arch_qwen3_14b|R | 10 | 1.00 [0.72, 1.00] | n/a | nan |
| arch_qwen3_14b|RP | 10 | 1.00 [0.72, 1.00] | n/a | nan |
| lexicon|R | 15 | 1.00 [0.78, 1.00] | 0.00 [0.00, 0.79] | 0.00 |
| lexicon|RP | 15 | 1.00 [0.80, 1.00] | n/a | nan |

## gams3_it|sl|edited (n_adj=150, prevalence R=0.36, OFF_TASK share=0.04)

| instrument | n | Se [CI] | Sp [CI] | kappa vs adj |
|---|---|---|---|---|
| primary_gemini|R | 150 | 0.91 [0.74, 0.97] | 0.73 [0.61, 0.83] | 0.56 |
| primary_gemini|RP | 150 | 0.91 [0.76, 0.97] | 0.74 [0.61, 0.84] | 0.55 |
| second_gpt41mini|R | 97 | 0.97 [0.75, 1.00] | 0.16 [0.08, 0.30] | 0.05 |
| second_gpt41mini|RP | 97 | 1.00 [0.84, 1.00] | 0.00 [0.00, 0.10] | 0.00 |
| ttj_J1_english|R | 38 | 1.00 [0.72, 1.00] | 0.62 [0.39, 0.81] | 0.60 |
| ttj_J1_english|RP | 38 | 1.00 [0.77, 1.00] | 0.88 [0.63, 0.97] | 0.84 |
| direct_J1_same_instrument|R | 38 | 1.00 [0.72, 1.00] | 0.74 [0.50, 0.89] | 0.69 |
| direct_J1_same_instrument|RP | 38 | 0.91 [0.65, 0.98] | 0.90 [0.66, 0.98] | 0.84 |
| arch_j1_mdeberta|R | 33 | 0.84 [0.50, 0.97] | 0.90 [0.69, 0.97] | 0.71 |
| arch_j1_mdeberta|RP | 33 | 0.87 [0.56, 0.97] | 0.94 [0.73, 0.99] | 0.86 |
| arch_j2_llama8b_exp9|R | 12 | 0.66 [0.23, 0.93] | 0.89 [0.51, 0.99] | 0.47 |
| arch_j2_llama8b_exp9|RP | 12 | 0.75 [0.32, 0.95] | 0.96 [0.56, 1.00] | 0.66 |
| arch_qwen3_14b|R | 117 | 0.99 [0.84, 1.00] | 0.30 [0.18, 0.45] | 0.31 |
| arch_qwen3_14b|RP | 87 | 1.00 [0.83, 1.00] | 0.01 [0.00, 0.10] | 0.02 |
| arch_llama8b_exp8|R | 6 | 1.00 [0.57, 1.00] | 1.00 [0.21, 1.00] | 1.00 |
| arch_llama8b_exp8|RP | 6 | 1.00 [0.57, 1.00] | 1.00 [0.21, 1.00] | 1.00 |
| lexicon|R | 150 | 0.62 [0.43, 0.78] | 0.90 [0.80, 0.95] | 0.51 |
| lexicon|RP | 150 | 0.52 [0.35, 0.68] | 0.89 [0.78, 0.95] | 0.40 |

## gams3_it|sl|orig (n_adj=15, prevalence R=1.00, OFF_TASK share=0.00)

| instrument | n | Se [CI] | Sp [CI] | kappa vs adj |
|---|---|---|---|---|
| primary_gemini|R | 15 | 1.00 [0.80, 1.00] | n/a | nan |
| primary_gemini|RP | 15 | 1.00 [0.80, 1.00] | n/a | nan |
| second_gpt41mini|R | 6 | 1.00 [0.61, 1.00] | n/a | nan |
| second_gpt41mini|RP | 6 | 1.00 [0.61, 1.00] | n/a | nan |
| ttj_J1_english|R | 15 | 1.00 [0.80, 1.00] | n/a | nan |
| ttj_J1_english|RP | 15 | 1.00 [0.80, 1.00] | n/a | nan |
| direct_J1_same_instrument|R | 15 | 1.00 [0.80, 1.00] | n/a | nan |
| direct_J1_same_instrument|RP | 15 | 1.00 [0.80, 1.00] | n/a | nan |
| arch_qwen3_14b|R | 11 | 1.00 [0.74, 1.00] | n/a | nan |
| arch_qwen3_14b|RP | 11 | 1.00 [0.74, 1.00] | n/a | nan |
| lexicon|R | 15 | 1.00 [0.80, 1.00] | n/a | nan |
| lexicon|RP | 15 | 1.00 [0.80, 1.00] | n/a | nan |

## gemma_it|en|edited (n_adj=60, prevalence R=0.18, OFF_TASK share=0.00)

| instrument | n | Se [CI] | Sp [CI] | kappa vs adj |
|---|---|---|---|---|
| primary_gemini|R | 60 | 1.00 [0.59, 1.00] | 0.70 [0.42, 0.88] | 0.37 |
| primary_gemini|RP | 60 | 0.84 [0.62, 0.94] | 0.80 [0.38, 0.96] | 0.49 |
| second_gpt41mini|R | 18 | 1.00 [0.31, 1.00] | 0.23 [0.08, 0.50] | 0.05 |
| second_gpt41mini|RP | 18 | 1.00 [0.70, 1.00] | 0.00 [0.00, 0.37] | 0.00 |
| ttj_J1_english|R | 40 | 0.96 [0.48, 1.00] | 0.61 [0.39, 0.79] | 0.30 |
| ttj_J1_english|RP | 40 | 0.89 [0.60, 0.98] | 0.72 [0.46, 0.89] | 0.50 |
| direct_J1_same_instrument|R | 26 | 0.92 [0.30, 1.00] | 0.53 [0.30, 0.75] | 0.16 |
| direct_J1_same_instrument|RP | 26 | 0.77 [0.43, 0.94] | 0.70 [0.36, 0.91] | 0.44 |
| arch_j1_mdeberta|R | 23 | 0.78 [0.36, 0.96] | 0.65 [0.37, 0.85] | 0.24 |
| arch_j1_mdeberta|RP | 23 | 0.67 [0.37, 0.88] | 0.94 [0.52, 1.00] | 0.56 |
| arch_j2_llama8b_exp9|R | 10 | 0.00 [0.00, 0.66] | 0.48 [0.16, 0.81] | -0.43 |
| arch_j2_llama8b_exp9|RP | 10 | 0.72 [0.34, 0.93] | 0.75 [0.24, 0.97] | 0.17 |
| arch_qwen3_14b|R | 37 | 1.00 [0.53, 1.00] | 0.46 [0.18, 0.76] | 0.10 |
| arch_qwen3_14b|RP | 25 | 1.00 [0.66, 1.00] | 0.00 [0.00, 0.24] | 0.00 |
| arch_gemini_exp8|R | 12 | 1.00 [0.34, 1.00] | 0.73 [0.24, 0.96] | 0.33 |
| arch_gemini_exp8|RP | 12 | 0.68 [0.31, 0.91] | 0.86 [0.22, 0.99] | 0.33 |
| lexicon|R | 60 | 0.62 [0.26, 0.89] | 0.53 [0.28, 0.77] | -0.03 |
| lexicon|RP | 60 | 0.74 [0.52, 0.89] | 0.75 [0.34, 0.95] | 0.12 |

## gemma_it|en|orig (n_adj=15, prevalence R=0.73, OFF_TASK share=0.00)

| instrument | n | Se [CI] | Sp [CI] | kappa vs adj |
|---|---|---|---|---|
| primary_gemini|R | 15 | 1.00 [0.74, 1.00] | 0.25 [0.05, 0.70] | 0.33 |
| primary_gemini|RP | 15 | 1.00 [0.80, 1.00] | n/a | nan |
| ttj_J1_english|R | 15 | 1.00 [0.74, 1.00] | 0.00 [0.00, 0.49] | 0.00 |
| ttj_J1_english|RP | 15 | 1.00 [0.80, 1.00] | n/a | nan |
| direct_J1_same_instrument|R | 15 | 1.00 [0.74, 1.00] | 0.25 [0.05, 0.70] | 0.33 |
| direct_J1_same_instrument|RP | 15 | 0.93 [0.70, 0.99] | n/a | 0.00 |
| arch_j1_mdeberta|R | 7 | 1.00 [0.61, 1.00] | 0.00 [0.00, 0.79] | 0.00 |
| arch_j1_mdeberta|RP | 7 | 1.00 [0.65, 1.00] | n/a | nan |
| arch_qwen3_14b|R | 8 | 1.00 [0.57, 1.00] | 0.00 [0.00, 0.56] | 0.00 |
| arch_qwen3_14b|RP | 8 | 1.00 [0.68, 1.00] | n/a | nan |
| lexicon|R | 15 | 1.00 [0.74, 1.00] | 0.25 [0.05, 0.70] | 0.33 |
| lexicon|RP | 15 | 0.93 [0.70, 0.99] | n/a | 0.00 |

## gemma_it|sl|edited (n_adj=150, prevalence R=0.53, OFF_TASK share=0.00)

| instrument | n | Se [CI] | Sp [CI] | kappa vs adj |
|---|---|---|---|---|
| primary_gemini|R | 150 | 0.99 [0.87, 1.00] | 0.66 [0.43, 0.83] | 0.65 |
| primary_gemini|RP | 150 | 0.98 [0.89, 1.00] | 0.90 [0.56, 0.98] | 0.73 |
| second_gpt41mini|R | 70 | 0.97 [0.76, 1.00] | 0.55 [0.22, 0.84] | 0.30 |
| second_gpt41mini|RP | 70 | 1.00 [0.85, 1.00] | 0.01 [0.00, 0.57] | 0.05 |
| ttj_J1_english|R | 69 | 1.00 [0.80, 1.00] | 0.36 [0.16, 0.63] | 0.60 |
| ttj_J1_english|RP | 69 | 0.98 [0.82, 1.00] | 0.96 [0.71, 1.00] | 0.82 |
| direct_J1_same_instrument|R | 69 | 1.00 [0.80, 1.00] | 0.41 [0.19, 0.67] | 0.65 |
| direct_J1_same_instrument|RP | 69 | 0.97 [0.80, 1.00] | 1.00 [0.77, 1.00] | 0.83 |
| arch_j1_mdeberta|R | 54 | 0.95 [0.80, 0.99] | 0.66 [0.46, 0.82] | 0.60 |
| arch_j1_mdeberta|RP | 54 | 0.87 [0.72, 0.94] | 1.00 [0.75, 1.00] | 0.78 |
| arch_j2_llama8b_exp9|R | 25 | 0.86 [0.51, 0.97] | 0.67 [0.41, 0.85] | 0.39 |
| arch_j2_llama8b_exp9|RP | 25 | 0.75 [0.48, 0.90] | 0.81 [0.48, 0.95] | 0.43 |
| arch_qwen3_14b|R | 96 | 0.99 [0.84, 1.00] | 0.39 [0.17, 0.67] | 0.25 |
| arch_qwen3_14b|RP | 66 | 1.00 [0.82, 1.00] | 0.00 [0.00, 0.12] | 0.00 |
| arch_gemini_exp8|R | 30 | 1.00 [0.72, 1.00] | 0.69 [0.32, 0.91] | 0.74 |
| arch_gemini_exp8|RP | 30 | 0.97 [0.73, 1.00] | 1.00 [0.46, 1.00] | 0.59 |
| lexicon|R | 150 | 0.97 [0.84, 0.99] | 0.66 [0.44, 0.83] | 0.58 |
| lexicon|RP | 150 | 0.88 [0.75, 0.94] | 0.89 [0.55, 0.98] | 0.55 |

## gemma_it|sl|orig (n_adj=15, prevalence R=1.00, OFF_TASK share=0.00)

| instrument | n | Se [CI] | Sp [CI] | kappa vs adj |
|---|---|---|---|---|
| primary_gemini|R | 15 | 1.00 [0.80, 1.00] | n/a | nan |
| primary_gemini|RP | 15 | 1.00 [0.80, 1.00] | n/a | nan |
| ttj_J1_english|R | 15 | 1.00 [0.80, 1.00] | n/a | nan |
| ttj_J1_english|RP | 15 | 1.00 [0.80, 1.00] | n/a | nan |
| direct_J1_same_instrument|R | 15 | 1.00 [0.80, 1.00] | n/a | nan |
| direct_J1_same_instrument|RP | 15 | 1.00 [0.80, 1.00] | n/a | nan |
| arch_qwen3_14b|R | 11 | 1.00 [0.74, 1.00] | n/a | nan |
| arch_qwen3_14b|RP | 11 | 1.00 [0.74, 1.00] | n/a | nan |
| lexicon|R | 15 | 1.00 [0.80, 1.00] | n/a | nan |
| lexicon|RP | 15 | 1.00 [0.80, 1.00] | n/a | nan |

## kappa gemini vs gpt-4.1-mini (edited rows)

- gams3_it|en|edited|decisive_exp9_exp11: {"n": 725, "kappa_R": 0.31195469156589634, "kappa_CI95": [0.2651088233959184, 0.3608448142523582], "kappa_RP": 0.1638071968812315, "rate_primary": 0.3724137931034483, "rate_second": 0.7324137931034482}
- gams3_it|en|edited|all: {"n": 2740, "kappa_R": 0.35147313362465893, "kappa_CI95": [0.31982487991013364, 0.3835779026880777], "kappa_RP": 0.14375861010060986, "rate_primary": 0.6113138686131386, "rate_second": 0.8551094890510949}
- gams3_it|sl|edited|decisive_exp9_exp11: {"n": 1387, "kappa_R": 0.39449983551644746, "kappa_CI95": [0.3558322714530605, 0.43414201140350656], "kappa_RP": 0.16200266641696892, "rate_primary": 0.4953136265320836, "rate_second": 0.7649603460706561}
- gams3_it|sl|edited|all: {"n": 3844, "kappa_R": 0.37539884984260335, "kappa_CI95": [0.3443363967956078, 0.40855514465034765], "kappa_RP": 0.13392427253984487, "rate_primary": 0.7008324661810614, "rate_second": 0.8644640998959418}
- gemma_it|en|edited|decisive_exp9_exp11: {"n": 753, "kappa_R": 0.4505316189137049, "kappa_CI95": [0.40073486845893547, 0.5000055734124789], "kappa_RP": 0.12040528701481733, "rate_primary": 0.36786188579017265, "rate_second": 0.6108897742363878}
- gemma_it|en|edited|all: {"n": 2081, "kappa_R": 0.40440371523170604, "kappa_CI95": [0.3692283264396162, 0.4388768918163545], "kappa_RP": 0.09260892583942744, "rate_primary": 0.557424315233061, "rate_second": 0.8000961076405574}
- gemma_it|sl|edited|decisive_exp9_exp11: {"n": 1358, "kappa_R": 0.7232844519008064, "kappa_CI95": [0.6854958021180932, 0.7645219238117534], "kappa_RP": 0.24621422375199786, "rate_primary": 0.56480117820324, "rate_second": 0.6620029455081001}
- gemma_it|sl|edited|all: {"n": 3112, "kappa_R": 0.7323618482583653, "kappa_CI95": [0.6996263401997324, 0.761142797867522], "kappa_RP": 0.25565895467531596, "rate_primary": 0.7663881748071979, "rate_second": 0.8255141388174807}

Retest: {"n": 40, "kappa_4class": 0.6047430830039525, "kappa_R": 0.6874999999999999, "agree_4class": 0.75, "type": "INTER-adjudicator (claude-sonnet-4.5 vs executing Claude Opus 5 agent), both blind under rubric v2", "note": "AM2: replaces the pre-registered intra-rater temperature-0.7 retest, which the platform key limit blocked"}