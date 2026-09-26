# Tracing every paper number to saved results (iteration-5 audit)

An **analysis-only audit** of the GaMS3-vs-Gemma-3 abliteration study. It makes no new generations, calls no paid judge, and
spends $0 on OpenRouter. The one exception is an optional, gated GPU re-measurement of an existing quantity
(exp15's first-token KL, using the saved adapters). The audit re-reads the saved outputs of earlier artifacts (read-only)
and answers the two analytical objections of the iteration-4 blocking review:

1. **Is the baseline component of the cross-model lag (exp15 `G3_orig`) a ceiling artefact?** It is estimated from
   lambda-0 refusal rates of 96-99.7%. The audit reports:
   - an exact **fragility index** (the minimum number of label flips that erases it, after Walsh et al. 2014);
   - the exact paired McNemar view;
   - leave-k-items resampling;
   - estimators that genuinely differ from one another. Hautus, the Jeffreys posterior mean of p and Haldane-Anscombe
     are the *same* logit, so they are not counted as alternatives to each other;
   - an item bootstrap and a permutation placebo;
   - a comparison with the expected number of judge mislabels.

   The same analysis is extended to every other item body in eval3's label frame.
2. **Does "no Slovene-specific KL leakage" (C5a) hold with intervals?** exp15 saved per-condition means only. Its
   points are therefore reproduced exactly and reported with seed/dose *sensitivity ranges*, which are not sampling
   intervals. exp9 and exp14 saved per-item KL, so both are item-bootstrapped. An optional GPU re-measurement of exp15's
   40 prompts is accepted only if it reproduces the saved means within 5%.

It also:

- builds the full `G3 / G3_orig / G3_edit / slope` decomposition for every body x readout;
- regenerates the exp14 tables from exp14's own `analysis.json`, with an independent count cross-check;
- writes a machine-readable **correction ledger** for the iteration-4 paper draft. Each audited number gets a status
  (`SURVIVES / SHRINKS / REVERSES / UNTRACEABLE`) plus an attribution flag;
- emits the owed iteration-3 tables;
- harmonises the criterion-shift (SDT `c`) sign conventions across bodies;
- writes the exp13 not-executed record, with the B/C item-pool overlap against exp14 **recomputed**;
- produces a coverage table and an end-of-run verdict table.

All decision thresholds for the post-hoc analyses were frozen in `protocol_eval.yaml` and git-committed before computation.
These analyses can downgrade a claim but cannot confirm a new one. **No human labels exist anywhere.** Every adjudication
re-used here is author-model, not human. The native-speaker audit is listed as outstanding human input.

**Headline numbers are not typed here.** See `PAPER_INSERTS.md`, which is rendered from `results/*.json`, and the per-step
markdown files in `results/`.

## Layout

| path | what |
|---|---|
| `protocol_eval.yaml` | frozen decision rules (committed before Steps 1-2) |
| `inputs.yaml` | every read-only source path (run-relative) |
| `eval.py` | orchestrator: runs Steps 0-7 and writes `eval_out.json` (exp_eval_sol_out schema) |
| `src/common.py` | paths, JSON helpers, Hautus logit, CIs |
| `src/check_inputs.py` | Step 0: existence, size and sha256 of every input -> `results/inputs_manifest.json` |
| `src/ceiling.py` | Step 1: fragility index, paired McNemar, leave-k, estimator sweep, bootstrap, permutation, judge-error comparison, eval3-body extension |
| `src/kl_excess.py` | Step 2: C5a excess ratio (exp15 points, exp9/exp14 item bootstrap, GPU gate, cross-body reconciliation) |
| `gpu/kl_recompute.py` | Step 2c (optional): per-prompt KL re-measurement of exp15; model and adapter code copied verbatim from exp15 `src/gen.py` |
| `gpu/pyproject.toml`, `gpu/uv.lock` | exp15's exact pinned GPU environment (torch 2.14, transformers 4.57.6, bitsandbytes 0.50.2) |
| `src/decomposition.py` | Step 3: decomposition table with frozen status rule |
| `src/exp14_tables.py` | Step 4: exp14 tables regenerated from JSON, plus an independent rows_final cross-check |
| `ledger_pointers.yaml` | executor-written POINTERS (file + JSON path, never values) for headline and review-named numbers |
| `src/ledger.py` | Step 5: token extraction, auto-matching, pointer resolution, statuses, placebo match rate |
| `src/owed.py` | Step 6: owed tables, criterion-shift harmonisation, exp13 record and overlap, coverage, verdicts |
| `src/make_tables.py` | renders every markdown table, `PAPER_INSERTS.md` and the figures from JSON |
| `verify/verify.py` | independent second code path (never imports `src/`) -> `results/verify.json` |
| `tests/test_units.py` | unit tests (estimator identity, fragility, ratio invariance, 8-gram overlap, sign-map round trip) |
| `results/` | all outputs: `ceiling_sensitivity.*`, `kl_excess.*`, `decomposition_table.*`, `exp14_tables_regenerated.*`, `correction_ledger.{json,csv}`, `ledger_summary.md`, `owed_tables.md`, `criterion_shift.*`, `not_executed_exp13.*`, `coverage_table.md`, `verdict_table.*`, `verify.json`, `inputs_manifest.json`, `kl_items_exp15_recomputed.jsonl` (if the GPU step ran) |
| `figures/` | `fig_fragility`, `fig_kl_excess_forest`, `fig_decomposition_forest` (PDF + PNG) |
| `eval_out.json` (+ `full_`/`mini_`/`preview_`) | schema-validated deliverable: headline metrics plus one example per ledger, ceiling, KL and decomposition row |
| `PAPER_INSERTS.md` | paste-ready sentences and tables for the paper, rendered from JSON |
| `logs/` | run logs |

## How to run

Upstream artifacts are located through one constant, `AII_RUN_ROOT` (default: three folders above this one, i.e. the
invention-loop root). See `reproducibility.md` for the full, as-run procedure.

```bash
uv venv .venv --python=3.12 && uv pip install --python .venv/bin/python -r requirements.lock.txt
.venv/bin/python eval.py                 # Steps 0-7 (CPU, ~5 min); reads sources read-only
.venv/bin/python -m pytest -q            # unit tests
.venv/bin/python verify/verify.py        # independent re-derivation
# optional GPU re-measurement (needs the pinned weights in the HF cache, an HF token for gated Gemma, and ~10 GB VRAM):
(cd gpu && uv sync --frozen && .venv/bin/python kl_recompute.py) && .venv/bin/python src/kl_excess.py && .venv/bin/python eval.py
```

Once the iteration-5 experiments have written `results/analysis.json`, `src/owed.py` fills the PENDING rows (RQ2, C-OUT)
by glob. Re-running `eval.py` refreshes every table.

## Honest limits

- Steps 1 and 2 are post-hoc sensitivity analyses on already-seen data.
- The unedited-cell judge specificity rests on 1-2 adjudicated non-refusals per cell, so the expected-mislabel comparison
  is order-of-magnitude only.
- Auto-matching a two-decimal number against about 10^4 JSON leaves has a high chance-match rate. This rate is measured
  by a shifted-token placebo and reported in `results/ledger_summary.md`. Auto `SURVIVES` is therefore weak evidence, and
  the pointer rows carry the audit. Unmatched and ambiguous tokens stay `UNTRACEABLE`.
- Criterion-shift estimates come from different bodies, judges and twin sets and are **not pooled**.
- The criterion-shift summary applies exp14's pre-registered 0.90 output-language compliance gate to the harmonised
  rows. exp14's `SLinput` rows use GaMS3's SL->EN cell, whose compliance is 0.00, so they are flagged
  INVALID-MANIPULATION. This is the same gate the decomposition table uses. It was applied *after* the frozen all-rows
  sign rule had been evaluated, so both outcomes are reported, and the refinement is labelled post-hoc. The
  compliance issue was raised in an external note and verified here against `compliance_gate` before it was used.

## Restoring removed files

Only regenerable environments are marked `delete` in `.aii/manifest.yaml`:

- `.venv/` (analysis environment): `uv venv .venv --python=3.12 && uv pip install --python .venv/bin/python -r requirements.lock.txt`
- `gpu/.venv/` (exp15's pinned GPU environment, about 9 GB): `cd gpu && uv sync --frozen`
- `src/__pycache__/` (bytecode cache): regenerated by running `.venv/bin/python eval.py`
- `tests/__pycache__/` and `.pytest_cache/` (test caches): regenerated by `.venv/bin/python -m pytest -q`
- Model weights are never stored here. They are read from the run's shared HF cache and can be re-downloaded with
  `huggingface-cli download google/gemma-3-12b-it --revision 96b6f1eccf38110c56df3a15bffe176da04bfd80` and
  `huggingface-cli download cjvt/GaMS3-12B-Instruct --revision 1d0b27af5748784482600d24779409e7e1dc9adc`.
