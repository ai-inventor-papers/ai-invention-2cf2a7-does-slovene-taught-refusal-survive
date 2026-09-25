# Readout repair of exp8 — re-judging saved GaMS3/Gemma-3 de-censoring outputs

**SCREEN REPAIR, not confirmation.** This evaluation adds *no new model generations*. It re-judges the 24,000 responses
that experiment 8 (`art_T5ChU9GV1tf7`) saved, with characterised judges, and recomputes the headline "de-censoring hits
Slovene harder" lag (G3) that exp8 had read off a language-asymmetric keyword lexicon. By the hypothesis's
evidence-separation rule this repairs the *screen*; confirmatory evidence (B′, FINAL, L3) belongs to other iter-3 artifacts.

## What exp8 claimed, and the problem
exp8's headline `G3 (curve B) = -2.36 [-3.18, -1.62]` and its conflicting `A1 = -0.19` both came from the **lexicon**
(gemini-2.5-flash had labelled 11,767 Gemma rows and **0 GaMS rows** before the run's OpenRouter budget was exhausted).
A cross-model contrast read from a keyword list whose kappa vs gemini is ~0.34 on Gemma-EN is uninterpretable, and B (64
new tokens) and A1 (128 tokens) were judged at *different response lengths* as well as by different instruments.

## Mode
The shared OpenRouter run budget is **exhausted** (`GET /key` → `limit_remaining 0.0`; a gemini smoke call returns
`403 aii_run_budget_exhausted`, non-retryable; `:free` mirrors of Llama-3.3-70B / Gemma-3-27B / DeepSeek / Mistral-Small
all return 404). So this artifact runs in **MODE L**: the local open-weight ensemble is the primary readout, `$0` spent.
See `work/mode.json`.

## Instruments
- **Local judges (NF4, first-token argmax over REFUSE/PARTIAL/COMPLY):** Qwen3-14B (`@40c0698`, exp5's judge) and
  Mistral-Small-24B-Instruct-2501 (`@9527884`, exp7's judge, vendor-disjoint from both graded models). Frozen exp8 P1
  judge prompt verbatim (sha `97332090…`). Primary = the family with higher binary-R kappa vs archived gemini on exp8's
  1,000-row Gemma calibration set (`results/eval_results.json → step1_selection`).
- **Archived readouts** co-reported for the correction record: gemini-2.5-flash (Gemma only), Llama-3.1-8B (exp8 local),
  the lexicon (diagnostic only).
- **Blind author-model adjudication** (`adjudication/`): 240 edited rows (60 per model×language), labels stripped, judged
  by the executing LLM agent under the P1 rubric before any label file was opened. **This is not a human reference** — every
  error table says so. It is the reference for the Rogan-Gladen / PPI corrections and the bias tipping point.

## Layout
```
protocol.yaml, protocol.sha256   frozen protocol + hash (committed before the first new label)
amendments.jsonl                 timestamped post-freeze changes (UTC)
eval.py                          STEPS 2-7: characterise readout, recompute lag, B-vs-A1 decomposition,
                                 tipping point, cross-artifact SDT meta, placebos, outputs
src/common.py                    paths, frozen prompt (sha asserted), helpers
src/build_master.py              STEP 0: master table (request text, resp64/resp128 under the Gemma-3 tokenizer,
                                 all archived labels) + frozen sampling frames + blind adjudication file
src/judge_local.py              local NF4 judges (resumable, append-only labels/<judge>.jsonl)
src/stats_core.py               G3 curves, item×step bootstrap, Rogan-Gladen, support fallbacks, kappa/Se/Sp
                                 (fit_glm / Hautus / isotonic / kappa IMPORTED from exp8 src/analysis.py)
src/rederive.py                 independent second code path (numpy Newton GLM) -> work/rederive.json
work/master.parquet             one row per exp8 row + request + resp64/resp128 + labels  [regenerable, see below]
work/frames.json                frozen sample25 / calibration / adjudication frames + inclusion weights
work/items_relabelled.jsonl.gz  every row × trunc with all labels (item_id×model×arm×curve×step×trunc)
labels/qwen3_14b.jsonl, mistral24b.jsonl   new local-judge labels
adjudication/blind_items.jsonl, author_labels.json, _key.json
results/eval_results.json        full STEP 2-7 results (headline numbers)
judge_error_matrices.json        {judge: {model|lang|coding: {Se, Sp, CI, ref}}}  (reusable by other iter-3 artifacts)
READOUT_REPAIR.md                every iter-1/2 number the paper might quote -> validated replacement + status
figures/                         transfer curves per readout; forest of G3; tipping-point contour; meta forest
eval_out.json (+ mini/preview)   exp_eval_sol_out (per-row labels as predict_*, headlines in metrics_agg)
```

## How to run
```bash
uv venv .venv --python=3.12 && uv pip install --python .venv/bin/python -r pyproject.toml
.venv/bin/python src/build_master.py           # STEP 0
.venv/bin/python src/judge_local.py --judge qwen3_14b  --sets calib,adjudication,B_all,A1_native,origharm_native,A1_64,orig_64,e7H
.venv/bin/python src/judge_local.py --judge mistral24b --sets calib,adjudication,sample25
# then do the blind adjudication (adjudication/blind_items.jsonl -> adjudication/author_labels.json), then:
.venv/bin/python eval.py                        # STEPS 2-7 -> results/, eval_out.json, figures/
.venv/bin/python src/rederive.py                # independent re-derivation check
```

## Kept artifacts (workspace paths for the paper)
- `work/master.parquet`, `labels/*.jsonl`, `results/eval_results.json`, `judge_error_matrices.json`,
  `work/items_relabelled.jsonl.gz`, `figures/*` — all under 100 MB and pushed to the repo.

## Restoring removed files
`.aii/manifest.yaml` marks only redownloadable/regenerable bulk as `delete`:
- **`.venv/`** — `uv venv .venv --python=3.12 && uv pip install --python .venv/bin/python -r pyproject.toml`
- **`work/master.parquet`** (regenerable) — `.venv/bin/python src/build_master.py` (reads exp8's saved rows; also
  rebuilds `work/e7_hard.parquet`).
- **`__pycache__/` and `src/__pycache__/`** (regenerable) — Python bytecode caches; recreated automatically on the next
  `.venv/bin/python src/*.py` / `eval.py` run.
- **HuggingFace weights** live in the run's shared cache (`$HF_HUB_CACHE`), not in this workspace, so they need no manifest
  entry; re-fetch with `hf download Qwen/Qwen3-14B --revision 40c069824f4251a91eefaf281ebe4c544efd3e18` and
  `hf download mistralai/Mistral-Small-24B-Instruct-2501 --revision 9527884be6e5616bdd54de542f9ae13384489724`.
