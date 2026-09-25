#!/usr/bin/env python3
"""CPU entry point (after the GPU phases): analysis -> audit -> figures -> method_out.json (exp_gen_sol_out schema).

GPU phases (see README): src/prep_data.py, src/phase_a.py, src/twins_vllm.py, src/gen_vllm.py, src/judge_distill.py,
src/judge_llm.py. This script only reads their saved outputs.

method_out.json: one dataset per probe set (P300 harmful, T150 benign twins). One example per (item, arm, step) that both
siblings answered; input = the prompt in that arm; output = expected behaviour ("REFUSE" for harmful RefusEU items,
"COMPLY" for benign twins); predict_gemma_it / predict_gams3_it = primary judge (J1) label of each sibling's response;
metadata_* = step, curve, block, J2 labels, lexicon, truncated responses.
"""
from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from loguru import logger

WS = Path(__file__).resolve().parent
sys.path.insert(0, str(WS / "src"))
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add(str(WS / "logs" / "method.log"), rotation="30 MB", level="DEBUG")


def run(script: str):
    logger.info(f"running {script}")
    r = subprocess.run([sys.executable, str(WS / "src" / script)], cwd=str(WS / "src"), capture_output=True, text=True)
    logger.info(r.stdout[-1500:])
    if r.returncode != 0:
        logger.error(r.stderr[-3000:])
        raise RuntimeError(f"{script} failed")


@logger.catch(reraise=True)
def main():
    run("analysis.py")
    run("audit.py")
    run("make_figs.py")
    from common import DATA, read_jsonl
    A = json.loads((WS / "results" / "analysis.json").read_text())
    rows = read_jsonl(WS / "results" / "items_final.jsonl")
    req = {}
    for f in ("probe_P300.jsonl", "twins_T150.jsonl"):
        for it in read_jsonl(DATA / f):
            for arm in ("en_orig", "sl_mt", "en_bt"):
                req[(it["item_id"], arm)] = it[arm]
    by = defaultdict(dict)
    for r in rows:
        by[(r["kind"], r["item_id"], r["arm"], r["step_name"])][r["model"]] = r
    ds = {"harmful": [], "benign": []}
    for (kind, iid, arm, step), d in sorted(by.items()):
        if len(d) != 2:
            continue
        g, s = d["gemma_it"], d["gams3_it"]
        ds[kind].append({
            "input": req[(iid, arm)], "output": "REFUSE" if kind == "harmful" else "COMPLY",
            "predict_gemma_it": g["j1"] or "UNJUDGED", "predict_gams3_it": s["j1"] or "UNJUDGED",
            "metadata_item_id": iid, "metadata_arm": arm, "metadata_step": step, "metadata_curve": g["curve"],
            "metadata_block": g["block"], "metadata_gold_cat": g.get("gold_cat"),
            "metadata_j2_gemma_it": g.get("j2"), "metadata_j2_gams3_it": s.get("j2"),
            "metadata_lex_gemma_it": g["lex"], "metadata_lex_gams3_it": s["lex"],
            "metadata_response_gemma_it": (g["response"] or "")[:300], "metadata_response_gams3_it": (s["response"] or "")[:300]})
    out = {"metadata": {"method_name": "Paired Heretic dose curves (B' trials, lambda curve, norm-matched random edits) "
                                       "on Gemma-3-12B-IT vs GaMS3-12B-Instruct; G3 + SDT",
                        "primary_judge": "J1 gemini-distilled mdeberta-v3-base (LOCAL; OpenRouter unavailable)",
                        "verdict": A["verdict"], "G3_primary": {k: A["G3"]["Bprime|j1|R1"][k] for k in ("G3", "ci90", "ci95", "mde")},
                        "G3_lambda": {k: A["G3"]["lambda|j1|R1"][k] for k in ("G3", "ci90", "ci95", "mde")},
                        "SDT": {m: {k: v for k, v in A["SDT"]["j1|R1"]["per_model"][m].items() if k != "per_step"}
                                for m in ("gemma_it", "gams3_it")},
                        "C5a": A.get("C5a"), "analysis_file": "results/analysis.json", "audit_file": "results/audit.json"},
           "datasets": [{"dataset": "refuseu_train_P300_harmful", "examples": ds["harmful"]},
                        {"dataset": "benign_twins_T150", "examples": ds["benign"]}]}
    (WS / "method_out.json").write_text(json.dumps(out, ensure_ascii=False))
    logger.info(f"method_out.json: {len(ds['harmful'])} harmful + {len(ds['benign'])} benign examples")


if __name__ == "__main__":
    main()
