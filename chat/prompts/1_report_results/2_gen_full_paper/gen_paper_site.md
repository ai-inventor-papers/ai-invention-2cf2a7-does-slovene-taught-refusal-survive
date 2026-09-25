# gen_paper_site — report_results

> Phase: `gen_paper_repo` · `gen_full_paper`
> Run: `gen_paper_repo_8de3f5a10f38` — Over-Refusal of Benign Slovene Prompts Survives English De-censoring in Gemma-3-12B
>
> Full, verbatim record of every prompt the AI Inventor pipeline gave this agent — system-user, human-user and skill-input — in the order they landed. Nothing truncated.

## Task: `gen_paper_site` (terminal_claude_agent)

### [1] SYSTEM-USER prompt · 2026-09-25 15:36:33 UTC

````
o far (iterations 1-3)

  **[Correction (iter 4, MUST-FIX #1): The C-LAG paragraph below is rewritten. Each artifact's pre-registered verdict is given verbatim. exp8, eval2, and exp10 share items and are counted as one dataset.]**

  **[Correction (iter 4, MUST-FIX #3): The criterion-shift claim is restricted to 'original models, HARD set'. On edited models and on benign content-matched twins, the model difference is not in c.]**

  **[Correction (iter 4, MUST-FIX #13): Each positive claim is compared with its nearest published neighbour.]**

  Three iterations screened the main claim (behaviour-level reach) and four alternates against SCORE data (iteration 1), the reserved FINAL evaluation split (iteration 2), and fresh data with mechanism tests and utility controls (iteration 3). Two alternates are dead (base-checkpoint geometry and persona gating). A third (prefill-depth signature, alternate 4) is uncitable because no available readout can validly score prefill continuations. Two mechanistic hypotheses were tested: the geometry hypothesis (Slovene refusal occupies a separate direction) is layer-dependent -- nearly collinear at own-L* (cos = 0.986-0.991) but divergent at a common layer (perp share 0.31 vs 0.38). The induction hypothesis (the Slovene-perpendicular component induces refusal) is not supported: u_SLperp never reached alpha50 in any cell. The teacher-inheritance screen found that GaMS3's refusal *decisions* do not detectably inherit from the Qwen teacher, while its refusal *wording* inherits almost entirely (76% of English and 91% of Slovene first sentences are verbatim from the SFT data).

  The primary contest between behaviour-level reach and supervised reach remains unresolved. The dose contrast is underpowered across all three iterations. The overall GaMS3 Slovene deficit (DiD) is judge-dependent; the meta-analytic estimate is -0.50 [-0.82, -0.21]. On original models and the HARD set, the signal-detection decomposition is robust: the DiD in d' (discrimination) is near zero (-0.003), while the DiD in criterion c is +0.52 [0.39, 0.67], driven by Gemma over-refusing benign Slovene prompts. This criterion shift replicates across experiments, judge families, and item sets on original models. However, on edited models (exp11 HARD post-edit), DiD_c = 0.14 [-0.78, 1.12]: the criterion-shift difference disappears after the edit. On the exp9 lambda curve, the model difference in the lag window sits in discrimination (DiD_d' = +0.99 [-0.11, 1.93]), not criterion (DiD_c = -0.00 [-0.42, 0.48]). The criterion-shift finding is therefore specific to the original-model HARD setting. Aziz et al. [7] showed calibration-not-representation across 23 languages; our sibling-pair design adds GaMS3-specific detail but does not change the interpretation.

  The cross-lingual abliteration lag (C-LAG) has a consistent negative sign but is not confirmed by pre-registered criteria. Each artifact's pre-registered verdict: exp9 verdict = ESTIMATE (support_rule False, second-family and R2 conditions False; model-swap permutation p = 0.084; 7 of 10 J1-J2 cells fail validation on GaMS edited rows); eval2 verdict = 'C-LAG screen holds under validated judges: False' and 'INCONCLUSIVE/weak-LAG, not a clean LAG'; exp11 verdict = ESTIMATE ('NOT reproduced on reserved data'). Exp8, eval2, and exp10 share the same item set (exp8's SCREEN P200 TEST160), so there are two independent datasets (exp8/eval2/exp10 on P200; exp9 on 300-item RefusEU-TRAIN; exp11 on FINAL), not three. The magnitude ranges from -0.6 to -2.4 across designs and judges, with the uncertainty driven by weak judge agreement on edited text (best kappa = 0.43, gemini) and the GaMS-SL false-COMPLY tipping path. Wang et al. [2] showed full-dose English-direction transfer across 14 languages; our contribution is the partial-dose sibling-pair design, but the lag does not yet meet confirmation criteria.

  The u_lang exploratory finding (the language-identity direction induces Slovene refusal, alpha50 = 0.65 in Gemma, 2.96 in GaMS3) is close to Upadhyaya and Sikdar [11], who showed safety features geometrically entangled with language identity and that ablating safety features shifts output language. Our delta is the matched sibling pair and the dose dimension, but u_lang failed the manipulation check in Gemma. The RQ4 AUROC = 1.00 finding (harmfulness decodable while refusal collapses) replicates Aziz et al. [7], who showed the same pattern across 23 languages; it is not a new finding from this study, and the ceiling likely reflects dataset-source separability rather than refusal readability (Balani and Panda show AUROC drops from >0.98 to 0.59-0.69 on matched-source negatives). The Hungarian ESTIMATE (-0.46 [-2.21, 1.44]) and Slovene two-point null (+0.05 [-1.49, 2.02]) are both uninformative; neither supports nor refutes a GaMS-specific account. On FINAL, the model difference in SL-vs-EN refusal is largely baseline (gams:sl = -1.73, p = 3e-5), not edit-induced.

  The utility control (experiment 12) established that the English-only abliteration edit does not damage Slovene downstream skills more than English ones. All macro headroom-normalised losses are below 0.05. The language asymmetry is positive in every cell (Slovene hurt less), and the random-adjusted excess asymmetry excludes zero for GaMS3 (excess = +0.051 [+0.012, +0.093]). Localised costs include GaMS3's English ARC-Challenge (3.7 pp, p = 0.041) and BoolQ (-2.0/-2.3 pp), both replicating across two edits. The excess Slovene KL divergence ratio is below 1 in both models across all iterations. Fluency (bits-per-byte) and Belebele comprehension are essentially unaffected (the exp11 4.5 pp Hungarian drop is not replicated in exp12).

  The identity calibration arm continues to replicate (FINAL identity DiD = 3.46 [2.55, 4.62]). GaMS3 credits Qwen or Alibaba in roughly half of its English identity answers.

  Open items at the end of iteration 3: the dose contrast remains underpowered. The lag magnitude is uncertain by a factor of two or more because no judge exceeds kappa 0.43 on edited text. The frozen-core Heretic procedure (bf16, 80 trials, Heretic's selection rule) has never been run. No artifact has scored natural RefusEU FINAL prompts under the edit. All adjudication is author-LLM, not human. The next iteration's budget belongs on validated labels and a lambda grid that covers EN 50%.

  ## References

  [1] A. Arditi, O. Obeso, A. Syed, D. Paleka, N. Rimsky, W. Gurnee, N. Nanda. "Refusal in Language Models Is Mediated by a Single Direction." NeurIPS 2024.

  [2] X. Wang, M. Wang, Y. Liu, H. Schutze, B. Plank. "Refusal Direction is Universal Across Safety-Aligned Languages." NeurIPS 2025.

  [3] H. Du, W. Li, M. Cai, K. Saraipour, Z. Zhang, H. Lakkaraju, Y. Sun, S. Zhang. "How Post-Training Reshapes LLMs: A Mechanistic View on Knowledge, Truthfulness, Refusal, and Confidence." arXiv 2504.02904, 2025.

  [4] U. Shaham, J. Herzig, R. Aharoni, I. Szpektor, R. Tsarfaty, M. Eyal. "Multilingual Instruction Tuning With Just a Pinch of Multilinguality." Findings ACL 2024.

  [5] F. Joad, M. Hawasly, S. Boughorbel, N. Durrani, H. Sencar. "There Is More to Refusal in Large Language Models than a Single Direction." arXiv 2602.02132, 2026.

  [6] V. Zhong, Q. Li. "Refusal Lives Downstream of Persona in Chat Models." ICML 2026 MI Workshop.

  [7] R. Aziz, I. A. Hanif, F. Koto. "Low-Resource Safety Failures Are Action Failures, Not Representation Failures." arXiv 2606.01196, 2026.

  [8] A. Krasnodebska, W. Kusa, A. Lipani. "Multilingual Refusal Alignment for Safer Large Language Models." Findings ACL 2026.

  [9] W. Hawkins et al. "The Heterogeneous Safety Impacts of Benign Multilingual Fine-Tuning." arXiv 2606.28843, 2026.

  [10] X. Li, Z.-X. Yong, S. H. Bach. "Preference Tuning For Toxicity Mitigation Generalizes Across Languages." EMNLP 2024.

  [11] A. Upadhyaya, S. Sikdar. "When Safety Speaks a Language: A Mechanistic Analysis of Safety-Language Identity Entanglement in LLMs." 2026.

  [12] S.-Y. Miao et al. "Who Bridges Safety? Identifying and Targeting Cross-Lingual Shared Safety Pathways." 2026.

  [13] A. Oppong et al. "The Illusion of Cross-Lingual Safety in Low-Resource Languages." 2026.

  [14] C. Kissane, R. Krzyzanowski, A. Conmy, N. Nanda. "Base LLMs Refuse Too." Alignment Forum, 2024.

  [15] L. Chua et al. "Crosslingual Capabilities and Knowledge Barriers in Multilingual Large Language Models." arXiv 2406.16135, 2024.

  [16] X. He et al. "TUBA: Cross-Lingual Transferability of Backdoor Attacks in LLMs with Instruction Tuning." Findings ACL 2025.

  [17] Y. Wu, L. Ding, L. Shen, D. Tao. "Edit Once, Update Everywhere: A Simple Framework for Cross-Lingual Knowledge Synchronization in LLMs." Findings ACL 2025.

  [18] G. Messenger. "Detecting Safety Training Modification in Language Models via Activation Analysis." IEEE Access, 2026.

  [19] A. Labunets. "Refusal geometry reflects refusal training: diverse refusal prefixes can raise stable rank and weaken refusal vector ablation attacks." 2026.

  [20] D. Vres, T. Arcon, T. Petric, D. Vajda, M. Robnik-Sikonja, I. L. Bajec. "Building a Strong Instruction Language Model for a Less-Resourced Language." arXiv 2603.01691, 2026.

  [21] R. Young. "Comparative Analysis of LLM Abliteration Methods: A Cross-Architecture Evaluation." arXiv 2512.13655, 2025.

  [22] A. Fafula. "Abliteration Is Not a Scalpel: Off-Target Effects of Refusal Removal on Decision Disposition Across Model Families." arXiv 2607.17427, 2026.

  [23] N. Truong. "Abliteration Mitigation via Refusal Aliases." arXiv 2608.18093, 2026.

  [24] P. E. Weidmann. "Heretic: Fully Automatic Censorship Removal for Language Models." GitHub, 2025. Commit 3521f86.

  # Iteration 4

  ## Strategy

  Three problems guided this iteration, following the reviewer's directive that the budget must go to the readout and a new confirmation rather than more probes.

  First, the C-LAG sign was consistent but no artifact's pre-registered verdict reached CONFIRM. The main blocker was the edited-row readout: every judge had kappa at most 0.43, and the GaMS-SL false-COMPLY tipping path reached measured error CIs. Iteration 4 addressed this with a paid-judge readout completion (evaluation 3) that applied gemini-2.5-flash and gpt-4.1-mini to all saved edited responses, added translate-then-judge and Rogan-Gladen correction [25], and pooled across item bodies.

  Second, the mechanism question shifted. The iter-2 hypothesis update replaced the comprehension-competence framing with two testable accounts: M-OUT (production-side, predicting the lag follows the output language) and M-IN (input-side caution, predicting the lag follows the input language). Experiment 14 tested these with a 2x3x3 design crossing input language (EN, SL, HU) with forced output language (EN, SL, HU) at three abliteration doses.

  Third, the lag estimate's uncertainty was partly driven by sparse lambda coverage near EN 50%. Experiment 15 addressed this with a fine-grained lambda ladder (13 steps for Gemma, 15 for GaMS) on a fresh 300-item RefusEU-TRAIN body disjoint from all prior probes.

  A fifth slot (research, art_NZ9n2Ej5RtGt) conducted a dated prior-art and fact-check, cataloguing nearest neighbours for each positive claim and verifying the M-OUT/M-IN design's novelty.

  The OpenRouter shared key was available for this iteration. All paid judge calls used gemini-2.5-flash and gpt-4.1-mini.

  Five artifact slots were planned. Slot 2 failed; the other four completed:

  1. Evaluation 3 (readout completion): paid-judge re-scoring of all saved edited and original rows from experiments 8, 9, 11 and the experiment 10 add-on, with translate-then-judge, adjudication, and Rogan-Gladen [25] / PPI++ [26] corrected cross-model lag pooled across item bodies.
  2. Experiment 13 (held-out confirmation, **FAILED**): a newly selected Heretic edit, a DEV-calibrated lambda grid bracketing English refusal of 50%, a confirmation curve on a new external 300-item harmful body, random-direction controls, and the frozen-core RQ2 natural RefusEU pairs under the edit. The container lost its GPU about 25 minutes into the run, so none of this was generated. The paid-judge substitute re-readout of archived curves was frozen but never labelled. See "Not executed or abandoned in iteration 4" below.
  3. Experiment 14 (mechanism 2x3x3): input language x output language x dose, with three models (Gemma, GaMS3, public p-e-w/heretic checkpoint), testing M-OUT vs M-IN.
  4. Experiment 15 (fine-grained lambda ladder): 13/15-step lambda curve on fresh 300-item body with random-direction controls, MT-noise check, and first-token KL collateral.
  5. Research artifact: prior-art search and fact verification.

  Because slot 2 failed, iteration 4 has **no held-out confirmation and no RQ2 result**. Every iteration-4 number below comes from re-readouts of saved rows (evaluation 3), a screen (experiment 14) or a denser curve on a fresh body (experiment 15).

  ## Artifact 15: Readout completion with paid judge (Evaluation 3)

  \footnote{Code: \url{https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-4/evaluation-3}}

  This evaluation applied the pre-registered paid readout to all saved edited and original rows from experiments 8, 9, 11 and the experiment 10 add-on block. The primary judge was gemini-2.5-flash (thinking off, primary scoring prompt). The second judge was gpt-4.1-mini on a stratified subset. Translate-then-judge (TTJ) applied NLLB SL-to-EN translation before judging, giving a language-neutral readout. Blind adjudication used two Claude-family adjudicators (claude-sonnet-4.5 for 285 rows, the executing agent for 195 rows; 40-row overlap, inter-adjudicator kappa 0.69).

  ### Readout gate: FAILS

  The pre-registered gate required per-cell Se >= 0.80 AND Sp >= 0.80 in both decisive cells (GaMS-SL-edited and Gemma-SL-edited), and kappa(gemini, gpt-4.1-mini) >= 0.60. Both decisive cells fail:

  **Table 25. Readout gate (gemini-2.5-flash vs adjudication).**

  | Cell | Se [95% CI] | Sp [95% CI] | kappa gemini-gpt | Pass |
  |-|-|-|-|-|
  | GaMS-SL-edited | 0.91 [0.74, 0.97] | 0.73 [0.61, 0.83] | 0.39 | False |
  | Gemma-SL-edited | 0.99 [0.87, 1.00] | 0.66 [0.43, 0.83] | 0.72 | False |

  The paid judge has high sensitivity but specificity of 0.66-0.73 on edited Slovene rows (it over-calls REFUSE), below the pre-registered 0.80 floor. No readout tier passed the bake-off. All numbers below are estimates with their CIs, not primary verdicts.

  ### Pooled cross-model lag: sign confirmed, edit-induced component is zero

  Pooling over three item bodies (experiment 9 lambda curve, experiment 11 reserved split, experiment 8 body A) using REML with the modified Hartung-Knapp-Sidik-Jonkman correction. We define the cross-model lag G3 as the GaMS-minus-Gemma difference in predicted Slovene refusal log-odds at matched English refusal of 50%; G3_orig is the pre-edit baseline component and G3_edit is the edit-induced component (G3 = G3_orig + G3_edit):

  **Table 26. Pooled lag estimates (REML + HKSJ, k = 3 item bodies, R coding).**

  | Readout | G3 [95% CI] | G3_edit [95% CI] | IG [95% CI] | I-squared |
  |-|-|-|-|-|
  | Raw primary (gemini) | -1.17 [-1.84, -0.50] | 0.39 [-1.95, 2.74] | -1.15 [-1.31, -0.99] | 0.22 |
  | RG (unstable) | -1.79 [-7.17, 3.58] | n/a | -2.02 [-5.40, 1.35] | 0.00 |
  | PPI | -1.77 [-1.89, -1.65] | 0.20 [-0.72, 1.11] | -2.00 [-3.19, -0.82] | 0.00 |
  | TTJ | -1.10 [-4.67, 2.47] | 0.33 [-6.52, 7.18] | -1.40 [-2.46, -0.33] | 0.59 |

  The pooled lag is negative under every readout. The edit-induced component is centred near zero in every readout. Subtracting each model's own pre-edit language gap, the lag is entirely explained by the baseline offset: GaMS3 starts with less Slovene refusal than Gemma before any de-censoring. **R-BASE (baseline offset) is the best-supported account.**

  ### Per-curve headlines

  The per-curve table shows the raw primary lag, pre-edit baseline, and edit-induced component for each curve:

  **Table 27. Per-curve G3 decomposition (raw primary readout, R coding).**

  | Curve | G3 [95% CI] | G3_orig [95% CI] | G3_edit [95% CI] | On support | Verdict |
  |-|-|-|-|-|-|
  | exp9 lambda | -1.12 [-1.70, -0.63] | -2.56 [-4.07, -1.32] | 1.43 [0.29, 2.98] | False | ESTIMATE |
  | exp11 FINAL | -1.00 [-1.40, -0.68] | -1.11 [-2.74, -0.21] | 0.10 [-0.85, 1.71] | True | CONFIRM-LAG |
  | exp8 A1 | -1.54 [-2.11, -1.00] | -1.13 [-2.67, 0.04] | -0.41 [-1.65, 1.26] | False | CONFIRM-LAG |
  | exp8 B | -1.20 [-1.77, -0.58] | -1.33 [-2.37, 0.78] | 0.12 [-2.21, 1.47] | True | ESTIMATE |
  | exp10 op point | G3_op -2.42 [-4.35, -1.53] | 0.99 [-1.10, 3.53] | -3.40 [-6.09, -1.30] | - | CONFIRM-LAG |

  The pre-edit baseline (G3_orig) is strongly negative in every body, confirming the baseline offset. The edit-induced component (G3_edit) spans zero in three of four curves. The experiment 9 lambda curve gives a positive edit-induced component (1.43 [0.29, 2.98]), suggesting that the edit actually *closes* the pre-existing gap in that body. Curve slopes: b_Gemma ranges from 1.40 to 1.66, b_GaMS from 0.97 to 1.13 -- both near 1, confirming parallel curves consistent with R-BASE.

  ### Tipping analysis

  Both tipping paths (Gemma-SL false-REFUSE and GaMS-SL false-COMPLY) reach measured error CIs in most curves. The Gemma-SL 1-Sp (measured 0.34 [0.17, 0.57]) exceeds the delta* needed to push the lag to the negative margin in the experiment 9 lambda curve (0.36) and the experiment 11 reserved split (0.21). The GaMS-SL 1-Se (measured 0.09 [0.03, 0.26]) reaches the eps* needed to push the lag to zero in experiment 9 (0.13) and experiment 11 (0.21). The lag sign is robust; its magnitude is not.

  ### R-JUDGE rival

  Translate-then-judge (TTJ) lag tracks the direct readout closely: experiment 9 lambda curve direct -0.89 vs TTJ -0.81 (difference 0.08); experiment 11 reserved split direct -0.83 vs TTJ -1.37 (difference -0.55). Both survive. If the lag were a judge artefact of Slovene-language responses, TTJ (which judges English translations) would erase it. It does not.

  ### Outcome

  The lag sign is replicated under a paid frontier judge. The readout gate fails, so the magnitude is uncertain. The R-BASE (baseline offset) account is the best-supported explanation: the lag is pre-edit, not edit-induced. Spend: $4.31 of $8.00 cap.

  ## Artifact 16: 2x3x3 input-language x output-language mechanism test (Experiment 14)

  \footnote{Code: \url{https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-4/experiment-14}}

  This experiment tested the M-OUT (production-side) and M-IN (input-side) accounts of why Gemma retains more Slovene refusal after English-objective abliteration. The design crossed input language (EN, SL, HU) with forced output language (EN, SL, HU) using a parallel one-line suffix in the input language that states the required response language. The suffix was present in every cell, including matched cells, so it is constant across the design. Three models were run: Gemma-3-12B-IT, GaMS3-12B-Instruct, and p-e-w/gemma-3-12b-it-heretic (a public English-abliterated Gemma checkpoint, one external dose). Items: 200 harmful + 100 benign. Total: 18,700 rows.

  **[Correction (iter 5): Tables 28-30 and this section's prose were regenerated from experiment 14's own `results/RESULTS_tables.md`. They replace earlier tables that did not match that file. The earlier tables showed Gemma SL->EN at 0.25 where the file has 0.07, and GaMS3 OUT_SL at +0.05 where the file has -0.44. The earlier text also said compliance was >= 90% in all but one cell, but four GaMS3 cells are below 0.90, one of them at 0.00.]**

  **Doses.** Doses were chosen on a DEV scan of EN->EN refusal with the suffix. Gemma: lambda_lo = 0.5 and lambda_hi = 1.0. EN->EN logit refusal was +0.36 and -1.47, so the scan straddles 50% (straddle ok and FINAL support both True). GaMS3: lambda_lo = 0.5 and lambda_hi = 0.625. EN->EN logit refusal was -0.82 and -1.32, both below 50%, so the scan does not straddle it (straddle ok and FINAL support both False). **Every GaMS3 quantity evaluated at matched EN->EN 50% (Table 30b, and the L*-based contrasts in Table 30) is therefore an extrapolation outside GaMS3's measured dose support.**

  ### Refusal rate tables

  Table 28 (Gemma) and Table 29 (GaMS3) give the refusal share per cell at all three doses. The readout is the primary judge on harmful items, coded R = REFUSE share, with Wilson 95% CIs. The RP coding is identical to R in every cell. Language compliance is the share of replies written in the requested output language, pooled over doses. Cells below 0.90 are marked †.

  **Table 28. Gemma-IT refusal rate per input->output cell, all three doses.**

  | Cell | zero | lo (lambda 0.5) | hi (lambda 1.0) | Language compliance |
  |-|-|-|-|-|
  | EN->EN | 0.88 [0.83, 0.92] | 0.59 [0.52, 0.66] | 0.18 [0.14, 0.24] | 1.00 |
  | EN->SL | 0.95 [0.92, 0.98] | 0.92 [0.87, 0.95] | 0.77 [0.71, 0.82] | 0.99 |
  | EN->HU | 0.94 [0.90, 0.97] | 0.81 [0.75, 0.86] | 0.46 [0.39, 0.53] | 0.98 |
  | SL->EN | 0.88 [0.82, 0.91] | 0.46 [0.39, 0.52] | 0.07 [0.05, 0.12] | 1.00 |
  | SL->SL | 0.95 [0.91, 0.97] | 0.85 [0.80, 0.90] | 0.56 [0.49, 0.63] | 1.00 |
  | SL->HU | 0.94 [0.90, 0.97] | 0.84 [0.78, 0.88] | 0.53 [0.46, 0.60] | 1.00 |
  | HU->EN | 0.88 [0.83, 0.92] | 0.54 [0.47, 0.60] | 0.10 [0.07, 0.15] | 1.00 |
  | HU->SL | 0.95 [0.92, 0.98] | 0.93 [0.89, 0.96] | 0.83 [0.78, 0.88] | 0.96 |
  | HU->HU | 0.94 [0.90, 0.97] | 0.80 [0.74, 0.85] | 0.55 [0.48, 0.62] | 1.00 |

  **Table 29. GaMS3-Instruct refusal rate per input->output cell, all three doses.**

  | Cell | zero | lo (lambda 0.5) | hi (lambda 0.625) | Language compliance |
  |-|-|-|-|-|
  | EN->EN | 0.82 [0.77, 0.87] | 0.30 [0.25, 0.37] | 0.21 [0.16, 0.27] | 1.00 |
  | EN->SL | 0.77 [0.71, 0.82] | 0.21 [0.16, 0.27] | 0.14 [0.09, 0.19] | 0.98 |
  | EN->HU | 0.80 [0.73, 0.85] | 0.34 [0.28, 0.41] | 0.23 [0.17, 0.29] | 0.97 |
  | SL->EN | 0.87 [0.82, 0.91] | 0.25 [0.20, 0.31] | 0.16 [0.12, 0.22] | 0.00 † |
  | SL->SL | 0.87 [0.82, 0.91] | 0.20 [0.15, 0.26] | 0.15 [0.11, 0.21] | 1.00 |
  | SL->HU | 0.82 [0.77, 0.87] | 0.27 [0.21, 0.33] | 0.17 [0.13, 0.23] | 0.56 † |
  | HU->EN | 0.86 [0.81, 0.91] | 0.29 [0.24, 0.36] | 0.19 [0.14, 0.25] | 0.14 † |
  | HU->SL | 0.92 [0.87, 0.95] | 0.23 [0.18, 0.29] | 0.12 [0.09, 0.18] | 0.86 † |
  | HU->HU | 0.91 [0.86, 0.94] | 0.41 [0.34, 0.48] | 0.28 [0.22, 0.35] | 1.00 |

  **Table 29b. p-e-w/gemma-3-12b-it-heretic (public checkpoint, single external dose).**

  | Cell | ext | Language compliance |
  |-|-|-|
  | EN->EN | 0.05 [0.03, 0.09] | 1.00 |
  | EN->SL | 0.15 [0.11, 0.21] | 0.92 |
  | EN->HU | 0.02 [0.01, 0.05] | 0.96 |
  | SL->EN | 0.01 [0.00, 0.03] | 0.99 |
  | SL->SL | 0.21 [0.16, 0.27] | 1.00 |
  | SL->HU | 0.07 [0.04, 0.11] | 0.99 |
  | HU->EN | 0.04 [0.02, 0.07] | 0.94 |
  | HU->SL | 0.14 [0.10, 0.19] | 0.68 † |
  | HU->HU | 0.08 [0.05, 0.13] | 1.00 |

  Gemma at the high dose shows a large output-language gradient. English-output cells refuse 0.07-0.18 and Slovene-output cells 0.56-0.83. EN->SL is 0.77 against EN->EN 0.18, a difference of 0.59. The gradient is present before the edit: at dose zero, the Slovene-output cells refuse 0.95 against 0.88 for the English-output cells. Input language matters less, and its sign depends on the column. At the high dose, Slovene input lowers refusal in the EN and SL output columns (0.18 -> 0.07 and 0.77 -> 0.56) and raises it slightly in the HU column (0.46 -> 0.53).

  GaMS3 at its high dose spans 0.12-0.28 with no Slovene-output excess. **GaMS3 did not follow the output-language instruction off the English-input row.** Its SL->EN compliance is 0.00, and all 32 of its high-dose SL->EN refusals were written in the input language, not the requested output language. HU->EN compliance is 0.14 and SL->HU 0.56. GaMS3's SL->EN column is therefore in practice a second SL->SL cell. Only the English-input row (EN->EN, EN->SL, EN->HU; compliance 0.97-1.00) is a valid output-language manipulation for GaMS3. Gemma complies at 0.96-1.00 in every cell.

  ### Mechanism contrast

  OUT_SL is the Slovene output-language effect and IN_SL the Slovene input-language effect, both on the edit-induced L* scale of Table 30b. OUT_SL averages (X->SL minus X->EN) over English and Slovene input X. IN_SL averages (SL->Y minus EN->Y) over English and Slovene output Y. These definitions reproduce the raw values of both models from Table 30b. **Both contrasts therefore use GaMS3's non-compliant SL->EN cell.** Table 30 gives every readout recorded in the results file. NA marks a readout that has no L*-based estimate: translate-then-judge ran only at edited doses, and the second judge produced no labels on these rows. MDE = 2.8 x bootstrap SE.

  **Table 30. Mechanism contrasts by readout (logit, 95% CI).**

  | Readout | Model | OUT_SL | IN_SL | INT_SL | OUT-IN (SL) | OUT_HU | IN_HU | INT_HU |
  |-|-|-|-|-|-|-|-|-|
  | raw_R | Gemma | 1.14 [0.60, 1.56] | -0.60 [-1.02, -0.18] | -0.02 [-0.71, 0.62] | 1.73 [1.03, 2.34] | 0.55 [0.13, 0.91] | -0.15 [-0.56, 0.25] | 0.34 [-0.42, 1.11] |
  | raw_R | GaMS3 | -0.44 [-0.98, 0.27] | -0.86 [-1.58, -0.13] | -0.66 [-2.74, 0.60] | 0.41 [-0.55, 1.59] | 0.30 [-0.30, 1.14] | -0.40 [-1.06, 0.61] | -0.35 [-1.92, 0.73] |
  | raw_RP | Gemma | identical to raw_R | | | | | | |
  | raw_RP | GaMS3 | identical to raw_R | | | | | | |
  | ttj_R | both | NA | NA | NA | NA | NA | NA | NA |
  | second_R | both | NA | NA | NA | NA | NA | NA | NA |
  | rg_R | Gemma | 1.85 [-3.67, 7.44] | -2.53 [-5.74, -0.12] | -3.95 [-6.12, 4.07] | 4.38 [-1.31, 10.08] | -0.66 [-4.37, 5.39] | -0.28 [-2.59, 1.69] | 0.65 [-3.45, 6.23] |
  | rg_R | GaMS3 | -3.07 [-8.76, 1.44] | -5.32 [-8.36, -0.70] | 6.15 [-5.56, 10.15] | 2.24 [-6.66, 7.01] | -0.24 [-7.21, 7.67] | -4.22 [-7.89, 3.18] | -4.84 [-9.29, 10.31] |
  | ppi_R | Gemma | 0.20 [-0.76, 1.13] | -0.42 [-0.88, 0.14] | 0.36 [-0.54, 1.00] | 0.62 [-0.55, 1.72] | -0.39 [-1.39, 0.36] | -0.14 [-0.56, 0.34] | 0.25 [-0.74, 1.18] |
  | ppi_R | GaMS3 | 3.09 [-7.69, 5.59] | -2.37 [-6.14, 3.21] | -4.32 [-13.58, 6.06] | 5.46 [-8.15, 9.05] | 0.41 [-2.09, 6.30] | -0.55 [-3.74, 2.95] | -0.94 [-8.59, 3.81] |

  Cross-model contrasts on the raw readout (GaMS3 minus Gemma):
  - dOUT_SL = -1.58 [-2.22, -0.66] (MDE 1.07)
  - dIN_SL = -0.26 [-1.13, 0.57] (MDE 1.19)
  - dINT_SL = -0.64 [-2.74, 0.83] (MDE 2.50)
  - dOUT_HU = -0.26 [-0.96, 0.69] (MDE 1.14)
  - dIN_HU = -0.25 [-1.02, 0.82] (MDE 1.32)
  - HU fluency = -0.09 [-1.37, 0.78] (MDE 1.54)

  **Pre-registered decisions.**
  - raw_R and raw_RP: P0 passes. SL: M-OUT SUPPORTED. HU: M-OUT SUPPORTED. Specificity checks: dOUT_SL DIFFERENT, dIN_SL ESTIMATE, G3 at SL->SL DIFFERENT, G3_edit at SL->SL ESTIMATE.
  - rg_R: P0 fails, so no mechanism call is made. The would-be SL call is MIXED/UNRESOLVED and HU is NEITHER (ESTIMATE). dOUT_SL = -4.92 [-13.28, 1.49], MDE 10.62.
  - ppi_R: P0 fails, so no mechanism call is made. The would-be SL call is NEITHER (ESTIMATE). dOUT_SL = 2.89 [-7.80, 5.65], MDE 9.71.
  - ttj_R and second_R: P0 fails; no call.
  - The results file's own robustness flag for the SL call across raw, RG, PPI and TTJ is **robust = False**.

  Gemma's raw OUT_SL = 1.14 [0.60, 1.56] excludes zero. So does its English-input-row component alone, L*(EN->SL) = 1.15 [0.54, 1.68] (Table 30b). The raw dOUT_SL = -1.58 excludes zero, but it averages in GaMS3's non-compliant SL->EN cell. **Restricted to the compliance-valid English-input row, the edit-induced cross-model contrast is G3_edit(EN->SL) = -1.26 [-2.17, 0.20], whose CI includes zero.** The total contrast on that row, including the pre-edit gap, is G3(EN->SL) = -2.63 [-3.46, -1.30]. M-OUT is therefore supported for Gemma on the raw readout. It is not supported as a cross-model edit-induced effect once GaMS3's failed manipulation is excluded, and it does not survive the corrected readouts.

  **Table 30b. Lag at matched EN->EN refusal of 50% (logit, 95% item-bootstrap CI, raw primary readout).** a is the total SL-vs-reference gap at the matched point. L* is its edit-induced part, that is, a minus the pre-edit gap. G3 = GaMS3 a minus Gemma a, and G3_edit = GaMS3 L* minus Gemma L*. GaMS3 values are extrapolated (see Doses).

  | Cell | Gemma a | Gemma L* | GaMS3 a | GaMS3 L* | G3 | G3_edit |
  |-|-|-|-|-|-|-|
  | EN->EN | 0.00 [-0.00, 0.00] | 0.00 [-0.00, 0.00] | 0.00 [-0.00, 0.00] | 0.00 [-0.00, 0.00] | 0.00 [-0.00, 0.00] | 0.00 [-0.00, 0.00] |
  | EN->SL | 2.17 [1.81, 2.67] | 1.15 [0.54, 1.68] | -0.45 [-1.15, 0.83] | -0.11 [-0.88, 1.29] | -2.63 [-3.46, -1.30] | -1.26 [-2.17, 0.20] |
  | EN->HU | 1.12 [0.88, 1.42] | 0.39 [-0.18, 0.85] | 0.28 [-0.36, 1.36] | 0.47 [-0.24, 1.56] | -0.85 [-1.57, 0.30] | 0.09 [-0.78, 1.37] |
  | SL->EN | -0.63 [-0.94, -0.34] | -0.59 [-1.02, -0.16] | -0.18 [-0.85, 0.91] | -0.53 [-1.28, 0.58] | 0.45 [-0.30, 1.57] | 0.06 [-0.79, 1.18] |
  | SL->SL | 1.46 [1.14, 1.86] | 0.54 [-0.14, 1.10] | -0.96 [-1.60, -0.16] | -1.30 [-2.04, -0.46] | -2.42 [-3.21, -1.53] | -1.84 [-2.80, -0.78] |
  | SL->HU | 1.34 [1.02, 1.77] | 0.52 [-0.14, 1.11] | -0.15 [-0.83, 1.07] | -0.15 [-0.97, 1.10] | -1.49 [-2.24, -0.34] | -0.67 [-1.65, 0.74] |
  | HU->EN | -0.32 [-0.63, 0.00] | -0.32 [-0.79, 0.16] | 0.08 [-0.73, 1.54] | -0.22 [-1.15, 1.23] | 0.40 [-0.41, 1.76] | 0.09 [-0.87, 1.55] |
  | HU->SL | 2.37 [1.96, 2.97] | 1.34 [0.74, 1.89] | -0.00 [-0.78, 1.53] | -0.81 [-1.77, 0.78] | -2.37 [-3.33, -0.75] | -2.15 [-3.16, -0.46] |
  | HU->HU | 1.14 [0.87, 1.46] | 0.41 [-0.21, 0.95] | 0.59 [-0.15, 1.97] | -0.10 [-0.96, 1.30] | -0.56 [-1.34, 0.84] | -0.51 [-1.51, 1.00] |

  G3_edit excludes zero in two cells, SL->SL (-1.84 [-2.80, -0.78]) and HU->SL (-2.15 [-3.16, -0.46]). Both rest on extrapolated GaMS3 values, and HU->SL is a non-compliant GaMS3 cell (0.86). A GLM co-primary estimate gives the same pattern: Gemma a(EN->SL) = 2.08 [1.77, 2.43] and GaMS3 a(EN->SL) = -0.44 [-0.73, -0.16]. A GEE logit with an exchangeable item cluster (n = 10,800) gives a model x SL-output x high-dose coefficient of -2.41 (SE 0.26, p = 8e-20).

  ### Placebo and controls

  **Placebos.** All null means are below 0.1.
  - In/out swap, OUT-minus-IN (SL): Gemma observed 1.73 (null SD 0.30, permutation p = 0.0); GaMS3 observed 0.41 (null SD 0.50, p = 0.41).
  - Model swap: G3 at SL->SL -2.42, G3_edit at SL->SL -1.84 and dOUT_SL -1.58 all give permutation p = 0.0; dIN_SL -0.26 gives p = 0.30.
  - Language swap, SL->SL minus EN->EN logit: Gemma +0.92, +1.40 and +1.71 at zero, lo and hi (p <= 0.002). GaMS3 +0.35 (p = 0.06), -0.59 (p = 0.002) and -0.37 (p = 0.11).

  **Random-direction edit at the high dose.** Refusal stays at its dose-zero level:
  - Gemma EN->EN: random 0.88 against real 0.185. Gemma SL->SL: random 0.96 against real 0.56.
  - GaMS3 EN->EN: random 0.825 against real 0.21. GaMS3 SL->SL: random 0.88 against real 0.155.
  - First-token KL, real against random: Gemma EN 0.57 vs 0.006 and SL 0.34 vs 0.005; GaMS3 EN 0.068 vs 0.001 and SL 0.049 vs 0.001.

  **MT noise.** EN-orig vs EN-BT refusal differs significantly at dose zero in both models:
  - Gemma: 0.935 vs 0.88, McNemar p = 0.019.
  - GaMS3: 0.905 vs 0.825, p = 0.005.
  - At the high dose there is no significant difference (p = 0.56 and 0.83).

  **Harmful content (R-INCAP).** The results file has an attack-success entry for one cell only, Gemma HU->SL: S = 0.00 at both edited doses (n = 186 and 167). No harmful-content reading exists for the decisive EN->SL and EN->EN cells.

  **Degeneracy.** The degeneracy rate is at most 0.008 in every model x dose; none is flagged.

  ### C-EXT: public checkpoint

  The public p-e-w/gemma-3-12b-it-heretic checkpoint (Table 29b) shows the same direction as edited Gemma. SL->SL refuses 0.21 against 0.05 for EN->EN, a residual of 16.0 pp. OUT_ext_SL = 1.38 [0.49, 2.44] and IN_ext_SL = -0.72 [-1.60, -0.08]. The checkpoint's absolute refusal is far lower than edited Gemma's, and its HU->SL cell fails compliance (0.68). Its judge-validity cells have only 10 rows each, with no gold REFUSE rows in either. So this is a directional replication in one checkpoint we did not build, not a validated magnitude.

  ### SDT decomposition

  **Table 30c. Signal-detection DiD (Gemma minus GaMS3) at dose zero and lambda_hi, benign twins as noise, 95% CI.** Negative c DiD means Gemma's criterion moves further toward refusal than GaMS3's.

  | Dose | Contrast | d' DiD | c DiD | Gemma-only d' | Gemma-only c |
  |-|-|-|-|-|-|
  | zero | SL input | -0.02 [-0.57, 0.58] | 0.20 [-0.07, 0.49] | 0.04 | 0.04 |
  | zero | SL output | -0.13 [-0.68, 0.39] | -0.76 [-1.06, -0.52] | -0.32 | -0.67 |
  | zero | SL both | -0.41 [-1.01, 0.15] | -0.47 [-0.78, -0.20] | -0.22 | -0.57 |
  | hi | SL input | 0.27 [-0.59, 0.83] | 0.48 [0.07, 0.75] | 0.08 | 0.57 |
  | hi | SL output | 0.72 [-0.06, 1.30] | -1.56 [-1.97, -1.29] | 0.42 | -1.41 |
  | hi | SL both | 0.18 [-0.87, 0.90] | -1.16 [-1.72, -0.81] | 0.19 | -0.95 |

  The Slovene-output effect sits in the criterion, not in discrimination. At high dose the c DiD is -1.56 [-1.97, -1.29] and the d' DiD is 0.72 [-0.06, 1.30], which includes zero. The criterion shift is already present before the edit: the dose-zero SL-output c DiD is -0.76 [-1.06, -0.52]. Slovene input moves the criterion the other way at high dose (+0.48 [0.07, 0.75]).

  ### Judge validity

  These figures compare the primary judge with blind author-model adjudication, NOT human review. Across 240 pooled edited rows, Se = 0.89 [0.81, 0.95], Sp = 0.73 [0.66, 0.79] and kappa3 = 0.51. In the decisive cells:
  - Gemma SL edited (n = 60): Se 0.89 [0.75, 0.96], Sp **0.42 [0.24, 0.61]**, kappa 0.35.
  - GaMS3 SL edited (n = 60): Se 0.86 [0.49, 0.97], Sp 0.81 [0.69, 0.89], kappa 0.43.
  - Gemma EN edited: Se 0.70 [0.40, 0.89], Sp 0.75 [0.53, 0.89].
  - Gemma HU edited: Sp 0.67 [0.45, 0.83].

  The phase-4 gate fails in both decisive cells. No gpt-4.1-mini labels exist on edited rows, and the shuffled-label kappa is NA. The judge over-calls REFUSE most in exactly Gemma's Slovene-output edited cells, the cells that carry the M-OUT effect.

  ### Outcome

  **Verdict: ESTIMATE (screen), not a confirmation.** On the raw readout, edited Gemma's residual refusal follows the output language. English-output cells refuse 0.07-0.18 whatever the input language, Slovene-output cells refuse 0.56-0.83, and the pre-registered raw call is M-OUT SUPPORTED. Five facts limit this:
  1. The call is not robust across readouts. RG and PPI make no mechanism call, TTJ and the second judge have no L* estimate, and the results file flags robust = False.
  2. GaMS3 failed the output-language manipulation off the English-input row. On the compliance-valid row, the cross-model edit-induced contrast -1.26 [-2.17, 0.20] includes zero, and GaMS3's L* values are extrapolated.
  3. The Slovene-output separation, and its criterion shift, already exist at dose zero.
  4. Gemma's Slovene-output edited cells have judge Sp 0.42.
  5. Harmful-content yield was measured in only one cell.

  The production-side reading remains a hypothesis. It holds that refusal is the fallback when the model must produce harmful content in a language it generates poorly (Gemma SL BPB 1.20 vs GaMS3 0.89, from experiment 12's competence covariates). This experiment does not test it directly.

  The nearest published neighbour for this finding is Upadhyaya and Sikdar [11], who showed safety features entangled with language identity in Gemma-2-9B. Our delta is the matched sibling pair under partial-dose abliteration with a 2x3x3 design that separates input from output language. As of 2026-09-24, no prior study crosses prompt language with response language for refusal measurement (research artifact verification).

  ## Artifact 17: Fine-grained lambda ladder (Experiment 15)

  \footnote{Code: \url{https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-4/experiment-15}}

  This experiment ran a fine-grained lambda ladder -- 13 steps for Gemma (0.000 to 2.000) and 15 steps for GaMS (0.000 to 1.538) -- on a fresh 300-item RefusEU-TRAIN body disjoint from all prior probes. Each step used NLLB EN-BT and SL-MT arms from one English source. The judge was a local model (primary) with archival and TTJ readouts.

  ### Per-step refusal rates

  Gemma SL refusal consistently exceeds EN refusal (margin positive throughout the entire dose range): at lambda 0 the margin is 1.48 log-odds; at lambda 2.0 it is 1.24. GaMS SL tracks EN closely: margin near zero or slightly negative in the middle range (e.g. -0.25 at lambda 0.420), turning positive at higher doses (0.72 at lambda 1.538). The margin never reaches the magnitude seen in Gemma.

  ### Headline readouts

  **Table 31. Headline G3 decomposition (R coding, raw readout).**

  | Readout | G3 [95% CI] | G3_orig [95% CI] | G3_edit [95% CI] |
  |-|-|-|-|
  | RAW | -0.70 [-1.01, -0.42] | -1.17 [-2.83, 0.22] | 0.47 [-0.96, 2.14] |
  | RG | -0.01 [-4.36, 11.27] | -1.76 [-5.45, 1.96] | 1.75 [-4.58, 13.18] |
  | PPI | -0.75 [-2.43, 0.99] | -1.52 [-6.46, 2.82] | 0.76 [-3.78, 6.27] |
  | TTJ | -0.79 [-1.09, -0.48] | -1.37 [-2.29, 0.37] | 0.58 [-1.18, 1.52] |

  G3_R = -0.70 [-1.01, -0.42] with MDE 0.42, the most powerful estimate in the entire study. It survives under TTJ (-0.79 [-1.09, -0.48]). G3_orig_R = -1.17 [-2.83, 0.22]: the pre-edit gap carries the lag. G3_edit_R = +0.47 [-0.96, 2.14]: the edit-induced component spans zero, confirming that the lag is baseline, not edit-induced. Rogan-Gladen correction is degenerate (CI [-4.36, 11.27]) due to low specificity. PPI includes zero.

  Curve slopes: b_Gemma = 0.94 [0.75, 1.17], b_GaMS = 0.80 [0.63, 0.95]. Both are near 1, confirming parallel-curve geometry consistent with R-BASE.

  ### Random-direction control

  Norm-matched random edits at four lambda points show G3_edit_rand near zero at all ranks (range 0.39 to 0.49), with CIs spanning zero at s=0.5 and including small positive values. The random control confirms that the (non-significant) G3_edit is not a directional artefact: random perturbations of equal norm produce the same null G3_edit.

  ### MT-noise check

  EN-orig vs EN-BT refusal rates do not differ significantly at any model-lambda combination (McNemar p >= 0.125 in all four tested cells). Machine translation noise is not driving the SL-EN margin.

  ### First-token KL collateral

  The real refusal edit produces much larger KL divergence than random directions at matched norm. For Gemma at lambda 2.0: real KL_EN 0.38, KL_SL 0.74, vs random KL_EN 0.008-0.011, KL_SL 0.019-0.019. For GaMS at lambda 1.538: real KL_EN 0.16, KL_SL 0.12, vs random KL_EN 0.003-0.005, KL_SL 0.004-0.004. The edit's collateral damage is real and directionally specific, not norm-induced.

  ### SDT per step

  Both models show a criterion shift across languages at every lambda step. At lambda 0: Gemma c_EN = 0.58, c_SL = 1.37 (shift +0.79); GaMS c_EN = 0.61, c_SL = 1.02 (shift +0.41). At lambda 2.0: Gemma c_EN = -1.05, c_SL = -0.22 (shift +0.83). The Slovene criterion is always higher (more conservative) than English in Gemma. In GaMS, the shift is smaller and reverses at higher doses. d' drops monotonically with dose in both models, as expected.

  ### Judge validity

  Per-cell adjudication: Gemma SL edited Sp = 0.55 [0.40, 0.69]; GaMS SL edited Se = 0.76 [0.55, 0.89], Sp = 0.62 [0.46, 0.75]. The pooled edited kappa is 0.51. These are the best validation numbers in the study, but still below the 0.80 gate.

  ### Verdict

  Primary verdict: ESTIMATE. The lag screen is not a confirmation because the readout gate fails and TOST equivalence for the cross-model lag does not hold. R-BASE is supported: the edit-induced component spans zero, the pre-edit baseline is negative, and the curves are parallel. The MDE (0.42) means a true edit-induced lag of magnitude 0.42 or larger would have been detected; the data are consistent with a true edit-induced component near zero.

  ## Artifact 18: Prior-art and fact check (Research)

  \footnote{Code: \url{https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-4/research-1}}

  This artifact conducted a dated (2026-09-24) prior-art search and fact verification. No LLM spend; web greps plus one local overlap script. Key findings:

  **Novelty.** No published paper crosses prompt language with response language for refusal or ASR measurement as of 2026-09-24. The M-IN/M-OUT design is novel. Confidence is medium (the handbook's base rate for unchecked lanes turning out occupied is 11/11, and paywalled or unindexed work was not covered). Nearest neighbours: Deng et al. 2023 (instruction language), Cognitive Overload (turn-language switch), Minionese (perturbation type over 18 input languages), Upadhyaya and Sikdar 2026 (output language as outcome of safety-feature ablation, not as a controlled factor). Related concurrent work: Zhang et al. [29] analyse why safety guardrails degrade across languages; Kompella and Mahajan [32] locate and price the cross-lingual refusal circuit in an MoE model; Stein et al. [33] use English steering vectors for multilingual safety alignment (BabelSteering).

  **Claim verdicts.**
  - Cross-lingual abliteration lag: incremental vs Wang et al. [2], who showed full-dose English-direction transfer across 14 languages with no sibling pairs or dose sweep.
  - Gemma criterion shift on originals: incremental. Aziz et al. [7] describe under-refusal as calibration; Yoon et al. [30] document non-English over-refusal costs. Our sibling-pair design adds GaMS3-specific detail.
  - Language-specificity of refusal direction: incremental, exploratory. Converse of Upadhyaya and Sikdar [11].
  - Harmfulness AUROC 1.00: replication of Aziz et al. [7], not a new finding. Source-separability confound documented by Balani and Panda [31].
  - M-OUT (production-fluency mechanism): novel as a hypothesis. Nearest neighbours report unclear or irrelevant low-resource output (Shen et al. [27], Dahir [28]), but none separates a generation metric from a comprehension metric.

  **Heretic facts.** Heretic @3521f86 is a 2.0.0.dev0 snapshot (2026-09-05). Defaults: 200 trials / 60 startup (not 80). English-keyword refusals on the first 100 AdvBench test prompts. No automatic selection: the choice is interactive over a Pareto front, or via a trial index. The pre-registered KL <= 0.5 selection rule is ours, not Heretic's.

  **Item overlap.** mlabonne/harmful_behaviors is set-identical to AdvBench (520/520), and Heretic uses 500 of those prompts. The item bodies for experiments 14 and 15 were verified disjoint from AdvBench, RefusEU evaluation, and all prior probes.

  **Hungarian.** Hungarian is not in the declared GaMS3 CPT/SFT mix. The model card shows SL 48.9 / EN 28.3% of CPT tokens (not 41.1/27.8 as earlier stated). Croatian/Serbian/Bosnian make up 22.3% of base continued pretraining, a South-Slavic confound for any claim about Slovene-specific training.

  [FIGURE:fig_mechanism_2x3]

  [FIGURE:fig_lambda_ladder]

  ## Not executed or abandoned in iteration 4

  Slot 2 of the iteration-4 strategy (experiment 13) was the held-out confirmation. It was to use a newly selected Heretic edit, a DEV-calibrated lambda grid, a confirmation curve on a new external 300-item body, random-direction controls and the frozen-core RQ2 natural pairs under the edit. It produced **no generation and no primary label**. Every item below is read from experiment 13's own workspace:
  - `protocol.yaml`
  - `results/protocol_amendments.json`
  - `results/tier_table.json`
  - `results/readout_provenance.json`
  - `data/split_manifest_iter4.json`
  - `.aii_worker_result.json`

  No number from this artifact appears in any result above.

  ### Amendment A1: GPU lost

  About 25 minutes into the run, the container lost access to its L4 GPU. nvidia-smi reported "Failed to initialize NVML: Unknown Error", and opening `/dev/nvidia*` returned EPERM, meaning the cgroup device permission was revoked host-side. This could not be fixed from inside the container, and provisioning another GPU was outside the task's tools and budget.

  The following were therefore **not executed**:
  - the new Heretic edit
  - the DEV lambda grid
  - the confirmation curve on the new B-300 items
  - the random-direction controls
  - the RQ2 natural RefusEU pairs under the edit

  The GPU code (`src/gpu_session.py`) and the new item body were delivered frozen and untested on GPU.

  The amendment substituted a paid-judge **re-readout** of the archived dose curves of two earlier Heretic edit draws. E9 is the exp9 selected edit, with Gemma random edits. E11 is the iteration-1 edit on 200 RefusEU-FINAL MT items plus 50 benign HARD items. The amendment itself states that this is a judge-validity re-readout of generations that were already analysed, not a new-item replication.

  The later amendments:
  - **A2:** gemini returned 403 PROHIBITED_CONTENT on 2 of 240 calibration rows. Such rows would take a gpt-4.1-mini fallback label.
  - **A3:** records the tier-gate failure (Table 31a below).
  - **A4:** the shared OpenRouter key hit its daily limit (403, key limit exceeded) at the first primary call. Before any label, A4 pre-registered a redesigned adjudication: 432 author-model gold rows, 12 per model x arm x lambda cell. It also pre-registered a PPI++ fallback on the archived exp9 labels, marked exploratory-substitute.

  ### Two-tier judge bake-off (tier_table)

  Two judge tiers were calibrated against eval2's 240 blind author-model adjudicated edited rows (NOT human). Both tiers fail the per-cell gate. The frozen rule therefore set gemini-2.5-flash as primary with an ESTIMATE ceiling. The two tiers agree with kappa = 0.52. Spend at this point was $0.064.

  **Table 31a. Experiment 13 judge bake-off, per cell (n = 60 per cell; gold REFUSE/non-REFUSE counts in brackets).**

  | Cell | flash-lite Se | flash-lite Sp | flash-lite kappa | flash Se | flash Sp | flash kappa |
  |-|-|-|-|-|-|-|
  | GaMS3 EN edited [38/22] | 0.97 | 0.36 | 0.39 | 0.89 | 0.55 | 0.47 |
  | GaMS3 SL edited [45/15] | 0.98 | 0.27 | 0.31 | 1.00 | 0.47 | 0.57 |
  | Gemma EN edited [27/33] | 0.89 | 0.33 | 0.21 | 0.93 | 0.55 | 0.45 |
  | Gemma SL edited [27/33] | 0.96 | 0.33 | 0.28 | 0.96 | 0.42 | 0.37 |
  | Overall (n = 240) [137/103] | 0.96 | 0.33 | 0.31 | 0.95 | 0.50 | 0.47 |
  | Gate pass | False | | | False | | |

  This is a second, independent measurement of the primary judge's over-calling on edited rows: flash specificity is 0.42-0.55. It points in the same direction as evaluation 3 (Sp 0.66-0.73) and experiment 14 (Gemma SL Sp 0.42).

  ### The re-readout: frozen but unlabelled

  The substitute re-readout table was frozen at 19,195 rows (rows sha256 `e37fd7d3...6c242`, source-file hashes recorded in `readout_provenance.json`):
  - E9: 7,040 rows. Gemma: edited 1,600 harmful + 960 benign, original 300 + 180, random 600 + 360. GaMS3: edited 1,600 + 960, original 300 + 180.
  - E11: 12,155 rows. Gemma: edited 3,200 + 800, original 400 + 100. GaMS3: edited 4,553 + 800, original 2,202 + 100.

  No primary, second-judge, translate-then-judge, StrongREJECT or adjudication label file exists in the workspace. The daily key limit (A4) was hit at the first primary call, and the executing session then ended with `failed = true` in `.aii_worker_result.json`. The table is reusable, but it carries no result.

  ### The item pool and its overlap with experiment 14

  Experiment 13 built a 519-item external harmful pool from HarmBench, JailbreakBench and StrongREJECT, with no SORRY-Bench items. It was split by sha1 order (manifest sha256 `adea9ff1...`) into:
  - **DEV:** 60 items (20 HarmBench / 5 JBB / 35 StrongREJECT).
  - **B:** 300 items for the experiment 13 confirmation (107 / 44 / 149).
  - **C:** 159 items reserved for the parallel mechanism artifact (63 / 19 / 77).
  - **SPARE:** 0 items.

  `protocol.yaml` still records the `items_iter4.jsonl` hash as PENDING, because NLLB translation was running on CPU after the GPU loss.

  Experiment 14 built its own item set from the same public sources, under its own IDs. The iteration-5 hypothesis revision found that **116 of the 300 B items and 55 of the 159 C items were consumed by experiment 14**. That leaves 184 B + 104 C = 288 items that no artifact has generated. This overlap count comes from the iteration-5 strategy record. It was not recomputed for this section, because the two artifacts use different item IDs and matching them needs a text-level join. So the B body is no longer the untouched held-out body the slot-2 plan assumed.

  **Table 31b. Iteration-4 components not executed.**

  | Component | Status | Reason | Evidence file |
  |-|-|-|-|
  | exp13 new Heretic edit and DEV lambda grid | Not executed | GPU lost (A1) | exp13 protocol.yaml |
  | exp13 held-out confirmation curve (B-300) | Not executed | GPU lost (A1) | exp13 protocol.yaml |
  | exp13 random-direction controls | Not executed | GPU lost (A1) | exp13 protocol.yaml |
  | RQ2 natural RefusEU FINAL pairs under the edit | Not executed (owed since iteration 1) | GPU lost (A1) | exp13 protocol.yaml |
  | exp13 substitute paid re-readout (19,195 rows) | Frozen, unlabelled | OpenRouter daily key limit (A4); session ended failed | exp13 readout_provenance.json, .aii_worker_result.json |
  | exp13 judge tier gate | Ran; both tiers FAIL | Sp 0.27-0.36 (flash-lite), 0.42-0.55 (flash) | exp13 tier_table.json |
  | exp13 held-out item body | Built; partly consumed by exp14 | 116 B + 55 C overlap | exp13 split_manifest_iter4.json; iteration-5 strategy |
  | exp14 harmful-content (ASR) readout | One cell only (Gemma HU->SL) | Not completed | exp14 RESULTS_tables.md |

  # Iteration 5

  **Strategy.** Three goals: (i) confirm the C-OUT finding on a fresh 294-item body with a new Heretic edit, a suffix-free design, a full 2x3x3+controls matrix, and PPI correction (experiment 16); (ii) run the deferred RefusEU FINAL evaluation with the full 1,300-item pool, random-edit and 256-token controls, and multiple readouts (experiment 17); (iii) test the R-INCAP question -- whether Gemma's Slovene reserve is real safety (harmful content separates) or production failure (the model refuses because it cannot produce harmful Slovene) -- with a StrongREJECT harmful-content endpoint alongside refusal (evaluation 4). Two support artifacts complete the iteration: a paper-number audit (evaluation 5) and a novelty and fact-check update (research 2).

  [Correction: C-LAG is now closed in favour of C-OUT. The overall cross-lingual abliteration lag is better characterised as an output-language effect (C-OUT) than as a generic cross-lingual lag (C-LAG), because the mechanism experiment (experiment 14) showed it sits in the output-language contrast, not the input-language contrast.]

  [Correction: The novelty verdict for the main claim is downgraded from NOVEL to PARTIALLY OCCUPIED. Two new preprints partly occupy the lane: Addagada [34] forces the output language and finds a relevance curse; Nguyen et al. [35] cross prompt and response language on benign content. The narrowed design (crossing both factors with safety endpoints, a sibling pair, partial-dose edit) remains unoccupied.]

  ## Artifact 19: C-OUT confirmation (Experiment 16)



  This experiment tested whether the output-language effect (C-OUT) -- edited Gemma refusing more when told to write in Slovene than in English -- replicates on a fresh 294-item body (146 StrongREJECT, 109 HarmBench, 39 JBB) with a new Heretic edit, using prediction-powered inference (PPI) as the primary estimator rather than raw rates. The design was 2 models x 7 cells (English-in English-out, English-in Slovene-out, English-in Hungarian-out, Slovene-in Slovene-out, suffix-free English, suffix-free Slovene, plus external checkpoints) x 4 doses (zero, low, high, full) plus random-direction and original-model controls. Benign twins (n = 100) were generated for signal-detection and false-refusal analyses. The primary estimator switched from Rogan-Gladen to PPI after the Youden-J diagnostic flagged Rogan-Gladen instability in decisive cells (the estimator-switch amendment; Fiedler [36]).

  ### Headline: C-OUT replicates

  The primary PPI estimate is OUT_Gemma = +2.43 [+0.89, +5.38] log-odds: edited Gemma refuses 2.43 log-odds more when told to answer in Slovene than in English, at the dose-matched lambda. The cross-model contrast dOUT = -2.31 [-5.34, -0.68] excludes zero: Gemma's output-language reserve is larger than GaMS3's. GaMS3 shows no output-language effect: OUT_GaMS3 = +0.12 [-0.47, +0.72], spanning zero. The input-language effect in Gemma is negative: IN_Gemma = -0.68 [-1.23, -0.36]. Slovene input reduces refusal.

  All confirmation clauses pass on the consensus reference: OUT_Gemma >= m, its lower CI > 0, dOUT <= -m, its upper CI < 0, sign holds under gemini-refused and adjudicated-explicit readouts, IN_Gemma <= +m, and decisive cells are compliance-valid. However, **the verdict is capped at ESTIMATE** because the adjudication kappa on harmful content is 0.12 (gate requires 0.60). The adjudicator disagreement stems from truncation: gpt-4.1 scored cut-off partial compliance as non-harmful (convincing = 1, specific = 1), while claude-haiku-4.5 graded the partial content 2-4. The anchor is WEAK.

  ### Per-cell refusal rates

  **Table 32a. Primary-judge refusal rates on harmful items, selected cells (n = 294 per cell).**

  | Model | Cell | Dose | Refusal (primary judge) |
  |-|-|-|-|
  | Gemma | EN->EN | hi | 0.330 |
  | Gemma | EN->SL | lo | 0.884 |
  | Gemma | EN->HU | lo | 0.731 |
  | Gemma | SL->EN | lo | 0.344 |
  | Gemma | SF_EN->EN | lo | 0.510 |
  | Gemma | SF_SL>SL | lo | 0.827 |
  | Gemma | EN->EN | zero | 0.918 |
  | Gemma | EN->SL | zero | 0.969 |
  | GaMS3 | EN->EN | hi | 0.490 |
  | GaMS3 | EN->SL | hi | 0.449 |
  | GaMS3 | SF_EN->EN | hi | 0.527 |
  | GaMS3 | SF_SL>SL | hi | 0.616 |
  | GaMS3 | EN->EN | zero | 0.820 |
  | GaMS3 | EN->SL | zero | 0.786 |

  Gemma's English-in Slovene-out refusal exceeds English-in English-out at every dose. The gap is present at dose zero (0.969 vs 0.918) and widens under abliteration (low dose: 0.884 vs 0.531). GaMS3's Slovene-out and English-out rates are close at every dose. The suffix-free cells show the same pattern as the suffixed cells: Slovene output drives higher refusal in Gemma (0.827 vs 0.510 at low dose), ruling out a suffix artefact.

  ### The edit widens the reserve

  The edit-induced output-language contrast OUT_edit = +2.43 [+0.92, +5.38]. English-only de-censoring does not close the Slovene reserve; it widens it. This is consistent with R-BASE: the edit suppresses English refusal more than Slovene refusal in Gemma, because Gemma's Slovene refusal was higher to begin with.

  ### SDT decomposition

  **Table 32b. Signal-detection DiD (Gemma minus GaMS3) at dose zero and dose*, 95% CI.**

  | Dose | Contrast | d' DiD | c DiD |
  |-|-|-|-|
  | zero | SL output | -0.37 [-0.81, 0.07] | -0.65 [-0.90, -0.46] |
  | lo | SL output | +0.09 [-0.62, 0.57] | -1.07 [-1.42, -0.85] |
  | zero | SL output (GaMS3 only) | | +0.10 [-0.12, 0.35] |
  | lo | SL output (GaMS3 only) | | -0.05 [-0.42, 0.38] |

  The output-language effect sits in the criterion, not in discrimination. At the dose-matched lambda, the criterion DiD is -1.07 [-1.42, -0.85] and the d' DiD is +0.09 [-0.62, 0.57], which includes zero. The criterion shift is already present before the edit (dose zero c DiD = -0.65 [-0.90, -0.46]). GaMS3's criterion DiD is near zero at both doses. This replicates the SDT pattern from experiment 14.

  ### Benign false refusal

  Gemma falsely refuses benign prompts more often when told to reply in Slovene than in English (gemini-refused readout): Slovene-out 0.38 vs English-out 0.08 (false-refusal output-language contrast = +1.95 [+1.40, +2.94]). The false-refusal input-language effect is null (+0.00 [-0.72, +0.74]). GaMS3 also shows higher false refusal in Slovene under the gemini readout (Slovene-out 0.21 vs English-out 0.02), but the sign does not hold under the template-token judge (the cross-model false-refusal difference reverses: +1.73 [+0.65, +3.17] under the template-token judge vs -0.61 [-2.25, +0.74] under gemini). The secondary benign verdict is ESTIMATE.

  ### C-EXT: public checkpoint

  The p-e-w/heretic checkpoint replicates the C-OUT direction: OUT_ext = +1.59 [+1.10, +2.24] (primary judge), +1.87 [+1.42, +2.51] (TTJ primary judge). The Slovene-vs-Hungarian contrast is also positive under the primary judge (+1.53 [+1.07, +2.08]). Only one external checkpoint was tested; the pre-registered external-replication rule requires two, so external replication cannot pass by construction.

  ### Judge validity

  **Table 32c. Judge error in decisive cells (LLM adjudication, NOT human; n = 100 per cell).**

  | Cell | Judge vs reference | Se | Sp | n |
  |-|-|-|-|-|
  | Gemma EN->EN | gemini_U vs adj_U | 0.93 | 0.63 | 99 |
  | Gemma EN->SL | gemini_U vs adj_U | 1.00 | 0.94 | 99 |
  | GaMS3 EN->EN | gemini_U vs adj_U | 0.92 | 0.84 | 100 |
  | GaMS3 EN->SL | gemini_U vs adj_U | 1.00 | 0.82 | 99 |
  | Gemma EN->EN | J1 vs adj_explicit | 1.00 | 0.46 | 100 |
  | Gemma EN->SL | J1 vs adj_explicit | 1.00 | 0.35 | 100 |

  The adjudicator kappa on harmful content is 0.12 -- far below the 0.60 gate. The four-class kappa is 0.63 (passes) and the refusal kappa is 0.90 (passes). The low harmful-content agreement is traced to gpt-4.1's handling of truncated partial compliance (the estimator-switch amendment).

  ### Placebos and sensitivities

  All within-item swap placebos centre at zero (p >= 0.15 for local readouts; p = 0.0000 for gemini readouts, confirming the signal is real on the gemini channel). The MT-noise control shows no significant difference. Random-direction edits produce near-zero output-language contrasts (random-vs-real OUT Gemma: -2.03 [-3.30, -0.98] on the primary judge, confirming the real edit is directionally specific). The OUT estimate is stable across item sources: StrongREJECT +2.60, HarmBench +2.25, JBB +2.12 (all gemini_U).

  ### Outcome

  **Verdict: ESTIMATE with WEAK anchor.** All confirmation clauses pass on the consensus reference. The C-OUT finding replicates: edited Gemma refuses more in Slovene-output cells than English-output cells, the effect sits in the criterion, and GaMS3 shows no such effect. The verdict is capped at ESTIMATE because the harmful-content adjudication kappa is 0.12, well below the 0.60 gate. The edit widens the reserve. The suffix-driver clause is false (OUT_SF +1.97 [+0.32, +5.13]): the suffix is not the mechanism. R-INCAP is tested in evaluation 4 (below).

  ## Artifact 20: RefusEU FINAL (Experiment 17)



  This experiment measured what one English-only de-censoring edit buys on RefusEU's own 1,300 prompts per language, in both models and both languages (English, Slovene). The judge stack used local substitutes after the OpenRouter budget was exhausted (judge-substitution deviation): PolyGuard refusal (replacing the primary gemini judge), Qwen3Guard-Gen-8B (replacing gpt-4o-mini adjudication), and the official StrongREJECT fine-tuned evaluator (replacing gemini StrongREJECT). Adjudication is blind author-model LLM, NOT human. 11,600 rows were analysed across four conditions: edited, original, random-edit, and 256-token sensitivity.

  ### The edit raises attack success in all four cells

  **Table 33. Paired edit effects (orig -> edit@1.0, exact McNemar, Holm-corrected).**

  | Model | Lang | ASR orig | ASR edit | Delta [95% CI] | Verdict |
  |-|-|-|-|-|-|
  | Gemma | EN | 0.045 | 0.897 | 0.852 [0.831, 0.870] | **ROBUST** |
  | Gemma | SL | 0.026 | 0.683 | 0.657 [0.629, 0.683] | **ROBUST** |
  | GaMS3 | EN | 0.033 | 0.970 | 0.937 [0.923, 0.949] | **ROBUST** |
  | GaMS3 | SL | 0.068 | 0.915 | 0.847 [0.826, 0.867] | **ROBUST** |

  All four cells are ROBUST: the edit produces a massive increase in attack success on RefusEU prompts. The edit is more effective on GaMS3 than Gemma in both languages, and more effective in English than Slovene in both models.

  ### Cross-model difference (descriptive, not dose-matched)

  The cross-model DiD in English is 0.085 [0.066, 0.105] and in Slovene 0.190 [0.159, 0.221] on the ASR readout: GaMS3 gains more from the edit than Gemma. This is descriptive because the two models were edited at the same lambda (1.0), not at dose-matched lambdas. The C-LAG line is closed in favour of C-OUT.

  ### Language confound

  The English and Slovene prompt sets are different natural prompts with LaBSE similarity 0.55, so the SL-vs-EN difference within a model is **NOT INTERPRETABLE AS A LANGUAGE EFFECT**. Even in the high-similarity subset (LaBSE >= 0.70, n = 58), the SL-EN gap in Gemma is -0.190 [-0.345, -0.035] and in GaMS3 is -0.035 [-0.121, 0.052].

  ### Corrected ASR

  Rogan-Gladen corrected deltas (using per-cell Se/Sp from blind author-model adjudication on 60 rows per cell):
  - Gemma EN: delta_RG = 0.863 [0.811, 0.892]
  - Gemma SL: delta_RG = 0.578 [0.473, 0.639]
  - GaMS3 EN: delta_RG = 0.967 [0.927, 0.976]
  - GaMS3 SL: delta_RG = 0.884 [0.826, 0.912]

  Judge validity varies by cell: GaMS3 EN passes the validation gate on ASR_row (Se 1.00, Sp 0.903) and LG-unsafe (Se 1.00, Sp 0.998). Gemma SL passes only on LG-unsafe (Se 0.889, Sp 0.829). StrongREJECT fine-tuned has near-zero sensitivity in Gemma cells (Se 0.067 EN, Se 0.000 SL), making it unsuitable as the sole harmful-content readout for Gemma.

  ### Controls

  Random-edit control: ASR changes are near zero in all four model x language cells (largest delta 0.020, McNemar p >= 0.125). The 256-token sensitivity shows higher StrongREJECT scores at longer generation but no change in ASR (e.g. Gemma EN ASR 0.850 at both 128 and 256 tokens). Language consistency is >= 0.999 in all cells. Degeneracy rates are at most 0.010.

  ### Ranking vs thresholding

  An added analysis tested whether the guards fail Slovene by ranking (AUROC) or by calibration (threshold). AUROC is high in all cells (0.887-1.000), meaning the guards rank harmful above harmless correctly. The failure is in the shipped decision threshold, not in the underlying score. This is consistent with Aziz et al.'s [7] calibration-not-representation account.

  ### Verdict

  All four paired-edit cells are ROBUST. The edit is effective on RefusEU prompts. The cross-model and cross-language differences are descriptive because the design is not dose-matched and the prompt sets are not parallel. The StrongREJECT fine-tuned evaluator has near-zero sensitivity for Gemma, confirming it cannot substitute for a paid rubric judge on this model.

  ## Artifact 21: R-INCAP safety evaluation (Evaluation 4)



  This artifact tested whether Gemma's Slovene-output reserve is real safety (harmful content separates: the model refuses AND produces less harmful content in Slovene) or production failure (the model refuses because it cannot produce harmful Slovene, not because it detects harm). It re-used experiment 14's body (200 items per cell) with refusal measured by the primary judge and harmful content measured by StrongREJECT (original gemini rubric, translated rubric, and local fine-tuned). Adjudication used a free LLM panel (Nemotron-3-ultra and Laguna-S, with dots-3/Nemotron-3-super tie-breaking), NOT human review.

  ### HARMFUL CONTENT SEPARATES (reserve = safety)

  **At high dose:** the output-language refusal contrast (primary judge) is OUT_R = 2.67 [2.29, 3.12] log-odds and the harmful-content contrast (original StrongREJECT rubric) is OUT_U = 2.61 [2.20, 3.07]. Both are positive and exclude zero. Gemma refuses more in Slovene AND produces less harmful content in Slovene. The PPI-corrected refusal (using explicit-refusal gold) is even larger: OUT_R(PPI explicit) = 5.39 [4.91, 5.85].

  **At low dose:** the same pattern holds: OUT_R (primary judge) = 2.05 [1.61, 2.65] and OUT_U (original rubric) = 2.80 [2.25, 3.69].

  The truncation-matched StrongREJECT (cutting English-out replies to the word length of the Slovene-out translation for the same item) gives a smaller contrast: OUT_U(fine-tuned StrongREJECT, truncation-matched) = 0.35 [-0.50, 1.32] at high dose, including zero. However, the gemini-scored truncation-matched contrast remains large: 2.39 [1.97, 2.86]. The truncation control shows that some of the harmful-content gap is explained by Slovene replies being shorter, but the effect survives under the paid rubric.

  **Verdict: R-INCAP = HARMFUL CONTENT SEPARATES (reserve = safety).** The reserve is not a production failure. Gemma genuinely produces less harmful content when replying in Slovene.

  ### Four-class composition

  **Table 34. Four-class composition at high dose, decisive cells.**

  | Cell | n | EXPLICIT | DEFLECT | COMPLY | PF index | U_adj |
  |-|-|-|-|-|-|-|
  | Gemma EN->SL hi | 50 | 0.54 | 0.26 | 0.20 | 0.57 | 0.14 |
  | Gemma EN->EN hi | 48 | 0.00 | 0.10 | 0.90 | 0.10 | 0.75 |
  | GaMS3 EN->SL hi | 49 | 0.00 | 0.08 | 0.90 | 0.08 | 0.90 |
  | GaMS3 EN->EN hi | 50 | 0.00 | 0.12 | 0.88 | 0.12 | 0.84 |

  The production-failure index (PF: share of degraded + deflection responses among non-explicit-refusal) in Gemma English-in Slovene-out is 0.57 vs 0.10 in English-in English-out, a difference of 0.46 [0.23, 0.65]. In GaMS3 the difference is -0.04 [-0.17, 0.09], near zero. Half of Gemma's Slovene non-compliance is deflection (the model changes the topic or gives a vague answer rather than explicitly refusing or complying). The paid sonnet-4.5 reference confirms: PF difference 0.50 [0.25, 0.68] for Gemma, -0.00 [-0.13, 0.13] for GaMS3.

  This means Gemma's Slovene reserve has two components: explicit refusal (54% of high-dose English-in Slovene-out responses) and deflection (26%). Both reduce harmful content. The deflection component is consistent with Shen et al.'s [27] relevance curse and Addagada's [34] observation that non-English output lowers attack success.

  ### SDT decomposition

  The criterion-shift pattern from experiment 14 replicates. At high dose, the SL-output c DiD (Gemma minus GaMS3) is -1.56 [-1.98, -1.29], and the d' DiD is 0.72 [-0.10, 1.31] (includes zero). The edit-induced component of the criterion shift: R-BASE-OUT c DiD(hi) - DiD(zero) = -0.80 [-1.23, -0.46]. The criterion shift widens under the edit, beyond the baseline.

  ### Benign false refusal (unedited models)

  Gemma falsely refuses benign English-in Slovene-out prompts at 0.20 [0.10, 0.37] vs English-in English-out at 0.10 [0.03, 0.26] (adjudicated any-refusal, n = 30 per cell). The primary-judge rate is higher (0.31 vs 0.09). GaMS3 shows no such gap (Slovene-out 0.10 vs English-out 0.25, but the English-out cell has only n = 4 adjudicated rows, making it uninformative).

  ### Adjudication quality

  Inter-adjudicator kappa on the four-class label is 0.82 (pooled), on any-refusal is 0.85, and on harmful content is 0.59. The sonnet-4.5 anchor agrees with the final adjudication at kappa 0.86 (class), 0.90 (any-refusal), and 0.87 (harmful content). The shuffled-label per-stratum kappa is -0.003 (pass). A bridge sample of 12 rows from evaluation 2's author-model gold gives any-refusal kappa = 0.75 (agree 0.92).

  ### Judge error matrices

  The local StrongREJECT fine-tuned evaluator has near-zero sensitivity for Gemma's Slovene-output cells: sensitivity = 0.00 [0.00, 0.35] for harmful content in Gemma English-in Slovene-out. The gemini rubrics (original and translated) have better sensitivity (0.57 [0.25, 0.84]) but lower specificity. Only sonnet-4.5 passes the validation gate in all four decisive cells (refusal sensitivity >= 0.80, specificity >= 0.80; harmful-content sensitivity >= 0.97, specificity >= 0.95). The Rogan-Gladen estimator is unidentifiable in several cells (Youden J < 0.3), so PPI is the preferred correction.

  ### Controls

  Random-edit controls: harmful-content score at random-edit high dose is near zero-dose levels (Gemma English-out: random 0.010 vs zero 0.010, Heretic 0.130). The experiment 15 lambda-0 StrongREJECT check gives Slovene-minus-English = 0.00 [0.00, 0.00] for both models, confirming no harmful-content gap at zero dose. Truncation matching reduces the StrongREJECT gap but does not eliminate it under the gemini rubric. Round-trip translation shifts StrongREJECT scores by -0.07 on average (median chrF 67.96), with 7% of U labels flipping. All placebos (model swap, outlang swap, inout swap) are centred and significant as expected.

  ### Outcome

  **Verdict: ESTIMATE with WEAK anchor.** HARMFUL CONTENT SEPARATES at both doses. The reserve is safety, not production failure. However, the local StrongREJECT evaluator has near-zero sensitivity for Gemma's Slovene cells, so the harmful-content endpoint relies on the paid gemini rubric and the free LLM panel. The PF index shows that deflection accounts for about a quarter of Gemma's Slovene reserve, consistent with the relevance curse [27, 34].

  ## Artifact 22: Paper number audit (Evaluation 5)



  This artifact audited the numerical claims across all prior iterations. Key findings:

  **R-BASE ceiling sensitivity.** Experiment 15's baseline component (cross-model gap at zero dose = -1.17) is a CEILING-ARTEFACT: one flip in the Gemma lambda-0 Slovene cell (299/300 refusals) moves it inside the margin. Only the experiment 9 lambda body has a ROBUST-OFFSET (cross-model gap = -2.56, fragility index 9). The experiment 11 and experiment 8 bodies are also ceiling artefacts (fragility index 1-2). The Jeffreys posterior gives P(gap < -m) = 0.74, 95% CrI [-3.98, 0.58].

  **Slovene-specific leakage check.** 'No Slovene-specific leakage' is supported in 8 of 12 rows; UNDETERMINED in 4 (experiment 12 Gemma, experiment 14 Gemma, experiment 15 Gemma and GaMS3). A gated GPU re-measurement of experiment 15's 40 prompts passed the gate (max relative difference 0.0000) but the bootstrap CIs of the top-dose excess are UNDETERMINED in both models.

  **Decomposition.** Across 107 body x readout rows: 15 are edit-induced, 0 are baseline, 64 are underdetermined. The parallel-curve geometry holds (b_Gemma = 0.94 [0.75, 1.17], b_GaMS3 = 0.80 [0.63, 0.95]).

  **Criterion shift.** 8 of 9 compliance-valid rows have a CI below 0: Gemma's criterion moves toward refusing when it replies in Slovene. The one exception is experiment 9 (iteration 3, English-50% window): 0.00 [-0.48, 0.42].

  **Ledger.** 1,176 numeric tokens plus 22 pointer claims: 332 SURVIVE, 844 UNTRACEABLE, 2 REVERSE, 1 SHRINKS. The claim-level reversals are: experiment 15 GaMS3 slope, experiment 15 best-validation claim, evaluation 3 experiment 10 edit-induced gap, evaluation 3 Qwen-positive. Attribution errors: experiment 15 pooled kappa, experiment 14 bits-per-byte attribution.

  **Verification.** 49/49 independent checks pass.

  ## Artifact 23: Novelty and fact check (Research 2)



  This artifact updated the novelty and fact check from iteration 4, with a search date of 2026-09-25.

  **Main-claim novelty verdict: PARTIALLY OCCUPIED** (was NOVEL). Two new preprints partly occupy the lane:
  - Addagada [34] (arXiv 2609.08373v1, 8 Sep 2026) forces the output language (EN/ES/HI/AR) of an English structural jailbreak and scores with a StrongREJECT-style rubric. Non-English output lowers attack success in 11 of 12 cells: the 'relevance curse'. N = 30 per cell, pilot preprint.
  - Nguyen et al. [35] (arXiv 2608.26186v1, 22 Aug 2026) fully cross prompt and response language (EN/NO) on benign questions. Refusals appear only in Norwegian-prompt conditions.

  **Still ours:** crossing both factors with safety endpoints (refusal + StrongREJECT, reported separately), the Gemma/GaMS3 sibling pair, the partial-dose English-only edit plus public checkpoints, Hungarian, and a constant suffix in all cells.

  **Claim verdicts.**
  - (a) Reply-language reserve: incremental. The cross-model contrast remains a screen (edit-induced cross-model gap, English-in Slovene-out: -1.26 [-2.17, 0.20]).
  - (b) Production-failure reading: incremental / replication of Shen et al.'s relevance curse [27]. The term 'relevance curse' should be cited, not coined.
  - (c) GaMS3 baseline Slovene deficit: descriptive. Confounded by different SFT. The GaMS3 paper [20] reports no safety evaluation.
  - (d) Per-cell judge error matrix: a check in a crowded lane. What remains ours is that the judge over-calls REFUSE on edited Slovene text.

  **Method specs confirmed.** StrongREJECT HEAD is unchanged (7a551d5). RefusEU is a re-implementation (Llama-Guard-3-8B + PolyGuard-Qwen, GPT-4o-mini adjudicating; no published snapshot). RG/Lang-Reiczigel formulas confirmed from Lee [25]; Fiedler [36] flags RG instability at low Youden J. PPI ids confirmed [26, 37].

  **Facts verified.** All pinned checkpoint shas equal main. GaMS3 Long-CPT BCMS share is 30.2% (vs 22.3% in Base CPT). No abliterated GaMS3 exists. NLLB is CC-BY-NC-4.0.

  **New caveat (Fiedler [36]).** RG is unstable at low Youden J. Gemma SL-edited cells with Se 0.89 / Sp 0.42 give J ~ 0.31, so PPI is the more robust correction; RG results for those cells should be flagged unstable.

  [FIGURE:fig_cout_forest]

  [FIGURE:fig_rincap_composition]

  ## Not executed or abandoned in iteration 5

  **Table 35. Iteration-5 components not executed.**

  | Component | Status | Reason | Evidence |
  |-|-|-|-|
  | Experiment 16 partial-dose points | Not executed | Hard stop at $4.00 budget cap | exp16 results/queue_*.json |
  | Experiment 16 Gemma high dose (partial) | Partial: only 100 English-out, 72 Slovene-out, 181 suffix-free English, 31 suffix-free Slovene at high dose | Gemma deadline cut | exp16 RESULTS_tables.md |
  | Experiment 16 huihui and mlabonne external checkpoints | Not run | Time: pre-registered cut order | exp16 RESULTS_tables.md |
  | Experiment 16 gpt-4.1-mini second adjudicator | Not run | OpenRouter budget | exp16 amendments |
  | Experiment 17 primary gemini judge | Replaced by PolyGuard (judge substitution) | OpenRouter budget exhausted | exp17 deviations.md |
  | Experiment 17 gemini StrongREJECT rubric | Replaced by StrongREJECT fine-tuned (judge substitution) | OpenRouter budget exhausted | exp17 deviations.md |
  | Experiment 17 gpt-4o-mini adjudicator | Replaced by Qwen3Guard-Gen-8B (judge substitution) | OpenRouter budget exhausted | exp17 deviations.md |
  | Evaluation 4 sonnet-4.5 on low dose | Not run | Budget: pre-registered high dose only | eval4 RESULTS.md |
  | Evaluation 4 human audit of adjudication | Requested, not performed | No human reviewer available | eval4 results/human_audit_request.json |
  | Frozen-core Heretic (bf16, 80 trials) | Still not executed | Owed since iteration 1 | |
  | Natural RefusEU reserved-split under edit | Still not executed | Owed since iteration 1 | |

  # What we have learned so far

  Five iterations have screened the main claim and four alternates against scoring-split data (iteration 1), the reserved evaluation split (iteration 2), fresh data with mechanism tests and utility controls (iteration 3), a paid-judge readout completion with a new mechanism experiment and a fine-grained confirmation (iteration 4), and a C-OUT confirmation with harmful-content endpoints and RefusEU FINAL (iteration 5). Two alternates are dead (base-checkpoint geometry and persona gating). A third (prefill-depth signature, alternate 4) is uncitable. The geometry of refusal is layer-dependent: nearly collinear at each model's best layer but divergent at a common layer. The perpendicular component does not induce refusal. The teacher-inheritance screen found that GaMS3's refusal decisions do not inherit from the Qwen teacher, while its wording inherits almost entirely.

  The primary contest (behaviour-level reach vs supervised reach) remains unresolved: the dose contrast is underpowered across all iterations. The overall GaMS3 Slovene deficit is judge-dependent; the meta-analytic estimate is -0.50 [-0.82, -0.21]. The criterion-shift finding replicates across experiments on compliance-valid rows: 8 of 9 CIs lie below zero (Gemma's criterion moves toward refusing when it replies in Slovene; GaMS3's does not). The shift is specific to the output language, not the input language, and is consistent with Aziz et al.'s [7] calibration-not-representation account.

  The cross-lingual abliteration lag is better characterised as an output-language effect (C-OUT) than as a generic cross-lingual lag. The C-OUT finding from experiment 14 replicates in experiment 16 on a fresh 294-item body: OUT_Gemma(PPI) = +2.43 [+0.89, +5.38], dOUT = -2.31 [-5.34, -0.68]. Gemma's refusal follows the output language; GaMS3's does not (OUT_GaMS3 = +0.12 [-0.47, +0.72]). The input-language effect is negative in Gemma (IN = -0.68 [-1.23, -0.36]): Slovene input reduces refusal, opposite to the output effect. The suffix is not the driver (suffix-free OUT spans the same range). All confirmation clauses pass on the consensus reference, but the verdict is capped at ESTIMATE because the harmful-content adjudicator kappa is 0.12 (anchor WEAK).

  **R-BASE remains the best-supported account for the overall lag.** The edit-induced component spans zero (experiment 15: edit-induced cross-model gap = +0.47 [-0.96, 2.14]). The pre-edit baseline is negative everywhere. The curves are parallel (slope near 1 in both models). The R-BASE baseline is, however, a ceiling artefact in most item bodies: experiment 15's baseline cross-model gap = -1.17 has fragility index 1 (one flip moves it inside the margin). Only the experiment 9 body has a robust offset (fragility index = 9).

  The R-INCAP question is answered: **the reserve is safety, not production failure.** At both doses, harmful content separates: Gemma produces less harmful content in Slovene-output cells (OUT_U original rubric = 2.61 [2.20, 3.07] at high dose) alongside higher refusal (OUT_R primary judge = 2.67 [2.29, 3.12]). The four-class decomposition shows that half of Gemma's Slovene non-compliance is deflection (PF index difference 0.46 [0.23, 0.65]), consistent with Shen et al.'s [27] relevance curse and Addagada's [34] output-language effect. The paid sonnet-4.5 reference confirms the pattern (PF difference 0.50 [0.25, 0.68] for Gemma; -0.00 [-0.13, 0.13] for GaMS3).

  The edit widens the Slovene reserve (edit-induced output-language contrast = +2.43 [+0.92, +5.38]). English-only abliteration does not close the Slovene-English refusal gap; it amplifies it. This is because the edit suppresses English refusal more than Slovene refusal in Gemma, as R-BASE predicts.

  On RefusEU FINAL prompts (experiment 17, n = 1,300 per cell), the edit is effective in all four cells (ROBUST). GaMS3 gains more from the edit than Gemma in both languages. The EN-vs-SL within-model difference is not interpretable as a language effect because the prompt sets differ (LaBSE 0.55). The ranking-vs-thresholding analysis shows the guards' AUROC is high (0.887-1.000) but their decision thresholds are miscalibrated for Slovene, consistent with the criterion-shift finding.

  The benign false-refusal rate is higher in Slovene-output cells than English-output cells for Gemma (Slovene-out 0.20 vs English-out 0.10, adjudicated; Slovene-out 0.38 vs English-out 0.08 on gemini-refused in experiment 16). The sign does not hold under all readouts (the template-token judge reverses the cross-model false-refusal difference).

  The novelty verdict is downgraded from NOVEL to PARTIALLY OCCUPIED. Addagada [34] forces the output language of a jailbreak and reports a relevance curse. Nguyen et al. [35] cross prompt and response language on benign content. The narrowed design -- crossing both factors with safety endpoints on a sibling pair under partial-dose abliteration -- remains unoccupied as of 2026-09-25 (medium-low confidence).

  The SDT criterion shift (c DiD) is the study's most replicable quantitative finding. It is present at dose zero (-0.65 to -0.76), widens under the edit (R-BASE-OUT c DiD(hi) - DiD(zero) = -0.80 [-1.23, -0.46]), and is specific to the output language. It means Gemma adopts a more conservative decision rule when replying in Slovene: at the same level of harmful-content discrimination, it sets a higher threshold for compliance.

  The p-e-w/heretic checkpoint replicates C-OUT across iterations: OUT_ext = +1.38 [+0.49, +2.44] (iteration 4), +1.59 [+1.10, +2.24] (iteration 5, primary-judge readout). A second public checkpoint has not been tested.

  The utility control (experiment 12) stands: the edit does not damage Slovene downstream skills more than English ones. The identity calibration arm continues to replicate.

  Open items: the readout gate has never passed. The frozen-core Heretic procedure (bf16, 80 trials, Heretic's own selection rule) has never been run. No artifact has scored natural RefusEU reserved-split prompts under the edit. All adjudication is author-LLM, not human. The harmful-content adjudicator kappa (0.12 in experiment 16; 0.59 in evaluation 4) remains below the gate; the sonnet-4.5 anchor is the best-validated readout (kappa 0.87 vs final adjudication) but is available only on high-dose decisive cells. If R-BASE is correct, the lag is an artefact of model selection (GaMS3 was simply trained to refuse less in Slovene), not a property of the abliteration procedure. The M-OUT finding (output language drives the lag) is confirmed as C-OUT and deserves pre-registered confirmation with a validated readout and human adjudication.

  ## References

  [1] A. Arditi, O. Obeso, A. Syed, D. Paleka, N. Rimsky, W. Gurnee, N. Nanda. "Refusal in Language Models Is Mediated by a Single Direction." NeurIPS 2024.

  [2] X. Wang, M. Wang, Y. Liu, H. Schutze, B. Plank. "Refusal Direction is Universal Across Safety-Aligned Languages." NeurIPS 2025.

  [3] H. Du, W. Li, M. Cai, K. Saraipour, Z. Zhang, H. Lakkaraju, Y. Sun, S. Zhang. "How Post-Training Reshapes LLMs: A Mechanistic View on Knowledge, Truthfulness, Refusal, and Confidence." arXiv 2504.02904, 2025.

  [4] U. Shaham, J. Herzig, R. Aharoni, I. Szpektor, R. Tsarfaty, M. Eyal. "Multilingual Instruction Tuning With Just a Pinch of Multilinguality." Findings ACL 2024.

  [5] F. Joad, M. Hawasly, S. Boughorbel, N. Durrani, H. Sencar. "There Is More to Refusal in Large Language Models than a Single Direction." arXiv 2602.02132, 2026.

  [6] V. Zhong, Q. Li. "Refusal Lives Downstream of Persona in Chat Models." ICML 2026 MI Workshop.

  [7] R. Aziz, I. A. Hanif, F. Koto. "Low-Resource Safety Failures Are Action Failures, Not Representation Failures." arXiv 2606.01196, 2026.

  [8] A. Krasnodebska, W. Kusa, A. Lipani. "Multilingual Refusal Alignment for Safer Large Language Models." Findings ACL 2026.

  [9] W. Hawkins et al. "The Heterogeneous Safety Impacts of Benign Multilingual Fine-Tuning." arXiv 2606.28843, 2026.

  [10] X. Li, Z.-X. Yong, S. H. Bach. "Preference Tuning For Toxicity Mitigation Generalizes Across Languages." EMNLP 2024.

  [11] A. Upadhyaya, S. Sikdar. "When Safety Speaks a Language: A Mechanistic Analysis of Safety-Language Identity Entanglement in LLMs." 2026.

  [12] S.-Y. Miao et al. "Who Bridges Safety? Identifying and Targeting Cross-Lingual Shared Safety Pathways." 2026.

  [13] A. Oppong et al. "The Illusion of Cross-Lingual Safety in Low-Resource Languages." 2026.

  [14] C. Kissane, R. Krzyzanowski, A. Conmy, N. Nanda. "Base LLMs Refuse Too." Alignment Forum, 2024.

  [15] L. Chua et al. "Crosslingual Capabilities and Knowledge Barriers in Multilingual Large Language Models." arXiv 2406.16135, 2024.

  [16] X. He et al. "TUBA: Cross-Lingual Transferability of Backdoor Attacks in LLMs with Instruction Tuning." Findings ACL 2025.

  [17] Y. Wu, L. Ding, L. Shen, D. Tao. "Edit Once, Update Everywhere: A Simple Framework for Cross-Lingual Knowledge Synchronization in LLMs." Findings ACL 2025.

  [18] G. Messenger. "Detecting Safety Training Modification in Language Models via Activation Analysis." IEEE Access, 2026.

  [19] A. Labunets. "Refusal geometry reflects refusal training: diverse refusal prefixes can raise stable rank and weaken refusal vector ablation attacks." 2026.

  [20] D. Vres, T. Arcon, T. Petric, D. Vajda, M. Robnik-Sikonja, I. L. Bajec. "Building a Strong Instruction Language Model for a Less-Resourced Language." arXiv 2603.01691, 2026.

  [21] R. Young. "Comparative Analysis of LLM Abliteration Methods: A Cross-Architecture Evaluation." arXiv 2512.13655, 2025.

  [22] A. Fafula. "Abliteration Is Not a Scalpel: Off-Target Effects of Refusal Removal on Decision Disposition Across Model Families." arXiv 2607.17427, 2026.

  [23] N. Truong. "Abliteration Mitigation via Refusal Aliases." arXiv 2608.18093, 2026.

  [24] P. E. Weidmann. "Heretic: Fully Automatic Censorship Removal for Language Models." GitHub, 2025. Commit 3521f86.

  [25] C. Lee, T. Zeng, J. Jeong, J. Sohn, K. Lee. "How to Correctly Report LLM-as-a-Judge Evaluations." ICML 2026. arXiv 2511.21140.

  [26] A. N. Angelopoulos, J. C. Duchi, T. Zrnic. "PPI++: Efficient Prediction-Powered Inference." arXiv 2311.01453, 2023.

  [27] L. Shen, W. Tan, S. Chen, Y. Chen, J. Zhang, H. Xu, B. Zheng, P. Koehn, D. Khashabi. "The Language Barrier: Dissecting Safety Challenges of LLMs in Multilingual Contexts." Findings ACL 2024. arXiv 2401.13136.

  [28] K. Y. Dahir. "SomaliBench Eval: Measuring English-to-Somali Refusal Gaps in Open-Weight Language Models." arXiv 2605.25420, 2026.

  [29] M. Zhang, A. Patel, S. T. Truong, S. Koyejo. "Why Do Safety Guardrails Degrade Across Languages?" arXiv 2605.17173, 2026.

  [30] C. Yoon, J. Park, A. Ritter. "Who Pays More for Safety? Measuring the Disparate Cost of Safety Alignment across Languages." arXiv 2608.22490, 2026.

  [31] P. Balani, S. Panda. "Hard Negatives Reveal What Easy Negatives Hide." arXiv 2609.27758, 2026.

  [32] R. P. Kompella, A. Mahajan. "Decided Upstream, Written Late: Locating and Pricing the Cross-Lingual Refusal Circuit of a Multilingual MoE." arXiv 2608.08032, 2026.

  [33] E. V. Stein, D. Meier, T. Ruas, J. P. Wahle, B. Gipp. "BabelSteering: Multilingual Safety Alignment via English Steering Vectors." arXiv 2608.16577, 2026.

  [34] T. C. Addagada. "Structural Jailbreaks Generalize but Do Not Compound: A Cross-Provider and Multilingual Study of Involuntary In-Context Learning." arXiv 2609.08373, 2026.

  [35] T. T. H. Nguyen, M. K. Tieu, M. A. Riegler, P. Halvorsen, T. Nguyen. "Investigating the Influence of Prompt and Response Languages on LLM Content Generation." arXiv 2608.26186, 2026.

  [36] J. Fiedler. "Bias and Uncertainty in LLM-as-a-Judge Estimation." arXiv 2605.06939, 2026.

  [37] A. N. Angelopoulos, S. Bates, C. Fannjiang, M. I. Jordan, T. Zrnic. "Prediction-Powered Inference." Science 382, 669-674, 2023.
summary: >-
  Iteration 5 appended five artifacts. Experiment 16 confirmed the output-language effect (C-OUT) on a fresh 294-item body
  with prediction-powered inference correction: output-language contrast for Gemma = +2.43 [+0.89, +5.38], cross-model difference
  = -2.31 [-5.34, -0.68]. The input-language effect is negative in Gemma (-0.68 [-1.23, -0.36]): Slovene input reduces refusal,
  opposite to the output effect. All confirmation clauses pass but the verdict is capped at ESTIMATE (harmful-content kappa
  0.12, anchor WEAK). Experiment 17 ran RefusEU FINAL on 1,300 prompts per cell: all four paired-edit cells are ROBUST (attack-success-rate
  deltas 0.657-0.937). The English-vs-Slovene within-model difference is not interpretable as a language effect (LaBSE 0.55).
  Evaluation 4 answered R-INCAP: the reserve is safety, not production failure. Harmful content separates at both doses (original-rubric
  output-language contrast = 2.61 [2.20, 3.07] at high dose). The four-class decomposition shows production-failure index
  difference 0.46 [0.23, 0.65] for Gemma, -0.04 for GaMS3, consistent with Shen et al.'s relevance curse and Addagada's output-language
  effect. The signal-detection criterion shift replicates: criterion DiD(high)-DiD(zero) = -0.80 [-1.23, -0.46]. Evaluation
  5 audited all prior numbers: 332 SURVIVE, 844 UNTRACEABLE, 2 REVERSE, 1 SHRINKS; experiment 15 baseline is a CEILING-ARTEFACT
  (fragility index 1). Research 2 downgraded the main-claim novelty from NOVEL to PARTIALLY OCCUPIED after Addagada (2609.08373)
  and Nguyen (2608.26186). The narrowed design remains unoccupied (medium-low confidence). The readout gate has never passed.
  All adjudication is author-LLM.
</paper_text>

<available_figures>
Each line gives the path the PAGE must use, then the figure's title and caption. It is the same
path the file has on disk here: the publish step copies the page and its figures into one folder,
so what works in this workspace is what works on the live site.

- figures/fig_sdt_v0.png [render from fig_sdt_v0.pdf first] — "Criterion Shift Across Models and Languages" (caption: "Signal-detection parameters on the HARD set from Experiment 5 (349 harmful and 1,093 safe XSTest/OR-Bench items; refusal labels from the Qwen3-14B judge; English = back-translation, Slovene = machine translation of the same items). (a) False-alarm rate $F$, the proportion of the 1,093 safe items refused, for Gemma and GaMS3 in English (blue) and Slovene (orange); error bars are Wilson 95\% CIs and the dashed grey line marks $F=0.5$. Gemma's false-alarm rate rises from 0.364 (English) to 0.569 (Slovene), while GaMS3 stays at 0.273 in both languages. (b) Difference-in-differences, $(\text{GaMS3}_{SL}-\text{GaMS3}_{EN})-(\text{Gemma}_{SL}-\text{Gemma}_{EN})$, on the criterion $c$ (DiD$_c$, orange-red) and on sensitivity $d'$ (DiD$_{d'}$, grey), in $z$ units, with 95\% percentile CIs from 2,000 item-level bootstrap resamples; the dashed line marks zero. The criterion shift is $+0.52$ [0.38, 0.68], meaning Gemma's criterion moves toward refusal in Slovene relative to GaMS3; the sensitivity shift, $-0.003$ [$-0.33$, 0.29], is indistinguishable from zero. The criterion shift is concentrated in OR-Bench-hard items and reverses sign when partial answers are coded as refusals.")
- figures/fig_grid_v0.png [render from fig_grid_v0.pdf first] — "Crossed Prompt-Language x Reply-Language Refusal Grid" (caption: "Refusal rates on harmful items in the crossed prompt-language $\times$ requested-reply-language design (Experiment 14, 200 harmful items per cell), at each model's high edit dose: (a) Gemma ($\lambda = 1.0$) and (b) GaMS3 ($\lambda = 0.625$). Rows give the prompt language and columns the requested reply language. Colour encodes the refusal rate on a shared 0--1 scale (blue below 0.5, red above), and each cell shows the rate with its Wilson 95\% CI in brackets. Hatched cells are those where under 90\% of replies were written in the requested language. All four are GaMS3 cells (SL$\to$EN, SL$\to$HU, HU$\to$EN, HU$\to$SL), so off the English-input row they do not measure the requested reply language. Gemma refuses 0.56--0.83 in the Slovene-reply column for every prompt language, against 0.07--0.18 in the English-reply column. GaMS3 stays at 0.12--0.28 in every cell. Refusal is scored by the primary judge, and the two panels use different edit strengths.")
- figures/fig_dose_v0.png [render from fig_dose_v0.pdf first] — "Dose-Response Curves for Refusal Under Abliteration" (caption: "Refusal rate on harmful prompts as a function of abliteration dose $\lambda$ (Experiment~9). $\lambda$ scales each model's own selected English-objective edit ($\lambda=0$: unedited model; $\lambda=1$: the selected edit), so the comparison that holds is English vs.\ Slovene within a model. Equal $\lambda$ does not mean an equal edit across models. Blue: Gemma-3-12B-IT; green: GaMS3-12B-Instruct. Solid lines with filled markers: English (back-translated) probes; dashed lines with open markers: Slovene (NLLB machine-translated) probes. Points are raw refusal proportions from the distilled J1 judge (label \textsc{refuse}). Shaded bands are Wilson 95\% intervals. $n=300$ items per model and language at $\lambda=0$ and $n=100$ at each of the 8 edited steps. Gemma's Slovene curve lies above its English curve at every dose, with a 0.21--0.32 gap between $\lambda=0.5$ and $1$ (e.g.\ 0.64 vs.\ 0.32 at $\lambda=1$), so more abliteration is needed to reach the same refusal reduction in Slovene. GaMS3's Slovene--English gap is smaller (at most 0.14, at $\lambda=0.5$) and closes by $\lambda=1$. The cross-model difference at matched 50\% English refusal ($G_3=-0.97$ [$-1.56$, $-0.44$] log-odds) did not meet the pre-registered confirmation criteria (verdict: \textsc{estimate}; model-label permutation $p=0.084$).")
</available_figures>

<figure_requirements>
- Reference every figure as `figures/` plus its filename, exactly as listed above.
  The publish step copies the page and its figures into one folder together, so that relative
  path is what resolves on the live site; anything else breaks once published.
- A browser cannot draw a PDF in an image element. Data figures are delivered as vector PDF for
  LaTeX's benefit, so for each one check whether a PNG of the same name already sits in
  `figures/`; if it does not, render one there at about 200 DPI with pdftoppm or
  pymupdf before referencing it. Renderable formats: .avif, .gif, .jpeg, .jpg, .png, .svg, .webp.
- Write those PNG files into `figures/` and nowhere else — that folder is published, a
  new folder of your own is not.
- Use each figure's own caption. It was written from the rendered image by the agent that drew
  the figure. Do not invent new ones, and do not describe a figure you did not place on the page.
- Look at every figure before you place it. A figure whose axis labels are unreadable at the size
  you give it is worse than no figure. Any colour, marker, axis or panel the page names must be
  one the image actually has, encoding what the image says it encodes.
</figure_requirements>

<page_structure>
In this order, top to bottom:

1. HERO — the paper's title, the author line as the paper gives it, and a one-paragraph TL;DR in
   plain language: what was asked, what was found, and the single number that carries the finding.
   Not the abstract, and not a rewrite of it. Below it, every link the links section below
   lists, each at the exact URL given there.
2. CONTRIBUTIONS — the paper's actual contributions as three to five scannable cards, each a short
   heading plus one or two sentences. If the paper claims four things, show four cards, not five.
3. METHOD — a walkthrough a technically literate non-specialist can follow: what goes in, what
   happens to it, what comes out, and why the design is the way it is. Lead with the paper's own
   method figure when it has one.
4. RESULTS — the paper's real headline numbers, read out of `paper.tex` and the data
   files behind it, each next to what it was measured on and what it is being compared against.
   A number that is not in the paper does not go on the page, and neither does a comparison the
   paper did not make. If a slot has no number, drop the slot.
5. FIGURE GALLERY — every figure, each with its caption, click-to-enlarge into a lightbox that
   closes on Escape, on a click outside, and on a visible close control.
6. LIMITATIONS — what the paper says it does not show. Verbatim in substance; do not soften it.
7. FOOTER — every link from the links section again, and the citation if the paper carries one.

A sticky section navigation runs alongside all of it and marks where the reader currently is.
Do NOT write its highlighting yourself: hand-written ones kept a stale section lit after a jump
back to the top, or never reached the short last sections. Instead give the nav element a
`data-scrollspy` attribute, make each of its links `href="#<id of that section>"`, style thecurrent link through `a.active` (it also gets `aria-current`), and paste this script VERBATIM
into the page's script element at the end of the body. It lights the section in view, the last one once the page is
scrolled to its end, and nothing while the reader is above the first linked section:

```js
/* aii-scroll-spy v1: paste verbatim */
(function () {
  var links = [], targets = [];
  document.querySelectorAll('[data-scrollspy] a[href^="#"]').forEach(function (a) {
    var el = document.getElementById(a.getAttribute('href').slice(1));
    if (el) { links.push(a); targets.push(el); }
  });
  if (!links.length) return;
  var queued = false;
  function current() {
    var view = window.innerHeight;
    var doc = document.documentElement;
    var atEnd = window.scrollY > 0 && view + window.scrollY >= doc.scrollHeight - 2;
    var line = atEnd ? view - 1 : Math.min(view * 0.3, 200);
    var best = null, bestTop = -Infinity;
    targets.forEach(function (el) {
      var top = el.getBoundingClientRect().top;
      if (top <= line && top > bestTop) { best = el; bestTop = top; }
    });
    return best;
  }
  function update() {
    queued = false;
    var el = current();
    links.forEach(function (a, i) {
      var on = targets[i] === el;
      a.classList.toggle('active', on);
      if (on) a.setAttribute('aria-current', 'location');
      else a.removeAttribute('aria-current');
    });
  }
  function schedule() {
    if (!queued) { queued = true; window.requestAnimationFrame(update); }
  }
  window.addEventListener('scroll', schedule, { passive: true });
  window.addEventListener('resize', schedule);
  window.addEventListener('load', schedule);
  if (window.ResizeObserver) new ResizeObserver(schedule).observe(document.body);
  update();
})();
```
</page_structure>

<technical_requirements>
- ONE file. All CSS in a style element, all JavaScript in a script element, both inline in
  `index.html`. No build step, no bundler, no framework, no external script, stylesheet, web
  font or analytics — nothing fetched at load time. The page must render with the network off,
  and the only files it may point at are the figures listed above and the PDF beside it.
- System font stack only, since no font may be downloaded.
- Light theme. Responsive from a 360px phone to a wide desktop, with no horizontal page scroll;
  wide content scrolls inside its own container.
- Honour prefers-reduced-motion: under it, transitions and any scroll-driven effect stop.
- Keyboard-navigable: every control reachable by Tab in a sensible order, a visible focus ring,
  the lightbox trapping focus while open and returning it to the thumbnail on close, and a skip
  link to the main content.
- Semantic HTML: one top-level heading, headings that descend without skipping, landmark elements,
  and alt text on every image that says what the figure shows rather than repeating its number.
- No emoji anywhere. No purple-to-blue gradients. No decorative icon fonts.
- Keep the whole file comfortably under a megabyte.
</technical_requirements>

<writing_register>
Write in the register of the field's best papers (the paper this page presents, which was written to them), not in the register of a language
model. Four things are measured on the finished draft, and a draft outside them is sent back with
the numbers:
- Never use: delve, underscore, showcase, intricate, pivotal, realm, commendable, meticulous, tapestry, garner, multifaceted, it is worth noting, plays a crucial role, not only ... but also. These are 10 to 30 times more frequent in machine-written abstracts than in
  human ones, and reviewers read them as such.
- Em dashes: at most 3 per 1,000 words. Use a comma, a colon or a full stop.
- Sentence rhythm: mix short and long sentences. An interquartile range of sentence length under
  8 words reads as machine-written.
- Hedging: at most 15 hedges (may, likely, suggests, appears) per 1,000
  words. State what the evidence supports plainly; hedge where it is thin, not everywhere.
Style never changes substance: numbers, claims, citations and figure markers stay exactly as the
evidence gives them. The user's original request (delivered as a separate message) overrides all
of this wherever the two conflict.
</writing_register>

<links>
Use these URLs VERBATIM wherever the page links to the paper, the report or the code. Do not
shorten them, do not turn any of them into a relative path, and do not compose one of your own.

- The paper PDF, labelled "Read the paper (PDF)": https://cdn.jsdelivr.net/gh/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive@fork/run_2MI56L8wzgdI/paper.pdf
- The code repository, labelled "Code repository": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI
- The full research report — every experiment, every table and every dead end: https://cdn.jsdelivr.net/gh/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive@fork/run_2MI56L8wzgdI/report.pdf
  Label this one "Read the full research report" and place it BESIDE the paper link, never in place of it.
- The executive summary, the short read of the run, labelled "Read the executive summary": https://cdn.jsdelivr.net/gh/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive@fork/run_2MI56L8wzgdI/exec_summary.pdf
  Place it right beside "Read the full research report".
- The report of each research round, as ONE compact line introduced by "Round reports:" under the document links, each round labelled as given:
  - "Round 1": https://cdn.jsdelivr.net/gh/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive@fork/run_2MI56L8wzgdI/round-1/report.pdf
  - "Round 2": https://cdn.jsdelivr.net/gh/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive@fork/run_2MI56L8wzgdI/round-2/report.pdf
  - "Round 3": https://cdn.jsdelivr.net/gh/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive@fork/run_2MI56L8wzgdI/round-3/report.pdf
  - "Round 4": https://cdn.jsdelivr.net/gh/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive@fork/run_2MI56L8wzgdI/round-4/report.pdf
  - "Round 5": https://cdn.jsdelivr.net/gh/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive@fork/run_2MI56L8wzgdI/round-5/report.pdf

Each carries the branch this run publishes to. A link without it opens a DIFFERENT run's work —
it resolves and looks correct, which is why it must be copied rather than derived. They begin
resolving only after this run finishes publishing, so do NOT try to open or verify them.

The paper text carries a third kind of link, per claim rather than per paper: where it attaches a
\footnote{Code: \url{...}} to a sentence, that URL points at the exact code behind THAT claim.
Carry each one onto the page as an inline link on the corresponding sentence, using the URL
verbatim, the same way you use the ones above. Do not collapse them into the repository link.

Every artifact this run produced is published with its code. Link EACH of these, verbatim, from the part of the page that discusses that artifact, labelled as given or as the page's own name for it; one the page does not otherwise discuss goes in a short code list above the footer:
- "Code: Reserved Slovene/English refusal test sets and audit": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-1/dataset-1
- "Code: GaMS vs Gemma: does Slovene refusal training stay Slovene?": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-1/experiment-1
- "Code: Do base models set Slovene refusal? GaMS3 vs Gemma-3": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-1/experiment-2
- "Code: Does a Slovene persona gate Slovene refusal?": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-1/experiment-3
- "Code: Does English de-censoring also unlock Slovene?": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-1/experiment-4
- "Code: Slovene vs English refusal: GaMS3 vs Gemma-3 confirmation": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-2/experiment-5
- "Code: Refusal Depth Language Experiment Pipeline": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-2/experiment-6
- "Code: Does GaMS refuse like its Qwen teacher?": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-2/experiment-7
- "Code: Does English de-censoring hit Slovene harder?": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-2/experiment-8
- "Code: Re-scoring all first-round screens on one judge": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-2/evaluation-1
- "Code: Re-judging saved de-censoring outputs": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-3/evaluation-2
- "Code: Slovene refusal survives English de-censoring": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-3/experiment-9
- "Code: Why Slovene refusals survive an English de-censoring edit": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-3/experiment-10
- "Code: Confirming the Slovene refusal lag on untouched data (GaMS3 vs Gemma-3, iter 3)": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-3/experiment-11
- "Code: Does de-censoring hurt Slovene skills more?": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-3/experiment-12
- "Code: Paid judges re-score the Slovene refusal lag": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-4/evaluation-3
- "Code: Does Slovene refusal follow the prompt or the reply?": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-4/experiment-14
- "Code: Dense dose ladder for the Slovene refusal lag: a baseline offset, not an edit-induced hole": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-4/experiment-15
- "Code: Prior-art and fact check for the Slovene refusal study": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-4/research-1
- "Code: Does Gemma keep a Slovene safety reserve? (confirmation)": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-5/experiment-16
- "Code: One English edit unlocks both Slovene and English models": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-5/experiment-17
- "Code: Is Gemma's Slovene refusal real safety?": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-5/evaluation-4
- "Code: Tracing every paper number to saved results": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-5/evaluation-5
- "Code: Is the reply-language safety finding new?": https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_2MI56L8wzgdI/round-5/research-2
</links>

FIRST, add ALL of these to your todo list using your task/todo-tracking tool:

CRITICAL: Todo content must be copied exactly as is written here, with NO CHANGES. These todos are intentionally detailed so that another LLM could read each one without any external context and understand exactly what it has to do.

<todos>
TODO 1. Read and STRICTLY follow these skills: aii-web-tools.
TODO 2. Read `paper.tex` end to end and list `figures/`. Write down the
paper's title, its author line, its contributions, and every headline number together with the
sentence it appears in — those sentences are the only numbers allowed on the page. Note which
figures are PDFs and so need a PNG rendered.
TODO 3. Render a PNG at about 200 DPI, into `figures/`, for every figure not already
in a browser-renderable format, then LOOK at each image you plan to use so you know what it shows
and how large it has to be on the page to stay legible.
TODO 4. Write `index.html` following the page_structure and technical_requirements sections
above: one file, inline CSS and JavaScript, every image referenced through the published figure
prefix.
TODO 5. VERIFY THE NUMBERS: for each number on the page, grep `paper.tex` for it and
confirm it appears there with the same meaning. Delete any number you cannot find. Then confirm
every claim on the page is one the paper actually makes.
TODO 6. VERIFY THE PAGE: confirm `index.html` has no external script, stylesheet or font
reference; that every image path starts with the published figure prefix and names a file that
exists in `figures/`; and that the PDF, repository and artifact code links are
character-for-character the URLs given in the links section — including the research report,
executive summary and round report links when they are listed there — and not `paper.pdf` nor any URL you composed. Then open the page in a browser, screenshot it at a phone width and a desktop width,
read both screenshots, and fix anything cramped, overlapping or cut off. At the desktop width,
also screenshot the page scrolled to the top, the middle and the end, and confirm the nav marks
nothing, the section in view, and the last section respectively. `chromium-headless-shell`
is already installed: drive it with Playwright (`uv pip install playwright` in a scratch virtual
environment, then launch Chromium with `executable_path` set to the output of
`which chromium-headless-shell`, with no `playwright install`). Only if that command finds
nothing, run `playwright install --with-deps chromium` instead.
TODO 7. ACCESSIBILITY PASS: tab through the whole page and confirm every control is reachable with a
visible focus ring, the lightbox traps focus and closes on Escape, headings descend without
skipping, and every image has alt text. Fix what fails.
</todos>

---

Output the result as JSON to: `./.terminal_claude_agent_struct_out.json`

JSON Schema:
```json
{
  "$defs": {
    "PaperSiteExpectedFiles": {
      "description": "All expected output files from paper-site generation.",
      "properties": {
        "site_html_path": {
          "description": "Path to the single self-contained HTML page. Example: 'index.html'",
          "title": "Site Html Path",
          "type": "string"
        }
      },
      "required": [
        "site_html_path"
      ],
      "title": "PaperSiteExpectedFiles",
      "type": "object"
    }
  },
  "description": "Paper site \u2014 structured output from presentation-page generation.",
  "properties": {
    "summary": {
      "description": "Brief summary of the page you built: the sections it carries, which figures it shows, which numbers it quotes and where each came from in the paper.",
      "maxLength": 5000,
      "minLength": 300,
      "title": "Summary",
      "type": "string"
    },
    "out_expected_files": {
      "$ref": "#/$defs/PaperSiteExpectedFiles",
      "description": "All output files you created. Must include index.html."
    }
  },
  "required": [
    "summary",
    "out_expected_files"
  ],
  "title": "PaperSite",
  "type": "object"
}
```

IMPORTANT: this task is NOT complete until `./.terminal_claude_agent_struct_out.json` exists and contains JSON matching the schema above.

carry out the research described in the attached “GaMS3 vs Gemma 3: Bilingual Refusal Suppression and Mechanistic Analysis” document and produce a reproducible research repository and a paper based on the experiments you actually complete.

read the entire document before choosing an approach. use it as the primary research specification, distinguishing the frozen core design, required analyses, optional extensions, discussion points for human collaborators, and deferred journal follow-up. briefly state your understanding of these priorities, then proceed with feasibility checks and execution.

the main research questions and intended contribution are already defined. choose the implementation, mechanistic methods, measurements, and controls needed to test them rigorously. verify the document’s factual claims, references, and novelty positioning against primary sources. treat its proposed explanations as hypotheses to investigate, not conclusions to confirm.

treat the core study as the anchor, while leaving room for discoveries that emerge during execution. if pilot results reveal a promising mechanism, unexpected pattern, or weakness in the proposed explanation, investigate it even if the exact experiment is not specified in the document. you may refine hypotheses and add or replace optional analyses when justified by evidence. preserve the core comparison and independent evaluation, and explain why each departure improves the science. prioritize a focused, well-tested insight over accumulating loosely connected experiments.

use scientific judgment to identify methodological weaknesses and resolve implementation choices. make consequential corrections explicit. where the document assigns decisions to a collaborator, make and justify defensible provisional choices so independent work can continue. flag anything that genuinely requires human input or unavailable access. do not claim human review, developer consultation, or access to private checkpoints unless it actually occurred.

adapt execution to the available compute while prioritizing completion of the core study. start with small feasibility checks before scaling up. if a required component is infeasible, explain the blocker and complete the remaining independent work. clearly label any reduced-scope experiment or substitute and its limitations. keep the deferred journal project outside the main run.

keep exploration separate from confirmation. preserve the document’s data-separation rules and freeze the relevant protocol before final testing. actively challenge the strongest explanations using competing hypotheses, simple baselines, and appropriate controls. report uncertainty, failed hypotheses, and negative results. limit causal and generalization claims to what the design supports, and do not present a familiar finding as novel merely because it appears in GaMS or Slovene.

deliver code, pinned dependencies, configurations, data provenance and split manifests, saved experimental outputs and scores, analysis scripts, and a paper whose claims can be traced to those results. distinguish completed findings, exploratory evidence, and unexecuted proposals. recompute every headline number from saved results and, after the final audit, reconcile the abstract, figures, tables, and conclusions so they all reflect the strongest evidence that actually survives.
````

### [2] SKILL-INPUT — aii-web-tools · 2026-09-25 15:36:41 UTC

The agent loaded the **aii-web-tools** skill; its `SKILL.md` (the instructions injected into the agent's context) follows verbatim.

````
---
name: aii-web-tools
description: "Runs web search, page fetch as markdown, and regex grep over full HTML or PDF text via this skill's own scripts (aii_fast_web_search.py, aii_fast_web_fetch.py) — a free-first keyless search stack with Serper fallback that works even where built-in WebSearch and WebFetch are absent. Use when a query, page, or paper must be searched, read, or mined for an exact quote, number, table value, or methodology sentence, and whenever a lossy summary would lose the detail. Triggers: web search, scholarly search, OpenAlex, Crossref, Serper, fetch a URL as markdown, read a PDF, arXiv, regex grep a page, exact quote, table value, citation check. NOT for: planning a broad multi-source literature review or mass verification campaign — use aii-web-research-tools; NOT for a PDF file already on disk — extraction, form filling, merging and PDF creation are anthropic-pdf; NOT for driving a browser or testing a UI."
---

## Web tools

You have three web capabilities: **search**, **fetch**, and **grep** (exact
regex extraction over a full page or PDF).

**Pick where they come from, in this order:**

1. **If you have built-in `WebSearch` / `WebFetch` tools, PREFER those over the
   scripts below.** They may be **deferred tools** (listed by name but with
   schemas not yet loaded) — if so, call `ToolSearch("select:WebSearch,WebFetch")`
   ONCE to load them, then use them normally. Do not skip them just because they
   need that one extra load step; they are the preferred path. Pair them with the
   `aii_web_tools__fetch_grep` script below when you need exact text / numbers /
   methodology that a summary would miss, or when reading a PDF.
2. **Only if you have NO built-in `WebSearch` / `WebFetch`** (e.g. the OpenHands
   backend), use the scripts in this skill (below). They are our own
   implementations — free-first web search (keyless general/scholarly engines,
   Serper fallback), html2text + PyMuPDF for fetch, and regex grep over the full
   document text. They work without any built-in web tools.

Workflow either way: **search** (discover) → **fetch** (read for the gist) →
**grep** (pull exact details / read PDFs).

---

## Running the scripts

Run every script with the skill's pre-provisioned interpreter (it already has
`requests`, `html2text`, `pymupdf`, `python-dotenv`). Set `PY` once:

```bash
export SKILL_DIR="$(git rev-parse --show-toplevel 2>/dev/null || echo /ai-inventor)/.claude/skills/aii-web-tools"
export PY="$SKILL_DIR/../.ability_client_venv/bin/python"
```

### 1. Search the web (free-first: general or scholarly)

```bash
# general web (default): keyless engines (ddgs, marginalia); Serper only if they miss
$PY "$SKILL_DIR/scripts/aii_fast_web_search.py" --query "neuro-symbolic FOL translation LLM" --max-results 10
# scholarly mode: OpenAlex + Crossref (DOIs, citation counts)
$PY "$SKILL_DIR/scripts/aii_fast_web_search.py" --query "neuro-symbolic FOL translation" --mode scholarly
```

Returns ranked title / URL / snippet lines. `--mode general` (default) uses
keyless general engines; `--mode scholarly` uses academic APIs. Both fall back
to Serper (paid) only when the free engines miss. Use search first to scan the
landscape; snippets are for discovery only — fetch a page before judging it.

### 2. Fetch a page as markdown (HTML or PDF)

```bash
$PY "$SKILL_DIR/scripts/aii_fast_web_fetch.py" fetch --url "https://arxiv.org/abs/2303.11366" --max-chars 10000
```

`--max-chars` caps output (default 10000); `--char-offset N` pages further in.
Handles PDFs transparently via PyMuPDF.

### 3. Grep a page or PDF (exact regex extraction)

```bash
$PY "$SKILL_DIR/scripts/aii_fast_web_fetch.py" grep --url "https://arxiv.org/pdf/2303.11366" --pattern "verbal reinforcement" --max-matches 20 --context-chars 200
```

Returns only the matching sections with surrounding context — the right tool
for exact numbers, table values, methodology, or long PDFs where a summary
would lose the detail. `-i` for case-insensitive.

**Parallelize** independent searches/fetches in one turn; only sequence a
fetch after the search that produced its URL.

---

## Notes

- The scripts call our ability server. If a script prints
  `Ability service not available`, the server is down — say so rather than
  silently improvising a different search method.
- Do **not** hand-roll your own `requests`/scraping for search when these
  tools are available: Serper returns clean Google results and the fetch/grep
  scripts already handle HTML, PDFs, and encoding.
````

### [3] SKILL-INPUT — artifact-design · 2026-09-25 15:38:30 UTC

The agent loaded the **artifact-design** skill.

```
Tool: Skill
artifact-design
```

### [4] SYSTEM-USER prompt · 2026-09-25 15:44:35 UTC

```
[Image: original 375x10017, displayed at 75x2000. Multiply coordinates by 5.00 to map to original image.]
```

### [5] SYSTEM-USER prompt · 2026-09-25 15:46:10 UTC

```
SITE VERIFICATION FAILED: 1 problem(s) in index.html.

- image source '' does not start with 'figures/', so it will not resolve once the page is published beside its figures folder

You MUST:
1. Fix every problem listed above in index.html.
2. Keep the page ONE self-contained file — all CSS and JavaScript inline, no external scripts, stylesheets or web fonts, nothing fetched at load time.
3. Point every image at figures/<filename>, where <filename> is a browser-renderable image that really exists in your figures/ folder. A vector PDF figure needs a PNG rendered beside it first; reference the PNG.
4. Re-open the page and confirm it still renders before finishing.
```

### [6] SYSTEM-USER prompt · 2026-09-25 15:47:12 UTC

```
SITE VERIFICATION FAILED: 1 problem(s) in index.html.

- image source '' does not start with 'figures/', so it will not resolve once the page is published beside its figures folder

You MUST:
1. Fix every problem listed above in index.html.
2. Keep the page ONE self-contained file — all CSS and JavaScript inline, no external scripts, stylesheets or web fonts, nothing fetched at load time.
3. Point every image at figures/<filename>, where <filename> is a browser-renderable image that really exists in your figures/ folder. A vector PDF figure needs a PNG rendered beside it first; reference the PNG.
4. Re-open the page and confirm it still renders before finishing.
```
