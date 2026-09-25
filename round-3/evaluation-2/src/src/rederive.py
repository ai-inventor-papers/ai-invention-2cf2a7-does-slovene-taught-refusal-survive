#!/usr/bin/env python3
"""Independent second code path (STEP 7). Reads ONLY labels/*.jsonl + work/master.parquet, re-derives the B and A1 G3
(GaMS - Gemma SL log-odds at EN 50%) under the primary and lexicon readouts with a self-contained numpy IRLS GLM and an
independent item x step bootstrap, and checks against results/eval_results.json to 1e-6 (point) / 0.05 (CI endpoints).
Writes work/rederive.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

WS = Path(__file__).resolve().parent.parent
LAB = WS / "labels"
LAB3 = ["REFUSE", "PARTIAL", "COMPLY"]
SEED = 20260925


def irls(x, k, n, iters=100):
    """binomial logit GLM by Newton-Raphson (independent of stats_core.fit_glm)."""
    X = np.c_[np.ones_like(x), x]
    b = np.zeros(2)
    for _ in range(iters):
        eta = X @ b
        p = 1.0 / (1.0 + np.exp(-eta))
        W = n * p * (1 - p) + 1e-9
        grad = X.T @ (k - n * p)
        H = X.T @ (X * W[:, None]) + 1e-6 * np.eye(2)
        step = np.linalg.solve(H, grad)
        b = b + step
        if np.max(np.abs(step)) < 1e-10:
            break
    return b[0], b[1]


def hlogit(k, n):
    p = (k + 0.5) / (n + 1.0)
    return np.log(p / (1 - p))


def main():
    d = pd.read_parquet(WS / "work/master.parquet",
                        columns=["row_key", "model", "arm", "curve", "step", "item_id", "in_P100", "degenerate", "R_lex"])
    prim = "qwen3_14b" if (LAB / "qwen3_14b.jsonl").exists() else "mistral24b"
    lab = {}
    for r in [json.loads(l) for l in open(LAB / f"{prim}.jsonl")]:
        if r["trunc"] == "native":
            lab[r["row_key"]] = r["label"]
    d["Rp"] = [(1.0 if lab.get(k) == "REFUSE" else 0.0 if lab.get(k) in LAB3 else np.nan) for k in d.row_key]
    d["Rl"] = d.R_lex.astype(float)
    bad = {k for k, v in d.groupby(["model", "curve", "step"]).degenerate.mean().items() if v > 0.20}
    out = {"primary": prim}
    for curve, col, paired in (("B", "Rp", True), ("B", "Rl", True), ("A1", "Rp", False), ("A1", "Rl", False)):
        if curve == "B":
            sub = d[(d.curve == "trial") & (d.in_P100 == 1) & d.arm.isin(["en_bt", "sl_mt"])]
        else:
            sub = d[(d.curve == "lambda") & d.arm.isin(["en_bt", "sl_mt"])]
        sub = sub[[(m, c, s) not in bad for m, c, s in zip(sub.model, sub.curve, sub.step)]]
        steps = {m: sorted(sub[sub.model == m].step.unique()) for m in ("gemma_it", "gams3_it")}
        if curve == "B":
            common = sorted(set(steps["gemma_it"]) & set(steps["gams3_it"]))
            steps = {m: common for m in steps}
        items = sorted(set(sub[sub.arm == "en_bt"].item_id) & set(sub[sub.arm == "sl_mt"].item_id))
        idx = {i: j for j, i in enumerate(items)}
        mats = {}
        for m in ("gemma_it", "gams3_it"):
            sidx = {s: j for j, s in enumerate(steps[m])}
            for arm in ("en_bt", "sl_mt"):
                A = np.full((len(steps[m]), len(items)), np.nan)
                g = sub[(sub.model == m) & (sub.arm == arm)]
                for s, it, v in zip(g.step, g.item_id, g[col]):
                    if s in sidx and it in idx and not np.isnan(v):
                        A[sidx[s], idx[it]] = v
                mats[(m, arm)] = A

        def g3(wsel=None, ssel=None):
            a = {}
            for m in ("gemma_it", "gams3_it"):
                E, S = mats[(m, "en_bt")], mats[(m, "sl_mt")]
                ok = ~np.isnan(E) & ~np.isnan(S)
                w = np.ones(E.shape[1]) if wsel is None else wsel
                kE = (np.where(ok, E, 0) * w).sum(1)
                kS = (np.where(ok, S, 0) * w).sum(1)
                nn = (ok * w).sum(1)
                sel = np.arange(len(nn)) if ssel is None else ssel
                keep = nn[sel] > 0
                a[m] = irls(hlogit(kE[sel][keep], nn[sel][keep]), kS[sel][keep], nn[sel][keep])[0]
            return a["gams3_it"] - a["gemma_it"]

        pt = g3()
        rng = np.random.default_rng(SEED)
        nI = len(items)
        boots = []
        nS = {m: len(steps[m]) for m in steps}
        for _ in range(2000):
            w = np.bincount(rng.integers(0, nI, nI), minlength=nI).astype(float)
            if paired:
                s = rng.integers(0, nS["gemma_it"], nS["gemma_it"])
                boots.append(g3(w, s))
            else:
                boots.append(g3(w, None))  # steps few; item bootstrap dominates
        boots = np.array([b for b in boots if np.isfinite(b)])
        out[f"{curve}|{col}"] = {"G3_50": float(pt), "CI95": np.percentile(boots, [2.5, 97.5]).tolist(),
                                 "n_items": nI, "n_steps": {m: len(v) for m, v in steps.items()}}
    # compare to eval_results.json
    ev_p = WS / "results/eval_results.json"
    cmp = {}
    if ev_p.exists():
        ev = json.loads(ev_p.read_text())
        pairs = {"B|Rp": ("B", "primary_R"), "B|Rl": ("B", "lexicon"), "A1|Rp": ("A1", "primary_R"), "A1|Rl": ("A1", "lexicon")}
        for k, (cur, rn) in pairs.items():
            main_r = ev["step3_lag"].get(cur, {}).get(rn, {}).get("G3_50")
            if isinstance(main_r, dict):
                dp = abs(out[k]["G3_50"] - main_r["est"])
                dci = max(abs(out[k]["CI95"][0] - main_r["CI95"][0]), abs(out[k]["CI95"][1] - main_r["CI95"][1])) if "CI95" in main_r else None
                cmp[k] = {"rederive_G3": out[k]["G3_50"], "main_G3": main_r["est"], "abs_diff_point": dp,
                          "point_ok_1e-6": dp < 1e-6, "max_CI_diff": dci, "CI_ok_0.05": (dci is not None and dci < 0.05)}
    out["comparison_to_main"] = cmp
    (WS / "work/rederive.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(cmp, indent=1))


if __name__ == "__main__":
    main()
