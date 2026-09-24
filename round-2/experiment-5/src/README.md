# Confirming Slovene vs English refusal on held-out items (GaMS3-12B-Instruct vs Gemma-3-12B-IT)

This is the iter-2 confirmation run of the GaMS3 vs Gemma-3 study (CONFIRM-SPEC v2, seed 20260924). It runs on the RESERVED
FINAL splits of the iter-1 dataset artifact `art_EG6OpEkGvysx`
(`/ai-inventor/aii_data/runs/run_FVi3e3O9CH5I/3_invention_loop/iter_1/gen_art/gen_art_dataset_1`). No earlier step had
touched those splits. In the user's research plan, this is the behavioural core for the two ORIGINAL checkpoints
(GEMMA-I and GAMS-I) on held-out RefusEU EN/SL, plus an over-refusal contrast set. Abliteration (Heretic) and the
mechanistic work are carried out in sibling artifacts.

- **Method model:** `cjvt/GaMS3-12B-Instruct` @ `1d0b27af`. This is Gemma-3-12B continued-pretrained and SFT'd for
  Slovene, including a small Slovene GaMS-Safety set.
- **Baseline / control:** `google/gemma-3-12b-it` @ `96b6f1ec`.
- **Held identical for both models:** NF4 4-bit weights (bitsandbytes, double quantisation, bf16 compute), greedy decoding,
  160 new tokens, an empty system turn, and the same Gemma-3 chat template. The rendered templates were verified
  byte-identical: `<bos><start_of_turn>user\n…<end_of_turn>\n<start_of_turn>model\n`, with EOS ids [1, 106].

## Results at a glance (FINAL, sealed; every number is recomputed in `results/analysis_final.json`; audit 27/27)

> **Read this first: the judge was substituted.** The run's shared OpenRouter budget ran out partway through FINAL
> judging (deviation D5). The pre-registered primary judge was gemini-2.5-flash. It was replaced for **all** FINAL
> refusal rows, both models, by the frozen-prompt local **Qwen3-14B** judge, and FINAL identity uses the regex
> self-name detector. Everything below is labelled with the judge that produced it. Positive contrasts = a GaMS
> Slovene refusal SURPLUS relative to Gemma. DiD values are log-odds; d′ and c are in z units.

Pre-registered margins (DEV addendum, gemini labels): m = 0.508, m_id = 0.402, m_d′ = 0.166, m_c = 0.083. The ceiling
rule fired (p0 = .91). By the pre-registered MDE rule (MDE ≤ 2m), only **DiD_ref** (MDE 0.59) and **DiD_ref^MT**
(MDE 0.83) are powered. D, D^MT, DiD_id, DiD_d′, DiD_c and D_d′ are "estimate only".

| Claim | Pre-registered verdict | Estimate [95% CI] | Status |
|---|---|---|---|
| **C1 identity anchoring** (GaMS names itself more in SL than EN, relative to Gemma) | **PASS** | DiD_id = 3.46 [2.55, 4.62]; control items 0 | Confirmed on reserved items. GaMS own-name rate is 90% in SL vs 33% in EN. GaMS credits Qwen/Alibaba in 51% of EN identity answers (iter 1: 42%). The readout is the regex detector (DEV κ vs gemini 1.0 for GaMS, .82 for Gemma) |
| **C2 dose contrast D** (RefusEU natural) | **INCONCLUSIVE** (MDE 1.36 > 2m) | D = −0.27 [−1.31, 0.71] | No support for ALT-1 (a dose-dependent "supervised reach"). The point estimate has the wrong sign for ALT-1. Misclassification-corrected D = −0.47; pooled with iter 1, D = −0.54 [−1.18, 0.10] |
| **C2 overall DiD_ref** (RefusEU natural, 1,300 pairs) | Powered. No branch fires: not MAIN (the 90% CI [−0.76, 0.05] leaves the ±m band) and not DEFICIT (the estimate is above −m) | −0.35 [−0.81, 0.13]; about −2.8 pp absolute | **Judge-dependent.** gemini on the 607 gemini-labelled pairs: −0.63 [−1.14, −0.16]. Qwen3 on the same 607 pairs: +0.03 [−0.75, 0.82]. Calibrated to the gemini scale: −1.21 [−2.47, −0.05]. DEV, gemini: −1.79 [−3.27, −0.85]. Iter 1 (gemini, 64 tokens): −0.38 [−0.72, −0.05]. The direction is a GaMS Slovene **deficit**, not a surplus; its size depends on the judge |
| **Item-matched DiD_ref^MT** (SL_MT vs EN_BT, same content) | Powered sensitivity | −1.67 [−2.75, −1.03]; about −2.5 pp absolute | Driven by **Gemma** refusing more in Slovene (97.5% → 99.5%, McNemar p = 3e-6). GaMS is flat (97.2% → 96.8%, p = .43). Calibrated: −2.03 [−3.83, −0.34]. DEV, gemini: −0.91 [−2.63, 0.73]. Near-ceiling log-odds magnify a 2-pp difference |
| **HARD DiD_d′** (harm sensitivity, SL_MT vs EN_BT; 349 unsafe / 1,093 safe) | Estimate only (MDE 0.56 > 2m_d′) | −0.003 [−0.33, 0.29] | **No evidence of a Slovene sensitivity surplus in GaMS.** Judge-dependent: calibrated +0.57 [−0.09, 1.20]; DEV gemini +0.58 [−0.07, 1.12]. Both CIs include 0 |
| **HARD DiD_c** (refusal criterion) | Estimate only (MDE 0.28 > 2m_c). The pre-registered tag is "SL criterion deficit in GaMS" | **+0.52 [0.38, 0.68]** | **The most robust finding: stable across every judge layer** (calibrated +0.66 [0.34, 1.00]; DEV gemini +0.67 [0.39, 1.02]; DEV Qwen3 +0.55 [0.30, 0.87]; SL_MT vs EN_orig +0.51; mt_fragile dropped +0.62). **Mechanism: Gemma-IT shifts toward refusal on benign Slovene prompts** (c_SL − c_EN = −0.43 [−0.57, −0.31]; false alarms on safe prompts .36 → .57), while **GaMS is language-invariant** (+0.09 [−0.00, 0.19]). The effect sits in OR-Bench-hard (ORB-only +0.70). XSTest-only is +0.10 [−0.13, 0.35]. The MT-noise control EN_BT vs EN_orig is −0.01 [−0.13, 0.11], so this is language, not translation drift. **FRAGILE under the pre-registered PARTIAL-as-refusal recoding** (DiD_c = −0.31 [−0.62, −0.09]): in Slovene, Gemma swaps hedged partial answers for outright refusals *and* for full compliance |
| HARD D_d′ (low- vs high-EN categories) | Estimate only | −0.68 [−1.48, −0.02] | The opposite sign to ALT-1. Underpowered |
| Holm-corrected one-sided ALT-1 tests | — | p = 1.0 and 1.0 | ALT-1 is not supported on either instrument |

**What survives.**
1. C1 identity anchoring is confirmed on reserved items. GaMS's self-identity is language-dependent: it is "GaMS" in
   Slovene, and often "Qwen/Alibaba" in English.
2. On matched content, **GaMS's refusal behaviour is language-invariant.** Relative to it, **Gemma-IT is more
   refusal-prone in Slovene.** It over-refuses benign Slovene OR-Bench-hard prompts, and it refuses slightly more
   harmful Slovene MT prompts. Gemma's refusal-criterion shift is the robust effect. It is a property of the
   *control* model that GaMS's Slovene training removed, not a Slovene refusal surplus that GaMS's safety SFT added.
3. No confirmatory support for ALT-1 ("Slovene-only safety data reaches only Slovene") or for a uniform Slovene
   sensitivity advantage (ALT-3). The natural-pair contrast points to a small GaMS Slovene *deficit*: about −3 pp,
   significant only with gemini labels.

**Exploratory (not pre-registered).** GaMS's Slovene refusals are terse and formulaic: a median of 16 tokens, and
52–61% open with "Oprostite, vendar vam pri tem ne morem pomagati". Its English refusals run about 80 tokens and open
"I'm sorry, but I can't". Gemma lectures to the 160-token cap in both languages. So the Slovene SFT visibly changed the
*form* of Slovene refusals while leaving the *rate* at parity. A consequence for measurement: Gemma answers are
truncated at 160 tokens in about 100% of refusal cells, whereas GaMS refusals end on their own.

**Judge checks.**
- **DEV gemini vs gpt-4.1:** binary κ .78–1.0 in every cell. No cell triggered the pre-registered prompt revision.
- **DEV gemini vs Qwen3:** binary κ .50–1.0. Qwen3 labels hedged English answers to benign HARD prompts as REFUSE
  +20–27 pp more often than gemini, but Slovene ones only +7–10 pp (`results/dev_judge_compare.json`,
  `figures/fig6_judge_calibration_dev`).
- **The per-cell calibration** (`results/judge_calibrated_*.json`) removes most of this bias in a split-half
  transfer test: the mean error on DiD_d′ goes from −0.48 to −0.05.
- **V5 (Qwen3; SL response vs its NLLB English translation, 400 responses):** agreement 90–98% and refusal-rate
  shift ≤ 4 pp, so the substitute judge is not language-asymmetric on identical content.
- **Language consistency** is ≥ 97.7% in every cell. Degenerate outputs are ≈ 0.

**Independent re-derivation** (`src/rederive_headlines.py` → `results/rederive_headlines.json`). It uses a pandas
code path and reads only the raw generations, labels, ledger and manifests.
- DiD_ref, DiD_ref^MT, HARD DiD_d′, HARD DiD_c and the gemini-subset DiD_ref reproduce the pipeline values to 1e-9.
- Within-item model-swap permutation tests:

  | Contrast | Real data p | Placebo (random model swap) p |
  |---|---|---|
  | DiD_c | < .001 | .82 |
  | DiD_ref^MT | < .001 | .88 |
  | DiD_id | < .001 | .31 |
  | natural DiD_ref | .13 | not applicable |

- C1 under an alternative regex coding ("mentions own name anywhere") gives DiD_id = 3.89, compared with the
  pipeline's first-match coding at 3.46.

**Not done / pending (needs budget; `finalize.sh` resumes):**
- the FINAL gemini labels for about 8.5k Gemma rows;
- the FINAL gpt-4.1 15% second family;
- the FINAL gemini/gpt-4.1 identity NAME|MAKER labels.

No human or native-speaker review took place, and none was simulated. The Slovene MT is not human-verified. Weights are
NF4 (reduced precision). Decoding is greedy with a single sample.

Spend: $2.10 of this artifact's $10 budget (`results/spend.json`). The run-level phase budget of $7.00, shared with
sibling artifacts, is what ran out.


## What changed from the plan, and why

Every change below is recorded in `protocol/deviation_*.json`, sha256-hashed and git-committed. Each commit was made
**before any FINAL outcome was computed**, and `git log` shows the order.

| Id | What | Why | Cost |
|---|---|---|---|
| D1 | A local third judge family was added: `Qwen/Qwen3-14B`@`40c06982`, NF4, non-thinking mode, the frozen v1 prompt; the label is the argmax of the next-token logits over REFUSE/PARTIAL/COMPLY (so it is deterministic and never unparsed). It judged all DEV rows, and all FINAL rows after the addendum commit (`src/judge_local.py`). | Judge-family robustness, and a hedge against the shared OpenRouter key, which was at its daily limit at 20:44 and 22:50 UTC. | None, because it was added. A 40-item DEV probe showed Qwen3 is self-biased as an identity judge: it answers "Qwen" for responses that never name themselves (`logs/qwen3_identity_selfbias_probe_dev40.jsonl`). It is therefore not used for identity. |
| D2 | A contingency rule in case the gemini DEV sweep did not complete. | KEY_DOWN at the start of the session. | Not triggered: the DEV sweep completed at 00:04 UTC. |
| D3 | Code edits after the freeze: the OpenRouter base URL is read from `OPENROUTER_BASE_URL` (platform requirement), retry/backoff was added, `spend.json` is exported, and one dead line was removed. | Infrastructure. | No item, prompt, decoding setting, statistic or verdict rule changed. |
| D4 | GaMS FINAL generation was interrupted at 9,088/10,150 rows when the agent session ended, and resumed with an identical configuration. | Session restart. | None. The file is intact and has no duplicate keys. |
| D5 | **The FINAL primary judge is the local Qwen3-14B (a substitute).** The FINAL identity primary is the regex self-name detector. | At 00:25 UTC the run relay failed. It then answered `403 aii_run_budget_exhausted` ("per-run OpenRouter budget reached … $7.02 of $7.00 … Retrying will not help"; `logs/relay_budget_exhausted_response.json`). The FINAL gemini sweep stopped at 11,146 of 19,660 labels: all GaMS rows plus the first 1,316 Gemma rows. No FINAL gpt-4.1 or identity labels exist. | FINAL refusal labels come from a weaker judge. On DEV, Qwen3 vs gemini binary kappa is 0.50–1.0 per cell, lowest on English HARD. Gemini vs gpt-4.1 is 0.78–1.0. No FINAL second-family kappa exists. |
| D6 | Verdicts are given under the committed margins (from gemini DEV labels: m=0.508, m_d'=0.166). They are **also** given under margins re-derived from Qwen3 DEV labels (m=0.773, m_d'=0.130; `protocol/addendum_dev_qwen3.json`). | The primary judge changed after the addendum was committed. | Two margin sets are reported. The committed set is the headline. |
| D7 | Replacement robustness layers: (a) every contrast recomputed on the gemini-labelled subset; (b) the complete **DEV** analysis judged by gemini (`results/analysis_dev.json`); (c) the V5 judge-language check redone with the Qwen3 primary, on RefusEU SL_MT and HARD SL_MT. | These replace the unavailable FINAL gpt-4.1 layer and the gemini V5 check. | The gemini-labelled subset covers only part of RefusEU natural for Gemma. |

Planned departures that the plan already listed (NF4 instead of bf16, no native-speaker review, judge-ASR instead of the
RefusEU guard ensemble, a 160-token truncation, greedy decoding, the gemini HARD MT, the opus-mt back-translation) all apply
unchanged.

## Pre-registered design (what was frozen, and when)

| Step | What | Evidence |
|---|---|---|
| 1 | Item manifests with fold asserts (1,300/100 RefusEU pairs; 1,442/616 HARD; 80+80/40+40 identity) | `data/*.jsonl`, `data/manifest_hashes.json`, `logs/build_items.log` |
| 2 | `protocol/protocol.json` frozen, sha256-hashed and committed **before the first FINAL generation** | commit `a76ee29` at 21:00:30 UTC. The first FINAL generation was at 21:10 UTC |
| 3 | Per model, one load: smoke test, throughput ladder (no cuts needed: 3.16 items/s at bs 64), batch check, DEV generation, FINAL generation (sealed) | `outputs/dev/{smoke,ladder,gpu_status}_*.json`, `outputs/final/gen_*.jsonl` |
| 4 | DEV judged (gemini on all, gpt-4.1 on 30% plus all identity items). `addendum_dev.json` fixes m, m_partial, m_id, m_d', m_c, the ceiling rule and the MDEs from DEV only. It was hashed and committed **before any FINAL judge call** | commit `36eb7c3` at 00:04:43 UTC. The first FINAL ledger line is at 00:04:5x UTC |
| 5 | FINAL judged: see D5 | `outputs/ledgers/`, `outputs/final/labels_local_qwen3.jsonl` |
| 6–8 | Merge, statistics, independent audit | `results/` |

Sealed-FINAL rule: `common.guard_final()` raises unless `addendum_dev.json` exists and its sha256 matches. `judge.py`,
`judge_local.py`, `scorers.py`, `analysis.py` and `judge_lang_check.py` call it before reading any FINAL response.
The audit checks the commit timestamps against the first FINAL generation and the first FINAL ledger line.

## Item sets and arms (FINAL)

| Set | Arms | n per arm | Role |
|---|---|---|---|
| RefusEU natural (`refuseu_nat`) | EN_nat, SL_nat | 1,300 pairs | Cross-model DiD. The EN and SL rows are **not** translations of each other (iter-1 LaBSE check) |
| RefusEU item-matched (`refuseu_x`) | SL_MT (NLLB MT of the EN item), EN_BT (opus-mt back-translation) | 1,296 | Within-model language contrast (DiD_ref^MT), which holds the item content fixed |
| HARD (`hard`) | EN_orig, SL_MT (gemini MT, BT-verified), EN_BT (gpt-4.1-mini BT); SL_NLLB (XSTest only) | 1,442 (349 unsafe / 1,093 safe); 312 for SL_NLLB | SDT co-primary (d', c) and the OR-Bench trade-off plane |
| Identity (`identity`) | EN, SL | 80 identity + 80 control pairs | C1 |

## Layout

```
method.py                 entry point; runs every stage in order (resumable)
finalize.sh               the same chain as one resumable shell command
pyproject.toml / requirements.lock   pinned environment (uv)
src/common.py             paths, constants (SEED 20260924, 160 tokens, frozen_groups.json), lexicons, sealed-FINAL guard
src/build_items.py        STEP 1: item manifests + T1 asserts
src/freeze.py             STEP 2: protocol freeze + git commit
src/gen.py                STEP 3: NF4 GPU pass (smoke, ladder, batch check, DEV, FINAL)
src/prompts.py            frozen judge prompts v1 + parsers
src/openrouter.py         async OpenRouter client, cost-capped resumable ledgers, KEY_DOWN handling
src/judge.py              STEP 4.1 / 5.1: API judges (gemini primary, gpt-4.1 second family / fallback) + label export
src/judge_local.py        D1: local Qwen3-14B judge (logits), DEV + FINAL
src/addendum.py           STEP 4.2: DEV-only margins, ceiling, MDE -> commit (--labels qwen3 for the D6 sensitivity)
src/scorers.py            STEP 5.2: $0 scorers (lexicon, lingua language ID, degenerate flags, regex self-names)
src/judge_lang_check.py   STEP 5.3 (V5): NLLB SL->EN, re-judged with the primary judge
src/stats_lib.py          pure statistics (Hautus log-odds, DiD, SDT, bootstrap, BCa, verdict mappings, misclassification)
src/analysis.py           STEPS 6-7: merge + every statistic, sensitivity, robustness layer and verdict
src/dev_judge_compare.py  DEV cross-judge replication (gemini vs Qwen3 on identical DEV items)
src/judge_calibrated.py   EXPLORATORY: FINAL Qwen3 estimates mapped to the gemini scale via DEV per-cell calibration
src/rederive_headlines.py independent pandas re-derivation of headline numbers + placebo-validated permutation tests
src/audit.py              STEP 8: independent plain-python recomputation, placebos, integrity checks
src/make_outputs.py       STEP 9: method_out.json + results/RESULTS.md
src/figures.py            figures/fig1..fig5 (PDF + PNG)
src/unit_tests.py         T0 unit tests -> results/unit_tests.json
src/iter1_copy/           read-only copies of the iter-1 modules this code was adapted from (provenance)
data/                     item manifests, manifest_hashes.json, cuts.json
protocol/                 protocol.json (+sha, commit), addendum_dev.json (+sha, commit), addendum_dev_qwen3.json,
                          deviation_1..3.json (+sha), primary_judge.json
outputs/dev/, outputs/final/   raw generations (append-only JSONL), labels, scores, smoke/ladder/batch-check logs
outputs/ledgers/          every OpenRouter call (key, raw text, parsed label, tokens, usage.cost, timestamp)
results/                  items_{final,dev}.jsonl/.parquet, analysis_{final,dev}.json, audit.json, RESULTS.md, spend.json,
                          judge_lang_check*.json(l), boot_idx_*.npz, unit_tests.json
figures/                  fig1_forest, fig2_tradeoff, fig3_dose, fig4_identity, fig5_rates
full_method_out.json      exp_gen_sol_out: one block per item set; predict_gemma_it / predict_gams3_it = primary labels
mini_/preview_method_out.json   3-example variants
logs/                     run logs (generation, judges, relay errors, retry log)
```

## How to run

```bash
uv sync                                  # pinned environment
uv run method.py                         # every stage; resumable (generation ~2 GPU-h on one RTX 4090)
uv run method.py --from judge_local_dev --skip-gen   # resume after generation
bash finalize.sh                         # the same chain as one shell command (SKIP_GEN=1 to skip the GPU generation)
cd src && uv run python unit_tests.py    # T0 unit tests
```

Environment variables: `OPENROUTER_API_KEY` and `OPENROUTER_BASE_URL` (the judges), `HF_TOKEN` (the gated Gemma repo),
`AII_COST_CAP` (default 9.0 USD).
To finish the API layer that D5 left incomplete (≈8.5k gemini calls, ≈3k gpt-4.1 calls and 1,280 identity calls, about
$4.5), run `cd src && uv run python judge.py --split final` once budget is available. The ledgers resume.
Deleting `protocol/primary_judge.json` would then restore the pre-registered gemini-primary analysis, which could be
reported as the planned primary next to this substitute-judge result.

## Restoring removed files

| Removed path (`.aii/manifest.yaml`) | Restore with |
|---|---|
| `.venv/` | `uv sync` (pins in `pyproject.toml` and `requirements.lock`) |
| `src/__pycache__/` | Recreated automatically on import (`python -m compileall src`) |
| Model weights (never stored in this workspace; shared run cache) | `huggingface-cli download google/gemma-3-12b-it --revision 96b6f1eccf38110c56df3a15bffe176da04bfd80`; `huggingface-cli download cjvt/GaMS3-12B-Instruct --revision 1d0b27af5748784482600d24779409e7e1dc9adc`; `huggingface-cli download Qwen/Qwen3-14B --revision 40c069824f4251a91eefaf281ebe4c544efd3e18` |
| NLLB for the V5 check | `huggingface-cli download facebook/nllb-200-distilled-1.3B` |
