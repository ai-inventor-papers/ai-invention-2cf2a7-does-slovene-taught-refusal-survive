#!/usr/bin/env python3
"""DEV-only judge calibration check for deviation D5 (substitute primary judge).

On the DEV items (never used for any FINAL decision other than the pre-registered margins), recompute every headline
contrast twice on identical items: once with gemini-2.5-flash labels (the planned primary) and once with the local
Qwen3-14B labels (the FINAL substitute). Also tabulate the judge disagreement per model x set x arm, because a judge whose
disagreement with gemini differs between the two models would bias the cross-model DiD.
Input: results/items_dev.jsonl (written by `analysis.py --split dev`). Output: results/dev_judge_compare.json
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict

import numpy as np
from loguru import logger

import analysis as AN
from common import PROTO, RESULTS, SEED, read_jsonl, setup_logging


def pick(res: dict, key: str) -> dict | None:
    v = res.get(key)
    return None if v is None else {"est": v["est"], "ci95": v["ci95"]}


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("dev_judge_compare")
    rows = read_jsonl(RESULTS / "items_dev.jsonl")
    add = json.loads((PROTO / "addendum_dev.json").read_text())
    out: dict = {"note": "DEV items only; same items under both judges; gemini = planned primary, qwen3 = FINAL substitute"}
    for tag, R in (("gemini", "R"), ("qwen3", "R_qwen3")):
        rng = np.random.default_rng(SEED)
        c2, _ = AN.refuseu_c2(rows, rng, add, outcome=R, tag=tag)
        mt = AN.mt_arm(rows, rng, outcome=R)
        h = AN.hard_sdt(rows, rng, outcome=R)
        out[tag] = {"DiD_ref": pick(c2, "DiD_overall"), "D": pick(c2, "D"), "n_pairs": c2["n_pairs"],
                    "DiD_ref_MT": pick(mt, "DiD_overall"), "n_MT": mt["n_items"],
                    "DiD_dprime": pick(h, "DiD_dprime"), "DiD_c": pick(h, "DiD_c"),
                    "hard_cells_H": h["cells"]["H"], "hard_cells_F": h["cells"]["F"],
                    "hard_own_delta": {k: v for k, v in h["own_delta"].items() if not k.endswith("ci95")}}
    dis = defaultdict(Counter)
    for r in rows:
        if r["set"] in ("refuseu_nat", "refuseu_x", "hard") and r.get("R") is not None and r.get("R_qwen3") is not None:
            extra = f"|{'unsafe' if r['is_harmful'] else 'safe'}" if r["set"] == "hard" else ""
            c = f"{r['model']}|{r['set']}{extra}|{r['arm']}"
            dis[c]["n"] += 1
            dis[c]["gemini_R"] += r["R"]
            dis[c]["qwen_R"] += r["R_qwen3"]
            dis[c][f"{r['judge_gemini']}->{r['judge_qwen3']}"] += 1
    out["per_cell"] = {c: {"n": v["n"], "rate_gemini": v["gemini_R"] / v["n"], "rate_qwen3": v["qwen_R"] / v["n"],
                           "qwen_minus_gemini": (v["qwen_R"] - v["gemini_R"]) / v["n"],
                           "transitions": {k: n for k, n in v.items() if "->" in k}}
                       for c, v in sorted(dis.items())}
    (RESULTS / "dev_judge_compare.json").write_text(json.dumps(AN.jsonable(out), indent=1))
    for tag in ("gemini", "qwen3"):
        logger.info(f"{tag}: " + json.dumps({k: (round(v["est"], 3), [round(x, 3) for x in v["ci95"]])
                                             for k, v in out[tag].items() if isinstance(v, dict) and "est" in v}))


if __name__ == "__main__":
    main()
