# Reproducibility: how this research was actually conducted

- **Executor:** an LLM agent (Claude, Claude Code harness) acting as the GEN_ART research executor for iteration 5.
- **Date:** all new searches and fetches ran on **2026-09-25, between 00:17 and ~01:15 UTC**.
- **Spend:** $0 OpenRouter; no model calls beyond the agent itself.
- **Code:** the only code is `analysis/build_extended.py`, which assembles `research_extended.json` from the logs plus `analysis/extended_static.json`. It also contains small inline parsing helpers (`evidence/parse_ax.py`, `evidence/parse_cit.py`, `evidence/show.py`).

## Tools
- **aii-web-tools scripts**, wrapped in `evidence/s.sh` (search), `evidence/f.sh` (fetch) and `evidence/g.sh` (fetch_grep). Each call writes a timestamped log:
  - `aii_fast_web_search.py --mode scholarly` (OpenAlex/Crossref) or `--mode general` (keyless engines, Serper fallback);
  - `aii_fast_web_fetch.py fetch|grep` (HTML/PDF to text; regex grep with context).
- **Built-in `WebSearch`** (11 queries) and **`WebFetch`** (2 pages: the Abliteration-Eval blog and the Wikipedia Slovene alphabet page, where the fetch script got HTTP 403). These are logged by hand in `research_extended.json` (`saturation_log`, engine "built-in WebSearch") and in `evidence/grep_fetch_logs/WF_*.txt`.
- **Direct JSON APIs** (curl or the fetch script):
  - Hugging Face `https://huggingface.co/api/models/<id>[/revision/<sha>]` and `/api/models?search=`;
  - `https://huggingface.co/api/datasets/NASK-PIB/RefusEU`;
  - GitHub `https://api.github.com/repos/dsbowen/strong_reject/commits`;
  - raw GitHub files;
  - arXiv API `http://export.arxiv.org/api/query?...`;
  - Semantic Scholar graph API `/paper/arXiv:<id>/citations`. Its `/paper/search` endpoint returned HTTP 429 on every retry, so that engine is **not covered**.
- **Env vars** that the web-tools scripts may read (names only): `SERPER_API_KEY`, `EXA_API_KEY`, `LINKUP_API_KEY`, `TAVILY_API_KEY`, `SEARXNG_URL`, `AII_FREE_TOOLS`, `AII_POLITE_CONTACT`, `AII_COST_LEDGER`. The HF/GitHub/arXiv/S2 API calls were anonymous (no tokens).

## Order of work (as run)
1. **Lane 0 (ingest).** Read, read-only, the iteration-4 artifact:
   - `research_report.md`, `research_extended.json` (method_specs), `evidence/search_logs`, `evidence/hf_cards` and `evidence/strongreject_7a551d5`;
   - exp14's `results/novelty_gate.json` and `results/RESULTS_tables.md`.

   Also grepped the computational-linguistics handbook files for JUDGe / 20-dataset / FLORES / base-rate text. The "11/11" figure was not found.
2. **Lane 1a (scholarly).** Q1-Q12 with `--mode scholarly`, run in parallel:
   - Q1 `"respond in" language jailbreak refusal multilingual`
   - Q2 `response language prompt language safety large language model refusal`
   - Q3 `output language harmful compliance multilingual LLM`
   - Q4 `input language output language decomposition refusal LLM`
   - Q5 `attack success rate by output language multilingual jailbreak harmful content`
   - Q6 `StrongREJECT multilingual response language harmful content score`
   - Q7 `abliterated refusal-ablated uncensored model multilingual evaluation`
   - Q8 `language-adapted continued pretraining national LLM safety refusal same base model`
   - Q9 `safety through incompetence low-resource language jailbreak harmful response quality`
   - Q10 `language confusion safety wrong-language response jailbreak`
   - Q11 `multilingual red teaming target language reply language evaluation protocol`
   - Q12 `Slovenian large language model safety refusal`

   OpenAlex results were mostly noise.
3. **Built-in WebSearch (4 queries).** Crossed prompt/response language; "respond in" target language; abliterated multilingual; language-adapted safety.
4. **arXiv API, 2026-06-01..2026-09-30 (AX1-AX8)** plus general queries G1-G4. AX1 surfaced **Nguyen et al. 2608.26186**; AX3 surfaced **Addagada 2609.08373**. The exact query strings are in `research_extended.json` → `saturation_log`.
5. **Lane 1b (full-text greps).** Ran `respond in|answer in|reply in|output language|response language|target language|in English regardless|StrongREJECT|harmful content|refus` on 11 candidates: 2608.26186, 2608.18131, 2608.13695, 2609.08373, 2607.05842, 2608.14626, 2609.22144, 2606.11202, 2602.16346, 2608.07862 and 2608.18089. Deeper greps followed on 2608.26186 and 2609.08373 (design, languages, threshold, language verification).
6. **More arXiv queries (AX6b, AX9-AX12).** Greps of 2609.04653, 2604.18510, 2607.14480, 2608.27548 and 2609.05241.
7. **Lane 1c (version checks).** Grepped the arXiv abs pages for 2401.13136, 2310.06474, 2608.29936, 2607.10112, 2605.25420, 2605.17173, 2404.07242, 2311.09827, 2310.02446, 2606.01196, 2606.07535, 2603.01691, 2511.21140, 2402.10260, 2608.26186 and 2609.08373. Later also 2505.17306, 2608.22490, 2609.27758, 2607.13075, 2606.28843, 2605.31381, 2301.09633, 2311.01453, 2607.14480, 2609.10594, 2602.13139 and 2605.06939.
8. **Lane 1d (citation hop).**
   - Pulled Semantic Scholar citations of 2401.13136, 2310.06474 and 2310.02446, filtered to 2026 and diffed against the iteration-4 hop logs: 163 unique 2026 citers.
   - Grepped 13 candidates in full text: 2605.23157, 2608.02665, 2609.10594, 2609.01210, 2601.22620, 2605.01224, 2608.01436, 2608.21985, 2609.14870, 2609.06573, 2605.00689, 2602.16660 and 2606.08451.
9. **Lane 4 (HF API).**
   - Pinned-revision and main queries for the three abliterated checkpoints, `google/gemma-3-12b-it`, `cjvt/GaMS3-12B-Instruct`, `cjvt/GaMS3-12B`, `facebook/nllb-200-distilled-1.3B`, `meta-llama/Llama-Guard-3-8B` and `ToxicityPrompts/PolyGuard-Qwen`.
   - Model searches `GaMS3`, `GaMS`, `gams-abliterated` and `GaMS3-12B-Instruct-heretic`.
   - Raw README cards were diffed against the iteration-4 pinned copies, and the CPT tables were recomputed per language.
10. **Lane 3.**
    - StrongREJECT: HEAD commits, and `evaluate.py` + `judge_templates.json` diffed against 7a551d5.
    - RefusEU PDF/HTML greps (guards, adjudicator, footnote model URLs).
    - Lee 2511.21140: fetched Section 4-5 (char offset 15300) for the exact equations.
    - PPI version checks.
    - Taxonomy greps (XSTest 2308.01263, SORRY-Bench 2406.14598, Do-Not-Answer 2308.13387, SomaliBench).
    - WebSearch for LID and judge-reporting guidance, then greps of GlotLID 2310.16248 (Table 8 rows), OpenLID-v3 2602.13139, CHALIS 2606.06088 (no hits), Fiedler 2605.06939 (checklist) and the lingua-py README.
    - Inspected exp14's `src/build_items.py` and `results/lid_cache.jsonl` (local) to identify its LID tool and count BCMS labels.
11. **Lane 2 extras.** Queries AX13-AX15 (arXiv relevance, no date filter), plus greps of Yamaguchi 2412.11704, PLLuM 2511.03823, 2607.13568, Hawkins 2606.28843 and Shen 2401.13136 (curse definitions). Tail queries Q13-Q16 (general/scholarly), the JUDGe page, the Bavaresco abs page, the Abliteration-Eval blog (WebFetch) and the ATR-2026-01903 rule page.
12. **Verification.**
    - Recomputed our exp14 numbers from `RESULTS_tables.md`. The judge cell gemma_it|sl|edited has Se 0.89 and Sp 0.42, and the LID cache holds 18,700 rows.
    - A late RefusEU re-grep of the PDF appendix (`L3b6`-`L3b8`, `F_refuseu_prompts*`) found the 'Safety evaluation prompt', which is response-only with the S1-S14 taxonomy. The report and JSON were updated accordingly.
    - Checked every supporting passage with fetch_grep (`evidence/passage_check/`). Nine failed the line-bound grep because of PDF line breaks. All but one were then confirmed in whitespace-normalized full text; the GlotLID table row was found by full-text grep earlier.

## How to retrace
- Re-run the logged queries (`evidence/search_logs/*.txt` headers, and the `AX*` URLs in `evidence/grep_fetch_logs/`) with the same scripts. Search results drift, so compare hit lists with the logged ones rather than expecting identical rankings.
- The decisive sources are stable arXiv ids: 2609.08373v1 and 2608.26186v1 (the new partial occupants), 2511.21140v4 and 2605.06939v1 (estimator), and 2310.16248 (LID).
- HF facts can be re-checked with the API URLs in `evidence/hf_api/_index.txt`.
- `python3 analysis/build_extended.py` rebuilds `research_extended.json` from the logs.
