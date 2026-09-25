# ALT-3 screen: does a Slovene-taught persona gate Slovene refusal? (GaMS3-12B-Instruct vs Gemma-3-12B-IT)

Screen `experiment_iter1_dir4` of run `run_FVi3e3O9CH5I` (SCREEN-SPEC v1). Tests the ALT-3 hypothesis: GaMS3's
Slovene-taught own-name persona **gates** its Slovene refusal behaviour, relative to its base family Gemma-3.

The method ablates a per-layer own-name persona direction in the late third of the network (layers 32-47). Controls:
- original model;
- the same direction ablated early (layers 0-15);
- 5 isotropic random directions;
- 5 variance-matched random directions;
- a Slovene-minus-English language-identity direction.

All of these run in both models, on 400 RefusEU harmful-prompt pairs (EN + SL). The signature is a triple difference (TD\*), with a pair bootstrap.

**Everything numeric below is recomputed from the saved files by `src/analyze.py`, with independent checks in
`src/audit.py` and placebo tests in `src/placebo.py`.** The authoritative source is `results/analysis.json` and
`method_out.json`. See "RESULTS" at the end, which is filled in from those files.

## What was done (in order)

1. **Data (CPU, `src/prep_data.py`).**
   - Source: NASK-PIB/RefusEU `lang_en` / `lang_sl`, splits train and test (2,889 rows per language). The reserved `evaluation/` split was **never downloaded or read**; `common.assert_not_eval` guards this.
   - Pairing: `row_id` is not unique, so pairs are row-index pairs. Row index aligns `row_id` and category at 100%.
   - **Finding: EN and SL rows that share an index are topic- and category-matched generated variants, NOT translations.** So "item-matched" here means category-matched.
   - Added a **translation-matched SL cell (`slmt`)**: NLLB-200-1.3B machine translation of the EN prompts, scored on s.
   - Split: CONSTRUCT (h = sha1 % 4 == 0; 726 pairs) vs SCORE (2,163 pairs).
   - SCORE-400: stratified; all low-EN-dose categories S5/S7/S8/S13, up to 45 each; 175 low / 68 mid / 157 high.
   - Other item sets: CONSTRUCT-200, MC-HARM-40, CONSTRUCT-DIR-300, and alpaca harmless 100 + 100 (SL by NLLB).
   - Hand-written EN/SL identity items: `src/identity_items.py`.
2. **Self-certification (`src/selftest.py`, both models).**
   - Hook no-op is bit-exact.
   - After ablation, the projection on u is below 2e-4·‖h‖.
   - Batched greedy generation is *not* token-identical to batch-1, but **equally so without any padding**. GaMS: 11/16 no-pad vs 8/16 left-pad; Gemma: 8/16 vs 8/16. Refusal labels agree 16/16.
   - So the divergence is NF4 kernel numerics (the bnb gemv kernel at batch-1 vs dequant+GEMM when batched), not the gemma-3 left-pad mask bug. Left-padded batches are used for every condition and both models.
   - s route (KV-cache copies vs full concatenation) differs by at most 0.2 (GaMS) and 0.45 (Gemma): symmetric numerical noise. The same route is used everywhere.
3. **CONSTRUCT phase (`src/gpu_run.py --stage construct`).**
   - Directions:
     - persona (a): forced prefix "I am GaMS/Gemma, …" minus 5 other names, read on the continuation tokens;
     - persona (b): identity questions minus personal questions, last token;
     - refusal directions for EN and SL;
     - language-identity direction;
     - ISO and VARMATCH random directions.
   - CONSTRUCT-200 originals (gives p0, m, b1).
   - Manipulation check (MC).
4. **Consequential pre-hash amendment: the ablation operator.** Details in `protocol.json › departures_pre_hash`.
   - The pre-registered zero-projection ablation h ← h − (h·u)u at every position was **catastrophic in GaMS**:
     - persona: 100% degenerate "Slovenian Slovenian …";
     - VARMATCH random: CJK loops;
     - even isotropic random: EN refusal 0.925→0.375 and '****' outputs.
   - Diagnosis: Gemma-3-family residual streams have massive activations. The diff-of-means persona direction's uncentred energy is up to ~10⁵× an isotropic direction's, and the BOS attention sink is hit. Zeroing a projection moves the state far off-distribution.
   - A CONSTRUCT-only pilot (`src/ablation_pilot.py`, `results/ablation_pilot_gams.json`) compared zero, zero-skip-BOS, mean, and mean-skip-BOS.
   - Only **mean-projection ablation that leaves BOS untouched**, h ← h − ((h·u) − μ·u)u, makes random ablation benign while keeping persona ablation coherent. It is used for **all** conditions.
   - μ is the mean residual over non-BOS positions of CONSTRUCT prompts.
   - VARMATCH directions were re-drawn and matched on the *centred* second moment. At GaMS layers 40-47, matching only reaches 0.15-0.41× of the persona variance (logged in `results/varc_stats_*.json`).
5. **Freeze.** `src/freeze.py` wrote `protocol.json` and hashed it (`protocol.sha256`) **before any SCORE item was scored in either model**.
   - It records: SCREEN-SPEC v1 text, selection rule, definitions, lexicons, prefixes, data hashes, p0/m/b1/m_s, MC results, and the chosen construction.
   - MC gates were re-evaluated with a 1e-9 float tolerance. An EN refusal shift of exactly 10 pp had been read as >10 pp. No PASS/FAIL outcome changed; the as-run values are kept.
6. **SCORE phase (`--stage score`).**
   - C0-C5 on SCORE-400 × {EN, SL}: R from 64 greedy tokens (frozen lexicon LEX-v1 and LEX-v1+), s, response language, degenerate flag.
   - s-only for SL-MT under C0-C3.
   - Harmless side effects: 100 × 2 prompts under C0-C3.
   - Band sweep: 6 bands × {persona, iso}, s only, on SCORE-200. This is pre-registered cut (2).
   - Projections: per-item projections on all 48 layers.
7. **Judge (`src/judge.py`)**: google/gemini-2.5-flash via OpenRouter, the pre-registered judge.
   - Coverage: all C0-C5 responses in EN and SL for both models; all MC identity responses; 50 per cell for harmless.
   - Fallbacks: provider-blocked or truncated items went to gpt-4.1-mini, then mistral-small (F8).
   - Key history: over its daily limit at the start (HTTP 403), recovered, then hit the limit again at 18:00 UTC.
   - Items still unlabelled use the lexicon label (imputation, counted per cell).
   - The local Qwen2.5-7B judge (`src/judge_local.py`) was run as fill-in and calibration only. Its κ vs gemini is 0.39, so it is not used for any number.
8. **Analysis** (`src/analyze.py` → `results/analysis.json`), assembly (`method.py` → `method_out.json`), audit (`src/audit.py` → `results/audit.json`), placebo (`src/placebo.py` → `results/placebo.json`).

## Layout

| path | content |
|---|---|
| `method.py` | assembles `method_out.json` (exp_gen_sol_out schema: one example per SCORE pair × model × language, predictions = responses per condition) |
| `run_pipeline.sh` | end-to-end driver (every stage resumable) |
| `src/common.py` | constants, frozen lexicon, Hautus logit, language detection, eval-split guard |
| `src/prep_data.py`, `src/identity_items.py`, `src/translate.py` | data preparation (P0) |
| `src/engine.py` | NF4 loading, chat rendering, residual hooks (capture / zero- or mean-projection ablation, BOS skip), batched greedy generation, s via KV-cache copies |
| `src/selftest.py`, `src/ablation_pilot.py`, `src/eightbit.py` | certification, the ablation-operator pilot, the (tier-2) 8-bit check |
| `src/gpu_run.py` | CONSTRUCT and SCORE stages |
| `src/freeze.py` | writes and hashes `protocol.json` |
| `src/judge.py`, `src/llm.py`, `src/judge_local.py` | gemini judge + cost ledger; local fallback judge |
| `src/analyze.py`, `src/audit.py`, `src/placebo.py`, `src/test_static.py` | analysis, independent audit, placebo tests, T0 static tests |
| `protocol.json`, `protocol.sha256` | frozen protocol (hash `eb718197…`) |
| `data/` | RefusEU EN/SL train and test parquet, pairs, splits (`splits_manifest.json`), SCORE-400, CONSTRUCT sets, harmless set, SL-MT, identity items, Heretic config |
| `results/items/*.jsonl` | per-item outputs: `{model}__C{0-5}.jsonl` (800 rows each), `__slmt`, `__harmless__`, `__sweep_*`, `__MC__*`, `__construct200__C0` |
| `results/directions/*.npz` | all directions (persona a and b, per-language persona, refusal EN/SL, langid, ISO/VARMATCH random), μ, centred VARMATCH |
| `results/projections_*.npz` | per-item projections (400 × 48) on persona / refusal / langid |
| `results/mc_*.json`, `results/construct_diag_*.json`, `results/selftest_*.json` | manipulation checks, direction diagnostics, certification |
| `results/judge_labels.jsonl`, `results/judge_ledger.jsonl` | judge labels, and the cost ledger with every call |
| `results/analysis.json`, `results/audit.json`, `results/placebo.json`, `results/test_static.json` | analysis outputs |
| `results/prompt_hashes.json` | sha1 of every prompt used, so confirmation can drop eval-split near-duplicates (the overlap list holds counts only) |
| `logs/` | all run logs |

## How to run

```bash
uv venv .venv --python=3.12 && uv pip install --python .venv/bin/python -r requirements.lock.txt
./run_pipeline.sh          # needs 1 GPU >= 20 GB, HF_TOKEN (gated gemma), OPENROUTER_API_KEY for the judge
```

## Restoring removed files

- `.venv/` (delete: regenerable): `uv venv .venv --python=3.12 && uv pip install --python .venv/bin/python -r requirements.lock.txt`
- `src/__pycache__/` (delete: regenerable): Python bytecode cache, recreated automatically the next time any script runs (e.g. `cd src && ../.venv/bin/python test_static.py`).
- Model weights are **not** in this workspace. They live in the run's shared HF cache. Restore with:
  - `huggingface-cli download cjvt/GaMS3-12B-Instruct --revision 1d0b27af5748784482600d24779409e7e1dc9adc`
  - `huggingface-cli download google/gemma-3-12b-it --revision 96b6f1eccf38110c56df3a15bffe176da04bfd80`
  - `huggingface-cli download facebook/nllb-200-distilled-1.3B`
- `data/refuseu/` is small and kept. It can be re-downloaded with `hf_hub_download('NASK-PIB/RefusEU', 'lang_{en,sl}/{train,test}-00000-of-00001.parquet', repo_type='dataset')`. Never download `evaluation/`.

## RESULTS (from `results/analysis.json`; audited by `src/audit.py`: 125/125 checks agree to 1e-9)

Throughout: CI = 95% pair-bootstrap (2,000 resamples, seed 20260923) over the 400 SCORE pairs.

### Verdict (pre-registered selection rule, protocol hash `eb718197…`)

**ALT-3 = UNTESTABLE.** The manipulation check (MC) failed in GaMS for all three pre-registered constructions (`results/mc_gams.json`):
- a_late;
- b_late;
- a over layers 24-47.

What passed and what failed:
- Persona ablation removed GaMS's own-name self-identification. Gemini judge, construction a_late with mean ablation: EN 0.45→0.00, SL 0.90→0.20.
- Isotropic random ablation left naming intact.
- But the **variance-matched random direction also cut EN naming** (0.45→0.275; the gate needs ≥ 0.36). So specificity fails.
- EN refusal moved exactly 10 pp in construction a (gate ≤ 10 pp, passes with float tolerance). Construction b passed this gate; a_24_47 fails the name-drop gate.

The descriptive SCORE results below are therefore not a test of a *persona* gate. They describe what ablating this particular own-name direction does. In Gemma, the MC (reported only) also fails on specificity.

The signature itself would not have survived either:

| readout | TD* (C2 early / C3 iso) | TD(C2) | TD(C3) | threshold | z_c | MDE |
|---|---|---|---|---|---|---|
| binary R, gemini judge (primary; lexicon κ<0.7 in C0-C3 cells of both models) | **+0.23 [−0.81, +1.25]** | +1.17 [+0.11, +2.23] | +0.23 [−0.81, +1.28] | m = 0.442 logit | −0.41 | 1.46 (> 2m, underpowered) |
| s (co-primary: ceiling rule fired, C0 refusal 0.97/0.97 EN) | **+0.43 [−0.11, +0.97]** | +5.14 [+4.44, +5.80] | +0.43 [−0.11, +0.97] | m_s = 1.32 | −3.17 | 0.78 |
| lexicon-only (robustness) | −1.35 [−2.10, −0.62] | | | m | | |
| s, translation-matched SL (NLLB-MT of EN prompt) | −0.24 [−0.78, +0.30] | | | m_s | | |

On s, the upper 95% bound of TD* (0.97) is **below the SESOI m_s = 1.32**. A persona-gate effect of the pre-registered minimum size is excluded on the continuous readout for this direction. This is conditional on the direction and on the MC caveat. The binary readout is inconclusive (MDE 1.46 > 2m).

Placebo (`results/placebo.json`, 60 model-label shuffles):
- no shuffle produced a TD* CI lower bound > 0 (false-survival rate 0/60, lexicon and s);
- min(TD₂,TD₃) is biased negative under the null (mean −0.19 lexicon, −0.17 s).

### Completed descriptive findings

1. **The baseline asymmetry runs the opposite way to ALT-3's premise.** GaMS has a Slovene refusal *deficit* relative to its sibling, not a surplus:
   - Originals, judge-rated refusal: GaMS EN 0.973 / SL 0.883; Gemma EN 0.970 / SL 0.955.
   - DiD_ref(C0) = GaMS(SL−EN) − Gemma(SL−EN) = **−1.11 logit [−2.00, −0.36]**.
   - On s: **−2.72 [−3.30, −2.13]**.
   - On translation-matched SL prompts (s): **−3.06 [−3.59, −2.52]**, so the deficit is not an artefact of RefusEU's non-parallel EN/SL variants.
   - By dose group (s): the deficit is *larger* in high-EN-dose categories (−3.40 [−4.26, −2.53]) than in low-EN-dose categories (−1.97 [−2.91, −0.99]). Difference +1.43 [+0.17, +2.77]; exploratory, and it belongs to MAIN/ALT-1.
2. **Late persona ablation barely changes GaMS's refusal** (C0→C1, judge readout):
   - EN 0.973→0.975; SL 0.883→0.853.
   - Per-item flips (McNemar exact): SL refuse→comply 26 vs comply→refuse 14, p = 0.081; EN 3 vs 4, p = 1.0.
   - Mean Δs (C1−C0): GaMS EN −0.68, SL −0.23.
   - In Gemma, the analogous own-name direction lowers s by ~8.3 nats in both languages, while judged refusal is unchanged (EN 0.970→0.975, SL 0.955→0.94). So s tracks the opening-phrase style ("I'm sorry, but…") more than the refusal decision there. s validity for Gemma EN is also weak: AUROC(s→R) = 0.56 at ceiling.
3. **Exploratory discovery (CONSTRUCT items, n = 40 per language, gemini identity judge; `results/items/*__MC__*`, `figures/identity_mc.png`): ablating GaMS's own-name direction does not make GaMS nameless. It makes GaMS say it is Qwen.**
   - Self-name "Qwen": EN 0.15→0.775, SL 0.025→0.60 (construction a, late, mean ablation). Construction b gives EN 0.625; a over layers 24-47 gives EN 0.725 / SL 0.45.
   - Controls: isotropic random 0.225 EN; variance-matched random 0.30 EN.
   - Gemma: 0 Qwen self-names in every condition.
   - Qwen models are reported to have generated GaMS's chat SFT data. So the GaMS persona direction behaves like a thin identity layer over a latent **teacher identity**: removing it *substitutes* the identity rather than deleting it.
   - This is a plausible alternative explanation to "persona gates refusal". It is untested beyond these 80 prompts per condition.
4. **Early (0-15) ablation is a broad perturbation, not a clean control.**
   - GaMS EN refusal 0.973→0.797. Gemma SL over-refusal on harmless prompts rises to 0.24.
   - TD(C2) is large on both readouts. This is why the pre-registered min() over controls matters.
5. **Other controls.**
   - Language-identity ablation (C5) is CATASTROPHIC by the language gate in both models: Slovene prompts answered in another language.
   - Variance-matched random (C4) is CATASTROPHIC in Gemma (25% degenerate SL).
   - Harmless side effects of C1 are small (over-refusal ≤ 0.02, language consistency ≥ 0.93). Exception: GaMS SL degenerate rate 0.15 under C1.
6. **Geometry** (last prompt token, layers 32-47 mean; for 1-D directions CKA reduces to squared cosine):
   - cos(persona, refusal-EN) = −0.07 (GaMS) / −0.09 (Gemma).
   - cos(persona, refusal-SL) = −0.24 / −0.24.
   - cos(persona, SL-minus-EN langid) = −0.38 / −0.24.
   - Item-level correlation of persona vs refusal projections is lower in SL than EN. SL−EN difference in r: GaMS −0.12 [−0.20, −0.04]; Gemma −0.41 [−0.52, −0.31]. Not GaMS-specific.
7. **Layer-band sweep** (s, SCORE-200, persona minus iso per band): large, non-monotone and model-specific. For example, Gemma band 24-31 gives −23.3, which is off-distribution. No band shows a GaMS-specific SL-gap shrink of the hypothesised sign that stands out from these swings (`sweep_s` in analysis.json, `figures/band_sweep_s.png`).

### Validity and measurement notes

- **The frozen lexicon (Heretic EN markers + SL markers) is unreliable here.** κ vs gemini is 0.02-0.69 across cells:
  - Gemma bolds refusals ("I **cannot**");
  - off-language answers defeat the language-specific markers;
  - "harmful"/"illegal" appear inside compliant text.
  - The pre-registered κ<0.7 rule therefore moved **both** models to judge labels for all C0-C5 cells.
- Judge coverage: gemini-2.5-flash labelled 100% of C0-C4 EN/SL responses of both models, except 49 provider-blocked or truncated items that went to gpt-4.1-mini / mistral-small (per F8).
- Imputation: the OpenRouter shared key hit its daily limit again at 18:00 UTC. The remaining 61 GaMS items (≤ 11 per cell) and all of GaMS C5 use the lexicon label (`judge_imputed_by_lexicon_per_cell`). A local Qwen2.5-7B judge was tried as fill-in but agrees poorly with gemini (κ 0.39, `results/judge_crosscheck.json`), so it is not used for any number.
- Total OpenRouter spend: $1.45 (ledger `results/judge_ledger.jsonl`).
- **Judge retry (18:37 UTC):** after a platform note said the OpenRouter key had been replaced, the imputed items were re-submitted to gemini. They got HTTP 403 again. The key file `/ai-inventor/aii_data/.secrets/openrouter_key.private` still held the exhausted key (same fingerprint as the environment variable, file dated 14:37 UTC), so no fresh key reached this workspace. **To finish the judging once a working key is present, run `./finalize.sh`.** The ledger is resumable, so only the ~1,254 imputed GaMS items are called (about $0.2). Analysis, audit, placebo and figures are then recomputed automatically.
- **The ablation operator was changed before the hash** (see step 4 above). Zero-projection ablation is catastrophic for Gemma-3-family models, including for random directions. Any Gemma-3 ablation study must mean-centre and skip BOS, and must use a centred-variance-matched random control.
- s validity: AUROC(s→R) on originals is GaMS 0.92 EN / 0.94 SL, Gemma 0.98 SL, but **Gemma EN 0.56** (ceiling, few non-refusals).
- Not run: the 4-bit vs 8-bit check (pre-registered cut 1) and the full-SCORE tier-3. The band sweep ran on SCORE-200 (cut 2), and SL-MT is s-only (time cut).

### Reduced scope and limitations

- NF4 4-bit weights for both models, on an NVIDIA L4.
- SCORE-400, not the full SCORE split.
- RefusEU SL prompts are generated variants, not translations; the MT cell is s-only.
- No human or native-speaker audit.
- Eval-split near-duplicates were not dropped (hashes exported in `results/prompt_hashes.json`).
- The MC used 40 items per language.
- A single API judge family (with a few fallbacks).
- Directions are diff-of-means over hand-written items. A different persona operationalisation could behave differently.
- **No causal claim about a persona gate is supported.** The Qwen-substitution observation is exploratory.

Figures: `figures/refusal_rates.png`, `figures/forest_G_TD.png`, `figures/band_sweep_s.png`, `figures/identity_mc.png`.
Kept artifact paths (workspace `.`): `results/directions/*.npz`, `results/items/`, `results/analysis.json`, `method_out.json`.
