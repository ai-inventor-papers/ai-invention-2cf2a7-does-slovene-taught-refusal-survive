# Reproducibility: GaMS3-12B-Instruct vs Gemma-3-12B-IT, Slovene vs English refusal (confirmation run)

This file describes what the run actually did, reconstructed from the workspace (`method.py`, `finalize.sh`, `src/*.py`, `pyproject.toml`, `requirements.lock`, `protocol/`, `results/`, `outputs/`, `logs/`, `README.md`). Where the workspace records nothing, this file says so.

Seed: `20260924` (`src/common.py`, `SEED`). Decoding is greedy, so it is deterministic up to GPU/NF4 numerics. Bootstrap replicates: `B_BOOT = 2000`.

## 1. Getting the artifact

This folder is one folder of a public GitHub repository. Clone the repository and `cd` into this folder (the repository URL is not recorded in the workspace):

```bash
git clone <repository-url>
cd <repository>/<path-to>/gen_art_experiment_5
```

**Input from another artifact.** The item sets are built from the dataset artifact **`art_EG6OpEkGvysx`** (folder `gen_art_dataset_1`, iter 1). The repository publishes it as a sibling folder. Two files from it are read: `full_data_out.json` and `outputs/frozen_groups.json`. `outputs/split_manifest.json` from the same folder is read by `src/audit.py`.

**Known portability gap.** `src/common.py` (lines 36-40) hard-codes the paths `RUN_DIR = ../../..` and `DS_DIR = RUN_DIR/3_invention_loop/iter_1/gen_art/gen_art_dataset_1`. `src/audit.py` reads the same dataset folder. `src/common.py` also sets `ITER1_EXP` to the iter-1 experiment folder `gen_art_experiment_1`, a second sibling input. `src/analysis.py` reads `outputs/judge_gemini.jsonl` and `data/pairs.jsonl` from it (the iter-1 pooled comparison). It also reads `labeller_calibration.json` and `dose_table.json` from the dataset artifact's `outputs/`. The workspace has no environment variable for these. A reader must edit `RUN_DIR`/`DS_DIR` (and `ITER1_EXP`) in `src/common.py` so they point at the sibling dataset folder, for example `DS_DIR = ROOT.parent / "gen_art_dataset_1"`. Alternatively, create a symlink at the absolute path. `RUN_DIR` is not otherwise used to write anything: all outputs go under the workspace via `ROOT = Path(__file__).resolve().parent.parent`.

**Stages that need no rebuild.** The item manifests already exist in `data/*.jsonl`, with hashes in `data/manifest_hashes.json`. All generations, labels, scores and results are already committed under `outputs/` and `results/`. Reproducing the tables and figures needs neither the GPU nor an API key (see 4b), but `analysis.py` still reads the dataset artifact and the iter-1 experiment (see below).

No user-uploaded inputs are used.

## 2. System, Python and environment

- OS: Ubuntu (the run was on Linux 6.17). Exact Ubuntu release: not recorded.
- Python: `>=3.12,<3.13` (`pyproject.toml`). The exact patch version is not recorded.
- Tooling: `uv` (`uv sync`, `uv run`). `uv.lock` is in the folder. `package = false`.
- NVIDIA driver / CUDA: torch is `2.14.0+cu130` (`outputs/dev/gpu_status_gams3_it.json`), with CUDA-13 wheels pinned. The driver version is not recorded.
- System packages: none are recorded as needed beyond a working NVIDIA driver, `git` and `uv`. `src/common.py` notes that torch>=2.14 routes some ops to Triton kernels that need a C compiler. It de-registers those overrides (`disable_torch_native_triton`), so a C compiler should not be required.

```bash
uv sync        # creates .venv from pyproject.toml / uv.lock
```

`pyproject.toml` and `requirements.lock` carry identical pins. Key pins:

| Package | Version |
|---|---|
| torch | 2.14.0 |
| transformers | 4.57.6 |
| bitsandbytes | 0.50.2 |
| accelerate | 1.15.0 |
| huggingface-hub | 0.36.2 |
| numpy | 2.5.3 |
| pandas | 3.0.6 |
| scipy | 1.18.1 |
| statsmodels | 0.15.0 |
| scikit-learn | 1.9.1 |
| matplotlib | 3.11.2 |
| pyarrow | 25.0.1 |
| lingua-language-detector | 2.2.0 |
| langid | 1.1.6 |
| sacrebleu | 2.6.0 |
| aiohttp | 3.14.3 |
| httpx | 0.28.1 |
| loguru | 0.7.3 |

The full list is in `pyproject.toml`.

## 3. Models, downloads, credentials

Weights are not stored in the workspace. Download them at the pinned revisions:

```bash
huggingface-cli download google/gemma-3-12b-it --revision 96b6f1eccf38110c56df3a15bffe176da04bfd80      # gated; needs HF_TOKEN
huggingface-cli download cjvt/GaMS3-12B-Instruct --revision 1d0b27af5748784482600d24779409e7e1dc9adc
huggingface-cli download Qwen/Qwen3-14B --revision 40c069824f4251a91eefaf281ebe4c544efd3e18              # local judge (deviation D1)
huggingface-cli download facebook/nllb-200-distilled-1.3B                                                # V5 judge-language check
```

The NLLB revision is not pinned in the workspace. The exact download commands or URLs the run used are not recorded. These commands come from the README's restore table.

Environment variables (names only):
- `HF_TOKEN`: the gated Gemma repository.
- `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL`: the API judges (gemini-2.5-flash primary as pre-registered, gpt-4.1 second family). The exact OpenRouter model slugs are set in `src/openrouter.py` and `src/judge.py`.
- `AII_COST_CAP`: cost cap in USD (default 9.0).

Without OpenRouter, the API-judge stages cannot run. The shipped ledgers in `outputs/ledgers/` and labels in `outputs/*/labels_*.jsonl` let every later stage run without it.

## 4. Commands

### 4a. Full pipeline (what was run)

Run from the workspace root. Each stage is resumable and idempotent (generations and ledgers skip keys already present):

```bash
uv sync
uv run method.py                              # all stages, in order
uv run method.py --from judge_local_dev --skip-gen   # resume after generation
bash finalize.sh                              # the same chain as one shell script (SKIP_GEN=1 skips the GPU generation)
cd src && uv run python unit_tests.py         # T0 unit tests -> results/unit_tests.json
```

`method.py` runs, with `cwd=src/`, these stages in this order:

1. `build_items.py` builds the item manifests and asserts the fold counts (`data/`).
2. `freeze.py protocol` writes `protocol/protocol.json` and its sha256, then git-commits it. In the original run this was commit `a76ee29`, made before any FINAL generation.
3. `gen.py --model gemma_it`, then `gen.py --model gams3_it`. The default `--phases` is `smoke,ladder,batchcheck,dev,final`.
4. `judge_local.py --split dev` (local Qwen3-14B judge).
5. `judge.py --split dev`, then `scorers.py --split dev`.
6. `addendum.py` (DEV-only margins, ceiling rule and MDE). It hashes and commits `protocol/addendum_dev.json` (commit `36eb7c3` in the original run). It unlocks FINAL through `common.guard_final()`.
7. `judge.py --split final`, `judge_local.py --split final`, `scorers.py --split final`.
8. `analysis.py --split final`, then `analysis.py --split dev`.
9. `dev_judge_compare.py`, `judge_calibrated.py --target dev`, `judge_calibrated.py --target final`.
10. `judge_lang_check.py` (V5 check; a failure is tolerated).
11. `judge.py --split final --export_only` (writes `results/spend.json`).
12. `audit.py`, `make_outputs.py`, `figures.py`.

Extra checks run separately: `src/rederive_headlines.py` produces `results/rederive_headlines.json`, and `src/unit_tests.py` produces `results/unit_tests.json`. `method.py` does not call them, and `finalize.sh` does not call them either.

Warnings for a re-run:
- **Freeze commits.** `freeze.py` and `addendum.py` git-commit the protocol files. Re-running them on a fresh clone creates new commits with new hashes, so the original commit ids `a76ee29` and `36eb7c3` cannot be reproduced. The committed `protocol/*.json` and `*.sha256` files are the record. `audit.py` checks commit timestamps against the first FINAL generation and the first FINAL ledger line, and this will differ on a re-run.
- **Judge substitution (D5).** `protocol/primary_judge.json` says `"primary": "qwen3_local"`. The analysis therefore uses the local Qwen3-14B labels as the FINAL refusal primary, and the regex self-name detector as the FINAL identity primary. This is what the reported numbers use. Per the README, deleting `protocol/primary_judge.json` after the missing gemini and gpt-4.1 labels are completed restores the pre-registered gemini-primary analysis. That was not done in this run.
- **Pending API layer.** The API judges stopped when the shared OpenRouter budget was exhausted (`logs/relay_budget_exhausted_response.json`). FINAL gemini labels exist for 11,146 rows. Not yet run: about 8.5k gemini calls, about 3k gpt-4.1 calls and 1,280 identity calls (README estimate about $4.5). `cd src && uv run python judge.py --split final` resumes them when budget is available.
- **Regeneration.** A full regeneration overwrites nothing that is committed only if the ledgers and generation files are kept. To regenerate from scratch, first move `outputs/` aside. Note that D4 records that GaMS FINAL generation was interrupted at 9,088/10,150 rows and resumed with the same configuration.

### 4b. Rebuild only the analysis, no GPU and no API

`outputs/` and `results/` are shipped, so the numbers can be regenerated on CPU. The scripts below read committed generations and labels:

```bash
cd src
uv run python scorers.py --split final
uv run python analysis.py --split final       # -> results/analysis_final.json (+ items_final.*, boot_idx_final.npz)
uv run python judge_calibrated.py --target final
uv run python rederive_headlines.py           # -> results/rederive_headlines.json
uv run python audit.py                        # -> results/audit.json
uv run python make_outputs.py                 # -> method_out.json, full_method_out.json, results/RESULTS.md
uv run python figures.py                      # -> figures/fig1..fig6 (PDF + PNG)
```

`analysis.py` calls `guard_final()`, so `protocol/addendum_dev.json` and `protocol/addendum_dev.sha256` must both be present and match. They are committed. `analysis.py` and `audit.py` also need the sibling dataset artifact `art_EG6OpEkGvysx` and the iter-1 experiment folder `gen_art_experiment_1` (see the portability gap in section 1). This list was derived from the code and the stage order; the workspace does not record that this exact CPU-only subset was ever run on its own.

## 5. Configuration actually used

- Models: `google/gemma-3-12b-it` (control) and `cjvt/GaMS3-12B-Instruct` (method), at the revisions above.
- Quantisation and precision: NF4 4-bit, double quantisation, bf16 compute (bitsandbytes).
- Decoding: greedy, 160 new tokens (`MAX_NEW`), an empty system turn, the same Gemma-3 chat template for both models (verified byte-identical, EOS ids [1, 106]).
- Generation batch size: 64. The ladder chose bs 64 at 3.16 items/s (peak VRAM fraction 0.675). bs 96 ran out of memory (`outputs/dev/ladder_gemma_it.json`). `data/cuts.json` records that no cuts were needed.
- Scale: 10,150 FINAL generations per model (20,300 in total). DEV: 1,456 per model.
- FINAL item sets: RefusEU natural 1,300 pairs; item-matched SL_MT/EN_BT 1,296; HARD 1,442 items (349 unsafe / 1,093 safe); identity 80+80 pairs.
- Judge prompt: the frozen v1 prompt in `src/prompts.py`. The Qwen3-14B judge uses non-thinking mode, NF4, and takes the argmax of next-token logits over REFUSE/PARTIAL/COMPLY (default `--bs 16`).
- Pre-registered margins (from `protocol/addendum_dev.json`): m=0.508, m_id=0.402, m_d'=0.166, m_c=0.083. The Qwen3-derived margins are in `protocol/addendum_dev_qwen3.json`.
- Statistics: Hautus-corrected log-odds, DiD, SDT (d', c) and bootstrap (2,000 replicates), in `src/stats_lib.py`.

## 6. Hardware and runtime

- GPU: the README says one RTX 4090. The workspace does not record VRAM size or CPU/RAM. Measured model VRAM after loading: 7.57 GB for the NF4 model (`gpu_status_gams3_it.json`).
- Generation: about 2 GPU-hours projected for both models together (`data/cuts.json`: projected 2.04 h, budget 3.3 h). Model load took 207.9 s for GaMS3. The GaMS3 FINAL rate in the status file was 1.29 items/s over its first resumed batch (1,062 rows).
- Wall-clock for the judging and analysis stages is not recorded. The local Qwen3 judge ran on the same GPU.
- API spend: $2.10 (`results/spend.json`: $2.0966). It was spread across five ledgers, with 11,146 FINAL gemini calls. The run-level $7.00 budget shared with sibling artifacts is what ran out.

## 7. Expected outputs and where the numbers live

The numbers below are FINAL, with the Qwen3-14B judge as refusal primary, and are computed in `results/analysis_final.json`. They are summarised in `results/RESULTS.md` and `README.md`. Every number is a log-odds DiD (95% CI), with a positive value meaning a GaMS Slovene surplus.

| Quantity | Value |
|---|---|
| C1, DiD_id (regex identity readout) | 3.46 [2.55, 4.62]. GaMS own-name rate 90% SL vs 33% EN. GaMS credits Qwen/Alibaba in 51% of EN identity answers |
| C2 dose contrast D | -0.27 [-1.31, 0.71]. Inconclusive (MDE 1.36 > 2m) |
| DiD_ref (natural, 1,300 pairs) | -0.35 [-0.81, 0.13], about -2.8 pp. Gemini on 607 pairs -0.63 [-1.14, -0.16]. Qwen3 on the same pairs +0.03 |
| DiD_ref^MT (item-matched) | -1.67 [-2.75, -1.03]. Gemma 97.5% to 99.5% refusal in Slovene |
| HARD DiD_d' | -0.003 [-0.33, 0.29] |
| HARD DiD_c | +0.52 [0.38, 0.68]. Calibrated +0.66, DEV gemini +0.67. Fragile under PARTIAL-as-refusal (-0.31 [-0.62, -0.09]) |
| Independent re-derivation | The five headline numbers match to 1e-9 (`results/rederive_headlines.json`). Permutation p<.001 for DiD_c, DiD_ref^MT and DiD_id. Placebo p = .82, .88, .31 |
| Audit | 27/27 (`results/audit.json`) |
| Re-derivation caveat | The alternative "mentions own name anywhere" regex coding gives DiD_id = 3.89 (README) |

The published files are: `full_method_out.json`, `method_out.json`, `mini_method_out.json`, `preview_method_out.json`; `results/analysis_final.json`, `analysis_dev.json`, `audit.json`, `RESULTS.md`, `judge_calibrated_*.json`, `judge_lang_check.json`, `dev_judge_compare.json`, `spend.json`, `unit_tests.json`; `figures/fig1_forest`, `fig2_tradeoff`, `fig3_dose`, `fig4_identity`, `fig5_rates`, `fig6_judge_calibration_dev` (PDF and PNG).

Where they appear in the paper: the workspace holds no paper file and no mapping from figures or tables to paper sections, so this is not recorded. The figure and table names above are the closest supported reference.

## 8. Not recorded / limits

- Repository URL, Ubuntu release and exact Python patch version, NVIDIA driver, GPU VRAM size, CPU/RAM, and per-stage wall-clock times were not recorded.
- The exact OpenRouter model slugs are in code (`src/openrouter.py`, `src/judge.py`); they are not restated here.
- The exact search queries or download URLs used to build the dataset are not in this workspace. They belong to the dataset artifact `art_EG6OpEkGvysx`.
- Weights are NF4, decoding is greedy with a single sample, and the Slovene MT is not human-verified. No human or native-speaker review took place.
- Exact bitwise reproduction of generations on a different GPU or driver is not guaranteed. This was not tested.
