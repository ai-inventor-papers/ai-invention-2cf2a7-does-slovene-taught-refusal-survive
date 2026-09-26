# Prompts

Complete, auto-generated record of **every prompt the AI Inventor system gave each agent** across this run — generated at repository-upload time so it captures all steps. For the full conversation (assistant turns, thinking, tool calls and results) see the sibling `../messages/` folder.

- Run: `gen_paper_repo_8de3f5a10f38` — Over-Refusal of Benign Slovene Prompts in Gemma-3-12B Is a Criterion Shift

Each prompt is labelled by type and timestamped, with its full untruncated body:

- **SYSTEM-USER** — the pipeline-generated role/instruction prompt placed in the user slot.
- **HUMAN-USER** — the task / human-typed message into the agent stream.
- **SKILL-INPUT** — a skill the agent loaded; its `SKILL.md` instructions, verbatim.

Layout mirrors the run's module tree: one folder per high-level phase, a `round_N/` per iteration where the phase iterates, then each module — a single-task module is one `.md` file, a parallel module (gen_plan / gen_art / gen_viz / gen_demo_art) is a folder with one `.md` per task.

## Index

- **1. report_results** — `gen_paper_repo`
  - `1_gen_full_paper/` — 3 task(s)
    - `chat/prompts/1_report_results/1_gen_full_paper/gen_full_paper.md` — 2 prompts
    - `chat/prompts/1_report_results/1_gen_full_paper/gen_paper_site.md` — 2 prompts
    - `chat/prompts/1_report_results/1_gen_full_paper/gen_report_doc.md` — 2 prompts
  - `chat/prompts/1_report_results/2_gen_html_demo.md` — 3 prompts
