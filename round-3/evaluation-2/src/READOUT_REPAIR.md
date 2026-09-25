# READOUT_REPAIR — every iter-1/2 number mapped to its validated replacement

**SCREEN REPAIR (MODE L).** exp8 saved 24,000 responses; this artifact re-judges them with local open-weight judges (primary **q14**) and a blind author-model adjudication (NOT human), because the shared OpenRouter budget is exhausted. Sign convention: G3 = (GaMS − Gemma) Slovene refusal log-odds at matched English refusal; **negative = de-censoring strips GaMS's Slovene refusal faster than Gemma's** (the original claim).

**C-LAG screen holds under validated judges: False.** Rule: B negative with CI95 excluding 0 under both local families, both codings, and after RG correction (statistic: G3_50 if on support, else the integrated gap IG)
Conditions: primary_R=True, primary_RP=False, secondary_R=True, secondary_RP=False, primary_R_RG=True, primary_RP_RG=False

| iter-1/2 quantity | old value | old readout | validated replacement | status | source |
|---|---|---|---|---|---|
| exp8 G3 curve B (lexicon) | -2.36 [-3.18, -1.62] | lexicon (kappa~0.34 vs gemini on Gemma-EN) | -1.95 [-3.75, -0.78] [q14, IG (integrated gap; B support rule failed, G3@50% extrapolated)]; RG-corrected -5.10 [-11.17, +5.60] | SURVIVES (sign holds, CI excludes 0) | iter_2/.../gen_art_experiment_8/results/analysis.json G3.B |
| exp8 G3 curve A1 (lexicon) | -0.19 [-1.03, 0.78] | lexicon | -0.47 [-1.86, +0.26] [q14, IG (integrated gap; B support rule failed, G3@50% extrapolated)] | SHRINKS/INCONCLUSIVE (CI now includes 0) | exp8 analysis.json G3.A1 |
| exp8 'Llama judge' cross-model readout | substitute local judge (Llama-3.1-8B, kappa 0.52 vs gemini) | Llama-8B on both models | replaced by q14 (calib kappa vs gemini 0.3577968806877048); Llama-8B B G3 = -1.44 [-2.41, -0.79] | SUPERSEDED | exp8 analysis.json primary_readout |
| exp8 gemini Gemma-only SL-minus-EN pp at EN50 (B) | +35.5 pp | gemini (Gemma rows only; GaMS never judged) | per-model lag now computed for BOTH models; see results eval_results.json step3_lag | CONTEXTUALISED | exp8 analysis.json gemma_judge_only.B.SL_minus_EN_pp_at_EN50 |
| exp8 gemini Gemma-only pp at EN50 (A1) | +40.2 pp | gemini (Gemma only) | see step3_lag per-model | CONTEXTUALISED | exp8 analysis.json gemma_judge_only.A1 |
| iter-1 screen lexicon G3 | -1.86 | iter-1 lexicon | -1.95 [-3.75, -0.78] (q14) | SURVIVES (sign holds, CI excludes 0) | hypothesis text / iter-1 |
| exp5 HARD DiD_c (criterion shift) | +0.52 [0.38, 0.68] | Qwen3-14B (exp5 FINAL) | reproduced in STEP 6 S1 under Qwen3-14B: +0.52 [+0.39, +0.67] | REPLICATED (confirmatory, reported separately) | exp5 analysis_final.json C2_hard_sdt.DiD_c |
| exp7 Gemma safe-SL over-refusal | +0.24 | Mistral-24B (exp7) | STEP 6 S2 DiD_c (gemini) +0.52 [+0.29, +0.79] | RELATED (criterion-shift meta S2) | exp7 analysis.json |

## Reading
- The exp8 lexicon B value (−2.36) and A1 value (−0.19) are **reproduced exactly** by the imported estimator (unit test `exp8_lexicon_B_reproduced`), so any change below is the readout, not the code.
- Primary judge selection: only q14 has full B+A1 coverage (MODE L, one GPU); calib-vs-gemini kappa winner=q14 is reported but gemini itself has a documented SL->REFUSE bias, so calib-vs-gemini is a judge-comparison diagnostic, not a truth reference; the blind adjudication is the truth reference for corrections
- On the 240 blind-adjudicated EDITED rows, **all** instruments (gemini, local judges, lexicon) agree only weakly with careful adjudication, and the errors are model- and language-dependent — see `judge_error_matrices.json` and `results/eval_results.json step2_characterise`. This is why the corrected estimate carries wide uncertainty and why the lexicon headline cannot be taken at face value.
- The bias tipping point (`step5_tipping`) states how much extra false-REFUSE in Gemma-SL (or false-COMPLY in GaMS-SL) would be needed to move the lag to −m or to 0, compared with the measured differential bias.
- Full numbers: `results/eval_results.json`; figures in `figures/`; independent re-derivation in `work/rederive.json`.