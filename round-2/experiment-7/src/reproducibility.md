# Reproducing the ALT-5 teacher-inheritance screen (iter 2, experiment 7)

This file describes what was **actually run**, in the order it ran, between 20:35 UTC on 2026-09-23 and 04:40 UTC on
2026-09-24. Two points shape everything below:

* The delivered headline numbers come from a **substitute local judge**. The pre-registered paid judge
  (gemini-2.5-flash + gpt-4.1) could not finish because the run-level OpenRouter budget ran out.
* Anything that needs OpenRouter is marked **[paid]**. Re-running those steps needs budget. Every other step costs $0.

## 1. Copy the artifact

```bash
cp -r /ai-inventor/aii_data/runs/run_FVi3e3O9CH5I/3_invention_loop/iter_2/gen_art/gen_art_experiment_7 ~/alt5 && cd ~/alt5
```

The per-item generations (`gens/`) and labels (`labels/`) are included, so steps 5–6 (analysis) reproduce every reported
number on a CPU without regenerating anything.

It also depends on two read-only inputs from earlier artifacts of the same run, which `src/build_items.py` reads by
absolute path:

* the dataset `…/iter_1/gen_art/gen_art_dataset_1/full_data_out.json` (+ `outputs/split_manifest.json`);
* the iter-1 experiment_1 data `…/iter_1/gen_art/gen_art_experiment_1/data/{mt_parallel,identity_items}.jsonl`.

`data/items.jsonl` (sha256 in `data/items_manifest.json`) is the frozen result of that step. You do not need to rebuild it.

## 2. System, Python, environment

* **OS:** Ubuntu 22.04 (RunPod container), NVIDIA driver with CUDA 13 support.
* **Python:** 3.12.14.
* **Environment manager:** `uv` 0.x.
* **Packages:** every dependency is pinned exactly in `pyproject.toml`, which matches `.venv` `pip freeze` in
  `logs/pip_freeze.txt`. The lockfile is `uv.lock`.
* **Key versions:**
  * torch 2.14.0 (CUDA 13 wheels)
  * transformers 4.57.6
  * bitsandbytes 0.50.2
  * accelerate 1.15.0
  * scikit-learn 1.9.1
  * statsmodels 0.15.0
  * scipy 1.18.1
  * numpy 2.5.3
  * sacrebleu 2.6.0
  * datasets 5.0.1
  * lingua-language-detector 2.2.0

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh     # if uv is missing
uv sync                                             # creates .venv from uv.lock (~6 min, ~9.7 GB incl. CUDA libs)
```

**Pod trap.** torch ≥ 2.14 on a pod without a compiler: `src/common.py::disable_torch_native_triton()` deregisters the
torch-native Triton ops, and every `generate` call passes `disable_compile=True`. Never set `RLIMIT_AS`.

## 3. Downloads, environment variables, keys (names only)

| name | needed for |
|---|---|
| `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL` | [paid] teacher/outgroup generation and the gemini/gpt-4.1 judges. Requests must go to the base URL (a proxy) with a browser-like User-Agent (already set in `src/orclient.py`). |
| `HF_TOKEN` | the gated `google/gemma-3-12b-it` (licence must be accepted) |
| `HF_HOME`, `HF_HUB_CACHE` | shared model cache; left at the run defaults |
| `AII_COST_CAP` (optional, default 9.0) | global stop for paid calls, summed over all ledgers |

Models are pulled with `huggingface_hub.snapshot_download`, safetensors plus configs only:

* `cjvt/GaMS3-12B-Instruct` @ `1d0b27af5748784482600d24779409e7e1dc9adc`
* `google/gemma-3-12b-it` @ `96b6f1eccf38110c56df3a15bffe176da04bfd80`
* `Qwen/Qwen3-14B` @ `40c069824f4251a91eefaf281ebe4c544efd3e18`
* `facebook/nllb-200-distilled-1.3B` (back-translation)
* `mistralai/Mistral-Small-24B-Instruct-2501` @ `9527884be6e5616bdd54de542f9ae13384489724` (substitute judge)

API models (via OpenRouter):

* `qwen/qwen3-235b-a22b` (teacher; provider Alibaba pinned, reasoning disabled, T = 0)
* `meta-llama/llama-3.3-70b-instruct` (outgroup; Novita pinned, T = 0)
* `google/gemini-2.5-flash` (judge)
* `openai/gpt-4.1` (second-family judge; never ran)

**Seed:** 20260924 everywhere (item selection, bootstrap with 2,000 resamples, placebo).

## 4. Commands, in the order they ran

All commands run from `src/` with `PY=../.venv/bin/python`.

| # | command | hardware | wall time | notes |
|---|---|---|---|---|
| 0 | `$PY build_items.py` | CPU | ~15 s (REF_sft cached) | H = 616 HARD-DEV, R = 400, R200, ID = 117; `data/ref_sft.jsonl` (3,057 GaMS SFT refusals); asserts no reserved id |
| 0b | `$PY api_gen.py --probe` | – | seconds | [paid] key/provider/price probe → `results/key_probe.json` |
| 1 | `$PY gpu_gen.py --model nllb` | RTX 4090 24 GB | ~6 min incl. load (BT itself 17 s) | `data/h_en_bt.jsonl` |
| 2 | `$PY gpu_gen.py --model gams --phase pilot --bs 32` | RTX 4090 | 95 s + bs-1 check | pilot → `gens/pilot/`, `results/pilot_checks.json` (`$PY pilot_checks.py`) |
| 2b | `$PY freeze.py`, then `git commit` | CPU | – | `results/protocol.json`, sha256 `d7577710…` at 21:18:56 UTC, commit `6f07794` |
| 3 | `../run_gpu_chain.sh` (GaMS → Gemma → Q14, `gpu_gen.py --phase full --bs 64`) | RTX 4090 | 21 + 22 + 15 min generation (+ loads) | 3 × 4,082 rows (k0 × 3 arms, T4 prefill on R200, ID) + bs-1 checks |
| 4 | `$PY api_gen.py --system q235\|out --phase pilot` and `$PY judge.py --judge refusal --phase pilot` | – | ~10 min | [paid] pilot, validation only; `results/pilot_checks_api.json` (`$PY pilot_checks.py --api`) |
| 5 | `$PY api_gen.py --system q235 --conc 16`, `$PY api_gen.py --system out --conc 10`, `$PY judge.py --judge refusal --conc 24 --systems gams,gemma,q14` (via `../finalize.sh` phase A) | – | ~2 h incl. outages | [paid] stopped at 00:33 UTC by 403 `aii_run_budget_exhausted`; artifact spend $1.16 |
| 6 | `../run_local_judge.sh` (`local_judge.py --task refusal --phase full`, `--task idname --phase full/pilot`) | RTX 4090 | 25 + 2 min | substitute readout `labels/refusal_local.jsonl`, `labels/idname_local.jsonl` |
| 7 | `for m in gams gemma q14; do $PY xent.py --model $m; done` | RTX 4090 / RTX 4000 Ada 20 GB | ~10 min + loads | exploratory likelihood; filled in on the RTX 4000 Ada in the resumed session |
| 8 | `$PY -c "import api_gen; [api_gen.export(s,'full') for s in ('q235','out')]"` + a re-run of step 6 | CPU/GPU | minutes | exported 53 late API rows and judged them locally |
| 9 | `$PY local_judge.py --task refusal --variant prefill_v2 --bs 16` | RTX 4000 Ada 20 GB | 8 min load + 11 min | post-hoc prefill variant, **rejected** (`$PY prefill_v2_validation.py`) |
| 10 | `$PY analyze.py --readout local` / `--readout gemini` / `--readout regex` | CPU | ~10 / 1 / 9 min | `results/analysis.json` (headline), `analysis_gemini_partial.json`, `analysis_regex.json` |
| 11 | `$PY prefill_v2_validation.py && $PY audit.py && $PY make_figs.py && $PY make_method_out.py && $PY make_report.py` | CPU | ~2 min | `results/prefill_v2_validation.json`, `audit.json` (52/52), `figures/`, `method_out.json`, `results/RESULTS.md` |
| 12 | `$PY rederive_headline.py` | CPU | ~3 min | independent re-derivation + placebos → `results/rederive_headline.json` |
| 13 | aii-json `aii_json_format_mini_preview.py --input method_out.json`; validate with `--format exp_gen_sol_out` | CPU | seconds | full/mini/preview, all PASS; 13 MB (< 100 MB, no split) |

Equivalent drivers:

* `python method.py --stage items|bt|gpu|api|judge|local|xent|analyze|report`
* `./finalize.sh`: [paid], resumable. Run it once the budget is raised to add the pre-registered gemini/gpt-4.1 readout.

`tests/test_pipeline.py` holds the unit tests: kappa vs sklearn, bootstrap reproducibility, and JSD. It also runs a
synthetic end-to-end check in which planted inheritance is detected. Run it with `AII_TEST_ROOT=<scratch dir inside
the workspace>`.

**NF4 non-determinism.** Batched NF4 output is not token-identical to batch-1 output. Outcome agreement:

* GaMS 32/32
* Q14 15/16
* Gemma 13/16

Regenerating therefore reproduces the outcome labels closely, not byte-for-byte. The saved `gens/` are the reference.
The teacher at T = 0 is also non-deterministic: only 17% of retest texts are identical, and the retest kappa is 0.88.

## 5. What you should get, and where it appears

The numbers below come from `results/analysis.json` (substitute readout). Each was independently re-derived by
`src/rederive_headline.py`, which uses a different code path, and the re-derivations agree.

| quantity | value | also in |
|---|---|---|
| FP-cal: κ(Q14,Q235) − κ(Q14,Gemma), H EN, n = 608 | −0.001 [−0.074, 0.079] → gate fails, T1 UNINTERPRETABLE | README §Results 1, fig2 |
| T1 dk: κ(GaMS,Q235) − κ(GaMS,Gemma) | −0.044 [−0.118, 0.032]; 90% CI [−0.107, 0.021] | README, fig2 |
| T1b vs Llama (n = 487) | 0.062 [−0.024, 0.151] | README |
| side-taking, GaMS − Llama placebo (117 discordant items) | −0.009 [−0.133, 0.123] | README |
| SL dk / SL FP-cal / DiffGap | 0.082 / 0.192 / −0.133 [−0.247, −0.011] | README §Results 2 |
| safe-item refusal SL − EN | Gemma +0.24, GaMS −0.06, Q235 −0.18 | README, RESULTS.md rates |
| teacher test-retest κ (n = 99) | 0.88 | README §Validity |
| GaMS EN refusal first sentence verbatim in SFT refusals | 76.1% (n = 1,267) | README §Results 3 |
| same, GaMS SL | 90.8% (n = 601) | README §Results 3 |
| source classifier: GaMS EN refusals classed teacher-like | 95.8% (CV 0.97); independent SVM re-derivation 98.4% (CV 0.977) | README §Results 3, fig3 |
| identity: GaMS EN answers self-naming Qwen | 21% (24/117) | README §Results 5, fig5 |
| T4 depth | UNINTERPRETABLE under the local readout: prefill κ vs gemini 0.15, and the prefill_v2 rescue was rejected | README §Results 4, fig4 (gemini subset) |

Placebos in `results/rederive_headline.json`:

* **Teacher labels shuffled:** κ(GaMS, Q235) falls to −0.02 in EN and 0.02 in SL.
* **Both comparators shuffled:** dk centres at −0.002, with a null 95% range of ±0.11.
* **Classifier with shuffled training labels:** CV accuracy falls to 0.48 (below the 0.56 majority rate), and the GaMS
  teacher share falls to 18%.
* **Coin-flip "GaMS" in side-taking:** 0.03.

The independent first-sentence check uses the `en_orig` arm only. It gives 77.1% (n = 647), close to the analysis value
of 76.1%, which also pools the `en_bt` arm.

**Not reproducible without budget.** The pre-registered primary readout is missing for the teacher and outgroup rows:
gemini labelled only the local systems, and gpt-4.1 never ran. Any paper claim about teacher decisions must therefore be
labelled as resting on the validated substitute judge.
