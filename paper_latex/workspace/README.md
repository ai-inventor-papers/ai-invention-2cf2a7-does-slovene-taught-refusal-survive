# Over-Refusal of Benign Slovene Prompts Survives English De-censoring in Gemma-3-12B

Research paper measuring over-refusal in Gemma-3-12B-IT versus GaMS3-12B-Instruct using signal-detection theory in a controlled abliteration study.

## Key Finding

Unedited Gemma-3-12B-IT false-refuses benign Slovene prompts at nearly twice the English rate (0.569 vs 0.364). This is a pure criterion shift (DiD_c = +0.52 [0.38, 0.68]) with no sensitivity difference, replicated across four experiments.

## Repository Contents

- `paper.tex` -- LaTeX source (11pt, letterpaper, natbib)
- `paper.pdf` -- Compiled PDF (12 pages)
- `references.bib` -- Bibliography (25 cited entries from Semantic Scholar)
- `references.json` -- Fetch record for bibliography entries
- `figures/fig_sdt_v0.pdf` -- Signal-detection parameters: grouped bar chart + forest plot
- `figures/fig_grid_v0.pdf` -- 3x3 heatmaps of crossed prompt x reply-language refusal rates
- `figures/fig_dose_v0.pdf` -- Dose-response curve of refusal rate vs abliteration dose

## Compilation

```bash
pdflatex -interaction=nonstopmode paper.tex
bibtex paper
pdflatex -interaction=nonstopmode paper.tex
pdflatex -interaction=nonstopmode paper.tex
```

## Restoring removed files

No files were removed; the workspace contains only text, code, and small binary files (all under 10 MB).
