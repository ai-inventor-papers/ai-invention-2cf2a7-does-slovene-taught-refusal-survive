#!/usr/bin/env python3
"""Independent second code path (numpy/scipy/pandas only; never imports vendor/, engine.py or eval.py).
Recomputes the headline point estimates from labels/readout_rows.jsonl.gz with its own Newton-Raphson binomial GLM,
its own Se/Sp and Rogan-Gladen, and its own HKSJ pooling, and compares with results/recompute.json.
Tolerances: 1e-6 for rates / Se-Sp / G3_orig; 1e-4 for GLM optima (different optimiser, no ridge); pooled estimates from
the main path's SEs to 1e-4.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]


def hl(k, n):
    p = (k + 0.5) / (n + 1.0)
    return np.log(p / (1 - p))


def glm(x, k, n):
    """exact binomial MLE of logit(p) = a + b x by Newton-Raphson."""
    beta = np.array([np.log((k.sum() + .5) / (n.sum() - k.sum() + .5)), 0.0])
    X = np.column_stack([np.ones_like(x), x])
    for _ in range(200):
        mu = 1 / (1 + np.exp(-(X @ beta)))
        g = X.T @ (k - n * mu)
        H = X.T @ (X * (n * mu * (1 - mu))[:, None])
        step = np.linalg.solve(H + 1e-12 * np.eye(2), g)
        beta = beta + step
        if np.max(np.abs(step)) < 1e-12:
            break
    return beta


def counts(d, m, col, w=None):
    out = {}
    for arm in ("en_bt", "sl_mt"):
        g = d[(d.model == m) & (d.arm == arm) & d[col].notna()]
        ww = np.ones(len(g)) if w is None else g[w].values
        k = pd.Series(g[col].values * ww).groupby(g.step.values).sum()
        n = pd.Series(ww).groupby(g.step.values).sum()
        out[arm] = (k, n)
    steps = sorted(set(out["en_bt"][0].index) & set(out["sl_mt"][0].index))
    return (np.array(steps), out["en_bt"][0].reindex(steps).values, out["en_bt"][1].reindex(steps).values,
            out["sl_mt"][0].reindex(steps).values, out["sl_mt"][1].reindex(steps).values)


def g3_point(d, col, fit_orig, corr=None):
    ab, g0, xs = {}, {}, {}
    for m in ("gemma_it", "gams3_it"):
        st, kE, nE, kS, nS = counts(d, m, col)
        if corr is not None:
            kE = np.array([corr(m, "en", s, k / n) * n for s, k, n in zip(st, kE, nE)])
            kS = np.array([corr(m, "sl", s, k / n) * n for s, k, n in zip(st, kS, nS)])
        sel = np.ones(len(st), bool) if fit_orig else st != 0
        x = hl(kE[sel], nE[sel])
        ab[m] = glm(x, kS[sel], nS[sel])
        xs[m] = x
        o = np.where(st == 0)[0]
        g0[m] = hl(kS[o[0]], nS[o[0]]) - hl(kE[o[0]], nE[o[0]]) if len(o) else np.nan
    G3 = ab["gams3_it"][0] - ab["gemma_it"][0]
    lo, hi = max(xs[m].min() for m in xs), min(xs[m].max() for m in xs)
    grid = np.linspace(lo, hi, 21)
    IG = float(np.mean((ab["gams3_it"][0] + ab["gams3_it"][1] * grid) - (ab["gemma_it"][0] + ab["gemma_it"][1] * grid))) if hi > lo else np.nan
    G3o = g0["gams3_it"] - g0["gemma_it"]
    return {"G3": G3, "G3_orig": G3o, "G3_edit": G3 - G3o, "IG": IG}


def main():
    df = pd.read_json(ROOT / "labels/readout_rows.jsonl.gz", lines=True, compression="gzip")
    rec = json.loads((ROOT / "results/recompute.json").read_text())
    curves = rec["curves"]
    df["R"] = np.where(df.prim3.isin(["REFUSE", "PARTIAL", "COMPLY"]), (df.prim3 == "REFUSE").astype(float), np.nan)
    df["adjR"] = np.where(df.adj4.isin(["REFUSE", "PARTIAL", "COMPLY", "OFF_TASK"]), df.adj4.isin(["REFUSE", "OFF_TASK"]).astype(float), np.nan)
    h = df[(df.kind == "harmful") & df.arm.isin(["en_bt", "sl_mt"])]
    frames = {"exp9_lambda": (h[(h.source == "exp9") & h.curve.isin(["orig", "lambda"])], True),
              "exp11_final": (h[(h.source == "exp11") & (h.priority == 1)], False),
              "exp8_A1": (h[(h.source == "exp8") & h.curve.isin(["orig", "lambda"])], False)}
    # Se/Sp by model x lang x condition (HT-weighted)
    a = df[df.adjR.notna() & df.R.notna()].copy()
    a["cell"] = a.model + "|" + a.lang + "|" + np.where(a.condition == "orig", "orig", "edited")
    sesp = {}
    for c, g in a.groupby("cell"):
        pos, neg = g.adjR == 1, g.adjR == 0
        se = float((g.adj_w[pos] * (g.R[pos] == 1)).sum() / g.adj_w[pos].sum()) if pos.any() else np.nan
        sp = float((g.adj_w[neg] * (g.R[neg] == 0)).sum() / g.adj_w[neg].sum()) if neg.any() else np.nan
        sesp[c] = (se, sp)

    def rg(m, lang, s, p):
        se, sp = sesp.get(f"{m}|{lang}|{'orig' if s == 0 else 'edited'}", (np.nan, np.nan))
        if not np.isfinite(se + sp) or se + sp - 1 <= 0.05:
            return p
        return float(np.clip((p + sp - 1) / (se + sp - 1), 0.005, 0.995))

    checks = []
    for name, (fr, fo) in frames.items():
        for rd, corr in (("raw_primary", None), ("RG", rg)):
            mine = g3_point(fr, "R", fo, corr)
            main_ = curves.get(f"{name}|{rd}|R", {})
            for k, v in mine.items():
                ref = main_.get(k, {}).get("est")
                if ref is None or not np.isfinite(v):
                    continue
                tol = 1e-6 if k == "G3_orig" and rd == "raw_primary" else 1e-4
                checks.append({"quantity": f"{name}|{rd}|{k}", "rederive": v, "main": ref, "abs_diff": abs(v - ref), "tol": tol,
                               "ok": bool(abs(v - ref) < tol)})
    # Se/Sp vs error matrices
    em = json.loads((ROOT / "results/judge_error_matrices_v2.json").read_text())
    for c, (se, sp) in sesp.items():
        r = em["cells"].get(c, {}).get("instruments", {}).get("primary_gemini|R", {})
        for nm, v in (("Se", se), ("Sp", sp)):
            if r.get(nm) is not None and np.isfinite(v):
                checks.append({"quantity": f"{c}|{nm}", "rederive": v, "main": r[nm], "abs_diff": abs(v - r[nm]), "tol": 1e-6,
                               "ok": bool(abs(v - r[nm]) < 1e-6)})
    # pooled HKSJ from the main path's per-body estimates and SEs (independent pooling code)
    for key, p in rec["pooling"].items():
        if key == "note":
            continue
        y, s = np.array(p["y"]), np.array(p["se"])
        k = len(y)
        v = s ** 2
        w = 1 / v
        mu_fe = np.sum(w * y) / np.sum(w)
        t = p["REML_HKSJ"]["tau2"]
        wi = 1 / (v + t)
        mu = np.sum(wi * y) / np.sum(wi)
        q = np.sum(wi * (y - mu) ** 2) / (k - 1)
        se_hk = math.sqrt(q / np.sum(wi))
        lo = mu - stats.t.ppf(0.975, k - 1) * se_hk
        # REML score equation at the reported tau2 (should be ~0 or tau2 = 0 at the boundary)
        score = np.sum(wi ** 2 * ((y - mu) ** 2 - v)) / np.sum(wi ** 2) + 1 / np.sum(wi) - t
        checks.append({"quantity": f"pool|{key}|est", "rederive": float(mu), "main": p["REML_HKSJ"]["est"], "abs_diff": float(abs(mu - p["REML_HKSJ"]["est"])),
                       "tol": 1e-4, "ok": bool(abs(mu - p["REML_HKSJ"]["est"]) < 1e-4)})
        checks.append({"quantity": f"pool|{key}|CI_lo", "rederive": float(lo), "main": p["REML_HKSJ"]["CI95"][0],
                       "abs_diff": float(abs(lo - p["REML_HKSJ"]["CI95"][0])), "tol": 1e-4, "ok": bool(abs(lo - p["REML_HKSJ"]["CI95"][0]) < 1e-4)})
        checks.append({"quantity": f"pool|{key}|REML_fixed_point", "rederive": float(score), "main": 0.0, "abs_diff": float(abs(score)) if t > 0 else 0.0,
                       "tol": 1e-4, "ok": bool(t == 0 or abs(score) < 1e-4)})
        checks.append({"quantity": f"pool|{key}|FE", "rederive": float(mu_fe), "main": p["FE"]["est"], "abs_diff": float(abs(mu_fe - p["FE"]["est"])),
                       "tol": 1e-6, "ok": bool(abs(mu_fe - p["FE"]["est"]) < 1e-6)})
    # pooled G3 / G3_edit rebuilt from the REDERIVED per-body points (main path's SEs), independent HKSJ code
    for stat in ("G3", "G3_edit"):
        ys, ses, bodies = [], [], []
        for name in ("exp8_A1", "exp9_lambda", "exp11_final"):
            fr, fo = frames[name]
            v = g3_point(fr, "R", fo)[stat]
            se = rec["curves"].get(f"{name}|raw_primary|R", {}).get(stat, {}).get("SE")
            if se:
                ys.append(v)
                ses.append(se)
                bodies.append(name)
        if len(ys) >= 2:
            y, sv = np.array(ys), np.array(ses)
            k = len(y)
            v = sv ** 2
            t = rec["pooling"][f"primary|raw_primary|{stat}"]["REML_HKSJ"]["tau2"]
            wi = 1 / (v + t)
            mu = float(np.sum(wi * y) / np.sum(wi))
            main_ = rec["pooling"][f"primary|raw_primary|{stat}"]["REML_HKSJ"]["est"]
            checks.append({"quantity": f"pooled_from_rederived_points|{stat}", "rederive": mu, "main": main_,
                           "abs_diff": abs(mu - main_), "tol": 1e-4, "ok": bool(abs(mu - main_) < 1e-4), "bodies": bodies})

    # per-cell primary refusal rates
    cr = df[df.R.notna()].groupby(["source", "model", "lang", "condition"]).R.mean()
    main_cells = {(c["source"], c["model"], c["lang"], c["condition"]): c["refusal_R"] for c in rec["sanity"]["cells"]}
    for k, v in cr.items():
        if k in main_cells and main_cells[k] is not None:
            checks.append({"quantity": f"rate|{'|'.join(k)}", "rederive": float(v), "main": main_cells[k], "abs_diff": float(abs(v - main_cells[k])),
                           "tol": 1e-6, "ok": bool(abs(v - main_cells[k]) < 1e-6)})
    out = {"n_checks": len(checks), "n_ok": int(sum(c["ok"] for c in checks)), "all_ok": bool(all(c["ok"] for c in checks)), "checks": checks,
           "note": "independent path: own GLM (exact Newton MLE), own Se/Sp, own RG and HKSJ; never imports vendor/, engine.py, eval.py"}
    (ROOT / "results/rederive.json").write_text(json.dumps(out, indent=1))
    print(f"rederive: {out['n_ok']}/{out['n_checks']} ok")
    for c in checks:
        if not c["ok"]:
            print("MISMATCH", c)


if __name__ == "__main__":
    main()
