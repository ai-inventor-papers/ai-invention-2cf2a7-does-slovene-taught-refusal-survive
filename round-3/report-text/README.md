# gen_report_text — Iteration 3

Internal research report for "Why Slovene refusal outlasts English abliteration."

## What this step does

Carries forward the iteration 1-2 report verbatim and appends five new artifact
sections covering iteration 3's experiments, then updates the closing summary.

## What changed in iteration 3

1. **Evaluation 2**: Re-judged experiment 8's 24,000 responses with Qwen3-14B and Mistral-Small-24B. The lexicon transfer-curve intercept of -2.36 reproduces; under the validated judge the integrated gap is -1.95.
2. **Experiment 9**: Fresh 300-item probe with DeBERTa judge. Lambda-curve transfer-curve intercept = -0.97, beyond the pre-registered margin.
3. **Experiment 10**: Mechanism test. English and Slovene refusal directions are nearly collinear (cos 0.986-0.991). Both the geometry and the induction hypotheses are refuted.
4. **Experiment 11**: FINAL confirmation on reserved split. Transfer-curve intercept = -0.60, verdict ESTIMATE (support rule failed). Hungarian behaves like Slovene under abliteration.
5. **Experiment 12**: Utility control via lm-eval on 6 tasks. No catastrophic Slovene skill damage.

## File layout

- `paper_draft.md` — full report covering iterations 1-3 (24 tables, 5 figures, 15 artifact markers)
- `references.bib` — bibliography (24 entries, fetched via Semantic Scholar)
- `domain_terms.json` — 62 domain terms for terminology validation
- `style_exemplars.md` — writing style reference from five exemplar papers
- `.aii/manifest.yaml` — workspace manifest
- `.terminal_claude_agent_struct_out.json` — structured output for pipeline integration

## How to run

This step is a text-generation step with no executable code. The report is
assembled from the previous iteration's report and the five artifact result
files listed in `.aii/manifest.yaml` under `depends_on`.

To regenerate, re-run the `gen_report_text` step of iteration 3 in the AI
Inventor pipeline with the same artifact inputs.
