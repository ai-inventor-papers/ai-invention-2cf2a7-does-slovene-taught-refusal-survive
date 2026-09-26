# Reproducibility: refusal depth by language, Gemma-3-12B-IT vs GaMS3-12B-Instruct

This file was written after the run, from the workspace files only. Where the workspace does not record something, it says so.

## 0. What to expect (read first)

- The run's main finding is negative. The pre-registered LLM judge (`google/gemini-2.5-flash`) failed validation, and so did the local fallback judge (Qwen3-8B). See `results/judge/validation.json` (`accepted = False`).
- The primary result is therefore the judge-free representation readout. The pre-registered H_depth verdict is "not evaluable with a validated judge". `RESULTS.md` lists it as FAIL only because the judged cells are empty.
- The causal steering claim is not established. The steering grids were generated but could not be judged.
- Precision is NF4 (bitsandbytes, double quant, bf16 compute) for both models.
- Greedy decoding on NF4 is not bit-identical across GPUs or batch compositions. Expect small differences from the saved generations (see section 4, hardware).

## 1. Get the artifact

Clone the public repository that contains this folder, then `cd` into the folder `gen_art_experiment_6`. Every command below runs from that folder with relative paths.

```bash
git clone <URL-of-the-public-repository>      # the URL is not recorded in the workspace
cd <repo>/<path-to>/gen_art_experiment_6
```

## 2. Environment

The workspace does not record a system-package list. It records:

- Ubuntu Linux, an NVIDIA GPU with 23–24 GB of VRAM, and the CUDA 12.4 wheels pinned in the lock file. The driver version is not recorded.
- `uv` for environment management. Python is 3.12 (`pyproject.toml`: `>=3.12,<3.13`).

```bash
uv venv .venv --python=3.12
uv pip install --python .venv/bin/python -r requirements.lock.txt
```

The main pins in `requirements.lock.txt` (which matches `pyproject.toml`, plus `formulaic`, `interface-meta`, `patsy`, `wrapt` and a pinned `statsmodels==0.15.0` and `tenacity==9.1.4`):

| package | version |
|---|---|
| torch | 2.6.0 |
| transformers | 4.56.2 |
| accelerate | 1.15.0 |
| bitsandbytes | 0.50.2 |
| tokenizers | 0.22.2 |
| huggingface-hub | 0.36.2 |
| numpy | 2.5.3 |
| scipy | 1.18.1 |
| scikit-learn | 1.9.1 |
| pandas | 3.0.6 |
| statsmodels | 0.15.0 |
| matplotlib | 3.10.6 |
| aiohttp | 3.14.3 |
| loguru | 0.7.3 |
| lingua-language-detector | 2.2.0 |
| sentencepiece | 0.2.2 |
| datasets | 5.0.1 |

The `nvidia-*-cu12` packages are pinned at 12.4.x, and `triton==3.2.0`.

## 3. Downloads, keys and inputs

**Model weights.** They are not stored in the repo. The README gives these commands:

```bash
huggingface-cli download google/gemma-3-12b-it --revision 96b6f1eccf38110c56df3a15bffe176da04bfd80
huggingface-cli download cjvt/GaMS3-12B-Instruct --revision 1d0b27af5748784482600d24779409e7e1dc9adc
```

Gemma-3 is a gated model on Hugging Face. If your account needs a token to download it, supply it with `huggingface-cli login` or the `HF_TOKEN` environment variable. The workspace does not say whether the run used a token. In the run, both models came from a shared HF cache. Judge-side weights: `Qwen/Qwen3-8B` (`src/local_judge.py`, `MODEL_ID`), bf16.

**Environment variables (names only).**

- `OPENROUTER_API_KEY` and `OPENROUTER_BASE_URL`. Both are required by `src/judge.py` and `src/judge_t0_variants.py`. The run's key worked only at the base URL it was given.
- `AII_RESULTS` (optional). It redirects the results directory (`src/common.py`, `src/audit.py`).

**Judge models via OpenRouter.** `google/gemini-2.5-flash` (primary) and `openai/gpt-4.1` (second family and 403-routed items). The DEV judge selection candidates are in `results/judge/select/` (deepseek-v3.2, mistral-medium-3.1, gpt-4.1, qwen3-235b-a22b-2507). The run's API budget was exhausted after 113 gpt-4.1 labels. Re-running the API judging will therefore differ from the saved ledgers unless you have your own budget. The saved ledgers under `results/judge/` let you re-analyse without any API calls.

**Inputs from other artifacts (a sibling of this folder in the repository, by id).** `src/common.py` hard-codes absolute paths from the original server:

- `ITER1 = ../../../round-1`
- `DATASET_DIR = ITER1/gen_art_dataset_1`. `src/prep_data.py` reads its `full_data_out.json`, the RefusEU items with NLLB Slovene translations and Marian back-translations. Its source sha256 is `35c98bc5d5336829af33a341d3d8b92a83d696e99a530ee5bc947d262c30803c` (`data/split_manifest.json`).
- `HARMLESS_SRC = ITER1/gen_art_experiment_2/data/alpaca_harmless.jsonl`. This is the harmless prompt source.

Those absolute paths are not portable. To re-run `src/prep_data.py`, edit the two constants in `src/common.py` to point at the sibling folders `gen_art_dataset_1` and `gen_art_experiment_2` of the published repository. You do not need to do this to re-analyse: the prepared files are already in `data/` (`depth600.jsonl`, `dev_items.jsonl`, `dev_nat_sl.jsonl`, `harmless.jsonl`, `split_manifest.json`), and the split-manifest sha256 values let you check them.

## 4. What was run, in order

**Seed.** `SEED = 20260924` (`src/common.py`). It is applied to `torch.manual_seed` and `np.random.seed` in `src/run_model.py`, to the item-ordering hashes (sha1 of id + seed), and to `np.random.default_rng` in `analysis.py`, `adjudicated.py` and `audit.py` (`audit.py` also uses seed+1 and seed+2). Bootstrap: 2,000 item resamples. Decoding is greedy, 160 new tokens (`MAX_NEW`); causal runs use 96 (`MAX_NEW_CAUSAL`).

**Hardware.** `results/hardware_manifest.json` records that the container was migrated mid-run:

- Gemma: all generation on an RTX 4090 (24 GB), except the supplementary `causal2` grid, which ran on an NVIDIA L4 (23 GB).
- GaMS3: smoke, dev, dirs and the first 3,532 final rows on the 4090. The remaining final rows, causal, collateral, causal2 and the hardware check ran on the L4.
- Both models were run with one model in GPU memory at a time.

Runtimes are only partly recorded. `results/gemma_it/timing.json` gives, in seconds, Gemma final generation 2,456.8 (tier A 1,172.5), causal 571.9 and collateral 160.4. `results/gams3_it/timing.json` has the GaMS numbers. The README estimates about 3 h of GPU plus judging. The total wall-clock time and the CPU/RAM are not recorded.

**Full pipeline (`method.py`).** The CLI accepts `pipeline` or `build-output` and takes no other arguments.

```bash
.venv/bin/python method.py pipeline
```

It runs, in order:

1. `src/prep_data.py`
2. For each of `gemma_it`, `gams3_it`: `src/run_model.py --model <m> --stages smoke,dev,dirs`, then `--stages freeze,final,causal,collateral`
3. `src/judge.py --t0`, then `src/judge.py --once`
4. `src/set_m.py`, `src/analysis.py`, `src/audit.py`, `src/make_figs.py`, `src/write_results_md.py`
5. `build_output()`, which writes `method_out.json`

Two caveats about how the run actually happened:

- The real run did not use `pipeline` end to end. It was staged with the shell chains in `src/` and `logs/`: `chain_gams.sh`, `chain_resume.sh` (resume after a session kill at about 22:38 UTC), `chain_causal2.sh` and `chain_hw.sh`. These add the stages `causal2` (the supplementary steering grid) and `hwcheck`.
- `method.py pipeline` does NOT include `causal2`, `hwcheck`, `src/local_judge.py`, `src/judge_select.py`, `src/judge_t0_variants.py`, `src/judge_validate.py` or the adjudication builders. Those were run separately. The workspace does not record their exact command lines beyond the argparse flags below.

**Steps the run actually included, with real arguments.**

```bash
.venv/bin/python src/prep_data.py
.venv/bin/python src/run_model.py --model gemma_it --stages smoke,dev,dirs
.venv/bin/python src/run_model.py --model gemma_it --stages freeze,final,causal,collateral
.venv/bin/python src/run_model.py --model gams3_it --stages smoke,dev,dirs
.venv/bin/python src/run_model.py --model gams3_it --stages freeze,final,causal,collateral
.venv/bin/python src/run_model.py --model gams3_it --stages final,causal,collateral,causal2   # resume after the kill
.venv/bin/python src/run_model.py --model gemma_it --stages causal2
.venv/bin/python src/run_model.py --model gams3_it --stages hwcheck
```

Optional `run_model.py` flags: `--limit`, `--max-bs` (default 64), `--budget-tokens` (default 64*360), `--final-budget-min` (default 75.0), `--n-causal` (default 100), `--tiers` (default `A,B,C,D`).

Judging, validation and analysis:

```bash
.venv/bin/python src/judge.py --t0            # synthetic 12-item test; gates FINAL judging (results/judge/GO_FINAL)
.venv/bin/python src/judge.py --once          # resumable OpenRouter judging into results/judge/*_ledger.jsonl
.venv/bin/python src/local_judge.py --score --plan primary   # local Qwen3-8B fallback after the API budget ran out
.venv/bin/python src/local_judge.py --validate ...           # also flags: --all --batch --nf4 --limit --model --ledger --hwcheck
.venv/bin/python src/set_m.py
./finalize.sh                                 # judge -> set_m -> analysis -> audit -> figures -> RESULTS.md -> method_out.json
```

The exact flag combinations used for the `local_judge.py` calls are not recorded. `logs/local_judge_*.out` show their output.

`finalize.sh` is the cheapest way to reproduce the numbers. With the saved ledgers it needs no GPU. It resumes the judge, so it will try OpenRouter for any unjudged rows and stop at the key or budget limit. `src/set_m.py` is a no-op if `results/m_frozen.json` exists.

**Pre-registration.** `protocol.json` has sha256 `435934d1f0c2e34d340fce5d47855b4c87da8138141249d117fa4d53e7a34770` (`protocol.sha256`). Its git commit is `28afce06d1a0f5f07bda3b3f6f5f89d6a0e64756` (`protocol.commit`), in the dedicated git dir `.protocol_git`. The GaMS addendum is in `protocol_addendum_gams.*`, and the amendments are `protocol_amendment_{1,2,3,5,6,7,8,9}.json` (there is no amendment 4 file). The README says "1..8", but amendment 9 exists as a file.

**Test.** `tests/fake_labels_e2e.py` exercises analysis, audit and figures on fake labels in a scratch results dir. Its outputs (`logs/e2e_test.out`, with DG = 1.524 for Gemma and 0.954 for GaMS3) are from fake labels and are NOT results.

## 5. Outputs and numbers to check

All numbers below come from the saved files.

- `results/analysis.json` holds every statistic. `RESULTS.md` is generated from it by `src/write_results_md.py`. `results/audit.json` is the independent re-derivation.
- Frozen m: `results/m_frozen.json`. p_dev = 0.0756 (28/376 DEV flips at P5), m = 0.5633 (log-odds), frozen at 2026-09-24T00:08:42Z.
- Judge validation (`results/judge/validation.json`, `RESULTS.md`):
  - Local Qwen3-8B judge: T0 10/12; κ(R) vs gpt-4.1 on DEV EN -0.076 (n=34) and SL 0.704 (n=79); κ vs blind adjudication 0.555 (n=58).
  - gemini-2.5-flash: κ vs adjudication 0.185 (n=50); it called 19 of 50 rows REFUSE where the adjudicator found actionable content, and every error ran in that direction.
  - Gates: T0 >= 11/12 false, κ vs gpt-4.1 EN >= 0.6 false, κ vs gpt-4.1 SL >= 0.6 true, κ vs adjudication >= 0.6 false. Accepted = False.
  - The adjudicator is a Claude model, not a human (`results/adjudication/`).
- Judge-free primary readout, from `RESULTS.md` (retention of the refusal direction at L*, SL-MT minus EN-BT, D300, n=300):
  - k0: Gemma 0.007 [-0.001, 0.014]; GaMS3 0.001 [-0.004, 0.006].
  - P5: Gemma -0.252; GaMS3 -0.408.
  - The README notes that at fixed token counts the two languages stop on different words, so only k0 and the full openers compare like with like.
- README headline (stratum-weighted blind adjudication, k=5 flip rate): Gemma 0.227 (SL-MT) vs 0.187 (EN-BT); GaMS3 0.399 vs 0.412. Both risk differences have intervals spanning zero. These figures are quoted from `README.md` only. In the saved `results/analysis.json` the `adjudicated_primary` key is `null` and `RESULTS.md` does not contain them, so they could not be re-derived from the saved files. `src/adjudicated.py` (called from `src/analysis.py`) is the code that computes them. Treat the numbers as unverified until `src/analysis.py` is re-run with the labels available.
- Pre-registered H_depth: FAIL / not evaluable. J = 0/600 for Gemma and 16/600 for GaMS3 under the local judge.
- The paper is not part of this folder. `RESULTS.md` and the figures serve as the write-up here, and no paper section numbering is recorded. Figures: `figures/fig1_depth_curves` to `fig10_judge_sensitivity` (png and pdf), made by `src/make_figs.py`. The README lists fig1..fig7 but `figures/` also holds fig8–fig10.

## 6. Not recorded / caveats

- The clone URL, the GPU driver version, the CUDA toolkit outside the pip wheels, the OS release beyond "Ubuntu", CPU and RAM, and the total wall-clock time.
- The exact command lines for `local_judge.py`, `judge_select.py`, `judge_validate.py`, `judge_t0_variants.py`, `make_adjudication2.py` and `make_adjudication3.py`. `TODO.md` is only the original task list.
- `method.py build-output` needs `results/analysis.json` and the label files, and it writes `method_out.json` (plus full/mini/preview variants, per the README). `method_out.json` is not in this workspace listing. Regenerate it with `.venv/bin/python method.py build-output`. Its `results_dir` metadata will contain your local absolute path.
- Some files are large: the `dev_raw_caps.npz` files are about 760 MB each, and the README says they can be regenerated with `--stages dev`. `results/gams3_it/final_gen.jsonl` and `results/gemma_it/final_gen.jsonl` are about 28 MB and 32 MB.
- The mid-run GPU migration (4090 to L4) creates a possible hardware x arm confound in GaMS tier A. `results/gams3_it/batch_check.jsonl` and the `hwcheck` stage, together with `results/judge/local8b_hwcheck.jsonl`, quantify it.
