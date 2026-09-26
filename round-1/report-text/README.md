# gen_report_text — Iteration 1

Internal lab-notebook report for the study "GaMS3 vs Gemma-3: Bilingual Refusal Suppression and Mechanistic Analysis."

## Files

| File | Description |
|---|---|
| `.terminal_claude_agent_struct_out.json` | Structured output (title, abstract, paper_text, figures, summary) |
| `report.md` | Full report text in markdown |
| `references.bib` | BibTeX bibliography (24 entries) |
| `style_exemplars.md` | Writing style exemplars from 5 reference papers |
| `domain_terms.json` | 61 domain-vocabulary terms with glosses and sources |
| `.aii/manifest.yaml` | Pipeline manifest |

## Artifacts covered

1. **Dataset** (art_EG6OpEkGvysx): RefusEU splits, supervision dose audit, translation-equivalence discovery
2. **Experiment 1** (art_hKWkjbNTydu_): Main refusal DiD screen, dose contrast D, identity calibration, MT arm
3. **Experiment 2** (art_NLTHj-fHEaG3): Base-model geometry (ALT-2 killed), ancestor-direction induction (C4 failure branch)
4. **Experiment 3** (art_3GJzU9GuyW5r): Persona-gate test (ALT-3 killed), teacher-identity substitution finding
5. **Experiment 4** (art_A_ALQ08RqTgB): Heretic abliteration, transfer curve, excess KL (C5a reverses), prefill signature (ALT-4 not survived)

## Key findings

- Main claim vs ALT-1: **inconclusive** (dose contrast MDE 1.5–1.9 log-odds)
- ALT-2 (base geometry): **dead**
- ALT-3 (persona gating): **dead**
- ALT-4 (thin gate): **not survived** (asymmetry too large)
- C1 (identity): **pass** (DiD_id = 3.22)
- C3 (frozen-core transfer): **fails both ways** (GaMS3 more exposed, G3 = −1.76)
- C5a (excess SL KL): **reverses** (ratio below 1 in both models)
