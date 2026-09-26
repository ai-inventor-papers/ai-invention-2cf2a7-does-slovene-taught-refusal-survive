# Reproducibility: reserved Slovene/English refusal test sets and audit (`gen_art_dataset_1`)

This file was written after the fact from the workspace contents (README.md, `data.py`, `scripts/`, `lib/`, `pyproject.toml`, `requirements.lock.txt`, `outputs/*.json`, `logs/`, `ledger/`). Nothing was re-run to write it. Where the workspace does not record something, the text says so.

## 1. Get the artifact

The workspace is one folder of a public GitHub repository. Clone the repository (URL not recorded in the workspace) and `cd` into the folder `gen_art_dataset_1`. All paths below are relative to that folder.

Everything needed to *rebuild the final files without any API call or GPU* is already in the folder: every raw LLM response is cached in `labels/*.jsonl`, intermediate tables are in `work/`, and `data.py` reads only these plus two external inputs (see section 3, "Sibling inputs").

## 2. System, Python, environment

- OS: Ubuntu (the run was on Linux 6.17). Exact distro and system packages were not recorded. A C compiler was *not* available, which is why local vLLM could not run (README, "Execution history"); no deliverable depends on it.
- Python: 3.12 (`requires-python = ">=3.12,<3.13"` in `pyproject.toml`).
- Tool: `uv`. Create the venv and install the exact pins (165 packages, `uv pip freeze` of the run's venv, dated 2026-09-23):

```bash
uv venv .venv --python=3.12
uv pip install --python .venv/bin/python -r requirements.lock.txt
```

`pyproject.toml` lists the same pins. Key versions: torch 2.7.1 (CUDA 12.6 wheels), transformers 4.56.2, sentence-transformers 6.1.0, sacrebleu 2.6.0, pandas 3.0.6, numpy 2.2.6, scikit-learn 1.9.1, scipy 1.18.1, pyarrow 25.0.1, huggingface-hub 0.36.2, aiohttp 3.14.3, loguru 0.7.3. The freeze still contains vLLM's dependency set (xformers, xgrammar, ray, etc.) although vLLM itself was uninstalled because no deliverable step used it.

`data.py` also declares its own inline `uv` script header (pandas>=2.2, pyarrow, numpy, scipy, scikit-learn, loguru), so `uv run data.py` works without the venv.

## 3. Downloads, keys, sibling inputs

**Environment variables (names only):**
- `OPENROUTER_API_KEY`: required by `scripts/s0_env_ledger.py` and by every LLM step (`lib/judge.py`, `s7_api_label.py`, `s4b_hard_api_mt.py`, `s7b_dose_hazard_harmonise.py`, `s8a_identity_gen.py`). Not needed to replay cached labels.
- A Hugging Face token is very likely needed for `meta-llama/Llama-Guard-3-8B` (gated repo); the workspace does not record the variable name used. `HF_HUB_CACHE` was pointed at a shared run cache (`scripts/s0_fetch_models.py` docstring); set it wherever you like.

**Datasets** (`scripts/s1_download.py` downloads into `temp/datasets/` at pinned revisions; sha256 values in `outputs/provenance.json`):
- NASK-PIB/RefusEU @ `5523ce30b9b6af59e95ade9c610b8b974412a6bb`
- cjvt/GaMS-Nemotron-Chat @ `0eab0b3cfcaaedf3958fe08ab1a7cd09302d65d7`
- Paul/XSTest @ `f600c994b256f12867dfa5b3eb3d545a3e62f8b5`
- bench-llm/or-bench @ `e36d8b80e81837c8a8f264bbb2a49f1b32c7e272`
- OpenAssistant/oasst2 @ `179dd21fc55192153d94adb0e0ce8f69e222bf75`
- natolambert/xstest-v2-copy and reference-only sets (MultiJail, do-not-answer, JBB-Behaviors, Aegis-2.0, aya_redteaming): downloaded but not in the deliverable.
- GaMS-Instruct-SAFE 0.5 (CLARIN.SI hdl 11356/2218): NOT downloaded from a URL by the script; `s1_download.py:76` copies `iter_2/gen_hypo/claude_agent/stage0/safe05/GaMS-Instruct-SAFE_0.5/GaMS-Instruct-SAFE_0.5.json` from another stage of the same run. A reader must obtain it from CLARIN.SI and place it at that location under `temp/datasets/` (adjust the path in `s1_download.py`).

**Models** (`scripts/s0_fetch_models.py`, no arguments = all): sentence-transformers/LaBSE, facebook/nllb-200-distilled-1.3B, Helsinki-NLP/opus-mt-tc-big-zls-en, meta-llama/Llama-Guard-3-8B. Model revisions were not recorded. Unused pre-fetched weights (Qwen2.5-14B-AWQ, Llama-3.1-8B, salamandra-7b) are not needed.

**API models via OpenRouter:** openai/gpt-4.1-mini, google/gemini-2.5-flash (reasoning off), meta-llama/llama-3.3-70b-instruct (tiebreak). Temperature 0 for labelling; gpt-4.1-mini identity paraphrases used T 0.7 with seed 20260923. Provider-side non-determinism means a live re-run may differ from the cached labels; the cache replay is exact.

**Sibling inputs (not published as separate artifacts under a known id).** `lib/common.py` defines `RUN = ROOT.parents[3]` (the run folder, `run_FVi3e3O9CH5I`) and reads from it:
- `iter_2/gen_hypo/claude_agent/stage0/` : `regex_flagged.jsonl`, `judge_labels.jsonl` (used by `s2_prepare.py:137-138` and `data.py:361`), and `safe05/...` (SAFE 0.5 copy).
- `iter_3/gen_hypo/claude_agent/stage0b/stage0b_summary.json` (used by `data.py:430`, `per_category_dose`).
- The TF-IDF featuriser is described as the "Stage-0b featurizer" retrained on RefusEU `lang_*/train` (`scripts/s3_tfidf.py`).

These are outputs of earlier stages of the same pipeline run, not of another published artifact that this repository carries as a sibling under a known id (the sibling folders present are `gen_art_experiment_1..4` and this dataset folder). They are not in this folder, so `s2_prepare.py` and `data.py` cannot be re-run from scratch without supplying equivalent files at those relative paths (the Stage-0 regex-flagged ids and Stage-0 judge labels for the Nemotron dose rows, and the Stage-0b per-category dose summary). Their content was not recorded elsewhere, except that the per-row results they fed are baked into `work/dose_rows.parquet` and `labels/`.

## 4. Commands, in the order the README documents them

Seeds: `SEED = 20260923` in `scripts/s2_prepare.py` (pandas `random_state` for the SRS dose samples and the keyword-stratum oversample); batching shuffles in `s7_api_label.py` use `make_batches(..., 20260923)` and `20260924` for dose (check and rest), `20260925 + (lang == "sl")` for HARD; identity generation used seed 20260923. Folds are hash-only (`sha1(pair_id)` / `sha1(item_id)`), frozen in `outputs/split_manifest.json` before any labelling. Local models are decoded greedily (Llama-Guard) so they take no seed.

```bash
uv venv .venv --python=3.12 && uv pip install --python .venv/bin/python -r requirements.lock.txt
.venv/bin/python scripts/s0_env_ledger.py            # env record + ledger init (needs OPENROUTER_API_KEY)
.venv/bin/python scripts/s0_fetch_models.py          # optional pre-fetch of local model weights
.venv/bin/python scripts/s1_download.py && .venv/bin/python scripts/s2_prepare.py && .venv/bin/python scripts/s3_tfidf.py
.venv/bin/python scripts/s4_mt.py && .venv/bin/python scripts/s5_correspondence.py   # s4_mt.py takes an optional item-count argument
.venv/bin/python scripts/s7_api_label.py calib       # then: eval, dose, tiebreak, hard (cached -> $0 on re-run)
.venv/bin/python scripts/s4b_hard_api_mt.py && .venv/bin/python scripts/s6_llamaguard.py && .venv/bin/python scripts/s3_tfidf.py
.venv/bin/python scripts/s8a_identity_gen.py && .venv/bin/python scripts/s8b_identity_finalize.py
.venv/bin/python scripts/s7b_dose_hazard_harmonise.py && .venv/bin/python scripts/s11_contamination.py
.venv/bin/python scripts/s12_ledger_summary.py
uv run data.py        # or .venv/bin/python data.py
```

Notes from the code and logs:
- `s7_api_label.py` takes the task as `sys.argv[1]` (`calib`, `eval`, `dose`, `tiebreak`, `hard`); `s7_smoke.py` is a 5-call price smoke test. The logs show the order actually used included `s3b`, `s4`, `s4b`, `s5`, `s6`, `s6b`, `s7*`, `s7b`, `s8a`, `s8b`, `s11`.
- `s6_llamaguard.py` accepts an optional item-count argument.
- `s2_prepare.py` rewrites `outputs/split_manifest.json` (same hash-only folds); rerun `data.py` afterwards to re-attach the label freeze.
- The plan's optional GaMS-Instruct regex scan was not run (repo gated); PolyGuard/COMET-QE was not run.
- `data.py` was run three times (`logs/data_run.out`, `data_uvrun.out`, `data_run_final.out`); each ends with the row counts below.

**Hardware:** 1x NVIDIA GeForce RTX 4090, 24,564 MiB, driver 580.126.20 (`logs/env.json`). The GPU is used only for NLLB/opus-mt MT, LaBSE and Llama-Guard-3-8B (bf16). Total wall-clock runtime and CPU/RAM were not recorded; the log timestamps show the whole run inside 2026-09-23 (env record 14:41 UTC, first `data.py` finish 15:44 UTC, final freeze 15:55 UTC). The gemini eval labelling alone took roughly 15 minutes of logged time. Spend: $9.2858 of the $9.50 cap, 14,450 calls (`ledger/summary.json`).

## 5. Outputs and numbers a reader should get

Final files (recomputable at $0 from cache with `data.py`): `full_data_out.json` (35,064,061 bytes; exp_sel_data_out; 8 blocks; 15,647 rows), `mini_data_out.json`, `preview_data_out.json`.

Rows per block (`logs/data_run_final.out`): refuseu_eval 2,800; refuseu_gold_calib 590; gams_dose_rows 6,239; hard_xstest 900; hard_orbench_hard1k 2,638; hard_orbench_toxic300 600; identity_confirm 480; refuseu_x_mt 1,400.

Headline numbers and where they live:
- Eval-label quality on gold test (`outputs/labeller_calibration.json`, `outputs/refuseu_eval_label_report.json`): majority-of-3 accuracy .759 EN / .716 SL; pure-only .947 / .941; Cohen kappa gpt-gemini .879 EN / .830 SL; item_pure share .647 EN / .534 SL. Eval category counts deviate from 100 per category (chi-square p ~ 1e-40; e.g. EN S9 = 30, S12 = 32, S6 = 50, S3 = 68).
- Correspondence (`outputs/refuseu_correspondence.json`): same-row_id EN/SL LaBSE cosine .553 vs .914 for MT pairs; 0/1,400 grade T.
- Dose (`outputs/dose_table.json`, `outputs/frozen_groups.json`): overall EN share of safety-refusal supervision .1781 with interval [.0549, .4516]; the "Slovene-dominant" wording is not licensed (`slovene_dominant_wording_allowed(upper<0.40)` = False). Frozen groups: low-EN S2/S5/S7/S13; high-EN S1/S3/S4/S8/S9/S10/S11/S14; intermediate S6/S12; 13 of 14 categories in `dose_uncertain` (S9 is the exception). `frozen_groups.json` sha256 `3a7214019b8e22d8bc6c8e967d689b000899a7d2b8b3ae5dbdcfae565a4a55d2`.
- Dose labelling: batching check agreement .945 (gpt) / .959 (gem) (`labels/dose_batching_check.json`); llama-3.3-70b tiebreak on 928 rows.
- HARD MT and votes: `outputs/hard_mt_report.json` (median back-translation chrF 79.2, 11 items dropped).
- Identity items: `outputs/identity_report.json`, `outputs/identity_items_ids.json` (120 identity + 120 control, 40 DEV / 80 FINAL).
- Contamination: `outputs/contamination_report.json`, `outputs/refuseu_overlap_recheck.json`.
- Cost: `ledger/summary.json`.

**Paper location:** this artifact is a dataset input to the parent study's paper. The workspace does not record which paper section or table uses each number, so no mapping is given.

## 6. Not recorded / limits

- Repository URL, exact system packages, RAM/CPU, per-step and total wall-clock runtime, HF token variable name, model revisions of local models, the exact upstream Stage-0/Stage-0b files (see section 3).
- No native-speaker audit; all Slovene items other than RefusEU's own are machine-translated and not human-verified.
- Live re-runs of API steps may not reproduce the cached labels exactly; replay from `labels/` instead.
