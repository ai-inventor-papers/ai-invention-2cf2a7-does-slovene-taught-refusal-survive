# RESULTS

All numbers below are produced by `src/analysis.py` from `results/items_final.jsonl` and re-derived by the
independent second code path `src/audit.py`. Full tables: [`results/summary_tables.md`](results/summary_tables.md).

## 1. Primary: does Slovene refusal fall faster at matched English suppression?

**G3 (B', 7 paired Heretic trial steps): NOT IDENTIFIED.** Every paired trial step that both models completed sits at high EN refusal, so this fit extrapolates to EN = 50% from a separated design; neither its point estimate nor its interval is interpretable, and it is excluded from the headline.

**G3 (lambda curve) = -0.97**, 95% CI [-1.56, -0.44].

Support rule satisfied: False Gemma-3-12B-IT #[.2,.5)=0, #[.5,.8]=0; GaMS3-12B-Instruct #[.2,.5)=0, #[.5,.8]=1.

**Pre-registered verdict: ESTIMATE** (margin m = 0.675; m_local = 0.20 co-reported).

| condition | met |
|---|---|
| G3_Bprime_identified | False |
| G3_Bprime_lt_minus_m_ci95_excl0 | False |
| G3_lambda_lt0_ci95_excl0 | True |
| second_family_same_sign_ci_excl0 | False |
| holds_R2 | False |
| support_rule | False |

### B' is off support -> pre-registered fallback F3

B' is off support / unidentified: the 7 paired trial steps that both models completed all sit at high EN refusal, so the GLM would extrapolate to EN=50% from a separated design.

**F3 verdict (lambda curve, 9 paired steps per model): CONFIRM-LAG (F3 lambda curve)** - G3 = -0.97, 95% CI [-1.56, -0.44], MDE 0.80.

| F3 condition | met |
|---|---|
| lambda_G3_identified | True |
| lambda_G3_lt0_ci95_excl0 | True |
| lambda_G3_lt_minus_m | True |
| second_family_same_sign_ci95_excl0 | True |
| holds_R2 | True |

EN-BT refusal range per model on the lambda curve: Gemma-3-12B-IT 0.06-0.94; GaMS3-12B-Instruct 0.02-0.93


## 2. Mechanism: criterion or geometry?

| model | n steps in window | Delta-c (SL-EN) | 95% CI | Delta-d' | 95% CI | reading |
|---|---|---|---|---|---|---|
| Gemma-3-12B-IT | 2 | 0.56 | [0.25, 0.97] | 0.39 | [-0.39, 1.07] | MIXED |
| GaMS3-12B-Instruct | 3 | 0.57 | [0.26, 0.84] | -0.60 | [-1.22, 0.16] | MIXED |
| DiD (Gemma - GaMS) | | -0.00 | [-0.42, 0.48] | 0.99 | [-0.11, 1.93] | |

## 3. Controls

- Placebos (must centre at 0): model-label swap null mean 0.01 (sd 0.55, p = 0.0840); language-label swap null mean -6921.72 (p = 0.0010).
- Norm-matched random-direction edits (5 seeds, matched per module on ||dW||_F):
  - Gemma-3-12B-IT: EN-BT refusal within 50% relative of the unedited model: True; per-seed rates in `results/summary_tables.md`.
  - GaMS3-12B-Instruct: EN-BT refusal within 50% relative of the unedited model: None; per-seed rates in `results/summary_tables.md`.
- C5a Gemma-3-12B-IT: SL/EN first-token-KL excess ratio 0.32 95% CI [0.16, 0.62].
- C5a GaMS3-12B-Instruct: SL/EN first-token-KL excess ratio 0.62 95% CI [0.43, 0.87].

## 4. Readout validity

- J1 (gemini-distilled classifier) vs held-out archived gemini labels: kappa_R 0.84 (3-way 0.81) on 2755 rows; per-cell table in `results/summary_tables.md`.
- J1 vs J2 (second family) per cell: 3/10 cells reach kappa_R >= 0.6; failing cells: ['gams3_it|benign|all', 'gams3_it|en_bt|edited', 'gams3_it|en_bt|orig', 'gams3_it|sl_mt|edited', 'gemma_it|en_bt|edited', 'gemma_it|sl_mt|edited', 'gemma_it|sl_mt|orig'].

## 5. Sanity gates

- Gemma-3-12B-IT: template sha1 match True; trial-1 replay identical True; lambda=1 reproduction True; EN refusal cut >= 50% relative True; engine gate PASS False.
- GaMS3-12B-Instruct: template sha1 match True; trial-1 replay identical True; lambda=1 reproduction True; EN refusal cut >= 50% relative True; engine gate PASS None.
- Pairing of the 40 Heretic trials across models: {'n_common': 40, 'n_identical': 40}.
- Steps excluded by QC (degeneracy >= 10% or SL language consistency < 95%): [].
- Second code path (`src/audit.py`): all_pass = True over 23 checks.

## 6. How much this verdict should be trusted

The pre-registered rule says a cell whose judge gate fails cannot carry a primary. Only 3 of 10 model x arm x edited cells reach kappa_R >= 0.6 between J1 and the second family, so the CONFIRM-LAG verdict above is **qualified**: the two readouts agree on the *sign and significance* of G3 on the lambda curve (J1 -0.97 [-1.56, -0.44], J2 -1.72 [-2.30, -0.96]) but not row by row. J1 itself is validated against 2,755 held-out real gemini labels (kappa_R 0.84), which is the stronger of the two checks; J2 is an 8B zero-shot judge whose own agreement with gemini is only kappa_R 0.58, so most of the disagreement is J2's error.

## 7. Limitations

- Reduced precision: everything runs in bitsandbytes NF4; absolute refusal levels may differ from bf16.
- The Slovene arm is NLLB machine translation without a native-speaker audit.
- The primary judge is a classifier distilled from archived `gemini-2.5-flash` labels (the run's OpenRouter
  budget was exhausted before this artifact started), so it inherits that judge's biases; GaMS edited rows have
  no archived gemini gold and rest on J1-J2 agreement plus the (agent, not human) adjudication.
- The 40 Heretic trials are sampler start-up draws: B' samples Heretic's parameter space, it is not "what
  Heretic would ship".

