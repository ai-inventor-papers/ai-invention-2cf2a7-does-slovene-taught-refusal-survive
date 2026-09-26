# gen_full_paper — report_results

> Phase: `gen_paper_repo` · `gen_full_paper`
> Run: `gen_paper_repo_8de3f5a10f38` — Over-Refusal of Benign Slovene Prompts in Gemma-3-12B Is a Criterion Shift
>
> Full, verbatim record of every prompt the AI Inventor pipeline gave this agent — system-user, human-user and skill-input — in the order they landed. Nothing truncated.

## Task: `gen_full_paper` (terminal_claude_agent)

### [1] HUMAN-USER prompt · 2026-09-25 23:17:58 UTC

```
[Message from staff account 'staff', not the run's owner]

Keep the title, headline, numbers and grading. Fix these points, checking each against the round record (eval5's criterion_shift.md for the first two):

1. Abstract and p4: the 8 of 9 count covers compliance-valid rows across exp5, eval2, exp9, exp15 and exp14, not "rows in Experiment 5". eval5 uses a harmonised sign in which the headline reads -0.52. Say "8 of 9 compliance-valid rows across five analyses point the same way as the headline (a post-hoc count)", and do not write "CIs below zero" next to +0.52.
2. p7: exp14/eval4 -1.56 is computed Gemma minus GaMS3. Its sign is flipped only by that convention; eval5 counts it as agreeing with the headline. Drop "opposite sign" and "does not replicate".
3. p7: drop "Half of Gemma's Slovene non-compliance is deflection". Of the n = 50 high-dose harmful replies, 54% are explicit refusals and 26% deflections.
4. p7: Experiment 9 uses 300 items per model and language at lambda = 0 and 100 at each edited step, as in the Fig. 3 caption.
5. p7: +0.47 [-0.96, 2.14] includes zero. Call the baseline-versus-edit question inconclusive.
6. p4: for the edited-model contrast (exp11 DiD_c 0.14 [-0.78, 1.12]), say it is inconclusive, not that "the criterion difference disappears".
7. Limitations: add that the exp5 XSTest-only DiD_c is 0.10 [-0.13, 0.35], so the effect is carried by the OR-Bench items.
8. Layout: fix the lines that run into the margin (p9 about 32 pt, p7 about 14 pt). Do not leave a figure-only page mostly blank. Make the CI text inside the dark Fig. 2 cells readable.

Report findings as measurements and what they mean for evaluation, with no operational recommendation for removing refusals.
```

### [2] SYSTEM-USER prompt · 2026-09-25 23:32:47 UTC

```
<CRITICAL_ERROR>
The module-end file check FAILED (attempt 1/3).

PROBLEMS:
  - .aii/manifest.yaml: 'paper.pdf' matches nothing that needs a decision — remove it (text, code and files under the auto-keep floor are always kept)
  - .aii/manifest.yaml: 'paper.aux' matches nothing that needs a decision — remove it (text, code and files under the auto-keep floor are always kept)
  - .aii/manifest.yaml: 'paper.bbl' matches nothing that needs a decision — remove it (text, code and files under the auto-keep floor are always kept)
  - .aii/manifest.yaml: 'paper.blg' matches nothing that needs a decision — remove it (text, code and files under the auto-keep floor are always kept)
  - .aii/manifest.yaml: 'paper.log' matches nothing that needs a decision — remove it (text, code and files under the auto-keep floor are always kept)
  - .aii/manifest.yaml: 'paper.out' matches nothing that needs a decision — remove it (text, code and files under the auto-keep floor are always kept)

FIX IT:
1. Add one entry per uncovered path to `.aii/manifest.yaml` (create it if missing).
   Every path is RELATIVE TO YOUR CWD and must resolve inside it. Globs and
   whole directories are fine — a whole `hf_cache/` is ONE entry.

   entries:
     - path: results/
       keep: six GPU-hours of sweep output, not reproducible in this run
     - path: hf_cache/
       delete: redownloadable
       source: "huggingface-cli download meta-llama/Llama-3-8B"
     - path: checkpoints/
       delete: regenerable
       source: "uv run train.py --epochs 3"

   `keep:` takes a one-line reason. `delete:` takes `redownloadable` or
   `regenerable` and a `source:` that brings the files back.
2. Make sure `README.md` reads like a GitHub repository README: what you did,
   the layout (a line per important file/dir), how to run it, and a
   "Restoring removed files" section with the command for EVERY delete entry.
3. Text and code files never need a decision, and neither does anything under
   the auto-keep floor. Only large binaries and cache directories do.
</CRITICAL_ERROR>
```
