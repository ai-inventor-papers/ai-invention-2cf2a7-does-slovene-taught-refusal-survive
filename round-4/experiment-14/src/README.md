# Does Slovene refusal follow the prompt or the reply?

Input-language × forced-output-language crossing of a refusal-abliteration "language lag" in a Slovene-adapted
model pair — **Gemma-3-12B-IT** vs **GaMS3-12B-Instruct** — under partial-dose English abliteration.

> This folder is one artifact of the AI-Inventor run `run_FVi3e3O9CH5I` (iter-4, mechanism arm). It is published
> as one directory of a public GitHub repository; sibling directories are the artifacts it reads (all read-only).

## The question

An English-objective Heretic LoRA, applied at matched **English** refusal strength, leaves earlier-iteration
Gemma-3-12B-IT refusing **more in Slovene than in English** (a residual "lag"), and less so in the Slovene-adapted
sibling GaMS3. Iter-4 asks *where that residual lives*: does the surviving refusal track the **prompt** language
(M-IN), the **reply** language the model is forced to write (M-OUT), or only the case where both are non-English
(M-MATCH)? We cross input language × forced output language over {EN, SL, HU} in a fully-paired 9-cell grid, at
λ = 0 and two edited doses bracketing English→English refusal = 50 %, and decompose the edit-induced lag `L*` into
output-side (`OUT`) and input-side (`IN`) shares.

`README_design.md` has the frozen design and every estimand; `RESULTS.md` + `results/RESULTS_tables.md` (generated
from `results/analysis.json`, no hand-typed numbers) have the verdicts.

## Method vs baselines (all in the same NF4 pipeline)

| role | what |
|---|---|
| **Method** | exp9's selected Heretic LoRA (r=3, o_proj+down_proj) as λ-scaled bf16 forward hooks; ΔW(λ)=λ·ΔW; λ=0 bit-identical to base (max\|Δlogit\|=0 asserted) |
| **Baseline 1** | unedited model, λ = 0, identical items/decoding/judge |
| **Baseline 2** | norm-matched **random-direction** edit at λ_hi (exp9 `rand_1`), EN→EN and SL→SL, + first-token KL collateral |
| **Baseline 3** | the **sibling** GaMS3-12B-Instruct — every cross-model contrast is GaMS − Gemma (G3), so shared Gemma-3 properties cancel |
| **Baseline 4** | a public English-abliterated checkpoint **p-e-w/gemma-3-12b-it-heretic** (C-EXT, descriptive) run through the same 9 cells |
| **Baseline 5** | **Hungarian** — a third language absent from GaMS3's CPT — separates "Slovene competence" from GaMS safety SFT |
| **MT-noise control** | EN_orig vs EN_BT (NLLB round-trip) in EN→EN at λ 0 / λ_hi (McNemar) |

## Layout

| path | what |
|---|---|
| `method.py` | orchestrator; `--stages prep,gemma,gams,ext,judge,ttj,asr,analysis` (all resumable) |
| `run_chain.sh` | the GPU chain actually used after the Gemma grid (GaMS → C-EXT → NLLB TTJ, with J1 labelling between loads) |
| `protocol.yaml`, `protocol.sha256` | frozen protocol, git-committed **before any grid row**; amendments in `results/protocol_amendments.jsonl` (A0–A6) |
| `src/preflight.py` | dependency + sha checks, HF pins, GaMS-Hungarian model-card check, OpenRouter smoke → `results/inputs_check.json` |
| `src/build_pool.py` | external harmful pool (HarmBench/StrongREJECT/JBB), dedup vs every earlier probe + Heretic's objective sets, C-half 200 harmful |
| `src/twins.py` | 40 JBB benign + 60 gpt-4.1-mini benign twins (each machine- and executor-vetted; `results/twins_review.json`) |
| `src/build_items.py` | NLLB SL/HU MT + chrF gate (copied from exp11), DEV items, KL stems, suffix QA, and the TTJ translator |
| `src/freeze.py` | writes + hashes + commits `protocol.yaml` |
| `src/gen.py` | NF4 loader, LoRA/random forward hooks, DEV dose scan, the 9-cell grid, first-token KL (hook code copied from exp11 `gen.py`) |
| `src/calib.py` | paid judge-tier selection on 562 previously-adjudicated rows (A0) → `results/judge_tier_table.json` |
| `src/judge_j1.py` | **primary judge** J1 (exp9's gemini-distilled mdeberta classifier; amendment A4) — calibration + labelling + TTJ labelling |
| `src/judge_paid.py`, `src/judge_worker.py` | paid OpenRouter judge infra (cache + ledger + $4.75 hard stop); used for calibration/twins before the key limit, resumable if the key returns |
| `src/asr.py` | StrongREJECT rubric (verbatim) on non-refused harmful rows (R-INCAP) |
| `src/adjudicate_frame.py` | draws the blind adjudication frame from generations only, before any label is read |
| `src/build_table.py` | merges generations + labels + lingua language-ID + adjudication → `results/rows_final.jsonl` |
| `src/analysis.py`, `src/stats_core.py` | the estimator (interpolated `a`, `L*`, OUT/IN/INT, G3, SDT, RG, PPI++, GEE, bootstrap, placebos); `stats_core.py` copied verbatim from exp11 |
| `src/rederive.py` | **independent** pandas re-derivation of every headline → `results/audit.json` |
| `src/figures.py`, `src/make_report.py`, `src/make_outputs.py` | figures F1–F6, `results/RESULTS_tables.md`, `method_out.json` |
| `data/` | `pool_*.jsonl`, `items.jsonl` (9-cell prompts), `dev_items.jsonl`, `kl_stems.jsonl`, `pool_manifest.json`, `dedup_log.jsonl` |
| `results/gens/{model}.jsonl` | every generation (one row per item×cell×λ×cond) |
| `results/labels/labels.jsonl` | J1 (+ any paid) labels, TTJ labels, ASR scores |
| `adjudication/` | blind frames, `author_labels_*.json` (executor, **NOT human**), keys |
| `results/analysis.json`, `results/audit.json`, `results/judge_validity.json` | all statistics, the re-derivation, per-cell judge Se/Sp |
| `figures/` | F1 L* heatmaps, F2 OUT/IN forest, F3 dose curves, F4 SDT, F5 judge Se/Sp, F6 C-EXT |
| `tests/test_core.py` | T0 unit tests (Hautus, RG, PPI recovery, κ vs sklearn, interpolation vs GLM, lockstep + planted-lag synthetics, placebo null) |

## How to run

```bash
uv sync
uv run method.py --stages prep      # preflight, pool, twins, NLLB items, judge calibration, freeze
uv run method.py --stages gemma     # MINI + DEV dose scan (amendment A1) + KL + 9-cell grid   [L4 GPU]
uv run method.py --stages gams      # same for GaMS3 (amendment A2)
uv run method.py --stages ext       # C-EXT public checkpoint
uv run method.py --stages judge,ttj # J1 primary labels + NLLB translate-then-judge
uv run method.py --stages asr       # StrongREJECT (only if the OpenRouter key is un-blocked)
uv run method.py --stages analysis  # table -> analysis -> audit -> figures -> report -> method_out.json
uv run pytest -c pytest.ini tests/  # 10 T0 checks
```
One NVIDIA L4 (23 GB). Every generation and label job is append-only and resumable by row key.

## Honest limitations

* **NF4 4-bit** everywhere (a 23 GB GPU cannot hold bf16 12B). Contrasts are within-precision; absolute levels are NF4-specific.
* **The paid judges were blocked mid-run** (`403 aii_openrouter_key_limit`, shared platform key hit its daily cap during
  the DEV scan). The **primary readout is therefore J1**, a local mdeberta classifier distilled from archived real
  gemini-2.5-flash labels (exp9; held-out κ_R 0.84). J1 over-calls refusal (Se≈0.90, **Sp≈0.60** on the fresh
  adjudication), so **every headline is led by its Rogan-Gladen / PPI++-corrected value**, and the raw J1 rate is a
  co-report only. The whole `judge_paid`/`judge_worker` path is intact and resumes automatically if the key returns.
* **No human review.** MT is not human-verified (chrF back-translation gate only); the blind adjudication is the
  **executor model, NOT a person** — `results/human_audit_request.json` requests a native-speaker audit.
* **128 generated tokens**, greedy, single sample (standard for refusal; ASR convincingness/specificity are lower bounds).
* **Two edited doses**, interpolated (no curvature check); the exp11 3-dose GLM is co-reported.
* Cross-model DiD is underpowered (MDE ≈ 1 logit); the primary mechanism call is made **within Gemma**, GaMS is an ESTIMATE.

## Restoring removed files

`.aii/manifest.yaml` marks these `delete` (everything else — code, `data/`, `results/`, `adjudication/`, `figures/`,
`method_out.json`, logs — is kept in place on the run's storage volume; files ≥ 100 MB are not pushed to GitHub).
`restore.sh` runs all of the below.

* **`.venv/`** (regenerable): `uv sync` (or `uv venv .venv --python 3.12 && uv pip install -r requirements.lock.txt`).
* **`src/__pycache__/`, `tests/__pycache__/`, `.pytest_cache/`** (regenerable): recreated by running any `src/*.py` or `uv run pytest -c pytest.ini tests/`.
* **J1 judge weight** (regenerable, reassembled to a temp dir OUTSIDE the repo, not published): sha256-verified from the sibling artifact
  `gen_art_experiment_9/judge_model/mdeberta_gemini_distill/model_parts/` — `cd src && python -c "from judge_j1 import ensure_local; ensure_local()"`.
* **model weights** are in the run's shared HuggingFace cache (`$HF_HOME`), not this folder:
  `hf download google/gemma-3-12b-it --revision 96b6f1ec…`, `cjvt/GaMS3-12B-Instruct --revision 1d0b27af…`,
  `p-e-w/gemma-3-12b-it-heretic --revision e037e6e1…`, `facebook/nllb-200-distilled-1.3B`.

The edit adapters are read read-only from the sibling artifact `gen_art_experiment_9/selected/{gemma_it,gams3_it}/adapter`.
