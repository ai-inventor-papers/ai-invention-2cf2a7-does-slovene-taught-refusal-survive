# Over-Refusal of Benign Slovene Prompts Survives English De-censoring in Gemma-3-12B

Research paper measuring language-dependent over-refusal in Gemma-3-12B-IT versus its Slovene-adapted sibling GaMS3-12B-Instruct, using signal-detection theory and controlled abliteration.

## Key Finding

Unedited Gemma-3-12B-IT false-refuses benign Slovene prompts at a rate of 0.569 compared to 0.364 in English. Signal-detection analysis attributes this entirely to a criterion shift (DiD_c = +0.52 [0.38, 0.68]) with no sensitivity difference, replicated across four experiments.

## Files

| Path | Description |
|------|-------------|
| `paper.tex` | LaTeX source |
| `paper.pdf` | Compiled PDF (11 pages) |
| `references.bib` | Bibliography (25 entries, fetched via Semantic Scholar) |
| `references.json` | Bibliography fetch record |
| `figures/fig_sdt_v0.pdf` | Signal-detection parameters (Figure 1) |
| `figures/fig_grid_v0.pdf` | Crossed prompt-language x reply-language heatmaps (Figure 2) |
| `figures/fig_dose_v0.pdf` | Dose-response curves (Figure 3) |
| `page_screenshots/` | PNG renderings of each PDF page at 150 DPI |

## Compilation

```bash
pdflatex -interaction=nonstopmode paper.tex
bibtex paper
pdflatex -interaction=nonstopmode paper.tex
pdflatex -interaction=nonstopmode paper.tex
```
