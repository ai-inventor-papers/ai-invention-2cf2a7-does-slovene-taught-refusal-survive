# Prior-art check and external facts for the Slovene refusal study (AI Inventor, iteration 4, research lane 1)

A web-only research artifact, run on **2026-09-24**. It settles the novelty gate for the GaMS3-vs-Gemma-3 refusal study and verifies the external facts that the parallel experiments (A/B/C) rely on. It has four parts:

1. A dated saturation search on input-language vs output-language designs.
2. The nearest neighbour and delta for every positive claim.
3. Method specs (StrongREJECT, RefusEU ASR, judge-label correction, Heretic @3521f86).
4. External facts: public abliterated Gemma-3-12B-IT checkpoints with SHAs, Hungarian in GaMS3, and AdvBench overlap of candidate benchmarks.

No OpenRouter or LLM spend. The only computation is a small local lexical-overlap script.

## Headline results
- **No paper crosses prompt language × response language** for refusal/ASR as of 2026-09-24. The design is novel; the mechanism is untested.
- **Heretic @3521f86 has no automatic trial-selection rule.** Selection is interactive over a Pareto front sorted by (refusals, KL), or via `trial_index`. Defaults are 200/60 trials. A pre-registrable rule is given in the report.
- **arXiv 2511.21140 (ICML 2026) adopts Rogan–Gladen**, not PPI++/EIF. The PPI arXiv id is 2301.09633.
- **`mlabonne/gemma-3-12b-it-abliterated-v2` exists.** All candidate checkpoints are pinned to 40-char SHAs.
- **`mlabonne/harmful_behaviors` = AdvBench (520/520).** Deduplicate JBB (14–19) and StrongREJECT (26). HarmBench and RefusEU have 0 overlap.
- **RQ4 AUROC 1.00 is an easy-negative / source-separability result** (cf. arXiv 2609.27758, 2607.13075). Report it as a check.
- **Hungarian is not in GaMS3's DECLARED CPT/SFT mix** (cards + paper). Do not write "absent".

## Layout
| path | what |
|---|---|
| `research_report.md` | Paste-ready report: saturation statement, related work, novelty paragraph, method specs, verified facts/corrections, limits, numbered sources |
| `research_out.json` | Structured output (answer, sources, follow-up questions), written automatically from the final response |
| `research_extended.json` | claims_table, saturation_log, external_facts, method_specs, recommended checkpoints, item-body guidance, assumption_corrections |
| `reproducibility.md` | Exactly how the research was done: queries in order, tools, fetched pages, timestamps |
| `analysis/overlap.py` | Exact + token-Jaccard overlap of Heretic's default harmful prompts (mlabonne/harmful_behaviors) with AdvBench, JBB, StrongREJECT, HarmBench, RefusEU-eval |
| `analysis/overlap_results.json`, `analysis/overlap_threshold_sweep.json` | Outputs of the overlap script |
| `analysis/fetch_data.sh` | Re-downloads the benchmark files (pinned revisions where possible) into `analysis/data/` |
| `analysis/data/` | Downloaded benchmark files (not published; restore with `fetch_data.sh`) |
| `evidence/grep_fetch_logs/` | Raw outputs of every fetch/grep call (header line = UTC timestamp, URL, regex) |
| `evidence/search_logs/` | Scholarly-search outputs (Q1–Q12) and Semantic Scholar citation snowball JSON |
| `evidence/heretic_3521f86/` | Heretic files at the pinned commit (config.default.toml, main.py, config.py, evaluator.py, kl_divergence.py, README.md, pyproject.toml) |
| `evidence/strongreject_7a551d5/` | StrongREJECT `evaluate.py` and `judge_templates.json` at the pinned commit |
| `evidence/hf_cards/` | Model cards (GaMS3 at pinned revisions; abliterated Gemma checkpoints) |
| `evidence/g.sh`, `evidence/f.sh` | Wrappers around the aii-web-tools grep/fetch scripts that write into `grep_fetch_logs/` |

## How to re-run
```bash
bash analysis/fetch_data.sh          # ~6 MB of benchmark files
python3 analysis/overlap.py          # needs pandas + pyarrow
# re-grep any source, e.g.:
bash evidence/g.sh check_lee https://arxiv.org/pdf/2511.21140 "Rogan|Gladen|PPI"
```
The web-tools wrappers need the AI Inventor `aii-web-tools` skill (its venv is at `/ai-inventor/.claude/skills/.ability_client_venv`). Any other fetcher gives the same pages.

## Restoring removed files
Nothing is marked `delete` in `.aii/manifest.yaml`. No file reaches the 10 MB floor. `analysis/data/` is excluded from the published repository because it holds third-party benchmark files under their own licences. Restore it with:
```bash
bash analysis/fetch_data.sh
```
It fetches `mlabonne/harmful_behaviors@01cead01`, AdvBench (llm-attacks), `JailbreakBench/JBB-Behaviors@886acc35`, the StrongREJECT CSV, HarmBench's text-behaviour CSV and `NASK-PIB/RefusEU@5523ce30` (evaluation split).
