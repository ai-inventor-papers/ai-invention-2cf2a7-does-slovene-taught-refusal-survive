# Iteration-3 audit of the research record (review_report)

This directory holds the adversarial audit of the run's internal research report (iterations 1-3,
GaMS3-12B-Instruct vs Gemma-3-12B-IT, English-objective Heretic abliteration in English/Slovene).

## What was done
- Read the report and walked every artifact it cites (14 artifacts across `iter_1..iter_3/gen_art/`).
- Opened each iteration-3 artifact's result files (`results/analysis.json`, `results/RESULTS*.md`,
  `results/summary_tables.md`, `READOUT_REPAIR.md`, `results/eval_results.json`) and compared every
  headline number and table with the report. Spot-checked iteration 1/2 numbers (exp4 G3, exp8 readout).
- Recomputed the sign of the exp11 three-way GEE interaction by hand from the McNemar rates.
- Checked the nearest published neighbours for the positive claims (Aziz et al. 2026; Upadhyaya & Sikdar 2026).

## Layout
- `.terminal_claude_agent_struct_out.json` — the structured review (scores, critiques, verdict flags).
- `README.md` — this file.
- `.aii/manifest.yaml` — disposable-output manifest (empty: nothing heavy was written).

## How to run
Nothing to run. The review is a static JSON document produced by reading the artifacts named above.

## Restoring removed files
No files are marked `delete`, so there is nothing to restore.
