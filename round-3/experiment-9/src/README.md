# Does English-objective abliteration remove Slovene refusal faster in a Slovene-adapted model?

Iteration-3 **confirmation** of the C-LAG finding plus a **signal-detection mechanism test**, on a fresh probe, with a
pre-registered protocol frozen before the confirmatory generation.

Two sibling 12B instruct models are put through the *same* abliteration machinery with the *same* parameters and the
*same* items, and their **English→Slovene transfer curves** are compared:

| | `gemma_it` (reference) | `gams3_it` (Slovene-adapted) |
|---|---|---|
| repo @ revision | `google/gemma-3-12b-it` @ `96b6f1eccf38110c56df3a15bffe176da04bfd80` | `cjvt/GaMS3-12B-Instruct` @ `1d0b27af5748784482600d24779409e7e1dc9adc` |
| precision | bitsandbytes NF4 (double quant, bf16 compute) — **reduced precision** | identical |
| chat template | official template, empty system turn dropped (rendered sha1 `389de5ab…`, verified in both) | identical |
| decoding | greedy, 128 new tokens, judged at 128 tokens | identical |
| abliteration | `p-e-w/heretic` @ `3521f864…`, iter-1 config verbatim, **English** objective (mlabonne/harmful_behaviors + harmless_alpaca) | identical |
| sampler | `TPESampler(seed=20260925, n_startup_trials=40, multivariate=True)` → all 40 draws are seeded start-up draws, so the two models see **parameter-identical** trials | identical |

**Headline quantity.** For each model, a binomial-logit GLM regresses the Slovene (SL-MT) refusal count of each edit step
on the logit of the same step's English (EN-BT) refusal rate. `a_m` is the predicted Slovene log-odds at *matched* English
refusal 50%; **G3 = a_GaMS − a_Gemma**. G3 < 0 means the Slovene-adapted model loses Slovene refusal faster at matched
English suppression ("Slovene over-exposure"); G3 ≈ 0 means the languages fall in lockstep. Pre-registered margin
m = 0.675 (inherited from iter-1), m_local = 0.20 co-reported.

**Mechanism (new in this artifact).** Every step is also scored on 150 **content-matched benign twins** (XSTest-style
minimal contrasts of the same harmful items), which puts the false-alarm rate off the floor and makes a signal-detection
decomposition identifiable:

* hit H = P(refuse | harmful), false alarm F = P(refuse | benign twin), per step and per language arm;
* d′ = z(H) − z(F) (how well the model *separates* harmful from benign), c_ref = (z(H)+z(F))/2 (how *refusal-prone* it is);
* Δc = mean(c_ref,SL − c_ref,EN) and Δd′ = mean(d′SL − d′EN) over the steps whose English refusal lies in [0.3, 0.7].

A **criterion** account (M-b) predicts Δc > 0 with Δd′ ≈ 0; a **geometry** account (M-a) predicts the reverse.

> **RESULTS: [`RESULTS.md`](RESULTS.md)** — every number there is recomputed from `results/items_final.jsonl` by
> `src/analysis.py`, re-derived by an independent second code path (`src/audit.py` → `results/audit.json`) and rendered
> into `results/summary_tables.md` by `src/write_results.py` (no hand-typed numbers).

## Headline results (see [`RESULTS.md`](RESULTS.md); every number recomputed from `results/items_final.jsonl`)

**1. The Slovene lag replicates on a fresh probe.** On the λ dose curve (9 paired steps per model, English refusal
0.94 → 0.06 in Gemma and 0.93 → 0.04 in GaMS), **G3 = -0.97, 95% CI [-1.56, -0.44]**
(MDE 0.80), i.e. at *matched* English refusal of 50% the Slovene-adapted model's Slovene refusal log-odds are
about one unit lower than the reference model's. The second judge family reproduces the sign and excludes 0
(-1.72 [-2.30, -0.96] on the identical core rows). The effect clears the
pre-registered margin m = 0.675, so the fallback-F3 verdict is **CONFIRM-LAG**.

**2. The confirmatory B′ curve did not survive the compute budget.** The two siblings completed only
7 parameter-identical Heretic trial steps in common, all at high English refusal, so
that fit is *unidentified* and is excluded from the headline rather than reported as a number (amendment A6).

**3. Mechanism: the Slovene criterion shift is real but NOT specific to the Slovene-adapted model.** With
content-matched benign twins, both models refuse more in Slovene at equal discriminability:
Δc = 0.56 [0.25, 0.97] (Gemma) and
0.57 [0.26, 0.84] (GaMS), while the
difference-in-differences is **-0.00 [-0.42, 0.48] — centred on zero**. A criterion account explains why Slovene
refusal survives an English-only edit, but it does *not* explain why the two models differ: that contrast is carried by
d′, whose per-model estimates have opposite signs with intervals that include 0. **Reported as a negative result.**

**4. Unedited false-alarm gap.** On benign twins the unedited models already refuse far more in Slovene than in English
(Gemma 0.26 vs 0.08; GaMS 0.18 vs 0.04), which is what makes the criterion
analysis identifiable at all and is itself a finding about Slovene over-refusal.

**5. Specificity and leakage.** Norm-matched random-direction edits (‖ΔW‖_F matched per module, exactly 1.000) leave
English refusal essentially untouched, so the transfer is not a generic weight-perturbation effect. The C5a excess ratio
is **below 1** in both models (0.32 and 0.62), i.e. the English-objective edit does *not* leak into Slovene
first-token distributions more than a matched random edit does — evidence against a simple "collateral damage" account.

## What is compared (baselines and controls)

1. **Unedited model** (λ = 0) — the anchor of every curve, scored on all 300 harmful + 150 benign items in three arms.
2. **Norm-matched random-direction edits** (5 seeds) — the field's standard specificity control. Each random direction is
   drawn per layer, orthogonalised against the Heretic direction the selected edit used, zeroed on the massive residual
   dimension, and then **rescaled so that every module's ‖ΔW‖_F equals the selected edit's**. Each seed reports its own
   collateral (Heretic KL, first-token KL on EN/SL stems).
3. **Dose–response, twice**: 40 paired Heretic trials (B′, the confirmatory curve) and a 9-point λ scaling of each model's
   selected edit — per-step points are shown, not only the fitted line, plus an isotonic fit.
4. **Item-matched language arms**: EN-orig → SL-MT → EN-BT, all from one English source via NLLB-200-distilled-1.3B.
   The language effect is SL-MT vs EN-BT; the MT-noise effect is EN-BT vs EN-orig (measured at λ ∈ {0, 1}).
5. **Sibling control** — the same base family, same config, same seed, same precision, same template.
6. **Placebos** — model-label swap within paired trials and language-label swap within items (2,000 permutations each);
   both must centre at 0.

## Layout

| path | what |
|---|---|
| `run_all.sh` | the whole pipeline in execution order (every step resumable) |
| `method.py` | CPU entry point after the GPU phases: analysis → audit → figures → `method_out.json` |
| `protocol.yaml`, `protocol.sha256` | frozen protocol (git-committed before the confirmatory generation) |
| `results/protocol_amendments.json` | every deviation, timestamped, written before the work it affects |
| `src/prep_data.py` | S2 data: exclusions → P300 probe + DEV12, benign twins, NLLB MT/back-translation, chrF/langid QA |
| `src/twins_vllm.py` | GPU twin rewriting + two-family SAFE screen (same prompts as `prep_data.stage_twins`) |
| `src/phase_a.py` | S5 per model: Heretic setup, 40 paired trials (+ adapter export), non-interference replay, selection, λ adapters, norm-matched random edits, C5a KL, HF reference generations for the engine gate |
| `src/gen_vllm.py` | S4 engine gate + S6 Phase B generation through vLLM (bnb 4-bit + LoRA adapters) |
| `src/judge_distill.py` | J1 primary judge: gemini-distilled mdeberta-v3 classifier (train + predict) |
| `src/judge_llm.py` | J2 second-family judge: local LLM with the frozen P1 prompt and first-token class log-probs |
| `src/adjudicate.py` | blind adjudication sample (labels written by the executing agent — **not** a human) |
| `src/analysis.py` | S8 statistics → `results/analysis.json` |
| `src/audit.py` | S9 independent second code path → `results/audit.json` |
| `src/write_results.py` | renders `results/summary_tables.md` from `analysis.json` |
| `src/make_figs.py` | `figures/fig1..fig5` (png + pdf) |
| `src/stats_core.py`, `src/common.py`, `src/probe.py`, `src/probe_tok.py`, `src/orclient.py` | statistics, constants/lexicon/judge prompt, GPU probe helpers, torch-free tokenisation, OpenRouter client with a hard-capped ledger |
| `tests/test_stats.py` | T0 unit checks (G3 recovery, bootstrap coverage, SDT branch recovery, rotating blocks, Rogan–Gladen, parsers) |
| `data/` | probe, twins, split manifest with sha256, provenance, contamination report |
| `adapters/{model}/` | every trial adapter, the λ grid and the random-direction edits (PEFT format) |
| `selected/{model}/` | the selected operating point: adapter + Optuna journal + trials + residual directions |
| `results/{model}/` | `gens.jsonl` (all scored generations), `gens_j1.jsonl`, `gens_j2.jsonl`, `trials.json`, `phase_a_checks.json`, `c5a_kl.jsonl`, `engine_gate*.json`, `gen_timing.json` |
| `results/items_final.jsonl` | the per-item table every statistic is computed from |
| `judge_model/mdeberta_gemini_distill/model_parts/` | the trained J1 classifier, stored as 12 x 95 MB parts (the 1.06 GB fp32 checkpoint exceeds the 100 MB per-file publishing limit); `src/judge_model_io.py:ensure_model_file()` reassembles it (sha256-verified) on every load, and `split_model_file()` re-splits after training |
| `logs/` | full run logs |

Absolute workspace path of the kept artifacts (they are **not** pushed to GitHub if ≥ 100 MB):
`./{selected,adapters,results,data}`.

## Data and separation rules

* **Universe**: RefusEU (`NASK-PIB/RefusEU` @ `5523ce30b9`) English train+test rows, through iter-1's pairing.
  The RefusEU **`evaluation` config is never loaded** (reserved for later confirmation artifacts).
* **Excluded by id and by normalised text**: iter-1 exp1/exp2 CONSTRUCT, exp4 trial-probe/construct/SCORE-400,
  exp8 P200/DEV20/construct_A2, exact matches to `mlabonne/harmful_behaviors` (Heretic's own objective set), and any item
  with an exact or ≥50% word-8-gram overlap with the reserved `refuseu_eval` / `refuseu_x_mt` blocks of the dependency
  dataset. Counts per rule: `data/contamination_P300.json`.
* **P300** is drawn by category round robin (each category in sha1(item_id + seed) order) over what remains, then split
  into a core block **C** (100 items, scored at *every* step), four rotating blocks **R1..R4** (50 each) and a
  second-judge core **G** (the first 50 of C). **DEV12** is used only for smoke tests and the engine gate.
* **Benign twins (T150)**: minimal-contrast rewrites of the first 200 P300 items, screened SAFE by two local model
  families, with alpaca/dolly/HARD overlap filters; blocks **HC** (60, every step), **HR1..HR3** (30 each, rotating),
  **GH** (first 25 of HC).
* **MT**: NLLB-200-distilled-1.3B (fp16, 4 beams) EN→SL→EN. chrF(EN-orig, EN-BT) and Slovene language-ID are gated and
  reported per item; `mt_fragile` items are dropped in a sensitivity run. **There is no native-speaker audit.**

## How to run

```bash
uv venv .venv --python 3.12       && uv pip install --python .venv/bin/python -r requirements.lock.txt
uv venv .venv_vllm --python 3.12  && uv pip install --python .venv_vllm/bin/python -r requirements_vllm.lock.txt
./run_all.sh
```
One NVIDIA L4 (23 GB), torch 2.14.0+cu130 / transformers 5.17.0 (HF env) and vLLM 0.30.0 (generation env).
`gcc` must be installed (`apt-get install -y gcc`): torch 2.14 compiles a Triton kernel at the first `generate`.

## What this artifact did NOT deliver (and why)

| planned | delivered | reason |
|---|---|---|
| paid judges (`gemini-2.5-flash`, `gpt-4.1-mini`) | a classifier distilled from **archived real gemini labels** (J1, κ_R = 0.84 vs held-out gemini) + a local second family (J2 = Llama-3.1-8B, κ_R = 0.58) | the run's OpenRouter budget was exhausted before this artifact started (`results/key_probe.json`); amendments A1, A2 |
| 40 paired Heretic trial steps scored in both models | 40 trials *run and exported* in both models; **7** scored in both (18 in Gemma) | vLLM 0.30 dropped bitsandbytes, the FP8 engine failed the equivalence gate, and engine load + 4.5 items/s ate the window; amendments A5, A6 |
| NF4 generation matching the Heretic objective | FP8 generation, **same engine for both siblings** | amendment A5; the equivalence gate numbers are in `results/gemma_it/engine_gate.json` and the failure is reported, not hidden |
| rotating item blocks R1–R4 / HR1–HR3 | core blocks C (100 harmful) + HC (60 benign) at every step; full P300 + T150 at λ = 0 | cut ladder A step 1 |
| 5 random-direction seeds per model | 3 seeds scored for Gemma, 0 for GaMS | generation deadline; the specificity control is Gemma-only |
| blind adjudication by the executing agent | sample drawn (`results/adjudication_items.jsonl`), **not labelled** | the misclassification correction instead uses the 2,755-row held-out gemini validation of J1, which is a stronger error-matrix source |

Everything above is recorded in `results/protocol_amendments.json`, each entry written before the work it affected.

## Restoring removed files

`.aii/manifest.yaml` marks only regenerable environments for deletion:

* **`.venv/`, `.venv_vllm/`** — Python environments:
  ```bash
  uv venv .venv --python 3.12      && uv pip install --python .venv/bin/python -r requirements.lock.txt
  uv venv .venv_vllm --python 3.12 && uv pip install --python .venv_vllm/bin/python -r requirements_vllm.lock.txt
  ```
* **`__pycache__/`** — recreated by `python -m compileall src tests`.

`adapters/` (1.8 GB) and `judge_model/` (1.1 GB) are **kept on the run volume** but excluded from the GitHub push
(`upload_ignore_regexes`), because they are large binaries rather than source. Their workspace paths are
`.../gen_art_experiment_9/adapters/{model}/` and `.../gen_art_experiment_9/judge_model/mdeberta_gemini_distill/`;
any trial adapter can also be rebuilt from `selected/{model}/heretic_study.journal` plus
`results/{model}/residual_directions.pt` (see `reproducibility.md`), and the judge can be retrained with
`.venv/bin/python src/judge_distill.py train`.

Model weights live in the run's shared HuggingFace cache (`$HF_HOME`), not in this repository, and are re-downloaded on
demand: `google/gemma-3-12b-it` @ `96b6f1ec`, `cjvt/GaMS3-12B-Instruct` @ `1d0b27af`, `facebook/nllb-200-distilled-1.3B`,
`microsoft/mdeberta-v3-base`, `Qwen/Qwen3-8B`, `meta-llama/Llama-3.1-8B-Instruct`.

Everything else — `data/`, `results/`, `adapters/`, `selected/`, `judge_model/`, `figures/`, `method_out.json`,
`logs/` — is kept in place and is this artifact's deliverable.
