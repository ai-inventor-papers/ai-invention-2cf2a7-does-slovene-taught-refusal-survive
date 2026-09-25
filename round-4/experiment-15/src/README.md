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
| Verdict (pre-registered rules) | **ESTIMATE** |
| Readout | **local/j1**: the J1 fallback, **not** the pre-registered gemini-2.5-flash (the run's OpenRouter key hit its limit, amendment A4) |
| G3 (R coding, raw J1) | **-0.70**, 95% CI [-1.01, -0.42], MDE 0.42 (0.29× iter-3 exp11's 1.44) |
| G3_orig (λ = 0 margin difference) | -1.17, 95% CI [-2.83, 0.22] |
| G3_edit = G3 − G3_orig | 0.47, 95% CI [-0.96, 2.14], 90% CI [-0.68, 1.91] |
| R-BASE supported? / LAG supported? / R-INCAP flag | True / False / False |
| Support rule (steps in [0.2,0.5) / (0.5,0.8]) | Gemma 5 / 5 (PASS); GaMS 5 / 5 (PASS) |
| Rows generated / OpenRouter spend | 33888 rows / $0.279 (12866 ledger rows) |

**What we find (raw J1 readout).** Across the 14-step ladder, the Slovene refusal gap is G3 = -0.70 log-odds (95% CI [-1.01, -0.42]); the achieved MDE is 0.42, about 0.29x iter-3 exp11's 1.44, so this artifact is the most powerful estimate of the gap so far. The decomposition splits it into a pre-edit component G3_orig = -1.17 [-2.83, 0.22] (the models' Slovene-minus-English margin already differs at lambda 0) and an edit-induced component G3_edit = 0.47 [-0.96, 2.14].

**The readout caveat that dominates the verdict.** Because the run's OpenRouter key hit its limit (A4), the full-coverage readout is the J1 fallback, not the pre-registered gemini-2.5-flash. On the 60+60 blind author-model adjudicated SL-edited rows, J1's specificity is 0.62 (GaMS) / 0.55 (Gemma) - below the pre-registered 0.80 gate (FAIL): J1 systematically over-calls REFUSE in edited Slovene, exactly the language-asymmetric readout error the R-JUDGE rival predicts. We therefore report the Rogan-Gladen and PPI-corrected headlines beside the raw one: RG G3 = -0.01 [-4.36, 11.27], PPI G3 = -0.75 [-2.43, 0.99].

**Rivals.** R-BASE (the lag is a pre-edit offset carried along a parallel curve): True - G3_edit's 90% CI is [-0.68, 1.91] (bound |G3_edit| < 1.91); per-model slopes b are 0.94 (Gemma) and 0.80 (GaMS). Translate-then-judge G3_TTJ = -0.79 [-1.09, -0.48]. The norm-matched random-direction control leaves the English refusal essentially unchanged (see fig2 / the random-arm table), separating a directed edit effect from generic perturbation.

**Headline: the lag is a BASELINE property, not made by the edit (R-BASE supported: True).** The raw Slovene lag is real and well-powered (G3 = -0.70, CI excludes 0; model-swap placebo p = 0.000; it persists under translate-then-judge, G3_TTJ = -0.79 [-1.09, -0.48]), so it is not merely a judge-language artifact. But the edit-induced component G3_edit is 0.47 with its 95% CI [-0.96, 2.14] spanning 0 (bound |G3_edit| < 1.91 at 90%), while the pre-edit offset G3_orig = -1.17 carries essentially the whole gap and both slopes b are ~1 (0.94, 0.80): the English abliteration edit does NOT open a Slovene-specific hole; GaMS simply starts and stays closer to English-Slovene parity than Gemma does. This answers the iteration's central question in the R-BASE direction and bounds the edit-induced C-LAG effect near 0.

**Verdict: ESTIMATE (SCREEN-grade).** LAG_SCREEN_SUPPORTED is not met: the readout is the non-validated J1 fallback and its SL-edited specificity fails the 0.80 gate (FAIL); the Rogan-Gladen correction is near its identifiability threshold here so its CI is uninformative (G3_RG = -0.01 [-4.36, 11.27]), and the PPI estimate -0.75 [-2.43, 0.99] has a CI that includes 0. The honest deliverables are (i) the bounded R-BASE result above, (ii) the first scored norm-matched random control for BOTH models, and (iii) 33,888 saved generations ready for the pre-registered paid readout (finalize.sh), which would lift this from ESTIMATE toward a decision.

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
| A4 | adjudication by the executing agent (author model, **not a human**): 240 blind rows, drawn per model | no native Slovene annotator is available | Se/Sp are "reference-model corrected" and could share the judges' blind spots |

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
