#!/usr/bin/env python3
"""S3 lambda placement (SCREEN evidence only; no FINAL row is read).

Deviation from the plan (F1 consequence): the plan's DEV calibration needed a judge between the DEV generation and the
FINAL curve. With the paid key down, that judge is a local 14B model that cannot share the 23 GB GPU with the
generating model, so every DEV judge pass would cost two extra model loads. Instead the curve steps are placed from the
ARCHIVED exp8 A1 dose curves of the SAME iter-1 adapter, NF4, 128 tokens, on DISJOINT RefusEU-TRAIN items (P200):
gemini labels for Gemma, and the frozen lexicon / emulator for GaMS (no gemini labels exist for GaMS lambda rows).
A common grid is used for both models (the G3 GLM compares at matched EN = 50%, so the grid need not match per
model). It is chosen so that the predicted EN-BT refusal gives >= 2 steps in [0.2, 0.5) and >= 2 in [0.5, 0.8] under
BOTH screens, dense at low lambda where Gemma drops fastest. Output: results/dev/lambda_calibration.json + sha256.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from loguru import logger
from sklearn.isotonic import IsotonicRegression

from common import DEV_DIR, E8, setup_logging, sha256_file

GRID = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8]


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("calibrate")
    d = pd.read_json(E8 / "results/items_final.jsonl", lines=True)
    d = d[d.curve.isin(["lambda", "orig"]) & (d.k == 0) & (d.arm == "en_bt")]
    out = {"source": "exp8 results/items_final.jsonl, A1 lambda curve (iter-1 selected adapter), arm en_bt, P200 "
                     "RefusEU-TRAIN items (disjoint from the reserved eval FINAL split)", "grid": GRID, "per_model": {}}
    for m, col in (("gemma_it", "R_gemini"), ("gams3_it", "R_lex"), ("gams3_it_emul", "R_emul")):
        mm = m.replace("_emul", "")
        s = d[(d.model == mm) & d[col].notna()].groupby("step")[col].mean()
        if len(s) < 3:
            out["per_model"][m] = {"readout": col, "steps": s.round(3).to_dict(), "note": "too few steps"}
            continue
        iso = IsotonicRegression(increasing=False, out_of_bounds="clip").fit(s.index.values, s.values)
        pred = iso.predict(np.array(GRID))
        sup = (int(((pred >= 0.2) & (pred < 0.5)).sum()), int(((pred >= 0.5) & (pred <= 0.8)).sum()))
        out["per_model"][m] = {"readout": col, "screen_steps": {str(k): round(v, 3) for k, v in s.items()},
                               "pred_EN_at_grid": dict(zip(map(str, GRID), np.round(pred, 3).tolist())),
                               "support_pred": sup}
        logger.info(f"{m} ({col}): pred EN {np.round(pred, 2)} support {sup}")
    out["lambdas"] = {"gemma_it": GRID, "gams3_it": GRID}
    out["anchors"] = [0.0, 1.0]
    p = DEV_DIR / "lambda_calibration.json"
    p.write_text(json.dumps(out, indent=1))
    (DEV_DIR / "lambda_calibration.sha256").write_text(sha256_file(p) + "  lambda_calibration.json\n")
    logger.info(f"wrote {p}")


if __name__ == "__main__":
    main()
