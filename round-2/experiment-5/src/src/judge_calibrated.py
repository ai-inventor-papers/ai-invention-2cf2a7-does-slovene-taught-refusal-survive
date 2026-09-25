#!/usr/bin/env python3
"""EXPLORATORY (added after deviation D5; not pre-registered): judge-calibration-corrected FINAL estimates.

Motivation (results/dev_judge_compare.json): on DEV items the substitute judge (local Qwen3-14B) labels hedged ENGLISH
answers to benign HARD prompts as REFUSE far more often than gemini-2.5-flash does (+20-27 pp), but Slovene ones much less
(+7-10 pp). That language-asymmetric false-alarm inflation biases the SDT contrasts. Correction: for every
model x set x arm (x safe/unsafe for HARD) cell, estimate on the DEV items of the same cell
  a = P(gemini REFUSE | qwen REFUSE),  b = P(gemini REFUSE | qwen not REFUSE)
and map the FINAL Qwen3 count k_q (of n) to the gemini scale: k_g = a k_q + b (n - k_q) (a regression-calibration
estimator; valid if the judge-confusion transfers from DEV to FINAL items of the same cell, which share the source and
construction). Uncertainty: parametric bootstrap over BOTH the FINAL cell counts (binomial at the observed Qwen rate) and
the DEV calibration (Beta(k+.5, n-k+.5) draws for a and b), B=2000. Cells are treated as independent, which ignores
the within-item pairing across arms/models and makes the intervals conservative.
Output: results/judge_calibrated_final.json. Usage: python judge_calibrated.py [--target final|dev]
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict

import numpy as np
from loguru import logger

import stats_lib as S
from common import RESULTS, SEED, read_jsonl, setup_logging

B = 2000
MODELS = ("gemma_it", "gams3_it")


def cell_of(r: dict) -> str | None:
    if r["set"] not in ("refuseu_nat", "refuseu_x", "hard"):
        return None
    extra = f"|{'unsafe' if r['is_harmful'] else 'safe'}" if r["set"] == "hard" else ""
    return f"{r['model']}|{r['set']}{extra}|{r['arm']}"


def calibration(dev: list[dict]) -> dict:
    t = defaultdict(lambda: [0, 0, 0, 0])  # [gemR & qR, qR, gemR & ~qR, ~qR]
    for r in dev:
        c = cell_of(r)
        if c is None or r.get("R") is None or r.get("R_qwen3") is None:
            continue
        if r["R_qwen3"]:
            t[c][0] += r["R"]
            t[c][1] += 1
        else:
            t[c][2] += r["R"]
            t[c][3] += 1
    return dict(t)


def counts(rows: list[dict], outcome: str) -> dict:
    t = defaultdict(lambda: [0, 0])
    for r in rows:
        c = cell_of(r)
        if c is None or r.get(outcome) is None:
            continue
        t[c][0] += r[outcome]
        t[c][1] += 1
    return dict(t)


def corrected_draws(cnt: dict, cal: dict | None, rng: np.random.Generator) -> dict[str, tuple[float, np.ndarray, int]]:
    """cell -> (point corrected count, B draws of corrected count, n)."""
    out = {}
    for c, (k, n) in cnt.items():
        if cal is None:  # identity mapping (direct labels)
            out[c] = (float(k), rng.binomial(n, k / n if n else 0.0, size=B).astype(float), n)
            continue
        ka, na, kb, nb = cal.get(c, [0, 0, 0, 0])
        a_hat = (ka + .5) / (na + 1)
        b_hat = (kb + .5) / (nb + 1)
        pt = a_hat * k + b_hat * (n - k)
        kq = rng.binomial(n, k / n if n else 0.0, size=B)
        a = rng.beta(ka + .5, na - ka + .5, size=B)
        b = rng.beta(kb + .5, nb - kb + .5, size=B)
        out[c] = (pt, a * kq + b * (n - kq), n)
    return out


def did_from(cd: dict, set_: str, en_arm: str, sl_arm: str, extra: str = "") -> tuple[float, np.ndarray]:
    keys = [f"gemma_it|{set_}{extra}|{en_arm}", f"gemma_it|{set_}{extra}|{sl_arm}",
            f"gams3_it|{set_}{extra}|{en_arm}", f"gams3_it|{set_}{extra}|{sl_arm}"]
    pt = S.did4(np.array([S.Lh(cd[k][0], cd[k][2]) for k in keys]))
    bt = S.did4(np.stack([S.Lh(cd[k][1], cd[k][2]) for k in keys], -1))
    return float(pt), bt


def sdt_from(cd: dict, en_arm: str, sl_arm: str) -> dict:
    cells = [("gemma_it", en_arm), ("gemma_it", sl_arm), ("gams3_it", en_arm), ("gams3_it", sl_arm)]
    zH_pt, zF_pt, zH_b, zF_b = [], [], [], []
    for mk, arm in cells:
        u, s = cd[f"{mk}|hard|unsafe|{arm}"], cd[f"{mk}|hard|safe|{arm}"]
        zH_pt.append(S.zh(u[0], u[2]))
        zF_pt.append(S.zh(s[0], s[2]))
        zH_b.append(S.zh(u[1], u[2]))
        zF_b.append(S.zh(s[1], s[2]))
    zH_pt, zF_pt = np.array(zH_pt), np.array(zF_pt)
    zH_b, zF_b = np.stack(zH_b, -1), np.stack(zF_b, -1)
    dp_pt, c_pt = zH_pt - zF_pt, -(zH_pt + zF_pt) / 2
    dp_b, c_b = zH_b - zF_b, -(zH_b + zF_b) / 2
    return {"DiD_dprime": S.summarize(float(S.did4(dp_pt)), S.did4(dp_b)),
            "DiD_c": S.summarize(float(S.did4(c_pt)), S.did4(c_b)),
            "H": [float((cd[f"{mk}|hard|unsafe|{arm}"][0] + .5) / (cd[f"{mk}|hard|unsafe|{arm}"][2] + 1))
                  for mk, arm in cells],
            "F": [float((cd[f"{mk}|hard|safe|{arm}"][0] + .5) / (cd[f"{mk}|hard|safe|{arm}"][2] + 1))
                  for mk, arm in cells],
            "gemma_c_SL_minus_EN": float(c_pt[1] - c_pt[0]), "gams_c_SL_minus_EN": float(c_pt[3] - c_pt[2]),
            "gemma_c_SL_minus_EN_ci95": S.pct_ci(c_b[:, 1] - c_b[:, 0]),
            "gams_c_SL_minus_EN_ci95": S.pct_ci(c_b[:, 3] - c_b[:, 2])}


def estimates(cnt: dict, cal: dict, rng) -> dict:
    cd = corrected_draws(cnt, cal, rng)
    out = {}
    pt, bt = did_from(cd, "refuseu_nat", "EN_nat", "SL_nat")
    out["DiD_ref_natural"] = S.summarize(pt, bt)
    pt, bt = did_from(cd, "refuseu_x", "EN_BT", "SL_MT")
    out["DiD_ref_MT"] = S.summarize(pt, bt)
    out["HARD_SLMT_vs_ENBT"] = sdt_from(cd, "EN_BT", "SL_MT")
    out["HARD_SLMT_vs_ENorig"] = sdt_from(cd, "EN_orig", "SL_MT")
    out["corrected_rates"] = {c: v[0] / v[2] for c, v in cd.items()}
    return out


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="final", choices=["final", "dev"])
    args = ap.parse_args()
    setup_logging("judge_calibrated")
    dev = read_jsonl(RESULTS / "items_dev.jsonl")
    cal = calibration(dev)
    tgt = dev if args.target == "dev" else read_jsonl(RESULTS / "items_final.jsonl")
    rng = np.random.default_rng(SEED)
    res = {"note": __doc__.split("Output:")[0].strip(), "target": args.target,
           "calibration_cells": {c: {"P(gem R|q R)": (v[0] + .5) / (v[1] + 1), "n_qR": v[1],
                                     "P(gem R|q notR)": (v[2] + .5) / (v[3] + 1), "n_qnotR": v[3]}
                                 for c, v in sorted(cal.items())},
           "qwen3_corrected_to_gemini_scale": estimates(counts(tgt, "R_qwen3"), cal, rng)}
    if args.target == "dev":  # self-check: corrected DEV estimates vs the direct gemini-labelled DEV estimates
        res["direct_gemini_dev"] = estimates(counts(dev, "R"), None, rng)
    if args.target == "dev":  # split-half transfer check: calibrate on half the DEV items, correct the other half
        import random
        items = sorted({r["item_id"] for r in dev})
        errs = defaultdict(lambda: {"raw_qwen": [], "corrected": []})
        for rep in range(20):
            rr = random.Random(SEED + rep)
            half = set(rr.sample(items, len(items) // 2))
            calA = calibration([r for r in dev if r["item_id"] in half])
            tgtB = [r for r in dev if r["item_id"] not in half]
            g = estimates(counts(tgtB, "R"), None, rng)
            qr = estimates(counts(tgtB, "R_qwen3"), None, rng)
            qc = estimates(counts(tgtB, "R_qwen3"), calA, rng)
            for name, get in (("DiD_ref_natural", lambda e: e["DiD_ref_natural"]["est"]),
                              ("DiD_ref_MT", lambda e: e["DiD_ref_MT"]["est"]),
                              ("DiD_dprime", lambda e: e["HARD_SLMT_vs_ENBT"]["DiD_dprime"]["est"]),
                              ("DiD_c", lambda e: e["HARD_SLMT_vs_ENBT"]["DiD_c"]["est"])):
                errs[name]["raw_qwen"].append(get(qr) - get(g))
                errs[name]["corrected"].append(get(qc) - get(g))
        res["split_half_transfer_check"] = {
            k: {f"{m}_mean_err_vs_gemini": float(np.mean(v[m])) for m in v} |
               {f"{m}_mae_vs_gemini": float(np.mean(np.abs(v[m]))) for m in v} for k, v in errs.items()}
        logger.info(json.dumps(res["split_half_transfer_check"]))
    (RESULTS / f"judge_calibrated_{args.target}.json").write_text(json.dumps(res, indent=1, default=float))
    q = res["qwen3_corrected_to_gemini_scale"]
    logger.info(f"[{args.target}] corrected: DiD_ref={q['DiD_ref_natural']['est']:.3f} {q['DiD_ref_natural']['ci95']}; "
                f"DiD_MT={q['DiD_ref_MT']['est']:.3f}; DiD_d'={q['HARD_SLMT_vs_ENBT']['DiD_dprime']['est']:.3f} "
                f"{q['HARD_SLMT_vs_ENBT']['DiD_dprime']['ci95']}; DiD_c={q['HARD_SLMT_vs_ENBT']['DiD_c']['est']:.3f} "
                f"{q['HARD_SLMT_vs_ENBT']['DiD_c']['ci95']}")


if __name__ == "__main__":
    main()
