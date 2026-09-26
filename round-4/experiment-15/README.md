# Dense dose ladder for the Slovene refusal lag: a baseline offset, not an edit-induced hole

`demo/` — Self-contained demo (Colab-ready notebook or markdown). Run without setup.  
`src/` — Full source code, data, and outputs from the experiment execution.

**Type:** experiment  
**ID:** `art_piu0nI9vij_F`

## Layman Summary

A Slovene-adapted model keeps refusing in Slovene after an English-only de-censoring edit, more than its base model does. This experiment shows that gap was already present before the edit; the edit does not open a new Slovene-specific hole.

## Full Summary

SCREEN-grade power-and-decomposition artifact (iter-4) for C-LAG. One NF4 code path (bf16, greedy, 64 new tokens, empty system turn), protocol.yaml sha256'd + git-committed before any BODY row; amendments A0 (64 tokens), A1 (ladder+tier+cut), A2 (fill-in), A4 (key limit) are timestamped in results/protocol_amendments.json.

DESIGN. The iter-3 exp9 English-objective Heretic LoRA (E_exp9, r=3, o_proj+down_proj) is applied to BOTH GaMS3-12B-Instruct (Slovene-adapted) and its base Gemma-3-12B-IT via forward hooks (lambda=0 bit-identical to base; hook matches exp9's saved lambda=1.0/0.5 adapters 20/20 argmax). Dose = a 13-step lambda ladder DEV-calibrated per model by inverting a logistic fit of EN refusal at 12 targets (0.88..0.12) + lambda 0; a pre-registered support check on the BODY EN curve (x-axis only) fired the fill-in (GaMS 4/4 -> +2 lambdas -> 5/5; final support PASSES both sides, both models). Items: fresh 300-item RefusEU-TRAIN harmful body + 120 content-matched benign twins, disjoint from exp1/2/4, exp8, exp9, all exp10 files and exp11, filtered against the reserved eval blocks and mlabonne/harmful_behaviors. Arms EN-orig/EN-BT/SL-MT from one English source via NLLB-1.3B (chrF median 74.9, SL langid 100%). BASELINES in the same pipeline: unedited model (lambda 0); the sibling control model Gemma; exp9's norm-matched random-direction LoRAs at matched lambda -- the FIRST scored GaMS random control.

RESULT (raw J1 readout). G3 = a_GaMS - a_Gemma = -0.70 [-1.01, -0.42], MDE 0.42 -- the most powerful estimate in the run (exp9 0.80, exp11 1.44). At EN 50% Gemma SL ~0.72 sits well above the diagonal, GaMS SL ~0.51 near parity (fig1). Model-swap placebo p=0.000; integrated gap IG=-0.74 [-1.02,-0.49] and isotonic SL@EN50 (-0.77) agree; leave-one-step-out G3 in [-0.73,-0.67]; mt_fragile-dropped -0.73; GEE gams:sl -0.69.

HEADLINE (decomposition). The lag is a BASELINE property, not made by the edit. G3_orig (lambda=0 SL-minus-EN margin difference) = -1.17 [-2.83, 0.22] carries essentially the whole gap; the edit-induced G3_edit = G3 - G3_orig = +0.47 [-0.96, 2.14] has a 95% CI spanning 0 (90% bound |G3_edit|<1.91), and both slopes b are ~1 (Gemma 0.94, GaMS 0.80). This is the R-BASE rival's prediction (parallel curves, pre-edit offset), so C-LAG's edit-induced claim (G3_edit<=-m/2, CI excl 0) is NOT met: the edit does not open a Slovene-specific hole; GaMS starts and stays closer to parity than Gemma (M0 1.48 vs 0.31). The random control confirms specificity: random edits leave EN refusal unchanged (dEN ~0.01/0.00) while Heretic lowers it (-0.22..-0.86); G3_edit_rand and G3_edit_heretic-at-matched-lambda have overlapping CIs. R-JUDGE only partly holds: the lag persists under translate-then-judge (G3_TTJ = -0.79 [-1.09,-0.48], CI excl 0), so it is not merely a judge-language artifact, but SDT shows a criterion component (DiD_c window = -0.33 [-0.53,-0.16]).

VERDICT: ESTIMATE (SCREEN). The run's shared OpenRouter key hit its $12 limit ($0.199 left) after this artifact spent $0.279, so the pre-registered paid readout (gemini-2.5-flash + gpt-4.1-mini + StrongREJECT ASR) could not run; the full-coverage readout is the J1 fallback (exp9 mdeberta distilled from archived real gemini labels), NOT promoted to a validated primary (F3). On 240 blind author-model (NOT human) adjudicated rows, J1 SL-edited specificity is 0.55 (Gemma)/0.62 (GaMS), below the 0.80 gate: J1 over-calls Slovene refusal roughly symmetrically. Rogan-Gladen sits near its identifiability threshold so its CI is uninformative (G3_RG=-0.01 [-4.36,11.27]); PPI gives -0.75 [-2.43,0.99] (CI incl 0). J1 emits no PARTIAL, so RP=R (not independent). Paid ASR (R-INCAP) was unaffordable; an exploratory author-model harmful-content flag is reported.

VERIFICATION. rederive.py (independent numpy/statsmodels path, never imports analysis.py) reproduces every headline to 1e-6/1e-4 -- 81/81 checks pass, its own placebo centres at 0. 10/10 unit tests pass (Hautus, RG inverse, kappa vs sklearn, planted-offset G3 recovery, R-BASE synthetic both cases, SDT, PPI unbiasedness+lower variance than RG, bootstrap coverage, placebo). Every number in README/RESULTS is generated from results/analysis.json.

DELIVERABLES: 33,888 saved generations, J1 + TTJ labels, 240 adjudicated rows, results/{analysis,audit,gates,rows_final,ledger}.json*, 5 figures, method_out.json (exp_gen_sol_out, 1,140 examples with per-model-per-lambda predictions; schema-validated; mini/preview), finalize.sh (runs the pre-registered paid readout on the saved generations, ~$3.5, to lift the verdict). Model weights, exp9 edits and the J1 checkpoint are read in place from the run volume; nothing in the workspace exceeds 10 MB except .venv (uv sync).

## Dependencies

- `art_EG6OpEkGvysx` — dataset

## Output Files

- `method.py`
- `full_method_out.json`
- `mini_method_out.json`
- `preview_method_out.json`
- `reproducibility.md`

## Demo Files

- **method.py** — Research methodology implementation

---
*Generated by AI Inventor Pipeline*
