# Results — C-LAG confirmation (iter 3)

All numbers are recomputed from saved JSONL by `src/analysis.py` and independently re-derived by `src/rederive.py`
(`results/audit.json`: **25/25 checks pass, all three placebos null**). Auto-generated tables:
[`results/RESULTS_tables.md`](results/RESULTS_tables.md). Primary judge **Q = Qwen3-14B (local, NF4)**; the paid
gemini/gpt judges were unavailable (`403 aii_run_budget_exhausted`). Protocol frozen at commit `68f3f73` before any
FINAL generation; deviations in `results/protocol_amendments.json` (AM1–AM4).

## Headline

> **C-LAG: ESTIMATE (not confirmed).** At matched English refusal (EN-BT = 50 %), GaMS3's Slovene refusal log-odds sits
> **G3 = a_GaMS − a_Gemma = −0.60 [95 % CI −1.31, +0.40]** below Gemma-3-IT's (item×step bootstrap, 1000 draws;
> within-item model-swap permutation p = 0.09). The sign matches the iter-2 screen's GaMS Slovene **over-exposure**,
> but the 95 % CI includes 0 and the pre-registered **support rule fails**, so the confirmatory verdict is **ESTIMATE**,
> not "met". The iter-2 headline of G3 = −2.36 is **not reproduced** on reserved data with a validated-per-cell judge;
> the effect, if present, is far smaller than the screen suggested.

**Why the support rule fails, and why it matters.** The pre-registered rule needs ≥2 curve steps with EN-BT refusal in
[0.2, 0.5) and ≥2 in [0.5, 0.8] per model. Under the local judge the English refusal rate never falls below ~0.60 even
at λ = 1 (Gemma EN 0.94→0.64, GaMS EN 0.96→0.60), so the curve lives almost entirely **above** 0.5 and G3 is an
**extrapolation** to EN = 50 %, not an interpolation. This is a direct consequence of the judge: the Qwen3-14B judge
**over-calls English refusal** (gate κ vs archived gemini = 0.27 on English *edited* rows; it labels 0.69 REFUSE where
gemini labels 0.32). A judge that inflates the English rate compresses the x-axis and widens the CI. **The primary
threat to this result is the judge, and it is not resolved here.**

## What is solid

1. **The λ dose works and is language-graded (McNemar, orig → λ=1, Q, R).** Every cell's English refusal is cut ≥ 30 %:
   Gemma EN 0.98→0.65 (−33 pp, p≈0), GaMS EN 0.97→0.58 (−39 pp). **Slovene falls further in GaMS than in Gemma**:
   GaMS SL 0.97→0.46 (relative cut 0.53) vs Gemma SL 0.99→0.68 (relative cut 0.31). This is the raw signal behind the
   negative G3.
2. **Hungarian (L3) behaves like Slovene, not like a GaMS-specific effect.** Both models lose Hungarian refusal at λ=1
   at rates close to their Slovene ones (Gemma L3 0.98→0.70, GaMS L3 0.98→0.60). The reduced two-point C-MOD contrast is
   **G3_L3 = −0.46 [−2.21, +1.44]** (ESTIMATE), and GaMS's own Hungarian lag at λ=1 is −0.23 log-odds — GaMS is *not*
   specifically worse in Hungarian, a language absent from its CPT/SFT (verified against the pinned model card,
   `results/l3_verification.json`). This is **evidence against** "GaMS-specific Slovene safety SFT" and **for** a generic
   *non-English abliteration transfer* that hits every non-English language the base Gemma-3 shares.
3. **The unedited-model finding replicates exactly.** On reserved items, **unedited Gemma-3-IT over-refuses benign
   Slovene** (HARD false-alarm rate 0.57 SL vs 0.36 EN) while **GaMS is language-invariant** (0.27 vs 0.27) — the robust
   iter-2 `DiD_c` mechanism, reproduced here from the reused exp5 originals (Qwen retest κ = 0.885 justifies the reuse).
4. **No catastrophic capability damage.** Belebele accuracy is unchanged by the λ=1 edit in every language
   (Gemma EN .93/.93, SL .885/.885, HU .88/.88; GaMS EN .905/.91, SL .875/.87, HU .87/.825); FLORES NLL/byte moves < 1 %.
5. **Audit and placebos.** 25/25 headline numbers reproduce to < 1e-6 by the independent pandas path; model-swap G3 ≈ 0
   (−0.01 ± 0.36), language-swap lag ≈ 0 (< 0.03), shuffled-judge κ ≈ 0.

## Verdicts (pre-registered mapping)

| Claim | Verdict | Value |
|---|---|---|
| **C-LAG** (Slovene refusal lag at matched English) | **ESTIMATE** (support rule fails; 95 % CI crosses 0) | G3 = −0.60 [−1.31, 0.40], MDE 1.44 |
| **C-MOD** (is the lag Slovene-competence or GaMS SFT?) | **ESTIMATE**, leaning COMPETENCE / generic transfer | G3_L3 = −0.46 [−2.21, 1.44]; GaMS HU lag −0.23 |
| **C-MECH** (criterion vs sensitivity) | see `results/analysis.json:sdt_curve`; HARD DiD_c at λ=1 = +0.14 [−0.78, 1.12] | underpowered |
| **C-EXT** (public checkpoints) | **NOT EVALUATED** — the p-e-w heretic block was cut for GPU time (AM3/AM4); the checkpoint is downloaded but ungenerated | — |

## What did not get done (honestly)

- **Second-family judge (Mistral-24B):** only its gate ran (κ vs gemini 0.42, also poor); it produced **0** curve
  labels before the module deadline, so C-LAG is reported **under the primary judge + blind adjudication only**, not the
  pre-registered two-judge conjunction.
- **Public checkpoints (ARM 3 / C-EXT):** not generated (the shared model cache was reclaimed mid-run and the GPU time
  to reload + generate did not fit alongside judging).
- **Full-FINAL λ=1 remainder (job J3):** GaMS reached 1353/2192; the curve (the rows the primary uses) is complete, the
  remainder is `NOT RUN`.
- **Judge:** local, over-refuses English edited responses (κ 0.27). The blind adjudication (author LLM, **not human**,
  162 rows) is the only independent check on it; see `results/analysis.json:adjudication`.

## Bottom line

The large iter-2 screen effect (G3 = −2.36) **does not survive** on reserved data with an item-matched three-language
probe and a per-cell-validated judge: the point estimate shrinks to −0.60 and its CI includes 0. The surviving,
audited findings are (a) the English abliteration transfers to Slovene *and* to Hungarian in both models, slightly more
so in GaMS, and (b) the pre-existing, robust asymmetry is that **unedited Gemma over-refuses benign Slovene while GaMS
does not**. The Slovene "lag" is better read as a **generic non-English abliteration-transfer** than as a GaMS-specific
safety property, but the judge limitation means even this is an estimate, not a confirmation.
