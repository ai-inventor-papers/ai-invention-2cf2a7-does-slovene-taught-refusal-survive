# Reproducing this artifact (Ubuntu, step by step)

This describes **what was actually run**, including the two things that went wrong and how they were handled
(the paid judge was unavailable, and the RQ4 process pool hung). Nothing here is an idealised rerun.

---

## 0. What you need

| | |
|---|---|
| OS | Ubuntu 22.04 (container), kernel 6.8 |
| GPU | 1 × **NVIDIA L4, 23 GB VRAM** (the whole study fits in NF4; bf16 12B does **not** fit) |
| CPU / RAM | 48 cores / 503 GB (only the RQ4 probes and the bootstraps are CPU-heavy) |
| Disk | ~60 GB free: ~26 GB model weights in the shared HF cache, 17 GB activations, 11 GB venv |
| Python | **3.12** (`requires-python = ">=3.12,<3.13"`) |
| Time | ≈ 5.5 h wall-clock end to end (breakdown in §5) |

System packages: a stock `ubuntu:22.04` plus `git`, `curl` and `uv` is enough — no `nvcc`, no build toolchain
(the pinned wheels are all binary). **Do not** install a C compiler expecting Triton to work; see the trap in §6.

## 1. Copy the artifact and create the environment

```bash
cp -r gen_art_experiment_10 ~/work && cd ~/work
uv venv .venv --python=3.12
uv pip install --python .venv/bin/python -r pyproject.toml     # 164 pinned deps, ~10 min on a cold cache
.venv/bin/python -c "import torch,transformers,peft,bitsandbytes;print(torch.__version__, torch.cuda.is_available())"
# expect: 2.14.0+cu130 True
```

`pyproject.toml` is pinned to exactly what ran (`uv pip freeze` output is also kept verbatim in
`requirements.lock.txt`). The load-bearing versions: `torch==2.14.0`, `transformers==5.17.0`, `peft==0.21.0`,
`bitsandbytes==0.50.2`, `scikit-learn==1.9.1`, `numpy==2.5.3`, `scipy==1.18.1`, `langid==1.1.6`, `sacrebleu==2.6.0`.
`heretic-llm @ git+…@3521f864` is pinned but **only** its config is read — the models are loaded with plain HF + peft.

## 2. Downloads and environment variables

Models (pinned revisions; ~26 GB total). Set `HF_HOME` to a shared cache **before** downloading:

```bash
export HF_HOME=/path/to/shared_cache/hf          # HF_HUB_CACHE/TRANSFORMERS_CACHE derive from this
hf download google/gemma-3-12b-it              --revision 96b6f1eccf38110c56df3a15bffe176da04bfd80
hf download cjvt/GaMS3-12B-Instruct            --revision 1d0b27af5748784482600d24779409e7e1dc9adc
hf download facebook/nllb-200-distilled-1.3B   --revision 7be3e24664b38ce1cac29b8aeed6911aa0cf0576
hf download Qwen/Qwen3-14B                     --revision 40c069824f4251a91eefaf281ebe4c544efd3e18
```

`databricks/databricks-dolly-15k` and `tatsu-lab/alpaca` are pulled by `src/prep_data.py` itself (their resolved
revision shas are written into `data/split_manifest.json`).

**Environment variables — names only, never values:**

| name | needed for |
|---|---|
| `HF_TOKEN` | gated Gemma-3 weights |
| `HF_HOME` | shared model cache (do **not** also set `TRANSFORMERS_CACHE` to the same path — it double-stores) |
| `OPENROUTER_BASE_URL`, `OPENROUTER_API_KEY` | the *planned* gemini judge. **In this run these were present but the key returned HTTP 403 `aii_run_budget_exhausted`, so no paid call was ever made** — see §4. Reproducing without them yields identical results, because the readout that was actually used is local. |

**Read-only inputs from earlier artifacts** (absolute paths, existence + sha256 checked at start-up into
`logs/inputs_check.json`): exp8 `data/probe_P200.jsonl` (sha256 `e152fe54…`) and `data/construct_A2.jsonl`
(`93c99356…`), exp8 `results/judge_labels.jsonl` (the archived **real** gemini labels the surrogate is trained on),
iter-1 `gen_art_experiment_4/results/{gemma_it,gams3_it}/selected_adapter/`, and the iter-1 dataset
`gen_art_dataset_1/full_data_out.json`.

## 3. The exact commands, in order

Seed is **20260925** everywhere (splits, bootstraps, random directions); it is hard-coded in `src/common.py`.

```bash
# T0 — unit tests (CPU, ~3 min). 10 tests.
.venv/bin/python -m pytest -q

# S0/S1 — input check + data build (NLLB on GPU, ~9 min)
.venv/bin/python src/prep_data.py

# Per model, pass 1: load, T1 smoke asserts, activations, geometry, ALL DEV generations
.venv/bin/python src/gpu_block.py --model gemma_it --phases smoke,acts,geom,devgen
.venv/bin/python src/gpu_block.py --model gams3_it --phases smoke,acts,geom,devgen

# Judge selection (CPU, ~7 min) — fits the surrogate and picks the readout BEFORE any TEST row exists
.venv/bin/python src/judge_local.py --judge qwen --calib --model gemma_it --what dev   # gate the LLM judge
.venv/bin/python src/judge_surrogate.py --fit

# DEV decisions (L*, alpha-grid multiplier, lambda*) from DEV rows + surrogate labels
.venv/bin/python src/judge_surrogate.py --apply gemma_it dev
.venv/bin/python src/dev_decide.py --model gemma_it --judge surrogate/gemini
.venv/bin/python src/judge_surrogate.py --apply gams3_it dev
.venv/bin/python src/dev_decide.py --model gams3_it --judge surrogate/gemini

# Per model, pass 2: band rule -> PROTOCOL FREEZE (git commit) -> TEST induction, add-on, RQ4 activations
.venv/bin/python src/gpu_block.py --model gemma_it --phases dev,freeze,induce,addon,rq4
.venv/bin/python src/gpu_block.py --model gams3_it --phases dev,freeze,induce,addon,rq4

# Label all TEST rows + second family + blind adjudication sample
.venv/bin/python src/judge_surrogate.py --apply gemma_it test
.venv/bin/python src/judge_surrogate.py --apply gams3_it test
.venv/bin/python src/judge_local.py --judge qwen --what second       # Qwen3-14B on a stratified 10% sample
.venv/bin/python src/adjudicate.py --sample --model gemma_it         # writes adjudication_items_blind_*.jsonl
.venv/bin/python src/adjudicate.py --sample --model gams3_it
#   -> the adjudicator (here: the executor agent, author model, NOT a human) reads ONLY
#      results/adjudication_items_blind_<M>.jsonl and writes results/adjudication_blind_<M>.jsonl
#      (fields: adj_id, label in {REFUSE,PARTIAL,COMPLY}) BEFORE looking at adjudication_key_<M>.jsonl.

# RQ4 probes, analysis, independent audit, figures, outputs
.venv/bin/python src/rq4.py --model gemma_it --workers 14
.venv/bin/python src/rq4.py --model gams3_it --workers 14
.venv/bin/python src/analysis.py
.venv/bin/python src/audit.py
.venv/bin/python src/reconcile_readme.py
.venv/bin/python src/summarize.py
.venv/bin/python src/make_figs.py
.venv/bin/python src/make_outputs.py
```

`method.py --stage {data,gemma,gams,judge,analysis}` wraps the same sequence; `run_chain.sh` / `run_chain2.sh` are the
resumable GPU chains actually used (every phase skips itself if its output file is already complete, so a crashed run
is restarted with the identical command).

## 4. The judge substitution (the single largest deviation — read before comparing numbers)

The frozen protocol names **gemini-2.5-flash**. The run's OpenRouter budget was exhausted *before* this artifact
started: every call returns HTTP 403 `aii_run_budget_exhausted` ("does not reset while this run goes on"), and
`:free` slugs return 404. `results/judge_probe.json` records the refused probe call and
`results/judge_ledger.jsonl` shows **$0.00 spent** (budget cap was $10; nothing was charged).

Fallback F1 ran, in this order, and is fully reproducible offline:

1. **Local Qwen3-14B judge — gated and REJECTED.** Against 530 archived *real* gemini labels it scored
   κ = **0.25 (EN) / 0.33 (SL)** on edited rows (`results/judge_calib_qwen.json`).
2. **Primary readout = `surrogate/gemini`** (`results/surrogate_model.pkl`): char+word TF-IDF → multinomial LR,
   trained on **11,767 archived gemini-2.5-flash labels** of exp8 Gemma rows, same frozen prompt, 64-token responses.
   Its candidate set and selection rule were written **before any TEST row existed**; grouped-CV κ on edited rows
   **EN 0.68 / SL 0.82** (`results/judge_surrogate_selection.json`).
3. **Blind agent adjudication** → per model × language error matrices → Rogan-Gladen corrected headlines.

The surrogate is Gemma-trained and **over-calls REFUSE on GaMS** (specificity 0.57/0.59). That is measured, not
hidden: cross-model statistics are therefore also reported under the judge-free lexicon and first-token-log-odds
proxies, where they replicate.

## 5. Runtime actually observed (L4, NF4)

| stage | Gemma | GaMS |
|---|---|---|
| model load | 2.9 min | 33.1 min (cold shared FS) |
| T1 smoke | 0.1 | 5.0 |
| construct activations | 1.8 | 2.6 |
| geometry (+ 2000-draw bootstrap) | 0.4 | 0.4 |
| DEV generations | 15.2 | 15.2 |
| TEST induction (7,776 rows) | 18.3 | 60.0 |
| TEST add-on (7,328 rows) | 28.7 | 74.9 |
| RQ4 activations | 3.0 | 6.9 |

Plus, off-GPU: data build 9 min, surrogate fit 7 min, Qwen sample ~10 min, RQ4 probes ~8 min/model,
analysis+audit ~4 min. **Total ≈ 5.5 h.**

## 6. Traps that will bite a rerun

* **fp16 activations overflow.** Gemma's residual coordinates exceed 65 504, so activations are stored **float32**
  (17 GB). Storing fp16 silently produces `inf` and a corrupted geometry.
* **Triton on torch 2.14 with no C compiler.** `src/gpu_block.py` calls
  `torch._native.registry.deregister_op_overrides(disable_dsl_names=["triton",...])` at import and passes
  `disable_compile=True` to `generate`. Removing either hangs generation.
* **`ProcessPoolExecutor(mp_context="spawn")` hangs on the shared network FS** — spawn workers stall importing, and
  killing the parent leaves orphans spinning at 20 % CPU each (load average 60, which then starves everything else).
  `src/rq4.py` therefore uses a **fork pool with `OMP_NUM_THREADS=1`**; multi-threaded BLAS on these small matrices
  also spins pathologically. If a run is interrupted, check for stray `multiprocessing.spawn` processes.
* **Batched bf16 generation is not bit-identical to single-prompt generation** (smoke check g: 24–26/32 exactly
  identical, 30/32 identical in the first 40 characters). This is logged as a limitation, not an abort.
* **Never `setrlimit(RLIMIT_AS)`** with CUDA — it kills the context.

## 7. What a reader should get, and where it appears

> **Note on `acts/`.** The 17 GB of float32 residual activations were **deleted after the analysis** to respect the
> 100 MB per-file publishing limit (they are declared `delete: regenerable` in `.aii/manifest.yaml`). Nothing in the
> analysis, figures or audit reads them any more: the derived artifacts (`results/<M>/directions_*.npz`,
> `geometry_*.json`, `results/rq4.json`) are kept, and `results/acts_Lstar/` retains the 14 MB of L\*-layer slices that
> `src/audit.py` needs to re-derive the RQ4 AUROC. Rebuild the full set with
> `src/gpu_block.py --model <M> --phases acts` and `--phases rq4` (~10 min total on an L4) only if you want to rerun
> `src/rq4.py` or the geometry from scratch.

Outputs: `method_out.json` + `full_/mini_/preview_` variants (schema `exp_gen_sol_out`, 30,208 examples — one per
TEST generation), `results/analysis.json` (every statistic), `results/summary_tables.md` (human-readable tables),
`results/audit.json`, `results/reconcile_readme.json`, `results/rq4.json`, `figures/fig1…fig5` (PDF + PNG).

Headline numbers to expect (all recomputed by `src/reconcile_readme.py`, **38/38 match**):

| number | value | where |
|---|---|---|
| Gemma Lag(E0) — the Slovene refusal lag | **1.98 logits [1.41, 2.73]** (R_EN .64 / R_SL .93) | abstract, add-on table, `fig4` |
| GaMS Lag(E0) — control | **−0.33 [−0.70, 0.07]** (no lag) | add-on table, `fig4` |
| G3_op = Lag_GaMS − Lag_Gemma | **−2.30 [−3.12, −1.61]** (lexicon proxy −2.31) | cross-model replication |
| M-a test: f contrast (Gemma − GaMS) | **+0.010 [0.005, 0.014]** → *refuted* (wrong sign) | geometry table, `fig1` |
| cos(r_EN, r_SL) at L\* | **.99 both models** (split-half ceiling .998) | geometry table, `fig1` |
| M-b test: `u_SLperp` α50 | **right-censored (> K=3) in both languages, both models** → *refuted* | induction table, `fig2` |
| M-b add-on: `A_perp` cut − random | **0.17 [−0.09, 0.44]** at s=1 → *not met* | add-on criteria |
| Rival: `u_lang` α50 SL / R_lang | **0.65 [0.46, 0.79]** / **4.64 [2.64, 5.95]** (exploratory) | induction table, `fig2` |
| RQ4 probe AUROC, every state | **1.000** (shuffled control ≈ .50) | RQ4 table, `fig5` |
| Verdict | **`neither`** mechanism, both models | verdict table |

Exact reproduction of the *generations* requires the same GPU class; batched bf16 decoding is not bit-identical
across hardware. The **analysis is fully deterministic** given the saved `results/test/*/*.jsonl` — rerunning
`src/analysis.py`, `src/audit.py` and `src/reconcile_readme.py` on the shipped files reproduces every number above
exactly (audit 127/127, reconcile 38/38).
