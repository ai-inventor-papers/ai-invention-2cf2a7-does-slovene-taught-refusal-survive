# Does English de-censoring hit Slovene harder? (C3 confirmation, CONFIRM-SPEC v2)

This repository re-tests one iter-1 screen finding. In iter-1, **English-objective Heretic abliteration seemed to remove
GaMS3-12B-Instruct's *Slovene* refusal faster than Gemma-3-12B-IT's, at matched English refusal**
(G3 = −1.86 log-odds, 95% CI [−2.87, −1.13]). That estimate came from a keyword lexicon, RefusEU EN/SL pairs that are
not translations of each other, 17 random-start trials and no judge labels.

This artifact repeats the test with the confounds removed:

* **Item-matched probe.** 200 new RefusEU-TRAIN items, each in three arms from ONE English source: the English
  original (EN-orig), an NLLB Slovene MT (SL-MT) and an NLLB English back-translation (EN-BT). The language effect is
  SL-MT vs EN-BT; the MT-noise effect is EN-BT vs EN-orig.
* **Judge-primary readout.** `google/gemini-2.5-flash` gives a 3-way label (REFUSE / PARTIAL / COMPLY), with
  `openai/gpt-4.1` as a second-family judge on a stratified 15%. The frozen keyword lexicon is a diagnostic only.
* **Three dose curves**, run on both models with identical items, grids, seed and code:
  * **B (confirmatory).** 29 fresh Heretic trials per model (seed 20260924; the TPE draws are paired across models).
  * **A1.** The iter-1 selected Heretic LoRA, linearly scaled by λ.
  * **A2.** Graded mean-projection ablation of a winsorized own-English refusal direction, plus a centred-variance
    random-direction control.
* **Depth link (C).** Compliant-prefill flips define *shallow* vs *deep* items. A discrete-time hazard model then tests
  whether shallow items lose refusal earlier along λ, and whether depth explains the Slovene-vs-English hazard gap.
* **C5a.** Slovene/English first-token-KL leakage of the λ=1 Heretic edit relative to random LoRA edits.

G3 = a_GaMS − a_Gemma, where a_m is the predicted SL-MT refusal log-odds at EN-BT refusal = 50%. Each a_m comes from a
per-model binomial GLM of SL refusal on the Hautus log-odds of EN refusal across steps (trials, λ values or ablation
strengths). The pre-registered margin m = 0.675 is inherited from iter-1; m_local = 0.20 is co-reported.

> RESULTS: see [`RESULTS.md`](RESULTS.md). Every number there is recomputed from `results/items_final.jsonl` by
> `src/analysis.py` and re-derived independently by `src/audit.py` (`results/audit.json`).

## Models, precision, decoding

| | Gemma-3-12B-IT (control) | GaMS3-12B-Instruct (target) |
|---|---|---|
| repo @ revision | `google/gemma-3-12b-it` @ `96b6f1eccf38110c56df3a15bffe176da04bfd80` | `cjvt/GaMS3-12B-Instruct` @ `1d0b27af5748784482600d24779409e7e1dc9adc` |
| precision | bitsandbytes NF4, double quant, bf16 compute (**reduced precision**) | identical |
| template | official chat template, empty system turn dropped (byte-identical rendering, `checks.json:template`) | identical |
| decoding | greedy; 128 new tokens (A, C); 64 (B probe, harmless) | identical |
| Heretic | `p-e-w/heretic@3521f8648a0dccf6e12a92666862632235fac7e6`, iter-1 config, `TPESampler(seed=20260924, n_startup=20, multivariate)`, batch 128, English datasets and English keyword objective untouched | identical |

Hardware: one NVIDIA L4 (23 GB), torch 2.14.0+cu130, transformers 5.17.0 (`requirements.lock.txt`).

## Layout

| path | what |
|---|---|
| `method.py` | CPU entry point: items table → analysis → audit → figures → `method_out.json` (exp_gen_sol_out schema) |
| `finalize.sh` | idempotent post-GPU pipeline: judge missing ids → contamination audit → `method.py` → schema check / mini / preview |
| `protocol.json`, `protocol.sha256` | frozen protocol (git commit `1010b14`, before the first FINAL generation) |
| `results/protocol_amendments.json` | timestamped amendments, each written (and git-committed) before the generation it affects |
| `src/prep_probe.py` | STEP 1 data: RefusEU-TRAIN pool → P200 / P100 / DEV20, NLLB MT + back-translation, chrF QA, alpaca harmless sets |
| `src/write_protocol.py` | STEP 2 protocol freeze |
| `src/gpu_block.py` | STEP 3 per-model GPU block (identical code path): checks → C depth → A1 λ-curve → A2 ablation (+ random control, collateral) → C5a → B Heretic trials with an off-objective bilingual logger. Resumable per step |
| `src/probe.py` | length-bucketed batched generation with an OOM halver, first-token log-probs, KL |
| `src/judge.py` | STEP 4 judge: resumable append-only ledger, 403 routing, stratified second family, 64-vs-128 truncation check, $ caps |
| `src/build_table.py` | STEP 6 per-item table `results/items_final.jsonl` (+ `items_dev.jsonl`) |
| `src/analysis.py` | STEP 7 statistics → `results/analysis.json`, `results/sanity.json`, `results/pairing_check.json` |
| `src/audit.py` | STEP 8 independent re-derivation + placebos → `results/audit.json` |
| `src/make_figs.py` | figures → `results/figs/*.pdf|png` |
| `src/contamination_check.py` | P200 vs the reserved dependency sets (exclusion reference only) → `data/contamination_P200.json` |
| `src/common.py` | constants, frozen lexicon, judge prompt (verbatim iter-1 P1), helpers |
| `tests/test_stats.py` | T0 unit checks (Hautus, G3 recovery, bootstrap coverage, judge parser, hazard sign) |
| `src_iter1_ref/` | read-only copy of the iter-1 exp4 code this artifact adapts (incl. `heretic_ref/objective.diff`) |
| `data/` | probe and auxiliary sets with sha256 manifest (`split_manifest.json`) and provenance (`provenance.json`) |
| `results/{gemma_it,gams3_it}/` | per-model raw outputs (below) |
| `results/dev/` | DEV smoke outputs (never pooled with FINAL) |
| `results/judge_ledger.jsonl`, `results/judge_labels.jsonl` | every judge call (cost, status) and the exported labels |
| `logs/` | full run logs, including the logs of processes killed by the session interruption (`*_killed_*.out`) |

Per-model raw files in `results/{model}/`:
`depth_orig.jsonl` (k=0 in EN-orig/EN-BT/SL-MT plus the compliant-prefill arm) · `curve_lambda.jsonl` (A1) ·
`harmless_gens.jsonl` · `lambda_harmless_kl.json` · `curve_ablate.jsonl` (A2) · `curve_ablate_rand.jsonl` (random
control) · `a2_collateral.json` · `a2_directions.pt` (per-layer u_l, μ_l) · `c5a_edit.jsonl` / `c5a_rand.jsonl` ·
`trial_probe.jsonl` (B: per trial × item × arm, with Heretic refusals/KL) · `heretic_study.journal` (Optuna journal; any
trial can be rebuilt from it plus `residual_directions.pt`) · `trials.json` · `checks.json` · `timing.json`.
No per-trial LoRA weights are saved.

## How to run

```bash
uv venv .venv --python 3.12 && uv pip install --python .venv/bin/python -r requirements.lock.txt
(cd src && ../.venv/bin/python prep_probe.py && ../.venv/bin/python write_protocol.py)   # data + frozen protocol
DL=$(date -u -d "+6 hours" +%s)
.venv/bin/python -u src/gpu_block.py --model gemma_it --gpu-deadline-epoch $DL --budget 30000 --max-bs 128
.venv/bin/python -u src/gpu_block.py --model gams3_it --gpu-deadline-epoch $DL --budget 30000 --max-bs 128
./finalize.sh                                   # judge + analysis + audit + figures + method_out.json
.venv/bin/python -m pytest -c pytest.ini tests/ # T0 unit checks
```
`OPENROUTER_API_KEY` and `OPENROUTER_BASE_URL` must be set for the judge. The GPU block needs about 7.8 GB of VRAM for the
NF4 model and up to about 17 GB at batch 128.

## Data and separation rules

* **Probe source.** Candidates are RefusEU EN rows (`NASK-PIB/RefusEU` @ `5523ce30b9`, `lang_en` train+test, through iter-1
  exp4's SCORE split). They exclude iter-1's trial-probe and CONSTRUCT items (by id and by normalised text), exact
  matches to `mlabonne/harmful_behaviors` (Heretic's objective set) and duplicates. P200 is sampled stratified by gold
  category (14–15 per S1..S14; 57 items in the frozen low-EN dose group S2/S5/S7/S13) and ranked by
  sha1(item_id + seed). P100 is the first half; DEV20 is kept separate and never used in any statistic.
* **MT.** `facebook/nllb-200-distilled-1.3B` (fp16, 4 beams) produces EN→SL (SL-MT) and SL→EN (EN-BT). Back-translation
  chrF: median 75.5, IQR 66.0–82.0. 2 items are `mt_fragile` (chrF < 40), with a sensitivity check that drops them.
  Language-ID of SL-MT is 100% `sl`. There is **no native-speaker audit**.
* **Reserved sets are never used.** The RefusEU `evaluation` config is never loaded. The dependency dataset
  `art_EG6OpEkGvysx` (iter-1 `gen_art_dataset_1`) is used only for (a) its frozen dose groups (`frozen_groups.json`) and
  (b) the exclusion reference in `src/contamination_check.py`. P200 has **0** exact matches and **0** items with ≥50%
  8-gram overlap with the reserved `refuseu_eval` / `refuseu_x_mt` blocks (max overlap 0.40). The 35 exact matches with
  `refuseu_gold_calib` are expected, because those are RefusEU train/test gold rows, i.e. the same source pool.
  Result: `data/contamination_P200.json`.
* **Harmless sets.** `tatsu-lab/alpaca` instruction-only items (not Heretic's `mlabonne/harmless_alpaca`):
  harmless100 (over-refusal, first-token KL), harmless_dir400 (A2 direction) and harmless_dev32 (A2 DEV rule).
  C5a uses iter-1's SEL/EVAL-KL stems (Slovenian-llm-eval ARC/HellaSwag, EN+SL) unchanged.

## Deviations from the plan (all logged in `results/protocol_amendments.json` before the affected generation)

1. **Hardware / throughput (F3).** Measured throughput on the L4 was 1.32 items/s at 128 tokens, too slow for the
   full grid plus ≥15 trials per model. Following the plan's F3 order, the plan's fallbacks were applied:
   * A2 tier-1 = {0.25, 0.5, 0.75, 1.0};
   * one random direction on P100 (the plan's own "if time binds" option);
   * harmless over-refusal generations only at λ ∈ {0, 1.2} (harmless first-token KL is still measured at every λ);
   * tier-2 fills cut.

   C depth, A1 tier-1 and the B floor were untouched.
2. **A1 extension trigger.** The shared OpenRouter key was over its daily limit for the whole GPU block, so the
   judge-based trigger (EN-BT judge R at λ=1.2 > 0.30) was replaced before any A1 generation. The replacement is a
   pre-registered lexicon proxy: run {1.5, 2.0} if lexicon R > 0.20, a lower bar because iter-1 found the lexicon
   under-reads refusal. The judge ran after the GPU block.
3. **Prefill length.** Instead of k = 5 tokens, the full meaning-matched prefix strings shared with the sibling depth
   artifact are used: 13 (EN) and 14 (SL) tokens, recorded in `checks.json`. The judge sees the request and the model's
   continuation only.
4. **Random-direction variance matching was not achievable.** Directions drawn as r ∝ Σ_w^{1/2} g have 8–260× (5th–95th
   percentile) the centred variance of the refusal direction u. None of 200 draws fell in [0.8, 1.25], so the closest
   draw was used (ratio 2.9 for Gemma; see `checks.json:A2_random_directions`). The control is therefore a *stronger*
   perturbation than the real edit. That makes the specificity test conservative, and it inflates the random edit's
   collateral KL/NLL. The same applies per layer to C5a's random LoRA edits (about 20% of layers in band).
5. **Session interruption.** The orchestrating session died at about 22:45 UTC. That killed Gemma's process mid-A2
   (after s = 0.75 had been saved) and the waiting GaMS process (nothing generated). Both were restarted with identical
   code. Every phase resumes from its saved per-step files, and finished steps are never regenerated. The GPU deadline
   moved from 01:20 to 02:40 UTC.
6. **n_B = 29 for both models.** The time-box rule was evaluated by the orchestrator, using t_trial = 132 s and the
   full-run A2 timing (the resumed process would have under-counted A2). This was written before Gemma's trial 2
   finished.
7. **Judge prompt wording.** The judge prompt is iter-1's P1, copied verbatim so that labels pool with the other
   iter-2 artifacts. It says "truncated at 64 tokens", but A/C responses are 128 tokens. The pre-registered
   64-vs-128 truncation check quantifies the effect of this mismatch.
8. **Endpoint.** The judge calls go through `$OPENROUTER_BASE_URL` (the run's proxy), not the public URL.

## Known limitations

* **Reduced precision.** Everything runs in NF4. Batched and single-item outputs are not token-identical (22/32
  identical at 32 tokens) but agree on outcome (30/32 lexicon).
* **Heretic trials.** There are 29 trials per model instead of Heretic's reference 200, and 20 of the 29 are TPE
  start-up (random) draws. B samples the parameter space; it is not "what Heretic would ship".
* **Translation and judge validation.** SL is NLLB MT without a human audit. The judge is an LLM that has not been
  validated on Slovene by humans; the only check is cross-family agreement with gpt-4.1.
* **Scope of the depth link.** The depth link is observational at the item level. Its claims are "predicts", not
  "causes".

## Restoring removed files

The manifest (`.aii/manifest.yaml`) marks only one heavy path for deletion after the round ends:

* **`.venv/`** (≈12 GB, regenerable) — the Python environment. Restore with:
  ```bash
  uv venv .venv --python 3.12
  uv pip install --python .venv/bin/python -r requirements.lock.txt
  ```
* **`src/__pycache__/`, `tests/__pycache__/`, `.pytest_cache/`** (regenerable caches) — recreated automatically:
  ```bash
  .venv/bin/python -m compileall src tests
  .venv/bin/python -m pytest -c pytest.ini tests/
  ```

Everything else stays in place. The two 12B model snapshots and NLLB are **not** in this workspace: they live in
the run's shared HuggingFace cache (`$HF_HOME`) and are redownloaded on demand by `transformers`
(`google/gemma-3-12b-it` @ `96b6f1ec`, `cjvt/GaMS3-12B-Instruct` @ `1d0b27af`,
`facebook/nllb-200-distilled-1.3B`, and the substitute judges `Qwen/Qwen3-8B`,
`meta-llama/Llama-3.1-8B-Instruct`). All experimental outputs (`results/`, `data/`, the per-model generations, the
judge labels, figures, `method_out.json` and its variants) are kept in place and are the artifact's deliverables.
