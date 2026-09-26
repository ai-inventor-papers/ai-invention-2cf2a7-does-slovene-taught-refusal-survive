# Over-Refusal of Benign Slovene Prompts in Gemma-3-12B Is a Criterion Shift

A 12-page research paper applying signal-detection theory (SDT) to multilingual over-refusal in safety-aligned language models. The study compares Gemma-3-12B-IT with GaMS3-12B-Instruct using controlled abliteration experiments.

## Repository Layout

| File / Directory | Description |
|---|---|
| `paper.tex` | LaTeX source |
| `paper.pdf` | Compiled 12-page PDF (primary output) |
| `references.bib` | BibTeX bibliography (26 entries, each with venue or arXiv ID) |
| `references.json` | Fetch record for each bibliography entry (written by the fetch script) |
| `figures/` | Pre-generated vector figures (PDF) |
| `figures/fig_sdt_v0.pdf` | Figure 1: SDT decomposition — false-alarm rate and criterion by model and language |
| `figures/fig_grid_v0.pdf` | Figure 2: 3x3 crossed-grid refusal-rate heatmaps for Gemma and GaMS3 |
| `figures/fig_dose_v0.pdf` | Figure 3: Dose-response curves of refusal rate vs abliteration strength |

## Building the PDF

```bash
pdflatex -interaction=nonstopmode paper.tex
pybtex paper.aux
pdflatex -interaction=nonstopmode paper.tex
pdflatex -interaction=nonstopmode paper.tex
```

Requires: `pdflatex` (TeX Live), `pybtex` (`pip install pybtex`).

## Restoring Removed Files

LaTeX auxiliary files (`paper.aux`, `paper.bbl`, `paper.blg`, `paper.log`, `paper.out`) are regenerable. To restore them, run the full build sequence above.
