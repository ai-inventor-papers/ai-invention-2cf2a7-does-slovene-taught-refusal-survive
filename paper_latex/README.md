# Paper: Over-Refusal of Benign Slovene Prompts in Gemma-3-12B Is a Criterion Shift

This directory holds the assembled paper and its GitHub Pages site.

## Layout

- `paper.tex` — LaTeX source of the paper
- `paper.pdf` — compiled PDF
- `references.bib` — bibliography
- `figures/` — all figures (PDF originals and rendered PNGs for the web page)
- `index.html` — self-contained public web page (GitHub Pages site)
- `interactive.html` — self-contained explorable companion page: every chart, count and item is drawn from JSON embedded from the run's output files (Experiments 5, 9, 14 and Evaluation 5)
- `workspace/` — scratch folder from the LaTeX compilation step

## Web page

`index.html` is a single self-contained HTML file with inline CSS and JavaScript.
It references figures via relative paths (`figures/*.png`) and links to the paper
PDF, research report, executive summary, round reports, and experiment code
repositories via absolute URLs on the `fork` branch.

Open it locally with any browser; no build step or network connection is needed.

## Restoring removed files

No files were marked for deletion. All content is under 10 MB.
