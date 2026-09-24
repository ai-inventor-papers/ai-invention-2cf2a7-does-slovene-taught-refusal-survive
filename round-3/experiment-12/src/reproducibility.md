# Reproducibility — RQ3 capability control (iter-3 exp12)

These are the steps that were **actually run** (2026-09-24, 05:56–11:20 UTC), including the mid-run restarts and cuts.
Every deviation is also logged in `results/cuts.json`.

## 1. Copy the artifact
```bash
cp -r <this folder> ~/rq3 && cd ~/rq3
```
Paths below are relative to the artifact root. Read-only inputs are referenced by absolute path on the run volume
(`/ai-inventor/aii_data/runs/run_FVi3e3O9CH5I/...`), set in `src/common.py`:
* iter-1 selected adapters, `selection_pick.json`, `random_edits.json`, `residual_directions.pt` and `cfg/config.toml`: `3_invention_loop/iter_1/gen_art/gen_art_experiment_4/results/{gams3_it,gemma_it}/`
* dataset dependency `art_EG6OpEkGvysx`, used only for the zero-overlap audit: `3_invention_loop/iter_1/gen_art/gen_art_dataset_1/full_data_out.json`
* RQ1 refusal rates: `3_invention_loop/iter_2/gen_art/gen_art_experiment_5/results/analysis_final.json`
* artifact 2's selected adapters (E_art2): `3_invention_loop/iter_3/gen_art/gen_art_experiment_9/selected/<model>/{adapter,selection.json}`

## 2. System, Python, libraries
* Ubuntu (Linux 6.8). There is **no C compiler** on the pod: the code sets `TORCHDYNAMO_DISABLE=1` and deregisters torch-native Triton ops (`torch._native.registry.deregister_op_overrides`).
* Python 3.12.14, managed with uv (no pip in the venv).
```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r env/requirements.lock.txt   # == pyproject.toml pins
```
Key pins: torch 2.14.0 (+cu130), transformers 5.17.0, peft 0.21.0, bitsandbytes 0.50.2, lm-eval 0.4.13,
heretic-llm @ p-e-w/heretic@3521f8648a0dccf6e12a92666862632235fac7e6, datasets 4.8.5, sacrebleu 2.6.0,
lingua-language-detector 2.2.0, scipy 1.18.1, numpy 2.5.3. The install takes about 10 min onto a network FS.

## 3. Data, models, env vars
* Env vars (by name only): `HF_TOKEN` (the gated `google/gemma-3-12b-it`), `HF_HOME` / `HF_HUB_CACHE` / `HF_DATASETS_CACHE` (shared cache). No OpenRouter calls were made ($0).
* Models: `cjvt/GaMS3-12B-Instruct@1d0b27af5748784482600d24779409e7e1dc9adc` and `google/gemma-3-12b-it@96b6f1eccf38110c56df3a15bffe176da04bfd80` (`src/download_models.py`, ~24 GB each), plus `facebook/nllb-200-distilled-1.3B` (MT only).
* Datasets (HF): cjvt/slovenian-llm-eval (rev `ca2f68d373`), allenai/ai2_arc, aps/super_glue boolq, Rowan/hellaswag, allenai/openbookqa, baber/piqa, allenai/winogrande (winogrande_xl), facebook/belebele (eng/slv/hun), databricks/databricks-dolly-15k, mlabonne/harmless_alpaca, tatsu-lab/alpaca.

## 4. Commands, in order (hardware: 1× NVIDIA L4, 23 GB VRAM; 48 CPU; NF4 via Heretic's loader)
Seed 20260925 is used everywhere; the random directions use iter-1's seed 20260923+j.
```bash
.venv/bin/python -m pytest -q -c pytest.ini tests/          # T0 unit tests (7 pass)
.venv/bin/python src/prep_data.py                            # ~3 min: item sets + overlap audit
.venv/bin/python src/prep_mt.py                              # ~2 min GPU: NLLB MT, chrF gate
.venv/bin/python src/write_protocol.py                       # freeze + git commit (protocol.sha256)
# GaMS block (06:45-08:32 UTC). It was restarted twice at condition boundaries (TaskManager-scan fix,
# ll_batch OOM fix, batch size kept at 8); every run resumes from the saved files:
.venv/bin/python src/gpu_block.py --model gams3_it --stages pilot,util,kl,gen,belebele,bpb,scorer2,chat \
   --n-gen 100 --n-gen-lambda 50 --util-bs 8 --lambda-conds orig,E_iter1,E_iter1_l2.0,E_iter1_l1.5,E_iter1_l0.5 --deadline-epoch <t>
# Gemma block (08:32-10:30 UTC):
.venv/bin/python src/gpu_block.py --model gemma_it --stages pilot,util,kl,gen,belebele,bpb,scorer2,chat \
   --n-gen 100 --n-gen-lambda 50 --util-bs 8 --util-conds orig,E_iter1,rand_nm_j1,rand_nm_j2 \
   --lambda-conds orig,E_iter1,E_iter1_l2.0,E_iter1_l1.5,E_iter1_l0.5 --deadline-epoch <t>
# resume passes (logs/chain_after_gemma.sh, logs/diag_sys.sh):
.venv/bin/python src/gpu_block.py --model gams3_it --stages util,kl_extra,hkl --util-conds E_art2 --kl-extra-conds E_art2
.venv/bin/python src/gpu_block.py --model gemma_it --stages hkl,bpb,scorer2
.venv/bin/python src/gpu_block.py --model gemma_it --stages hkl_sys
./finalize.sh                                                # analyze, audit, P0, outputs, figures, JSON variants (~4 min CPU)
.venv/bin/python src/rederive_headlines.py                   # independent third-path re-derivation + shuffled placebos
```
`method.py` chains the same steps (`.venv/bin/python method.py`). Timings are in `results/models/*/timing.json`:
a 300-item × 12 task-language utility condition takes about 9.2 min, KL (800 rows) 21–23 min, and one generation condition 4.4 min.

## 5. What you should get
* `results/RESULTS.md`: findings, then the gate table. No E_iter1 or E_art2 condition is catastrophic. Macro losses: GaMS E_iter1 0.018 (EN) / −0.007 (SL); Gemma E_iter1 −0.008 / −0.022; GaMS E_art2 0.020 / 0.009; Gemma E_art2 −0.016 / −0.049. Gemma λ=2.0 is POSSIBLY_CATASTROPHIC; its raw-pp sensitivity is OK.
* Interaction I (GaMS − Gemma) = +0.010 [−0.065, 0.074] for E_iter1 and −0.022 [−0.116, 0.043] for E_art2.
* KL multi-token EXCESS (E_iter1) = 0.566 (GaMS) and 0.294 (Gemma); the self-KL floor is exactly 0.
* `results/audit.json`: 346 checks, 0 failed; placebos centred. `results/rederive_headlines.json`: third-path agreement.
* `results/gates.json` (what artifacts 2–4 cite), `results/competence_covariates.json`, `results/p0_table.md`, `results/figs/fig1–4`.
* Small numerical differences are expected on other GPUs (bf16 lm-eval logliks, NF4 kernels). The utility bootstrap CIs use seeds 20260926+.
