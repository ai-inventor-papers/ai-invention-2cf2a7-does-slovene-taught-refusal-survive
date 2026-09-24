#!/usr/bin/env python3
"""TODO-5 independent re-derivation of the headline G3 numbers, through a DIFFERENT code path.

analysis.py fits the per-model GLM by hand-written IRLS; audit.py by scipy BFGS. This script uses a THIRD route:
pandas groupby for the per-step counts and statsmodels GLM (Binomial, logit) for a_m and b_m. It re-derives
G3 = a_GaMS - a_Gemma at EN-BT=50% for curves B, A1, A2 on the primary readout, prints them next to analysis.json,
and runs the model-label-swap PLACEBO (2,000 perms) confirming the observed |G3| is NOT reproduced under permutation
(a test that "passes" on shuffled labels would be vacuous). Reads results/items_final.jsonl only.
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm

from common import DATA, RESULTS, read_jsonl

CURVE = {"B": "trial", "A1": "lambda", "A2": "ablate"}


def hautus(k, n):
    p = (k + 0.5) / (n + 1.0)
    return np.log(p / (1 - p))


def per_step(df, readout):
    """pandas groupby -> per (model, step) EN/SL refusal counts over items scored in BOTH arms."""
    out = {}
    for (m, step), g in df.groupby(["model", "step"]):
        piv = g.pivot_table(index="item_id", columns="arm", values=readout, aggfunc="first")
        if "en_bt" not in piv or "sl_mt" not in piv:
            continue
        piv = piv.dropna(subset=["en_bt", "sl_mt"])
        if len(piv) == 0:
            continue
        out.setdefault(m, []).append((step, int(piv["en_bt"].sum()), int(piv["sl_mt"].sum()), len(piv)))
    return out


def fit_a(rows_ms):
    """statsmodels binomial GLM: k_SL ~ Hautus(logit p_EN); return intercept a (SL log-odds at EN=50%) and slope b."""
    arr = np.array([(hautus(kE, n), kS, n) for _, kE, kS, n in rows_ms], float)
    if len(arr) < 3:
        return None
    x, kS, n = arr[:, 0], arr[:, 1], arr[:, 2]
    X = sm.add_constant(x)
    m = sm.GLM(np.c_[kS, n - kS], X, family=sm.families.Binomial()).fit()
    return float(m.params[0]), float(m.params[1])


def g3_for(df, readout, curve, paired):
    ps = per_step(df[df.curve == CURVE[curve]], readout)
    if curve == "B":  # paired: keep steps present in both models
        common = set(s for s, *_ in ps.get("gemma_it", [])) & set(s for s, *_ in ps.get("gams3_it", []))
        ps = {m: [r for r in v if r[0] in common] for m, v in ps.items()}
    fits = {m: fit_a(v) for m, v in ps.items() if fit_a(v)}
    if set(fits) != {"gemma_it", "gams3_it"}:
        return None, ps
    return fits["gams3_it"][0] - fits["gemma_it"][0], ps


def main():
    A = json.loads((RESULTS / "analysis.json").read_text())
    ro = A["primary_readout"]
    rows = read_jsonl(RESULTS / "items_final.jsonl")
    P100 = {r["item_id"] for r in read_jsonl(DATA / "probe_P200.jsonl") if r["in_P100"]}
    df = pd.DataFrame([r for r in rows if r["arm"] in ("en_bt", "sl_mt") and r.get(ro) is not None])
    # drop steps flagged degenerate>20% to match analysis.py
    deg = df.groupby(["model", "curve", "step"])["degenerate"].mean()
    df = df[df.apply(lambda r: deg.get((r["model"], r["curve"], r["step"]), 0) <= 0.20, axis=1)]
    out = {"readout": ro, "rederived_G3": {}, "analysis_G3": {}, "match_0.05": {}}
    for c in ("B", "A1", "A2"):
        dfc = df[df.item_id.isin(P100)] if c == "B" else df
        g3, _ = g3_for(dfc, ro, c, c == "B")
        ana = A["G3"].get(c, {})
        ana_g3 = ana.get("primary", {}).get("G3") if isinstance(ana, dict) else None
        out["rederived_G3"][c] = g3
        out["analysis_G3"][c] = ana_g3
        if g3 is not None and ana_g3 is not None:
            out["match_0.05"][c] = bool(abs(g3 - ana_g3) < 0.05)
    # PLACEBO: model-label swap on B (paired by step) -> null G3 must be centred at 0 and |obs| an outlier
    dfB = df[(df.curve == "trial") & (df.item_id.isin(P100))].copy()
    obs = out["rederived_G3"]["B"]
    rng = np.random.default_rng(20260924)
    null = []
    steps = sorted(dfB.step.unique())
    for _ in range(2000):
        flip = {s: rng.random() < 0.5 for s in steps}
        d2 = dfB.copy()
        d2["model"] = d2.apply(lambda r: ({"gemma_it": "gams3_it", "gams3_it": "gemma_it"}[r["model"]]
                                          if flip[r["step"]] else r["model"]), axis=1)
        g3, _ = g3_for(d2, ro, "B", True)
        if g3 is not None:
            null.append(g3)
    null = np.array(null)
    p = float(np.mean(np.abs(null) >= abs(obs))) if obs is not None else None
    out["placebo_model_swap_B"] = {"obs_G3": obs, "null_mean": float(null.mean()), "null_sd": float(null.std()),
                                   "p_two_sided": p, "n_perm": len(null),
                                   "placebo_fails_as_required": bool(p is not None and p < 0.05 and abs(null.mean()) < 0.15)}
    (RESULTS / "rederive_headline.json").write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps(out, indent=2, default=float))
    if out["placebo_model_swap_B"]["obs_G3"] is not None and not out["placebo_model_swap_B"]["placebo_fails_as_required"]:
        print("WARNING: placebo did not behave as required", file=sys.stderr)


if __name__ == "__main__":
    main()
