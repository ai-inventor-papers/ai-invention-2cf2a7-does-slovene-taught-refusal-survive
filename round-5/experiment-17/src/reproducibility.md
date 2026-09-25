# Reproducibility — exactly what was run

This describes what **actually** ran, including the mid-run substitutions, not an idealized pipeline.
Every path below is **relative to this artifact folder**. Nothing here refers to the machine it ran on.

## 0. Get this artifact

This folder is published as one directory of a public GitHub repository. The sibling artifact folders it reads are
published beside it.

```bash
git clone <repository-url> && cd <repository>/<this-artifact-folder>
```

Cross-artifact inputs are read through **one** constant, `RUN` in `src/common.py`, which resolves in this order:
`$AII_RUN_ROOT` → the nearest ancestor directory named `3_invention_loop` → `../../../..` (the grandparent of this
folder, which is where the published repository puts the sibling folders). If your clone's layout differs, set it
explicitly and nothing else needs changing:

```bash
export AII_RUN_ROOT=/absolute/path/to/the/folder/that/contains/iter_1,iter_3,iter_4
```

Artifacts read (by id; each is a sibling folder, read-only):

| artifact id | what is read | relative path under `$AII_RUN_ROOT` |
|---|---|---|
| `art_EG6OpEkGvysx` (dataset) | `full_data_out.json` block `refuseu_eval`; `outputs/split_manifest.json`; `scripts/s6_llamaguard.py` (guard loader precedent) | `iter_1/gen_art/gen_art_dataset_1/` |
| iteration-3 experiment 9 | the saved edits `selected/{gemma_it,gams3_it}/adapter/` and the norm-matched random controls `adapters/<model>/rand_1/` | `iter_3/gen_art/gen_art_experiment_9/` |
| iteration-3 experiment 11 | the NF4 loader and forward-hook generation code this artifact's `src/gen.py` is adapted from | `iter_3/gen_art/gen_art_experiment_11/src/gen.py` |
| iteration-2 experiment 8 | the verbatim P1 refusal-judge prompt (its sha256 is asserted in preflight) | `iter_2/gen_art/gen_art_experiment_8/src/common.py` |
| iteration-4 experiment 14 | the paid-judge client and the StrongREJECT rubric template (`data/strongreject_judge_templates.json`, copied into this folder) | `iter_4/gen_art/gen_art_experiment_14/` |
| `art_NZ9n2Ej5RtGt` (research) | the verified RefusEU protocol, StrongREJECT formula and Rogan-Gladen/Lang-Reiczigel estimator specs | `iter_4/gen_art/gen_art_research_1/` |

**No user-uploaded file is used by this artifact.** The user-upload folder was checked and nothing in it feeds this
experiment, so there is no private input a reader must supply.

`src/preflight.py` existence-checks every one of those paths and records each file's sha256 in
`results/inputs_check.json`; a reader can verify they have the same inputs.

## 1. System, Python, environment

- Ubuntu (Linux 6.8), one **NVIDIA L4, 23 GB VRAM**, 48 CPU cores, 503 GB RAM.
- **Python 3.12** (`requires-python = ">=3.12,<3.13"`).
- System packages: only a working CUDA driver (the run had driver 580.173.02 / CUDA 13.0). No other apt packages are
  needed; `uv` installs everything else, including the CUDA runtime wheels.
- `uv` (any recent version) must be on PATH.

```bash
uv sync                    # creates .venv and installs the 113 pins in pyproject.toml / uv.lock
.venv/bin/python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

Key installed versions, pinned in `pyproject.toml` and listed in full in `requirements.lock`
(`uv pip freeze` output): torch 2.14.0+cu130, transformers 4.57.6, bitsandbytes 0.50.2, peft 0.21.0, numpy 2.5.3,
scipy 1.18.1, pandas 3.0.6, statsmodels 0.15.0, scikit-learn 1.9.1, matplotlib 3.11.2,
lingua-language-detector 2.2.0, loguru 0.7.3, pytest 9.1.1, openai 3.19.2, pyyaml 6.0.3.

## 2. Downloads, environment variables, credentials

Seven model repositories are downloaded from the HuggingFace Hub at **pinned revisions** (about 110 GB total).
`restore.sh` runs exactly these commands:

```bash
hf download google/gemma-3-12b-it          --revision 96b6f1eccf38110c56df3a15bffe176da04bfd80
hf download cjvt/GaMS3-12B-Instruct        --revision 1d0b27af5748784482600d24779409e7e1dc9adc
hf download meta-llama/Llama-Guard-3-8B    --revision 7327bd9f6efbbe6101dc6cc4736302b3cbb6e425 --exclude "original/*"
hf download ToxicityPrompts/PolyGuard-Qwen --revision 644bfe73ff498c9a14818b72a11187eaf23f0ff1
hf download Qwen/Qwen3Guard-Gen-8B         --revision 4505cb1a6f1864f21f8b27f7daf1b9a1aab6edbb
hf download qylu4156/strongreject-15k-v1   --revision 4bd893d32390d2cace4f067dc2e3ef5294fd78a2
hf download google/gemma-2b                --revision 9cf48e52b224239de00d483ec8eb84fb8d0f3a3a --exclude "*.gguf"
```

Environment variables, **by name only** (never write values into the repository):

- `HF_TOKEN` — required. `google/gemma-3-12b-it`, `google/gemma-2b` and `meta-llama/Llama-Guard-3-8B` are gated: accept
  their licences on the Hub with the same account first.
- `HF_HOME` — where the ~110 GB of weights land. Model weights are **not** in this repository.
- `AII_RUN_ROOT` — see §0. Only needed if the sibling-artifact layout differs from the published one.
- `OPENROUTER_BASE_URL`, `OPENROUTER_API_KEY` — **not needed to reproduce anything in this artifact.** No paid call was
  made (see §5). They are read only by `src/judge_paid.py` / `src/label.py`, which were not executed.
- Optional knobs actually used: `AII_DEV_GRID` (set to `0,1.0` for the GaMS session, amendment A0), `AII_DEVICE`
  (set to `cpu` only for the component smoke tests while the GPU was busy), `AII_TOKEN_BUDGET`, `AII_MAX_BS`.

## 3. The exact commands, in order

Seed **20260925** everywhere (bootstraps, permutations, sampling frames, hash orders). The one-shot driver is
`method.py`; below is the stage sequence it runs, which is what was actually executed.

```bash
cd src
../.venv/bin/python preflight.py                    # inputs + sha256, model pins, disk, API check  (~1 min)
../.venv/bin/python build_items.py                  # data/items_final.jsonl (2,600), items_dev.jsonl (200)  (~1 min)
cd .. && .venv/bin/python -m pytest -q -c pytest.ini   # 14 unit tests, BEFORE any model load  (~40 s)
cd src && ../.venv/bin/python freeze.py             # sha256-freeze + git-commit protocol.yaml
../.venv/bin/python gen.py --model gemma_it         # hook checks, MINI, 8-dose DEV grid, FINAL orig + edit@1.0,
                                                    #   rand_1 control, 256-token subset     (~65 min, 5,800 rows)
cd .. && bash run_chain.sh "" 650                   # everything below, unattended:
#   guards on Gemma rows: PolyGuard (~30 min) -> Llama-Guard-3 (~16 min) -> Qwen3Guard on disagreements (~7 min)
#   dev_gate.py --model gemma_it                    -> amendment A1: PASS at lambda 1.0, so NO gate session
#   AII_DEV_GRID=0,1.0 gen.py --model gams3_it      (~55 min, 6,220 rows)
#   guards on the new rows (~50 min) -> dev_gate.py --model gams3_it -> PASS at 1.0, no gate session
#   sr_ft.py                                        StrongREJECT-ft on all 13,000 rows (~19 min at 11.5 rows/s)
#   build_table.py                                  -> results/rows_final.jsonl
cd src
../.venv/bin/python adjudicate_frame.py --model gemma_it    # 120 blind rows; drawn BEFORE any label
../.venv/bin/python adjudicate_frame.py --model gams3_it    # 120 blind rows
#   then the blind labelling: adj_show.py <model> <start> <n> prints rows, adj_add.py appends labels,
#   per the fixed rubric in adjudication/RUBRIC.md -> adjudication/labels.jsonl (240 rows)
../.venv/bin/python analysis.py                     # -> results/analysis.json, rq2_table.csv, judge_validity.json
../.venv/bin/python rederive.py                     # independent re-derivation -> results/audit.json
../.venv/bin/python figures.py                      # figures/F1..F5 (.pdf + .png)
../.venv/bin/python make_report.py                  # RESULTS.md, every number rendered from analysis.json
../.venv/bin/python make_outputs.py                 # method_out.json
cd .. && .venv/bin/python -m pytest -q -c pytest.ini   # includes the RESULTS/README number-reconciliation test
```

Total wall time on the single L4: **about 5 h**. Every stage is append-only and resumable by row key, so an
interrupted stage continues where it stopped (this happened twice during the real run — a duplicated Gemma DEV
process, and a killed StrongREJECT pass that resumed at row 4,192 — see `deviations.md` D-DUP).

## 4. Protocol freeze and amendments

`protocol.yaml` was frozen (sha256 → `protocol.sha256`, git-committed) **before the first FINAL generation row**:
sha256 `f11860cf2fe8e6c11c400edcc5c4405f019416f9112664c0101d3479e4d9593c`, at 2026-09-25T00:45:46Z
(`results/freeze.json`). `src/common.guard_final` refuses to generate a FINAL row unless the file still hashes to
that value. Amendments are in `results/protocol_amendments.jsonl`, each written before the work it affects:
A0 (short GaMS DEV grid), A1 per model (gate status), A2 (gate-condition size), A3 (no paid readout), A4 (adjudicator
scope).

## 5. The substitution a reader must know about

The run's shared OpenRouter budget was **already exhausted** when this artifact started (HTTP 403
`aii_run_budget_exhausted`, recorded verbatim in `results/inputs_check.json`). Paid spend in this artifact is
**$0.00**. Before the protocol was frozen, every paid readout was replaced by a local, pinned, published model:
the guard-disagreement adjudicator → `Qwen/Qwen3Guard-Gen-8B`; the StrongREJECT rubric scorer → the official
fine-tuned StrongREJECT evaluator (`qylu4156/strongreject-15k-v1` on `google/gemma-2b`); the P1 refusal judge →
the guards' own refusal flags. `deviations.md` D-R0 states what that costs each claim. A reader therefore needs **no
API key** and reproduces the same numbers deterministically (greedy decoding throughout).

## 6. What a reader should get, and where it appears

| file | contents |
|---|---|
| `results/rows_final.jsonl` | 11,600 FINAL rows (2 models × {orig, edit@1.0} × 2,600, plus 400 random-control and 200 256-token rows per model), each with every readout. The analysis input. |
| `results/analysis.json` | every statistic with its CI, n, p, Holm-adjusted p, and a status in {CONFIRMATORY, DESCRIPTIVE, EXPLORATORY, NOT_EXECUTED} |
| `results/rq2_table.csv` | the headline table: model × language × condition × readout, raw and Rogan-Gladen corrected |
| `results/audit.json` | the independent re-derivation: every headline recomputed through a second code path, with the count of mismatches (expected 0) |
| `results/dev_gate_<model>.json` | the DEV dose-gate curves behind the manipulation check |
| `results/judge_validity.json` | per-cell sensitivity/specificity of every readout against the blind author-model gold |
| `RESULTS.md` | the report; every number rendered from `analysis.json` by `src/make_report.py`, no hand-typed figures |
| `figures/F1..F5` | paired rates; forest of deltas; StrongREJECT distributions; guard agreement and validity; DEV gate curves |
| `method_out.json` (+ `full_`/`mini_`/`preview_`) | one example per generated row, baseline (`metadata_role: baseline`) and edited (`method`) side by side |

The headline numbers a reader should reproduce, and where they live: the manipulation check and the paired
original→edited effect per model × language are in `RESULTS.md` §1 (from `analysis.json` keys `statements.S2`,
`statements.S1` and `edit_effects`); the readout-validity table is §2 (`adjudication.cells`); the cross-model
difference is §2 (`did`). The gold labels are a **blind author-model (LLM) adjudication**, never human — so every
corrected rate is labelled "adjudicator-agreement-corrected", and `results/human_audit_request.json` records the
native-speaker audit that was requested and **not** performed.
