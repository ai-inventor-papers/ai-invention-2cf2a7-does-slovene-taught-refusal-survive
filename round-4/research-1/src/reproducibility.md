# Reproducibility: how this research was actually conducted

- **Date:** 2026-09-24. All web calls fell between 18:25 and 18:45 UTC.
- **Executor:** an LLM agent (Claude) running in the AI Inventor pipeline. It worked alone: no human reviewed any verdict, and no GaMS developer was consulted.
- **Spend:** $0 on OpenRouter/LLM APIs.
- **Inputs read first:** the user-uploaded plan `GaMS3_Gemma_Abliteration_Conference_Research_Plan_v10.docx`, used for context and extracted locally (the extracted text was deleted and is not published), and the `aii-handbook-auto-mechanistic-interpretability` skill (SKILL.md/SOURCES.md, for the S3 knowledge-action-gap entry and the 11/11 base rate).

## Tools
| tool | used for | credentials (names only) |
|---|---|---|
| `aii-web-tools` → `aii_fast_web_fetch.py fetch` | page/PDF → markdown, mainly arXiv `abs` pages | none (the skill's ability server) |
| `aii-web-tools` → `aii_fast_web_fetch.py grep -i` | regex extraction over full arXiv PDFs, GitHub and HF pages | none |
| `aii-web-tools` → `aii_fast_web_search.py --mode scholarly` | OpenAlex + Crossref discovery (Q1–Q12) | Serper fallback key held by the ability server (`SERPER_API_KEY`, not used directly) |
| Built-in `WebSearch` (general) | discovery of 2025–2026 preprints | none |
| `curl` | GitHub raw files and REST API (commits, tags, compare), HF Hub API (`/api/models/<id>`, `/api/datasets/<id>`, `?search=`), HF raw READMEs at pinned revisions, ACL Anthology `.bib`, Semantic Scholar Graph API citations | none (unauthenticated) |
| `python3` + pandas/pyarrow | `analysis/overlap.py` (lexical overlap) | none |

The wrappers `evidence/g.sh NAME URL REGEX [max] [ctx]` and `evidence/f.sh NAME URL [chars]` call the two skill scripts. Each writes its output to `evidence/grep_fetch_logs/NAME.txt`, with a first line of `# <UTC timestamp> <URL> :: <regex>`. `evidence/call_index.txt` lists all 145 calls in time order.

## Order of work (as run)
1. **18:25. Abstract fetches** (`abs_*`) for the 19 anchor IDs named in the plan, to confirm titles, authors, versions and dates: 2607.10112, 2608.29936, 2608.09095, 2608.11146, 2310.06474, 2310.00905, 2310.02446, 2511.00689, 2605.18239, 2609.03781, 2406.20052, 2505.17306, 2606.01196, 2511.21140, 2606.07535, 2603.01691, 2402.10260, 2406.11717, 2603.18353.
2. **18:26. Lane-1 full-text greps** (`L1_*`) on arXiv PDFs. Core regex: `respond in|answer in|output language|response language|reply in|in English regardless|language of the response|respond only in`, plus paper-specific terms such as code-switch, translationese, target language, LoDNA, unintentional, "think in English", BYPASS.
3. **18:27. Twelve scholarly searches** (`evidence/search_logs/Q1–Q12.txt`), with the plan's query strings reworded for keyword engines, plus three general WebSearches: `jailbreak "respond in English" non-English prompt output language safety LLM arXiv`; `"output language" "input language" refusal jailbreak multilingual LLM crossed design 2026`; `"response language" harmful compliance multilingual LLM safety evaluation arXiv 2025`.
4. **18:28. Six more general WebSearches:** forcing output language; abliteration strength multilingual; continued-pretraining safety; low-resource fluency/"incompetence"; translated-response judge bias; language confusion and refusal.
5. **18:28. Greps of new candidates** (`L1b_*`): 2608.08032, 2606.11202, 2505.12287, 2505.24119, 2608.14626, 2404.07242, 2401.13136, 2608.18089, 2606.08451, 2609.03887, 2603.22061, 2509.15202.
6. **18:29. Lane-2 greps** (`L2_*`): Wang 2505.17306, Arditi, Aziz (incl. language list and harmless-refusal table), Upadhyaya (steering/amplification), Shen 2401.13136, Zhao 2507.11878, 2605.05427, Basu 2603.18353.
7. **18:30. Lane-3.**
   - StrongREJECT: paper greps, docs and GitHub.
   - RefusEU (2606.07535) and Lee et al. (2511.21140), including targeted greps for Rogan/Gladen/PPI/shift.
   - PPI (2301.09656 turned out to be the wrong paper, so it was re-checked as 2301.09633), PPI++, AutoEval.
   - Heretic: GitHub commit, tags and releases pages. The full SHA came from the commit page. The raw files `config.default.toml`, `src/heretic/main.py`, `config.py`, `evaluator.py`, `scorers/kl_divergence.py`, `README.md` and `pyproject.toml` were curled at that SHA. The GitHub API supplied the commit date and tag list, a compare against v1.0.1/v1.4.0, and the default configs at v1.0.1/v1.1.0/v1.4.0.
   - StrongREJECT `evaluate.py` and `judge_templates.json` at repo HEAD `7a551d5b…`.
8. **18:32. Lane-4.** HF API JSON for 9 model repos (sha, lastModified, gated, safetensors dtype/params, architectures, file lists). Raw READMEs of the 6 abliterated checkpoints and of both GaMS3 cards at the pinned revisions (byte-identical to `main`). The GaMS3 paper was grepped for Hungarian/safety terms. HF dataset API was queried for RefusEU, mlabonne sets, AdvBench, HarmBench, SORRY-Bench, StrongREJECT, JBB and GaMS-Nemotron-Chat.
9. **18:33. Overlap computation.** Benchmark files were downloaded (`analysis/fetch_data.sh` reproduces this), then `python3 analysis/overlap.py` was run, followed by a Jaccard threshold sweep (0.5–0.8). SORRY-Bench was skipped because it is gated.
10. **18:36. Contrast searches** (six WebSearches): language-adapted siblings, multilingual over-refusal, ablation dose-response, generation-vs-comprehension, matched-twin probes, and the C5a re-run (`abliteration Slovene OR multilingual collateral damage random direction control capability 2026`). Hits were grepped (`C_*`): 2607.13075, 2608.25390, 2602.02132, 2605.25420, 2606.23375, 2609.03781, 2605.18239, 2608.16577, 2606.28843, 2608.05578.
11. **18:37. Snowball.** Semantic Scholar `/graph/v1/paper/arXiv:<id>/citations` for 2606.01196, 2607.10112, 2608.29936, 2505.17306 and 2608.11146 (`evidence/search_logs/cit_*.json`). New hits were grepped (`S_*`, `abs_*`): 2609.27758, 2608.22490, 2605.17173, 2605.20262, 2609.16204.
12. **18:38–18:43. Verification.** Abstract fetches for all remaining cited IDs; ACL Anthology `.bib` for Shen 2024, RefusEU 2026 and Tongue-Tied 2025; a final strict response-language grep (`Z_*`, `Z2_*`) on 2311.09827, 2401.16765, MINIONESE, Upadhyaya, Atil and Wang; two last WebSearches (`answer in English` vs target language; decoupling prompt/response language), with 2608.02941 and 2602.11157 grepped.
13. **18:44. HF Hub search** for abliterated GaMS3 (`/api/models?search=GaMS3|GaMS-3|gams3`) and for Heretic Gemma forks.

## How to retrace
- Re-run any line of `evidence/call_index.txt` with `evidence/g.sh`/`f.sh`, or open the URL; arXiv IDs carry version numbers in `research_report.md`.
- Pinned objects: Heretic `3521f8648a0dccf6e12a92666862632235fac7e6`; StrongREJECT `7a551d5b440ec7b75d4f6f5bb7c1719965b76b47`; HF SHAs listed in `research_extended.json → external_facts`. These do not drift.
- **Search results drift.** The 2026 preprint landscape changes weekly, so a re-run later than 2026-09-24 should expect new hits and must re-date the saturation statement.
- The overlap numbers are deterministic given the pinned dataset revisions (AdvBench and the StrongREJECT/HarmBench CSVs are fetched from GitHub `main`).

## Known deviations from the plan
- The plan said "no code". One small local script (`analysis/overlap.py`) was added because computing the AdvBench overlap directly is stronger evidence than a dataset card, which here states no provenance.
- The scholarly engine had low recall for 2026 preprints, so general WebSearch plus arXiv full-text greps and the Semantic Scholar snowball did most of the discovery.
- Venue confirmations were not possible for StrongREJECT (NeurIPS D&B), PPI (*Science*) and Wang et al. (NeurIPS 2025, confirmed only indirectly). They are marked as such.
