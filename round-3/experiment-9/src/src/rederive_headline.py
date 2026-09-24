#!/usr/bin/env python3
"""THIRD code path for the headline number (TODO 5): pandas + statsmodels, reading results/{model}/gens.jsonl and
gens_j1.jsonl directly (NOT items_final.jsonl, NOT analysis.json, NOT stats_core). Also runs the placebo: the same
statistic on permuted MODEL labels must lose significance."""
import json, sys
import numpy as np, pandas as pd
import statsmodels.api as sm
from pathlib import Path
WS = Path(__file__).resolve().parent.parent
LAM = ["orig"] + [f"lambda_{x:.2f}" for x in (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)]

rows = []
for m in ("gemma_it", "gams3_it"):
    j1 = {r["key"]: r["j1"] for r in map(json.loads, (WS / "results" / m / "gens_j1.jsonl").open())}
    for r in map(json.loads, (WS / "results" / m / "gens.jsonl").open()):
        if r["kind"] != "harmful" or r["step_name"] not in LAM or r["arm"] not in ("en_bt", "sl_mt"):
            continue
        lab = j1.get(f"{r['model']}|{r['step_name']}|{r['arm']}|{r['item_id']}")
        if lab:
            rows.append((r["model"], r["step_name"], r["arm"], r["item_id"], int(lab == "REFUSE")))
df = pd.DataFrame(rows, columns=["model", "step", "arm", "item", "ref"])

def a_hat(d):
    p = d.pivot_table(index=["model", "step"], columns="arm", values="ref", aggfunc=["sum", "count"])
    out = {}
    for mdl in d.model.unique():
        s = p.loc[mdl]
        kE, nE = s[("sum", "en_bt")].values, s[("count", "en_bt")].values
        kS, nS = s[("sum", "sl_mt")].values, s[("count", "sl_mt")].values
        x = np.log(((kE + .5) / (nE + 1)) / (1 - (kE + .5) / (nE + 1)))
        g = sm.GLM(np.column_stack([kS, nS - kS]), sm.add_constant(x), family=sm.families.Binomial()).fit()
        out[mdl] = g.params[0]
    return out["gams3_it"] - out["gemma_it"]

g3 = a_hat(df)
rng = np.random.default_rng(7)
perm = []
for _ in range(400):                      # placebo: swap model labels within each (step, arm, item)
    d2 = df.copy()
    flip = rng.random(len(LAM)) < 0.5
    fl = {s: f for s, f in zip(sorted(df.step.unique()), flip)}
    d2["model"] = [("gams3_it" if r.model == "gemma_it" else "gemma_it") if fl[r.step] else r.model
                   for r in df.itertuples()]
    perm.append(a_hat(d2))
perm = np.array(perm)
ref = json.loads((WS / "results" / "analysis.json").read_text())["G3"]["lambda|j1|R1"]
out = {"g3_third_code_path": float(g3), "g3_analysis_py": ref["G3"], "abs_diff": abs(g3 - ref["G3"]),
       "matches_within_0.05": bool(abs(g3 - ref["G3"]) < 0.05),
       "placebo_model_label_swap": {"n": len(perm), "mean": float(perm.mean()), "sd": float(perm.std()),
                                    "p_two_sided": float((np.sum(np.abs(perm) >= abs(g3)) + 1) / (len(perm) + 1)),
                                    "centred_on_zero": bool(abs(perm.mean()) < 0.25 * max(perm.std(), 1e-9)),
                                    "test_fails_on_placebo": bool(np.mean(np.abs(perm) >= abs(g3)) > 0.05)},
       "note": "pandas pivot + statsmodels GLM on the raw gens/gens_j1 files; analysis.py uses hand-written IRLS on "
               "numpy matrices built from items_final.jsonl, audit.py uses scipy BFGS on dict counts"}
(WS / "results" / "rederive_headline.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
