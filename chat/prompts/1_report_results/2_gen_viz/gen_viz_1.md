# gen_viz_1 — report_results

> Phase: `gen_paper_repo` · `gen_viz`
> Run: `gen_paper_repo_8de3f5a10f38` — Why Slovene refusal outlasts English abliteration
>
> Full, verbatim record of every prompt the AI Inventor pipeline gave this agent — system-user, human-user and skill-input — in the order they landed. Nothing truncated.

## Task: `gen_viz_1` (terminal_claude_agent)

### [1] SYSTEM-USER prompt · 2026-09-25 07:48:38 UTC

````
<research_methodology>
Create figures that belong in a top-venue paper.

- Every figure needs a clear takeaway visible at a glance.
- Choose chart types that match the data relationship (comparisons, trends, correlations, distributions).
- Include uncertainty (error bars, confidence intervals) when showing experimental results.
- Keep it clean — no clutter, clear labels with units, readable at print size.
</research_methodology>

<system_reminder>
Do not ask follow up questions and do not ask the user anything. Execute all steps independently.
You must follow the todo list provided in each prompt exactly as written.
No placeholders, stubs, or incomplete code — all code must be complete and functional.
</system_reminder>

<process_isolation>
CRITICAL: Multiple pipeline runs may execute simultaneously on this machine. `ps aux | grep method.py` matches ALL runs, not just yours.
- NEVER kill processes by name (`killall`, `pkill -f`, `ps aux | grep ... | xargs kill`). This kills OTHER runs' processes.
- NEVER monitor processes by name (`ps aux | grep method.py`). You will see other runs' processes and get confused.
- ALWAYS use PID-based process management:
  Run: `uv run method.py & PID=$!` or `timeout <seconds> uv run method.py & PID=$!`
  Check: `kill -0 $PID 2>/dev/null && echo "Running" || echo "Ended"`
  Stop: `kill $PID`
  Wait: `wait $PID; echo "Exit code: $?"`
  Monitor: `tail -f logs/run.log & TAIL_PID=$!` then `kill $TAIL_PID` when done
</process_isolation>

<workspace>
Your workspace: `/ai-inventor/aii_data/runs/run_UESxYRggGt7E/4_gen_paper_repo/_3_gen_viz/gen_viz_1`

CRITICAL: Every file you create, write, or save MUST be inside this workspace directory (subdirectories OK). You MUST NOT write files anywhere outside this path — external paths are READ-ONLY. Use absolute paths for all file operations.

EVERY file write MUST start with `/ai-inventor/aii_data/runs/run_UESxYRggGt7E/4_gen_paper_repo/_3_gen_viz/gen_viz_1/`:
GOOD: `/ai-inventor/aii_data/runs/run_UESxYRggGt7E/4_gen_paper_repo/_3_gen_viz/gen_viz_1/file.py`, `/ai-inventor/aii_data/runs/run_UESxYRggGt7E/4_gen_paper_repo/_3_gen_viz/gen_viz_1/results/out.json`
BAD: `/tmp/file.py`, `~/output.json`, `./file.py`, any path outside the workspace
</workspace>
<disposable_outputs>
YOUR WORKING DIRECTORY IS A DELIVERABLE. When this module ends it must read
like a GitHub repository someone else can fork, resume and run — and the bulk
it holds must be either worth keeping or restorable. This run shares a storage
volume with the database; a run that fills it stops every other run on the box.

So before you finish, produce TWO files:

1. `.aii/manifest.yaml` — one entry per heavy path, each with EXACTLY ONE decision.
   The `.aii/` directory ALREADY EXISTS in your cwd: write the file into
   it. Do not create, replace or `touch` `.aii` itself — a plain file by
   that name makes the manifest unwritable for the rest of the module.

```yaml
entries:
  - path: results/
    keep: six GPU-hours of sweep output, not reproducible inside this run
  - path: hf_cache/
    delete: redownloadable
    source: "huggingface-cli download meta-llama/Llama-3-8B"
  - path: checkpoints/
    delete: regenerable
    source: "uv run train.py --epochs 3 --seed 0"
```

   - `keep:` takes a ONE-LINE reason. Use it for the expensive and the
     irreproducible: trained weights, long-running results, datasets you
     collected yourself.
   - `delete:` takes `redownloadable` (and a `source:` naming the repo id, URL
     or command) or `regenerable` (and a `source:` that is the command which
     rebuilds it). These are deleted AFTER the round ends, never mid-step.
   - Every path is RELATIVE TO YOUR CWD and must resolve INSIDE it. Absolute
     paths, `..`, and anything resolving outside are rejected.
   - Globs and whole directories are fine. A whole `hf_cache/` is ONE entry —
     do not list files individually.

2. `README.md` — written as if your cwd were a GitHub repository: what you
   did, the layout with a line per important file/directory, how to run it,
   and a **"Restoring removed files"** section giving the install/download
   command for EVERY `delete` entry. An `install.sh` or `restore.sh` beside it
   is welcome.

A CHECKER RUNS WHEN YOU SUBMIT. If anything heavy has no decision it fails
your submission and hands you the uncovered list, grouped by directory with
sizes, and you fix the manifest and submit again.

WHAT NEEDS NO DECISION — do not write entries for these:
- text and code files, at ANY size (source, JSON, CSV, YAML, logs, markdown);
- anything under the auto-keep floor (10 MB), whatever it holds.
Only large binaries and cache directories (`hf_cache/`, `.venv/`,
`node_modules/`, `checkpoints/`, `wandb/`, `__pycache__/`, …) need one.

NEVER mark your results, figures, papers, code, logs or anything a later step
reads as `delete`. If a later step needs it, it is a `keep`.

WHAT A `keep` BUYS YOU. Anything you do not mark `delete` stays exactly where
you wrote it, on this run's storage volume, at the path it already has — it is
not moved, renamed or copied. A later round reads it there, by that absolute
workspace path, so a checkpoint you keep is a checkpoint the next round can
load instead of retraining. It is also the ONLY copy: the publish step pushes
your cwd to GitHub but skips every file of 100 MB or
more, so trained weights and large binary artifacts never leave the volume.
Name each kept artifact in your results and your `README.md` by its path
RELATIVE to your cwd, and say it stays on the run's volume rather than in the
published repository. Never write an absolute server path into a file that is
published: a reader's machine has none of them.
</disposable_outputs>

<task>
Generate a publication-quality figure for a top-tier venue research paper that exactly follows the provided specification.

Use the aii-concept-fig-gen skill to generate the figure in the aspect ratio from the spec. ALWAYS pass `--model sunburst --style neurips` to EVERY concept_fig_gen.py call (this run uses the **sunburst** image tier). `--style neurips` appends the paper style — white background, sans-serif labels, no 3D or shadows or gradients — so the tool carries it on every call instead of you having to remember it in every prompt. Be as detailed as possible in your image generation prompt: include all data values, axis labels, ranges, legend entries, preferred colors, and describe where each element should be positioned. Then END the prompt with a separate sentence listing the words that must appear, verbatim — "The boxes read Tokenizer, Transformer, Classifier." Naming them inside the layout sentence instead is what turns Encoder into `Enc:der`; every measured run that stated them as their own closing sentence spelled all of them correctly, and word length made no difference either way.

IMPORTANT — Two-phase workflow: explore cheaply at 1K, then finalize at 2K. Create a subfolder `fig_overview_all/` in your workspace for ALL attempts. NOTE if `sunburst` is `sunburst`: it ignores `--image-size` entirely and always renders at its own maximum quality and size regardless of which phase asks for it — this is by design (Sunburst is meant to always be the best a figure gets), but it means "explore cheaply at 1K" is not literally cheaper on this tier, so budget for the tier's real per-image price, not a discounted draft price, across every attempt in both phases.

PHASE 1 — Explore at 1K (HARD LIMIT: 5 attempts):
- Generate at `--model sunburst --image-size 1K` (fast and cheap). Save attempts as `fig_overview_all/fig_overview_v0_it1.jpg`, `fig_overview_all/fig_overview_v0_it2.jpg`, … up to `_it5.jpg`.
- After EACH attempt, read the image back and verify it against the checklist below. If it has issues, regenerate with a corrected prompt.
- Do AT MOST 5 generations in this phase — stop early as soon as one is clean. Then pick the single best 1K attempt (the "chosen base").

PHASE 2 — Finalize at 2K (EXACTLY 2 upscale passes of the chosen base):
- Run EXACTLY TWO generations at `--model sunburst --image-size 2K`, each in edit mode passing the chosen base as the input image (`--edit` the chosen base .jpg). Instruct it to upscale and sharpen while preserving the exact layout, data values, labels, and composition — and to fix any remaining issues from the checklist.
- Save them as `fig_overview_all/fig_overview_v0_2k_1.jpg` and `fig_overview_all/fig_overview_v0_2k_2.jpg`.
- Read both back, verify both, and choose the better of the two as the final figure.
- IF THE GENERATOR REFUSES EDIT MODE — on a $0 run the free image provider has no
  edit endpoint at all, and the tool says so ("the free image variant cannot edit
  an existing image") before spending anything — then SKIP this phase entirely and
  deliver the best PHASE 1 attempt. Do NOT pass `--paid` to get around it: that puts
  paid image spend on a run chosen to be free, which is the single largest line item
  a "free" run has ever been billed.

DELIVERABLE:
- Copy the chosen final image to your workspace root as: fig_overview_v0.jpg — the
  chosen 2K upscale when phase 2 ran, and the chosen 1K attempt when it could not.
- The file `fig_overview_v0.jpg` is the deliverable — everything in `fig_overview_all/` is reference only.

Verification checklist (apply after EVERY generation in BOTH phases). Check for:
- Layout issues (e.g. text too close together, figure looks cluttered, elements crammed into corners)
- Overlapping or touching labels, legends, or annotations
- Cut-off or truncated text, axis labels, or titles
- Wrong or missing data values, bars, lines, or data points
- Incorrect axis ranges, tick marks, or scales
- Missing or misplaced legend entries
- Blurry text, unreadable font sizes, or poor contrast
- Wrong font family (MUST be sans-serif like Helvetica/Arial — reject any serif fonts like Times New Roman)
- MISSPELLED labels. Read every word in the image letter by letter against the word you asked for. This is the most common defect by a wide margin — `erooder` for Encoder, `routter` for Router, `conveged?` for converged? — and it is the one that survives a glance, because the shape of the word is right
- Invented text you never asked for. A prompt ending "no text of any kind" came back lettered with `Kat q` and fake axis ticks, so absence has to be checked too, not assumed
- A box, arrow or panel that is duplicated, missing, or pointing nowhere, even when every word in the image is spelled correctly

In Phase 1, if ANY issue is found — even minor — do another attempt (within the 5-attempt limit). Do NOT accept a figure with problems as the chosen base.

Change the prompt only when the prompt is what was wrong — a word you never specified, an element you forgot to name. For a defect the prompt already rules out, re-run it UNCHANGED: the same prompt sent twice gave a correct three-box chain once and four boxes with one label repeated the other time. Rewriting a prompt that was already right spends one of five attempts on a variable that was not the cause.
</task>

<figure_specification>
Figure ID: fig_overview
Title: Study Design Overview
Caption: Overview of the experimental design. Two 12B-parameter models (Gemma-3-12B-IT and GaMS3-12B-Instruct) undergo English-objective abliteration at varying doses. The residual refusal is measured on safe and harmful items across languages and decomposed into criterion (threshold) and sensitivity (discriminability) components using signal-detection theory.
Image Generation Description: A concept diagram showing the experimental pipeline. Left side: two model boxes labeled 'Gemma-3-12B-IT' (blue) and 'GaMS3-12B-Instruct' (green), both built on a shared 'Gemma-3 base' foundation. An arrow labeled 'Abliteration edit (LoRA, TPE-optimized)' points from a 'Refusal direction' vector to both models, with a lambda dial showing dose levels (0 to 1.0). Center: the edited models receive test items from two streams: '1,093 safe items' (white) and '349 harmful items' (red), in two languages 'English' and 'Slovene'. Right side: a signal-detection theory diagram showing two overlapping Gaussian distributions (one for safe items labeled 'Noise', one for harmful items labeled 'Signal'), with a vertical criterion line 'c' between them. Two criterion positions are shown: one for English (moderate position) and one for Slovene (shifted left, stricter). Labels: d-prime (sensitivity, distance between distribution means) and c (criterion, threshold position). Below the SDT diagram, the key finding: 'DiD on criterion: +0.52; DiD on sensitivity: ~0'. Clean, academic style with sans-serif labels, white background, muted blue and green color scheme.
Aspect Ratio: 21:9
Summary: Concept diagram showing the two-model abliteration design and the signal-detection decomposition of refusal into criterion and sensitivity components.
</figure_specification>

<critical_requirements>
1. Accurately represent ALL data values described above — include every number mentioned
2. Do NOT invent additional data points beyond what is described
3. Include clear axis labels only if the figure has axes (not for diagrams/flowcharts)
4. FONT: ALL text MUST use sans-serif font (Helvetica/Arial). NO serif fonts (Times New Roman). Always include "Sans-serif font throughout (Helvetica/Arial style, NOT Times New Roman)" in your image generation prompt. This is the #1 most common issue — check it first during verification
5. Publication camera-ready style: white backgrounds, properly formatted axes, no 3D effects/shadows/gradients. Follow aii-concept-fig-gen skill for image generation, prompting best practices, and figure type templates
6. TEXT SPACING: Ensure generous spacing between ALL text labels. Labels MUST NOT overlap or touch. Use large readable font sizes (minimum 12pt equivalent). If labels would overlap, stagger them vertically, use leader lines, or abbreviate. For multi-panel figures, add clear padding between panels
7. RESOLUTION: Explore at 1K (Phase 1), then finalize with two 2K upscale passes of the chosen base (Phase 2) — see the two-phase workflow above. Do NOT use 4K. For multi-panel or detail-heavy figures, use wider aspect ratios to give elements room
8. MANDATORY VERIFICATION: After EVERY generation attempt, read the image and check font first (sans-serif?), then layout, data accuracy, and readability. If anything is wrong, regenerate. Do NOT stop at the first attempt
</critical_requirements>


<evidence_check>
CRITICAL — this run's own final audit says its headline result is NOT supported:
the final review is marked blocking. The figure specification above was written from a paper draft
that may therefore quote numbers no run ever produced.

Before you plot ANY number, find the artifact output file it is supposed to come from
and read the value there. Plot only values you have read back from an artifact output
file. If a value in the specification above is not in any results file — or the results
file holds far fewer examples, methods or conditions than the specification implies —
do NOT invent it and do NOT carry it over: draw only the series the data actually
supports, and say what the figure covers in its caption.

A figure whose bars disagree with the run's own output files is worse than a missing
figure, because nothing downstream can detect it.
</evidence_check>


<comparison_completeness>
If this figure's title, caption or summary names specific checkpoints, models or
variants being COMPARED — "ours vs baseline", "the base and the abliterated model",
"across the three checkpoints" — every one of them named there MUST appear in the
rendered figure as its own bar, curve, point or panel. Before you render, list every
comparator the specification names and check each one off as you draw it. A
comparison figure that quietly drops one of its own named comparators is wrong even
when every bar it does draw is numerically correct — the missing one is invisible to
anyone who was not told to look for it, which is what makes it worse than an
obviously incomplete figure.
</comparison_completeness>


<caption_from_the_rendered_figure>
The caption in <figure_specification> is a DRAFT, written before this figure existed by a step
that never saw it. After your final render, read the final image back and write the figure's
caption into the `caption` field of your output. It replaces the draft caption everywhere this
figure appears: the paper, the report and the paper's website.
- Describe what the image actually shows: what each axis measures, what each colour, marker or
  line style encodes, and what each panel plots, using the image's own labels.
- Name a colour, marker, panel or series only if it is in the image. Where the draft caption and
  the image disagree (colours said to encode models when they encode languages, an axis the panel
  does not plot, a grey series that was never drawn), the image wins.
- Keep what is still true of the draft: the data, the sample size, what the error bars are, and
  the takeaway. Keep it LaTeX-ready in the same form as the draft caption.
- State no number the figure and its data do not carry.
</caption_from_the_rendered_figure>


---

Output the result as JSON to: `./.terminal_claude_agent_struct_out.json`

JSON Schema:
```json
{
  "$defs": {
    "VizExpectedFiles": {
      "description": "Expected output files from viz generation.",
      "properties": {
        "image_path": {
          "description": "Path to the generated figure image file. Example: 'fig1_v0.jpg'",
          "title": "Image Path",
          "type": "string"
        }
      },
      "required": [
        "image_path"
      ],
      "title": "VizExpectedFiles",
      "type": "object"
    }
  },
  "description": "Structured output from viz figure generation agent.",
  "properties": {
    "title": {
      "description": "Figure title in plain, everyday language \u2014 short and jargon-free so a non-expert grasps it at a glance. Aim for about 4-8 words (~40 characters).",
      "maxLength": 90,
      "minLength": 12,
      "title": "Title",
      "type": "string"
    },
    "summary": {
      "description": "Brief summary of the generated figure: what it shows, style, any issues fixed",
      "maxLength": 5000,
      "minLength": 500,
      "title": "Summary",
      "type": "string"
    },
    "caption": {
      "description": "The figure's caption, written from the FINAL rendered image after you read it back, in the same LaTeX-ready form as the draft caption. It replaces the draft caption in the paper, the report and the paper's website. Name only axes, colours, markers, panels and series that are in the image, with what each one encodes there.",
      "maxLength": 2000,
      "minLength": 20,
      "title": "Caption",
      "type": "string"
    },
    "out_expected_files": {
      "$ref": "#/$defs/VizExpectedFiles",
      "description": "Output file you created. Must include the generated figure image path."
    }
  },
  "required": [
    "title",
    "summary",
    "caption",
    "out_expected_files"
  ],
  "title": "VizFigureOutput",
  "type": "object"
}
```

IMPORTANT: this task is NOT complete until `./.terminal_claude_agent_struct_out.json` exists and contains JSON matching the schema above.
````

### [2] HUMAN-USER prompt · 2026-09-25 07:48:38 UTC

```
carry out the research described in the attached “GaMS3 vs Gemma 3: Bilingual Refusal Suppression and Mechanistic Analysis” document and produce a reproducible research repository and a paper based on the experiments you actually complete.

read the entire document before choosing an approach. use it as the primary research specification, distinguishing the frozen core design, required analyses, optional extensions, discussion points for human collaborators, and deferred journal follow-up. briefly state your understanding of these priorities, then proceed with feasibility checks and execution.

the main research questions and intended contribution are already defined. choose the implementation, mechanistic methods, measurements, and controls needed to test them rigorously. verify the document’s factual claims, references, and novelty positioning against primary sources. treat its proposed explanations as hypotheses to investigate, not conclusions to confirm.

treat the core study as the anchor, while leaving room for discoveries that emerge during execution. if pilot results reveal a promising mechanism, unexpected pattern, or weakness in the proposed explanation, investigate it even if the exact experiment is not specified in the document. you may refine hypotheses and add or replace optional analyses when justified by evidence. preserve the core comparison and independent evaluation, and explain why each departure improves the science. prioritize a focused, well-tested insight over accumulating loosely connected experiments.

use scientific judgment to identify methodological weaknesses and resolve implementation choices. make consequential corrections explicit. where the document assigns decisions to a collaborator, make and justify defensible provisional choices so independent work can continue. flag anything that genuinely requires human input or unavailable access. do not claim human review, developer consultation, or access to private checkpoints unless it actually occurred.

adapt execution to the available compute while prioritizing completion of the core study. start with small feasibility checks before scaling up. if a required component is infeasible, explain the blocker and complete the remaining independent work. clearly label any reduced-scope experiment or substitute and its limitations. keep the deferred journal project outside the main run.

keep exploration separate from confirmation. preserve the document’s data-separation rules and freeze the relevant protocol before final testing. actively challenge the strongest explanations using competing hypotheses, simple baselines, and appropriate controls. report uncertainty, failed hypotheses, and negative results. limit causal and generalization claims to what the design supports, and do not present a familiar finding as novel merely because it appears in GaMS or Slovene.

deliver code, pinned dependencies, configurations, data provenance and split manifests, saved experimental outputs and scores, analysis scripts, and a paper whose claims can be traced to those results. distinguish completed findings, exploratory evidence, and unexecuted proposals. recompute every headline number from saved results and, after the final audit, reconcile the abstract, figures, tables, and conclusions so they all reflect the strongest evidence that actually survives.
```

### [3] SKILL-INPUT — aii-concept-fig-gen · 2026-09-25 07:48:48 UTC

The agent loaded the **aii-concept-fig-gen** skill; its `SKILL.md` (the instructions injected into the agent's context) follows verbatim.

````
---
name: aii-concept-fig-gen
description: "Generates and edits CONCEPT FIGURES — architecture and pipeline diagrams, flow charts, cover and hero artwork — with OpenAI GPT Image and Gemini Nano Banana image models through OpenRouter, at a chosen aspect ratio and resolution, free or paid, in parallel batches. Use whenever a figure must be DRAWN because no dataset sits behind it, or an existing image needs editing from a text instruction. Triggers: concept figure, figure_type='concept', architecture diagram, pipeline diagram, flow chart, cover image, conceptual artwork, image generation, image editing, nano banana, gemini image. NOT for: anything with numbers behind it — bars, curves, heatmaps, confusion matrices, scaling laws — which an image model only approximates, so use aii-data-fig-gen; multi-round variant batches are amg-iter-image-gen-human; calling a TEXT model over OpenRouter is aii-openrouter-llms; displaying a file is amg-open-img-ubuntu."
---

# Image Generation & Editing (nano_banana)

> **Not for data figures.** An image model approximates numbers: bars come
> back close to but not equal to their labels, and axis ticks do not divide
> evenly. Nothing downstream detects it. If the figure has numbers behind
> it, use `aii-data-fig-gen`, which renders them deterministically.

Generate images via OpenRouter's dedicated images API (`/api/v1/images`) through the ability server, on four paid tiers tried in order with automatic fallback: `sunburst` (`openai/gpt-image-2.5-sunburst`, Sunburst 2.5, default) → `gpt` (`openai/gpt-5.4-image-2`) → `pro` (`google/gemini-3-pro-image-preview`, Nano Banana Pro) → `flash` (`google/gemini-3.1-flash-image-preview`, Nano Banana 2, the safety net every tier ends on). The `OPENROUTER_API_KEY` lives on the ability server — this skill routes requests through `call_server()`. Inside an AI Inventor run the call still goes to the run's `OPENROUTER_BASE_URL` on the run's own key, so every image counts against the run's OpenRouter budget; past it, generation fails with a message starting "AI Inventor per-run OpenRouter budget".

## Setup

```bash
SKILL_DIR="$(git rev-parse --show-toplevel 2>/dev/null || echo /ai-inventor)/.claude/skills/aii-concept-fig-gen"
G="$SKILL_DIR/scripts/concept_fig_gen.py"
PY="$SKILL_DIR/../.ability_client_venv/bin/python"
```

## Generate Image

```bash
$PY $G --prompt "prompt describing the image" --output output.jpg --aspect-ratio 16:9
```

## Free vs paid — check before you generate

Two billing paths. **You do not normally choose**: the run's backend already
set the default, and the flags below only override it.

| Path | Cost | Editing |
|---|---|---|
| paid (default) | $0.2469/image (sunburst, max quality) | yes |
| `--free` | $0 | no |

The paid path is OpenRouter's `openai/gpt-image-2.5-sunburst` (`--model
sunburst`, the default); `--free` is Cloudflare Workers AI (FLUX / SDXL),
falling back to Hugging Face
`stabilityai/stable-diffusion-3-medium-diffusers` (SD3).

`--free` serves inside Cloudflare's 10,000-neuron **daily** free allocation.
None of the four paid tiers has a free image path, so this is the only
genuinely $0 route.

**None of the four tiers is one price, and `sunburst` is not tiered at all —
it always renders at the maximum.** `sunburst` ignores `--image-size`
entirely and always requests OpenRouter's highest quality setting for this
model (`quality: "max"` — its own catalog gives it an enum
`["auto","low","medium","high","xhigh","max"]` that no other tier has) at the
largest size OpenRouter accepts for the requested `--aspect-ratio` (a
3840px-longest-edge "size", OpenRouter's own ceiling for this model — see
below): $0.2469/image measured live (21:9 → 3840x1648). This is a standing
policy, not a per-call choice: Sunburst is meant to be the best a figure gets,
so it is never asked to render a cheaper draft. `gpt` is ~$0.04/image at 1K
but ~$0.19 at 2K and ~$0.42 at 4K (`size` and `quality: "high"` scale with
resolution — see below, and `gpt` DOES still honour `--image-size`, unlike
`sunburst`). `flash` is ~$0.067/image at 1K but ~$0.101 at 2K, measured live
at $0.1017 for a 2K edit. It matters because the figure step deliberately
uses both 1K and 2K for the non-`sunburst` tiers: it explores at 1K and then
makes exactly TWO 2K passes per figure. `pro` is flat at ~$0.134 across 1K
and 2K.

The paid path has four quality tiers, `sunburst` by default, selected with
`--model` (orthogonal to `--free`/`--paid`), tried in order with automatic
fallback down the chain:

| `--model` | ~Price | Falls back to |
|---|---|---|
| `sunburst` | $0.2469/image, always max/4K | `gpt`, `pro`, `flash` |
| `gpt` | $0.04 / $0.19 / $0.42 (1K / 2K / 4K) | `pro`, then `flash` |
| `pro` | $0.134 / $0.134 / $0.24 (1K / 2K / 4K) | `flash` |
| `flash` | $0.067 / $0.101 / $0.15 | none (it IS the fallback) |

`sunburst`'s 4K/max figure is measured live; its 1K/2K entries in the price
table exist only as area-scaled estimates because current code never
requests them for `sunburst` — a call that falls back off `sunburst` onto
`gpt` after exhausted retries drops the max override and resumes `gpt`'s own
tiered behaviour (including whatever `--image-size` the caller asked for).
Every call reports its real charge back, so the table only ever stands in for
a response that carried no `usage` block.

**You do not normally choose this**: the pipeline sets it from the run's
`gen_paper_repo.gen_viz.image_model` config, and every preset except Lite
picks `sunburst` (Lite keeps `flash`). A call that exhausts its retries on one
tier moves to the next one in
the chain, and every charge the provider reports is recorded — including one
on a response that came back priced and carrying no image, which is a refusal
(quota, moderation) rather than a blank a retry fills in. Such a response is
not asked for again at the same price, and the figure's failure still names
what the body said.

**The two OpenAI tiers ignore `resolution` outright** (verified live: they
return the same pixel dimensions whatever `resolution` tier is sent). Instead
this skill translates the requested size tier into an explicit `size` (pixel
width×height, derived from `--aspect-ratio`, both dimensions rounded to the
nearest multiple of 16 — OpenRouter rejects anything else live with HTTP 400
"Width and height must both be divisible by 16") plus a `quality` field —
`--aspect-ratio` itself is still honoured directly by all four models.
`gpt` uses whatever tier `--image-size` asked for, at `quality: "high"`.
**`sunburst` ignores `--image-size`, always resolving to the "4K" tier at
`quality: "max"`** — the largest size and highest quality OpenRouter accepts
for it, on any aspect ratio, regardless of what `--image-size` said (even a
missing or invalid value); a call that exhausts sunburst's retries and falls
back to `gpt` resumes `gpt`'s own tiered behaviour, not sunburst's max. Every
tier's `size` longest edge is capped at 3840px (OpenRouter's own ceiling: a
4096px request answers HTTP 400), so the "4K" tier renders at a 3840px
longest edge, not 4096. Edit mode (`--edit`) works identically across all
four tiers — the source image rides along the same way regardless of
`--model`.

- **On a free-tier run the default is already `--free`** (the backend exports
  `AII_FREE_TOOLS=1`). Do not pass `--paid` there: six figures on the paid
  path cost $0.81, which was 78% of a measured "free" run's entire bill.
- Pass `--paid` only when you must EDIT an existing image, which the free
  provider cannot do — it takes a prompt with no image input.
- The free path has TWO providers and walks between them. Cloudflare's
  10,000-neuron daily allocation is shared with the free LLM pool, so a busy day
  spends it; the call then fails over to Hugging Face automatically. You do not
  need to do anything for this.
- If BOTH are down the call fails. Do not silently fall back to paid on a free
  run: report it and continue without the figure.

### Free costs you the labels, not just the fidelity

The returned JSON's `model` field says which of the three served the image, and
it is worth reading: they are tiers apart on the thing concept figures are
mostly made of — words in boxes. Same prompt, same day, measured live:

| Model that served it | Diagram | Labels came out as |
|---|---|---|
| paid `gemini-3.1-flash-image-preview` | right | all three correct |
| CF `flux-1-schnell` | right | `Enc:der`, `conveged?` |
| HF SD3 medium | wrong | `erooder`, `routter` |

Three paid runs, three clean figures — every word right, and the flow chart
came back with the NO branch actually looping back, which neither free model
managed once. SD3 went the other way and put text in a figure that asked for
none: a prompt ending "no text of any kind" came back with `Kat q` and
`Wet ker wee Bir Sauh` lettered across it, in red and green as its two main
colours under `--style neurips`. Treat an HF-served image as a draft to check
hard, not a figure to ship.

That is where the $0.067 goes, so spend the verification effort to match: on a
free run read every word in the image letter by letter, and on a paid one look
first for the things a good speller still gets wrong — a stage you do not have,
an arrow the wrong way round.

None of it is checked automatically. `success: true` means a valid JPEG of the
right size arrived — nothing reads the words in it.

## Edit Image

```bash
$PY $G --edit input.jpg --prompt "Make the background blue" --output edited.jpg
```

**Parameters:**
- `--prompt` / `-p` (required) — image description or edit instruction
- `--output` / `-o` (default: `./generated_image.jpg`) — output file path (always saved as `.jpg`; suffix is forced)
- `--edit` — path to source image for editing (omit for generation)
- `--aspect-ratio` (default: `16:9`) — valid: `1:1`, `2:3`, `3:2`, `3:4`, `4:3`, `4:5`, `5:4`, `9:16`, `16:9`, `21:9`
- `--image-size` (default: `1K`) — resolution: `1K`, `2K`, `4K` (on `gpt` this becomes an explicit pixel `size`, not the `resolution` field — see above; `sunburst` ignores this flag entirely and always renders at its own max size)
- `--model` (default: `sunburst`) — paid tier: `sunburst` (`openai/gpt-image-2.5-sunburst`, Sunburst 2.5, always $0.2469/img at max quality/size regardless of `--image-size`, falls back to `gpt` then `pro` then `flash`), `gpt` (`openai/gpt-5.4-image-2`, ~$0.04-0.42/img depending on resolution, falls back to `pro` then `flash`), `pro` (Nano Banana Pro, ~$0.134/img @1K-2K, falls back to `flash`), or `flash` (Nano Banana 2, ~$0.067/img, cheapest, no further fallback). Normally set by the pipeline from `gen_paper_repo.gen_viz.image_model` (every preset except Lite picks `sunburst`); ignored on `--free`.
- `--style neurips` — appends NeurIPS academic style guidance
- `--negative-prompt` — things to exclude from the image
- `--system` — system-level style instruction
- `--timeout` (default: `180`) — the WHOLE call's deadline, and therefore the
  retry budget. Each attempt gets the lesser of 180 s and whatever is left, and
  the loop will not start one it cannot finish: with 180 s and fast failures
  (a connection error, a 5xx) every attempt in the chain runs — up to twelve
  for the default `sunburst` tier (3 attempts on each of sunburst, gpt, pro,
  flash), nine for `gpt`, six for
  `pro`, three for `flash` — while on slow responses it stops and says how
  much budget was left rather than being cut off mid-request. Raise it if you
  want the full budget under slow responses — nine attempts of 180 s would
  need up to 1638 s.

## Parallel Batch Generation

Use GNU `parallel` for multiple images:

```bash
export SKILL_DIR="$(git rev-parse --show-toplevel 2>/dev/null || echo /ai-inventor)/.claude/skills/aii-concept-fig-gen"
export PY="$SKILL_DIR/../.ability_client_venv/bin/python"
export G="$SKILL_DIR/scripts/concept_fig_gen.py"
parallel -j 5 -k --group --will-cite 'eval {}' ::: \
  "\$PY \$G -p \"prompt 1\" -o output_1.jpg --aspect-ratio 21:9" \
  "\$PY \$G -p \"prompt 2\" -o output_2.jpg --aspect-ratio 16:9" \
  "\$PY \$G -p \"prompt 3\" -o output_3.jpg --aspect-ratio 1:1"
```

## Preview

Do **NOT** open generated images in a GUI viewer (`loupe`, `xdg-open`, `eog`,
etc.). This skill is for automated / headless generation (e.g. pipeline figure
steps), and popping image windows clutters the user's desktop. Inspect images
programmatically if needed (read the file, check the returned JSON), not by
opening a viewer.

For interactive, human-curated review of multiple figure variants — where the
user wants to arrow-navigate batches in `loupe` — use the
`amg-iter-image-gen-human` skill instead; loupe-driven review is its job, not
this one's.

## Features

- **Model**: default `openai/gpt-5.4-image-2` (`--model gpt`); `--model pro` selects `gemini-3-pro-image-preview` (Nano Banana Pro); `--model flash` selects `gemini-3.1-flash-image-preview` (Nano Banana 2). Each tier that exhausts its retries falls back to the next one down the chain (gpt → pro → flash)
- **Auth**: API key on ability server (routed via `call_server()`)
- **Retries**: 3 attempts with exponential backoff per tier, then the next tier in the chain — as far as `--timeout` allows, since it is the deadline for the whole call
- **Edit mode**: Edit existing images with text instructions
- **Parallel**: GNU `parallel` with `-j 5` for batch generation
- **Headless**: never auto-opens a viewer (use `amg-iter-image-gen-human` for human review)

## Prompting Tips

- Name every element and where it sits — boxes, arrows, groupings, labels.
  The model places what you describe and invents what you leave out
- **Put the labels in their own closing sentence**, not inline in the sentence
  that describes the layout. "…three boxes joined by arrows. The boxes read
  Tokenizer, Transformer, Classifier." rendered all three words correctly;
  "…three labelled boxes left to right, Encoder, Router, Decoder, joined by
  arrows…" rendered `Enc:der`. Four out of four runs that stated the labels
  as a separate final sentence spelled every one of them right, including the
  same words the inline phrasing had corrupted. Word length was not the
  driver — `Transformer` and `Classifier` both came out clean
- Specify colors, fonts, layout, and what to exclude
- Use `--style neurips` for academic papers. It also pins the figure to the
  same colours every DATA figure in the paper uses — seaborn's `colorblind`
  — and tells the model not to let red-versus-green be the only difference
  between two elements, which is the one pairing that carries no meaning for
  about 8% of male readers
- Any number that DOES appear — a throughput on an arrow, a stage count —
  has to be stated explicitly, and read back off the image to check it
  survived. If the figure is mostly numbers, it is a data figure: stop and
  use `aii-data-fig-gen`, which renders them instead of approximating them
- 1K resolution is default and most reliable

## Figure type templates

An image model draws what you name and invents what you leave out, so the
prompt for each kind of concept figure has a different set of things it
cannot omit. Each entry below names the kind, its usual aspect ratio and those
things; start from the one that matches and add the specifics.

- **Architecture / pipeline diagram** (`21:9`) — every stage in order, left to
  right; what flows along each arrow and which way it points; which stages are
  yours vs. baseline or off-the-shelf; where the boundary of the system sits.
- **Flow chart** (`21:9` or `16:9`) — each decision point and both of its
  outcomes; where a branch rejoins; the start and the terminal states; that
  arrows are labelled, not bare.
- **Side-by-side comparison** (`16:9`) — what the two panels are, in which
  order; that both use the SAME visual vocabulary so only the difference
  differs; a caption strip or heading per panel.
- **Conceptual artwork / cover** (`1:1`, `16:9`) — the single idea in one
  sentence; the metaphor and what maps to what; that no text appears unless you
  asked for it, since invented labels are the usual failure.

Two things every entry shares: state the sans-serif requirement (`--style
neurips` does it for you), and read the image back to check that nothing was
invented — a stage that is not in your pipeline, an arrow that runs the wrong
way, a label you never wrote.

Reading it back is not optional, and re-running is a real fix. The same prompt
sent twice gave a correct three-box chain once and, the other time, four boxes
with `Encoder` in two of them and an arrow pointing at nothing — identical
text, different diagram. So a structure you cannot check by looking is a
structure you do not have; when it comes back wrong, generate it again rather
than editing the prompt, because the prompt was not what failed.

## Aspect Ratios

Pick by shape, not by venue. `--help` lists all ten; these are the ones a
paper figure normally wants.

| Ratio | Use Case |
|-------|----------|
| `21:9` | Ultra-wide — pipelines, architecture, the hero figure |
| `16:9` | Wide — side-by-side comparisons, multi-panel concepts |
| `4:3`, `3:2`, `5:4` | Standard — one diagram with room around it |
| `1:1` | Square — a symmetric diagram, a cover image |
| `9:16`, `3:4`, `2:3`, `4:5` | Vertical — a stacked flow or poster |

**If the ability server is not running**, nothing needs doing: the CLI already
falls back to running the same function in-process, so `concept_fig_gen.py`
works standalone. Verified — with no server reachable it still resolves the
free/paid path and reports its own errors ("OPENROUTER_API_KEY not set")
rather than a connection failure.

What it needs is the deps. If the import fails, install them INTO THE VENV
`$PY` names above — creating a `.venv` in whatever directory you happen to be
standing in leaves `$PY` pointing at the same broken interpreter:
```bash
CLIENT_VENV="$SKILL_DIR/../.ability_client_venv"
uv venv "$CLIENT_VENV" --python=3.12          # only if it is not there yet
uv pip install --python="$CLIENT_VENV/bin/python" \
  -r "$SKILL_DIR/scripts/server_requirements.txt"
```
````

### [4] SYSTEM-USER prompt · 2026-09-25 07:53:36 UTC

```
[Image: original 3840x1648, displayed at 2000x858. Multiply coordinates by 1.92 to map to original image.]
```

### [5] SYSTEM-USER prompt · 2026-09-25 07:55:12 UTC

```
[Image: original 3840x1648, displayed at 2000x858. Multiply coordinates by 1.92 to map to original image.]
```

### [6] SYSTEM-USER prompt · 2026-09-25 07:56:34 UTC

```
[Image: original 3840x1648, displayed at 2000x858. Multiply coordinates by 1.92 to map to original image.]
```

### [7] SYSTEM-USER prompt · 2026-09-25 07:58:06 UTC

```
[Image: original 3840x1648, displayed at 2000x858. Multiply coordinates by 1.92 to map to original image.]
```

### [8] SYSTEM-USER prompt · 2026-09-25 08:00:15 UTC

```
[Image: original 3840x1648, displayed at 2000x858. Multiply coordinates by 1.92 to map to original image.]
```

### [9] SYSTEM-USER prompt · 2026-09-25 08:00:15 UTC

```
[Image: original 3840x1648, displayed at 2000x858. Multiply coordinates by 1.92 to map to original image.]
```
