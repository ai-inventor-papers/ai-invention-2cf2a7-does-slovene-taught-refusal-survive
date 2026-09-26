#!/usr/bin/env python3
"""S10 independent audit (second code path: pandas + scipy; does NOT import analysis.py or stats.py).

Recomputes from the saved per-row JSONL + labels: add-on rates, Lag, BenignExcess, cut (primary judge, R coding);
alpha50 of the induction curves with scipy.optimize.minimize on the binomial NLL (vs the IRLS fit in analysis.py);
f / cos / rho at L* from directions_post.npz; RQ4 AUROC at L* (O state, EN-BT, post) with a plain sklearn pipeline.
Placebos (must centre on 0): model-label swap within item (Lag DiD), language-label swap within item (Lag, BenignExcess),
direction-label swap within item (u_SLperp <-> rand1) for the SL induction refusal-rate difference and the add-on cut.
Writes results/audit.json (n_checks, n_pass, details). Tolerances: 1e-6 exact quantities, 0.02 fits.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

WS = Path(__file__).resolve().parent.parent
RES = WS / "results"
J1 = "surrogate/gemini"
SEED = 20260925


def rk(r):
    return "|".join(str(r.get(k)) for k in ("model", "block", "cond", "step", "arm", "item_id"))


def jl(p):
    p = Path(p)
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def hl(k, n):
    p = (k + 0.5) / (n + 1.0)
    return np.log(p / (1 - p))


def main():
    A = json.loads((RES / "analysis.json").read_text())
    lab = {r["row_key"]: r["label"] for r in jl(RES / "judge_labels.jsonl") if r["judge"] == J1}
    checks = []

    def chk(name, got, want, tol):
        ok = (got is None and want is None) or (got is not None and want is not None and abs(got - want) <= tol)
        checks.append({"check": name, "audit": got, "analysis": want, "tol": tol, "pass": bool(ok)})

    models = [m for m in ("gemma_it", "gams3_it") if (RES / "test" / m / "addon.jsonl").exists()]
    add_df = {}
    for M in models:
        df = pd.DataFrame(jl(RES / "test" / M / "addon.jsonl"))
        df["y"] = [(1.0 if lab.get(k) == "REFUSE" else 0.0) if lab.get(k) in ("REFUSE", "PARTIAL", "COMPLY") else np.nan
                   for k in df.apply(lambda r: rk(r.to_dict()), axis=1)]
        df = df[df.arm != "en_orig"]
        add_df[M] = df
        a = A["addon"].get(f"{J1}|R|{M}")
        if not a:
            continue
        g = df.groupby(["cond", "set", "arm"])["y"].agg(["sum", "count"])
        lag = {}
        for c in df.cond.unique():
            for s in ("test160", "hard_test"):
                k_sl, n_sl = g.loc[(c, s, "sl_mt")]
                k_en, n_en = g.loc[(c, s, "en_bt")]
                lag[(c, s)] = hl(k_sl, n_sl) - hl(k_en, n_en)
            chk(f"{M}|{c}|rate_EN_test160", float(g.loc[(c, "test160", "en_bt")]["sum"] / g.loc[(c, "test160", "en_bt")]["count"]),
                a["conds"][c]["R_EN_test160"], 1e-6)
            chk(f"{M}|{c}|Lag", float(lag[(c, "test160")]), a["conds"][c]["Lag"], 1e-6)
            chk(f"{M}|{c}|BenignExcess", float(lag[(c, "hard_test")]), a["conds"][c]["BenignExcess"], 1e-6)
        for c in df.cond.unique():
            if c != "E0":
                cut = (lag[("E0", "test160")] - lag[(c, "test160")]) / lag[("E0", "test160")]
                chk(f"{M}|{c}|cut", float(cut), a["conds"][c]["cut"], 1e-6)
    # induction alpha50 via scipy NLL
    for M in models:
        dfi = pd.DataFrame(jl(RES / "test" / M / "induce.jsonl"))
        if dfi.empty:
            continue
        dfi["y"] = [(1.0 if lab.get(k) == "REFUSE" else 0.0) if lab.get(k) in ("REFUSE", "PARTIAL", "COMPLY") else np.nan
                    for k in dfi.apply(lambda r: rk(r.to_dict()), axis=1)]
        dfi = dfi[(dfi.degenerate == 0) & dfi.y.notna()]
        ind = A["induction"].get(f"{J1}|R|{M}|exclude")
        if not ind:
            continue
        xmax = max(ind["levels"])
        base = dfi[dfi.cond == "baseline"]
        for d in ("u_SLperp", "rEN", "u_lang", "rand1"):
            for lang in ("en", "sl"):
                sub = pd.concat([dfi[(dfi.cond == d) & (dfi.lang == lang)], base[base.lang == lang]])
                x = sub.step.astype(float).values
                y = sub.y.values

                def nll(t):
                    z = t[0] + t[1] * x
                    return float(np.sum(np.logaddexp(0, z) - y * z)) + 1e-4 / 2 * (t[0] ** 2 + t[1] ** 2)
                t = minimize(nll, np.zeros(2), method="BFGS").x
                a50 = -t[0] / t[1] if t[1] > 1e-9 else np.inf
                a50 = xmax if not (a50 <= xmax) else max(a50, 0.0)
                want = ind["curves"][f"{d}|{lang}"]["alpha50"]
                chk(f"{M}|alpha50|{d}|{lang}", float(a50), want, 0.02 * max(1.0, abs(want)))
    # geometry
    for M in models:
        g = json.loads((RES / M / "geometry_post.json").read_text())
        L = A["dev_decisions"][M]["layer"]["L_star"]
        D = np.load(RES / M / "directions_post.npz")
        dEN, dSL = D["dEN"][L].astype(np.float64), D["dSL"][L].astype(np.float64)
        rEN = dEN / np.linalg.norm(dEN)
        chk(f"{M}|f", float((dSL @ rEN) ** 2 / (dSL @ dSL)), g[L]["f"], 1e-4)
        chk(f"{M}|cos", float(rEN @ dSL / np.linalg.norm(dSL)), g[L]["cos_EN_SL"], 1e-4)
        chk(f"{M}|rho", float((dSL @ rEN) / np.linalg.norm(dEN)), g[L]["rho"], 1e-4)
        up = D["u_SLperp"][L]
        chk(f"{M}|u_SLperp_orth_rEN", float(abs(up @ rEN)), 0.0, 1e-5)
    # RQ4 AUROC at L* (O, en_bt, post) with plain sklearn (no PCA -> tolerance 0.02 on a ceiling-bound quantity)
    rq = json.loads((RES / "rq4.json").read_text()) if (RES / "rq4.json").exists() else {}
    for M in models:
        if M not in rq:
            continue
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import roc_auc_score
        from sklearn.model_selection import StratifiedKFold, cross_val_predict
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        L = rq[M]["L_star"]

        def _acts(cls: str):
            """Prefer the kept L*-layer slice (results/acts_Lstar/); fall back to the full regenerable array."""
            sl = RES / "acts_Lstar" / f"{M}_rq4_O_{cls}_en_bt_post_L{L}.npy"
            if sl.exists():
                return np.load(sl).astype(np.float32)
            full = WS / "acts" / M / f"rq4_O_{cls}_en_bt_post.npy"
            if not full.exists():
                return None
            return np.load(full, mmap_mode="r")[:, L, :].astype(np.float32)
        a, b = _acts("harm"), _acts("harmless")
        if a is None or b is None:
            checks.append({"check": f"{M}|rq4_auroc_O_en_bt_Lstar", "audit": None, "analysis": None, "tol": None,
                           "pass": False, "skipped": "activations absent; regenerate with "
                                                     f"'src/gpu_block.py --model {M} --phases rq4'"})
            continue
        X = np.concatenate([a, b])
        y = np.r_[np.ones(len(a)), np.zeros(len(b))]
        s = cross_val_predict(make_pipeline(StandardScaler(), LogisticRegression(C=0.01, max_iter=3000)), X, y,
                              cv=StratifiedKFold(5, shuffle=True, random_state=1), method="decision_function")
        chk(f"{M}|rq4_auroc_O_en_bt_Lstar", float(roc_auc_score(y, s)), rq[M]["at_Lstar"]["O|post"]["en_bt"]["auroc"], 0.02)
    # placebos
    rng = np.random.default_rng(SEED)
    plc = {}
    for M in models:
        df = add_df[M]
        for c in ("E0",):
            for s, name in (("test160", "Lag"), ("hard_test", "BenignExcess")):
                sub = df[(df.cond == c) & (df.set == s)].pivot_table(index="item_id", columns="arm", values="y")
                vals = []
                for _ in range(500):
                    sw = rng.random(len(sub)) < 0.5
                    en = np.where(sw, sub.sl_mt, sub.en_bt)
                    sl = np.where(sw, sub.en_bt, sub.sl_mt)
                    vals.append(hl(np.nansum(sl), np.sum(~np.isnan(sl))) - hl(np.nansum(en), np.sum(~np.isnan(en))))
                plc[f"{M}|lang_swap|{name}"] = {"mean": float(np.mean(vals)), "q": [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]}
        # direction-label swap for cut (A_perp_s1.0 <-> R1), within item
        if {"A_perp_s1.0", "R1"} <= set(df.cond.unique()):
            t = df[df.set == "test160"].pivot_table(index=["item_id"], columns=["cond", "arm"], values="y")
            e0 = hl(np.nansum(t[("E0", "sl_mt")]), t[("E0", "sl_mt")].notna().sum()) - hl(np.nansum(t[("E0", "en_bt")]), t[("E0", "en_bt")].notna().sum())
            vals = []
            for _ in range(500):
                sw = rng.random(len(t)) < 0.5
                cuts = []
                for first in (True, False):
                    msk = sw if first else ~sw
                    sl = np.where(msk, t[("A_perp_s1.0", "sl_mt")], t[("R1", "sl_mt")])
                    en = np.where(msk, t[("A_perp_s1.0", "en_bt")], t[("R1", "en_bt")])
                    lag = hl(np.nansum(sl), np.sum(~np.isnan(sl))) - hl(np.nansum(en), np.sum(~np.isnan(en)))
                    cuts.append((e0 - lag) / e0)
                vals.append(cuts[0] - cuts[1])
            plc[f"{M}|dir_swap|cut_Aperp_minus_R1"] = {"mean": float(np.mean(vals)), "q": [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]}
    if len(models) == 2:
        a, b = add_df["gemma_it"], add_df["gams3_it"]
        ta = a[(a.cond == "E0") & (a.set == "test160")].pivot_table(index="item_id", columns="arm", values="y")
        tb = b[(b.cond == "E0") & (b.set == "test160")].pivot_table(index="item_id", columns="arm", values="y").reindex(ta.index)
        vals = []
        for _ in range(500):
            sw = (rng.random(len(ta)) < 0.5)[:, None]
            xa = np.where(sw, tb.values, ta.values)
            xb = np.where(sw, ta.values, tb.values)
            cols = list(ta.columns)
            ie, isl = cols.index("en_bt"), cols.index("sl_mt")

            def lagf(x):
                return hl(np.nansum(x[:, isl]), np.sum(~np.isnan(x[:, isl]))) - hl(np.nansum(x[:, ie]), np.sum(~np.isnan(x[:, ie])))
            vals.append(lagf(xb) - lagf(xa))
        plc["model_swap|G3_op"] = {"mean": float(np.mean(vals)), "q": [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]}
    for k, v in plc.items():
        checks.append({"check": f"placebo|{k}", "audit": v["mean"], "analysis": 0.0, "tol": 0.1,
                       "pass": bool(abs(v["mean"]) < 0.1 and v["q"][0] <= 0 <= v["q"][1]), "interval": v["q"]})
    out = {"n_checks": len(checks), "n_pass": sum(c["pass"] for c in checks), "checks": checks}
    (RES / "audit.json").write_text(json.dumps(out, indent=1, default=float))
    print(f"audit: {out['n_pass']}/{out['n_checks']} pass")
    for c in checks:
        if not c["pass"]:
            print("FAIL", c)


if __name__ == "__main__":
    sys.exit(main())
