# Reproducibility

## Hardware and software

* 1 x NVIDIA L4 (23 GB), AMD EPYC 9254 (48 vCPU visible), 503 GB RAM, Linux 6.8.
* Two pinned environments (both Python 3.12, `uv` only):
  * `requirements.lock.txt` — HF + Heretic: torch 2.14.0+cu130, transformers 5.17.0, peft 0.21.0, bitsandbytes 0.50.2,
    optuna 4.9.0, `heretic-llm @ git+https://github.com/p-e-w/heretic@3521f8648a0dccf6e12a92666862632235fac7e6`.
  * `requirements_vllm.lock.txt` — generation and the second-family judge: vllm 0.30.0, torch 2.13.0+cu130,
    transformers 5.17.0, bitsandbytes 0.50.2.
* `apt-get install -y gcc g++` is required: torch 2.14 compiles a Triton kernel at the first `generate` call.
  (The alternative, `torch._native.registry.deregister_op_overrides(disable_dsl_names=["triton", ...])`, is applied
  defensively in `src/phase_a.py` and logged as `phase_a_checks.json:triton`.)
* `resource.setrlimit(RLIMIT_AS)` is deliberately **not** used (it breaks safetensors mmap); VRAM is capped with
  `torch.cuda.set_per_process_memory_fraction` instead (0.95 for the Heretic process, 0.30 for the judge trainer that
  shares the GPU with it).

## Seeds and determinism

* Global seed 20260925. `TPESampler(seed=20260925, n_startup_trials=40)` — with `n_startup_trials == n_trials` every
  draw comes from the sampler's seeded `RandomSampler`, so the two models receive **identical parameters** trial by
  trial. `results/analysis.json:pairing_check` reports how many of the 40 parameter sets matched exactly.
* Random-direction control seeds: 20260926..20260930 (`SEED + s`), with replacement of a catastrophic draw logged in
  `phase_a_checks.json:random_replaced_seeds`.
* Bootstrap: 2,000 draws, `numpy.random.default_rng(20260925)`; permutation placebos: 2,000 draws from the same stream.
* Decoding is greedy everywhere; vLLM runs with `seed=0` and `temperature=0`.

## Known non-determinism

* NF4 quantisation plus batched attention is **not** token-identical to single-item decoding
  (`phase_a_checks.json:batch_vs_single` reports both token identity and outcome agreement).
* vLLM and HF differ numerically; the pre-registered engine gate (`results/{model}/engine_gate.json`) quantifies the
  difference on DEV12 + 40 harmless prompts at λ ∈ {0, 1} (first-token top-1 agreement, outcome agreement, throughput
  ratio, adapter effect) before any confirmatory generation is accepted.
* `torch.svd_lowrank` inside Heretic's `row_normalization = "full"` path is randomized but reseeded immediately before
  each call with the configured seed, so a trial can be rebuilt from its parameters.

## Rebuilding any single step

Each trial adapter in `adapters/{model}/trial_KK/` carries `meta.json` with the trial index, its objective values
(`[refusal rate, KL]`) and the sha1 of its LoRA tensors. Any trial can also be rebuilt from
`selected/{model}/heretic_study.journal` plus `results/{model}/residual_directions.pt` by replaying
`Model.abliterate(residual_directions, direction_index, parameters)` — this is exactly what the non-interference replay
of trial 1 does (`phase_a_checks.json:replay_trial1`, which must report identical objective values and an identical LoRA
hash).

## Statistical code paths

Every headline number is computed twice: `src/analysis.py` (IRLS GLM, vectorised bootstrap) and `src/audit.py`
(scipy BFGS MLE, dictionary counting, no shared helpers). `results/audit.json` lists each comparison and the absolute
difference; `results/summary_tables.md` and `RESULTS.md` are rendered from `analysis.json` so no number is typed by hand.

## What cannot be reproduced from this repository alone

* The archived `google/gemini-2.5-flash` labels used to train the primary judge come from earlier artifacts of this run
  (`iter_2/.../gen_art_experiment_8/results/items_final.jsonl` and `iter_1/.../gen_art_experiment_1/outputs/judge_gemini.jsonl`).
  The run's OpenRouter budget was exhausted before this artifact started (`results/key_probe.json`,
  `results/judge_ledger.jsonl`), so those labels cannot be regenerated here.
* Model weights are pulled from the HuggingFace Hub at the pinned revisions and are not stored in this repository.

---

# What was ACTUALLY run (chronological, Ubuntu / Linux 6.8, one NVIDIA L4 23 GB)

## 0. System packages and environments

```bash
apt-get update -qq && apt-get install -y gcc g++          # torch 2.14 JIT-compiles a Triton kernel on first generate
uv venv .venv       --python 3.12 && uv pip install --python .venv/bin/python      -r requirements.lock.txt
uv venv .venv_vllm  --python 3.12 && uv pip install --python .venv_vllm/bin/python -r requirements_vllm.lock.txt
# vLLM 0.30 needs a CUDA toolchain for its FlashInfer/Triton JIT; without it the engine dies with
# "Could not find nvcc and default cuda_home='/usr/local/cuda' doesn't exist":
uv pip install --python .venv_vllm/bin/python nvidia-cuda-nvcc-cu13 nvidia-cuda-runtime-cu13 nvidia-cuda-nvrtc-cu13
source scratch/vllm_env.sh    # sets CUDA_HOME/PATH to that wheel, VLLM_USE_FLASHINFER_SAMPLER=0
```
Exact versions: `pyproject.toml` (`dependencies` = the HF/Heretic env, `optional-dependencies.vllm` = the vLLM env),
mirrored in `requirements.lock.txt` and `requirements_vllm.lock.txt`.

## 1. Environment variables (names only)

`HF_TOKEN` (gated Gemma-3 access), `HF_HOME` / `HF_HUB_CACHE` / `HF_DATASETS_CACHE` (shared model cache),
`OPENROUTER_BASE_URL`, `OPENROUTER_API_KEY` (probed, then unused — see below).

## 2. Downloads

`google/gemma-3-12b-it@96b6f1ec`, `cjvt/GaMS3-12B-Instruct@1d0b27af`, `facebook/nllb-200-distilled-1.3B`,
`microsoft/mdeberta-v3-base`, `Qwen/Qwen3-8B`, `meta-llama/Llama-3.1-8B-Instruct`; HF datasets
`mlabonne/harmful_behaviors`, `mlabonne/harmless_alpaca`, `tatsu-lab/alpaca`, `databricks/databricks-dolly-15k`.
Read-only iter-1/iter-2 artifact paths are listed in `README.md` ("Data and separation rules").

## 3. Commands, in the order they were run (seeds are in `protocol.yaml`; global seed 20260925)

```bash
(cd src && ../.venv/bin/python key_probe.py)              # -> results/key_probe.json: 403 aii_run_budget_exhausted
(cd src && ../.venv/bin/python prep_data.py pool)         # ~6 min (NLLB on GPU)
.venv/bin/python -u src/phase_a.py --model gemma_it       # 59 min: 40 trials, select, lambda + random adapters, C5a, HF gate refs
.venv/bin/python -u src/judge_distill.py train            # 18 min (shares the GPU; fp32 - bf16 autocast makes DeBERTa-v2 NaN)
.venv_vllm/bin/python -u src/twins_vllm.py                # 14 min: Qwen3-8B rewrites + 2-family SAFE screen
(cd src && ../.venv/bin/python prep_data.py twins_finalize && ../.venv/bin/python prep_data.py twins_mt)
.venv/bin/python -u src/phase_a.py --model gams3_it       # 41 min
(cd src && ../.venv/bin/python write_protocol.py)         # FREEZE: protocol.yaml + protocol.sha256, git-committed
.venv_vllm/bin/python -u src/gen_vllm.py --model gemma_it --mode gate --quant fp8     # engine gate -> FAILED (amendment A5)
.venv_vllm/bin/python -u src/gen_vllm.py --model gemma_it  --mode full --quant fp8 --core-only --max-trials 18 \
        --n-random 3 --gpu-util 0.92 --deadline-epoch <t>  # 42 min, 10,630 generations
.venv_vllm/bin/python -u src/gen_vllm.py --model gams3_it --mode full --quant fp8 --core-only --max-trials 18 \
        --n-random 3 --gpu-util 0.92 --deadline-epoch <t>  # 23 min, 6,150 generations (stopped by its deadline)
./finalize.sh                                              # J1 (3 min) -> J2 calib+score (26 min) -> analysis -> audit -> figures -> method_out.json
.venv/bin/python src/rederive_headline.py                  # third code path + placebo
.venv/bin/python -m pytest -c pytest.ini tests/            # 10 passed
```
Total wall clock ≈ 5 h 15 min on one L4.

## 4. Deviations that a re-run will hit as well

`results/protocol_amendments.json` A1–A6: the OpenRouter budget was already exhausted (so the judges are local),
vLLM 0.30 no longer accepts `quantization="bitsandbytes"` (so generation is FP8 and the equivalence gate **fails**),
and the trial curve was truncated to 7 paired steps. Re-running with a working key and a bitsandbytes-capable vLLM
would change the absolute refusal levels and should restore the 40-step B′ curve.

## 5. Outputs a reader should get, and where they appear

| file | what to check |
|---|---|
| `results/analysis.json` | `G3["lambda|j1|R1"]["G3"] = -0.970`, 95% CI [-1.56, -0.44]; `verdict_F3.verdict = "CONFIRM-LAG (F3 lambda curve)"` |
| `results/audit.json` | `all_pass = true` over 23 checks (second code path) |
| `results/rederive_headline.json` | third code path reproduces G3 to 3e-8; placebo p = 0.085 (test correctly fails) |
| `results/summary_tables.md`, `RESULTS.md` | every table, rendered from `analysis.json` — no hand-typed numbers |
| `results/items_final.jsonl` | 16,780 scored rows, the input of every statistic |
| `figures/fig1..fig5` | transfer curves, G3 forest, SDT per step, C5a, judge kappa |
| `method_out.json` | 3,900 harmful + 2,250 benign paired examples, `exp_gen_sol_out` schema |

## 6. The J1 checkpoint is stored split

`judge_model/mdeberta_gemini_distill/model.safetensors` (1.06 GB) is kept as
`model_parts/model.safetensors.part_001..012` plus `model_parts/manifest.json` (sha256 of the whole file).
`src/judge_distill.py` calls `ensure_model_file()` before loading, so no manual step is needed; to rebuild it by hand:

```bash
.venv/bin/python src/judge_model_io.py ensure   # reassemble (verifies sha256)
.venv/bin/python src/judge_model_io.py split    # re-split after retraining
```
