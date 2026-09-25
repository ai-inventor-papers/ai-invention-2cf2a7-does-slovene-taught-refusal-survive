# gen_report_text — Iteration 4

Internal research report for the cross-lingual abliteration lag study comparing
GaMS3-12B-Instruct and Gemma-3-12B-IT, two sibling checkpoints from
google/gemma-3-12b-pt that diverge in safety-supervision language.

## What this step does

Writes the lab-notebook report (`paper_draft.md`) covering four iterations of
experiments. Iteration 4 added a paid-judge readout completion, a 2x3x3
input/output language mechanism test, a fine-grained lambda ladder, and a
prior-art fact check. Fifteen reviewer corrections from the iteration 3 review
were applied as in-place markers throughout the earlier sections.

## File layout

| File | Description |
|---|---|
| `paper_draft.md` | Full lab notebook, iterations 1-4 (~1208 lines, 31 tables, 7 figures, 19 artifact markers) |
| `references.bib` | BibTeX bibliography (33 entries, fetched via aii-semscholar-bib) |
| `references.json` | Fetch provenance record for each reference |
| `domain_terms.json` | Domain terminology dictionary for consistency checking |
| `style_exemplars.md` | Style exemplars extracted from nearest-neighbour papers |
| `.terminal_claude_agent_struct_out.json` | Pipeline structured output (title, abstract, 7 figure specs, summary) |
| `.aii/manifest.yaml` | Artifact manifest with entries |

## How to run

This step is run by the AI Inventor pipeline (Step 3.4: GEN_REPORT_TEXT).
It reads artifact outputs from sibling `gen_art_*` directories under
`iter_4/gen_art/` and from prior iterations' reports, then writes the report
into this directory.

No external dependencies beyond the pipeline environment. The bibliography
is built with the `aii-semscholar-bib` skill (Semantic Scholar / OpenAlex /
Crossref lookups).

## Restoring removed files

All files in this directory are text. No files were removed.
