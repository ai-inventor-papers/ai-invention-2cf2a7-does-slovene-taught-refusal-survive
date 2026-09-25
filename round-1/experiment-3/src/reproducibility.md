# Reproducibility: "Does a Slovene persona gate Slovene refusal?" (ALT-3 screen, SCREEN-SPEC v1)

Everything below is taken from the files in this folder. Where the workspace does not record something, it says so.

## 1. Get the artifact

This folder is one folder of a public GitHub repository. Clone the repository, then `cd` into this folder (`gen_art_experiment_3`). All paths below are relative to it. The code anchors on `Path(__file__)` (`src/common.py` sets `ROOT`, `method.py` sets `ROOT`).

Two things are not portable and are described honestly:
- `src/prep_data.py` line 16 reads a file from an earlier stage of the original run, by an absolute path (`.../iter_3/gen_hypo/claude_agent/stage0b/stage0b_summary.json`). That file is not published. You do not need it: the outputs of `prep_data.py` are shipped in `data/` (`run_pipeline.sh` skips the step when `data/harmless.jsonl` exists). Do not rerun `prep_data.py` unless you supply your own copy of that file and edit `STAGE0B`. It is only used to copy the `per_category_dose` table into `data/splits_manifest.json`.
- The last line of `finalize.sh` calls a JSON schema validator at `../../../tools/aii-json/...`. It exists only on the original server. Skip that line (it validates `method_out.json` and changes nothing).

## 2. System, Python, environment

- Ubuntu, one NVIDIA GPU with at least 20 GB of VRAM (per `README.md`). The original run used an **NVIDIA L4** (24 GB). CUDA userland from the pinned wheels is 12.4 (`nvidia-*-cu12` pins). The driver version, CPU, RAM and OS release were not recorded.
- Python 3.12 (`requires-python = ">=3.12,<3.13"`). No other system packages are named in the workspace.
- Environment, as in `README.md`:

```bash
uv venv .venv --python=3.12
uv pip install --python .venv/bin/python -r requirements.lock.txt
```

`requirements.lock.txt` and the `dependencies` in `pyproject.toml` hold the same pins. Key ones: torch==2.6.0, transformers==4.56.2, bitsandbytes==0.50.2, accelerate==1.15.0, huggingface-hub==0.36.2, numpy==2.5.3, scipy==1.18.1, scikit-learn==1.9.1, pandas==3.0.6, pyarrow==25.0.1, matplotlib==3.10.6, lingua-language-detector==2.2.0, aiohttp==3.14.3, sentencepiece==0.2.2, loguru==0.7.3.

## 3. Downloads, keys, environment variables

Names only, never values:
- `HF_TOKEN`: needed for the gated `google/gemma-3-12b-it`.
- `OPENROUTER_API_KEY`: read by `src/llm.py` for the judge (`google/gemini-2.5-flash`; fallbacks gpt-4.1-mini, then mistral-small). Not needed to re-run the analysis from the saved files. `README.md` says the key sat over its daily limit for part of the run.
- Models (4-bit NF4, double quant, bf16 compute; `src/engine.py`), pinned in `src/common.py`:
  - `cjvt/GaMS3-12B-Instruct` revision `1d0b27af5748784482600d24779409e7e1dc9adc`
  - `google/gemma-3-12b-it` revision `96b6f1eccf38110c56df3a15bffe176da04bfd80`
  - `facebook/nllb-200-distilled-1.3B` (used by `src/translate.py`; no revision recorded)
  - Local fallback judge Qwen2.5-7B-Instruct (`src/judge_local.py`; its κ vs gemini is 0.39 and no reported number uses it; no revision recorded).
  ```bash
  huggingface-cli download cjvt/GaMS3-12B-Instruct --revision 1d0b27af5748784482600d24779409e7e1dc9adc
  huggingface-cli download google/gemma-3-12b-it --revision 96b6f1eccf38110c56df3a15bffe176da04bfd80
  huggingface-cli download facebook/nllb-200-distilled-1.3B
  ```
- Data: NASK-PIB/RefusEU `lang_en` and `lang_sl`, splits train and test. A copy is kept in `data/refuseu/`. The reserved `evaluation/` split was never downloaded; never download it (`common.assert_not_eval` guards this). The download URL or date was not recorded beyond the dataset id. Harmless prompts come from `tatsu-lab/alpaca` (`prep_data.py`). The Heretic keyword markers are in `data/heretic_config.default.toml` (p-e-w/heretic @3521f86 per `src/common.py`).
- Model weights and the HF cache are not in the repository. The cache location variable was not recorded (the logs show a `TRANSFORMERS_CACHE` deprecation warning, so it was set in the original shell).

## 4. Commands, in the order they were run

`run_pipeline.sh` is the driver (resumable; every stage skips finished outputs). It runs from `src/`, sets `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` and `B="--budget 10000 --max-bs 40"`. As executed:

```bash
./run_pipeline.sh
```
which is, in order:
```bash
cd src
python prep_data.py                       # skipped if data/harmless.jsonl exists (see section 1)
python translate.py                       # NLLB EN->SL for SCORE-400 -> data/score400_mt_sl.jsonl
python selftest.py --model gams           # certification (hook no-op, projection ~0, batching)
timeout 1500 python gpu_run.py --model gams --stage construct --variant zero --budget 10000 --max-bs 40   # pre-registered zero-projection ablation; catastrophic, interrupted
python ablation_pilot.py --model gams     # results/ablation_pilot_gams.json (zero / zero-skip-BOS / mean / mean-skip-BOS)
python gpu_run.py --model gams --stage construct --variant mean_skipbos --budget 10000 --max-bs 40
python selftest.py --model gemma
python gpu_run.py --model gemma --stage construct --variant mean_skipbos --budget 10000 --max-bs 40
python freeze.py                          # writes protocol.json + protocol.sha256, BEFORE any SCORE item
python gpu_run.py --model gemma --stage score --slmt --budget 10000 --max-bs 40
python gpu_run.py --model gams  --stage score --slmt --budget 10000 --max-bs 40
cd .. && ./finalize.sh                    # judge.py -> judge_local.py -> analyze.py -> method.py -> audit.py -> placebo.py -> figures.py
```
(`run_pipeline.sh` ends with `exit 0` after `finalize.sh`; the two lines after it never run.) The original run actually launched the steps through `logs/chain2.sh`, `logs/chain3.sh` and `logs/continue_after_gams_construct.sh`, with the same commands. `logs/continue_after_gams_construct.sh` is an earlier version that calls the Gemma construct stage without `--variant`; `logs/gpu_gemma_construct.out` shows the recorded Gemma run used `ablation variant = mean_skipbos`.

Details that matter:
- Seeds: `SEED = 20260923` in `src/common.py` for all screen randomness (bootstrap 2,000 resamples, judge sampling); `20260924` is reserved for a confirmation run and was not used; `selftest.py` uses `torch.manual_seed(0)`. Generation is greedy, 64 new tokens.
- Protocol hash: `protocol.sha256` holds `eb718197a7316c90f811b945dd3341d743e1d4f060e5b728da5336d2421a882d` (SHA-256 of `protocol.json`). Check with `sha256sum protocol.json`.
- Judge (`src/judge.py`): gemini-2.5-flash via OpenRouter, temperature 0. Spend was $1.45 (`results/judge_ledger.jsonl`). The key hit its daily limit, so 61 GaMS items plus all of GaMS C5 use lexicon imputation. With a working key, `./finalize.sh` judges the ~1,254 imputed GaMS items (about $0.2; resumable). This will change the reported numbers slightly, so the numbers below are for the shipped, partly imputed state. Judge outputs are API calls and are not bit-reproducible; the shipped `results/judge_labels.jsonl` and `results/judge_ledger.jsonl` let you reproduce the analysis without the key.
- Not run: the 4-vs-8-bit check (`src/eightbit.py --model <gams|gemma>` exists but was not run), a full-SCORE tier-3 run. The band sweep used SCORE-200. SL-MT is s-only.
- Not bit-exact by design: NF4 batched greedy generation is not token-identical to batch 1 (`results/selftest_*.json`, `README.md` step 2); left-padded batches were used everywhere.
- Runtime: wall-clock time per stage was not recorded in a summary. `logs/*.out` hold the raw logs; no total is stated. Peak VRAM was not recorded.

To re-derive everything from the saved outputs without a GPU or API key (CPU only):
```bash
cd src && ../.venv/bin/python analyze.py && ../.venv/bin/python audit.py && ../.venv/bin/python placebo.py && ../.venv/bin/python figures.py
cd .. && .venv/bin/python method.py
.venv/bin/python src/test_static.py     # or: cd src && ../.venv/bin/python test_static.py
```
(`analyze.py` and its neighbours take no command-line arguments.) Note `analyze.py` reads the judge labels; do not run `judge.py` without a key, as it would try to call the API.

## 5. Outputs and the numbers to expect

The authoritative source is `results/analysis.json`, with `method_out.json` as the assembled form (schema exp_gen_sol_out; `full_method_out.json`, `mini_method_out.json`, `preview_method_out.json` are size variants). `results/audit.json`: 125/125 independent checks agree to 1e-9. `results/placebo.json`: false-survival 0/60.

| quantity | value | file |
|---|---|---|
| verdict | ALT-3 UNTESTABLE (manipulation check failed in GaMS for a_late, b_late, a_24_47) | `results/mc_gams.json`, `analysis.json › manipulation_checks` |
| m (logit SESOI), m_s | 0.442, 1.319 | `analysis.json` |
| TD*, judge readout | +0.23 [−0.81, +1.25]; MDE 1.46 | `analysis.json › verdict_primary` |
| TD*, s co-primary | +0.43 [−0.11, +0.97] vs m_s = 1.32 | `analysis.json › verdict_s` |
| lexicon-only TD* | −1.35 [−2.10, −0.62] | `analysis.json › robustness` |
| SL-MT s TD* | −0.24 [−0.78, +0.30] | `analysis.json › robustness` |
| DiD_ref(C0): judge / s / SL-MT s | −1.11 [−2.00, −0.36] / −2.72 [−3.30, −2.13] / −3.06 [−3.59, −2.52] | `analysis.json › primary, s_coprimary` |
| C0→C1 SL refusal in GaMS | 0.883 → 0.853, McNemar p = 0.081 | `analysis.json › flip_tables_C0_to_C1` |
| Own-name ablation makes GaMS say "Qwen" (exploratory, n=40/lang) | EN 0.15 → 0.775, SL 0.025 → 0.60; Gemma 0 | `results/mc_gams.json`, `results/mc_gemma.json`, `results/items/*__MC__*` |
| Lexicon κ vs gemini | 0.02–0.69 | `analysis.json › kappa` |
| Operator pilot | zero vs mean-skip-BOS | `results/ablation_pilot_gams.json` |

CIs are 95% pair-bootstrap over the 400 SCORE pairs (2,000 resamples, seed 20260923). The `README.md` "RESULTS" section lists every reported number and points to the source keys. Figures: `figures/refusal_rates.png`, `figures/forest_G_TD.png`, `figures/band_sweep_s.png`, `figures/identity_mc.png`. The paper itself is not in this folder; the workspace records no table or figure numbering for it, so the mapping of these outputs to paper sections was not recorded.

Per-item generations are in `results/items/{model}__C{0-5}.jsonl` (800 rows each), directions in `results/directions/*.npz`, projections in `results/projections_*.npz`, prompt hashes in `results/prompt_hashes.json`.

## 6. Known limits (from the workspace)

NF4 for both models; SCORE-400 rather than the full SCORE split; RefusEU SL prompts are generated variants, not translations; no human audit; eval-split near-duplicates not dropped; a single judge family. No causal claim about a persona gate is supported.
