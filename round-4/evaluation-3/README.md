# Paid judges re-score the Slovene refusal lag

`demo/` — Self-contained demo (Colab-ready notebook or markdown). Run without setup.  
`src/` — Full source code, data, and outputs from the experiment execution.

**Type:** evaluation  
**ID:** `art_gOdYt7zLWvfr`

## Layman Summary

Re-judges 45,000 already-saved AI answers with a paid frontier judge to check a claim that removing English safety guards hurts Slovene more, and finds the gap predates the edit.

## Full Summary

Protocol completion for the C-LAG line: no new generations, a paid readout applied to the SAVED responses of exp8 (art_T5ChU9GV1tf7), exp9 (art_n3Crj0p24sBa), exp10 (art_sfQmnafZ153j) and exp11 (art_Aw3AXCXv9pUg), 45,207 rows in one frame, with every artifact's own estimator re-run and only the label column swapped. Primary judge google/gemini-2.5-flash (frozen P1 prompt sha 97332090..., temperature 0, thinking off): 25,025 fresh labels plus ~11.9k archived gemini labels reused after a 300-row drift check (kappa_3 0.97); second family openai/gpt-4.1-mini on 9,888 stratified rows; NLLB translate-then-judge with a 600-row EN->SL->EN round-trip control (flip rate 0.141); StrongREJECT ASR arm. Validation: a 480-row BLIND 4-class adjudication, AUTHOR-MODEL, NOT HUMAN. Spend $4.31 of an $8.00 self-imposed cap.

HEADLINE 1 - the lag is real but is NOT an effect of the edit. Pooled G3 (GaMS minus Gemma Slovene refusal log-odds at matched English refusal) = -1.17 [-1.84, -0.50] (REML+HKSJ, 3 item bodies; PPI++ -1.77 [-1.89, -1.65]; IG -1.15 [-1.31, -0.99]), same negative sign in every body, every readout and under translate-then-judge, and at exp10's operating point (G3_op -2.42 [-4.35, -1.53]). But G3_orig at lambda=0 is ALREADY -1.1 to -2.6 in every body, so pooled G3_edit = G3 - G3_orig = +0.39 [-1.95, +2.74], centred on zero -> verdict REFUTE-BOUND, |G3_edit| < 2.74. The pre-registered rival R-BASE (baseline offset) is NOT refuted and is the best-supported account: GaMS3 starts with less Slovene refusal than Gemma-3, and per-model slopes (b_Gemma 1.40-1.66, b_GaMS 0.97-1.13) show the two curves move roughly in parallel. Downstream artifacts should quote G3_edit, not G3.

HEADLINE 2 - even the paid frontier judge fails the pre-registered gate. Against the blind adjudication, gemini-2.5-flash has Se 0.91 (GaMS-SL-edited) / 0.99 (Gemma-SL-edited) but Sp 0.73 / 0.66: it OVER-CALLS REFUSE on edited Slovene. kappa(gemini, gpt-4.1-mini) = 0.39 in GaMS-SL-edited. Both decisive cells fail the C2 gate (Se AND Sp >= 0.80), so the C-LAG readout verdict is READOUT NOT VALIDATED and no number carries a primary verdict. The symmetric tipping analysis closes it: erasing the lag needs 0.55 extra Gemma-SL false-REFUSE or 0.13 extra GaMS-SL false-COMPLY, and the MEASURED error CIs (1-Sp 0.34 [0.17, 0.57]; 1-Se 0.09 [0.03, 0.26]) reach BOTH thresholds - judge error alone can still account for the lag. A native-speaker audit (60 edited rows per model x language) is REQUESTED as human input, never assumed.

Corrections to the direction, each logged in protocol.yaml: C1 the 590-row 'gold calibration' block holds hazard-category gold for PROMPTS, not refusal labels (verified at start-up) so it cannot calibrate a refusal judge; C2 the gate is placed on Se AND Sp in BOTH decisive cells because the lag's real vulnerability is a SENSITIVITY failure in GaMS-SL, not the direction's Sp-only rule; C3 3 h; C4 the P1 prompt's stale '64 tokens' wording kept verbatim for protocol identity.

VALIDITY: protocol.yaml sha256'd and git-committed before the first paid call; 3 timestamped amendments each committed before the work they affect (AM0 no tier passed the bake-off -> frozen fallback, every headline flagged; AM1 pre-registered cut ladder after the $8.30 projection; AM2 the PLATFORM's shared OpenRouter key hit its own daily limit mid-run -> ASR stopped at 1,108/5,800 and the R-INCAP DiD is NOT EXECUTED, the paid TTJ pass was replaced by exp9's J1 mdeberta judge applied to both the translations and the direct rows, 195 adjudication rows were labelled blind by the executing agent, and a 40-row INTER-adjudicator overlap (kappa_R 0.69) replaced the blocked intra-rater retest). Smoke tests reproduce every archived headline from its archived label column (exp8 lexicon B -2.3617, A1 -0.1869, exp9 J1 -0.9698, exp11 Qwen -0.5997, eval2 IG and exp10 G3_op exactly). An independent numpy/scipy path (src/rederive.py, never imports vendor/, engine.py or eval.py; exact Newton MLE, own Se/Sp, own RG and HKSJ) agrees on 155/155 checks including the pooled headlines rebuilt from rederived per-body points (3e-8). Placebos are null: model-label swap centred at 0 with p=0.001 for the observed G3, language-label swap centred at 0, shuffled-judge kappa 0.007. Parse rate >= 99.96%; the 87 rows the judge provider blocked (Gemini PROHIBITED_CONTENT) are bounded both ways (G3 moves < 0.02).

FOR LATER ARTIFACTS: results/judge_error_matrices_v2.json gives per-cell Se/Sp with Wilson CIs for TEN instruments (paid gemini, gpt-4.1-mini, TTJ-J1, direct-J1, exp9 J1/J2, exp11 Qwen3-14B, eval2 Mistral, exp8 Llama-8B, lexicon); reusable as the calibration table for any re-analysis of these rows; labels/readout_rows.jsonl.gz holds every row with every label, the TTJ translation, ASR fields and adjudication; READOUT_v2.md maps each previously quoted number to its validated replacement with a SURVIVES/SHRINKS/REVERSES/UNCITABLE status.

## Dependencies

- `art_n3Crj0p24sBa` — rescores
- `art_Aw3AXCXv9pUg` — rescores
- `art_T5ChU9GV1tf7` — rescores
- `art_sfQmnafZ153j` — rescores

## Output Files

- `eval.py`
- `full_eval_out.json`
- `mini_eval_out.json`
- `preview_eval_out.json`
- `reproducibility.md`

## Demo Files

- **eval.py** — Evaluation script with metrics computation

---
*Generated by AI Inventor Pipeline*
