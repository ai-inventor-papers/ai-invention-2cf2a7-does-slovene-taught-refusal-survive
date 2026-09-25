# Reproducibility: GaMS3-12B-Instruct vs Gemma-3-12B-IT, Slovene refusal screen (experiment 1)

Everything below is taken from the files in this folder (README.md, code, `requirements.lock.txt`, `pyproject.toml`, `protocol.json`, `logs/`, `results/`). Items the workspace does not record are marked **not recorded**.

## 1. Get the artifact
Clone the public GitHub repository that publishes this workspace (URL not recorded in the workspace) and `cd` into the folder `gen_art_experiment_1`. Sibling folders are published alongside it (for example `gen_art_dataset_1`).

**Portability caveat (from the code as shipped).** Three code paths use absolute paths on the original server:
- `common.py`: `RUN_DIR = ../../..`, `STAGE0B` (a file `iter_3/gen_hypo/claude_agent/stage0b/stage0b_summary.json` with the key `per_category_dose`), and `DATASET_ART_GLOB` (a glob for `*overlap*.json` in the dataset artifact).
- `analysis.py`: `DATASET_DOSE` = `../../dataset-1/src/outputs/dose_table.json` (the sibling artifact `gen_art_dataset_1`). It is used only for the labelled sensitivity analysis and is skipped if absent.
- `freeze.py` and `analysis.py` (primary) read the Stage-0b dose file (`STAGE0B`). It is **not published here**, so a reader must edit `RUN_DIR`/`STAGE0B` in `common.py` to point at their own copy. The dose values in effect are frozen in `protocol.json`.

To re-run the analysis without that file, use the saved outputs and skip `freeze.py` (see step 6).

## 2. System, Python, environment
- Ubuntu Linux, one NVIDIA GPU (see hardware below), CUDA 13 wheels (`nvidia-*-cu13`, `torch==2.14.0`).
- Python `>=3.12,<3.13` (README uses `--python=3.12`; the exact patch version is not recorded).
- System packages: none are recorded. `uv` is used for the venv.

```bash
uv venv .venv --python=3.12
uv pip install --python .venv/bin/python -r requirements.lock.txt
```
`pyproject.toml` pins the same set (for example `torch==2.14.0`, `transformers==4.57.6`, `bitsandbytes==0.50.2`, `accelerate==1.15.0`, `datasets==5.0.1`, `numpy==2.5.3`, `pandas==3.0.6`, `scipy==1.18.1`, `statsmodels==0.15.0`, `scikit-learn==1.9.1`, `sacrebleu==2.6.0`, `langid==1.1.6`, `loguru==0.7.3`, `matplotlib==3.11.2`, `httpx==0.28.1`, `aiohttp==3.14.3`). LaBSE is loaded through `transformers` `AutoModel` in `build_mt.py`, so `sentence-transformers` is not needed.

## 3. Downloads, environment variables, keys
Models and data are downloaded from Hugging Face by the code with pinned revisions:
- `google/gemma-3-12b-it` @ `96b6f1eccf38110c56df3a15bffe176da04bfd80` (gated: needs a HF account that has accepted the licence).
- `cjvt/GaMS3-12B-Instruct` @ `1d0b27af5748784482600d24779409e7e1dc9adc`.
- Dataset `NASK-PIB/RefusEU` @ `5523ce30b9b6af59e95ade9c610b8b974412a6bb` (`lang_en`/`lang_sl`, train+test only; the `evaluation` split is never touched).
- MT and correspondence models (`build_mt.py`): `facebook/nllb-200-distilled-1.3B` @ `7be3e24664b38ce1cac29b8aeed6911aa0cf0576`, `Helsinki-NLP/opus-mt-tc-big-zls-en` @ `c52478f738ad47408224c8183984560ba0ebb3b0`, `sentence-transformers/LaBSE` @ `836121a0533e5664b21c7aacc5d22951f2b8b25b`.

Note that `gpu_pass.py` and `build_mt.py` set `HF_HUB_OFFLINE=1` by default (`os.environ.setdefault`). On a fresh machine, download the checkpoints first (for example `huggingface-cli download <repo> --revision <rev>`, with a HF token in your environment) or run with `HF_HUB_OFFLINE=0`. The original run used a shared, pre-populated HF cache. The HF token variable name is not recorded.

Environment variables:
- `OPENROUTER_API_KEY` (required by `openrouter.py` for the judges; the value is never stored).
- `AII_COST_CAP` (optional, default `4.0` USD, the artifact's own OpenRouter cost cap).
- `REUSE_ITEMS=1` (optional, dev only, in `analysis.py`; the final run rebuilt items).

## 4. Commands, in the order run (from README "How to run", `run_gpu_chain*.sh`, `method.py`)
```bash
.venv/bin/python build_data.py && .venv/bin/python build_mt.py && .venv/bin/python fix_identity.py
.venv/bin/python gpu_pass.py --model gemma_it --phase pilot && .venv/bin/python test_synthetic.py
.venv/bin/python freeze.py            # pre-registration; already committed (sha256 10f3cdcf...); re-running changes the hash
.venv/bin/python gpu_pass.py --model gemma_it --phase main --skip_construct_s
.venv/bin/python gpu_pass.py --model gams3_it --phase main --skip_construct_s
# GPU queues actually used (run_gpu_chain.sh, then run_gpu_chain2.sh)
.venv/bin/python gpu_pass.py --model gemma_it --phase prec8 --prec_n 20
.venv/bin/python gpu_pass.py --model gams3_it --phase prec8 --prec_n 20
.venv/bin/python gpu_pass.py --model gemma_it --phase main --construct_gen   # CONSTRUCT generation + s
.venv/bin/python gpu_pass.py --model gams3_it --phase main --construct_gen
.venv/bin/python judge_or.py --judge gemini; .venv/bin/python judge_or.py --judge gpt; .venv/bin/python judge_or.py --judge idname
.venv/bin/python analysis.py && .venv/bin/python method.py && .venv/bin/python audit.py \
  && .venv/bin/python rederive.py && .venv/bin/python rederive2.py
.venv/bin/python make_report.py
.venv/bin/python tests/test_units.py   # unit tests; how this was invoked (pytest or directly) is not recorded
```
`judge_or.py` also accepts `--frac`, `--conc` (default 16) and `--limit`. `gpu_pass.py` defaults: `--bs 32`, `--s_bs 16`, `--prec_n 20`.

**Configuration and seeds** (from `common.py`, `protocol.json`, `gpu_pass.py`, `stats_core.py`): NF4 4-bit (bitsandbytes, double quant, bf16 compute), empty system prompt, greedy decoding, 64 new tokens (96 for identity items), exact-token-length batches of 32. Screen seed 20260923 (`torch.manual_seed(20260923)`, bootstrap and power simulation RNGs, the 20% gpt-4.1-mini subset); 20260924 is reserved and never used. Split rule: `sha1(pair_id) % 4` gives 752 CONSTRUCT and 2,137 SCORE pairs; `pair_id = split:row_id:category`. Judges: `google/gemini-2.5-flash` (all responses, temperature 0, reasoning disabled, max_tokens 5) with a `gpt-4.1-mini` fallback for provider-blocked items; `openai/gpt-4.1-mini` on a 20% subset. Frozen protocol: `protocol.json`, sha256 `10f3cdcf2c8fec91af7f4509331ef31ab8e3bfec2a0c28d83ad766f19fe9bd4d` (`protocol.sha256`), plus `protocol_addendum_1.json`.

**Hardware and runtime.** One NVIDIA L4 (23 GB VRAM), 6 CPUs (README). Recorded timings in `outputs/gpu_status_gams3_it.json`: SCORE generation 1,910 s, SCORE s scoring 904 s, CONSTRUCT s 217 s; the MT arm for GaMS took about 466 s + 88 s (`logs/main_gams.out`). Total wall-clock is not recorded. The GPU stages are resumable (appended per item, keyed `pair_id|lang|condition`). OpenRouter spend was about $0.91 (`outputs/ledger_*.jsonl`).

## 5. Outputs and expected numbers
Nondeterminism warning: NF4/bf16 kernels are batch-size dependent (token-identical to batch 1 on only 18/32 outcome-certification items for GaMS; outcome agreement 32/32). Exact re-generation of the responses is therefore not guaranteed, and the judges are external APIs. To reproduce the reported numbers exactly, re-run only the analysis stage on the shipped `outputs/*.jsonl`: `analysis.py`, `method.py`, `audit.py`, `rederive.py`, `rederive2.py`, `make_report.py`. The Stage-0b dose file is needed by `analysis.py` (see section 1).

Files: `outputs/` (per-item generations `gen_*.jsonl`, prefix scores `s_*.jsonl`, judge outputs `judge_*.jsonl`, cost ledgers `ledger_*.jsonl`, `gpu_status_*.json`, `precision_*.json`), `results/analysis_results.json`, `results/RESULTS.md`, `results/items_scored.jsonl`, `results/audit.json` (30/30 checks pass), `results/rederive.json`, `results/rederive2.json`, `figures/fig1..fig5` (pdf+png), `method_out.json`.

Numbers to expect (`results/RESULTS.md`; SCORE analysis set n = 2,137 pairs; log-odds DiD = GaMS(SL-EN) - Gemma(SL-EN)):
- R_judge rates Gemma EN/SL, GaMS EN/SL = 0.979 / 0.929 / 0.971 / 0.865. R_lex = 0.961 / 0.885 / 0.942 / 0.723.
- Overall DiD: R_lex -0.67 [-0.95, -0.41]; R_judge -0.38 [-0.69, -0.05] (-5.6 pp [-7.0, -4.1]); R_judge_partial -0.03 [-0.39, 0.39]. m = 0.402 log-odds.
- Dose contrast D: R_lex 0.61 [-0.58, 2.15]; R_judge -0.08 [-1.27, 0.94]; R_judge_partial -0.73 [-2.11, 0.48]; MDE about 1.5-1.9 log-odds.
- Selection: the CEILING fallback fires (Gemma-EN R_lex 0.961, s AUROC 0.61); neither MAIN nor ALT-1 survives on R_judge incl. PARTIAL; C3 pending (Heretic artifact, not available).
- MT-parallel arm (SCORE-400): GaMS SL-MT 0.968 vs EN 0.970 (R_judge); judged DiD -2.0 pp [-4.3, 0.0] vs -6.0 pp on natural pairs of the same ids.
- Identity C1: DiD_id 3.22 [2.38, 4.38], m_id 0.43; GaMS own-name 0.90 SL vs 0.35 EN.
- 4-bit vs 8-bit first-token agreement 0.95 (Gemma) / 1.00 (GaMS); language consistency 100%.

Paper mapping: the workspace contains no paper file. `results/RESULTS.md` and `figures/` (fig1 forest per-category DiD, fig2 base rates, fig3 D across outcomes, fig4 identity names, fig5 meta-regression) are the sources for the paper's tables and figures; the mapping to specific paper sections is **not recorded**.

## 6. Known gaps
- All 1,504 GaMS CONSTRUCT responses are unjudged (the OpenRouter key hit its daily limit); they only feed the m_s calibration, which uses R_lex.
- `judge_local.py` is a fallback written while OpenRouter was blocked and was not used for the reported results.
- The item-level GEE returned NaN for R_lex (quasi-separation); this is reported as is.
- Search queries and download URLs beyond the pinned HF repos/revisions are not recorded; no human audit was done.
