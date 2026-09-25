# Review of the iteration-5 internal research report (GaMS3 vs Gemma-3 bilingual refusal)

This directory holds the adversarial audit (step 3.5, REVIEW_REPORT) of the run's iteration-5 internal report.

## What was done
- Read the report, then walked the iteration-5 artifacts: experiment 16 (C-OUT confirmation), experiment 17 (RefusEU FINAL / RQ2),
  evaluation 4 (R-INCAP), evaluation 5 (number audit) and research 2 (novelty). The run's own generated tables were compared
  with the report: `results/RESULTS_tables.md`, `RESULTS.md`, `verdicts.json`, `decomposition_table.md`,
  `ceiling_sensitivity.md`, `criterion_shift.md`, `owed_tables.md` and `ledger_summary.md`.
- Headline numbers were recomputed by hand from the artifacts' own per-cell tables:
  - the exp17 ASR deltas;
  - exp16 OUT_Gemma, from its PPI-corrected S rates;
  - eval4 OUT_U, from its per-cell U rates;
  - the exp16 SDT DiD. This one showed that the report's "Gemma minus GaMS3" label is a within-Gemma contrast.
- Checked each MUST-FIX item from the previous review against the new text.

## Layout
- `.terminal_claude_agent_struct_out.json`: the structured review (scores, critiques, flags).
- `.aii/manifest.yaml`: the disposable-outputs manifest. It is empty because nothing heavy was written.
- `README.md`: this file.

## How to reproduce
The review reads the artifact workspaces listed in the report's supplementary materials, read-only. No code was run
beyond small inspection commands, and nothing was generated.

## Restoring removed files
Nothing is marked `delete`, so there is nothing to restore.
