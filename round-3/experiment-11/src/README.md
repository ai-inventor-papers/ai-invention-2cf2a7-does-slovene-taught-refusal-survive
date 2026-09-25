# Does an English-only abliteration reach Slovene less in GaMS3 than in Gemma-3? (C-LAG confirmation, iter 3)

This repository is the iter-3 **confirmation** run for one claim of the GaMS3-vs-Gemma-3 abliteration study: when an
English-objective Heretic edit is applied at matched *English* strength, does the **Slovene** refusal rate fall
differently in the Slovene-adapted `cjvt/GaMS3-12B-Instruct` than in the generalist `google/gemma-3-12b-it`?

The iter-2 screen (`gen_art_experiment_8`, curve **B**, 29 Heretic trials per model, RefusEU-**TRAIN** items, an
unvalidated keyword lexicon as readout) reported **G3 = −2.36 [−3.18, −1.62]**: a large GaMS Slovene *over-exposure*.
The same artifact's curve **A1** — the *same* λ-scaled adapter this run uses, judged by gemini — reported
**G3 = −0.19 [−1.03, 0.78]**: nothing. This run re-tests the claim on the **reserved FINAL split** that no earlier
step had scored, with an item-matched three-language probe, a 3-way LLM judge, a second judge family, blind
adjudication, placebos and an independent re-derivation.

> **Results:** [`RESULTS.md`](RESULTS.md) (narrative + verdicts) and
> [`results/RESULTS_tables.md`](results/RESULTS_tables.md) (auto-generated from `results/analysis.json`).
> Every headline number is recomputed from the raw JSONL by a second code path (`src/rederive.py` →
> `results/audit.json`).

## What is being compared (method vs baselines)

| | role |
|---|---|
| **Method** | the iter-1 exp4 selected **Heretic LoRA** (English objective, English data), applied to each model and **dose-scaled** by λ: `ΔW(λ) = λ · ΔW_saved`, with λ = 0 (no edit) → 1 (the shipped edit) |
| **Baseline 1** | the **unedited** model on the identical items, decoding and judge (condition `orig`) |
| **Baseline 2** | the **sibling model** — every contrast is GaMS3 *minus* Gemma-3-IT at matched English refusal, so a shared Gemma-3 property cancels |
| **Baseline 3** | three **public English-abliterated Gemma-3-12B-IT checkpoints** we did not build (p-e-w/heretic, huihui-ai, mlabonne v2) |
| **Baseline 4** | a **third language** (Hungarian) that is absent from GaMS3's CPT and SFT mix, separating "Slovene competence" from "GaMS-specific safety SFT" |
| **Control set** | benign look-alikes (XSTest safe + OR-Bench-hard) for over-refusal, giving an SDT decomposition into sensitivity `d′` and criterion `c` |

## Design in one paragraph

All prompts descend from **one English source** (the RefusEU evaluation items of the reserved iter-1 dataset
artifact): `EN_orig` → NLLB Slovene `SL_MT` → NLLB English back-translation `EN_BT` (the MT-noise control), and — new
here — NLLB Hungarian `L3_MT` produced with the **same** NLLB-1.3B settings (beam 4, sentence-split) as the Slovene
arm. The language effect is therefore `SL_MT` vs `EN_BT`, not Slovene-vs-English *items*. Refusal is scored by an
LLM judge with the frozen 3-way REFUSE/PARTIAL/COMPLY prompt of iter-2 exp5, on the first 128 generated tokens. The
headline statistic is

> **G3 = a_GaMS − a_Gemma**, where `a_m` is model *m*'s predicted **SL-MT refusal log-odds at EN-BT refusal = 50 %**,
> from a per-model binomial GLM `k_SL,s ~ Bin(n, expit(a + b·logit(p_EN,s)))` fitted across the λ steps.

Negative G3 = the Slovene refusal of GaMS collapses *further* than Gemma's at the same English strength.

## Layout

| path | what |
|---|---|
| `protocol.yaml`, `protocol.sha256` | the frozen protocol (git commit **`68f3f73`**, written *before* the first FINAL generation row) |
| `results/protocol_amendments.json` | timestamped amendments, each committed before the generation it affects |
| `src/common.py` | paths, seed 20260925, 128-token cap, lexicon (diagnostic only), freeze guard |
| `src/preflight.py` | S0: dependency existence + hashes, OpenRouter relay probe, L3 verification, checkpoint pins |
| `src/build_items.py` | S1: Hungarian NLLB MT + chrF QC, seeded nested subsets, Belebele/FLORES items |
| `src/calibrate.py` | S3: λ placement from the archived exp8 screen curves (SCREEN evidence, never FINAL) |
| `src/freeze.py` | S4: writes + hashes + commits `protocol.yaml` |
| `src/gen.py` | S5/S6: one model load per invocation — NF4 loader, LoRA forward hooks, λ dose, resumable FINAL jobs, Belebele + FLORES NLL |
| `src/judge_local.py` | S2: local judges (Qwen3-14B primary, Mistral-24B second family), gate/retest/final modes |
| `src/build_table.py` | merges generations + labels (+ the reused exp5 originals) into `results/rows_final.parquet` |
| `src/analysis.py`, `src/stats_core.py` | S8: rates, McNemar, G3 + bootstrap + permutation, SDT, two-point L3 lag, public checkpoints, gates |
| `src/rederive.py` | S9: independent re-derivation + three placebos → `results/audit.json` |
| `src/adjudication.py` | S7: blind adjudication batches (author model, **not** human) |
| `src/make_report.py`, `src/figures.py`, `src/make_outputs.py` | tables, figures, `method_out.json` (exp_gen_sol_out) |
| `data/` | `items.jsonl` (all prompts), `split_manifest_iter3.json` (seeded ranked subsets + sha256), L3 MT cache, Belebele/FLORES, `data_hashes.json` |
| `results/final/gens_*.jsonl` | every generation, one row per (item × arm × model × condition × λ) |
| `results/labels/` | judge labels, gate/retest reports |
| `results/` | `analysis.json`, `gates.json`, `audit.json`, `rows_final.parquet`, `competence.jsonl`, `preflight.json`, `l3_*.json` |
| `tests/test_stats.py` | T0 unit checks (Hautus, SDT closed form, exact McNemar, GLM recovery, bootstrap coverage, placebo null) |

## How to run

```bash
uv sync                                        # pinned environment (pyproject.toml + uv.lock)
cd src
../.venv/bin/python preflight.py               # dependency + relay + L3 checks
../.venv/bin/python build_items.py             # GPU (NLLB) ~11 min
../.venv/bin/python calibrate.py               # λ grid from the archived screen curves
../.venv/bin/python freeze.py --curve_n 200 …  # protocol freeze + git commit  (nothing FINAL before this)
../.venv/bin/python gen.py --model gemma_it  --phases final,batchcheck,bele
../.venv/bin/python gen.py --model gams3_it  --phases mini,regen,final,batchcheck,bele
../.venv/bin/python gen.py --model pew_heretic --phases public,bele
../.venv/bin/python judge_local.py --judge qwen3_14b  --mode gate,retest,final
../.venv/bin/python judge_local.py --judge mistral24b --mode gate,final
../.venv/bin/python build_table.py && ../.venv/bin/python analysis.py
../.venv/bin/python rederive.py && ../.venv/bin/python make_report.py
../.venv/bin/python figures.py && ../.venv/bin/python make_outputs.py
../../.venv/bin/python -m pytest -c ../pytest.ini ../tests/
```
One 23 GB GPU (NVIDIA L4). Every generation and judge job is **resumable** (append-only JSONL keyed by row) and every
model-facing job honours a wall-clock deadline file (`results/deadline_<model>.txt`), so an interrupted run resumes
instead of regenerating.

## Honest limitations

* **NF4 4-bit** everywhere (a 23 GB GPU cannot hold bf16 12B). Every contrast is within-precision, but absolute rates
  may differ from the released bf16 behaviour — this matters most for the public checkpoints.
* **The paid judge was unavailable.** The run-level OpenRouter budget was already exhausted
  (`403 aii_run_budget_exhausted`, see `results/preflight.json`), so the pre-registered gemini/gpt judges were
  replaced by **local** Qwen3-14B + Mistral-24B, gated against 586 *archived real gemini labels*
  (`results/labels/gate_report_*.json`). Judge quality is the main threat to these numbers and is reported per cell.
* **No human review.** The MT is not human-verified, there is no native-speaker audit, and the "blind adjudication"
  is done by the executor LLM, not a person. Every table that uses it says so.
* **The edit is the iter-1 Heretic pick**, which never reached ≤ 10/100 keyword refusals; it is a *dose axis*, not
  "what Heretic would ship".
* **Greedy decoding, single sample.** NF4 greedy output is batch-composition dependent: the exp5 regeneration check
  reproduced only 10/64 exact 128-token prefixes while agreeing 64/64 on the lexicon outcome
  (`results/dev/regen_check_gemma_it.json`).

## Restoring removed files

`.aii/manifest.yaml` marks these for deletion after the round; everything else (code, data, results, labels, figures,
logs, `method_out.json`) is kept in place.

* **`.venv/`** (≈ 12 GB, regenerable):
  ```bash
  uv sync            # or: uv venv .venv --python 3.12 && uv pip install --python .venv/bin/python -r requirements.lock.txt
  ```
* **`hf_cache/public/`** (≈ 90 GB, redownloadable — the three public checkpoints at their pinned shas):
  ```bash
  hf download p-e-w/gemma-3-12b-it-heretic            --revision e037e6e112ea85777fc3858469cdc31fdfceaa13 --local-dir hf_cache/public/pew_heretic
  hf download huihui-ai/gemma-3-12b-it-abliterated    --revision 33b9e7402b3d8b396afdd9a3cfcefe391bf7a696 --local-dir hf_cache/public/huihui
  hf download mlabonne/gemma-3-12b-it-abliterated-v2  --revision b8ae69bd7844187c27c941785afc1b0919f91f8e --local-dir hf_cache/public/mlabonne_v2
  ```
* **`src/__pycache__/`, `tests/__pycache__/`, `.pytest_cache/`** (regenerable): recreated by running the pipeline.

The two 12B within-study checkpoints, NLLB and the two judge models are **not** in this workspace: they live in the
run's shared HuggingFace cache (`$HF_HOME`) and are redownloaded on demand
(`google/gemma-3-12b-it@96b6f1ec`, `cjvt/GaMS3-12B-Instruct@1d0b27af`, `facebook/nllb-200-distilled-1.3B`,
`Qwen/Qwen3-14B@40c06982`, `mistralai/Mistral-Small-24B-Instruct-2501@9527884b`). No adapter is trained here; the
edit is read read-only from
`/ai-inventor/aii_data/runs/run_FVi3e3O9CH5I/3_invention_loop/iter_1/gen_art/gen_art_experiment_4/results/{gemma_it,gams3_it}/selected_adapter/`.
