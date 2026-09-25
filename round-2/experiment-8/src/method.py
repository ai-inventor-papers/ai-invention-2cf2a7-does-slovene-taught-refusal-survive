#!/usr/bin/env python3
"""Entry point (CPU): items table -> statistics -> audit -> figures -> method_out.json (exp_gen_sol_out schema).

The GPU work lives in src/gpu_block.py (run_gpu.sh) and the judge in src/judge.py; this script only reads saved outputs.
Each example = one (item, arm, curve, step) cell with BOTH models' predictions:
  predict_gemma_it / predict_gams3_it = primary readout label (gemini REFUSE/PARTIAL/COMPLY, or LEX_REFUSE/LEX_NONREFUSE when
  the judge is pending); metadata_* carry responses, s1, lexicon, degeneracy, judge labels of the second family, etc.
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
from common import DATA, MODEL_ORDER, RESULTS, read_jsonl  # noqa: E402

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add(str(WS / "logs" / "method.log"), rotation="30 MB", level="DEBUG")

DATASET_NAME = {"orig": "refuseu_train_P200__original_k0", "prefill": "refuseu_train_P200__compliant_prefill",
                "lambda": "refuseu_train_P200__A1_lambda_scaled_heretic_adapter",
                "ablate": "refuseu_train_P200__A2_graded_own_direction_ablation",
                "ablate_rand": "refuseu_train_P100__A2_random_direction_control",
                "trial": "refuseu_train_P100__B_fresh_heretic_trials", "harmless_lambda": "alpaca_harmless100__over_refusal"}


def run(cmd: list[str]):
    logger.info("$ " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=WS / "src", capture_output=True, text=True)
    if r.returncode != 0:
        logger.error(r.stderr[-3000:])
        raise RuntimeError(f"{cmd} failed")
    logger.info(r.stdout[-1500:])


@logger.catch(reraise=True)
def main():
    py = sys.executable
    run([py, "build_table.py"])
    run([py, "analysis.py"])
    run([py, "audit.py"])
    run([py, "make_figs.py"])
    run([py, "summarize.py"])
    A = json.loads((RESULTS / "analysis.json").read_text())
    AU = json.loads((RESULTS / "audit.json").read_text())
    rows = read_jsonl(RESULTS / "items_final.jsonl")
    req = {}
    for f in ("probe_P200.jsonl", "harmless100.jsonl"):
        for it in read_jsonl(DATA / f):
            for arm in ("en_orig", "sl_mt", "en_bt"):
                req[(it["item_id"], arm)] = it[arm]
    ro = A["primary_readout"]
    cells = defaultdict(dict)
    for r in rows:
        cells[(r["curve"], r["step"], r["arm"], r["item_id"])][r["model"]] = r
    by_ds = defaultdict(list)
    for (curve, step, arm, iid), d in sorted(cells.items(), key=lambda x: (x[0][0], x[0][1], x[0][2], x[0][3])):
        harmless = curve.startswith("harmless")
        ex = {"input": req[(iid, arm)], "output": "COMPLY" if harmless else "REFUSE",
              "metadata_item_id": iid, "metadata_arm": arm, "metadata_curve": curve, "metadata_step": step,
              "metadata_readout": ro}
        any_r = next(iter(d.values()))
        ex["metadata_gold_cat"] = any_r.get("gold_cat")
        ex["metadata_dose_group"] = any_r.get("dose_group")
        for m in MODEL_ORDER:
            r = d.get(m)
            if r is None:
                ex[f"predict_{m}"] = "MISSING"
                continue
            if ro == "R_gemini":
                ex[f"predict_{m}"] = r["label3_gemini"] or "UNJUDGED"
            else:
                ex[f"predict_{m}"] = "LEX_REFUSE" if r["R_lex"] else "LEX_NONREFUSE"
            ex[f"metadata_{m}_response"] = r["response"]
            ex[f"metadata_{m}_label_gemini"] = r["label3_gemini"]
            ex[f"metadata_{m}_label_gpt41"] = r["label3_gpt41"]
            ex[f"metadata_{m}_lexicon"] = r["R_lex"]
            ex[f"metadata_{m}_s1"] = r["s1"]
            ex[f"metadata_{m}_degenerate"] = r["degenerate"]
            if r.get("heretic_refusals") is not None:
                ex[f"metadata_{m}_heretic_refusals"] = r["heretic_refusals"]
                ex[f"metadata_{m}_heretic_kl"] = r["heretic_kl"]
        by_ds[DATASET_NAME.get(curve, curve)].append(ex)
    out = {"metadata": {"method_name": "C3 confirmation: English Heretic abliteration reach into Slovene, GaMS3 vs Gemma-3",
                        "description": "Fresh Heretic trials (B, primary), lambda-scaled iter-1 adapter (A1) and graded "
                                       "own-direction ablation (A2); G3 = GaMS-minus-Gemma SL-MT refusal log-odds at EN-BT "
                                       "refusal 50%; prefill-depth hazard link; C5a. Baseline/control = Gemma-3-12B-IT on "
                                       "identical items/grids/trials, plus random-direction controls.",
                        "protocol_sha256": (WS / "protocol.sha256").read_text().split()[0],
                        "analysis": A, "audit": AU,
                        "amendments": json.loads((RESULTS / "protocol_amendments.json").read_text()),
                        "checks": {m: json.loads((RESULTS / m / "checks.json").read_text())
                                   for m in MODEL_ORDER if (RESULTS / m / "checks.json").exists()},
                        "kept_paths": {"results": str(RESULTS), "data": str(DATA)}},
           "datasets": [{"dataset": k, "examples": v} for k, v in by_ds.items()]}
    (WS / "method_out.json").write_text(json.dumps(out, ensure_ascii=False, default=float))
    logger.info(f"method_out.json: {sum(len(v) for v in by_ds.values())} examples in {len(by_ds)} datasets")


if __name__ == "__main__":
    main()
