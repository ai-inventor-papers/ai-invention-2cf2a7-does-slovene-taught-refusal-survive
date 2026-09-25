#!/usr/bin/env python3
"""S5 DEV decisions (layer L*, alpha-grid multiplier, lambda*) from DEV rows + the DEV judge labels. The add-on band is
decided afterwards inside gpu_block (forward-only KL rule, judge-free) right before the freeze.
Usage: .venv/bin/python src/dev_decide.py --model gemma_it [--judge local/qwen3-14b]"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402

from common import RESULTS, read_jsonl, row_key, setup_logger  # noqa: E402

CAND_LAYERS = [16, 20, 24, 28, 32, 36]
K_GRID = [0.1, 0.2, 0.35, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--judge", default="local/qwen3-14b")
    a = ap.parse_args()
    logger = setup_logger(f"dev_decide_{a.model}")
    D = RESULTS / "dev" / a.model
    lab = {r["row_key"]: r["label"] for r in read_jsonl(RESULTS / "judge_labels.jsonl") if r["judge"] == a.judge}
    geo = json.loads((RESULTS / a.model / "geometry_post.json").read_text())

    def R(rows):
        v = [lab.get(row_key(r)) == "REFUSE" for r in rows if lab.get(row_key(r)) is not None]
        return float(np.mean(v)) if v else float("nan")
    missing = [row_key(r) for f in ("dev_layer", "dev_grid", "dev_lambda") for r in read_jsonl(D / f"{f}.jsonl")
               if row_key(r) not in lab]
    assert not missing, f"{len(missing)} DEV rows unlabelled"
    dec = {"judge": a.judge}
    rows = read_jsonl(D / "dev_layer.jsonl")
    base = read_jsonl(D / "dev_grid.jsonl")
    cand = []
    for L in CAND_LAYERS:
        rr = [r for r in rows if r["layer"] == L]
        r1, r2 = R([r for r in rr if r["step"] == 1.0]), R([r for r in rr if r["step"] == 2.0])
        deg = float(np.mean([r["degenerate_text"] for r in rr]))
        lok = float(np.mean([r["lang_ok"] for r in rr]))
        cand.append({"L": L, "refusal_k1": r1, "refusal_k2": r2, "score": (r1 + r2) / 2, "degenerate_text": deg,
                     "lang_ok": lok, "passes": bool(deg < 0.10 and lok >= 0.95)})
    ok = [c for c in cand if c["passes"]] or cand
    best = max(ok, key=lambda c: (round(c["score"], 6), -c["L"]))
    Lstar = best["L"]
    dec["layer"] = {"L_star": Lstar, "candidates": cand, "baseline_refusal_induce_dev_en": R([r for r in base if r["cond"] == "baseline"]),
                    "rule": "argmax mean judged refusal over k in {1,2} (+k|d_EN(L)| rEN(L) on 24 induce_dev EN-BT) s.t. degenerate_text < 10% and lang_ok >= 95%; ties -> lower layer",
                    "fallback_no_layer_passes": not any(c["passes"] for c in cand),
                    "positive_control_k2_ge_0.5": best["refusal_k2"] >= 0.5,
                    "positive_control_any_layer_k2_ge_0.5": max(c["refusal_k2"] for c in cand) >= 0.5}
    g = [r for r in base if r.get("layer") == Lstar]
    r_en = R([r for r in g if r["cond"] == "rEN"])
    r_sl = R([r for r in g if r["cond"] == "u_SLperp"])
    mult = 2.0 if r_en < 0.5 else (0.25 if r_sl > 0.5 else 1.0)
    dec["grid"] = {"K": [round(k * mult, 4) for k in K_GRID], "multiplier": mult, "rEN_at_Kmax_EN_refusal": r_en,
                   "uSLperp_at_Kmin_SL_refusal": r_sl, "Delta_norm_dSL": geo[Lstar]["norm_dSL"], "norm_dEN": geo[Lstar]["norm_dEN"],
                   "Nbar_mean_resid_norm": geo[Lstar]["mean_resid_norm"],
                   "alpha_over_Nbar_uSLperp": [k * mult * geo[Lstar]["norm_dSL"] / geo[Lstar]["mean_resid_norm"] for k in K_GRID],
                   "alpha_over_Nbar_rEN": [k * mult * geo[Lstar]["norm_dEN"] / geo[Lstar]["mean_resid_norm"] for k in K_GRID],
                   "rule": "rEN at K=3 < .5 EN refusal -> x2; u_SLperp at K=0.2 (DEV check point; plan said 0.1) > .5 SL refusal -> /4"}
    rows = read_jsonl(D / "dev_lambda.jsonl")
    lams = sorted({r["step"] for r in rows})
    curve_en = {l: R([r for r in rows if r["step"] == l and r["arm"] == "en_bt"]) for l in lams}
    curve_sl = {l: R([r for r in rows if r["step"] == l and r["arm"] == "sl_mt"]) for l in lams}
    main_grid = [0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0]
    best0 = min(main_grid, key=lambda l: (abs(curve_en[l] - 0.5), l))
    used = list(main_grid)
    if abs(curve_en[best0] - 0.5) > 0.15:  # pre-registered extension: bracketing midpoints / grid ends (pre-generated)
        used = lams
    lam_star = min(used, key=lambda l: (abs(curve_en[l] - 0.5), l))
    lag = None
    if 0 < curve_en[lam_star] < 1:
        from common import hautus, logit
        n = sum(1 for r in rows if r["step"] == lam_star and r["arm"] == "en_bt")
        lag = logit(hautus(curve_sl[lam_star] * n, n)) - logit(hautus(curve_en[lam_star] * n, n))
    dec["lambda"] = {"lambda_star": lam_star, "curve_en_bt": {str(k): v for k, v in curve_en.items()},
                     "curve_sl_mt": {str(k): v for k, v in curve_sl.items()}, "grid_used": used,
                     "R_EN_at_star": curve_en[lam_star], "R_SL_at_star": curve_sl[lam_star], "dev_lag_logit_hautus": lag,
                     "in_0.35_0.65": 0.35 <= curve_en[lam_star] <= 0.65,
                     "rule": "argmin |R_EN(DEV40 EN-BT) - .5| over {0.2,...,1.0}; if > .15 away the pre-generated extension points {0.1,0.15,0.25,0.35,0.45,1.5} are admitted"}
    (D / "dev_decisions.json").write_text(json.dumps(dec, indent=2))
    logger.info(json.dumps(dec)[:3000])


if __name__ == "__main__":
    main()
