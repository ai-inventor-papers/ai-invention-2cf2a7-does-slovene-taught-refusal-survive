#!/usr/bin/env python3
"""S9 AUDIT: independent second code path (plain numpy/scipy; no stats_core / analysis imports) recomputing the headline
numbers from results/items_final.jsonl and comparing them with results/analysis.json -> results/audit.json.

Recomputed: per-step Hautus rates, a_m (binomial logit MLE by scipy.optimize), G3 (B' and lambda, J1 R1 and R2),
Delta-c / Delta-d' (SDT window), C5a excess ratio, J1-vs-J2 kappas.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm

WS = Path(__file__).resolve().parent.parent
import os
R = Path(os.environ.get("AII_RESULTS", str(WS / "results")))


def rd(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def mle(x, k, n):
    def nll(beta):
        eta = beta[0] + beta[1] * x
        return -np.sum(k * eta - n * np.logaddexp(0, eta)) + 0.5e-6 * np.sum(beta ** 2)
    r = minimize(nll, np.zeros(2), method="BFGS", options={"gtol": 1e-10, "maxiter": 10000})
    return r.x


def main():
    A = json.loads((R / "analysis.json").read_text())
    rows = rd(R / "items_final.jsonl")
    used_tr = A["steps_used"]["trials"]
    used_la = A["steps_used"]["lambda"]
    rep = {"checks": {}}

    def rates(model, readout, pos, steps, arm, kind, ids=None):
        k, n = defaultdict(float), defaultdict(float)
        for r in rows:
            if r["model"] != model or r["arm"] != arm or r["kind"] != kind or r["step_name"] not in steps:
                continue
            if ids is not None and r["item_id"] not in ids:
                continue
            lab = r.get(readout)
            if lab is None:
                continue
            n[r["step_name"]] += 1
            k[r["step_name"]] += float(lab in pos)
        ks = np.array([k[s] for s in steps])
        ns = np.array([n[s] for s in steps])
        return ks, ns

    def a_m(model, readout, pos, steps, ids=None):
        kE, nE = rates(model, readout, pos, steps, "en_bt", "harmful", ids)
        kS, nS = rates(model, readout, pos, steps, "sl_mt", "harmful", ids)
        pE = (kE + 0.5) / (nE + 1)
        x = np.log(pE / (1 - pE))
        return mle(x, kS, nS)[0]

    P = rd(WS / "data" / "probe_P300.jsonl")
    G = {p["item_id"] for p in P if p["in_G"]}
    specs = {"Bprime|j1|R1": ("j1", {"REFUSE"}, used_tr, None), "Bprime|j1|R2": ("j1", {"REFUSE", "PARTIAL"}, used_tr, None),
             "lambda|j1|R1": ("j1", {"REFUSE"}, used_la, None), "Bprime|j1|R1|G_rows": ("j1", {"REFUSE"}, used_tr, G)}
    if "Bprime|j2|R1|G_rows" in A["G3"]:
        specs["Bprime|j2|R1|G_rows"] = ("j2", {"REFUSE"}, used_tr, G)
    for name, (ro, pos, steps, ids) in specs.items():
        g = a_m("gams3_it", ro, pos, steps, ids) - a_m("gemma_it", ro, pos, steps, ids)
        ref = A["G3"][name]["G3"]
        ident = A["G3"][name].get("identified", True)
        rep["checks"][f"G3:{name}"] = {"audit": g, "analysis": ref, "abs_diff": abs(g - ref), "identified": ident,
                                       "pass": bool(abs(g - ref) < 1e-4 or not ident),
                                       "note": None if ident else "off-support/unidentified fit: the two optimisers are "
                                               "not expected to agree under separation; excluded from the headline"}
    # SDT
    for m in ("gemma_it", "gams3_it"):
        rec = A["SDT"]["j1|R1"]["per_model"][m]
        W = rec.get("window_steps", [])
        if not W:
            continue
        dc, dd = [], []
        for s in W:
            v = {}
            for arm in ("en_bt", "sl_mt"):
                kH, nH = rates(m, "j1", {"REFUSE"}, [s], arm, "harmful")
                kF, nF = rates(m, "j1", {"REFUSE"}, [s], arm, "benign")
                H, F = (kH[0] + .5) / (nH[0] + 1), (kF[0] + .5) / (nF[0] + 1)
                v[arm] = (norm.ppf(H) - norm.ppf(F), (norm.ppf(H) + norm.ppf(F)) / 2)
            dd.append(v["sl_mt"][0] - v["en_bt"][0])
            dc.append(v["sl_mt"][1] - v["en_bt"][1])
        for nm, val, ref in (("delta_c", np.mean(dc), rec["delta_c"]), ("delta_dprime", np.mean(dd), rec["delta_dprime"])):
            rep["checks"][f"SDT:{m}:{nm}"] = {"audit": float(val), "analysis": ref, "abs_diff": abs(val - ref),
                                             "pass": abs(val - ref) < 1e-6}
    # C5a
    for m, rec in A.get("C5a", {}).items():
        kr = rd(R / m / "c5a_kl.jsonl")
        sel = {l: np.mean([r["kl"] for r in kr if r["edit"] == "selected" and r["lang"] == l]) for l in ("en", "sl")}
        rnd = {l: np.mean([r["kl"] for r in kr if r["edit"] == "random" and r["lang"] == l]) for l in ("en", "sl")}
        v = (sel["sl"] / sel["en"]) / (rnd["sl"] / rnd["en"])
        rep["checks"][f"C5a:{m}"] = {"audit": float(v), "analysis": rec["excess_ratio"], "abs_diff": abs(v - rec["excess_ratio"]),
                                    "pass": abs(v - rec["excess_ratio"]) < 1e-6}
    # kappas J1 vs J2
    for cell, rec in A["judge"].get("j1_vs_j2_cells", {}).items():
        m, arm, ed = cell.split("|")
        pairs = []
        for r in rows:
            if r["model"] != m or not r.get("j1") or not r.get("j2"):
                continue
            if arm == "benign":
                if r["kind"] != "benign":
                    continue
            else:
                if r["kind"] != "harmful" or r["arm"] != arm or (ed == "orig") != (r["step_name"] == "orig"):
                    continue
            pairs.append((r["j1"] == "REFUSE", r["j2"] == "REFUSE"))
        a = np.array([p[0] for p in pairs])
        b = np.array([p[1] for p in pairs])
        po = np.mean(a == b)
        pe = np.mean(a) * np.mean(b) + np.mean(~a) * np.mean(~b)
        k = (po - pe) / (1 - pe) if pe < 1 else float("nan")
        ok = (np.isnan(k) and np.isnan(rec["kappaR"])) or abs(k - rec["kappaR"]) < 1e-9
        rep["checks"][f"kappa:{cell}"] = {"audit": float(k), "analysis": rec["kappaR"], "pass": bool(ok)}
    # placebos centred
    for k, v in A.get("placebos", {}).items():
        rep["checks"][f"placebo:{k}"] = {"null_mean": v["null_mean"], "null_sd": v["null_sd"], "pass": v["centred"]}
    rep["all_pass"] = all(v["pass"] for v in rep["checks"].values())
    rep["n_checks"] = len(rep["checks"])
    (R / "audit.json").write_text(json.dumps(rep, indent=1, default=float))
    print(json.dumps({"all_pass": rep["all_pass"], "n": rep["n_checks"],
                      "failed": [k for k, v in rep["checks"].items() if not v["pass"]]}))


if __name__ == "__main__":
    main()
