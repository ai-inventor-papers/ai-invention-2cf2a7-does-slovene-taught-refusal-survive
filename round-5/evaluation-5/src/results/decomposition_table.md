# Step 3 - G3 / G3_orig / G3_edit / slope decomposition (every body x readout)

Rule: edit-induced: G3_edit CI95 excl 0 & |G3_edit|>=m/2; baseline: G3_orig CI95 excl 0 & G3_edit CI90 within +-m; else underdetermined

Status counts: {'edit-induced': 15, 'baseline': 0, 'underdetermined': 64}; G3_edit range over valid R rows: [-9.97, 10.49]

Edit-induced rows by direction: {'lag_valid_manipulation': ['exp8_A1|PPI|RP|', 'exp8_B|archived_arch_lex|R|', 'exp8_B|PPI|RP|', 'exp10_op|raw_primary|R|', 'exp10_op|raw_primary|RP|', 'exp14_grid|raw_R|R|slsl', 'exp14_grid|raw_RP|RP|slsl', 'exp14_grid|rg_R|R|ensl'], 'lag_invalid_manipulation': ['exp14_grid|raw_R|R|husl', 'exp14_grid|raw_RP|RP|husl', 'exp14_grid|rg_R|R|husl'], 'anti_lag': ['exp9_lambda|raw_primary|R|', 'exp9_lambda|archived_arch_j1|R|', 'exp8_A1|archived_arch_q14|R|', 'exp8_B|archived_arch_q14|R|']}

_exp14 rg_R rows are numerically degenerate (exp14 rg_stability.degenerate = True); do not cite_

| body | readout | coding | G3 [95%] | G3_orig [95%] | G3_edit [95%] | G3_edit 90% | MDE(G3) | b_Gemma | b_GaMS | b_diff | status | ceiling (G3_orig) | flag |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| exp9_lambda | raw_primary | R | -1.12 [-1.70, -0.63] | -2.56 [-4.07, -1.32] | 1.43 [0.29, 2.98] | [0.47, 2.86] | 0.76 | 1.45 [1.14, 1.80] | 0.99 [0.84, 1.13] | -0.46 | edit-induced | ROBUST-OFFSET |  |
| exp9_lambda | RG | R | no estimate saved | | | | | | | | | | |
| exp9_lambda | PPI | R | -1.73 [-2.88, -0.04] | -2.18 [-5.00, -0.11] | 0.45 [-1.04, 3.30] | [-0.85, 3.06] | 2.03 | 1.39 [0.77, 2.09] | 1.33 [0.63, 2.61] | -0.06 | underdetermined | ROBUST-OFFSET |  |
| exp9_lambda | second_gpt41mini_IPW | R | 1.27 [-3.23, 3.01] | NA NA | NA NA | NA | 4.45 | 2.11 [-1.16, 3.13] | 0.66 [-0.32, 0.95] | -1.46 | None | ROBUST-OFFSET |  |
| exp9_lambda | ttj | R | -0.81 [-1.36, -0.31] | -1.55 [-2.40, 0.48] | 0.74 [-1.21, 1.60] | [-0.93, 1.47] | 0.75 | 1.28 [0.87, 1.88] | 0.92 [0.75, 1.16] | -0.35 | underdetermined | ROBUST-OFFSET |  |
| exp9_lambda | asr_noharm | R | fewer than 3 steps with labels | | | | | | | | | | |
| exp9_lambda | archived_arch_j1 | R | -0.97 [-1.52, -0.50] | -3.19 [-3.80, -2.37] | 2.23 [1.33, 2.90] | [1.49, 2.76] | 0.73 | 1.42 [1.12, 1.75] | 1.10 [0.92, 1.26] | -0.32 | edit-induced | ROBUST-OFFSET |  |
| exp9_lambda | archived_arch_j2 | R | -1.72 [-2.33, -0.95] | 0.75 [-1.65, 3.13] | -2.47 [-4.66, 0.04] | [-4.38, -0.37] | 0.98 | 1.76 [1.06, 2.47] | 1.97 [1.03, 2.33] | 0.20 | underdetermined | ROBUST-OFFSET |  |
| exp9_lambda | archived_arch_lex | R | -0.86 [-1.28, -0.39] | -0.89 [-2.55, 0.75] | 0.04 [-1.69, 1.74] | [-1.44, 1.60] | 0.63 | 0.98 [0.80, 1.17] | 1.30 [1.10, 1.52] | 0.32 | underdetermined | ROBUST-OFFSET |  |
| exp9_lambda | raw_primary | RP | -1.44 [-1.93, -1.03] | -2.43 [-3.99, -1.18] | 0.99 [-0.16, 2.53] | [-0.02, 2.43] | 0.65 | 1.26 [0.98, 1.52] | 0.96 [0.82, 1.09] | -0.30 | underdetermined | ROBUST-OFFSET |  |
| exp9_lambda | RG | RP | no estimate saved | | | | | | | | | | |
| exp9_lambda | PPI | RP | -2.26 [-4.06, -0.16] | -1.51 [-2.87, 0.14] | -0.75 [-3.08, 1.62] | [-2.64, 1.20] | 2.78 | 0.75 [0.53, 2.16] | 1.54 [0.63, 2.75] | 0.80 | underdetermined | ROBUST-OFFSET |  |
| exp9_lambda | second_gpt41mini_IPW | RP | -5.18 [-19.69, 20.71] | NA NA | NA NA | NA | 28.86 | 0.09 [-0.22, 7.49] | 1.67 [-2.99, 12.71] | 1.58 | None | ROBUST-OFFSET |  |
| exp9_lambda | ttj | RP | -0.81 [-1.36, -0.31] | -1.55 [-2.40, 0.48] | 0.74 [-1.21, 1.60] | [-0.93, 1.47] | 0.75 | 1.28 [0.87, 1.88] | 0.92 [0.75, 1.16] | -0.35 | underdetermined | ROBUST-OFFSET |  |
| exp11_final | raw_primary | R | -1.00 [-1.40, -0.68] | -1.11 [-2.74, -0.21] | 0.10 [-0.85, 1.71] | [-0.66, 1.46] | 0.51 | 1.40 [1.11, 1.79] | 0.97 [0.83, 1.12] | -0.43 | underdetermined | CEILING-ARTEFACT |  |
| exp11_final | RG | R | -1.55 [-3.43, -0.13] | NA NA | NA NA | NA | 2.36 | 0.78 [0.53, 2.08] | 0.96 [0.50, 1.98] | 0.19 | None | CEILING-ARTEFACT |  |
| exp11_final | PPI | R | -1.84 [-4.50, 0.67] | -1.94 [-4.60, 0.63] | 0.10 [-3.65, 3.91] | [-2.77, 3.50] | 3.70 | 0.70 [0.01, 1.07] | 0.74 [0.30, 1.32] | 0.04 | underdetermined | CEILING-ARTEFACT |  |
| exp11_final | second_gpt41mini_IPW | R | point estimate unusable: fewer than 2 usable steps | | | | | | | | | | |
| exp11_final | ttj | R | -1.37 [-1.88, -0.94] | -0.99 [-2.74, 0.88] | -0.38 [-2.34, 1.38] | [-1.96, 1.18] | 0.67 | 1.63 [1.04, 2.50] | 1.21 [0.85, 1.63] | -0.42 | underdetermined | CEILING-ARTEFACT |  |
| exp11_final | archived_arch_q14 | R | -0.60 [-1.33, 0.45] | -0.75 [-2.77, 0.72] | 0.15 [-1.54, 2.60] | [-1.25, 2.18] | 1.27 | 1.89 [1.33, 2.70] | 1.40 [1.08, 1.71] | -0.49 | underdetermined | CEILING-ARTEFACT |  |
| exp11_final | archived_arch_lex | R | point estimate unusable: quasi-separation (|a| or |b| > 30) | | | | | | | | | | |
| exp11_final | raw_primary | RP | -1.23 [-1.59, -0.94] | -0.60 [-2.42, 0.86] | -0.63 [-2.12, 1.17] | [-1.80, 0.87] | 0.46 | 0.98 [0.76, 1.27] | 0.91 [0.77, 1.04] | -0.08 | underdetermined | CEILING-ARTEFACT |  |
| exp11_final | RG | RP | -0.91 [-2.50, 0.51] | NA NA | NA NA | NA | 2.15 | 0.66 [0.29, 1.02] | 0.56 [0.37, 1.38] | -0.10 | None | CEILING-ARTEFACT |  |
| exp11_final | PPI | RP | -0.77 [-2.17, 0.35] | 0.00 [-0.67, 0.81] | -0.77 [-2.33, 0.48] | [-2.15, 0.22] | 1.80 | 1.00 [0.57, 1.85] | 1.32 [0.57, 2.23] | 0.32 | underdetermined | CEILING-ARTEFACT |  |
| exp11_final | second_gpt41mini_IPW | RP | point estimate unusable: fewer than 2 usable steps | | | | | | | | | | |
| exp11_final | ttj | RP | -1.48 [-1.95, -1.01] | -0.65 [-2.54, 1.45] | -0.83 [-3.00, 1.15] | [-2.55, 0.91] | 0.67 | 1.14 [0.80, 1.63] | 1.09 [0.78, 1.47] | -0.06 | underdetermined | CEILING-ARTEFACT |  |
| exp8_A1 | raw_primary | R | -1.54 [-2.11, -1.00] | -1.13 [-2.67, 0.04] | -0.41 [-1.65, 1.26] | [-1.43, 1.05] | 0.79 | 1.66 [1.31, 2.00] | 1.03 [0.85, 1.20] | -0.64 | underdetermined | CEILING-ARTEFACT |  |
| exp8_A1 | RG | R | -2.51 [-6.12, -0.53] | NA NA | NA NA | NA | 4.00 | 1.14 [0.87, 2.06] | 1.09 [0.59, 2.26] | -0.05 | None | CEILING-ARTEFACT |  |
| exp8_A1 | PPI | R | -1.78 [-3.18, 0.34] | -1.53 [-4.45, 0.66] | -0.25 [-2.81, 3.43] | [-2.22, 2.92] | 2.51 | 0.95 [0.34, 1.78] | 1.23 [0.49, 1.81] | 0.29 | underdetermined | CEILING-ARTEFACT |  |
| exp8_A1 | second_gpt41mini_IPW | R | point estimate unusable: fewer than 2 usable steps | | | | | | | | | | |
| exp8_A1 | archived_arch_q14 | R | 1.57 [0.11, 3.00] | -1.64 [-3.34, -0.39] | 3.21 [1.26, 5.49] | [1.54, 5.04] | 2.06 | 2.31 [1.57, 3.01] | 1.20 [0.75, 1.69] | -1.11 | edit-induced | CEILING-ARTEFACT |  |
| exp8_A1 | archived_arch_lex | R | -0.19 [-0.50, 0.12] | -0.77 [-2.33, 0.40] | 0.58 [-0.64, 2.16] | [-0.45, 1.96] | 0.45 | 1.17 [0.98, 1.36] | 1.03 [0.85, 1.21] | -0.14 | underdetermined | CEILING-ARTEFACT |  |
| exp8_A1 | archived_arch_m24 | R | 7.58 [-14.70, 23.76] | NA NA | NA NA | NA | 27.47 | 1.90 [-0.68, 2.02] | -2.20 [-7.72, 7.45] | -4.10 | None | CEILING-ARTEFACT |  |
| exp8_A1 | raw_primary | RP | -1.87 [-2.39, -1.41] | -0.72 [-2.35, 0.68] | -1.15 [-2.62, 0.55] | [-2.34, 0.33] | 0.70 | 1.44 [1.14, 1.79] | 0.89 [0.75, 1.03] | -0.55 | underdetermined | CEILING-ARTEFACT |  |
| exp8_A1 | RG | RP | -1.54 [-3.92, 0.07] | NA NA | NA NA | NA | 2.84 | 0.68 [0.51, 1.35] | 0.74 [0.42, 1.37] | 0.06 | None | CEILING-ARTEFACT |  |
| exp8_A1 | PPI | RP | -2.45 [-3.42, -0.45] | 0.49 [-0.48, 1.73] | -2.94 [-4.50, -0.73] | [-4.23, -1.12] | 2.12 | 0.88 [0.53, 2.48] | 1.10 [0.32, 1.34] | 0.22 | edit-induced | CEILING-ARTEFACT |  |
| exp8_A1 | second_gpt41mini_IPW | RP | point estimate unusable: fewer than 2 usable steps | | | | | | | | | | |
| exp8_B | raw_primary | R | -1.20 [-1.77, -0.58] | -1.33 [-2.37, 0.78] | 0.12 [-2.21, 1.47] | [-1.59, 1.27] | 0.85 | 1.47 [0.94, 2.61] | 1.13 [0.83, 1.45] | -0.34 | underdetermined | CEILING-ARTEFACT |  |
| exp8_B | RG | R | -1.74 [-3.38, 0.35] | NA NA | NA NA | NA | 2.67 | 1.16 [0.50, 1.51] | 1.13 [0.44, 1.79] | -0.04 | None | CEILING-ARTEFACT |  |
| exp8_B | PPI | R | -1.73 [-2.86, -0.36] | -1.17 [-3.72, 1.17] | -0.57 [-3.01, 2.50] | [-2.49, 2.12] | 1.78 | 0.84 [-0.45, 1.54] | 1.14 [0.09, 1.46] | 0.31 | underdetermined | CEILING-ARTEFACT |  |
| exp8_B | second_gpt41mini_IPW | R | point estimate unusable: fewer than 2 usable steps | | | | | | | | | | |
| exp8_B | archived_arch_q14 | R | 1.57 [-0.34, 3.63] | -2.03 [-3.30, 0.04] | 3.59 [0.78, 5.81] | [1.18, 5.18] | 2.84 | 2.56 [1.47, 3.39] | 1.22 [0.63, 1.51] | -1.34 | edit-induced | CEILING-ARTEFACT |  |
| exp8_B | archived_arch_lex | R | -2.36 [-2.97, -1.72] | -0.64 [-1.72, 1.29] | -1.72 [-3.69, -0.52] | [-3.39, -0.69] | 0.89 | 2.34 [1.70, 2.90] | 1.38 [1.06, 1.65] | -0.96 | edit-induced | CEILING-ARTEFACT |  |
| exp8_B | archived_arch_m24 | R | 0.04 [-2.52, 1.18] | NA NA | NA NA | NA | 2.65 | 1.06 [0.12, 1.45] | 0.36 [-0.04, 0.89] | -0.70 | None | CEILING-ARTEFACT |  |
| exp8_B | raw_primary | RP | -1.30 [-1.90, -0.59] | -0.83 [-2.16, 2.24] | -0.47 [-3.59, 1.25] | [-3.10, 0.99] | 0.94 | 1.24 [0.75, 2.51] | 1.05 [0.76, 1.33] | -0.19 | underdetermined | CEILING-ARTEFACT |  |
| exp8_B | RG | RP | -0.78 [-2.48, 1.50] | NA NA | NA NA | NA | 2.85 | 0.78 [0.39, 0.93] | 0.75 [0.30, 1.31] | -0.03 | None | CEILING-ARTEFACT |  |
| exp8_B | PPI | RP | -2.19 [-2.98, -0.59] | 1.12 [-0.54, 2.01] | -3.31 [-4.33, -0.66] | [-3.98, -1.03] | 1.71 | 1.05 [0.38, 1.69] | 1.64 [-0.50, 1.81] | 0.59 | edit-induced | CEILING-ARTEFACT |  |
| exp8_B | second_gpt41mini_IPW | RP | point estimate unusable: fewer than 2 usable steps | | | | | | | | | | |
| exp9_trial_Bprime | raw_primary | R | point estimate unusable: fewer than 2 usable steps | | | | | | | | | | |
| exp9_trial_Bprime | archived_arch_j1 | R | 9.33 [-5.69, 20.38] | -1.16 [-2.10, 0.82] | 10.49 [-4.85, 21.51] | [-4.35, 19.29] | 18.62 | 8.33 [6.42, 13.17] | 1.09 [0.79, 1.42] | -7.24 | underdetermined |  |  |
| exp9_trial_Bprime | archived_arch_j2 | R | point estimate unusable: quasi-separation (|a| or |b| > 30) | | | | | | | | | | |
| exp9_trial_Bprime | archived_arch_lex | R | point estimate unusable: quasi-separation (|a| or |b| > 30) | | | | | | | | | | |
| exp9_trial_Bprime | raw_primary | RP | point estimate unusable: fewer than 2 usable steps | | | | | | | | | | |
| exp10_op | raw_primary | R | -2.42 [-4.35, -1.53] | 0.99 [-1.10, 3.53] | -3.40 [-6.09, -1.30] | [-5.79, -1.64] | 2.02 | NA NA | NA NA | NA | edit-induced | NOT-OUTSIDE-MARGIN |  |
| exp10_op | RG | R | -3.79 [-5.48, -1.19] | NA NA | NA NA | NA | 3.06 | NA NA | NA NA | NA | None | NOT-OUTSIDE-MARGIN |  |
| exp10_op | archived_lex | R | -2.31 [-2.96, -1.74] | -1.82 [-3.38, -0.72] | -0.48 [-1.80, 1.17] | [-1.61, 1.01] | 0.87 | NA NA | NA NA | NA | underdetermined | NOT-OUTSIDE-MARGIN |  |
| exp10_op | raw_primary | RP | -2.29 [-4.21, -1.39] | 0.35 [-1.60, 2.31] | -2.64 [-4.95, -0.81] | [-4.61, -1.14] | 2.02 | NA NA | NA NA | NA | edit-induced | NOT-OUTSIDE-MARGIN |  |
| exp10_op | RG | RP | -1.90 [-4.07, 2.55] | NA NA | NA NA | NA | 4.73 | NA NA | NA NA | NA | None | NOT-OUTSIDE-MARGIN |  |
| exp15_ladder | RAW | R | -0.70 [-1.01, -0.42] | -1.17 [-2.83, 0.22] | 0.47 [-0.96, 2.14] | [-0.68, 1.91] | 0.42 | 0.94 [0.75, 1.17] | 0.80 [0.63, 0.95] | -0.14 | underdetermined | CEILING-ARTEFACT |  |
| exp15_ladder | RG | R | -0.01 [-4.36, 11.27] | -1.76 [-5.45, 1.96] | 1.75 [-4.58, 13.18] | [-3.08, 7.00] | 16.11 | NA NA | NA NA | NA | underdetermined | CEILING-ARTEFACT |  |
| exp15_ladder | PPI | R | -0.75 [-2.43, 0.99] | -1.52 [-6.46, 2.82] | 0.76 [-3.78, 6.27] | [-3.11, 5.56] | 2.45 | NA NA | NA NA | NA | underdetermined | CEILING-ARTEFACT |  |
| exp15_ladder | second_family_IPW | R | NA NA | NA NA | NA NA | NA | NA | NA NA | NA NA | NA | None | CEILING-ARTEFACT |  |
| exp15_ladder | RAW | RP | -0.70 [-1.01, -0.42] | -1.17 [-2.83, 0.22] | 0.47 [-0.96, 2.14] | [-0.68, 1.91] | 0.42 | 0.94 [0.75, 1.17] | 0.80 [0.63, 0.95] | -0.14 | underdetermined | CEILING-ARTEFACT |  |
| exp15_ladder | RG | RP | -0.53 [-4.34, 2.92] | 1.10 [0.00, 3.38] | -1.63 [-5.80, 2.57] | [-4.78, 1.60] | 10.93 | NA NA | NA NA | NA | underdetermined | CEILING-ARTEFACT |  |
| exp15_ladder | PPI | RP | -0.49 [-1.90, 0.66] | 1.92 [-2.56, 3.87] | -2.41 [-4.90, 2.44] | [-4.44, 1.98] | 1.79 | NA NA | NA NA | NA | underdetermined | CEILING-ARTEFACT |  |
| exp15_ladder | second_family_IPW | RP | NA NA | NA NA | NA NA | NA | NA | NA NA | NA NA | NA | None | CEILING-ARTEFACT |  |
| exp15_ladder | TTJ | R | -0.79 [-1.09, -0.48] | -1.37 [-2.29, 0.37] | 0.58 [-1.18, 1.52] | NA | NA | 0.86 NA | 0.64 NA | -0.22 | underdetermined | CEILING-ARTEFACT |  |
| exp15_random_arm | rank0 random vs Heretic at matched lambda | R | NA NA | NA NA | -0.40 [-2.14, 1.29] | NA | NA | NA NA | NA NA | NA | underdetermined |  |  |
| exp15_random_arm | rank1 random vs Heretic at matched lambda | R | NA NA | NA NA | -0.30 [-2.10, 1.27] | NA | NA | NA NA | NA NA | NA | underdetermined |  |  |
| exp15_random_arm | rank2 random vs Heretic at matched lambda | R | NA NA | NA NA | 0.11 [-1.65, 1.73] | NA | NA | NA NA | NA NA | NA | underdetermined |  |  |
| exp15_random_arm | rank3 random vs Heretic at matched lambda | R | NA NA | NA NA | 0.06 [-1.76, 1.70] | NA | NA | NA NA | NA NA | NA | underdetermined |  |  |
| exp14_grid | raw_R | R | -2.42 [-3.21, -1.53] | -0.58 NA | -1.84 [-2.80, -0.78] | [-2.66, -0.93] | 1.17 | NA NA | NA NA | NA | edit-induced |  |  |
| exp14_grid | raw_R | R | -2.63 [-3.46, -1.30] | -1.37 NA | -1.26 [-2.17, 0.20] | [-2.02, -0.17] | 1.55 | NA NA | NA NA | NA | underdetermined |  |  |
| exp14_grid | raw_R | R | -2.37 [-3.33, -0.75] | -0.22 NA | -2.15 [-3.16, -0.46] | [-3.02, -0.84] | 1.84 | NA NA | NA NA | NA | edit-induced |  | INVALID-MANIPULATION (GaMS output-language compliance < 0.90) |
| exp14_grid | raw_R | R | 0.00 [-0.00, 0.00] | 0.00 NA | 0.00 [-0.00, 0.00] | [-0.00, 0.00] | 0.00 | NA NA | NA NA | NA | underdetermined |  |  |
| exp14_grid | raw_R | R | 0.45 [-0.30, 1.57] | 0.39 NA | 0.06 [-0.79, 1.18] | [-0.67, 0.97] | 1.33 | NA NA | NA NA | NA | underdetermined |  | INVALID-MANIPULATION (GaMS output-language compliance < 0.90) |
| exp14_grid | raw_R | R | -0.85 [-1.57, 0.30] | -0.93 NA | 0.09 [-0.78, 1.37] | [-0.66, 1.13] | 1.33 | NA NA | NA NA | NA | underdetermined |  |  |
| exp14_grid | raw_R | R | -0.56 [-1.34, 0.84] | -0.05 NA | -0.51 [-1.51, 1.00] | [-1.35, 0.70] | 1.56 | NA NA | NA NA | NA | underdetermined |  |  |
| exp14_grid | raw_R | R | -1.49 [-2.24, -0.34] | -0.83 NA | -0.67 [-1.65, 0.74] | [-1.46, 0.43] | 1.45 | NA NA | NA NA | NA | underdetermined |  | INVALID-MANIPULATION (GaMS output-language compliance < 0.90) |
| exp14_grid | raw_R | R | 0.40 [-0.41, 1.76] | 0.30 NA | 0.09 [-0.87, 1.55] | [-0.72, 1.22] | 1.61 | NA NA | NA NA | NA | underdetermined |  | INVALID-MANIPULATION (GaMS output-language compliance < 0.90) |
| exp14_grid | raw_RP | RP | -2.42 [-3.21, -1.53] | -0.58 NA | -1.84 [-2.80, -0.78] | [-2.66, -0.93] | 1.17 | NA NA | NA NA | NA | edit-induced |  |  |
| exp14_grid | raw_RP | RP | -2.63 [-3.46, -1.30] | -1.37 NA | -1.26 [-2.17, 0.20] | [-2.02, -0.17] | 1.55 | NA NA | NA NA | NA | underdetermined |  |  |
| exp14_grid | raw_RP | RP | -2.37 [-3.33, -0.75] | -0.22 NA | -2.15 [-3.16, -0.46] | [-3.02, -0.84] | 1.84 | NA NA | NA NA | NA | edit-induced |  | INVALID-MANIPULATION (GaMS output-language compliance < 0.90) |
| exp14_grid | raw_RP | RP | 0.00 [-0.00, 0.00] | 0.00 NA | 0.00 [-0.00, 0.00] | [-0.00, 0.00] | 0.00 | NA NA | NA NA | NA | underdetermined |  |  |
| exp14_grid | raw_RP | RP | 0.45 [-0.30, 1.57] | 0.39 NA | 0.06 [-0.79, 1.18] | [-0.67, 0.97] | 1.33 | NA NA | NA NA | NA | underdetermined |  | INVALID-MANIPULATION (GaMS output-language compliance < 0.90) |
| exp14_grid | raw_RP | RP | -0.85 [-1.57, 0.30] | -0.93 NA | 0.09 [-0.78, 1.37] | [-0.66, 1.13] | 1.33 | NA NA | NA NA | NA | underdetermined |  |  |
| exp14_grid | raw_RP | RP | -0.56 [-1.34, 0.84] | -0.05 NA | -0.51 [-1.51, 1.00] | [-1.35, 0.70] | 1.56 | NA NA | NA NA | NA | underdetermined |  |  |
| exp14_grid | raw_RP | RP | -1.49 [-2.24, -0.34] | -0.83 NA | -0.67 [-1.65, 0.74] | [-1.46, 0.43] | 1.45 | NA NA | NA NA | NA | underdetermined |  | INVALID-MANIPULATION (GaMS output-language compliance < 0.90) |
| exp14_grid | raw_RP | RP | 0.40 [-0.41, 1.76] | 0.30 NA | 0.09 [-0.87, 1.55] | [-0.72, 1.22] | 1.61 | NA NA | NA NA | NA | underdetermined |  | INVALID-MANIPULATION (GaMS output-language compliance < 0.90) |
| exp14_grid | rg_R | R | -8.24 [-13.75, -2.16] | -0.54 NA | -7.70 [-17.05, 0.64] | [-15.46, -0.90] | 8.81 | NA NA | NA NA | NA | underdetermined |  |  |
| exp14_grid | rg_R | R | -12.75 [-13.96, -4.96] | -2.78 NA | -9.97 [-13.77, -0.90] | [-13.25, -2.15] | 6.83 | NA NA | NA NA | NA | edit-induced |  |  |
| exp14_grid | rg_R | R | -12.98 [-13.87, -3.44] | 2.65 NA | -15.64 [-18.85, -3.59] | [-18.59, -5.50] | 8.45 | NA NA | NA NA | NA | edit-induced |  | INVALID-MANIPULATION (GaMS output-language compliance < 0.90) |
| exp14_grid | rg_R | R | 0.00 [-0.00, 0.00] | 0.00 NA | 0.00 [-0.00, 0.00] | [-0.00, 0.00] | 0.00 | NA NA | NA NA | NA | underdetermined |  |  |
| exp14_grid | rg_R | R | -5.60 [-6.91, 4.31] | 2.23 NA | -7.83 [-10.70, 3.70] | [-10.23, 2.26] | 9.32 | NA NA | NA NA | NA | underdetermined |  | INVALID-MANIPULATION (GaMS output-language compliance < 0.90) |
| exp14_grid | rg_R | R | 0.67 [-9.34, 6.61] | -2.49 NA | 3.16 [-8.54, 10.19] | [-7.55, 8.12] | 22.79 | NA NA | NA NA | NA | underdetermined |  |  |
| exp14_grid | rg_R | R | -0.87 [-7.89, 6.27] | 2.65 NA | -3.52 [-11.60, 6.58] | [-9.34, 4.78] | 24.07 | NA NA | NA NA | NA | underdetermined |  |  |
| exp14_grid | rg_R | R | -3.04 [-12.78, 4.73] | -2.02 NA | -1.02 [-12.49, 8.04] | [-10.48, 5.87] | 18.99 | NA NA | NA NA | NA | underdetermined |  | INVALID-MANIPULATION (GaMS output-language compliance < 0.90) |
| exp14_grid | rg_R | R | -0.02 [-6.91, 7.11] | 1.18 NA | -1.20 [-10.53, 6.75] | [-9.16, 4.82] | 24.41 | NA NA | NA NA | NA | underdetermined |  | INVALID-MANIPULATION (GaMS output-language compliance < 0.90) |
| exp14_grid | ppi_R | R | 0.33 [-8.13, 4.77] | -0.60 NA | 0.93 [-7.54, 5.40] | [-7.35, 4.20] | 9.85 | NA NA | NA NA | NA | underdetermined |  |  |
| exp14_grid | ppi_R | R | 3.82 [-8.36, 8.35] | -1.40 NA | 5.23 [-6.94, 9.78] | [-6.70, 8.28] | 12.43 | NA NA | NA NA | NA | underdetermined |  |  |
| exp14_grid | ppi_R | R | 4.64 [-8.25, 10.28] | -0.24 NA | 4.87 [-8.11, 10.49] | [-7.74, 8.59] | 12.49 | NA NA | NA NA | NA | underdetermined |  | INVALID-MANIPULATION (GaMS output-language compliance < 0.90) |
| exp14_grid | ppi_R | R | 0.00 [-0.00, 0.00] | 0.00 NA | 0.00 [-0.00, 0.00] | [-0.00, 0.00] | 0.00 | NA NA | NA NA | NA | underdetermined |  |  |
| exp14_grid | ppi_R | R | 0.79 [-1.89, 6.37] | 0.40 NA | 0.39 [-2.33, 5.96] | [-1.23, 4.53] | 5.79 | NA NA | NA NA | NA | underdetermined |  | INVALID-MANIPULATION (GaMS output-language compliance < 0.90) |
| exp14_grid | ppi_R | R | 0.44 [-1.68, 8.74] | -0.95 NA | 1.40 [-0.93, 9.74] | [-0.36, 7.88] | 7.93 | NA NA | NA NA | NA | underdetermined |  |  |
| exp14_grid | ppi_R | R | 0.34 [-1.23, 6.44] | -0.06 NA | 0.40 [-1.32, 6.57] | [-1.06, 4.84] | 5.72 | NA NA | NA NA | NA | underdetermined |  |  |
| exp14_grid | ppi_R | R | 2.13 [-7.46, 8.65] | -0.85 NA | 2.98 [-6.73, 9.58] | [-6.39, 8.04] | 10.94 | NA NA | NA NA | NA | underdetermined |  | INVALID-MANIPULATION (GaMS output-language compliance < 0.90) |
| exp14_grid | ppi_R | R | 0.50 [-1.10, 4.22] | 0.31 NA | 0.20 [-1.48, 4.00] | [-1.19, 2.89] | 4.25 | NA NA | NA NA | NA | underdetermined |  | INVALID-MANIPULATION (GaMS output-language compliance < 0.90) |

**Correction (parallel curves):** report both slopes with CIs; b_diff CI not saved -> no 'parallel' claim; b_Gemma 0.94 [0.75, 1.17], b_GaMS 0.80 [0.63, 0.95].

**Correction (MDE attribution):** MDE 0.422 belongs to G3; G3_edit's MDE is 2.319 and its 90% bound |G3_edit| < 1.914.
