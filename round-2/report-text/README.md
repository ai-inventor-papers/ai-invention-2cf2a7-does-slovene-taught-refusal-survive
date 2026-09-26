# GaMS3 vs Gemma 3: Bilingual Refusal Suppression

Internal research report (iteration 2) investigating whether Slovene-taught refusal in GaMS3-12B-Instruct survives English abliteration, compared against sibling checkpoint Gemma-3-12B-IT.

## What was done

Two iterations of experiments (ten artifacts total) screened five rival accounts of how refusal transfers across languages in a bilingual model. Experiments covered refusal rates, dose-response by hazard category, signal-detection analysis, Heretic abliteration transfer curves, teacher-inheritance wording analysis, and a reconciliation evaluation.

## Layout

- `paper_draft.md` — full chronological report (iterations 1 and 2, 16 tables, 4 figure markers, 10 artifact markers)
- `references.bib` — BibTeX entries for all 24 cited works
- `style_exemplars.md` — prose style reference passages from the field
- `domain_terms.json` — 61 domain terms with glosses and source titles
- `.aii/manifest.yaml` — artifact manifest with file entries
- `README.md` — this file

## How to use

The report is self-contained Markdown. Read `paper_draft.md` directly. Figure markers (`[FIGURE:fig_id]`) are placeholders for a downstream image-generation step. Artifact markers (`[ARTIFACT:art_id]`) link claims to the code that produced them.

## Key findings

- The dose contrast between low- and high-English-dose hazard categories remains underpowered
- The refusal difference-in-differences is judge-family-dependent (gemini vs Qwen3 disagree on sign)
- GaMS3 retains less Slovene refusal than Gemma under English abliteration (transfer-curve intercept = -2.36)
- GaMS3's refusal wording inherits from Qwen SFT data (76% EN, 91% SL verbatim)
- On HARD items, the models differ in criterion not sensitivity (criterion DiD = +0.52)
