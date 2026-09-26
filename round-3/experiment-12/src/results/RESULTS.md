# RESULTS — RQ3 capability control (iter-3 exp12)

All numbers below are read from `results/analysis.json` (recomputed by `src/audit.py`, path B). NF4 precision, zero-shot, lm-eval 0.4.13, 300 paired EN/SL items per task.

## Findings (hand-written summary; every number is from the tables below / `results/analysis.json`)

**Design recap.** The edits are the iter-1 selected Heretic edit (E_iter1, λ=1; λ-scaled 0.5/1.5/2.0) and artifact 2's B′ selection (E_art2). Controls are the original model and norm-matched random-direction edits (same Heretic parameters, only the directions random). There are 300 row-paired EN/SL items per task over 6 zero-shot MC tasks. H = headroom-normalised change: 0 = no change, −0.20 = the pre-registered catastrophe line. Positive A = SL damaged *less* than EN.

1. **No edit is catastrophic (confirmatory gate, full 300-item sets).** On E_iter1 and E_art2, every model × language point loss lies between −0.05 (a gain) and +0.018 of headroom. The largest 95% upper bound of the loss is 0.039 (GaMS E_iter1, EN). The raw-pp sensitivity agrees: every macro change is within ±0.8 pp. On the 100-item λ subset every λ ≤ 1.5 is OK in both models. Gemma λ=2.0 is **POSSIBLY_CATASTROPHIC** under the pre-registered rule: its SL point loss is 0.03, but the 95% upper bound is 0.33. That bound comes entirely from the Gemma-SL Winogrande cell, whose original headroom is exactly the 0.10 floor (0.60 vs chance 0.50), so a 3-point dip becomes H = −0.30 with a bootstrap tail to −1.5. The raw-pp macro for that cell set is +0.25 pp [−2.25, 2.75] (OK). We report the pre-registered verdict unchanged, **largest λ licensed OK: GaMS 2.0, Gemma 1.5**, and flag the λ=2.0 Gemma verdict as a headroom-floor artefact.
2. **No evidence that de-censoring hurts Slovene skills more than English ones.** For E_iter1 the asymmetry is A = H_SL − H_EN = +0.025 [−0.009, 0.060] in GaMS and +0.014 [−0.036, 0.082] in Gemma; for E_art2 it is +0.011 [−0.023, 0.050] (GaMS) and +0.033 [−0.020, 0.125] (Gemma). All four point estimates say SL is hurt *less*. The model × language interaction is I = +0.010 [−0.065, 0.074] for E_iter1 and −0.022 [−0.116, 0.043] for E_art2. The design resolves |I| only to about 0.10 of headroom, so the CI rules out a GaMS-specific SL penalty larger than about 0.07. A smaller one is undetermined, not excluded. Random-adjusted (edit − rand_nm_j1), the GaMS asymmetry is A_excess = +0.051 [+0.012, +0.093] for E_iter1 and +0.038 [+0.001, +0.080] for E_art2: relative to a same-size random perturbation, the edit spares Slovene. The language-swap placebo centres at 0 (audit).
3. **The one localised cost is English-side, in the Slovene-CPT model, and it replicates across two independently selected edits.** GaMS E_iter1 loses 3.7 pp on EN ARC-C (12 vs 1 discordant items; McNemar Holm p = 0.041) and 2.0 pp on EN BoolQ (6 vs 0; Holm p = 0.34). GaMS E_art2 loses 2.7 pp on EN ARC-C (9 vs 1) and 2.3 pp on EN BoolQ (7 vs 0), Holm p = 0.24 and 0.19. Their SL counterparts do not move (|Δ| ≤ 0.7 pp). Gemma shows no such cell for either edit (all |Δ| ≤ 2 pp, and ARC-C improves). The effect is small (macro EN loss 0.018–0.020). It is compatible with the English-derived direction being more entangled with English reasoning in GaMS, but one task at n = 300 does not establish a mechanism.
4. **Utility deltas of this size sit at the random-perturbation noise floor.** Random edits with ~100× smaller KL move macro H by −0.030 (GaMS rand_nm_j1, SL; CI excludes 0) and by ±0.01 (Gemma, two seeds). Flips concentrate on near-ties: 64–80% of all flips (edit or random) fall in the bottom quartile of the original choice margin, and the flip rate at margins ≥ median is ≤ 1%. lm-eval log-likelihoods are bf16 (92% are multiples of 1/16), so part of this floor is quantisation. One random draw per model (two for Gemma) cannot fully characterise the floor; this is a limitation.
5. **KL footprint: the edit perturbs English next-token distributions more than Slovene or Hungarian ones (C5a re-stated as a confirmed negative).** GaMS first-token KL(orig‖edit) is 0.097 on EN-BT vs 0.050 on SL-MT (ratio 0.52) and 0.039 on HU-MT (0.40). Random edits give ratio ≈1.1. Gemma: 0.311 EN-BT vs 0.223 SL-MT (0.72) vs 0.120 HU-MT (0.39). The multi-token EXCESS over random (SL/EN ratio of the edit ÷ that of the random edits) is 0.57 [0.49, 0.66] for GaMS and 0.29 [0.24, 0.37] for Gemma. This reproduces iter-1 (0.574 / 0.298) on a fresh harmless set never used for selection, at batch size 1 with an exactly-0 self-KL floor. Both < 1 means the refusal edit reaches Slovene *less* than English. The GaMS value is about 2× Gemma's, so GaMS's Slovene shares more of the edit's footprint, but it still sits below English. E_art2 behaves the same way: multi-token EXCESS is 0.57 [0.51, 0.66] (GaMS) and 0.31 [0.25, 0.39] (Gemma). The first-token EXCESS CIs are wide for Gemma (E_iter1 0.63 [0.33, 1.15]).
6. **Fluency is essentially untouched.** Bits-per-byte on human-translated FLORES passages changes under E_iter1 by +0.05% / +0.10% / +0.07% (GaMS, EN/SL/HU) and +0.03% / +0.09% / −0.03% (Gemma), versus +1.0–1.8% (GaMS) and +0.1–1.4% (Gemma) for the c=6 random edit. E_art2 is the same (Gemma +0.03% / +0.10% / +0.01%). Harmless-generation language consistency stays at 0.94–1.00 in every model × condition × arm (orig 0.96–1.00), and the degenerate rate is ≤ 0.03. The formal ≥ 95% consistency gate is missed only by GaMS λ=2.0 on HU-MT (0.94 vs 0.96 for the original). Competence covariates for artifact 4 are in `results/competence_covariates.json`: GaMS has much lower SL BPB than Gemma (0.890 vs 1.199), with EN 0.763 vs 0.873.
7. **Exploratory, not confirmatory: the chat template may matter.** On the same 100 GaMS items, E_iter1's SL ARC-C/BoolQ change is H = −0.15 / −0.075 *with* the chat template versus 0.00 / 0.00 without it (EN: −0.10 / −0.03 vs −0.12 / −0.03). The CIs are wide (n = 100) and cross 0, but the plan's concern (f) is real. The MC battery without chat template could understate chat-context damage in Slovene. It deserves a powered follow-up.
8. **Manipulation checks.** GaMS reproduces the logged Heretic KLs: E_iter1 0.227 vs 0.233 (−2.5%) and E_art2 0.275 vs 0.283 (−3%). All 5 norm-matched random edits reproduce within 1.5×, and so does the c=6 edit (0.025 vs 0.026). For Gemma, E_iter1 measures 0.510 vs the logged 0.366 (+39%, outside the ±25% rule, so formally **UNVERIFIED** per F3). Artifact 2's independently built Gemma pick shows the *same* inflation (0.532 vs 0.380, +40%). Gemma's random edits (0.002–0.004 vs 0.0018–0.0034) and its c=6 edit (0.070 vs 0.065) reproduce. So the adapters are live and correctly scaled, and the gap is a Gemma-specific difference in how the KL was *measured*, common to every structured Heretic edit. Diagnostic 1 **refutes padding/batching** as the cause: with left-padded batches of 100 and 16, as Heretic's evaluator uses, the Gemma KL stays at 0.518 / 0.516 (E_iter1) and 0.536 / 0.526 (E_art2). Diagnostic 2 **refutes prompt rendering**: rendering with an empty system turn changes the Gemma string, but the KL is unchanged (0.508 / 0.537). The gap therefore remains **unexplained**. Candidates we could not test are Heretic's evaluator internals (scores returned by `generate`) and iter-1's noisy Gemma baseline (unedited self-KL 0.030 under batching). The adapter's identity is not in doubt: the sha256 equals the iter-1 file, and the random and c=6 edits built by the same code reproduce. The Gemma E_iter1 gate verdict (OK) is reported with the UNVERIFIED label.

**What this does NOT show.** Generative capability (GSM8K was cut), long-form quality, and chat-context MC at scale were not tested. SL-Eval is machine-translated, and only deltas are interpreted. NF4 absolute accuracies are not bf16-comparable. The original models' SL accuracies match the GaMS3 paper's published numbers within 0.06 on all 6 tasks for both models when `acc` is compared for HellaSwag/OBQA (the paper's metric is apparently `acc`). With our primary `acc_norm`, 5/6 (GaMS) and 4/6 (Gemma) match. E_art2 has no random control built with its own parameters; the iter-1-parameter random edits serve as its reference.


## 1. Catastrophe gate (pre-registered: macro headroom-normalised loss > 0.20 in EN or SL)

| model | condition | EN loss (95% hi) | SL loss (95% hi) | verdict | source | raw-pp sensitivity EN / SL loss (95% hi), 5-pp rule |
|---|---|---|---|---|---|---|
| gams3_it | E_art2 | 0.020 (0.043) | 0.009 (0.038) | **OK** | full | 0.72 (1.44) OK / 0.28 (0.94) OK |
| gams3_it | E_iter1 | 0.018 (0.039) | -0.007 (0.021) | **OK** | full | 0.72 (1.39) OK / -0.11 (0.56) OK |
| gams3_it | rand_nm_j1 | 0.003 (0.019) | 0.030 (0.058) | **OK** | full | 0.06 (0.50) OK / 0.72 (1.33) OK |
| gams3_it | E_iter1_l0.5 | 0.032 (0.070) | 0.010 (0.082) | **OK** | lambda_subset | 1.00 (2.25) OK / -0.00 (1.50) OK |
| gams3_it | E_iter1_l1.5 | 0.050 (0.100) | 0.004 (0.087) | **OK** | lambda_subset | 2.00 (3.50) OK / 0.25 (2.25) OK |
| gams3_it | E_iter1_l2.0 | 0.027 (0.080) | 0.042 (0.138) | **OK** | lambda_subset | 1.25 (3.00) OK / 1.25 (3.50) OK |
| gemma_it | E_art2 | -0.016 (0.002) | -0.049 (-0.000) | **OK** | full | -0.44 (0.11) OK / -0.67 (0.11) OK |
| gemma_it | E_iter1 | -0.008 (0.009) | -0.022 (0.024) | **OK** | full | -0.28 (0.22) OK / -0.17 (0.61) OK |
| gemma_it | rand_nm_j1 | -0.009 (0.003) | -0.002 (0.045) | **OK** | full | -0.28 (0.06) OK / 0.11 (0.78) OK |
| gemma_it | rand_nm_j2 | 0.007 (0.022) | 0.008 (0.059) | **OK** | full | 0.17 (0.61) OK / 0.11 (0.78) OK |
| gemma_it | E_iter1_l0.5 | 0.000 (0.023) | -0.026 (0.104) | **OK** | lambda_subset | -0.00 (0.75) OK / -0.50 (0.75) OK |
| gemma_it | E_iter1_l1.5 | -0.013 (0.028) | -0.036 (0.116) | **OK** | lambda_subset | -0.50 (0.75) OK / -0.75 (1.50) OK |
| gemma_it | E_iter1_l2.0 | -0.013 (0.034) | 0.032 (0.327) | **POSSIBLY_CATASTROPHIC** | lambda_subset | -0.50 (1.00) OK / -0.25 (2.25) OK |
- E_art2 on gams3_it: scored (artifact 2 = iter_3/gen_art_experiment_9 selected adapter; random reference = rand_nm_j1, iter-1 parameters).
- E_art2 on gemma_it: scored (artifact 2 = iter_3/gen_art_experiment_9 selected adapter; random reference = rand_nm_j1, iter-1 parameters).

## 2. Macro H, language asymmetry A = H_SL − H_EN, interaction I = A_GaMS − A_Gemma

| model | cond | macro H EN [95% CI] | macro H SL [95% CI] | A [95% CI] | raw-pp EN | raw-pp SL | ineligible (EN/SL) |
|---|---|---|---|---|---|---|---|
| gams3_it | E_art2 | -0.020 [-0.043, 0.003] | -0.009 [-0.038, 0.022] | 0.011 [-0.023, 0.050] | -0.72 | -0.28 | – / – |
| gams3_it | E_iter1 | -0.018 [-0.039, 0.004] | 0.007 [-0.021, 0.037] | 0.025 [-0.009, 0.060] | -0.72 | 0.11 | – / – |
| gams3_it | rand_nm_j1 | -0.003 [-0.019, 0.013] | -0.030 [-0.058, -0.004] | -0.027 [-0.059, 0.005] | -0.06 | -0.72 | – / – |
| gemma_it | E_art2 | 0.016 [-0.002, 0.037] | 0.049 [0.000, 0.141] | 0.033 [-0.020, 0.125] | 0.44 | 0.67 | – / – |
| gemma_it | E_iter1 | 0.008 [-0.009, 0.025] | 0.022 [-0.024, 0.090] | 0.014 [-0.036, 0.082] | 0.28 | 0.17 | – / – |
| gemma_it | rand_nm_j1 | 0.009 [-0.003, 0.021] | 0.002 [-0.045, 0.069] | -0.007 [-0.053, 0.061] | 0.28 | -0.11 | – / – |
| gemma_it | rand_nm_j2 | -0.007 [-0.022, 0.008] | -0.008 [-0.059, 0.054] | -0.001 [-0.052, 0.061] | -0.17 | -0.11 | – / – |

| cond | I (GaMS − Gemma) | 95% CI | 90% CI |
|---|---|---|---|
| E_iter1 | 0.010 | [-0.065, 0.074] | [-0.049, 0.063] |
| E_art2 | -0.022 | [-0.116, 0.043] | [-0.099, 0.033] |
| rand_nm_j1 | -0.020 | [-0.096, 0.034] | [-0.078, 0.024] |

Resolution limit: the interaction is resolvable only to ~0.10–0.12 of headroom at n=300/task; a smaller |I| is an estimate, not evidence of no asymmetry.

### Random-adjusted (H_edit − H_rand, rand = norm-matched random edit j=1)

- gams3_it/E_art2: EN -0.016 [-0.040, 0.007]; SL 0.021 [-0.010, 0.055]; A_excess 0.038 [0.001, 0.080]
- gams3_it/E_iter1: EN -0.015 [-0.038, 0.008]; SL 0.037 [0.004, 0.072]; A_excess 0.051 [0.012, 0.093]
- gemma_it/E_art2: EN 0.008 [-0.011, 0.028]; SL 0.048 [0.002, 0.109]; A_excess 0.040 [-0.009, 0.103]
- gemma_it/E_iter1: EN -0.001 [-0.020, 0.017]; SL 0.020 [-0.024, 0.069]; A_excess 0.021 [-0.028, 0.073]

## 3. Per-task cells (E_iter1 vs original)

| model | lang | task | acc orig | acc edit | chance | H [95% CI] | raw pp | McNemar p (Holm) | eligible |
|---|---|---|---|---|---|---|---|---|---|
| gams3_it | en | arc_challenge | 0.627 | 0.590 | 0.25 | -0.097 [-0.159, -0.040] | -3.7 | 0.041 | True |
| gams3_it | en | boolq | 0.877 | 0.857 | 0.50 | -0.053 [-0.100, -0.017] | -2.0 | 0.344 | True |
| gams3_it | en | hellaswag | 0.827 | 0.830 | 0.25 | 0.006 [-0.018, 0.031] | 0.3 | 1.000 | True |
| gams3_it | en | openbookqa | 0.460 | 0.460 | 0.25 | 0.000 [-0.065, 0.071] | 0.0 | 1.000 | True |
| gams3_it | en | piqa | 0.820 | 0.823 | 0.50 | 0.010 [-0.022, 0.050] | 0.3 | 1.000 | True |
| gams3_it | en | winogrande | 0.753 | 0.760 | 0.50 | 0.026 [-0.037, 0.103] | 0.7 | 1.000 | True |
| gams3_it | sl | arc_challenge | 0.517 | 0.517 | 0.25 | 0.000 [-0.049, 0.053] | 0.0 | 1.000 | True |
| gams3_it | sl | boolq | 0.837 | 0.840 | 0.50 | 0.010 [-0.061, 0.093] | 0.3 | 1.000 | True |
| gams3_it | sl | hellaswag | 0.710 | 0.707 | 0.25 | -0.007 [-0.035, 0.015] | -0.3 | 1.000 | True |
| gams3_it | sl | openbookqa | 0.440 | 0.443 | 0.25 | 0.018 [-0.038, 0.089] | 0.3 | 1.000 | True |
| gams3_it | sl | piqa | 0.723 | 0.720 | 0.50 | -0.015 [-0.106, 0.082] | -0.3 | 1.000 | True |
| gams3_it | sl | winogrande | 0.697 | 0.703 | 0.50 | 0.034 [-0.059, 0.143] | 0.7 | 1.000 | True |
| gemma_it | en | arc_challenge | 0.600 | 0.613 | 0.25 | 0.038 [0.000, 0.088] | 1.3 | 1.000 | True |
| gemma_it | en | boolq | 0.830 | 0.833 | 0.50 | 0.010 [-0.034, 0.056] | 0.3 | 1.000 | True |
| gemma_it | en | hellaswag | 0.820 | 0.820 | 0.25 | 0.000 [-0.017, 0.018] | 0.0 | 1.000 | True |
| gemma_it | en | openbookqa | 0.500 | 0.493 | 0.25 | -0.027 [-0.069, 0.000] | -0.7 | 1.000 | True |
| gemma_it | en | piqa | 0.760 | 0.770 | 0.50 | 0.038 [0.000, 0.096] | 1.0 | 1.000 | True |
| gemma_it | en | winogrande | 0.743 | 0.740 | 0.50 | -0.014 [-0.064, 0.031] | -0.3 | 1.000 | True |
| gemma_it | sl | arc_challenge | 0.477 | 0.487 | 0.25 | 0.044 [-0.053, 0.162] | 1.0 | 1.000 | True |
| gemma_it | sl | boolq | 0.830 | 0.820 | 0.50 | -0.030 [-0.091, 0.030] | -1.0 | 1.000 | True |
| gemma_it | sl | hellaswag | 0.617 | 0.610 | 0.25 | -0.018 [-0.062, 0.023] | -0.7 | 1.000 | True |
| gemma_it | sl | openbookqa | 0.437 | 0.440 | 0.25 | 0.018 [-0.073, 0.122] | 0.3 | 1.000 | True |
| gemma_it | sl | piqa | 0.693 | 0.697 | 0.50 | 0.017 [-0.036, 0.085] | 0.3 | 1.000 | True |
| gemma_it | sl | winogrande | 0.600 | 0.610 | 0.50 | 0.100 [-0.125, 0.467] | 1.0 | 1.000 | True |

## 4. λ gate curve (100 items × ARC/BoolQ/OBQA/Winogrande)

| model | λ | macro H EN | macro H SL | verdict |
|---|---|---|---|---|
| gams3_it | 0.5 | -0.032 [-0.070, -0.001] | -0.010 [-0.082, 0.069] | OK |
| gams3_it | 1.0 | -0.045 [-0.088, -0.007] | -0.013 [-0.070, 0.048] | OK |
| gams3_it | 1.5 | -0.050 [-0.100, -0.000] | -0.004 [-0.087, 0.105] | OK |
| gams3_it | 2.0 | -0.027 [-0.080, 0.039] | -0.042 [-0.138, 0.070] | OK |
| gams3_it | largest λ OK | 2.0 | monotone SL damage: False | |
| gemma_it | 0.5 | -0.000 [-0.023, 0.024] | 0.026 [-0.104, 0.276] | OK |
| gemma_it | 1.0 | 0.005 [-0.028, 0.042] | -0.008 [-0.177, 0.184] | OK |
| gemma_it | 1.5 | 0.013 [-0.028, 0.062] | 0.036 [-0.116, 0.300] | OK |
| gemma_it | 2.0 | 0.013 [-0.034, 0.068] | -0.032 [-0.327, 0.198] | POSSIBLY_CATASTROPHIC |
| gemma_it | largest λ OK | 1.5 | monotone SL damage: False | |

## 5. Belebele (human-translated, 200 parallel items; three-language axis)

| model | cond | EN acc (H) | SL acc (H) | HU acc (H) |
|---|---|---|---|---|
| gams3_it | orig | 0.930 | 0.850 | 0.885 |
| gams3_it | E_iter1 | 0.930 (0.000 [-0.022, 0.022]) | 0.850 (0.000 [-0.025, 0.025]) | 0.885 (0.000 [-0.032, 0.033]) |
| gams3_it | rand_nm_j1 | 0.930 (0.000 [0.000, 0.000]) | 0.850 (0.000 [0.000, 0.000]) | 0.880 (-0.008 [-0.025, 0.000]) |
| gemma_it | orig | 0.940 | 0.860 | 0.820 |
| gemma_it | E_art2 | 0.930 (-0.014 [-0.037, 0.000]) | 0.845 (-0.025 [-0.056, 0.000]) | 0.815 (-0.009 [-0.028, 0.000]) |
| gemma_it | E_iter1 | 0.940 (0.000 [0.000, 0.000]) | 0.850 (-0.016 [-0.041, 0.000]) | 0.825 (0.009 [0.000, 0.029]) |
| gemma_it | rand_nm_j1 | 0.940 (0.000 [0.000, 0.000]) | 0.860 (0.000 [0.000, 0.000]) | 0.815 (-0.009 [-0.028, 0.000]) |

## 6. KL footprint (batch size 1, fp32, full vocab; fresh Dolly harmless set)

| model | cond | first-token KL EN-BT | SL-MT | HU-MT | 32-tok KL EN-BT | SL-MT | SL/EN ratio | EXCESS vs random [95% CI] | HU/EN ratio |
|---|---|---|---|---|---|---|---|---|---|
| gams3_it | E_art2 | 1.15e-01 | 6.21e-02 | 5.08e-02 | 2.87e-02 | 1.14e-02 | 0.542 | 0.490 [0.399, 0.624] | 0.443 |
| gams3_it | E_iter1 | 9.73e-02 | 5.02e-02 | 3.91e-02 | 2.44e-02 | 9.55e-03 | 0.516 | 0.466 [0.379, 0.597] | 0.401 |
| gams3_it | E_iter1_l0.5 | 3.87e-02 | 1.84e-02 | 1.50e-02 | 8.35e-03 | 3.45e-03 | 0.474 | 0.429 [0.356, 0.538] | 0.389 |
| gams3_it | E_iter1_l1.5 | 1.47e-01 | 8.32e-02 | 6.02e-02 | 4.50e-02 | 1.76e-02 | 0.566 | 0.512 [0.415, 0.654] | 0.409 |
| gams3_it | E_iter1_l2.0 | 1.86e-01 | 1.13e-01 | 7.64e-02 | 6.71e-02 | 2.70e-02 | 0.608 | 0.550 [0.445, 0.696] | 0.410 |
| gams3_it | rand_c6_j1 | 3.57e-02 | 3.03e-02 | 3.30e-02 | 2.83e-02 | 2.10e-02 | 0.847 | 0.765 [0.650, 0.904] | 0.922 |
| gams3_it | rand_nm_j1 | 1.58e-03 | 1.76e-03 | 1.74e-03 | 1.99e-03 | 1.38e-03 | – | – – | – |
| gams3_it | self | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | – | – – | – |
| gams3_it | rand_nm_avg | 1.67e-03 | 1.84e-03 | 1.83e-03 | 2.12e-03 | 1.46e-03 | 1.106 | – – | 1.096 |
| gams3_it | self-KL floor | mean 0.00e+00 | max 0.00e+00 | | | | readable: True | | |
| gemma_it | E_art2 | 3.63e-01 | 2.61e-01 | 1.42e-01 | 7.63e-02 | 2.10e-02 | 0.719 | 0.630 [0.339, 1.146] | 0.390 |
| gemma_it | E_iter1 | 3.11e-01 | 2.23e-01 | 1.20e-01 | 7.28e-02 | 1.90e-02 | 0.717 | 0.628 [0.337, 1.169] | 0.387 |
| gemma_it | E_iter1_l0.5 | 1.10e-01 | 6.71e-02 | 2.81e-02 | 2.39e-02 | 5.67e-03 | 0.609 | 0.534 [0.266, 1.044] | 0.255 |
| gemma_it | E_iter1_l1.5 | 5.25e-01 | 4.23e-01 | 2.48e-01 | 1.28e-01 | 3.96e-02 | 0.805 | 0.706 [0.390, 1.224] | 0.473 |
| gemma_it | E_iter1_l2.0 | 6.91e-01 | 6.08e-01 | 3.64e-01 | 1.80e-01 | 6.41e-02 | 0.879 | 0.771 [0.425, 1.317] | 0.527 |
| gemma_it | rand_c6_j1 | 4.52e-02 | 5.37e-02 | 6.96e-02 | 4.57e-02 | 3.82e-02 | 1.187 | 1.040 [0.606, 2.001] | 1.540 |
| gemma_it | rand_nm_j1 | 2.47e-03 | 2.32e-03 | 2.17e-03 | 1.74e-03 | 1.45e-03 | – | – – | – |
| gemma_it | self | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | – | – – | – |
| gemma_it | rand_nm_avg | 2.73e-03 | 3.12e-03 | 2.89e-03 | 1.90e-03 | 1.69e-03 | 1.141 | – – | 1.057 |
| gemma_it | self-KL floor | mean 0.00e+00 | max 0.00e+00 | | | | readable: True | | |

## 7. Bits-per-byte on human-translated FLORES passages (150/lang)

| model | lang | cond | BPB | Δ vs orig [95% CI] | rel Δ % | Δ vs random |
|---|---|---|---|---|---|---|
| gams3_it | en | E_iter1 | 0.7634 | +0.0004 [-0.0002, 0.0009] | +0.05 | 0.0000 |
| gams3_it | en | E_iter1_l2.0 | 0.7650 | +0.0020 [0.0011, 0.0029] | +0.26 | 0.0016 |
| gams3_it | en | orig | 0.7630 | +0.0000 [0.0000, 0.0000] | +0.00 | -0.0004 |
| gams3_it | en | rand_c6_j1 | 0.7709 | +0.0079 [0.0063, 0.0095] | +1.03 | 0.0075 |
| gams3_it | en | rand_nm_j1 | 0.7634 | +0.0004 [-0.0000, 0.0008] | +0.05 | – |
| gams3_it | sl | E_iter1 | 0.8904 | +0.0009 [0.0001, 0.0017] | +0.10 | 0.0009 |
| gams3_it | sl | E_iter1_l2.0 | 0.8952 | +0.0057 [0.0041, 0.0073] | +0.64 | 0.0057 |
| gams3_it | sl | orig | 0.8895 | +0.0000 [0.0000, 0.0000] | +0.00 | -0.0000 |
| gams3_it | sl | rand_c6_j1 | 0.9004 | +0.0109 [0.0091, 0.0128] | +1.23 | 0.0109 |
| gams3_it | sl | rand_nm_j1 | 0.8895 | +0.0000 [-0.0004, 0.0004] | +0.00 | – |
| gams3_it | hu | E_iter1 | 0.8994 | +0.0006 [0.0002, 0.0012] | +0.07 | 0.0002 |
| gams3_it | hu | E_iter1_l2.0 | 0.9026 | +0.0039 [0.0029, 0.0051] | +0.44 | 0.0035 |
| gams3_it | hu | orig | 0.8987 | +0.0000 [0.0000, 0.0000] | +0.00 | -0.0004 |
| gams3_it | hu | rand_c6_j1 | 0.9151 | +0.0164 [0.0143, 0.0188] | +1.82 | 0.0160 |
| gams3_it | hu | rand_nm_j1 | 0.8991 | +0.0004 [0.0000, 0.0008] | +0.05 | – |
| gemma_it | en | E_art2 | 0.8728 | +0.0003 [-0.0004, 0.0009] | +0.03 | 0.0002 |
| gemma_it | en | E_iter1 | 0.8728 | +0.0003 [-0.0003, 0.0009] | +0.03 | 0.0002 |
| gemma_it | en | E_iter1_l2.0 | 0.8736 | +0.0011 [-0.0003, 0.0024] | +0.12 | 0.0010 |
| gemma_it | en | orig | 0.8725 | +0.0000 [0.0000, 0.0000] | +0.00 | -0.0001 |
| gemma_it | en | rand_c6_j1 | 0.8735 | +0.0010 [-0.0009, 0.0029] | +0.11 | 0.0009 |
| gemma_it | en | rand_nm_j1 | 0.8726 | +0.0001 [-0.0003, 0.0005] | +0.01 | – |
| gemma_it | sl | E_art2 | 1.2000 | +0.0012 [0.0004, 0.0020] | +0.10 | -0.0005 |
| gemma_it | sl | E_iter1 | 1.2000 | +0.0011 [0.0002, 0.0020] | +0.09 | -0.0006 |
| gemma_it | sl | E_iter1_l2.0 | 1.2026 | +0.0037 [0.0019, 0.0055] | +0.31 | 0.0021 |
| gemma_it | sl | orig | 1.1988 | +0.0000 [0.0000, 0.0000] | +0.00 | -0.0017 |
| gemma_it | sl | rand_c6_j1 | 1.2153 | +0.0164 [0.0131, 0.0198] | +1.37 | 0.0148 |
| gemma_it | sl | rand_nm_j1 | 1.2005 | +0.0017 [0.0010, 0.0023] | +0.14 | – |
| gemma_it | hu | E_art2 | 1.1156 | +0.0001 [-0.0008, 0.0009] | +0.01 | -0.0005 |
| gemma_it | hu | E_iter1 | 1.1152 | -0.0003 [-0.0012, 0.0006] | -0.03 | -0.0009 |
| gemma_it | hu | E_iter1_l2.0 | 1.1170 | +0.0014 [-0.0003, 0.0031] | +0.13 | 0.0009 |
| gemma_it | hu | orig | 1.1155 | +0.0000 [0.0000, 0.0000] | +0.00 | -0.0006 |
| gemma_it | hu | rand_c6_j1 | 1.1281 | +0.0125 [0.0089, 0.0158] | +1.12 | 0.0120 |
| gemma_it | hu | rand_nm_j1 | 1.1161 | +0.0006 [-0.0001, 0.0012] | +0.05 | – |

## 8. Harmless generations (128 tokens, greedy): language consistency and degeneracy

| model | cond | arm | n | lang-consistent | S-Slavic (SL) | consistent incl. S-Slavic | degenerate |
|---|---|---|---|---|---|---|---|
| gams3_it | E_iter1 | en_bt | 100 | 0.990 | – | – | 0.000 |
| gams3_it | E_iter1 | hu_mt | 100 | 0.960 | – | – | 0.030 |
| gams3_it | E_iter1 | sl_mt | 100 | 0.990 | 0.010 | 1.000 | 0.000 |
| gams3_it | E_iter1_l2.0 | en_bt | 50 | 0.980 | – | – | 0.000 |
| gams3_it | E_iter1_l2.0 | hu_mt | 50 | 0.940 | – | – | 0.020 |
| gams3_it | E_iter1_l2.0 | sl_mt | 50 | 0.960 | 0.040 | 1.000 | 0.000 |
| gams3_it | orig | en_bt | 100 | 1.000 | – | – | 0.000 |
| gams3_it | orig | hu_mt | 100 | 0.960 | – | – | 0.020 |
| gams3_it | orig | sl_mt | 100 | 0.980 | 0.010 | 0.990 | 0.000 |
| gams3_it | rand_nm_j1 | en_bt | 100 | 1.000 | – | – | 0.000 |
| gams3_it | rand_nm_j1 | hu_mt | 100 | 0.960 | – | – | 0.020 |
| gams3_it | rand_nm_j1 | sl_mt | 100 | 0.980 | 0.010 | 0.990 | 0.000 |
| gemma_it | E_art2 | en_bt | 100 | 1.000 | – | – | 0.000 |
| gemma_it | E_art2 | hu_mt | 100 | 0.980 | – | – | 0.000 |
| gemma_it | E_art2 | sl_mt | 100 | 0.950 | 0.030 | 0.980 | 0.000 |
| gemma_it | E_iter1 | en_bt | 100 | 1.000 | – | – | 0.000 |
| gemma_it | E_iter1 | hu_mt | 100 | 0.980 | – | – | 0.000 |
| gemma_it | E_iter1 | sl_mt | 100 | 0.960 | 0.020 | 0.980 | 0.000 |
| gemma_it | E_iter1_l2.0 | en_bt | 50 | 1.000 | – | – | 0.000 |
| gemma_it | E_iter1_l2.0 | hu_mt | 50 | 1.000 | – | – | 0.000 |
| gemma_it | E_iter1_l2.0 | sl_mt | 50 | 0.960 | 0.040 | 1.000 | 0.000 |
| gemma_it | orig | en_bt | 100 | 1.000 | – | – | 0.000 |
| gemma_it | orig | hu_mt | 100 | 0.980 | – | – | 0.000 |
| gemma_it | orig | sl_mt | 100 | 0.960 | 0.020 | 0.980 | 0.000 |
| gemma_it | rand_nm_j1 | en_bt | 100 | 1.000 | – | – | 0.000 |
| gemma_it | rand_nm_j1 | hu_mt | 100 | 0.980 | – | – | 0.000 |
| gemma_it | rand_nm_j1 | sl_mt | 100 | 0.960 | 0.020 | 0.980 | 0.000 |

## 8b. Chat-template sensitivity (ARC-C + BoolQ, same 100 items, orig vs E_iter1)

| model | lang | task | H with chat template [95% CI] | H without (same items) [95% CI] |
|---|---|---|---|---|
| gams3_it | en | arc_challenge | -0.100 [-0.251, 0.037] (acc 0.550→0.520) | -0.119 [-0.230, -0.026] |
| gams3_it | en | boolq | -0.032 [-0.176, 0.120] (acc 0.810→0.800) | -0.030 [-0.108, 0.000] |
| gams3_it | sl | arc_challenge | -0.151 [-0.404, 0.056] (acc 0.450→0.420) | 0.000 [-0.101, 0.121] |
| gams3_it | sl | boolq | -0.075 [-0.225, 0.079] (acc 0.900→0.870) | 0.000 [-0.075, 0.086] |

## 8c. EXPLORATORY: are flips near-ties? (primary-metric margin between best and 2nd choice under orig)

| model | cond | flip rate | flip rate, margin < p10 | flip rate, margin ≥ median | share of flips in bottom-quartile margin | median max|Δll| |
|---|---|---|---|---|---|---|
| gams3_it | E_iter1 | 0.026 | 0.161 | 0.009 | 0.69 | 0.500 |
| gams3_it | rand_nm_j1 | 0.015 | 0.081 | 0.006 | 0.64 | 0.250 |
| gams3_it | E_art2 | 0.025 | 0.139 | 0.009 | 0.63 | 0.500 |
| gemma_it | E_iter1 | 0.021 | 0.114 | 0.007 | 0.66 | 0.500 |
| gemma_it | rand_nm_j1 | 0.014 | 0.103 | 0.001 | 0.80 | 0.312 |
| gemma_it | rand_nm_j2 | 0.015 | 0.106 | 0.001 | 0.71 | 0.375 |
| gemma_it | E_art2 | 0.024 | 0.136 | 0.009 | 0.65 | 0.562 |

## 9. Checks

- Published-anchor check (orig SL vs GaMS3 paper bf16 numbers): `{"gams3_it": {"arc_challenge": {"acc": 0.5133, "acc_norm": 0.5167, "published": 0.527, "primary_metric": "acc_norm", "diff_primary": -0.0103, "within_0.10_primary": true, "within_0.10_either_metric": true}, "boolq": {"acc": 0.8367, "acc_norm": 0.8367, "published": 0.852, "primary_metric": "acc", "diff_primary": -0.0153, "within_0.10_primary": true, "within_0.10_either_metric": true}, "hellaswag": {"acc": 0.4933, "acc_norm": 0.71, "published": 0.511, "primary_metric": "acc_norm", "diff_primary": 0.199, "within_0.10_primary": false, "within_0.10_either_metric": true}, "openbookqa": {"acc": 0.39, "acc_norm": 0.44, "published": 0.394, "primary_metric": "acc_norm", "diff_primary": 0.046, "within_0.10_primary": true, "within_0.10_either_metric": true}, "piqa": {"acc": 0.73, "acc_norm": 0.7233, "published": 0.715, "primary_metric": "acc_norm", "diff_primary": 0.0083, "within_0.10_primary": true, "within_0.10_either_metric": true}, "winogrande": {"acc": 0.6967, "acc_norm": 0.66, "published": 0.706, "primary_metric": "acc", "diff_primary": -0.0093, "within_0.10_primary": true, "within_0.10_either_metric": true}}, "gemma_it": {"arc_challenge": {"acc": 0.4733, "acc_norm": 0.4767, "published": 0.451, "primary_metric": "acc_norm", "diff_primary": 0.0257, "within_0.10_primary": true, "within_0.10_either_metric": true}, "boolq": {"acc": 0.83, "acc_norm": 0.83, "published": 0.853, "primary_metric": "acc", "diff_primary": -0.023, "within_0.10_primary": true, "within_0.10_either_metric": true}`
- Second-path scorer agreement: `{"gams3_it/orig": {"per_task": {"arc_challenge": {"n_items": 50, "median_abs_dloglik": 0.09945917129516602, "p99_abs_dloglik": 0.5035261535644534, "max_abs_dloglik": 0.6047153472900391, "argmax_agreement": 0.98}, "boolq": {"n_items": 50, "median_abs_dloglik": 0.05335116386413574, "p99_abs_dloglik": 0.20442867279052734, "max_abs_dloglik": 0.20442867279052734, "argmax_agreement": 1.0}, "hellaswag": {"n_items": 50, "median_abs_dloglik": 0.2406635284423828, "p99_abs_dloglik": 1.2451458740234365, "max_abs_dloglik": 1.6198272705078125, "argmax_agreement": 1.0}, "openbookqa": {"n_items": 50, "median_abs_dloglik": 0.08745718002319336, "p99_abs_dloglik": 0.4595909118652342, "max_abs_dloglik": 0.5496559143066406, "argmax_agreement": 0.98}, "piqa": {"n_items": 50, "median_abs_dloglik": 0.17054367065429688, "p99_abs_dloglik": 0.9538998413085944, "max_abs_dloglik": 1.0834808349609375, "argmax_agreement": 1.0}, "winogrande": {"n_items": 50, "median_abs_dloglik": 9.420665740966797, "p99_abs_dloglik": 13.105038375854502, "max_abs_dloglik": 15.054372787475586, "argmax_agreement": 0.9}}, "argmax_agreement_excl_winogrande": 0.992, "pass_argmax_ge_0.98_excl_winogrande": true, "note": "lm-eval logliks are bf16 (92% are exact multiples of 1/16); |d| of 0.1-0.6 nats is bf16 + batch-composition noise, so the plan's <0.05-nat criterion cannot hold for bf16 lm-eval output"}, "gams3_it/E_iter1": {"per_task": {"arc_challenge": {"n_items": 50, "median_abs_dloglik": 0.11003303527832031, "p99_abs_dloglik": 0.5285301971435548, "max_abs_dloglik": 0.6195240020751953, "argmax_agreement": 1.0}, "boolq": {"n_items": 50, "median_abs_dloglik": 0.0365447998046875, "p99_abs_dloglik": 0.24787631988525446, "max_abs_dloglik": 0.3542957305908203, "argmax_agreement": 1.0}, "hellaswag": {"n_items": 50, "median_abs_dloglik": 0.227569580078125, "p99_abs_dloglik": 1.1241668701171872, "max_abs_dloglik": 1.20135498046875, "argmax_agreement": 1.0}, "openbookqa": {"n_items": 50, "median_abs_dloglik": 0.09954357147216797, "p99_abs_dloglik": 0.4246086120605467, "max_abs_dloglik": 0.5844783782958984, "argmax_agreement": 1.0}, "piqa": {"n_items": 50, "median_abs_dloglik": 0.1885051727294922, "p99_abs_dloglik": 0.7831593322753907, "max_abs_dloglik": 0.7969512939453125, "argmax_agreement": 1.0}, "winogrande": {"n_items": 50, "median_abs_dloglik": 9.532119274139404, "p99_abs_dloglik": 13.762319173812871, "max_abs_dloglik": 14.753436088562012, "argmax_agreement": 0.88}}, "argmax_agreement_excl_winogrande": 1.0, "pass_argmax_ge_0.98_excl_winogrande": true, "note": "lm-eval logliks are bf16 (92% are exact multiples of 1/16); |d| of 0.1-0.6 nats is bf16 + batch-composition noise, so the plan's <0.05-nat criterion cannot hold for bf16 lm-eval output"}, "gemma_it/orig": {"per_task": {"arc_challenge": {"n_items": 50, "median_abs_dloglik": 0.21718978881835938, "p99_abs_dloglik": 1.4748104858398439, "max_abs_dloglik": 1.6144256591796875, "argmax_agreement": 1.0}, "boolq": {"n_items": 50, "median_abs_dloglik": 0.09112548828125, "p99_abs_dloglik": 0.5041575813293463, "max_abs_dloglik": 0.6121234893798828, "argmax_agreement": 1.0}, "hellaswag": {"n_items": 50, "median_abs_dloglik": 0.19107818603515625, "p99_abs_dloglik": 0.9358923339843748, "max_abs_dloglik": 1.2013397216796875, "argmax_agreement": 1.0}, "openbookqa": {"n_items": 50, "median_abs_dloglik": 0.12458562850952148, "p99_abs_dloglik": 0.5662895584106439, "max_abs_dloglik": 0.8300704956054688, "argmax_agreement": 0.98}, "piqa": {"n_items": 50, "median_abs_dloglik": 0.3175830841064453, "p99_abs_dloglik": 3.05185241699219, "max_abs_dloglik": 3.48419189453125, "argmax_agreement": 1.0}, "winogrande": {"n_items": 50, "median_abs_dloglik": 10.57775592803955, "p99_abs_dloglik": 16.66196468353272, "max_abs_dloglik": 17.5946102142334, "argmax_agreement": 0.78}}, "argmax_agreement_excl_winogrande": 0.996, "pass_argmax_ge_0.98_excl_winogrande": true, "note": "lm-eval logliks are bf16 (92% are exact multiples of 1/16); |d| of 0.1-0.6 nats is bf16 + batch-composition noise, so the plan's <0.05-nat criterion cannot hold for bf16 lm-eval output"}, "gemma_it/E_iter1": {"per_task": {"arc_challenge": {"n_items": 50, "median_abs_dloglik": 0.2039337158203125, "p99_abs_dloglik": 1.3009431457519576, "max_abs_dloglik": 1.886444091796875, "argmax_agreement": 1.0}, "boolq": {"n_items": 50, "median_abs_dloglik": 0.06416845321655273, "p99_abs_dloglik": 0.2990612792968751, "max_abs_dloglik": 0.3185558319091797, "argmax_agreement": 1.0}, "hellaswag": {"n_items": 50, "median_abs_dloglik": 0.17709732055664062, "p99_abs_dloglik": 0.8089553833007812, "max_abs_dloglik": 1.08953857421875, "argmax_agreement": 0.98}, "openbookqa": {"n_items": 50, "median_abs_dloglik": 0.13744544982910156, "p99_abs_dloglik": 0.7764497375488263, "max_abs_dloglik": 1.0070114135742188, "argmax_agreement": 1.0}, "piqa": {"n_items": 50, "median_abs_dloglik": 0.2954120635986328, "p99_abs_dloglik": 1.2267858886718754, "max_abs_dloglik": 1.324432373046875, "argmax_agreement": 0.98}, "winogrande": {"n_items": 50, "median_abs_dloglik": 10.660959243774414, "p99_abs_dloglik": 17.089043030738832, "max_abs_dloglik": 17.25288724899292, "argmax_agreement": 0.8}}, "argmax_agreement_excl_winogrande": 0.992, "pass_argmax_ge_0.98_excl_winogrande": true, "note": "lm-eval logliks are bf16 (92% are exact multiples of 1/16); |d| of 0.1-0.6 nats is bf16 + batch-composition noise, so the plan's <0.05-nat criterion cannot hold for bf16 lm-eval output"}, "gemma_it/winogrande_template_check": {"n_items": 100, "median_abs_d_double_space": 0.09200859069824219, "median_abs_d_single_space": 11.038915634155273, "argmax_agreement_double_space": 0.98, "explains_offset": true}}`
- Manipulation check gams3_it: all_pass=True; E_iter1 KL 0.2272 vs iter-1 pick 0.2330
- Pilot gams3_it: batch-vs-single max |Δloglik| = 0.213 nats, pair argmax agreement 16/16, BOS first=True doubled=False
- Manipulation check gemma_it: all_pass=False; E_iter1 KL 0.5101 vs iter-1 pick 0.3656
- Pilot gemma_it: batch-vs-single max |Δloglik| = 0.807 nats, pair argmax agreement 16/16, BOS first=True doubled=False
- Audit (path B): 346 recomputation checks, 0 failed; placebos centred: True
  - placebo cond_swap H gams3_it/E_iter1/en: observed -0.0180, permutation mean -0.0001 (sd 0.0107), p=0.093
  - placebo cond_swap H gams3_it/E_iter1/sl: observed 0.0065, permutation mean 0.0010 (sd 0.0147), p=0.668
  - placebo cond_swap H gemma_it/E_iter1/en: observed 0.0077, permutation mean 0.0001 (sd 0.0079), p=0.346
  - placebo cond_swap H gemma_it/E_iter1/sl: observed 0.0218, permutation mean 0.0014 (sd 0.0231), p=0.335
  - placebo lang_swap A gams3_it/E_iter1: observed 0.0245, permutation mean -0.0001 (sd 0.0165), p=0.140
  - placebo lang_swap A gemma_it/E_iter1: observed 0.0141, permutation mean 0.0003 (sd 0.0201), p=0.499
  - placebo model_swap I E_iter1: observed 0.0104, permutation mean 0.0007 (sd 0.0293), p=0.746
  - placebo cond_swap H gams3_it/E_art2/en: observed -0.0199, permutation mean 0.0004 (sd 0.0113), p=0.075
  - placebo cond_swap H gams3_it/E_art2/sl: observed -0.0088, permutation mean 0.0011 (sd 0.0160), p=0.577
  - placebo cond_swap H gemma_it/E_art2/en: observed 0.0163, permutation mean 0.0000 (sd 0.0095), p=0.085
  - placebo cond_swap H gemma_it/E_art2/sl: observed 0.0491, permutation mean 0.0018 (sd 0.0238), p=0.030
  - placebo lang_swap A gams3_it/E_art2: observed 0.0110, permutation mean -0.0006 (sd 0.0177), p=0.520
  - placebo lang_swap A gemma_it/E_art2: observed 0.0327, permutation mean 0.0001 (sd 0.0206), p=0.113
  - placebo model_swap I E_art2: observed -0.0217, permutation mean 0.0003 (sd 0.0306), p=0.465

## 10. Cuts / deviations (logged)

- 2026-09-24T06:50Z [cut 5-partial] harmless generations reduced 200 -> 100 prompts per arm (EN-BT/SL-MT/HU-MT) for orig/E_iter1/rand_nm_j1, lambda-variant generations only for lambda=2.0 at 50 prompts per arm; trigger: pilot 0.17 s/item -> projected GaMS block ~115 min vs ~100 min budget per model (6 h total, 2 models).
- 2026-09-24T07:00Z [reorder, not a cut] GaMS block restarted at the util/orig boundary (resumable) with a later deadline and stage order util,kl,gen,belebele,bpb,scorer2,chat so the never-cut items (gate, random KL control) and the fluency gates run before the optional ones. util batch size kept at 8 for EVERY condition (a brief bs=16 restart was killed before writing any file: NF4 batch composition shifts logliks by up to 0.21 nats, so batch size must be identical across conditions).
- GSM8K 5-shot (optional STEP 7) not run: projected time after both model blocks < 45 min (cut 1).
- 2026-09-24T08:40Z [E_art2] artifact 2's selections (iter_3/gen_art_experiment_9/selected/{gams3_it,gemma_it}/adapter, written 06:58Z) appeared AFTER the GaMS build (06:33Z) and BEFORE the Gemma build: Gemma scores E_art2 inside its block; GaMS scores E_art2 utility + KL in a late pass (resume path, same protocol). E_art2's OWN norm-matched random controls (Heretic abliterate with art2 params) were NOT built (time); the iter-1-parameter random edits rand_nm_j1..5 serve as the random reference for E_art2 (same Heretic machinery, KL ~0.002-0.004 for both parameter sets' magnitude class). Stated as a limitation.
- 2026-09-24T08:40Z [noise floor addition] a second random seed (rand_nm_j2) was added to the Gemma utility conditions (and queued last for GaMS) after GaMS showed the seed-1 random edit moving SL macro H by -0.030 (CI excluding 0): with one random draw the utility noise floor is unknown.
- 2026-09-24T09:00Z [bug fix, pre-analysis] headroom eligibility uses >= 0.10 with a 1e-9 float tolerance (0.60-0.50 evaluated to 0.0999...; the pre-registered rule is inclusive).
- [template deviation, all conditions and both models identical] Winogrande continuations were stored with a leading space and lm-eval prepends its target delimiter, so every lm-eval Winogrande continuation starts with a double space. Within-task deltas are unaffected (identical across conditions); absolute Winogrande accuracies are not harness-default. Verified on Gemma by scorer2wino (100 items): with the double space the second path matches lm-eval (median |d| 0.09 nats, argmax 98%) vs median |d| 11.0 nats with a single space.
- [precision] lm-eval 0.4.13 computes log_softmax in the model dtype (bf16): 92% of logged logliks are exact multiples of 1/16, so per-item loglik differences below ~0.1-0.5 nats are quantisation noise; the second-path scorer (fp32 softmax, bs 1) agrees in argmax on 99.2% of non-Winogrande items (GaMS). The plan's <0.05-nat agreement criterion is not attainable for bf16 harness output and is reported as failed-by-design.
- 2026-09-24T10:30Z [deadline cuts] Gemma main block hit its deadline before scorer2 and chat. scorer2 and the remaining BPB rows ran in the resume pass; the Gemma chat-template sensitivity was NOT run (cut 2), so it is GaMS-only and exploratory. GaMS rand_nm_j2 utility (second random seed) was queued last and skipped for time: the utility noise floor has 2 seeds for Gemma and 1 for GaMS.
- 2026-09-24T10:55Z [diagnostics added] Gemma manipulation-check gap: (1) batched left-padded KL (bs 100/16) vs bs 1; (2) empty-system-turn rendering. Both are diagnostics only; no edit or verdict was changed.
