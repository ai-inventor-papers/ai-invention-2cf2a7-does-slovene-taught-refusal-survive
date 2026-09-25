"""Build research_extended.json: saturation_log parsed from evidence/ logs + hand-written decisions,
claims_table, diff_vs_iter4, external_facts, method_specs, assumption_corrections.
Run from the workspace root:  python3 analysis/build_extended.py"""
import json, re, glob, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
EV = ROOT / "evidence"

# ---------- saturation log (queries) ----------
DECISIONS = {
    "Q1": "OpenAlex noise; only Shen 2024 [4] relevant (already on file). 0 new includes.",
    "Q2": "Noise (general LLM papers). 0 includes.",
    "Q3": "Noise. 0 includes.",
    "Q4": "Noise (SLA 'input/output' pedagogy). 0 includes.",
    "Q5": "MLingualFC (VLM, input-language) excluded: no output-language factor. 0 includes.",
    "Q6": "Noise (content-language pedagogy). 0 includes.",
    "Q7": "RefusEU [20] (on file); RAND anti-refusal tampering report excluded (no language factor). 0 new includes.",
    "Q8": "Noise. 0 includes.",
    "Q9": "Zhang 2605.17173 [7] (on file). 0 new includes.",
    "Q10": "Noise. 0 includes.",
    "Q11": "Noise. 0 includes.",
    "Q12": "No Slovene safety paper found. 0 includes.",
    "Q13": "ATR-2026-01903 output-language hijack rule [47] INCLUDED as positioning (prompt-injection, not safety study).",
    "Q14": "Practitioner blogs only. 0 includes.",
    "Q15": "Guard-model papers (Qwen3Guard, PolyGuard, IndicGuard, TWGuard) screened by title; none measures judge error by reply language on edited models. 0 includes.",
    "Q16": "OpenAlex noise. 0 includes.",
    "G1": "General engine; Deng/Sandwich already on file. 0 new includes.",
    "G2": "General engine; 0 new includes.",
    "G3": "No abliterated Slovene/Hungarian/Croatian model or study. 0 includes.",
    "G4": "0 includes.",
    "AX1": "INCLUDED Nguyen et al. 2608.26186 [2] (full 2x2 prompt x response, benign). 2608.18089 (African LRL refusal anchoring, input-side) excluded.",
    "AX2": "24 hits screened; all input-side or English-only abliteration work; BabelSteering/MINIONESE/TF-RefusalBench on file. 0 new includes for the narrowed claim.",
    "AX3": "INCLUDED Addagada 2609.08373 [1] (forced output language + StrongREJECT-style endpoint). Screened 2608.18131, 2608.13695, 2608.14626, 2609.22144 (grep: no output-language factor). 2607.14480 [31] INCLUDED for Lane 2d.",
    "AX4": "Noise. 0 includes.",
    "AX5": "2607.14480 [31] (judge language bias) INCLUDED for Lane 2d; Nemotron 3.5 CS moderator excluded (guard model, no reply-language factor).",
    "AX6": "Query matched 'GAM' (additive models); re-run as AX6b.",
    "AX6b": "Only GaMS3 paper 2603.01691 [16] relevant (no safety evaluation). 0 new includes.",
    "AX7": "0 hits.",
    "AX8": "Nguyen 2608.26186 again; others on file. 0 new includes.",
    "AX9": "Nguyen 2608.26186 again; 0 new includes.",
    "AX10": "Noise. 0 includes.",
    "AX11": "2607.05842 (same-lineage aligned vs abliterated, English vulnerability analysis) screened by grep: no output-language factor; excluded. 2609.05241 (uncensored redistribution) excluded.",
    "AX12": "2609.04653 (language mode for reasoning, not safety) excluded; 2608.26186 / 2609.08373 again.",
    "AX13": "INCLUDED Yamaguchi et al. 2412.11704 [15] for Lane 2c (chat-model language adaptation, safety = toxicity/truthfulness).",
    "AX14": "PLLuM 2511.03823 (has a safety-evaluation section, no base-vs-adapted refusal comparison found by grep) excluded; 2607.13568 (Polish adaptation + refusal steering on entity familiarity) excluded (not harmful requests).",
    "AX15": "Addagada 2609.08373 again. 0 new includes.",
}
ENGINE = {"Q": "aii-web-tools scholarly (OpenAlex/Crossref) or general (keyless)", "G": "aii-web-tools general (keyless engines)",
          "AX": "arXiv API (export.arxiv.org) via aii-web-tools fetch"}

sat = []
for f in sorted(glob.glob(str(EV / "search_logs" / "*.txt"))):
    name = pathlib.Path(f).stem
    txt = open(f).read()
    for m in re.finditer(r"^# (\S+) (\w+) :: (.*)$", txt, re.M):
        seg = txt[m.end(): txt.find("\n# ", m.end()) if txt.find("\n# ", m.end()) > 0 else len(txt)]
        n = len(re.findall(r"^\s*\d+\. ", seg, re.M))
        sat.append({"id": name, "date_utc": m.group(1), "engine": f"aii-web-tools {m.group(2)}", "query": m.group(3),
                    "hits_screened": n, "decision": DECISIONS.get(name, "screened; 0 includes")})
for f in sorted(glob.glob(str(EV / "grep_fetch_logs" / "AX*.txt"))):
    name = pathlib.Path(f).stem
    txt = open(f).read()
    m = re.match(r"# (\S+) (\S+)", txt)
    n = len(re.findall(r"http://arxiv\.org/abs/\d{4}\.\d{4,5}v\d+", txt))
    q = re.search(r"search_query=([^&\s]+)", m.group(2))
    sat.append({"id": name, "date_utc": m.group(1), "engine": ENGINE["AX"], "query": q.group(1) if q else m.group(2),
                "hits_screened": n, "decision": DECISIONS.get(name, "screened; 0 includes")})
# built-in WebSearch calls (not logged by script; recorded by hand)
for q, d in [
    ('arXiv 2026 jailbreak "response language" "prompt language" crossed harmful output language refusal', "No crossing paper; 2605.18239, 2511.00689, 2505.17306 on file. 0 includes."),
    ('"respond in" target language jailbreak attack success output language multilingual LLM 2026', "Sandwich [10] on file; 2606.11202 grep: input-side detection only; 2602.16346 grep: 0 output-language hits. 0 includes."),
    ("abliterated model multilingual refusal evaluation non-English languages 2026 arXiv", "RefusEU [20]; TF-RefusalBench (on file); Abliteration-Eval blog [51] INCLUDED as grey literature (5 input languages, no output factor)."),
    ("language-adapted LLM continued pretraining safety degradation refusal compared to base instruct model 2026", "No paper comparing a language-adapted sibling's refusal to its base instruct model found. 0 includes."),
    ('"relevance curse" "harmfulness curse" multilingual LLM 2026 output quality harmful low-resource', "Shen [4] origin of the terms; Addagada [1] again."),
    ("continued pretraining language adaptation erodes safety alignment refusal instruct model Swallow OR SEA-LION OR EuroLLM OR PLLuM OR Salamandra safety evaluation", "Domain-FT safety-erosion papers only; no language-adapted sibling refusal comparison. 0 includes."),
    ('"Dual-Track Red Teaming" Traditional Chinese localized LLMs safety base model comparison', "Could not locate the paper (title only in S2 citer list); UNVERIFIED, not cited."),
    ("GaMS3 Slovenian LLM safety evaluation refusal harmful prompts GaMS-Safety", "Only the GaMS3 card [17]; no external GaMS safety evaluation exists."),
    ("GlotLID OR OpenLID Slovenian Croatian confusion language identification F1 slv hrv bos srp", "GlotLID [37], OpenLID-v3 [38] INCLUDED for 3f."),
    ("language identification South Slavic Croatian Serbian Bosnian Slovene discrimination fastText lid.176 error", "OpenLID-v3 again; no published slv-vs-hrv confusion for lid.176 found (UNVERIFIED)."),
    ("reporting guidelines LLM-as-a-judge evaluation 2026 sensitivity specificity calibration set per-stratum confidence intervals inter-annotator agreement checklist", "Lee [27]; Fiedler 2605.06939 [28] INCLUDED (checklist); 2601.05420 screened by abstract only."),
]:
    sat.append({"id": "WS", "date_utc": "2026-09-25", "engine": "built-in WebSearch (general web)", "query": q, "hits_screened": 9, "decision": d})
# citation hop
sat.append({"id": "CIT", "date_utc": "2026-09-25", "engine": "Semantic Scholar graph API citations (via aii-web-tools fetch)",
            "query": "2026 citers of arXiv:2401.13136 (Shen), arXiv:2310.06474 (Deng), arXiv:2310.02446 (Yong); diffed vs iteration-4 hop logs (2608.29936, 2505.17306, 2608.11146, 2606.01196, 2607.10112)",
            "hits_screened": 163,
            "decision": "163 unique 2026 citers screened by title; 13 grepped in full text (2605.23157, 2608.02665, 2609.10594, 2609.01210, 2601.22620, 2605.01224, 2608.01436, 2608.21985, 2609.14870, 2609.06573, 2605.00689, 2602.16660, 2606.08451). INCLUDED 2609.10594 [25] (evaluator comparison) for 3a; others excluded (no reply-language factor or no safety endpoint). Addagada [1] also appears among Deng citers."})
sat.append({"id": "S2KW", "date_utc": "2026-09-25", "engine": "Semantic Scholar keyword search API",
            "query": "4 queries (prompt/response language jailbreak; output language harmful ASR; abliteration multilingual; language-adapted safety)",
            "hits_screened": 0, "decision": "NOT COVERED: HTTP 429 rate limit after 3 retries per query."})

ext = json.load(open(ROOT / "analysis" / "extended_static.json"))
ext["saturation_log"] = sat
ext["meta"]["n_saturation_entries"] = len(sat)
json.dump(ext, open(ROOT / "research_extended.json", "w"), indent=1, ensure_ascii=False)
print("wrote research_extended.json with", len(sat), "saturation entries")
