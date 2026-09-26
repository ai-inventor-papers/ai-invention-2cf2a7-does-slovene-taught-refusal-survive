# English abliteration's reach into Slovene: Heretic core screen (dir5, SCREEN-SPEC v1)

This repository contains the code, data splits, per-item outputs and analysis for **one pinned Heretic
([p-e-w/heretic@3521f864](https://github.com/p-e-w/heretic/tree/3521f8648a0dccf6e12a92666862632235fac7e6))
English-objective abliteration**. It is run on **cjvt/GaMS3-12B-Instruct** (rev `1d0b27af57…`), with
**google/gemma-3-12b-it** (sha `96b6f1ec…`) as the same-family control. Both runs use the same config, NF4 4-bit
precision, an empty system prompt, `TPESampler(seed=20260923)` and the same items.

A custom driver copies Heretic's `objective()` verbatim; see `src/heretic_ref/objective.diff` for the only added lines.
After each trial's objective has been computed, the driver logs **bilingual off-objective metrics** that never enter
the objective. These are refusal on a 50+50 RefusEU TRIAL-PROBE, first-token prefix log-odds, and first-token KL on
Slovene/English ARC + HellaSwag stems. The saved trials feed three screen statistics:

- **C3:** GaMS-minus-Gemma Slovene refusal at matched English refusal of 50%.
- **C5a/C5b:** Slovene off-target KL leakage against random-direction edits, and bilingual re-selection.
- **ALT-4:** a compliant-prefill flip test on the original models.

The RefusEU `evaluation` split is **never loaded**; it is reserved for the next iteration's confirmation.


## Headline findings (all numbers from `results/analysis.json`; re-derived 20/20 in `results/audit.json`)

**1. English-objective abliteration reaches Slovene in both models.** On the 400-pair RefusEU SCORE set the selected
edit takes lexicon refusal from 0.965 → 0.242 (EN) and 0.932 → 0.223 (SL) in Gemma-3-12B-IT, and from 0.940 → 0.133 (EN)
and 0.830 → 0.098 (SL) in GaMS3-12B-Instruct. Across trials the EN→SL slope is positive in both models
(Gemma 1.21 [0.75, 1.83], GaMS 0.79 [0.51, 1.14]); a placebo that shuffles the Slovene rates across trials gives
0.01 ± 0.28, so the coupling is real, not an artefact of the fit.

**2. The two models differ in *how much* Slovene survives at matched English suppression — and the pre-registered
C3 conjunct fails in the unexpected direction.** G3 = a_GaMS − a_Gemma = **−1.86 [−2.87, −1.13]** log-odds
(matched first 17 trials; −1.76 [−2.77, −1.04] on all trials; −1.74 on the T/R pair subset; −0.99 on the λ curve).
MAIN needs |G3| < m = 0.675 and ALT-1 needs G3 > m: **both fail** (z_c = −2.67 and −5.72). GaMS's Slovene refusal is
*lower* than Gemma's at the same English refusal level, i.e. Slovene is **more** exposed in the Slovene-adapted model,
not less. A permutation test that reassigns trials to models gives p = 0.000 (null 0.000 ± 0.347).
The ALT-1 category version (G3_low − G3_high = 0.39 [−1.19, 2.12]) does **not** separate low-EN-dose from
high-EN-dose hazard categories.

**3. ALT-4 (thin templated gate): the strongest signal here, but its language-interaction conjunct fails.**
With a 5-token compliant prefill, the flip rate on items refused at k = 0 is Gemma 0.031 (EN) / 0.558 (SL) versus
GaMS **0.559 (EN) / 0.855 (SL)**. Sig_EN = 3.63 and Sig_SL = 1.54 both clear m2 = 0.402 with CIs above 0 (z_c = 6.23),
and a paired per-item model-label swap gives p = 0.000. The candidate is nonetheless scored **not survived**, because
|Sig_SL − Sig_EN| = 2.10 exceeds m = 0.675. GaMS's refusal behaves like a shallow template that a compliant prefix
overrides, and Gemma's English refusal does not.

**4. C5a: no Slovene KL leakage — the effect reverses.** The excess SL/EN first-token-KL ratio (edit ÷ random edit) is
0.298 [0.154, 0.562] for Gemma and 0.574 [0.409, 0.796] for GaMS against norm-matched random directions (0.262 and
0.540 against the EN-KL-matched variant). All four CIs exclude 1 **from below**: relative to a random direction of the
same layer weights, the real refusal direction damages Slovene *less* than English, not more. Leakage is not supported
in either model.

**5. C5b: bilingual re-selection had nothing to select from.** With 17–20 trials only one trial satisfied the
candidate band in each model, so `resel == pick` and the gain is 0 by construction. This is a power failure, not
evidence against re-selection.

**6. Negative/limiting result: 17–20 random TPE draws do not abliterate these models by Heretic's own objective.**
No trial reached the pre-registered ≤10/100 keyword refusals, so the selection rule fell back to min-refusals
(Gemma 64/100, GaMS 29/100 — GaMS is markedly easier to suppress at equal search budget). The public reference edit
uses 200 trials. Every Pareto and C3 number is therefore a *reduced-trial, random-search* number.
The EN-KL-matched random control was **unmatchable** even at the 6× cap (random-direction KL 0.035–0.065 versus the
pick's 0.366), which is itself a positive control: the difference-of-means direction does far more first-token damage
per unit weight than a random direction.

**7. Measurement caveat that the paper must carry.** Judge validation did **not** confirm the frozen lexicon
(κ < 0.7 in every cell). Much of that is the kappa paradox — raw agreement is 95% on the original-model cells
(PABAK ≈ 0.90) — but on abliterated 40-token continuations the readouts genuinely diverge (lexicon 0.47 versus judge
0.92 EN refusal), and two judge prompt wordings disagree with each other (κ = 0.22–0.50). Per fallback F6 the
R-based statistics are reported as an **unvalidated screen** with s1 as co-primary. The GaMS judge pass could not run:
the shared OpenRouter key hit its daily limit (HTTP 403) after $0.94 of $10, so `results/judge.jsonl` covers Gemma only
and both judge sensitivity readouts are skipped rather than half-computed. **Retried at 19:31 UTC with the replacement
key** supplied by the platform (`/ai-inventor/aii_data/.secrets/openrouter_key.private`): it is the same workspace key
id and still returns `Key limit exceeded (daily limit)`, so the attempt was aborted immediately at $0 additional spend
(the failed calls are logged in `results/judge_ledger.jsonl`). Judging GaMS is the single outstanding item for the next
run; the command is `python3 src/judge.py --models gams3_it --all` (then `--prompt-version v1`), and
`src/analyze.py` picks the labels up automatically and fills in both sensitivity readouts.

**8. Numerical noise floor on KL (disclose with C5a).** Re-running the *unedited* model against its own cached
baseline gives a per-item first-token KL of up to 0.030 (Gemma) and 0.006 (GaMS) instead of exactly 0, because
NF4 matmuls are not bit-identical across different batch compositions. Absolute KLs of that order are at the noise
floor. The C5a statistic is a *ratio of ratios* computed from the same batching for edit and control, so it is far
less affected, but individual small KL values in `trial_kl.jsonl` should not be read as exact.

**9. Data-validity correction.** The LLM pair grading found **0 / 200** RefusEU EN–SL pairs to be translations
(67% different requests, 33% same request reworded). Within-model EN-vs-SL differences are therefore **not**
interpretable as language effects; only between-model gaps and DiDs are, and C3 is additionally reported on the
T/R subset, where it is unchanged (−1.74).


> Full tables: see `RESULTS.md` (written from `results/analysis.json` after the final audit), `method_out.json`
> (`metadata.analysis`), `results/selection.json`, `results/audit.json` and `results/figs/`.

## What was run (and what was changed from the plan)

| Plan | Executed | Why |
|---|---|---|
| 80 trials (25 start-up), time-boxed with a floor of 40 | **Gemma 20, GaMS 17** trials, all of them TPE start-up (random) draws with the same seed, so the draws are identical across models (paired). C3 is reported on the matched first 17 as primary (plan F3) and on all trials. | Measured 148–164 s per trial on the RTX 2000 Ada 16 GB pod (plan assumed an A4500 20 GB). Recorded in `results/protocol_amendments.json` (amendments 1–3) **before** any C3/C5/ALT-4 statistic. |
| Per-trial probe: 100+100 items, 64 new tokens, multi-token `s` | 50+50 items (plan cut rule 5), **40 new tokens**, **s1** (first-token prefix log-odds) | Same throughput constraint. Multi-token `s` is kept on all SCORE-400 blocks. |
| Lexicon R primary, judge on 150/cell | κ < 0.7 in every cell, so all 4,941 Gemma responses were judged (two prompt wordings). The judges did **not** validate the lexicon and disagree with each other, and the shared OpenRouter key then hit its daily limit before GaMS could be judged. The **pre-registered lexicon stays primary**, every R statistic is labelled an unvalidated screen (fallback F6) with s1 co-primary, and both judge readouts are reported as skipped sensitivity analyses. | Truncated 40-token continuations are genuinely ambiguous between 'declines' and 'hedges then complies'; raw agreement is still 95% (PABAK 0.90) on the unedited models. |
| λ grid 0…1.2 (13 points) | λ ∈ {0 (original), 0.5, 1.0 (pick trial), 1.2} | Time. |
| Random edits: Heretic scores + TRIAL-PROBE R/s | Norm-matched random ×5: Heretic KL (keyword refusals for j=1), SEL/EVAL KL, s1; EN-KL-matched random ×5: KL | C5a needs only KL. |
| Rank-1/rank-5 activation ablation (Arditi-style) | Ran on Gemma: **it destroyed the model** (KL 20–53 nats at every candidate layer; even the random 5-dim basis R5 produced garbage), so it is invalid. Kept as `results/gemma_it/rank_k_raw*`. A "projected" variant (bases orthogonalised against the per-layer harmless means) is implemented but was **not run** for lack of GPU time. | Gemma-3's massive-activation dimensions get smeared across all coordinates when any direction is projected out of the full residual stream. |
| Pair T/R/U grading | Done (gemini-2.5-flash): **0/200 pairs are translations**, 67% different requests, 33% same request reworded | Confirms that RefusEU EN/SL rows sharing a row_id are *independently generated variants*. Only between-model gaps and DiDs are interpretable. |
| Harmless SL set | gemini-2.5-flash MT of harmless_alpaca train[400:600]. The v1 prompt made the MT model *execute* the instructions, so a v2 "translate, do not execute" prompt was used. | |

The following choices also held throughout:

- **Pairing.** RefusEU `row_id` is **not unique**: 279 row_ids occur twice with different categories. Pairs are matched
  by row index; the category and row_id sequences were asserted identical across languages. `pair_id` is
  `split:row_id` for the last occurrence (the sibling artifacts' convention) and `split:row_id:dup` for the earlier one.
- **Template.** The Gemma template turns an empty system turn into a `\n\n` prefix, so it is monkey-patched to drop an
  empty system message, identically for both models. Heretic's tokenisation adds a double BOS; this is kept as-is for
  fidelity to the pinned tool.
- **Batch size.** Heretic's `batch_size` is fixed at 128 for both models (not auto-benchmarked).
- **Compilation.** `TORCHDYNAMO_DISABLE=1` is set, and gcc was installed on the pod (Triton needs a C compiler).

## Layout

```
method.py                  entry point: analysis -> figures -> method_out.json (exp_gen_sol_out schema)
run_all.sh                 GPU chain actually used (Gemma then GaMS; final amendment-3 flags)
protocol.json / .sha256    frozen SCREEN-SPEC v1 + selection rule + splits sha256 (frozen before GPU scoring)
pyproject.toml, requirements.lock.txt   exact pins (heretic git sha, torch 2.14.0+cu130, transformers 5.17.0, ...)
src/common.py              paths, lexicon, prefix sets, hautus/logit
src/prep_data.py           S0: RefusEU pairs + SCREEN-SPEC splits, KL sets, harmless set
src/prep_openrouter.py     S0: SL MT of harmless set, T/R/U pair grades (OpenRouter)
src/write_protocol.py      freezes protocol.json
src/probe.py               GPU helpers: length-bucketed greedy generation, s / s1, first-token KL, ablation hooks
src/run_model.py           per-model GPU block (Phase O original, Phase H Heretic study + probe, Phase P post hoc)
src/judge.py               gemini-2.5-flash refusal judge (resumable ledger)
src/analyze.py             all statistics (judge primary, lexicon secondary) -> results/analysis.json, selection.json
src/make_figs.py           results/figs/*
src/audit.py               independent re-derivation + placebo tests -> results/audit.json
src/post_gemma.py          optional projected rank-k + Mechanistic-Question-C pass for Gemma (IMPLEMENTED, NOT RUN: time)
                           (run_model.run_mech_c is the Mech-C implementation; --no-mech-c was used in the final chain)
src/heretic_ref/           Heretic main.py/model.py/evaluator.py @3521f864 + objective.diff
data/splits/*.jsonl        construct / score / score400 / trial_probe / sel_kl / eval_kl / kl_spare
data/pair_grades.jsonl     T/R/U grades; data/harmless_sl_mt.jsonl; data/shingles.jsonl (eval-side dedup next iter)
results/<model>/           (no baseline_lp cache by default: 400 prompts x 262k vocab is ~400 MB per model,
                           over the 100 MB publish limit; --save-baseline-lp writes <90 MB shards instead)
                           orig_score400.jsonl, selected_score400.jsonl, prefill.jsonl, trial_probe.jsonl,
                           trial_kl.jsonl, posthoc_probe.jsonl, posthoc_kl.jsonl, trials.json,
                           heretic_study.journal (Optuna journal, resumable), selection_pick.json,
                           selected_adapter/ (LoRA of the selected edit), random_edits.json, lambda_curve.json,
                           checks.json, residual_directions.pt, aborted_attempt*/ (discarded partial trials, kept for audit)
results/judge.jsonl        one row per judged response; results/judge_ledger.jsonl = OpenRouter cost ledger
results/smoke_gemma_it/    smoke test outputs (2 trials; not used in statistics)
logs/                      all run logs, including the aborted attempts (OOM, too-slow probe)
```

## How to run

```bash
uv venv .venv --python 3.12 && uv pip install --python .venv/bin/python -r requirements.lock.txt
python3 src/prep_data.py && python3 src/prep_openrouter.py && python3 src/write_protocol.py   # S0 (CPU)
./run_all.sh                                   # GPU, ~3.5 h on a 16 GB card
python3 src/judge.py --all                     # OpenRouter judge (~$1)
.venv/bin/python method.py                     # analysis + figures + method_out.json
.venv/bin/python src/audit.py                  # independent re-derivation + placebos
```

Models load from the run's shared HF cache (`$HF_HOME`); nothing large is stored in this workspace.

## Restoring removed files

`.aii/manifest.yaml` marks three paths for deletion — the virtual environment and the two Python bytecode caches.
Everything under `results/` is kept.

| Deleted path | Restore with |
|---|---|
| `.venv/` | `uv venv .venv --python 3.12 && uv pip install --python .venv/bin/python -r requirements.lock.txt` |
| `__pycache__/` | nothing to do: CPython rewrites it on the next import, e.g. `.venv/bin/python method.py` |
| `src/__pycache__/` | nothing to do: CPython rewrites it on the next import, e.g. `.venv/bin/python method.py` |

Two things this repository never stores, and how to get them back:

- **Model weights** (~24 GB, loaded from the run's shared HF cache, never copied here):
  `huggingface-cli download google/gemma-3-12b-it` and
  `huggingface-cli download cjvt/GaMS3-12B-Instruct --revision 1d0b27af5748784482600d24779409e7e1dc9adc`.
- **The O2 first-token log-prob cache** (~400 MB per model, over the 100 MB publish limit). It is *not written by
  default* and nothing downstream reads it — Phase O2 recomputes the log-probs in ~45 s. To materialise it anyway, add
  `--save-baseline-lp` to the `src/run_model.py` command in `run_all.sh`; it then writes float16 shards of <90 MB
  (`results/<model>/baseline_lp_part_*.pt`) which `run_model.load_baseline_lp` reassembles on the next run.
  `src/test_baseline_lp.py` unit-tests that round trip.
