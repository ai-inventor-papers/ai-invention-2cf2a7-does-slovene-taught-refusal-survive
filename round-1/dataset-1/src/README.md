# Reserved test sets and re-audited safety dose (GaMS3 vs Gemma-3, run_FVi3e3O9CH5I, iter 1)

This workspace builds the **confirmation-only (reserved) inputs** and the **audited supervision-dose covariate** for the study of bilingual (EN/SL) refusal in GaMS3-12B-Instruct vs Gemma-3-12B-IT.

- Workspace (absolute): `/ai-inventor/aii_data/runs/run_FVi3e3O9CH5I/3_invention_loop/iter_1/gen_art/gen_art_dataset_1`
- Main deliverable: `full_data_out.json` (exp_sel_data_out schema, validated; 35 MB, below the 100 MB split limit).
- `mini_data_out.json`: from the aii-json format script, 3 examples in every block.
- `preview_data_out.json`: written by `data.py`, 3 examples per block with strings truncated to 200 chars. The aii-json script's preview kept only the first 3 of the 8 blocks, so it was not used.
- Total OpenRouter spend: **$9.286 of the $9.50 cap** (`ledger/summary.json`; 14,450 calls, every call logged in `ledger/ledger.jsonl`).

> **RESERVED-USE RULE.** Do not use these items in iter-1 screens, prompt tuning or any model generation:
> - the RefusEU evaluation split (`refuseu_eval_*`);
> - the identity/control items (`identity_confirm_*`, ids in `outputs/identity_items_ids.json`);
> - `refuseu_x_*`.
>
> No study model (GaMS3 / Gemma-3) has generated on them. DEV folds (100 RefusEU pairs, 40+40 identity items, 30% of HARD) may be used only for protocol freezing, never for FINAL claims. Sibling screens must verify disjointness against `outputs/identity_items_ids.json` and `outputs/split_manifest.json`.

## What is in `full_data_out.json`: 8 dataset blocks, 15,647 examples

| block | rows | input → output | folds |
|---|---|---|---|
| `refuseu_eval` | 2,800 (1,400 pairs × EN/SL) | prompt → blind per-language hazard label `item_label` (S1–S14) | `refuseu_eval_DEV` (100 pairs), `refuseu_eval_FINAL` (1,300 pairs) |
| `refuseu_gold_calib` | 590 (RefusEU lang_*/test 141+141; 154 train pairs × 2) | prompt → GOLD category | `refuseu_gold_calib` |
| `gams_dose_rows` | 6,239 | SFT user turn → `consensus_response_type\|hazard(eval taxonomy)` | `dose_row` |
| `hard_xstest` | 900 (450 × EN/SL) | prompt → majority S label | `hard_DEV` / `hard_FINAL` / `hard_dropped_mt` |
| `hard_orbench_hard1k` | 2,638 (1,319 × 2) | same | same |
| `hard_orbench_toxic300` | 600 (300 × 2) | same | same |
| `identity_confirm` | 480 (240 items × EN/SL) | question → `identity` / `control` | `identity_confirm_DEV` (40+40), `identity_confirm_FINAL` (80+80) |
| `refuseu_x_mt` | 1,400 | NLLB MT of each EN eval prompt → inherited EN `item_label` | `refuseu_x_DEV`, `refuseu_x_FINAL`, `refuseu_x_dropped_mt` |

Every example carries all raw votes, runner-ups, confidences, flags and provenance as flat `metadata_*` fields.

## Key findings

### 1. RefusEU EN/SL items that share a row_id are NOT translations
This corrects the hypothesis wording "EN and SL are DeepL translations". See `outputs/refuseu_correspondence.json`.

- **LaBSE cosine.** Same-row_id eval pairs average **0.553**, against 0.914 for MT pairs and 0.394 for shuffled pairs.
- **Correspondence grades.** No pair (0/1,400) reaches the translation threshold (grade T: cosine ≥ 0.872, the 5th percentile of the MT reference). 792 pairs are S (same topic) and 608 are U.
- **Gold comparison.** Gold EN/SL position pairs, which share the gold category by construction, average 0.547, i.e. the same as the eval pairs. Shuffled gold pairs of the same category average only 0.444. So eval pairs behave like same-category, same-style per-language generations.
- **Label agreement.** EN vs SL `item_label` agrees on 76.1% of eval pairs, against 83.7% on gold test pairs (known same category).

Consequences:
- Labels are **primary per language item**. Pair-level labels are secondary.
- Within-model SL−EN contrasts are **not item-matched**. Use `refuseu_x_mt` for item-matched contrasts, since no grade-T pairs exist.
- The cross-model DiD, [GaMS(SL−EN) − Gemma(SL−EN)], needs no translation matching, because both models see identical EN and SL sets.

### 2. Blind hazard labels on the eval split, calibrated on gold
See `outputs/labeller_calibration.json` and `outputs/refuseu_eval_label_report.json`.

**Labellers.**
- openai/gpt-4.1-mini (F1) and google/gemini-2.5-flash (F2, reasoning off): temperature 0, one item per request, prompt text only.
- The Stage-0b TF-IDF classifier, retrained on RefusEU lang_*/train. It reproduces CV .901 EN / .844 SL, with gold test accuracy .887 / .865.
- Llama-Guard-3-8B as an extra vote, run locally in bf16.

**Frozen prompt.** The prompt was adapted to RefusEU's *operationalisation* of the taxonomy, based on gold TRAIN items only; eval was never looked at.
- In the benchmark, S14 means hacking or malicious code in general, S6 means specialist how-to (e.g. home drug synthesis), and S13 means election rigging or disinformation.
- The literal Llama-Guard wording is kept as `prompts/hazard_label_v0_llamaguard_literal.txt`. It was never used.

**Calibration gate.**
- v1 gold accuracy was below 0.70 in SL for both families (gpt .709/.627, gem .702/.620, EN/SL).
- One revision (v2) added one gold-train example per category, raising accuracy to gpt .732/.631 and gem .722/.675.
- v2 is frozen for both families. No further tuning was done.

**Accuracy of the aggregated `item_label` on gold test items.**
- Majority of the 3 core votes: **.759 EN / .716 SL**.
- On `item_pure` items only: **.947 / .941** (67% / 60% of test items are pure).
- Low/high-EN *group* accuracy: .858 / .830.

**Agreement.**
- Cohen κ gpt vs gemini: **.879 EN / .830 SL**, meeting the ≥ 0.6 target.
- Fleiss κ over the 3 core votes: .731 / .642.
- Fleiss κ over the 5 pair-level core votes: .706.
- `item_pure` share: .647 EN / .534 SL, **below the 0.70 target**.

**Category counts.** The paper designs 100 per category. The counts deviate (χ² p ≈ 1e-40):
- S6, S9, S12 and S3 are under-counted (e.g. S9 has 30 in EN), and S2 and S1 are over-counted.
- This is plan failure scenario (2): `item_balanced_label` is a linear assignment at exactly 100 per category per language, and agrees with the majority label on 83.5% of EN items.
- Downstream must run D on pure items as a sensitivity analysis. Blind-label error (~24–28%) **dilutes D toward 0**, which is the direction of the main claim.

**Pure FINAL items in S5/S7/S8/S13.**
- EN: 95 / 74 / 76 / 90.
- SL: 61 / 71 / **50** / 88. SL S8 is below 60 (scenario 3), so pool the low-EN group.

Using the relabelled groups in `outputs/frozen_groups.json`, the pure FINAL low-EN item counts are 332 EN and 308 SL.

**Other checks.**
- `refuseu_overlap_recheck.json` reproduces Stage-0b: at most 3 exact and at most 9 near-duplicates between gold and eval.
- There is 0 contamination of eval items against GaMS-Nemotron-Chat (`outputs/contamination_report.json`).

### 3. Supervision dose, re-labelled by two families with a tiebreak
See `outputs/dose_table.json` and `outputs/frozen_groups.json`.

**Rows.**
- The 3,959 regex-flagged rows are only **3,157 unique conversation_ids**. The 1,439 duplicate ids in GaMS-Nemotron-Chat are exact copies, and **802 of them are flagged refusals**; one refusal appears 191 times. Each row keeps its `multiplicity`, and the table also reports copy-weighted shares.
- Samples: 1,000 SRS rows per language (including 299/300 Stage-0 rows), plus a keyword-stratum oversample (EN 181, i.e. a census of the stratum; SL 400).
- 501 GaMS-Instruct-SAFE 0.5 rows.

**Labels.** gpt and gemini label 5 rows per request.
- The batched-vs-unbatched check (200 rows) kept batching: response_type agreement .945 (gpt) and .959 (gem).
- llama-3.3-70b broke ties on 928 rows (14.9%).
- κ gpt vs gemini on safety_refusal (binary): .949 EN / .918 SL.
- κ against the Stage-0 gemini labels: .91–.94.

**Taxonomy harmonisation (a deviation from the plan).**
- The plan's dose prompt used the literal Llama-Guard wording (hacking goes to S2). The eval labels use the RefusEU operationalisation (hacking goes to S14). Group assignments must live in one category space.
- All 3,433 rows that any family called safety_refusal or compliance_on_hazard were re-labelled for hazard with the **same frozen eval labeller and prompt** (gpt-4.1-mini, v2), from the user turn only. 3,344 rows were done this way; 89 fall back to TF-IDF.
- The primary `per_category` table uses this eval taxonomy. `per_category_literal` is kept for transparency only.

**Pre-registered 0.10 group rule, applied to point estimates of the primary table.**
- S2 moves high→low (EN share .075, because hacking now falls in S14).
- S1 moves intermediate→high (.291).
- S8 moves low→high (.118, but this rests on only **8 EN vs 60 SL** rows).
- Final groups: **low-EN S2/S5/S7/S13**; high-EN S1/S3/S4/S8/S9/S10/S11/S14; intermediate S6/S12.

**Uncertainty.**
- 13 of 14 categories are `dose_uncertain`: their propagated interval straddles 0.10. The Wilson upper bound on the huge unflagged no-hit strata (N ≈ 17k EN / 76k SL, n ≈ 1,000) dominates the upper bounds.
- Overall EN share of safety-refusal supervision is **0.178**, with interval [0.055, 0.452].
- The upper bound is ≥ 0.40, so the "Slovene-dominant" wording is **not** licensed by the 0.40 rule.
- The census-only counts (`census_only_en_sl_point`) are the least model-dependent numbers, e.g. S13 0 EN / 5 SL, S7 4 / 72, S5 10 / 51, S2 19 / 234.
- Dose estimates the **released** mix (97,915 rows; 96,476 after dedup), not proven checkpoint exposure (88,126 rows per the model card). No developer was consulted.

### 4. HARD set (XSTest, OR-Bench hard-1k, OR-Bench toxic-300)
See `outputs/hard_mt_report.json`.

**MT.**
- Forward MT: gemini-2.5-flash. Back-translation: gpt-4.1-mini (a different family).
- Median chrF: 79.2 (NLLB-1.3B round trip, kept in `nllb_*` columns: 69.2).
- 11 items stay below 40 after one retry and go to fold `hard_dropped_mt`. No MT refusals.
- 250 XSTest items carry `mt_fragile` (homonym, figurative, safe-target, safe-context and definition types, plus their contrast twins). Example: gemini kept "ubijem proces" (kill a process), whereas NLLB rendered it "uničim" (destroy).

**Labels, reduced by plan failure scenario 7** (spend > $8 before step C).
- Core votes are GPT-EN, GPT-SL, TF-IDF-EN and TF-IDF-SL, plus Llama-Guard-3 EN/SL as extras. **GEM-EN was skipped.**
- `pure` means at most one dissent among the available core votes, with ≥ 3 votes. The pure share is only 0.45.
- Category labels of **benign** items are weak, because TF-IDF is out of domain there. For benign items, prefer `metadata_vote_f1_en`.

**Other.**
- Llama-Guard unsafe rates behave as expected: XSTest-safe 2.8% EN / 8.0% SL; XSTest-unsafe .82 / .71; OR-toxic .83 / .71; OR-hard .19 / .24.
- Split: 30% DEV / 70% FINAL by sha1(item_id) within source × is_harmful.
- Contamination: 1 EN and 4 SL items overlap Nemotron prompts (flagged per item).

### 5. Identity confirmation items
See `outputs/identity_report.json` and `outputs/identity_items_ids.json`.

- **Composition.** 120 identity items (20 per facet: name, creator/company, model family, who-made-you, origin/language, comparison) and 120 personal-question controls.
- **Sources.** Real OASST2 phrasings where usable: 7 identity and 10 control items (OASST2 has no Slovene prompts). The rest are gpt-4.1-mini paraphrases (T 0.7, seed 20260923).
- **Comparison facet.** Names GaMS and Gemma in counterbalanced order (10 GaMS-first, 10 Gemma-first). No other item names a product, company or country.
- **Length matching.** Controls are matched 1:1 on length; 77.5% fall within ±30% of the word count.
- **MT.** gemini translates into informal ti-form Slovene and gpt back-translates; median chrF 76.3, minimum 40.3.
- **Overlap.** 0 n-gram overlap with the EN and SL Nemotron prompts, including the 694 SL identity rows.

## Honest limitations (reduced scope)
- **No native-speaker audit.** All SL HARD, identity and RefusEU-X items are machine-translated and **not human-verified**. Round-trip chrF only loosely measures meaning.
- **Blind LLM labels.** The eval-split categories are blind LLM labels, not gold. Their error is calibrated above and dilutes D toward 0.
- **PolyGuard not run.** COMET-QE was skipped (Unbabel/wmt22-cometkiwi-da is not accessible).
- **HARD reduced.** HARD labels use a reduced vote set (scenario 7).
- **Llama-Guard as a category labeller.** Weak on this benchmark's operationalisation: gold accuracy .631 EN / .479 SL.
- **GaMS-Instruct not scanned.** The optional regex scan (plan 6d) was **not run**, because the repo is gated with manual approval.
- **RefusEU-X MT source.** RefusEU-X uses the local NLLB-1.3B / opus-mt round trip (median chrF 74.0; 6 items below 40 dropped), not gemini. It was optional, and the plan's spend gate (< $6.5 after step 6) was not met.
- **Budget deviations.** Documented in `ledger/summary.json`:
  - A slightly exceeded its sub-cap ($2.78 vs 2.6).
  - B was raised to $4.3.
  - About $0.8 was wasted on gpt HARD batch retries before validation was made lenient.
- **Execution history.**
  - At module start the shared OpenRouter key was exhausted.
  - Local fallbacks (NLLB MT, a local-vLLM labeller) were prepared. vLLM could not run (no C compiler for Triton), and no local-LLM labels were produced.
  - After a restart the key worked, and every LLM label in the deliverable comes from the plan's OpenRouter models.
  - Unused weights (Qwen2.5-14B-AWQ, Llama-3.1-8B, salamandra-7b) were pre-fetched into the run's shared HF cache and can be removed by the run owner.

## Layout

**Top level**
- `data.py`: final assembly (uv inline script). Aggregates all votes, runs the calibration metrics, balanced assignment, pair labels, dose table, group rule and contamination merge, freezes the labels in `split_manifest.json`, and writes `full/mini/preview_data_out.json`.
- `pyproject.toml`: every one of the 165 installed packages pinned exactly (`uv pip freeze`).
- `requirements.lock.txt`: the same freeze.
- Key pins: torch 2.7.1, transformers 4.56.2, sentence-transformers 6.1.0, sacrebleu 2.6.0, pandas 3.0.6.
- vLLM was uninstalled because it was not used by any deliverable step.

**`lib/`**
- `common.py`: paths, hashing, Wilson intervals, kappa.
- `ledger.py`: cost ledger with caps.
- `judge.py`: async OpenRouter client with resumable caches.
- `api_mt.py`: gemini/gpt MT round trip.
- `mt.py`: NLLB / opus-mt local MT and chrF.

**`scripts/`**, in run order:
- `s0_env_ledger.py`, `s0_fetch_models.py`: environment record and model pre-fetch.
- `s1_download.py`: pinned downloads, writes `outputs/provenance.json`.
- `s2_prepare.py`: item tables; freezes the hash-only folds in `outputs/split_manifest.json` **before any labelling**.
- `s3_tfidf.py`: TF-IDF vote.
- `s4_mt.py`: local NLLB MT for HARD, RefusEU-X and the 50 gold MT references.
- `s4b_hard_api_mt.py`: gemini/gpt MT for HARD.
- `s5_correspondence.py`: LaBSE correspondence check.
- `s6_llamaguard.py`: Llama-Guard-3 votes.
- `s7_smoke.py`: 5-call price smoke test.
- `s7_api_label.py {calib,eval,dose,tiebreak,hard}`: LLM labels.
- `s7b_dose_hazard_harmonise.py`: taxonomy harmonisation of dose hazards.
- `s8a_identity_gen.py`, `s8b_identity_finalize.py`: identity set.
- `s11_contamination.py`: contamination flags.
- `s12_ledger_summary.py`: ledger summary.

**`prompts/`** (sha256 recorded in `split_manifest.json`)
- `hazard_label_v1.txt`: frozen base.
- `hazard_label_v2_{gpt,gem}.txt`: the versions actually used.
- `hazard_label_v2h_gpt.txt`: HARD variant.
- `dose_label_v1.txt`.
- `hazard_keywords_v1.json`: keyword lexicon, frozen before labelling.

**`labels/`**
- Every raw API response, as resumable JSONL caches that make every label reproducible without re-calling: `*_calib_v*.jsonl`, `*_eval.jsonl`, `*_dose_*.jsonl`, `llama70_dose.jsonl`, `gpt_hard*.jsonl`, `gpt_dose_hazard_harmonise.jsonl`, `hard_mt_*.jsonl`, `identity_*.jsonl`.
- `tfidf_votes.parquet`, `llamaguard3_*`.
- `refuseu_eval_labels_frozen.parquet`.

**`outputs/`**
- `split_manifest.json`, `labeller_calibration.json`, `refuseu_eval_label_report.json`, `refuseu_correspondence.json`.
- `dose_table.json`, `frozen_groups.json`, `dose_sampling_frame.json`.
- `hard_mt_report.json`, `identity_report.json`, `identity_items_ids.json`.
- `contamination_report.json`, `tfidf_report.json`, `refuseu_overlap_recheck.json`.
- `provenance.json`, `dataset_selection.json`: 25 candidates with keep/discard reasons.

**Other directories**
- `work/`: intermediate parquet tables (items, MT outputs, identity pool, correspondence, contamination).
- `ledger/`: `ledger.jsonl`, `summary.json`, `prices.json`.
- `logs/`: all run logs and `env.json`.

## Provenance
All sources are pinned; sha256 values are in `outputs/provenance.json`.

| source | revision | licence |
|---|---|---|
| NASK-PIB/RefusEU | 5523ce30b9 (= HEAD, matches the hypothesis pin) | card: llama3.1 tag, "to be specified" → **flagged, research use only** |
| cjvt/GaMS-Nemotron-Chat | 0eab0b3cfc | none stated on card → research use |
| GaMS-Instruct-SAFE 0.5 | CLARIN.SI hdl 11356/2218 (copied from Stage-0) | CC BY-SA 4.0 |
| Paul/XSTest | f600c994b2 | CC-BY-4.0 |
| bench-llm/or-bench | e36d8b80e8 | CC-BY-4.0 |
| OpenAssistant/oasst2 | 179dd21fc5 | Apache-2.0 |

Reference-only downloads, not in the deliverable: MultiJail, do-not-answer, JBB-Behaviors, Aegis-2.0 test, aya_redteaming, xstest-v2-copy.

## How to run
```bash
uv venv .venv --python=3.12 && uv pip install --python .venv/bin/python -r requirements.lock.txt
.venv/bin/python scripts/s1_download.py && .venv/bin/python scripts/s2_prepare.py && .venv/bin/python scripts/s3_tfidf.py
.venv/bin/python scripts/s4_mt.py && .venv/bin/python scripts/s5_correspondence.py
.venv/bin/python scripts/s7_api_label.py calib   # then: eval, dose, tiebreak, hard (all cached -> $0 on re-run)
.venv/bin/python scripts/s4b_hard_api_mt.py && .venv/bin/python scripts/s6_llamaguard.py && .venv/bin/python scripts/s3_tfidf.py
.venv/bin/python scripts/s8a_identity_gen.py && .venv/bin/python scripts/s8b_identity_finalize.py
.venv/bin/python scripts/s7b_dose_hazard_harmonise.py && .venv/bin/python scripts/s11_contamination.py
uv run data.py        # or .venv/bin/python data.py
```
Because `labels/*.jsonl` holds every response, re-running any API step replays from cache at $0.

## Restoring removed files
- `.venv/` (regenerable):
  ```bash
  uv venv .venv --python=3.12 && uv pip install --python .venv/bin/python -r requirements.lock.txt
  ```
- `temp/datasets/` (redownloadable):
  ```bash
  .venv/bin/python scripts/s1_download.py
  ```
  This re-downloads every HF source at the pinned revision and re-copies GaMS-Instruct-SAFE 0.5 from `iter_2/gen_hypo/claude_agent/stage0/safe05/`, or from CLARIN.SI hdl 11356/2218.
- `work/nemotron_prompts.parquet` (regenerable):
  ```bash
  .venv/bin/python scripts/s2_prepare.py
  ```
  This needs `temp/datasets/`. **Caution:** it also rewrites `outputs/split_manifest.json` (same hash-only folds); re-run `data.py` afterwards to re-attach the label freeze.
- `lib/__pycache__/` (regenerable): Python bytecode, recreated automatically the next time any script imports `lib`. To force it:
  ```bash
  .venv/bin/python -c "import lib.common"
  ```
