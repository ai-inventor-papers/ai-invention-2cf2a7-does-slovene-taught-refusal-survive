# Paid judges re-score the Slovene refusal lag

**Protocol completion, not a re-screen.** This artifact makes **no new model generations**. It re-judges the responses that
four earlier artifacts of this run already saved (exp8, exp9, exp10, exp11), with the paid readout those artifacts had
pre-registered but never been able to run, and it recomputes every lag headline with only the label column swapped.

The number the whole line turns on is **G3** — the GaMS3-minus-Gemma-3 Slovene refusal log-odds at *matched English
refusal*. Every G3 on record so far came from an instrument with no validated error rates in the two cells that fix its
sign: **GaMS-SL-edited** and **Gemma-SL-edited**. This artifact measures those error rates and reports what survives.

## What it found

| | |
|---|---|
| **Pooled G3** (GaMS − Gemma Slovene refusal log-odds at matched English refusal) | **−1.17 [−1.84, −0.50]** (REML + HKSJ, 3 item bodies; PPI-rectified −1.77 [−1.89, −1.65]) |
| **Pooled G3_edit** (same, minus each model's own pre-edit language gap) | **+0.39 [−1.95, +2.74]** — centred near zero |
| **Gate (Se and Sp ≥ 0.80 in both decisive cells)** | **FAILS**: gemini-2.5-flash Se 0.91/0.99 but **Sp 0.73/0.66** — it over-calls REFUSE on edited Slovene |
| Verdict | `REFUTE-BOUND` on G3_edit (`|G3_edit| < 2.74`), reported as **READOUT NOT VALIDATED** because the gate failed |

**The lag at matched English refusal is real and reproduces under a paid frontier judge** — the same negative sign in
every item body, every readout (raw, Rogan-Gladen, PPI++, second family, translate-then-judge) and at exp10's operating
point (G3_op = −2.42 [−4.35, −1.53]). The within-item model-label-swap placebo is centred at 0 with p = 0.001, the
language-swap placebo is centred at 0, and the shuffled-judge kappa is 0.007.

**But it is not an effect of the de-censoring edit.** `G3_orig` — the same contrast at λ = 0, before anything is edited —
is already −1.1 to −2.6 in every body. Subtracting it leaves `G3_edit` indistinguishable from zero. The pre-registered
rival **R-BASE (baseline offset) is therefore not refuted; it is the best-supported account** of the whole C-LAG line:
GaMS3 simply starts with less Slovene refusal than Gemma-3, and the English-objective edit moves both models' Slovene
refusal roughly in parallel.

**A separate, reusable result: the paid frontier judge is not good enough for this measurement either.** Against a blind
4-class adjudication it reaches Se 0.91–0.99 but Sp 0.66–0.73 on edited Slovene rows, and gemini-vs-gpt-4.1-mini kappa
is only 0.39 in GaMS-SL-edited. The tipping analysis closes the loop: erasing the lag needs 0.55 extra Gemma-SL
false-REFUSE or 0.13 extra GaMS-SL false-COMPLY, and the **measured** error CIs (1−Sp = 0.34 [0.17, 0.57]; 1−Se = 0.09
[0.03, 0.26]) reach **both** of those thresholds. Judge error alone can still account for the lag.

## What was actually run

| stage | status |
|---|---|
| Row frame over 4 artifacts' saved generations (45,207 rows) | done — `work/frame.parquet` |
| Judge-tier bake-off (flash-lite vs flash) on 721 prior adjudications + 300-row drift set | done — `results/tier_bakeoff.json` |
| Primary pass, `google/gemini-2.5-flash`, frozen P1 prompt, thinking off | done — 25,025 fresh labels + 11.9k reused archived gemini labels |
| Second family, `openai/gpt-4.1-mini`, stratified | done — 9,888 labels |
| Blind adjudication, 480 rows, 4-class rubric v2 | done — 285 by `claude-sonnet-4.5`, 195 by the executing agent (AM2), 40-row overlap |
| StrongREJECT ASR arm | **partial** — 1,108 of 5,800 rows before the platform key limit (AM2) |
| Translate-then-judge (NLLB SL→EN) | translations done (5,800 + 600 round-trip); judged with exp9's **J1** instead of the paid judge (AM2) |
| Recompute, rivals, tipping, HKSJ pooling, placebos, audit | done — `results/recompute.json`, `results/rederive.json` |

**Spend: $4.31** of the $8.00 self-imposed hard stop. The run stopped early because the *platform's* shared OpenRouter key
hit its own daily limit (`GET /key`: limit 12.0, usage 11.80), not because this artifact's cap was reached. Every
consequence of that is logged in `amendments.jsonl` as **AM2** and flagged in every table it touches.

## The four corrections to the direction (in `protocol.yaml`)

- **C1** The "590-row gold calibration block" of the iter-1 dataset artifact holds **hazard-category gold for prompts**,
  not refusal labels for responses — verified at start-up (`work/inputs_check.json`, `C1_gold_calib_check.verified: true`).
  It cannot calibrate a refusal judge, so the bake-off uses pooled prior refusal adjudications instead.
- **C2** The direction's gate (`Sp >= 0.80` in GaMS-SL-edited) guards the **wrong error**. The lag breaks after only
  ~0.098 GaMS-SL *false-COMPLY*, which is a **sensitivity** failure. The gate is therefore **Se >= 0.80 AND Sp >= 0.80 in
  both decisive cells**, plus kappa(primary, second family) >= 0.6.
- **C3** 3 h wall clock, not 6 h.
- **C4** The frozen P1 prompt says "truncated at 64 tokens" even where 128-token responses are judged. Kept **verbatim**,
  because its sha256 (`97332090…`) is the pre-registered identity of the instrument. The wording mismatch is not tested.

## Layout

```
protocol.yaml, protocol.sha256   frozen protocol, sha256'd and git-committed BEFORE the first paid call
amendments.jsonl                 timestamped amendments (AM0 bake-off outcome, AM1 cut ladder, AM2 key limit), each committed before the work it affects
eval.py                          STEPS 3-9: error matrices, recompute, rivals, tipping, pooling, verdict, placebos, figures, outputs
src/common.py                    paths, the frozen P1 prompt (sha asserted at import), helpers
src/build_frame.py               STEP 1a: the row frame over all four artifacts + inputs check + the C1 verification
src/bakeoff.py                   STEP 1c: judge-tier bake-off and the archived-label drift check
src/judge_api.py                 async OpenRouter client: append-only ledger, resume, cumulative-$ printout, HARD STOP
src/label_passes.py              STEP 1d + 2: cost projection and the primary / second / TTJ / ASR passes
src/nllb_ttj.py                  NLLB-200-distilled-1.3B translation (exp11 settings) + the EN->SL->EN round-trip control
src/ttj_judge_j1.py              AM2: exp9's J1 judge on the English translations (the paid TTJ pass was blocked);
                                 ensure_model() rebuilds work/j1_model/ from exp9's shards on demand (not shipped, see below)
restore.sh                       rebuilds everything this repo does not ship (.venv, the J1 checkpoint)
src/adjudicate.py                STEP 3: blind sampling, rubric v2, adjudication run
src/readout.py                   assembles the per-row readout table from frame + ledger + adjudication
src/engine.py                    the common curve engine (imports the byte-identical vendored exp9 GLM and exp8 fit_glm)
src/rederive.py                  STEP 9: independent numpy/scipy audit path (never imports vendor/, engine.py or eval.py)
src/smoke.py                     reproduces each artifact's archived headline from its archived label column
vendor/                          byte-identical estimator code from exp8/exp9/exp10/exp11/eval2 + vendor/SHA256.json
prompts/                         frozen P1 rubric v2, the official StrongREJECT rubric and the JSON-output adaptation
labels/ledger.jsonl              append-only paid-call ledger (cache key, judge, label, usage cost, timestamp)
labels/readout_rows.jsonl.gz     per-row readout: response, every judge label, the TTJ translation, ASR fields, adjudication
adjudication/                    blind batches, key, labels, and the agent blind batch (AM2)
results/                         tier_bakeoff.json, judge_error_matrices_v2.{json,md}, recompute.json, rederive.json, smoke_tests.json
READOUT_v2.md                    every quotable lag number mapped to its validated replacement, with a SURVIVES/SHRINKS/REVERSES/UNCITABLE status
figures/                         curves under each readout, forest plot, Se/Sp table, tipping plot
eval_out.json + full/mini/preview  exp_eval_sol_out schema
```

## How to run

```bash
uv venv .venv --python=3.12 && uv pip install --python .venv/bin/python -r <(sed -n '/dependencies/,/]/p' pyproject.toml | grep '==' | tr -d ' ",')
cd src && ../.venv/bin/python build_frame.py          # row frame (needs the sibling artifact folders; see reproducibility.md)
../.venv/bin/python bakeoff.py                        # PAID (~$0.14)
../.venv/bin/python label_passes.py project           # cost projection -> the cut ladder
../.venv/bin/python label_passes.py primary 2         # PAID (~$2.2)
../.venv/bin/python label_passes.py second            # PAID (~$1.1)
../.venv/bin/python nllb_ttj.py                       # GPU, no spend
../.venv/bin/python ttj_judge_j1.py                   # GPU, no spend (AM2 substitute for the paid TTJ pass)
../.venv/bin/python label_passes.py asr               # PAID (~$1.6 for the full frame)
../.venv/bin/python adjudicate.py sample && ../.venv/bin/python adjudicate.py run   # PAID (~$0.6)
cd .. && .venv/bin/python eval.py                     # no spend
.venv/bin/python src/rederive.py                      # independent audit
```

## Honest limits

- **The reference is not human.** Se/Sp are measured against two Claude-family adjudicators working blind under a
  committed rubric. They may share failure modes with the judges (both are LLMs, and one adjudicator is the executing
  agent). Every table says **NOT HUMAN**. A **native-speaker audit of 60 edited rows per model × language is formally
  requested as human input** and is nowhere assumed to have happened.
- **Inherited generations.** NF4 precision, 128 new tokens (64 on the exp8 trial curve and exp10). StrongREJECT normally
  scores full responses, so the ASR numbers are a **lower bound** on harmful content and absolute levels are engine-specific.
  All contrasts are within-precision.
- **MT items.** Probes are NLLB machine translations, not human-verified, and translate-then-judge adds a second MT pass.
  The round-trip flip rate quantifies that noise floor.
- **k = 3 item bodies**, two of which share the iter-1 LoRA — item-independent but *not* edit-independent, so the
  prediction interval is nearly uninformative and this artifact reports only **its half** of the C-LAG decision.
- **AM2 substitutions** (ASR partial, TTJ judged by J1 rather than the paid judge, 195 rows adjudicated by the executing
  agent, P3 rows never labelled, 87 rows blocked by the judge provider) are each flagged where they are used, and the
  87 blocked rows are bounded both ways in `results/recompute.json → blocked_row_bounds`.

## Restoring removed files

Nothing in this section is needed to **read** the results: every number lives in `results/`, `READOUT_v2.md`,
`labels/` and `eval_out.json`. These are only needed to **re-run** the pipeline. `./restore.sh` does the first two.

| path | why it is not here | how to restore |
|---|---|---|
| `.venv/` (9.0 GB) | regenerable Python environment | `./restore.sh`, or `uv venv .venv --python=3.12` followed by `uv pip install --python .venv/bin/python` with the pinned list in `pyproject.toml` |
| `src/__pycache__/`, `vendor/exp9/__pycache__/` | CPython bytecode caches | regenerated automatically on the next import — nothing to do; explicitly: `cd src && ../.venv/bin/python -c "import common, engine, readout"` |
| `work/j1_model/` (1.1 GB) | a reassembled copy of the **exp9** artifact's `judge_model/mdeberta_gemini_distill/model_parts/` shards, which are published with that artifact; it exceeded GitHub's 100 MB per-file limit | `./restore.sh`, or `cd src && ../.venv/bin/python -c "import ttj_judge_j1 as t; t.ensure_model()"`. `ensure_model()` refuses any checkpoint whose sha256 does not match exp9's manifest. **You only need it to regenerate** `work/ttj_j1_labels.jsonl`; that file (12,200 labels) **is shipped**, so the translate-then-judge arm and every number depending on it reproduce without this step. Verified regenerable in `results/restore_test.json`: sha256 matches and a class-balanced replay of 22 already-labelled rows reproduces 22/22 exactly. |
| NLLB weights | live in the shared HuggingFace cache outside this folder | `huggingface-cli download facebook/nllb-200-distilled-1.3B` — optional, since the translations are shipped in `work/ttj_translations.jsonl` |

Everything else is **kept** and ships as it is. In particular `labels/` (the $4.31 of paid judge labels and the per-row
readout table — not reproducible without spending again), `work/frame.parquet` (the 45,207-row frame every statistic is
keyed to), and `results/`, `adjudication/`, `figures/`, `READOUT_v2.md`, `protocol.yaml` and `amendments.jsonl`.
Kept files stay on the run's storage volume at their path inside this folder; the publish step skips any file of
100 MB or more, which is why `work/j1_model/` was removed rather than shipped.
