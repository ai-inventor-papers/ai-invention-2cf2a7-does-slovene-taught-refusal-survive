> NOTE (published copy): this file names server paths this repository
> does not publish (a stage it does not ship, or another run's workspace),
> so the steps that read them will not run from a clone as written:
>   /ai-inventor/aii_data/runs/run_FVi3e3O9CH5I/iter_3/gen_hypo/claude_agent/stage0b

# Reproducibility: ALT-2 + C4 screen, GaMS3 vs Gemma-3 (experiment_2)

This file was written after the fact from the workspace files (README.md, code, configs, logs, results). Nothing was re-run. Where the workspace does not record something, it says so.

## 1. Get the artifact
This folder is one folder of a public GitHub repository. Clone the repository and `cd` into this folder (`gen_art_experiment_2`). All paths below are relative to it. Master seed everywhere: `20260923` (`src/common.py`, `data_build.py`, `analyze.py`, `base_stats.py`, `judge.py`, `base_punct_check.py`).

**Fastest check (no GPU, no API key):** all saved outputs are in the repo, so you can re-derive the numbers with the CPU-only steps in section 5. The largest raw inputs (`results/**/resid_L22_part_00{1,2}.npy`, per-item JSONL) are kept for that.

## 2. System, Python, venv
- Ubuntu Linux with an NVIDIA GPU driver and CUDA 12.8-compatible PyTorch wheels. Other system packages were not recorded. `uv` was used (`logs/uv_install.pid` exists) and Python 3.12 (`requires-python >=3.12`).
- Hardware actually used: one RTX 4090 (24 GB), per README (planned A4500 was not used). Each 12B model in NF4 used about 8.4 GB GPU memory (`logs/run_inst_gemma.out`).
- Environment (exact pins are in `pyproject.toml` / `requirements.lock`; key ones: torch 2.9.1+cu128, transformers 4.57.6, bitsandbytes 0.50.2, accelerate 1.15.0, huggingface-hub 0.36.2, numpy 2.5.3, scipy 1.18.1, statsmodels 0.15.0, scikit-learn 1.9.1, pandas 3.0.6, matplotlib 3.11.2, sacrebleu 2.6.0, aiohttp 3.14.3):
```bash
uv venv .venv --python=3.12
uv pip install --python .venv/bin/python -r requirements.lock \
  --extra-index-url https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match
```

## 3. Downloads, keys, env vars
- Models (Hugging Face, pinned revisions in `config/resolved_revisions.json`; `src/prefetch.py` downloads the four checkpoints):
  - `google/gemma-3-12b-pt` @ 295efb63d01a7017928f273a94ebb86105c9526f
  - `cjvt/GaMS3-12B` @ 46127695de173a5de72e1da9dc43846f58553477
  - `google/gemma-3-12b-it` @ 96b6f1eccf38110c56df3a15bffe176da04bfd80
  - `cjvt/GaMS3-12B-Instruct` @ 1d0b27af5748784482600d24779409e7e1dc9adc
  - `facebook/nllb-200-distilled-1.3B` (MT of alpaca prompts; no revision recorded).
  Gemma checkpoints are gated on Hugging Face, so accept the license and log in with your own token (a token name/env var is not set in the code; standard `huggingface-cli login`).
- Datasets (`src/data_build.py`): `NASK-PIB/RefusEU` @ 5523ce30b9b6af59e95ade9c610b8b974412a6bb (only `lang_en`/`lang_sl` train+test; the `evaluation/` split is never read), `tatsu-lab/alpaca`, `mlabonne/harmless_alpaca`. Exact download URLs are not recorded beyond these repo ids.
- Env var: `OPENROUTER_API_KEY` (name only) is required by `src/ledger.py`, used by `src/judge.py`, `src/mt_alpaca.py`, `src/mt_compare.py` (judge and comparison MT model `google/gemini-2.5-flash`). Total recorded spend $4.74 (cap $10 in `src/ledger.py`); ledger in `results/shared/openrouter_ledger.jsonl`.
- **Not portable / private input:** `src/data_build.py` reads the Stage-0b supervision-dose table from `STAGE0B = /ai-inventor/aii_data/runs/run_FVi3e3O9CH5I/iter_3/gen_hypo/claude_agent/stage0b`, an absolute path of another artifact of this run (not published here). Its output is kept as `data/dose_table_stage0b.json`. You do not need to re-run `data_build.py`; use the shipped `data/` files. `src/audit.py` also has an absolute path to the run's shared HF cache (used only for a note on whether the `evaluation` split exists in the cache); edit that line, or ignore that one field, when auditing elsewhere. These two absolute paths were not made relative in the code.

## 4. Protocol freeze (do not regenerate)
`config/protocol.json` (sha256 in `config/protocol.sha256`: ba4da6d9…2ffb) and `config/protocol_addendum.json` (`protocol_addendum.sha256`: b7d41c76…1971) were frozen and committed before the first model forward pass (protocol commit 14:51:47Z, first forward 14:54:15Z, per README). Re-running `src/make_protocol.py` / `src/make_addendum.py` would overwrite them, so do not.

## 5. Commands (what was run, in order)
`method.py` documents the chain (`python method.py --run-all` runs it; default `python method.py` only rebuilds `method_out.json`):
```bash
.venv/bin/python src/data_build.py            # RefusEU pairing/split, SCORE-400, alpaca sample (needs the private Stage-0b path; skip, data/ is shipped)
.venv/bin/python src/mt_nllb.py               # NLLB EN->SL of alpaca prompts (used)
.venv/bin/python src/make_protocol.py         # freeze (skip)
.venv/bin/python src/smoke_test.py            # -> results/smoke_test.json
.venv/bin/python src/base_geometry.py --model pt   # then --model gb   (residuals, all layers)
.venv/bin/python src/base_stats.py --model pt      # then --model gb   (directions, d', probes, harm-z)
.venv/bin/python src/instruct_run.py --model gemma # then --model gams (stages acdefg by default)
.venv/bin/python src/judge.py --full          # judge labels (needs OPENROUTER_API_KEY); earlier runs used default flags, see logs/judge_*.out
.venv/bin/python src/analyze.py               # -> results/analysis/analysis.json
.venv/bin/python src/audit.py                 # -> results/analysis/audit.json
.venv/bin/python src/figures.py               # -> figures/
.venv/bin/python method.py                    # -> method_out.json
```
Post-freeze exploratory steps: `bash src/post_gams_chain.sh` (mean-pooled base residuals with `--pool mean --tag _meanpool`, `base_stats.py --tag _meanpool --workers 14`, and `src/quant_check.py --model gams`); `src/quant_check.py --model gemma`; `src/base_punct_check.py` (-> `results/analysis/punct_check.json`); `src/mt_compare.py` (-> `results/analysis/mt_comparison.json`, `data/alpaca_harmless_gemini_mt.jsonl`, comparison only).
Regenerating the deleted 4.7 GB all-layer caches (`scratch/resid_*.npy`, not in the repo) is needed to re-run `base_stats.py`/`base_punct_check.py`: run the four `base_geometry.py` commands listed in README.md ("Restoring removed files"). Steps are resumable (skipped if output exists). The exact per-step command lines and flags used for every run were not all logged; the above follows README, `method.py` and the `logs/*.out` files. `src/base_geometry.py` args: `--model --limit --tag --bs (32) --pool {last,mean}`; `instruct_run.py`: `--model --stages --limit --tag --gen_bs 64 --ind_bs 96 --s_bs 32 --ind_budget_min 55 --s_mode cache`.

Setup: NF4 4-bit (double quant, bf16 compute), greedy decoding, one model on the GPU at a time; steering layer L_pt = 22 (`results/base_pt/layer_choice.json`).
Runtime: not summarised in the workspace. Log timestamps show the pt base-geometry pass starting 15:01 and finishing stats by 15:31 on 2026-09-23, and the Gemma-IT run starting 15:37; full wall time not recorded.

## 6. Expected outputs and numbers
(Also in README.md; `results/analysis/audit.json` re-derives them and all checks match.)
- ALT-2 (base geometry, `analysis.json`, `results/base_*/layer_stats.json`): d' at L22 EN/SL: pt 2.72/1.92, GaMS-base 1.05/0.94; Δd'_SL(GaMS−pt) = −0.98 [−1.13, −0.85]; at own layers (pt 22, GaMS 26) +2.85 [2.39, 3.38]; regression geometry share 0.042 [0.005, 0.122], dose increment 0.013. ALT-2 fails.
- C4 (`results/inst_*/induction.jsonl`, `judge_labels.jsonl`): pt direction never reaches R=0.5 (judge peak 0.03–0.25); own-direction Δ_C4 = −0.09 [−0.28, 0.07] (lexicon), +0.24 [0.13, 0.38] (judge); both inside ±ln1.5.
- SCORE-400 judge refusal: Gemma 0.957 EN / 0.945 SL; GaMS 0.967 EN / 0.917 SL; DiD −0.70 [−1.45, 0.02] logits.
- Validity: GaMS SL κ 0.38; lexicon SL rate for GaMS 0.78 vs judge 0.92; NF4 vs int8 first-token agreement 18/20 (`results/inst_*/quant_check.json`).
- Exploratory: `results/analysis/punct_check.json`. MT check: `results/analysis/mt_comparison.json` (16.5% of used items, chrF<40 vs Gemini).
- Figures `figures/fig1`–`fig5` (pdf+png); `method_out.json` (3 datasets). Location of each number in the paper: no paper file is in this workspace, so paper section/table mapping was not recorded.
- LLM-judge outputs depend on the remote gemini-2.5-flash API and may not be bit-identical on re-run; the saved labels in `results/shared/judge_labels.jsonl` are the reference. GPU results may vary slightly with hardware/driver.
