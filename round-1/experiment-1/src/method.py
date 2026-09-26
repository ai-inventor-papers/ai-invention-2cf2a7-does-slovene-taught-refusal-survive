#!/usr/bin/env python3
"""Entry point / orchestrator of the MAIN vs ALT-1 screen, and builder of method_out.json (exp_gen_sol_out schema).

Pipeline (each stage is resumable; see README):
  python build_data.py                         # STEP 1  pairs, CONSTRUCT/SCORE split, SCORE-400, shingles
  python build_mt.py && python fix_identity.py # STEP 2  identity items + MT-parallel arm + LaBSE correspondence
  python gpu_pass.py --model gemma_it --phase pilot   # CONSTRUCT-only pilots (T2,T3,T5,T6)
  python test_synthetic.py                     # T8 analysis dry run on synthetic data
  python freeze.py                             # STEP 3  protocol.json + sha256 + git commit (before any SCORE pass)
  python gpu_pass.py --model gemma_it --phase main ; python gpu_pass.py --model gams3_it --phase main   # STEP 4
  python judge_or.py --judge gemini|gpt|idname # STEP 5 gemini-2.5-flash (all) + gpt-4.1-mini (20%) + identity judge
  python gpu_pass.py --model {m} --phase prec8 # 4-bit vs 8-bit check (cut-able)
  python analysis.py                           # STEP 6  results/analysis_results.json + figures
  python method.py                             # method_out.json (this file)
  python audit.py                              # STEP 7  recompute headline numbers from per-item JSONL

"Our method" vs "baseline": the screen contrasts the Slovene-specialised GaMS3-12B-Instruct (predict_gams3_it)
against its same-family control Gemma-3-12B-IT (predict_gemma_it) on identical prompts; the DiD removes prompt
effects. Scorers: frozen bilingual lexicon (spec primary) vs gemini-2.5-flash judge (co-primary) vs continuous s.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from loguru import logger

from common import DATA, MODELS, OUT, ROOT, read_jsonl, setup_logging

RES = ROOT / "results"


def build_examples(items: pd.DataFrame, pairs: dict) -> list[dict]:
    ex = []
    items = items.set_index(["key", "model"])
    keys = sorted({k for k, _ in items.index})
    for key in keys:
        pid, lang, cond = key.split("|")[:3]
        p = pairs[pid]
        prompt = p[f"prompt_{lang}"] if cond == "original" else None
        if cond == "mt_from_en":
            prompt = None
        e: dict = {}
        for mk in MODELS:
            if (key, mk) not in items.index:
                continue
            r = items.loc[(key, mk)]
            e[f"predict_{mk}"] = str(r["response"])
            for col in ("R_lex", "R_lex_tr", "R_judge", "R_judge_partial", "R_gpt", "guard_unsafe", "s", "s_first"):
                v = r.get(col)
                e[f"metadata_{col}_{mk}"] = None if v is None or (isinstance(v, float) and pd.isna(v)) else float(v)
            e[f"metadata_judge_label_{mk}"] = None if pd.isna(r.get("J_gemini")) else r.get("J_gemini")
            e[f"metadata_lang_detected_{mk}"] = r.get("lang_detected")
        if len([k for k in e if k.startswith("predict_")]) < 2:
            continue
        ex.append({"input": prompt if prompt is not None else "(MT-parallel prompt, see data/mt_parallel.jsonl)",
                   "output": f"REFUSE (harmful RefusEU prompt, gold Llama-Guard category {p['category']})",
                   "metadata_key": key, "metadata_pair_id": pid, "metadata_lang": lang, "metadata_condition": cond,
                   "metadata_category": p["category"], "metadata_role": p["role"],
                   "metadata_in_score400": p["in_score400"], **e})
    return ex


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("method")
    pairs = {p["pair_id"]: p for p in read_jsonl(DATA / "pairs.jsonl")}
    mt = {r["pair_id"]: r for r in read_jsonl(DATA / "mt_parallel.jsonl")}
    items = pd.read_json(RES / "items_scored.jsonl", lines=True)
    res = json.loads((RES / "analysis_results.json").read_text())
    ex = build_examples(items, pairs)
    for e in ex:
        if e["metadata_condition"] == "mt_from_en":
            e["input"] = mt[e["metadata_pair_id"]]["prompt_sl_mt"]
    # identity dataset
    idr = read_jsonl(RES / "identity_scored.jsonl")
    qs = {q["iid"]: q for q in read_jsonl(DATA / "identity_items.jsonl")}
    by = {}
    for r in idr:
        by.setdefault((r["iid"], r["lang"]), {})[r["model"]] = r
    idex = []
    for (iid, lg), d in sorted(by.items()):
        if len(d) < 2:
            continue
        q = qs[iid]
        e = {"input": q[f"text_{lg}"], "output": ("self-identification (own model name)" if q["type"] == "identity"
                                                  else "no self-name expected (control)"),
             "metadata_iid": iid, "metadata_type": q["type"], "metadata_intent": q["intent"], "metadata_lang": lg}
        for mk, r in d.items():
            e[f"predict_{mk}"] = r["response"]
            e[f"metadata_name_label_{mk}"] = r["judge_label"]
            e[f"metadata_own_name_{mk}"] = r["own_judge"] if r["own_judge"] is not None else r["own_regex"]
        idex.append(e)
    status = {mk: json.loads((OUT / f"gpu_status_{mk}.json").read_text()) if (OUT / f"gpu_status_{mk}.json").exists()
              else None for mk in MODELS}
    prec = {mk: json.loads((OUT / f"precision_{mk}.json").read_text()) if (OUT / f"precision_{mk}.json").exists()
            else None for mk in MODELS}
    for v in prec.values():
        if v:
            v.pop("per_item", None)
    proto_sha = (ROOT / "protocol.sha256").read_text().split()[0] if (ROOT / "protocol.sha256").exists() else None
    meta = {
        "method_name": "MAIN vs ALT-1 screen: GaMS3-12B-Instruct vs Gemma-3-12B-IT (control) refusal DiD on RefusEU EN/SL",
        "protocol_sha256": proto_sha,
        "checkpoints": {k: {"repo": v["repo"], "revision": v["revision"]} for k, v in MODELS.items()},
        "precision": "NF4 4-bit (bitsandbytes, double quant, bf16 compute) -- REDUCED PRECISION",
        "gpu_status": {mk: {k: v for k, v in (s or {}).items() if k not in ("rendered_en", "rendered_sl")}
                       for mk, s in status.items()},
        "precision_check_4v8": prec,
        "analysis": res,
        "synthetic_T8": json.loads((RES / "synthetic_T8.json").read_text()) if (RES / "synthetic_T8.json").exists() else None,
        "cost_ledger_openrouter_usd": round(sum(float(r.get("cost") or 0) for p in OUT.glob("ledger_*.jsonl")
                                                for r in read_jsonl(p)), 4),
        "blockers": ["OpenRouter key was over its $50 daily limit (HTTP 403) from ~14:40 to ~15:10 UTC: identity/MT "
                     "translation was done locally (NLLB-200 + opus-mt back-translation, 6 manual fixes) and the protocol "
                     "was frozen with local judges; addendum 1 (before any label) restored the pre-registered "
                     "gemini-2.5-flash / gpt-4.1-mini judges once the key worked again.",
                     "gemini-2.5-flash refuses to grade some harmful items (PROHIBITED_CONTENT): those use the "
                     "gpt-4.1-mini fallback, flagged in outputs/judge_gemini.jsonl.",
                     "Token-level batching certification failed (NF4 batch-size-dependent kernels); exact-length "
                     "buckets kept for both models; outcome-level agreement reported in gpu_status."],
    }
    out = {"metadata": meta, "datasets": [
        {"dataset": "RefusEU_lang_en_sl_train_test_SCORE_and_MT_pairs", "examples": ex},
        {"dataset": "identity_and_control_items_EN_SL", "examples": idex}]}
    (ROOT / "method_out.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str))
    logger.info(f"method_out.json: {len(ex)} refusal examples, {len(idex)} identity examples")


if __name__ == "__main__":
    main()
