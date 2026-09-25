#!/usr/bin/env python3
"""method_out.json (exp_gen_sol_out): one example per item x lang_arm (k0), grouped by set.

input  = the user prompt shown to every system (byte-identical);
output = the TEACHER's (Qwen3-235B-A22B) judge label = the reference the ALT-5 test compares against;
predict_<system> = that system's label under the readout of results/analysis.json (REFUSE / PARTIAL / COMPLY; ID set:
self-name label). Headline readout = SUBSTITUTE local judge (Mistral-Small-24B NF4, same frozen P1 prompt, all systems),
because the run budget blocker stopped the primary gemini judge before it reached the teacher/outgroup rows; the primary
gemini label is kept per system as metadata_gemini_label_<system> wherever it exists (local systems, H cells).
predict_gams is 'our' system under test, predict_gemma the shared-base sibling baseline, predict_out the outgroup
placebo, predict_q14 the same-family positive control. metadata_* = responses and second-family labels.
All summary statistics go in the top-level metadata (copied from results/analysis.json)."""
from __future__ import annotations

import json
from collections import defaultdict

from common import DATA, GENS, LABELS, RESULTS, ROOT, SYSTEMS, read_jsonl, sha256_file


def main() -> None:
    items = {i["item_id"]: i for i in read_jsonl(DATA / "items.jsonl")}
    bt = {r["item_id"]: r for r in read_jsonl(DATA / "h_en_bt.jsonl")}
    gens = {}
    for s in SYSTEMS:
        for r in read_jsonl(GENS / f"{s}.jsonl"):
            gens[r["key"]] = r
    A0 = json.loads((RESULTS / "analysis.json").read_text()) if (RESULTS / "analysis.json").exists() else {}
    local = A0.get("readout_key", "local") == "local"
    l1 = {r["key"]: r for r in read_jsonl(LABELS / ("refusal_local.jsonl" if local else "refusal_gemini.jsonl"))}
    l2 = {r["key"]: r for r in read_jsonl(LABELS / "refusal_gemini.jsonl")} if local else \
        {r["key"]: r for r in read_jsonl(LABELS / "refusal_gpt41.jsonl")}
    lid = {r["key"]: r for r in read_jsonl(LABELS / ("idname_local.jsonl" if local else "idname.jsonl"))}
    l2name = "gemini_label" if local else "gpt41_label"
    groups = defaultdict(dict)
    for k, g in gens.items():
        if g["condition"] not in ("k0", "pre_comply5", "pre_neutral"):
            continue
        groups[(g["set"], g["item_id"], g["lang_arm"], g["condition"])][g["system"]] = g
    ds = defaultdict(list)
    names = {"H": "hard_dev_xstest_orbench", "R": "refuseu_score400", "ID": "identity_items"}
    for (set_, iid, arm, cond), per in sorted(groups.items()):
        it = items[iid]
        prompt = bt[iid]["en_bt"] if (set_ == "H" and arm == "en_bt") else it["arms"][arm]
        labs = lid if set_ == "ID" else l1

        def lab(s):
            g = per.get(s)
            if not g:
                return "NOT_RUN"
            if g.get("blocked_generation"):
                return "PROVIDER_BLOCKED"
            return (labs.get(g["key"]) or {}).get("label", "UNLABELLED")
        ex = {"input": prompt, "output": lab("q235")}
        for s in SYSTEMS:
            ex[f"predict_{s}"] = lab(s)
        ex["metadata_item_id"] = iid
        ex["metadata_lang_arm"] = arm
        ex["metadata_condition"] = cond
        ex["metadata_prefix"] = next((g.get("prefix", "") for g in per.values() if g.get("prefix")), "")
        for key in ("source", "is_harmful", "hazard", "mt_fragile", "category", "type"):
            if key in it:
                ex[f"metadata_{key}"] = it[key]
        for s in SYSTEMS:
            g = per.get(s)
            if g:
                ex[f"metadata_response_{s}"] = g.get("response", "")
                if set_ != "ID" and g["key"] in l2:
                    ex[f"metadata_{l2name}_{s}"] = l2[g["key"]]["label"]
                if set_ != "ID" and g["key"] in l1:
                    ex[f"metadata_judge_src_{s}"] = l1[g["key"]].get("judge_src")
        ds[names[set_] + ("" if cond == "k0" else "_prefill")].append(ex)
    A = json.loads((RESULTS / "analysis.json").read_text()) if (RESULTS / "analysis.json").exists() else {}
    meta = {"method_name": "ALT-5 teacher-inheritance screen: GaMS3-12B-Instruct vs its Qwen3-235B-A22B SFT teacher",
            "systems": {"predict_gams": "cjvt/GaMS3-12B-Instruct (NF4, system under test)",
                        "predict_gemma": "google/gemma-3-12b-it (NF4, shared-base sibling baseline)",
                        "predict_q14": "Qwen/Qwen3-14B (NF4, same-family positive control)",
                        "predict_q235": "qwen/qwen3-235b-a22b via OpenRouter (teacher; also 'output')",
                        "predict_out": "meta-llama/llama-3.3-70b-instruct via OpenRouter (unrelated outgroup)"},
            "readout": A0.get("readout"),
            "readout_note": "predict_* = labels under the analysis.json readout; the pre-registered primary judge "
                            "(gemini-2.5-flash) covers only the local systems (metadata_gemini_label_*), see README",
            "protocol_sha256": (RESULTS / "protocol_sha256.txt").read_text().split()[0]
            if (RESULTS / "protocol_sha256.txt").exists() else None,
            "items_sha256": sha256_file(DATA / "items.jsonl"),
            "workspace": str(ROOT),
            "verdicts": A.get("verdicts"),
            "headline": {k: A.get("T1", {}).get("H_en_orig", {}).get(k) for k in
                         ("n_core", "refusal_rate_core", "fpcal_dk", "dk", "n", "t1b_dk_q235_minus_out", "d_agree",
                          "d_pabak")},
            "analysis_file": "results/analysis.json (all statistics)"}
    out = {"metadata": meta, "datasets": [{"dataset": k, "examples": v} for k, v in ds.items() if v]}
    (ROOT / "method_out.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float))
    print({k: len(v) for k, v in ds.items()})


if __name__ == "__main__":
    main()
