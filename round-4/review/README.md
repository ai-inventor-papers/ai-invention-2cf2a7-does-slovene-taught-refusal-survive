# Iteration-4 review of the research report (REVIEW_REPORT step)

This is an adversarial audit of the run's internal research report, which covers iterations 1-4 of the GaMS3-12B-Instruct vs Gemma-3-12B-IT study of Slovene refusal after English de-censoring. The audit checks the report against the saved artifacts of iteration 4 (eval3, exp13, exp14, exp15, research_1) and against the previous review's MUST-FIX list.

## Layout
- `.terminal_claude_agent_struct_out.json`: the review (ReviewerFeedback schema). It has 12 critiques, scores, `results_reported=false` and `blocking=true`.
- `make_review.py`: the script that wrote that JSON. It holds the review text, and every number in it was checked against the artifact files it names.
- `.aii/manifest.yaml`: the disposable-output manifest. It is empty because this directory holds only text.

## Key checks performed (all read-only, against the run's artifact workspaces)
- **exp14:** `results/RESULTS_tables.md` compared with report Tables 28-30. There are mismatches, and the `compliance_gate` table shows the GaMS output-language manipulation failing.
- **eval3:** `READOUT_v2.md` compared with report Tables 25-27. The tables match, but the report's claims about the tipping analysis and about "every readout" contradict the artifact.
- **exp15:** G3_orig recomputed from the per-step counts with Hautus correction, giving -1.17. It is sensitive to 3 items at ceiling.
- **exp15:** the excess KL ratio was recomputed from its KL table at the top dose, giving about 0.96 for Gemma and 0.80 for GaMS.
- **exp13:** this artifact is missing from the report. It lost its GPU, and its tier bake-off gate failed (`results/tier_table.json`).

## How to run
`python3 make_review.py` regenerates the JSON. It writes into the current directory.

## Restoring removed files
Nothing is marked `delete`, so there is nothing to restore.
