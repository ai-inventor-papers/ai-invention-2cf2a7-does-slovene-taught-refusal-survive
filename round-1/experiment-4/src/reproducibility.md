# Reproducibility: English de-censoring and Slovene (dir5, SCREEN-SPEC v1)

Everything below is taken from the files in this folder (`README.md`, `run_all.sh`, `finalize.sh`, `method.py`,
`pyproject.toml`, `requirements.lock.txt`, `protocol.json`, `results/*`). Points the workspace does not record are marked
**not recorded**.

## 1. Get the artifact
This folder is one folder of a public GitHub repository. Clone that repository and `cd` into this folder
(`gen_art_experiment_4`). All paths below are relative to it. The repository URL is not recorded in the workspace.

All per-item outputs, splits, the frozen protocol and analysis results are already committed, so the analysis stage
(section 5) can be re-run on CPU without a GPU or any download.

## 2. System, Python, environment
- Ubuntu (Linux 6.17 kernel on the analysis host). The GPU pod's OS is not recorded. A C compiler (gcc) was installed on
  the pod because Triton needs one (README, "Compilation"); `TORCHDYNAMO_DISABLE=1` is set by `src/run_model.py`.
- Python `>=3.12,<3.13` (`pyproject.toml`), managed with `uv`.
- Create the environment and install the pins (`requirements.lock.txt` matches `pyproject.toml`):
  ```bash
  uv venv .venv --python 3.12
  uv pip install --python .venv/bin/python -r requirements.lock.txt
  ```
  Key pins: torch 2.14.0 (CUDA 13.0 wheels, nvidia-*-cu13), transformers 5.17.0, bitsandbytes 0.50.2, peft 0.21.0,
  accelerate 1.15.0, optuna 4.9.0, datasets 4.8.5, huggingface-hub 1.32.0, numpy 2.5.3, scipy 1.18.1,
  scikit-learn 1.9.1, statsmodels 0.15.0, matplotlib 3.11.2, and Heretic
  `heretic-llm @ git+https://github.com/p-e-w/heretic@3521f8648a0dccf6e12a92666862632235fac7e6`.
  A copy of Heretic's `main.py`, `model.py`, `evaluator.py` at that commit is in `src/heretic_ref/`;
  `src/heretic_ref/objective.diff` shows the only lines added to `objective()`.

## 3. Downloads, keys, environment variables
- Models (about 24 GB, never stored here):
  - `google/gemma-3-12b-it` (resolved sha `96b6f1eccf38110c56df3a15bffe176da04bfd80`, from `results/gemma_it/checks.json`)
  - `cjvt/GaMS3-12B-Instruct` at revision `1d0b27af5748784482600d24779409e7e1dc9adc`
  ```bash
  huggingface-cli download google/gemma-3-12b-it
  huggingface-cli download cjvt/GaMS3-12B-Instruct --revision 1d0b27af5748784482600d24779409e7e1dc9adc
  ```
  The runs loaded models from a shared HF cache (`HF_HOME`). Gemma-3 is a gated model and may need an HF login
  (token name not recorded).
- Datasets (fetched by `src/prep_data.py` via `datasets.load_dataset`): `NASK-PIB/RefusEU` (configs `lang_en`, `lang_sl`;
  train+test only, the `evaluation` split is never loaded), `cjvt/slovenian-llm-eval` (`arc_challenge`, `hellaswag`),
  `allenai/ai2_arc` (ARC-Challenge), `Rowan/hellaswag`, `mlabonne/harmless_alpaca` (`train[400:600]`).
  Exact download URLs and dataset revisions were not recorded beyond these ids; splits are pinned by sha256 in `protocol.json`.
- API key, by name only: `OPENROUTER_API_KEY` (used by `src/openrouter.py`, `src/prep_openrouter.py`, `src/judge.py`,
  `finalize.sh`). Judge/MT/pair-grading model: `google/gemini-2.5-flash`.
- Optional env vars: `AII_RESULTS`, `AII_LEDGER` (test overrides only), `HF_HOME`.
- Inputs from other artifacts, not published as part of this folder:
  - `src/prep_data.py` (constant `OVERLAP_JSON`) reads an RefusEU overlap-count file from an earlier stage of the run
    (`.../iter_3/gen_hypo/claude_agent/stage0b/refuseu_overlap.json`), and `src/write_protocol.py` (constant `STRAT`)
    reads `build_strategy.py` from `gen_strat_1`. Both are absolute paths to the original server; a reader must edit
    those constants to their own copy or skip S0. The committed `data/`, `data/splits/` and `protocol.json` make S0 unnecessary.
  - The comparison to the sibling artifact `gen_art_experiment_1` (dir2) named in `results/selection.json` is not needed to reproduce this artifact's numbers.

## 4. Commands actually run, in order
Seeds: `SEED = 20260923` (`src/common.py`), Optuna `TPESampler(seed=20260923)`, `torch.manual_seed(SEED)`; random-direction
generators use `SEED` / `SEED + j`. `RESERVED_SEED = 20260924` is never used.

S0 (CPU; data + frozen protocol, before any GPU scoring):
```bash
python3 src/prep_data.py
python3 src/prep_openrouter.py     # Slovene MT of harmless set, T/R/U pair grades (OpenRouter)
python3 src/write_protocol.py      # writes protocol.json, protocol.sha256 (4c5fbc69...369a)
```
GPU chain (`run_all.sh`, final flags from `results/protocol_amendments.json` amendments 2-3):
```bash
.venv/bin/python -u src/run_model.py --model gemma_it --n-trials 20 --rank-variant none --lambda-grid 0.5,1.2 --no-mech-c --skip-replay
.venv/bin/python -u src/run_model.py --model gams3_it --n-trials 20 --rank-variant none --lambda-grid 0.5,1.2 --no-mech-c --deadline-epoch 1790190480
```
`--deadline-epoch` was a hard stop for Phase H, so GaMS finished **17** trials (Gemma 20); the first 17 TPE draws are
identical across models (`results/pairing_check.json`: 17/17). Phases: O (original model scoring, prefill), H (Heretic
study + bilingual off-objective probe), P (post hoc). Config: `results/<model>/cfg/config.toml`; NF4 4-bit, empty system
prompt, batch_size 128.
Judge (Gemma only completed; GaMS blocked, see section 6):
```bash
(cd src && python3 judge.py --models gemma_it,gams3_it --all)                         # v2 prompt
(cd src && python3 judge.py --models gemma_it,gams3_it --all --prompt-version v1)     # v1 prompt
```
Post-GPU (`finalize.sh` wraps: key check, judge, `method.py`, `src/audit.py`, `src/write_results_md.py`, `method.py`):
```bash
.venv/bin/python method.py          # src/analyze.py -> src/make_figs.py -> method_out.json
(cd src && ../.venv/bin/python audit.py)
(cd src && ../.venv/bin/python write_results_md.py)
```
The outstanding item: `python3 src/judge.py --models gams3_it --all` (then `--prompt-version v1`), then rerun `method.py`.

Hardware: README states an RTX 2000 Ada, 16 GB VRAM pod (plan assumed A4500 20 GB); vram after load about 7.6-7.8 GB.
CPU/RAM not recorded. Runtime (`results/*/timing.json`): Gemma Phase H 2729 s, Phase P 1414 s, Phase O about 800 s;
GaMS Phase H 2989 s, Phase P 1415 s; about 148-164 s per trial; README says about 3.5 h on a 16 GB card. Failed attempts
(OOM, too-slow probe) are in `logs/gemma_it_attempt*.out` and `results/gemma_it/aborted_attempt*/`.
`results/smoke_gemma_it/` is a 2-trial smoke test, unused in statistics.

## 5. Outputs and expected numbers
Analysis is deterministic from the saved per-item files: `results/analysis.json` (all statistics), `results/selection.json`,
`results/audit.json` (20/20 re-derived), `RESULTS.md`, `method_out.json`, figures in `results/figs/`
(`c3_transfer_curves`, `c5a_kl_ratio_forest`, `pareto_fronts`, `prefill_depth`, `readout_comparison`; .pdf/.png).
Expected values (from `analysis.json` / README):
- Lexicon refusal, 400 RefusEU pairs, original to selected: Gemma EN 0.965 to 0.242, SL 0.932 to 0.223; GaMS EN 0.940 to 0.133, SL 0.830 to 0.098.
- EN to SL trial slope: Gemma 1.21 [0.75, 1.83]; GaMS 0.79 [0.51, 1.14]; shuffled placebo 0.01 +- 0.28.
- C3: G3 = -1.86 [-2.87, -1.13] (matched 17 trials); -1.76 all trials; -1.74 T/R subset; -0.99 lambda curve. m = 0.675 (`results/m.json`); z_c = -2.67 (MAIN), -5.72 (ALT-1); both fail. Category version 0.39 [-1.19, 2.12].
- ALT-4 (5-token prefill flip): Gemma 0.031 EN / 0.558 SL; GaMS 0.559 EN / 0.855 SL; Sig_EN 3.63, Sig_SL 1.54, m2 = 0.402, z_c = 6.23; not survived since |Sig_SL - Sig_EN| = 2.10 > m. Hypervolume ratio GaMS/Gemma 2.29 [2.01, 3.36].
- C5a excess SL/EN KL ratio vs norm-matched random: Gemma 0.298 [0.154, 0.562]; GaMS 0.574 [0.409, 0.796].
- C5b unpowered (resel == pick). No trial reached the <=10/100 keyword-refusal bar; fallback picks 64/100 (Gemma), 29/100 (GaMS).
Paper location of these numbers: no paper file is in this folder; not recorded which paper section holds them.
The README headline findings and `RESULTS.md` list the same numbers.

## 6. Known limits affecting reproduction
- Optuna/TPE with NF4 batching is not bit-identical across batch compositions: unedited KL reproduces only to 0.030 (Gemma) / 0.006 (GaMS). Rerunning the GPU stage may give slightly different values; the committed journals (`results/<model>/heretic_study.journal`) are resumable.
- OpenRouter: the shared key hit its daily limit ($0.94 spent, `results/judge_ledger.jsonl`), so `results/judge.jsonl` covers Gemma only; judge sensitivity readouts for GaMS are skipped. A rerun needs a key with budget.
- Raw rank-k ablation (`results/gemma_it/rank_k_*raw*`) destroyed Gemma and is a failed attempt; the projected variant and Mechanistic-Question-C code (`src/post_gemma.py`, `run_model.run_mech_c`) were not run.
- Baseline log-prob cache is not stored (about 400 MB per model); `--save-baseline-lp` writes it if wanted.
- `.venv/` and `__pycache__/` are removed from the published folder (`.aii/manifest.yaml`); recreate as in section 2.
