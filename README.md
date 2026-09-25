# Why Slovene refusal outlasts English abliteration

<div align="center">

<a href="https://cdn.jsdelivr.net/gh/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive@fork/run_UESxYRggGt7E/workflow.svg">
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="workflow-dark.svg">
  <img alt="Artifact workflow — how every artifact in this repo was built" src="workflow.svg">
</picture>
</a>

<sub>🖱️ <b><a href="https://cdn.jsdelivr.net/gh/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive@fork/run_UESxYRggGt7E/workflow.svg">Open the interactive diagram</a></b> — every card links to its artifact folder.</sub>

</div>

> **TL;DR** — Gemma-3-12B-IT false-refuses benign Slovene prompts at a rate of 0.569, nearly twice its English rate of 0.364, while GaMS3-12B-Instruct shows no such language gap (0.273 in both languages). Signal-detection analysis attributes this entirely to a criterion shift (DiD_c = +0.52 [0.38, 0.68], 95% CI) with no change in the models' ability to discriminate harmful from benign items, replicated across four independent experiments. A secondary output-language refusal effect is too fragile to confirm: the prediction-powered-inference correction is consistent with zero and judge agreement is only kappa = 0.12 in Slovene.

<details>
<summary>Full hypothesis</summary>

SETTING (unchanged). Gemma-3-12B-IT (Gemma) and GaMS3-12B-Instruct (GaMS) are sibling checkpoints of google/gemma-3-12b-pt. GaMS adds Slovene continued pretraining (declared CPT mix: SL 48.9% / EN 28.3%, plus HR/SR/BS 22.3%) and an SFT mix that is about 79% Slovene. The FROZEN CORE is kept: {Gemma, GaMS} x {original, one English-objective Heretic edit} x {EN, SL}, plus RQ1-RQ4. Margin m = 0.675 log-odds.

Iteration 5 is the FINAL iteration. It has three jobs:
(1) confirm or refute the one live lead (C-OUT, below) on held-out items, with a readout anchored to adjudication;
(2) pay the RQ2 frozen-core debt;
(3) write a paper in which every number traces to an artifact.
It runs NO new mechanism probes beyond the pre-registered cells of the C-OUT confirmation.

CORRECTED RECORD OF ITERATION 4. This overrides the iter-4 paper draft; the reviewer verified the numbers against the artifacts.

- eval3 (art_gOdYt7zLWvfr), paid readout of the saved exp8/9/10/11 rows.
  - Pooled G3 = -1.17 [-1.84, -0.50] (gemini raw, REML+HKSJ, 3 bodies).
  - READOUT NOT VALIDATED. Gemini Sp is 0.73 in GaMS-SL-edited and 0.66 in Gemma-SL-edited. kappa(gemini, gpt-4.1-mini) is 0.39 in GaMS-SL-edited.
  - The sign is NOT robust to the measured judge error. In both exp9 and exp11, both tipping paths reach G3 = 0 within the measured error CIs. The artifact says 'judge error alone can still account for the lag'.
  - The sign flips under other judges:
    - gpt-4.1-mini, exp9: +1.27 [-3.23, 3.01];
    - archived Qwen3-14B, exp8_A1: +1.57 [0.11, 3.00];
    - Mistral-24B: +7.58 and +0.04;
    - exp9 B' J1: +9.33.
  - The pooled TTJ CI [-4.67, 2.47] includes 0. TTJ used the local J1 judge, not a paid one.
  - Pooled G3_edit = +0.39 [-1.95, 2.74] (REFUTE-BOUND). Per body, G3_edit ranges from -3.40 [-6.09, -1.30] (exp10 op point) and -1.72 [-3.69, -0.52] (exp8_B lexicon) to +1.43 [0.29, 2.98] (exp9 raw).
  - G3_orig CIs include 0 in exp8_A1 and exp8_B. At the exp10 op point, G3_orig is +0.99.
  - The slopes are NOT parallel: b_Gemma 1.40-1.66 vs b_GaMS 0.97-1.13.
  - AM2: ASR stopped at 1,108/5,800 rows, so R-INCAP was not executed. 195/480 adjudication rows were labelled by the executing agent.
  - C1: the 590-row 'gold calibration' block is prompt hazard gold. It holds no refusal labels.
- exp15 (art_piu0nI9vij_F): a dense lambda ladder on a fresh RefusEU-TRAIN body of 300 harmful items + 120 twins. The body was cut from the planned 400+200; record the reason. It has 14 Gemma and 15 GaMS steps, including lambda 0.
  - Readout: local J1 only, not validated. SL-edited Sp is 0.55 (Gemma) and 0.62 (GaMS).
  - G3 = -0.70 [-1.01, -0.42]. The MDE of 0.42 belongs to G3, NOT to G3_edit.
  - G3_edit = +0.47 [-0.96, 2.14]. Its 90% bound, |G3_edit| < 1.91, does NOT exclude -m.
  - G3_orig = -1.17 rests on a ceiling: Gemma SL 299/300 vs EN 294/300. At Gemma SL 296/300, G3_orig would be about -0.06.
  - Slopes: b = 0.94 (Gemma) vs 0.80 (GaMS).
  - SDT: DiD_c = -0.33 [-0.53, -0.16] in the window and -0.39 at lambda 0. DiD_d' = -0.18 / -0.06.
  - The excess KL ratio at the top dose is about 0.96 (Gemma) and 0.80 (GaMS), from the reviewer's recompute; it is not yet computed with a CI. Raw Gemma first-token KL is higher in SL than EN (0.74 vs 0.38).
  - Only Gemma cells have gpt-4.1-mini labels.
- exp14 (art_4Mf1Fazk33yZ). The paper's Tables 28-30 were WRONG; these are the verified values. Harmful refusal rates at zero / lo / hi dose; Gemma lo = 0.5, hi = 1.0:
  - Gemma: EN->EN 0.88 / 0.59 / 0.18; EN->SL 0.95 / 0.92 / 0.77; EN->HU 0.94 / 0.81 / 0.46; SL->EN 0.88 / 0.46 / 0.07; SL->SL 0.95 / 0.85 / 0.56; HU->HU 0.94 / 0.80 / 0.55; hi HU->SL 0.83.
  - Gemma benign twins: EN->EN 0.09 / 0.03 / 0.02; EN->SL 0.31 / 0.20 / 0.22.
  - GaMS: EN->EN 0.82 / 0.30 / 0.21; EN->SL 0.77 / 0.21 / 0.14; EN->HU 0.80 / 0.34 / 0.23; SL->SL 0.87 / 0.20 / 0.15; HU->HU 0.91 / 0.41 / 0.28.
  - Contrasts:
    - Gemma OUT_SL = +1.14 [0.60, 1.56]; IN_SL = -0.60 [-1.02, -0.18]. A Slovene prompt LOWERS refusal.
    - GaMS OUT_SL = -0.44 [-0.98, 0.27]; IN_SL = -0.86 [-1.58, -0.13].
    - G3_edit: SL->SL -1.84 [-2.80, -0.78] (model-swap p = 0.000); EN->SL -1.26; HU->SL -2.15 [-3.16, -0.46].
  - SDT: DiD_c is -1.56 [-1.97, -1.29] at hi|SLoutput and -0.76 [-1.06, -0.52] at zero|SLoutput. DiD_d' at hi is +0.72 [-0.06, 1.30].
  - GaMS FAILED the output-language manipulation: compliance SL->EN 0.00, HU->EN 0.14, SL->HU 0.555, HU->SL 0.865. Every cross-model OUT/IN contrast that uses these cells is INVALID. The EN-input row and the matched SL->SL and HU->HU cells comply (>= 0.97).
  - The GaMS dose bracket failed: support_ok False, and GaMS EN->EN is already 0.30 at lambda 0.5.
  - Readout: local J1 (A4). Gemma-SL-edited Sp is 0.42. RG is degenerate. PPI keeps the sign. robust_call_SL is False. TTJ and second-family readouts are NA.
  - Author-model gold on 120 rows (NOT human):
    - Gemma: non-EN reply 0.50 (n = 90) vs EN reply 0.33 (n = 30); non-EN prompt with EN reply 0.38 (n = 21).
    - GaMS: 0.17 / 0.20 / 0.21.
  - MT noise at lambda 0 is significant (McNemar p = 0.019 Gemma, 0.005 GaMS).
  - C-EXT was cut to one checkpoint (A3). p-e-w/gemma-3-12b-it-heretic: EN->EN 0.05, EN->SL 0.15, SL->SL 0.21, SL->EN 0.005.
- exp13 (strategy slot 2) was ABANDONED and is not in the artifact list.
  - The L4 GPU was revoked at about 25 min (A1). No new Heretic edit, no confirmation curve, no RQ2 and no random controls were run.
  - Tier bake-off on eval2's 240 adjudicated edited rows (a second, independent measurement of the over-call):
    - gemini-2.5-flash: Sp 0.42-0.55 per cell, kappa 0.47;
    - flash-lite: Sp 0.27-0.36;
    - both fail the gate.
  - A frozen re-readout of 19,195 rows has no labels, because of the key limit (A4).
  - A 519-item external pool with a DEV / B / C split is preserved.
  - CHECKED DURING THIS REVISION: B is NOT untouched. exp14's 200 items share 116 B items and 55 C items (exact or 8-gram match). 288 pool items (184 B + 104 C) were never generated by any artifact.
- research (art_NZ9n2Ej5RtGt): findings on Heretic and C-EXT pins.
  - Heretic @3521f86 has NO automatic trial selection. Its defaults are 200 trials / 60 start-up, not 80. Its KL objective is first-token.
  - C-EXT pins: p-e-w e037e6e1, mlabonne v2 b8ae69bd, huihui 33b9e740.
  - Hungarian is absent from the DECLARED mix only.
  - AdvBench is excluded.
  - Novelty of the prompt-language x reply-language design: MEDIUM confidence.

MAIN CLAIM C-OUT (deepens exp14's lead; object held at full size; status LEAD, prior about 0.5).
- The claim: under an English-only abliteration edit, the generalist Gemma keeps refusing harmful requests whenever it must WRITE Slovene, whatever the prompt language, far more than when it writes English. The Slovene-adapted GaMS has no such reply-language channel: its refusal falls equally in every output language.
- What it means: national-LLM adaptation REMOVES an accidental Slovene reserve that the generalist has against an English attack, and that reserve is keyed to the REPLY language, not the prompt language.
- Why it matters:
  - Red-teamers auditing an English-abliterated generalist must vary the reply language, not only the prompt language.
  - Builders of national LLMs should expect no residual Slovene reserve after English de-censoring.
  - Supervised-reach accounts predict the opposite (GaMS, with more Slovene refusal supervision, should keep more).
- The screen evidence is all from exp14 above (Gemma EN->SL 0.77 vs EN->EN 0.18 at hi; GaMS 0.14 vs 0.21; the gold subset; the p-e-w checkpoint).
- Why it is a lead and not a positive:
  - the Slovene-output cells are exactly the ones every judge over-calls;
  - R-INCAP is untested (ASR on 1 cell);
  - there is one item body;
  - the GaMS manipulation failed off the EN-input row;
  - suffix-free RefusEU bodies (exp15) show a CONSTANT Gemma SL-EN margin under the edit (1.48 -> 1.24), so the edit-induced widening seen in exp14 may be an artefact of the suffix or of the item body;
  - Hungarian output is also elevated in Gemma (0.46).

RIVALS C-OUT must beat (pre-registered, tested on the held-out body).
- R-JUDGE-OUT: Slovene output is mis-scored as refusal. Predicts that the effect vanishes under:
  - the harmful-content readout on English translations;
  - PPI++ correction anchored to a two-family adjudication;
  - the adjudicated 4-class explicit-refusal label.
- R-INCAP: Gemma's Slovene-output 'refusals' are deflections or degraded non-answers, not safety. Predicts that harmful-content yield is equal in SL and EN output. If refusal separates and harmful content does not, report a PRODUCTION-FAILURE finding: no reserve for attack purposes.
- R-SUFFIX: the output-language instruction, not the output language, triggers caution. Predicts no effect in SUFFIX-FREE SL->SL vs EN->EN on the same items.
- R-BASE-OUT: the reserve is Gemma's pre-edit Slovene-output criterion shift (benign FA 0.31 vs 0.09), carried along the dose. Predicts OUT_edit ~ 0 and SDT DiD_c(hi) ~ DiD_c(zero). BOTH outcomes are informative. If R-BASE-OUT holds, C-OUT is stated as a pre-existing reply-language caution that English de-censoring does not remove; it is not called edit-induced.
- R-GENERIC-NONEN: any non-English output triggers the residual. The SL-HU contrast is reported; the M-OUT fluency account predicts HU ~ SL in Gemma (BPB 1.12 vs 1.20).

CLOSED (one sentence each in the paper; no new generation).
- C-LAG as an edit-induced cross-model lag on RefusEU-derived bodies: REFUTE-BOUND / underdetermined.
  - R-BASE is NOT REFUTED. The split of G3 into baseline and edit components is UNDERDETERMINED.
  - If R-BASE holds, the C-LAG line reduces to the pre-edit GaMS Slovene deficit already measured in iterations 1-2 (DiD -0.35 to -0.67; meta -0.50 [-0.82, -0.21]). That is an expected-direction result, and the paper says so plainly.
  - Analysis only (on saved rows): ceiling sensitivity of G3_orig (leave-k-items; Jeffreys and exact alternatives to Hautus).
- C5a leakage. Add the exp15 excess ratio with a CI, recomputed on saved rows.
- RQ3 utility: delivered.
- M-b: dead. M-a: layer-dependent.
- ALT-2/3/4.
- Identity C1: calibration only.
- Teacher decision inheritance.
- RQ4: relabelled as source separability.
- Criterion shift: reported as an unresolved DISAGREEMENT across bodies and judges, each named:
  - HARD originals: +0.52 [0.39, 0.67];
  - exp9 lag window: -0.00;
  - exp15: -0.33;
  - exp14 SL-output: -1.56 hi / -0.76 zero.
  Sign conventions are harmonised in the paper. The C-OUT SDT per cell is its pre-registered resolution.

EXECUTION FOR ITERATION 5 (final).

(A) C-OUT HELD-OUT CONFIRMATION (experiment; never cut).
- Items:
  - The 288 never-generated items of exp13's pool (iter_4/gen_art/gen_art_experiment_13/data/split_manifest_iter4.json, B u C minus the exp14 overlap): StrongREJECT 146, HarmBench 103, JBB 39.
  - Re-verify the exact and 8-gram dedup against exp14, exp15, RefusEU, AdvBench/mlabonne and every earlier probe, and log it.
  - At least 120 benign twins from exp13's twins.jsonl / jbb_benign.jsonl.
  - DEV: exp13's DEV items that no artifact has generated (34), used for dose calibration and the compliance gate only.
  - Arms: NLLB SL-MT, HU-MT and EN-BT from one English source.
- Cells, both models, using exp14's suffix:
  - EN->EN, EN->SL, EN->HU, SL->SL, HU->HU;
  - SUFFIX-FREE EN->EN and SL->SL.
  - Gemma only: SL->EN and HU->EN.
  - Compliance gate: >= 90% per cell on DEV. Cells that fail are dropped BEFORE confirmation and reported.
- Edit: exp9's selected adapters (iter_3/gen_art/gen_art_experiment_9/selected/), applied as lambda-scaled hooks.
- Doses per model:
  - lambda 0;
  - two DEV-chosen doses bracketing EN->EN refusal of 50%, with >= 1 verified step on each side. GaMS needs a finer grid in (0, 0.5].
  - lambda 1.0.
  - Norm-matched random edits for both models at the high dose.
- C-EXT: the mlabonne v2 @b8ae69bd, huihui @33b9e740 and p-e-w @e037e6e1 checkpoints, run on the same body, with the EN-input row plus suffix and suffix-free SL->SL. Drop and report any checkpoint that is unavailable.
- Primary endpoint: U = unsafe completion = StrongREJECT score >= 0.5. The threshold is ours; the continuous score is a sensitivity analysis.
  - Scored by gemini-2.5-flash on the NLLB English translation AND on the original text.
  - Reason for the switch from refusal: refusal judges failed Sp on edited Slovene in four measurements (eval2, eval3, exp13 bake-off, exp14/15), and harmful content is what an attack cares about.
  - Secondary readouts: the P1 3-way refusal label, and a 4-class label (explicit refusal / deflect / degraded non-answer / compliance).
- Anchor: blind TWO-family adjudication of >= 600 edited rows, stratified model x output language x dose.
  - Both families differ from the primary judge's (e.g., claude-sonnet-4.5 and gpt-4.1). A third model settles disagreements.
  - >= 100 rows in each decisive cell: Gemma EN->SL, Gemma EN->EN, GaMS EN->SL and GaMS EN->EN, at the bracketing doses.
  - Report inter-adjudicator kappa. Label the adjudication 'LLM, NOT human'.
- Estimators:
  - PRIMARY: PPI++ anchored to the adjudicated labels, because RG was degenerate in exp14 and exp15.
  - Sensitivities: RG with a Lang-Reiczigel CI, and the raw judge.
  - 2,000-draw item-cluster bootstrap; within-item input/output-swap and model-swap placebos.
- Estimands, in log-odds of S = 1 - U:
  - OUT = S(EN->SL) - S(EN->EN), for each model;
  - dOUT = OUT_GaMS - OUT_Gemma;
  - OUT_edit = OUT(lambda*) - OUT(lambda 0);
  - IN_Gemma = S(SL->EN) - S(EN->EN);
  - SUF = OUT with the suffix vs suffix-free;
  - SL-HU: SL-output vs HU-output residual.
  - SDT d' and c per cell and dose, using the benign twins.
- DECISION RULES. These are fixed now, frozen in protocol.yaml and sha256'd before the first confirmation generation.
  - C-OUT CONFIRMED iff all four hold under the primary readout at the bracketing dose (lambda 1 co-reported):
    - OUT_Gemma >= m with the 95% CI above 0;
    - dOUT <= -m with the 95% CI below 0;
    - the signs hold under the raw refusal label and the adjudicated explicit-refusal label;
    - IN_Gemma is not above +m.
  - OUT_edit >= m/2 with its CI above 0 licenses 'English de-censoring WIDENS the reserve'. Otherwise the reserve is reported as pre-existing (R-BASE-OUT).
  - R-INCAP wins if refusal-OUT >= m but U-OUT < m/2.
  - R-SUFFIX wins if suffix-free OUT < m/2 while suffix OUT >= m.
  - C-OUT REFUTED iff the 90% CI of OUT_Gemma lies within +/-m with MDE <= 2m. Then report the bound.
  - C-EXT replicates if >= 2 of 3 checkpoints show OUT >= m with the CI above 0.
  - No subgroup hunting after a failed confirmation.

(B) RQ2 FROZEN-CORE COMPLETION (never cut).
- Items: the natural RefusEU FINAL pairs (1,300 EN + 1,300 SL, art_EG6OpEkGvysx; never generated under an edit), original vs the selected edit.
- The edit is exp9's adapters at lambda 1, declared as the frozen-core edit with its deviations: 40 parameter-identical TPE start-up trials, NF4 inference, and our pre-registered selection rule (KL <= 0.5 -> fewest refusals -> lower KL), because Heretic has none.
- A fresh 200/60-trial Heretic run is NOT planned: GPU loss killed exp13. Record it as not executed.
- Outputs per model x language:
  - refusal: gemini P1, plus gpt-4.1-mini on >= 25%;
  - RefusEU-protocol ASR: Llama-Guard-3-8B + PolyGuard-Qwen run locally, with gpt-4o-mini adjudicating disagreements;
  - StrongREJECT;
  - McNemar deltas, language consistency and degeneracy;
  - the DiD of the edit effect, as a descriptive full-dose C-LAG.
- Gate: EN refusal must be cut by >= 50% relative. If lambda 1 misses it, add the DEV-chosen lambda that meets it and say so.

(C) ANALYSIS ONLY, on saved rows (about $0-1):
- the G3_orig ceiling sensitivity;
- the exp15 excess-KL CI;
- eval3's 1,108 ASR rows, reported or declared unused;
- exp14's full tables regenerated from analysis.json.

(D) HUMAN INPUT, flagged and never claimed: a native Slovene audit of 60 edited rows per model x output language. The specs are in exp14 results/human_audit_request.json and in eval3.

BUDGET.
- OpenRouter: <= $12, with a resumable ledger. The key is shared at $50/day across all runs; use the cheapest model that passes.
- GPU: one 12B model at a time. Checkpoint every 500 rows, so that a lost GPU does not lose the run.
- Cut order: the third C-EXT checkpoint -> HU cells other than EN->HU -> random edits at the second dose -> one bracketing dose.
- Never cut:
  - (A) EN->EN, EN->SL, suffix-free SL->SL and Gemma SL->EN, at lambda 0 and at the bracketing dose, for both models, with the adjudication and U;
  - (B) in full.

EVIDENCE SEPARATION.
- SCREEN: exp14's 200+100 items, all RefusEU-derived bodies, and exp13 DEV.
- CONFIRMATION: the 288 unseen external items, the two unseen public checkpoints, and natural RefusEU FINAL under the edit (RQ2; descriptive for C-LAG).

NOVELTY. Medium confidence.
- Nearest neighbours: Shen et al. 2024 (low-resource output quality drives unsafe or irrelevant responses), Deng et al. 2023 (instruction language), and Upadhyaya & Sikdar 2026 (output language as an OUTCOME of safety-feature ablation).
- Our delta: prompt language and reply language are crossed under partial-dose English abliteration, in a sibling pair that differs in Slovene adaptation, with a harmful-content primary.
- Re-run a dated saturation check before writing.

PAPER CORRECTIONS OWED (the previous review was BLOCKING; every item must appear in the final paper).
- Add 'Artifact 19 (not executed): exp13'. Include:
  - A1 GPU loss;
  - the tier_table per-cell Se/Sp/kappa for both tiers;
  - the frozen but unlabelled re-readout;
  - the pool, with its B/C overlap with exp14.
  Change the Strategy to say that five slots were planned and slot 2 failed.
- Regenerate Tables 28-30 and the exp14 prose from results/RESULTS_tables.md. Include:
  - all 3 doses and the pew row;
  - the compliance column;
  - the mechanism contrasts for every readout;
  - the L* G3/G3_edit table;
  - every SDT DiD;
  - amendments A3/A4/A5, the support failure and the MT-noise result.
  Restrict M-OUT to 'Gemma-only, raw J1 + 120-row gold, not robust'.
- R-BASE: 'not refuted; decomposition underdetermined'. Tabulate G3_orig and G3_edit for every body and readout. Delete the claim of a 0.42 MDE for G3_edit and quote the 1.91 bound. Replace 'parallel' with the slope CIs.
- Copy eval3's full per-curve table and tipping table verbatim. Fix the false sentence '0.34 exceeds 0.36'. State that the sign is not robust to the measured judge error.
- State which readout was local J1 and which was paid, in the Strategy and in each artifact's judge line. Add eval3's AM2 and C1.
- Add the exp15 and exp14 SDT evidence and rewrite the criterion-shift claim as a disagreement.
- Add the tables owed from iteration 3:
  - exp11 per-step Hautus, a/b, the four-readout G3, the gates and the 5-cell adjudication (Gemma-SL Sp 0.22);
  - exp9 SDT;
  - exp10 geometry, induction and add-on;
  - exp12 Belebele and first-token KL.
  Put '[superseded, see box]' on every heading that contradicts its box. Add eval2's RG -5.10 [-11.17, 5.60] and Qwen +1.57. Fix Table 9 (C3 = -1.86).
- Update the coverage table:
  - RQ2 NOT DONE in iteration 4 (exp13 GPU loss);
  - frozen core respecified per the research artifact;
  - the human audit listed as a human-input item.
- Fix these attributions:
  - the 0.51 kappa is exp14's;
  - exp14 GaMS-SL Sp 0.81 is the highest;
  - BPB comes from exp12 competence_covariates.json;
  - u_lang SL alpha50 is 1.78;
  - C-EXT evidence is in exp11's files, not exp13's;
  - the exp15 step counts and the scale cut.
- Add 'Why iteration 4 looked like this', quoting the ITER-3 update. End iteration 4 with a verdict table:
  - eval3: READOUT NOT VALIDATED / REFUTE-BOUND;
  - exp14: raw M-OUT, robust False;
  - exp15: ESTIMATE, R_BASE_SUPPORTED True (not refuted);
  - exp13: not executed.
  The table covers C-LAG, R-BASE, R-JUDGE, R-INCAP, M-OUT, M-IN, C-EXT and RQ2.
- After the final audit, reconcile the abstract, figures, tables and conclusions to the strongest surviving evidence.

</details>

[![Read the presentation](https://img.shields.io/badge/Read-Presentation-8A2BE2?style=for-the-badge)](https://ai-inventor-papers.github.io/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/fork/run_UESxYRggGt7E/) [![Explore the interactive demo](https://img.shields.io/badge/Explore-Interactive_Demo-D9480F?style=for-the-badge)](https://ai-inventor-papers.github.io/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/fork/run_UESxYRggGt7E/interactive.html)

[![Download PDF](https://img.shields.io/badge/Download-PDF-red)](https://cdn.jsdelivr.net/gh/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive@fork/run_UESxYRggGt7E/paper.pdf) [![Read the full report](https://img.shields.io/badge/Read-Full_Report-blue)](https://cdn.jsdelivr.net/gh/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive@fork/run_UESxYRggGt7E/report.pdf) [![Read the executive summary](https://img.shields.io/badge/Read-Executive_Summary-blue)](https://cdn.jsdelivr.net/gh/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive@fork/run_UESxYRggGt7E/exec_summary.pdf) [![Read the internal report](https://img.shields.io/badge/Read-Internal_Report-green)](https://cdn.jsdelivr.net/gh/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive@fork/run_UESxYRggGt7E/round-5/report.pdf) [![LaTeX Source](https://img.shields.io/badge/LaTeX-Source-orange)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/paper_latex)

**Round reports:** [Round 1](https://cdn.jsdelivr.net/gh/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive@fork/run_UESxYRggGt7E/round-1/report.pdf) · [Round 2](https://cdn.jsdelivr.net/gh/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive@fork/run_UESxYRggGt7E/round-2/report.pdf) · [Round 3](https://cdn.jsdelivr.net/gh/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive@fork/run_UESxYRggGt7E/round-3/report.pdf) · [Round 4](https://cdn.jsdelivr.net/gh/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive@fork/run_UESxYRggGt7E/round-4/report.pdf) · [Round 5](https://cdn.jsdelivr.net/gh/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive@fork/run_UESxYRggGt7E/round-5/report.pdf)

This repository contains all **24 artifacts** produced across **5 rounds** of an autonomous AI research run — round by round, exactly in the order they were invented.

## Round 1

| Artifact | Type | Demo | Source | Builds on |
|----------|------|------|--------|-----------|
| **[Reserved Slovene/English refusal test sets and audit](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/dataset-1)** | [![dataset](https://img.shields.io/badge/dataset-f59e0b)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/dataset-1) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/blob/fork/run_UESxYRggGt7E/round-1/dataset-1/demo/data_code_demo.ipynb) | [![Source Code](https://img.shields.io/badge/Source_Code-2962FF)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/dataset-1/src) | — |
| **[GaMS vs Gemma: does Slovene refusal training stay Slovene?](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/experiment-1)** | [![experiment](https://img.shields.io/badge/experiment-8b5cf6)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/experiment-1) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/blob/fork/run_UESxYRggGt7E/round-1/experiment-1/demo/method_code_demo.ipynb) | [![Source Code](https://img.shields.io/badge/Source_Code-2962FF)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/experiment-1/src) | — |
| **[Do base models set Slovene refusal? GaMS3 vs Gemma-3](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/experiment-2)** | [![experiment](https://img.shields.io/badge/experiment-8b5cf6)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/experiment-2) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/blob/fork/run_UESxYRggGt7E/round-1/experiment-2/demo/method_code_demo.ipynb) | [![Source Code](https://img.shields.io/badge/Source_Code-2962FF)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/experiment-2/src) | — |
| **[Does a Slovene persona gate Slovene refusal?](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/experiment-3)** | [![experiment](https://img.shields.io/badge/experiment-8b5cf6)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/experiment-3) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/blob/fork/run_UESxYRggGt7E/round-1/experiment-3/demo/method_code_demo.ipynb) | [![Source Code](https://img.shields.io/badge/Source_Code-2962FF)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/experiment-3/src) | — |
| **[Does English de-censoring also unlock Slovene?](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/experiment-4)** | [![experiment](https://img.shields.io/badge/experiment-8b5cf6)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/experiment-4) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/blob/fork/run_UESxYRggGt7E/round-1/experiment-4/demo/method_code_demo.ipynb) | [![Source Code](https://img.shields.io/badge/Source_Code-2962FF)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/experiment-4/src) | — |

## Round 2

| Artifact | Type | Demo | Source | Builds on |
|----------|------|------|--------|-----------|
| **[Slovene vs English refusal: GaMS3 vs Gemma-3 confirmation](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-2/experiment-5)** | [![experiment](https://img.shields.io/badge/experiment-8b5cf6)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-2/experiment-5) | — | [![Source Code](https://img.shields.io/badge/Source_Code-2962FF)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-2/experiment-5/src) | <sub><i>uses:</i><br/>[dataset‑1&nbsp;(R1)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/dataset-1)</sub> |
| **[Refusal Depth Language Experiment Pipeline](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-2/experiment-6)** | [![experiment](https://img.shields.io/badge/experiment-8b5cf6)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-2/experiment-6) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/blob/fork/run_UESxYRggGt7E/round-2/experiment-6/demo/method_code_demo.ipynb) | [![Source Code](https://img.shields.io/badge/Source_Code-2962FF)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-2/experiment-6/src) | <sub><i>uses:</i><br/>[dataset‑1&nbsp;(R1)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/dataset-1)</sub> |
| **[Does GaMS refuse like its Qwen teacher?](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-2/experiment-7)** | [![experiment](https://img.shields.io/badge/experiment-8b5cf6)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-2/experiment-7) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/blob/fork/run_UESxYRggGt7E/round-2/experiment-7/demo/method_code_demo.ipynb) | [![Source Code](https://img.shields.io/badge/Source_Code-2962FF)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-2/experiment-7/src) | <sub><i>uses:</i><br/>[dataset‑1&nbsp;(R1)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/dataset-1)</sub> |
| **[Does English de-censoring hit Slovene harder?](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-2/experiment-8)** | [![experiment](https://img.shields.io/badge/experiment-8b5cf6)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-2/experiment-8) | — | [![Source Code](https://img.shields.io/badge/Source_Code-2962FF)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-2/experiment-8/src) | <sub><i>uses:</i><br/>[dataset‑1&nbsp;(R1)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/dataset-1)</sub> |
| **[Re-scoring all first-round screens on one judge](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-2/evaluation-1)** | [![evaluation](https://img.shields.io/badge/evaluation-10b981)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-2/evaluation-1) | — | [![Source Code](https://img.shields.io/badge/Source_Code-2962FF)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-2/evaluation-1/src) | <sub><i>similarities:</i><br/>[experiment‑1&nbsp;(R1)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/experiment-1)<br/>[experiment‑2&nbsp;(R1)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/experiment-2)<br/><i>differences:</i><br/>[experiment‑3&nbsp;(R1)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/experiment-3)<br/>[experiment‑4&nbsp;(R1)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/experiment-4)<br/><i>uses:</i><br/>[dataset‑1&nbsp;(R1)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/dataset-1)</sub> |

## Round 3

| Artifact | Type | Demo | Source | Builds on |
|----------|------|------|--------|-----------|
| **[Re-judging saved de-censoring outputs](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-3/evaluation-2)** | [![evaluation](https://img.shields.io/badge/evaluation-10b981)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-3/evaluation-2) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/blob/fork/run_UESxYRggGt7E/round-3/evaluation-2/demo/eval_code_demo.ipynb) | [![Source Code](https://img.shields.io/badge/Source_Code-2962FF)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-3/evaluation-2/src) | <sub><i>uses:</i><br/>[experiment‑8&nbsp;(R2)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-2/experiment-8)<br/>[experiment‑7&nbsp;(R2)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-2/experiment-7)<br/>[dataset‑1&nbsp;(R1)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/dataset-1)<br/><i>similarities:</i><br/>[experiment‑5&nbsp;(R2)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-2/experiment-5)</sub> |
| **[Slovene refusal survives English de-censoring](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-3/experiment-9)** | [![experiment](https://img.shields.io/badge/experiment-8b5cf6)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-3/experiment-9) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/blob/fork/run_UESxYRggGt7E/round-3/experiment-9/demo/method_code_demo.ipynb) | [![Source Code](https://img.shields.io/badge/Source_Code-2962FF)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-3/experiment-9/src) | <sub><i>uses:</i><br/>[dataset‑1&nbsp;(R1)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/dataset-1)</sub> |
| **[Why Slovene refusals survive an English de-censoring edit](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-3/experiment-10)** | [![experiment](https://img.shields.io/badge/experiment-8b5cf6)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-3/experiment-10) | — | [![Source Code](https://img.shields.io/badge/Source_Code-2962FF)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-3/experiment-10/src) | <sub><i>uses:</i><br/>[dataset‑1&nbsp;(R1)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/dataset-1)</sub> |
| **[Confirming the Slovene refusal lag on untouched data (GaMS3 …](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-3/experiment-11)** | [![experiment](https://img.shields.io/badge/experiment-8b5cf6)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-3/experiment-11) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/blob/fork/run_UESxYRggGt7E/round-3/experiment-11/demo/method_code_demo.ipynb) | [![Source Code](https://img.shields.io/badge/Source_Code-2962FF)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-3/experiment-11/src) | <sub><i>uses:</i><br/>[dataset‑1&nbsp;(R1)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/dataset-1)</sub> |
| **[Does de-censoring hurt Slovene skills more?](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-3/experiment-12)** | [![experiment](https://img.shields.io/badge/experiment-8b5cf6)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-3/experiment-12) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/blob/fork/run_UESxYRggGt7E/round-3/experiment-12/demo/method_code_demo.ipynb) | [![Source Code](https://img.shields.io/badge/Source_Code-2962FF)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-3/experiment-12/src) | <sub><i>background:</i><br/>[dataset‑1&nbsp;(R1)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/dataset-1)</sub> |

## Round 4

| Artifact | Type | Demo | Source | Builds on |
|----------|------|------|--------|-----------|
| **[Paid judges re-score the Slovene refusal lag](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-4/evaluation-3)** | [![evaluation](https://img.shields.io/badge/evaluation-10b981)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-4/evaluation-3) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/blob/fork/run_UESxYRggGt7E/round-4/evaluation-3/demo/eval_code_demo.ipynb) | [![Source Code](https://img.shields.io/badge/Source_Code-2962FF)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-4/evaluation-3/src) | <sub><i>uses:</i><br/>[experiment‑9&nbsp;(R3)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-3/experiment-9)<br/>[experiment‑11&nbsp;(R3)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-3/experiment-11)<br/><i>differences:</i><br/>[experiment‑8&nbsp;(R2)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-2/experiment-8)<br/><i>similarities:</i><br/>[experiment‑10&nbsp;(R3)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-3/experiment-10)</sub> |
| **[Does Slovene refusal follow the prompt or the reply?](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-4/experiment-14)** | [![experiment](https://img.shields.io/badge/experiment-8b5cf6)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-4/experiment-14) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/blob/fork/run_UESxYRggGt7E/round-4/experiment-14/demo/method_code_demo.ipynb) | [![Source Code](https://img.shields.io/badge/Source_Code-2962FF)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-4/experiment-14/src) | <sub><i>uses:</i><br/>[dataset‑1&nbsp;(R1)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/dataset-1)</sub> |
| **[Dense dose ladder for the Slovene refusal lag: a baseline of…](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-4/experiment-15)** | [![experiment](https://img.shields.io/badge/experiment-8b5cf6)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-4/experiment-15) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/blob/fork/run_UESxYRggGt7E/round-4/experiment-15/demo/method_code_demo.ipynb) | [![Source Code](https://img.shields.io/badge/Source_Code-2962FF)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-4/experiment-15/src) | <sub><i>uses:</i><br/>[dataset‑1&nbsp;(R1)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/dataset-1)</sub> |
| **[Prior-art and fact check for the Slovene refusal study](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-4/research-1)** | [![research](https://img.shields.io/badge/research-3b82f6)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-4/research-1) | [![View Research](https://img.shields.io/badge/View-Research-green)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/blob/fork/run_UESxYRggGt7E/round-4/research-1/demo/research_demo.md) | [![Source Code](https://img.shields.io/badge/Source_Code-2962FF)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-4/research-1/src) | — |

## Round 5

| Artifact | Type | Demo | Source | Builds on |
|----------|------|------|--------|-----------|
| **[Does Gemma keep a Slovene safety reserve? (confirmation)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-5/experiment-16)** | [![experiment](https://img.shields.io/badge/experiment-8b5cf6)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-5/experiment-16) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/blob/fork/run_UESxYRggGt7E/round-5/experiment-16/demo/method_code_demo.ipynb) | [![Source Code](https://img.shields.io/badge/Source_Code-2962FF)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-5/experiment-16/src) | <sub><i>uses:</i><br/>[dataset‑1&nbsp;(R1)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/dataset-1)<br/>[research‑1&nbsp;(R4)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-4/research-1)</sub> |
| **[One English edit unlocks both Slovene and English models](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-5/experiment-17)** | [![experiment](https://img.shields.io/badge/experiment-8b5cf6)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-5/experiment-17) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/blob/fork/run_UESxYRggGt7E/round-5/experiment-17/demo/method_code_demo.ipynb) | [![Source Code](https://img.shields.io/badge/Source_Code-2962FF)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-5/experiment-17/src) | <sub><i>uses:</i><br/>[dataset‑1&nbsp;(R1)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-1/dataset-1)<br/>[research‑1&nbsp;(R4)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-4/research-1)</sub> |
| **[Is Gemma's Slovene refusal real safety?](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-5/evaluation-4)** | [![evaluation](https://img.shields.io/badge/evaluation-10b981)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-5/evaluation-4) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/blob/fork/run_UESxYRggGt7E/round-5/evaluation-4/demo/eval_code_demo.ipynb) | [![Source Code](https://img.shields.io/badge/Source_Code-2962FF)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-5/evaluation-4/src) | <sub><i>similarities:</i><br/>[experiment‑14&nbsp;(R4)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-4/experiment-14)<br/><i>uses:</i><br/>[experiment‑15&nbsp;(R4)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-4/experiment-15)</sub> |
| **[Tracing every paper number to saved results](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-5/evaluation-5)** | [![evaluation](https://img.shields.io/badge/evaluation-10b981)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-5/evaluation-5) | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/blob/fork/run_UESxYRggGt7E/round-5/evaluation-5/demo/eval_code_demo.ipynb) | [![Source Code](https://img.shields.io/badge/Source_Code-2962FF)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-5/evaluation-5/src) | <sub><i>differences:</i><br/>[experiment‑15&nbsp;(R4)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-4/experiment-15)<br/>[experiment‑11&nbsp;(R3)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-3/experiment-11)<br/><i>uses:</i><br/>[experiment‑14&nbsp;(R4)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-4/experiment-14)<br/><i>similarities:</i><br/>[experiment‑9&nbsp;(R3)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-3/experiment-9)</sub> |
| **[Is the reply-language safety finding new?](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-5/research-2)** | [![research](https://img.shields.io/badge/research-3b82f6)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-5/research-2) | [![View Research](https://img.shields.io/badge/View-Research-green)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/blob/fork/run_UESxYRggGt7E/round-5/research-2/demo/research_demo.md) | [![Source Code](https://img.shields.io/badge/Source_Code-2962FF)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-5/research-2/src) | <sub><i>extends:</i><br/>[research‑1&nbsp;(R4)](https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive/tree/fork/run_UESxYRggGt7E/round-4/research-1)</sub> |

## Repository Structure

Artifacts are grouped by the round of invention that produced them. Each
artifact has its own folder with source code and a self-contained demo:

```
.
├── round-1/                         # One folder per round of invention
│   ├── experiment-1/
│   │   ├── README.md                # What this artifact is + dependencies
│   │   ├── src/                     # Full workspace from execution
│   │   │   ├── method.py            # Main implementation
│   │   │   ├── method_out.json      # Full output data
│   │   │   └── ...                  # All execution artifacts
│   │   └── demo/                    # Self-contained demo
│   │       └── method_code_demo.ipynb # Colab-ready notebook (code + data inlined)
│   ├── dataset-1/
│   │   ├── src/
│   │   └── demo/
│   └── evaluation-1/
│       ├── src/
│       └── demo/
├── round-2/                         # Later rounds build on earlier artifacts
├── paper.pdf                        # Research paper
├── paper_latex/                     # LaTeX source files
├── report.pdf                       # Full internal report — every experiment, table and dead end
├── report_latex/                    # LaTeX source of the report
├── exec_summary.pdf                 # Executive summary of the report, at most four pages
├── chat/                            # Every prompt, response and tool call, per module
├── workflow.svg                     # Artifact dependency diagram (this page's header)
└── README.md
```

## Running Notebooks

### Option 1: Google Colab (Recommended)

Click the "Open in Colab" badges above to run notebooks directly in your browser.
No installation required!

### Option 2: Local Jupyter

```bash
# Clone the repo
git clone -b fork/run_UESxYRggGt7E https://github.com/ai-inventor-papers/ai-invention-2cf2a7-does-slovene-taught-refusal-survive
cd ai-invention-2cf2a7-does-slovene-taught-refusal-survive

# Install dependencies
pip install jupyter

# Run any artifact's demo notebook
jupyter notebook <artifact_folder>/demo/
```

## Source Code

The original source files are in each artifact's `src/` folder.
These files may have external dependencies - use the demo notebooks for a self-contained experience.

---
*Generated by AI Inventor Pipeline - Automated Research Generation*
