# gen_report_text — Iteration 5

Internal research report for the cross-lingual abliteration lag study comparing
GaMS3-12B-Instruct and Gemma-3-12B-IT, two sibling checkpoints from
google/gemma-3-12b-pt that diverge in safety-supervision language.

## What this step does

Writes the lab-notebook report (`paper_draft.md`) covering five iterations of
experiments. Iteration 5 added a C-OUT confirmation on a fresh body with PPI
correction, RefusEU FINAL with 1,300 prompts per cell, an R-INCAP safety
evaluation answering whether Gemma's Slovene reserve is real safety or production
failure, a paper-number audit, and an updated novelty check that downgraded the
Lane-1 verdict from NOVEL to PARTIALLY OCCUPIED.

## File layout

| File | Description |
|---|---|
| `paper_draft.md` | Full lab notebook, iterations 1-5 (~1680 lines, 35 tables, 9 figures, 24 artifact markers) |
| `references.bib` | BibTeX bibliography (39 entries, fetched via aii-semscholar-bib) |
| `references.json` | Fetch provenance record for each reference |
| `domain_terms.json` | Domain terminology dictionary for consistency checking |
| `style_exemplars.md` | Style exemplars extracted from nearest-neighbour papers |
| `.terminal_claude_agent_struct_out.json` | Pipeline structured output (title, abstract, 9 figure specs, summary) |
| `.aii/manifest.yaml` | Artifact manifest with entries |

## How to run

This step is run by the AI Inventor pipeline (Step 3.4: GEN_REPORT_TEXT).
It reads artifact outputs from sibling `gen_art_*` directories under
`iter_5/` and carries forward the previous iteration's `paper_draft.md`.
