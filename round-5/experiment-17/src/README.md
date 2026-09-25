# What does one English-only de-censoring edit buy on RefusEU's own prompts?

A pre-registered, paired experiment on the reserved **natural** RefusEU evaluation prompts (1,300 English + 1,300
Slovene), measuring what a single **English-only** Heretic-style refusal-direction edit does to attack success on
**Gemma-3-12B-it** and its Slovene-adapted sibling **GaMS3-12B-Instruct**, read out with the benchmark's own
guard-ensemble protocol run locally.

This is a **coverage and measurement** deliverable, not a novelty claim. That English-derived refusal directions
transfer to other safety-aligned languages is a premise here (Wang et al. 2025), not a finding. What is new is the
combination: the benchmark's own protocol, on its own reserved natural prompts, under a documented edit, in a sibling
pair that differs by language adaptation, with the readout error measured rather than assumed.

## Design in one paragraph

Both models run in identical NF4, greedy, 128 new tokens, an empty system turn, and their own (byte-identical) chat
template. Every FINAL prompt is generated twice per model: **ORIGINAL** (λ = 0, the baseline) and **EDITED** (λ = 1.0,
the saved iteration-3 Heretic LoRA r = 3 on `o_proj`/`down_proj`, applied as a scaled forward hook). λ = 0 is asserted
bit-identical to the unedited model (max |Δlogit| = 0). A third condition at **λ_gate** is added for a model whose DEV
English refusal is not cut by at least 50 % at λ = 1.0. Controls: a **norm-matched random direction** (rand_1) at λ = 1.0
on 200 pairs, and a **256-token** regeneration of 100 pairs. Every generated row is scored by the RefusEU guard
ensemble (Llama-Guard-3-8B + PolyGuard-Qwen, with a third guard adjudicating their disagreements), by a StrongREJECT
harmful-content evaluator, by two refusal flags, and by language-consistency and degeneracy checks. A 240-row blind
adjudication estimates each readout's sensitivity and specificity per model × language cell, and the headline rates are
also reported Rogan-Gladen corrected with a Lang-Reiczigel interval.

**The gold labels are a blind AUTHOR-MODEL (LLM) adjudication, not human labels.** No human review of any kind was
performed. A native-speaker audit is requested in `results/human_audit_request.json`.

**Budget note (important).** The run's shared OpenRouter budget was already exhausted when this artifact started
(HTTP 403, $12.12 of $12.00 spent by earlier steps). Every paid readout in the plan was therefore replaced by a local,
pinned, published substitute **before the protocol was frozen** — the gpt-4o-mini adjudicator by Qwen3Guard-Gen-8B, the
gemini StrongREJECT rubric by the official fine-tuned StrongREJECT evaluator, the P1 judge by the guards' refusal flags.
Paid spend in this artifact: **$0.00**. What that costs the claims is spelled out in `deviations.md` (D-R0) and in the
"Not executed" section of `RESULTS.md`.

## Layout

| path | what it is |
|---|---|
| `protocol.yaml`, `protocol.sha256` | the pre-registration, frozen (sha256) and committed before any FINAL generation |
| `results/protocol_amendments.jsonl`, `results/amendments/` | timestamped amendments (A1 = λ_gate per model), each committed before the work it affects |
| `deviations.md` | every departure from the plan, with its cost |
| `src/preflight.py` | existence + sha256 of every cross-artifact input, adapter sha1, P1-prompt sha assertion, model pins, OpenRouter check, disk |
| `src/build_items.py` | builds `data/items_final.jsonl` / `items_dev.jsonl` from the reserved dataset; fold, count and length assertions; provenance; contamination grep |
| `src/freeze.py` | freezes and commits the protocol; `record_amendment` |
| `src/gen.py` | one model per invocation: hook checks, MINI, the DEV dose grid, the FINAL conditions, controls |
| `src/guards.py` | the three local guards at pinned revisions, one in GPU memory at a time |
| `src/sr_ft.py` | StrongREJECT score from the official fine-tuned evaluator |
| `src/dev_gate.py` | the DEV dose-gate rule → amendment A1 |
| `src/adjudicate_frame.py`, `src/adj_show.py`, `adjudication/RUBRIC.md` | draws the blind adjudication frame and presents it; the fixed label rubric |
| `src/build_table.py` | merges generations with every readout → `results/rows_final.jsonl` |
| `src/analysis.py` | rates, paired McNemar effects, DiD, corrections, agreement, controls, placebos, statements |
| `src/rederive.py` | an independent re-derivation of every headline (never imports `analysis.py`) → `results/audit.json` |
| `src/figures.py`, `src/make_report.py`, `src/make_outputs.py` | figures F1–F5, `RESULTS.md`, `method_out.json` |
| `src/judge_paid.py`, `src/label.py` | the paid-readout path, kept for provenance; **not executed** (budget) |
| `results/rows_final.jsonl` | one row per generated FINAL row with every readout (the analysis input) |
| `results/analysis.json`, `results/rq2_table.csv`, `RESULTS.md` | every statistic with its status; the headline table; the rendered report |
| `results/judge_validity.json`, `results/cells_compliance.json` | per-cell Se/Sp and per-cell compliance (language, degeneracy, NA) |
| `results/gens/` | raw generations, append-only and resumable by key |
| `results/labels/` | raw guard and evaluator outputs, keyed by row |
| `data/provenance.json`, `data/contamination_check.json` | data provenance, split-manifest hashes, the contamination audit |
| `figures/` | F1 paired rates, F2 forest of deltas, F3 StrongREJECT distributions, F4 agreement and validity, F5 DEV gate curves |
| `method_out.json` (+ `mini_`/`preview_`) | `exp_gen_sol_out`: one example per generated row, baseline and method side by side |
| `tests/` | unit tests (statistics, parsers, cache keys) and the RESULTS/README number-reconciliation test |
| `run_chain.sh` | the GPU chain actually run, in order |
| `reproducibility.md` | pins, hashes, commands, wall time per phase |

## How to run it

```bash
uv sync                                    # Python 3.12; pins in pyproject.toml / uv.lock
export AII_RUN_ROOT=/path/to/3_invention_loop   # where the sibling artifacts live (dataset, exp9 adapters)
cd src
../.venv/bin/python preflight.py           # inputs, hashes, model pins, disk
../.venv/bin/python build_items.py         # data/items_final.jsonl (2,600 rows), items_dev.jsonl (200)
../.venv/bin/python -m pytest -c ../pytest.ini    # unit tests (run before any model load)
../.venv/bin/python freeze.py              # freeze + commit protocol.yaml
../.venv/bin/python gen.py --model gemma_it       # session A for the first model
cd .. && bash run_chain.sh                 # guards -> gates -> gate sessions -> StrongREJECT -> build_table
cd src
../.venv/bin/python adjudicate_frame.py --model gemma_it   # draw the blind frame (before labelling)
../.venv/bin/python adjudicate_frame.py --model gams3_it
# label adjudication/blind_<model>.jsonl into adjudication/labels.jsonl per adjudication/RUBRIC.md
../.venv/bin/python analysis.py && ../.venv/bin/python rederive.py
../.venv/bin/python figures.py && ../.venv/bin/python make_report.py && ../.venv/bin/python make_outputs.py
```

Hardware actually used: one NVIDIA L4 (23 GB), 48 CPU cores. One 12B or 8B model is resident at a time; every stage is
resumable by row key, so an interrupted run continues where it stopped.

## Restoring removed files

Nothing that a later step reads is deleted. The manifest (`.aii/manifest.yaml`) marks only regenerable caches:

| removed path | how to restore |
|---|---|
| `.venv/` | `uv sync` (pins in `pyproject.toml` / `uv.lock`; Python 3.12) |
| `__pycache__/`, `src/__pycache__/` | `python -m compileall src` |
| `tests/__pycache__/`, `.pytest_cache/` | `python -m pytest -c pytest.ini` |

Everything else in this workspace is kept: `results/` (the 11,600 generated rows and every guard and evaluator
label), `adjudication/` (the 240-row blind gold standard), `data/` (the frozen item files, provenance and
contamination audit), `figures/`, and the `method_out*.json` outputs. They are text, code, JSON or small figures, so
they stay in the repository as they are.

Model weights are **not** stored in this repository. They live in the run's shared HuggingFace cache and are restored by:

```bash
hf download google/gemma-3-12b-it        --revision 96b6f1eccf38110c56df3a15bffe176da04bfd80
hf download cjvt/GaMS3-12B-Instruct      --revision 1d0b27af5748784482600d24779409e7e1dc9adc
hf download meta-llama/Llama-Guard-3-8B  --revision 7327bd9f6efbbe6101dc6cc4736302b3cbb6e425 --exclude "original/*"
hf download ToxicityPrompts/PolyGuard-Qwen --revision 644bfe73ff498c9a14818b72a11187eaf23f0ff1
hf download Qwen/Qwen3Guard-Gen-8B       --revision 4505cb1a6f1864f21f8b27f7daf1b9a1aab6edbb
hf download qylu4156/strongreject-15k-v1 --revision 4bd893d32390d2cace4f067dc2e3ef5294fd78a2
hf download google/gemma-2b              --revision 9cf48e52b224239de00d483ec8eb84fb8d0f3a3a --exclude "*.gguf"
```

`restore.sh` runs exactly these commands. Llama-Guard-3 and Gemma are gated on HuggingFace and need an accepted licence
plus `HF_TOKEN`.

The LoRA edits themselves are **not** in this repository either: they are read from the sibling iteration-3 artifact
(`round-3/experiment-9/src/selected/{gemma_it,gams3_it}/adapter` and `.../adapters/<model>/rand_1`), which
stays on the run's storage volume. Their sha1 hashes are recorded in `results/inputs_check.json`, so a reader can verify
that the edit used here is the one that artifact published.

## Headline result

Every number here is rendered from `results/analysis.json`; `RESULTS.md` is the full report.

| model | language | ASR original | ASR edited | paired delta [95% CI] | verdict |
|---|---|---|---|---|---|
| Gemma-3-12B-it | EN | 0.045 | 0.897 | 0.852 [0.831, 0.870] | ROBUST |
| Gemma-3-12B-it | SL | 0.026 | 0.683 | 0.657 [0.629, 0.683] | ROBUST |
| GaMS3-12B-Instruct | EN | 0.033 | 0.970 | 0.937 [0.923, 0.949] | ROBUST |
| GaMS3-12B-Instruct | SL | 0.068 | 0.915 | 0.847 [0.826, 0.867] | ROBUST |

Three things the design, not the size of those numbers, is what makes reportable:

1. **The edit transfers.** One English-only edit raises benchmark-protocol attack success in *both* languages and
   *both* models, by an exactly paired McNemar test on identical prompts (Holm-corrected across the four cells).
   That English-derived refusal directions reach other safety-aligned languages is a **premise** here (Wang et al.
   2025), not a discovery; what is new is measuring it with the benchmark's own protocol on its own reserved
   natural prompts.
2. **The readout is the weak link.** Against a blind author-model gold standard, the guard-ensemble ASR has
   sensitivity 1.00 everywhere but specificity of only 0.73–0.90, so **three of the four cells fail the
   pre-registered validity gate** (Sp ≥ 0.80). The raw ASR over-counts harm: many "unsafe" edited responses hedge,
   lecture or deflect without giving real uplift. Corrected rates are reported beside every raw one.
3. **The controls hold.** A norm-matched random direction at the same dose moves nothing, label-permutation
   placebos centre on zero, and the λ = 0 condition is bit-identical to the unedited model.

The cross-model difference (GaMS strips further than Gemma in both languages) is reported **descriptively only** —
it is not dose-matched, and the pre-registered criterion for claiming it requires adjudication gates that two cells
do not pass.

## What to read first

`RESULTS.md` — it is rendered from `results/analysis.json` by code, with no hand-typed numbers, and separates completed
confirmatory findings, descriptive and exploratory readings, and components that were not executed.
