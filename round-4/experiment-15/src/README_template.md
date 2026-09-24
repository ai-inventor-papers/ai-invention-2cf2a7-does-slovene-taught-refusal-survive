# Dense dose ladder for the Slovene refusal lag (C-LAG), iter 4

**SCREEN-grade decomposition artifact.** An English-objective Heretic abliteration edit (iter-3 exp9 selected LoRA,
`E_exp9`) is applied to **GaMS3-12B-Instruct** (Slovene-adapted) and to its base family **Gemma-3-12B-IT**. The edit
strength λ is scaled continuously through a **13-step ladder** (λ = 0 plus 12 DEV-calibrated steps), and at every step
we measure English (EN-BT) and Slovene (SL-MT) refusal on the same 300 RefusEU-TRAIN harmful items and 120 content-matched
benign twins. The question is whether Slovene refusal falls *faster* than English refusal in GaMS than in Gemma at
matched English refusal (the **C-LAG** gap G3), and whether any such gap was created by the edit (**G3_edit**) or was
already present before it (**G3_orig**, the R-BASE rival).

> Every number below is filled in by `src/make_outputs.py` from `results/analysis.json`; `results/audit.json`
> re-derives the headline on an independent code path (`src/rederive.py`).

## Status at a glance

| | |
|---|---|
| Verdict (pre-registered rules) | **{{verdict}}** |
| Readout | **{{judge_primary}}**: the J1 fallback, **not** the pre-registered gemini-2.5-flash (the run's OpenRouter key hit its limit, amendment A4) |
| G3 (R coding, raw J1) | **{{G3_R}}**, 95% CI {{G3_R_ci95}}, MDE {{G3_R_mde}} ({{MDE_ratio_exp11}}× iter-3 exp11's 1.44) |
| G3_orig (λ = 0 margin difference) | {{G3_orig_R}}, 95% CI {{G3_orig_R_ci95}} |
| G3_edit = G3 − G3_orig | {{G3_edit_R}}, 95% CI {{G3_edit_R_ci95}}, 90% CI {{G3_edit_R_ci90}} |
| R-BASE supported? / LAG supported? / R-INCAP flag | {{R_BASE}} / {{LAG}} / {{R_INCAP}} |
| Support rule (steps in [0.2,0.5) / (0.5,0.8]) | Gemma {{support_gemma_it}}; GaMS {{support_gams3_it}} |
| Rows generated / OpenRouter spend | {{n_rows}} rows / ${{spend}} ({{n_paid_calls}} ledger rows) |

RESULTS_NARRATIVE_PLACEHOLDER

## Design (as frozen in `protocol.yaml` v0, with amendments in `results/protocol_amendments.json`)

* **Models**: `google/gemma-3-12b-it@96b6f1ec`, `cjvt/GaMS3-12B-Instruct@1d0b27af`; NF4 double-quant, bf16 compute,
  greedy decoding, **64 new tokens** (A0), official chat template with a single user turn.
* **Edit and dose**: exp9's selected Heretic LoRA per model (`selected/{model}/adapter`, r = 3, o_proj + down_proj,
  96 modules), applied as forward hooks `out += λ · B A x`. λ = 0 is bit-identical to the base model (max |Δlogit| = 0).
  The hook matches exp9's saved λ = 1.00 and λ = 0.50 adapters exactly (20/20 first-token argmax, Δlogit 0), which is
  logged in `results/check_{model}.json`.
* **Ladder**: a 9-point coarse grid on 100 DEV items (EN-BT). A logistic fit of EN refusal on λ is inverted at the
  targets 0.88 … 0.12 (λ ≤ 2.0). Step order is randomised. A support check on the BODY EN curve (x-axis only) would
  trigger up to 3 fill-in steps (A2).
* **Items**: a fresh RefusEU-TRAIN body disjoint from every earlier probe (`data/contamination_P400.json`); the
  EN-orig → SL-MT → EN-BT arms are NLLB-200-distilled-1.3B translations of one English source (chrF median 74.9, 7
  `mt_fragile` items, Slovene langid 100%). Benign twins were rewritten by gpt-4.1-mini with exp9's verbatim prompt and
  screened SAFE by gemini-2.5-flash-lite AND gpt-4.1-mini with token-Jaccard ≥ 0.3. The first 120 are all
  content-matched.
* **Random-direction control**: exp9's norm-matched random LoRAs (`rand_1`, `rand_2`, ‖ΔW‖ matched per module) at
  the ladder λ nearest EN 0.72 / 0.54 / 0.34 and at the maximum λ. This is **matched λ (edit size), not matched EN
  refusal**, because random edits do not lower EN refusal.
* **Statistics** (primary estimator copied from exp11 `stats_core`):
  * per model, a binomial GLM `k_SL,s ~ Bin(n_s, expit(a_m + b_m·logit p_EN,s))` over the λ > 0 steps, with
    G3 = a_GaMS − a_Gemma;
  * G3_orig = difference of the λ = 0 margins M = logit p_SL − logit p_EN (Hautus), and G3_edit = G3 − G3_orig in the
    same bootstrap draw;
  * 2,000 bootstrap draws resampling items as clusters jointly for both models (paired) and steps within model;
  * readouts: Rogan-Gladen and a PPI++-style per-cell rectifier (Se/Sp and the rectifier from the blind adjudication),
    the integrated gap IG over EN ∈ [0.2, 0.8], the isotonic SL rate at EN 50%, SDT d′ / c per step, a GEE, and
    within-item model-swap and language-swap placebos.

## Departures from the plan (each logged before the work it affects)

| id | departure | why | cost |
|---|---|---|---|
| A0 | 64 instead of 128 new tokens | measured L4 throughput (~2 rows/s at 128 tokens in exp11) could not fit the design; 64 makes the frozen P1 wording ("truncated at 64 tokens") literally true | late refusals and partials after token 64 are missed; absolute rates are not comparable with exp11 |
| A1 | judge tier = gemini-2.5-flash | the frozen tier rule failed all three flash-lite conditions (kappa(lite, gpt) < 0.6 in edited cells; Sp(lite) < 0.8; kappa(lite, archived flash) = 0.31) | ~3× cost, so the flash budget rule applied (random arm harmful-only; TTJ at 4 window steps + λ0 + max λ) |
| A1 | harmful 400 → 300, twins 200 → 120, replication (E_iter1) dropped, DEV fine grid skipped | throughput gate, following the pre-registered cut order | power; no within-run replication |
| A1 | BODY drawn before DEV in the category round-robin | so the rare categories (S4/S6/S7/S8/S13) are in the body rather than in the calibration-only DEV set | none for the estimand |
| A4 | **readout = J1** (exp9's gemini-distilled mdeberta classifier), not paid gemini-2.5-flash; no gpt-4.1-mini second family; no paid ASR rubric | **the run's OpenRouter key reached its $12.00 limit at 19:05 UTC** ($0.199 left) after this artifact had spent $0.28 | J1 is a *fallback readout*: it is validated against real flash labels on this artifact's rows and against the blind adjudication, but under F3 the verdict cannot be promoted beyond ESTIMATE on it |
| A4 | adjudication by the executing agent (author model, **not a human**): {{adj_n}} blind rows, drawn per model | no native Slovene annotator is available | Se/Sp are "reference-model corrected" and could share the judges' blind spots |

## Human input needed (flagged, not done)

* A **native Slovene annotator** to adjudicate a sample of SL-edited rows. Every correction here is anchored to an
  LLM (author-model) reference.
* **OpenRouter budget** (~$3.5) to run the pre-registered paid readout (`finalize.sh`) on the saved generations. All
  generations are on disk; nothing needs to be regenerated.

## Layout

| path | what |
|---|---|
| `protocol.yaml`, `protocol.sha256` | frozen protocol v0 (committed before any BODY row) |
| `results/protocol_amendments.json` | A0–A4 with timestamps and evidence |
| `src/common.py` | constants, P1 judge prompt (sha 97332090…), lexicon, helpers |
| `src/build_items.py` | S1 items: exclusions, round-robin draw, twins (paid rewrite + SAFE screen), NLLB MT/BT + QA |
| `src/gen.py` | S4–S6 GPU: NF4 load, hook LoRA with λ scaling, identity checks, DEV calibration, ladder, fill-in, random arm, KL |
| `src/judge_paid.py`, `src/orclient.py` | OpenRouter calls with a hard-capped ledger: tier selection, flash labels, (finalize) second family / TTJ / ASR |
| `src/judge_local.py` | J1 fallback readout (exp9 checkpoint reassembled in memory, sha-checked) |
| `src/ttj.py` | translate-then-judge: NLLB SL→EN of SL responses |
| `src/adjudicate.py` | blind draw / unblind for the author-model adjudication |
| `src/analysis.py`, `src/stats_core.py` | every pre-registered statistic → `results/analysis.json`, `results/gates.json` |
| `src/rederive.py` | independent audit → `results/audit.json` |
| `src/figures.py`, `src/make_outputs.py` | figures, RESULTS.md, README.md, method_out.json |
| `tests/test_stats.py` | unit tests (Hautus, RG, kappa vs sklearn, G3 recovery, R-BASE synthetic, SDT, PPI, bootstrap coverage, placebo) |
| `data/items.jsonl`, `data/split_manifest.json`, `data/contamination_P400.json` | items and provenance (sha256 per file) |
| `results/gens/{model}.jsonl` | every generation (row_id = sha1(item\|model\|edit\|arm\|λ)) |
| `results/labels/` | J1, flash (DEV + validation subsample), calibration-set labels, TTJ labels |
| `results/rows_final.jsonl` | one row per generation with all labels (shared SPEC) |
| `results/adjudication/` | blind files, author labels, unblinded join, timestamps |
| `RESULTS.md` | auto-generated tables |
| `figures/fig1..fig5.{pdf,png}` | SL vs EN per step; margin (R-BASE) with random arm; SDT; G3 forest; judge Se/Sp |
| `method_out.json` (+ mini/preview) | exp_gen_sol_out: per item × arm, the J1 label at every model × λ |

## How to run

```bash
uv sync                                    # pinned deps (pyproject.toml + uv.lock)
uv run pytest -q tests                     # T0 unit tests
cd src
../.venv/bin/python build_items.py --stages pool,twins,mt      # S1 (twins stage is paid)
../.venv/bin/python judge_paid.py tier                         # S3 (paid)
cd .. && ./run_gen_all.sh                                      # S4-S6 both models (GPU, ~3 h on an L4)
cd src && ../.venv/bin/python judge_local.py once --device cuda && ../.venv/bin/python judge_local.py ttj --device cuda
../.venv/bin/python ttj.py --judge local/j1
../.venv/bin/python adjudicate.py draw --model gemma_it --judge_short j1   # then label blind_*.jsonl, then: adjudicate.py unblind
../.venv/bin/python analysis.py && ../.venv/bin/python rederive.py && ../.venv/bin/python figures.py && ../.venv/bin/python make_outputs.py
# with OpenRouter budget: ../finalize.sh runs the pre-registered paid readout on the same generations
```

## Restoring removed files

| path | restore with |
|---|---|
| `.venv/` | `uv sync` (pinned by `uv.lock`) |
| `src/__pycache__/`, `tests/__pycache__/`, `.pytest_cache/` | regenerated automatically on the next `uv run ...` / `uv run pytest -q tests` |
| model weights (not stored here; shared HF cache) | `hf download google/gemma-3-12b-it --revision 96b6f1eccf38110c56df3a15bffe176da04bfd80`; `hf download cjvt/GaMS3-12B-Instruct --revision 1d0b27af5748784482600d24779409e7e1dc9adc`; `hf download facebook/nllb-200-distilled-1.3B` |
| edits and J1 (read-only inputs, not copied) | iter-3 exp9 `selected/{model}/adapter`, `adapters/{model}/rand_*`, `judge_model/mdeberta_gemini_distill/model_parts` on the run volume |

Nothing in this workspace is large: results, data, figures and logs are text and are kept.
