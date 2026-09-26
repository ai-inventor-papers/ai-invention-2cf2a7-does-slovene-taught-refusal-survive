# Do base models set Slovene refusal? (ALT-2 + C4 screen, GaMS3 vs Gemma-3)

This is slot 3 of the SCREEN-SPEC v1 five-way screen (run_FVi3e3O9CH5I, iteration 1). It tests two claims:

- **ALT-2:** the *base* checkpoint's harm geometry sets the EN/SL refusal profile of the instruct model.
- **C4:** a refusal gate readable from the shared ancestor (gemma-3-12b-pt) causally induces refusal in both instruct models, with the same EN/SL potency.

Four checkpoints ran one at a time in identical **NF4 4-bit (reduced precision)** on one RTX 4090 (24 GB):

- google/gemma-3-12b-pt@295efb63
- cjvt/GaMS3-12B@46127695de
- google/gemma-3-12b-it@96b6f1ec
- cjvt/GaMS3-12B-Instruct@1d0b27af57

The RefusEU `evaluation/` split was **never read**; it is reserved for confirmation. `results/analysis/audit.json` checks this. Seed 20260923.

## Headline results

All numbers below were recomputed from the raw JSONL/NPY files by `src/audit.py`, a separate code path using pandas, statsmodels and scipy.curve_fit. All checks match. The placebos fail as they should:
- shuffled-label d′: −0.03
- permuted-y R²adj: 0.0002
- shuffled-α Spearman: ≈0

### Completed, pre-registered

**1. ALT-2 FAILS on both parts; it does not survive.**

*(a) Base separability at the pre-registered layer L_pt = 22.* This is the difference-of-means d′ of SCORE harmful vs harmless prompts.

| | gemma-3-pt | GaMS3-base |
|---|---|---|
| EN | 2.72 | 1.05 |
| SL | 1.92 | 0.94 |

Δd′_SL (GaMS − pt) = **−0.98 [−1.13, −0.85]**. That is the opposite sign to ALT-2. The DiD, [SL−EN]_gb − [SL−EN]_pt, is +0.69 [0.50, 0.88].

At each model's *own* best layer (pt 22, GaMS 26), Δd′_SL = +2.85 [2.39, 3.38]. **The sign of the base-geometry contrast depends on the layer.** Probe AUROC is ≥0.99 at every probed layer ≥ 8 in both models (0.990–0.996 at layer 4). It is flagged CEILING and is uninformative (knowledge ≠ action).

*(b) Item-level regression, n = 2,146 SCORE pairs.* The outcome is the instruct DiD on s. Base harm-z projections explain almost nothing:

| Model | R²adj |
|---|---|
| Geometry | 0.005 |
| Dose | 0.002 |
| Category fixed effects (ceiling) | 0.120 |

- **Geometry share = 0.042 [0.005, 0.122]**, z_c = −15.1.
- Dose increment = 0.013 [−0.005, 0.063].
- Dose coefficients: wild-cluster bootstrap p = 0.87 / 0.92.
- The same holds for the offset-corrected s_c. Its R² quantities are identical by construction.

**2. C4: failure branch — no causal support readable from the ancestor.**

The gemma-3-12b-pt pooled direction, added at L22, **never reaches R = 0.5**:

- **Judge readout:** NR in all 4 model × language cells. Peak judge refusal is 0.03 to 0.25.
- **Judge incoherence:** over all α, 61–65% of pt-steered outputs are judged incoherent, versus 41–48% for the own directions and 23–31% for language-ID. The pt direction mostly breaks generation rather than gating refusal. Judge coverage of induction outputs is 87–95% per cell; the rest had unparseable judge replies and are excluded from the judge readout.
- **Random directions:** peak R is similar (up to 0.47 in one 20-item cell).
- **Lexicon readout:** pt reaches α50 only in GaMS EN, 0.067·N̄. This is a lexicon artefact: in that cell the lexicon's PPV against the judge is 0.08.
- **Cosine with own directions:** in both instruct models, the pt direction has cos ≈ −0.02 to −0.07 with their own refusal directions.

**Positive control passes.** Each instruct model's *own* pooled refusal direction (CONSTRUCT harmful − harmless) reaches α50 in all 4 cells:

| Model | α50 (lexicon) | α50 (judge, interpolated) |
|---|---|---|
| Gemma-IT | 0.030–0.033·N̄ | 0.029–0.052·N̄ |
| GaMS | 0.050–0.060·N̄ | 0.046–0.058·N̄ |

GaMS needs about 1.1–1.8× more steering, relative to its own N̄. Curves are inverted-U: refusal peaks at ≈0.07–0.10·N̄, then the model collapses off-manifold.

**Pre-registered failure branch (own-direction Δ_C4).** Δ_C4 = [ln(a50_SL/a50_EN)]_GaMS − [ln(a50_SL/a50_EN)]_Gemma:

| Readout | Δ_C4 | ln-ratio GaMS | ln-ratio Gemma |
|---|---|---|---|
| Lexicon | −0.09 [−0.28, 0.07] | | |
| Judge | +0.24 [0.13, 0.38] | −0.26 | −0.50 |

Both CIs lie inside ±ln 1.5, so **ALT-1 is not supported**. There is no large GaMS-specific language asymmetry in the potency of the refusal gate. The small residual effect changes sign with the readout, so it is not interpretable. Both models need less α in Slovene than in English.

**3. Instruct behaviour on SCORE-400 (secondary; the MAIN/ALT-1 screen is authoritative).**

Refusal rates:

| Model | EN judge | SL judge | EN lexicon | SL lexicon |
|---|---|---|---|---|
| Gemma-IT | 0.957 | 0.945 | 0.955 | 0.918 |
| GaMS | 0.967 | 0.917 | 0.955 | 0.780 |

- DiD_ref on judge labels = −0.70 logits [−1.45, +0.02]; on the lexicon, −1.13 [−1.87, −0.46].
- DiD on raw s = −2.49 [−3.12, −1.87].
- D (low-EN − high-EN categories), judge: −0.55 [−2.46, 1.12], not significant.
- The ceiling rule applies (Gemma EN R > 0.95), so the s-based DiD is co-primary.

### Validity findings (these change how R- and s-based numbers must be read)

- **The frozen lexicon is asymmetric across languages.**
  - Heretic's EN markers include "illegal/unethical/harmful"; the SL list has no equivalents.
  - GaMS's Slovene refusals are often moral objections ("neetično, nezakonito") without "ne morem".
  - Judge κ values: GaMS SL 0.38; Gemma EN 0.17 (prevalence paradox at ceiling, 87% raw agreement); pt-induction EN 0.10–0.15.
  - Lexicon-based SL−EN contrasts therefore overstate GaMS's SL deficit (0.78 vs judge 0.92).
  - R_judge (gemini-2.5-flash, all 1,600 SCORE-400 responses plus all pt/own/langID/random induction responses) is co-primary (D16).
- **The s readout is dominated by template/language priors.**
  - Mean s on harmless prompts is −19.9 for Gemma EN vs −4.1 for Gemma SL.
  - The offset-corrected s_c reverses the mean DiD, from −2.9 to +11.7 (D5 disagreement flagged).
  - AUROC(s→R) is 0.93–0.97 except Gemma EN (0.50–0.57, ceiling; minority n ≈ 17).
- **Quantisation check:** NF4 vs int8 greedy first-token agreement is 18/20 for both instruct models, passing the ≥17/20 bar.

### Exploratory (post-freeze, found during execution; not part of the decision rule)

- **Last-token format confound in base-model harm directions.** Harmful RefusEU prompts end in `"` (EN, 52% quote-wrapped) or `?` (SL 95%); alpaca prompts mostly end in `.`.

  | Check | Δd′_SL at L22 | Δd′_SL at own layers |
  |---|---|---|
  | Punctuation-matched (`?` vs `?`; ~25 harmless items/lang) | +3.17 [2.37, 4.10] (EN +3.63) | +0.30 [−0.20, 0.78] (EN −1.28) |
  | Mean-pooled residuals | −0.38 [−0.44, −0.32] | +0.76 [0.48, 1.05] |

  **Conclusion:** base-model separability contrasts between these checkpoints are not robust to layer choice, pooling or format matching. ALT-2(a) cannot be established either way with this design.
- **Direction geometry.** In the instruct residual space at L22, the GaMS-base pooled direction is closely aligned with the language-ID direction: cos +0.88 in both instruct models. The instruct models' own refusal directions are anti-aligned with language-ID (−0.78 / −0.86). GaMS's own EN and SL refusal directions are nearly identical (cos 0.99, vs 0.93 in Gemma-IT). The analysis of this pattern is not complete.

### Not executed / limitations

- Screen only: one greedy decode, NF4, single layer L22.
- 100 induction prompts per language (Arditi floor); random directions use 20 prompts.
- No human or native-speaker audit and no developer consultation.
- Harmless prompts were translated with a local NLLB-200 1.3B (F7) because the OpenRouter key was at its daily limit when the data were built. After the key was restored, the plan's gemini-2.5-flash translation was run as a check (`src/mt_compare.py` → `results/analysis/mt_comparison.json`, `data/alpaca_harmless_gemini_mt.jsonl`; $0.06). The frozen NLLB items were **not** replaced, because the protocol and all GPU runs used them. Gemini sometimes *executes* the instruction instead of translating it (e.g. it writes the requested recipe or story): 17% of used items diverge strongly from NLLB (chrF < 40), and gemini back-translation falls below chrF 50 in 19% of items vs 11% for NLLB. NLLB is therefore the more faithful source for instruction prompts, and the degraded-MT concern does not apply.
- Supervision dose is category-level (14 values) and classifier-derived (Stage-0b).
- RefusEU EN/SL rows are generated variants, not translations. Only between-model contrasts on the same items are interpreted.
- No overlap drop (D1): the confirmation step must dedupe the reserved split against `data/screen_item_manifest.json`.

## Deviations

- **D1–D12:** frozen in `config/protocol.json`, sha256 in `config/protocol.sha256`, git commit 14:51:47Z. This precedes the first model forward pass (14:54:15Z).
- **D2 (m):** frozen at 0.459 log-odds in `config/protocol_addendum.json`, commit 16:25:26Z.
- **D13–D16:** declared in the same addendum:
  - D13: fp32-verified KV-reuse scorer.
  - D14: 3 lower α steps (the own-direction norm is only ~6–9% of N̄).
  - D15: rising-limb 4PL fit (inverted-U curves).
  - D16: full judge labels.
- **Hardware:** RTX 4090 24 GB instead of the planned A4500.
- **Shared HF cache:** checkpoints were not deleted between models, because sibling runs share the cache.

## Layout

| Path | What |
|---|---|
| `method.py` | Driver (`--run-all`) + builds `method_out.json` (exp_gen_sol_out schema; 3 datasets: SCORE-400 generations, all-SCORE s, C4 induction) |
| `src/data_build.py`, `src/mt_nllb.py`, `src/mt_alpaca.py`, `src/mt_compare.py` | RefusEU pairing/split/SCORE-400 + alpaca sample; NLLB MT (used); gemini MT (run after key restore, comparison only) |
| `src/make_protocol.py`, `src/make_addendum.py` | Protocol freeze (sha256) and m addendum + post-freeze deviations |
| `src/common.py` | NF4 loading, decoder finder, per-row steering hook, exact-length bucketing (no padding), KV-reuse s scorer, lexicon |
| `src/smoke_test.py` | Unit + tiny-model tests (hook exactness, α=0 identity, fp32 cache≡concat) → `results/smoke_test.json` |
| `src/base_geometry.py`, `src/base_stats.py` | Base residuals (all 49 layers) → directions, cross-fitted layer, d′, probes, harm-z, style check |
| `src/instruct_run.py` | Own/lang-ID directions, N̄, CONSTRUCT-100 R, s on all SCORE, SCORE-400 R, C4 induction |
| `src/judge.py`, `src/ledger.py` | gemini-2.5-flash judge, resumable cost ledger (total spend $4.74 of $10 cap) |
| `src/analyze.py`, `src/audit.py`, `src/figures.py` | S1–S5 analysis; independent re-derivation + placebos; figures |
| `src/base_punct_check.py`, `src/quant_check.py`, `src/post_gams_chain.sh` | Exploratory format check; NF4-vs-int8 check; GPU chain |
| `config/` | protocol, addendum, lexicon (Heretic 3521f864 markers + SL), prefixes, resolved revisions |
| `data/` | `refuseu_pairs.jsonl`, `alpaca_harmless.jsonl`, `screen_item_manifest.json`, `dose_table_stage0b.json` |
| `results/base_{pt,gb}[_meanpool]/` | directions.npz, layer_stats.json, item_proj.jsonl, resid_index.jsonl; `results/base_{pt,gb}/resid_L22_part_00{1,2}.npy` = raw last-token residuals at L_pt, split into two parts (<50 MB each), used by `src/audit.py` |
| `results/inst_{gemma,gams}/` | own_dirs.npz, s_score.jsonl, r_score400.jsonl, r_construct100.jsonl, induction.jsonl, norm_profile.json, quant_check.json |
| `results/shared/` | random_dirs.npy, judge_labels.jsonl, kappa.json, openrouter_ledger.jsonl |
| `results/analysis/` | analysis.json (all statistics), audit.json, punct_check.json |
| `figures/` | fig1 base layer curves; fig2 induction dose–response (lexicon, judge); fig3 flip-threshold ECDF; fig4 y vs g; fig5 forest |

All kept artifacts are at `./results/`, which is small (<100 MB).

## Run

```bash
uv venv .venv --python=3.12
uv pip install --python .venv/bin/python -r requirements.lock --extra-index-url https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match
.venv/bin/python method.py --run-all   # or run the src/ steps in the order listed in method.py
```

Each GPU step is resumable (a stage is skipped if its output file exists). The judge resumes from `results/shared/openrouter_ledger.jsonl`.

## Restoring removed files

- `.venv/` (regenerable): `uv venv .venv --python=3.12 && uv pip install --python .venv/bin/python -r requirements.lock --extra-index-url https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match`
- `src/__pycache__/` (regenerable): Python bytecode cache; it is recreated automatically when any `src/` script is next run (e.g. `.venv/bin/python src/analyze.py`).
- `scratch/resid_*.npy` (deleted: four 4.7 GB fp32 all-layer residual caches over GitHub's 100 MB limit; `src/base_stats.py` and `src/base_punct_check.py` need them and raise a clear error if they are absent; the audit uses the kept L22 split parts). Regenerate: `.venv/bin/python src/base_geometry.py --model pt && .venv/bin/python src/base_geometry.py --model gb && .venv/bin/python src/base_geometry.py --model pt --pool mean --tag _meanpool && .venv/bin/python src/base_geometry.py --model gb --pool mean --tag _meanpool`
- Model weights (run-wide shared HF cache, not in this workspace): `huggingface-cli download google/gemma-3-12b-pt --revision 295efb63d01a7017928f273a94ebb86105c9526f`, `cjvt/GaMS3-12B --revision 46127695de173a5de72e1da9dc43846f58553477`, `google/gemma-3-12b-it --revision 96b6f1eccf38110c56df3a15bffe176da04bfd80`, `cjvt/GaMS3-12B-Instruct --revision 1d0b27af5748784482600d24779409e7e1dc9adc`, `facebook/nllb-200-distilled-1.3B`.
