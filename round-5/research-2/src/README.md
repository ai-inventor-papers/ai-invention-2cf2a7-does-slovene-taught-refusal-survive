# Novelty and fact check for the reply-language claim (iteration 5)

This is a web-only research artifact dated **2026-09-25**, with $0 LLM spend. It re-runs the novelty gate for the narrowed lead claim of the GaMS3-vs-Gemma-3 Slovene refusal study. The claim: an English-only de-censoring edit leaves Gemma-3-12B-IT refusing whenever it must *write* Slovene, while the Slovene-adapted GaMS3 does not.

The artifact also verifies the method specifications and external facts that the four parallel iteration-5 artifacts depend on. It extends the iteration-4 research artifact `art_NZ9n2Ej5RtGt`, which it reads read-only.

## Main findings
- **The novelty lane is PARTIALLY OCCUPIED:**
  - Addagada 2609.08373 forces the output language of an English jailbreak and scores it with a StrongREJECT-style rubric at a 0.5 threshold;
  - Nguyen et al. 2608.26186 cross prompt x response language, but on benign content.
- **Still ours:** crossing both factors with safety endpoints, the sibling pair, the partial-dose edit, Hungarian, and a constant suffix.
- **Claim verdicts:**
  - (a) reply-language reserve: incremental, still a screen;
  - (b) production failure: Shen's relevance curse, so incremental or a replication;
  - (c) GaMS3 baseline deficit: descriptive;
  - (d) judge error matrix: a check.
- **Method specs:**
  - StrongREJECT is unchanged.
  - A RefusEU run must be labelled a re-implementation: the GPT-4o-mini snapshot is unpublished, and the appendix safety prompt is response-only and only inferably the adjudicator's.
  - The Rogan-Gladen / Lang-Reiczigel formulas are extracted exactly. A Youden-J caveat is added (Fiedler 2605.06939): the Gemma-SL-edited cell has J ~ 0.31.
  - Language-ID guidance is included.
- **External facts:**
  - All pinned checkpoints still equal `main`, and `mlabonne` -v2 is 47 GB F32.
  - The GaMS3 cards are unchanged, and the Long-CPT South-Slavic share is 30.2 %.
  - No public abliterated GaMS3 exists.

## Layout
| Path | What |
|---|---|
| `research_report.md` | Main deliverable: saturation statement, related work, novelty paragraph, claims table, method specs, verified facts and corrections, limits, source list. |
| `research_out.json` | Structured output: answer, 52 sources with passages, follow-ups. Auto-saved from `.terminal_claude_agent_struct_out.json`. |
| `research_extended.json` | `lane1_verdict`, `claims_table`, `saturation_log` (49 dated entries), `diff_vs_iter4`, `external_facts`, `method_specs`, `assumption_corrections`. |
| `reproducibility.md` | How the search was actually run: order, tools, queries, env-var names. |
| `analysis/build_extended.py` | Rebuilds `research_extended.json` from the logs plus `analysis/extended_static.json`. |
| `analysis/extended_static.json` | Hand-written claims, facts, specs and corrections. |
| `evidence/search_logs/` | Timestamped search outputs (Q1-Q16 scholarly/general; G1-G4 general). |
| `evidence/grep_fetch_logs/` | Timestamped fetch/grep outputs: arXiv API listings (`AX*`), paper greps (`L*`, `SN_*`, `V_*`, `PC*`), Semantic Scholar citations (`CIT_*`), WebFetch notes (`WF_*`). |
| `evidence/hf_api/` | Hugging Face API JSON and raw model cards, retrieved 2026-09-25 (`_index.txt` lists the URLs). |
| `evidence/strongreject_head/` | `evaluate.py` and `judge_templates.json` at the StrongREJECT repo HEAD, plus the commit list. |
| `evidence/passage_check/` | fetch_grep checks of every supporting passage. |
| `evidence/*.sh`, `evidence/*.py` | Small wrappers and parsers for the aii-web-tools scripts. |

## How to run
Nothing needs to run to use the results. To rebuild the extended JSON: `python3 analysis/build_extended.py`. To re-run a search: `evidence/s.sh NAME scholarly "query"`. To re-run a fetch or grep: `evidence/f.sh` / `evidence/g.sh`. The wrappers need the aii-web-tools skill environment.

## Restoring removed files
Nothing is marked for deletion (`.aii/manifest.yaml` has `entries: []`). Full-text PDF dumps made during the passage check were deleted rather than kept, and are regenerable with:
`evidence/f.sh NAME https://arxiv.org/pdf/<id> 2000000`.
