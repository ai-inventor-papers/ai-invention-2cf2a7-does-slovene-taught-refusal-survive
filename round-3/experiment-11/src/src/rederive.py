#!/usr/bin/env python3
"""S9 AUDIT: independent second code path (pandas + statsmodels GLM; shares NO analysis code). Reads the raw
generation JSONL, the judge-label JSONL, protocol.yaml and the split manifest; recomputes the headline numbers and
compares them with results/analysis.json (|diff| < 1e-6 where the estimator is identical; GLM fits are compared at
1e-4 because a different optimiser is used). Placebos: (i) model labels swapped within item -> G3 ~ 0 (mean over
permutations); (ii) SL <-> EN_BT labels swapped within item x step -> per-model SL lag ~ 0; (iii) judge labels
shuffled within cell -> kappa ~ 0. Output: results/audit.json.
"""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import statsmodels.api as sm
import yaml
from scipy.stats import norm

from common import DATA, E5, FINAL_DIR, LABELS, RESULTS, ROOT, SEED


def jl(p):
    with open(p) as f:
        return [json.loads(x) for x in f if x.strip()]


def main() -> None:
    proto = yaml.safe_load((ROOT / "protocol.yaml").read_text())
    man = json.loads((DATA / "split_manifest_iter3.json").read_text())
    A = json.loads((RESULTS / "analysis.json").read_text())
    g = pd.concat([pd.DataFrame(jl(p)) for p in sorted(FINAL_DIR.glob("gens_*.jsonl"))]).drop_duplicates("key")
    q = pd.DataFrame(jl(LABELS / "labels_qwen3_14b_final.jsonl")).drop_duplicates("key", keep="last")
    g = g.merge(q[["key", "label"]].rename(columns={"label": "lq"}), on="key", how="left")
    # exp5 originals (lambda = 0) read independently: exp5 gens + exp5's Qwen3-14B labels
    l5 = pd.DataFrame(jl(E5 / "outputs/final/labels_local_qwen3.jsonl"))[["key", "qwen_label"]]
    e5 = pd.concat([pd.DataFrame(jl(E5 / "outputs/final" / f"gen_{m}.jsonl")) for m in ("gemma_it", "gams3_it")])
    e5 = e5[e5.set.isin(["refuseu_x", "hard"]) & e5.arm.isin(["EN_BT", "SL_MT", "EN_orig"])].merge(l5, on="key")
    e5 = e5.assign(item_id=np.where(e5.set == "refuseu_x", e5.pair_id, e5.item_id), condition="orig", **{"lambda": 0.0},
                   lq=e5.qwen_label)
    have = set(zip(g[g.condition == "orig"].model, g[g.condition == "orig"].set, g[g.condition == "orig"].arm,
                   g[g.condition == "orig"].item_id))
    e5 = e5[[(a, b, c, d) not in have for a, b, c, d in zip(e5.model, e5.set, e5.arm, e5.item_id)]]
    items = pd.DataFrame(jl(DATA / "items.jsonl"))[["set", "arm", "item_id", "is_harmful"]].drop_duplicates()
    e5 = e5.drop(columns=[c for c in ("is_harmful",) if c in e5]).merge(items, on=["set", "arm", "item_id"], how="inner")
    g = pd.concat([g, e5[["model", "set", "arm", "item_id", "condition", "lambda", "lq", "is_harmful"]]],
                  ignore_index=True)
    g["R"] = (g.lq == "REFUSE").astype(float).where(g.lq.notna())
    checks = []

    def chk(name, ours, theirs, tol=1e-6):
        ok = (ours is None and theirs is None) or (
            ours is not None and theirs is not None and np.isfinite(ours) and np.isfinite(theirs)
            and abs(ours - theirs) < tol)
        checks.append({"check": name, "rederived": ours, "pipeline": theirs, "tol": tol, "pass": bool(ok)})

    # 1. McNemar counts orig -> lambda=1 (RefusEU-x EN_BT / SL_MT)
    for r in A["mcnemar"]["q_R"]:
        if r["set"] != "refuseu_x":
            continue
        s = g[(g.model == r["model"]) & (g.set == "refuseu_x") & (g.arm == r["arm"])]
        o = s[s.condition == "orig"].set_index("item_id").R.dropna()
        e = s[(s.condition == "edit") & (s["lambda"] == 1.0)].set_index("item_id").R.dropna()
        ix = o.index.intersection(e.index)
        chk(f"mcnemar_b|{r['model']}|{r['arm']}", float(((o[ix] == 0) & (e[ix] == 1)).sum()), float(r["b_0to1"]))
        chk(f"mcnemar_c|{r['model']}|{r['arm']}", float(((o[ix] == 1) & (e[ix] == 0)).sum()), float(r["c_1to0"]))
        chk(f"rate_lam1|{r['model']}|{r['arm']}", float(e[ix].mean()), float(r["rate_lam1"]), 1e-4)
    # 2. G3 with statsmodels GLM (different optimiser)
    curve = set(man["CURVE_rank"][:proto["subsets"]["curve_n"]])
    lams = set(float(x) for x in proto["lambda_curve"]["lambdas"]["gemma_it"]) | {1.0}
    c = g[(g.set == "refuseu_x") & g.item_id.isin(curve) & g.condition.isin(["lam", "edit"]) & g["lambda"].isin(lams)
          & g.arm.isin(["EN_BT", "SL_MT"]) & g.model.isin(["gemma_it", "gams3_it"])]
    w = c.pivot_table(index=["model", "item_id", "lambda"], columns="arm", values="R").dropna().reset_index()

    def fit_a(ww):
        agg = ww.groupby("lambda").agg(ken=("EN_BT", "sum"), ksl=("SL_MT", "sum"), n=("SL_MT", "size"))
        pen = (agg.ken + 0.5) / (agg.n + 1)
        X = sm.add_constant(np.log(pen / (1 - pen)).values)
        y = np.column_stack([agg.ksl.values, (agg.n - agg.ksl).values])
        res = sm.GLM(y, X, family=sm.families.Binomial()).fit()
        return float(res.params[0])

    a = {m: fit_a(w[w.model == m]) for m in ("gemma_it", "gams3_it")} if len(w) else {}
    if a and "q_R" in A["G3"]:
        chk("G3_q_R", a["gams3_it"] - a["gemma_it"], A["G3"]["q_R"]["G3"], 1e-4)
        for m in a:
            chk(f"a_{m}_q_R", a[m], A["G3"]["q_R"]["per_model"][m]["a"], 1e-4)
    # placebo (i): model labels swapped within item
    rng = np.random.default_rng(SEED)
    pl = []
    items = w.item_id.unique() if len(w) else []
    for _ in range(100 if len(w) else 0):
        flip = set(items[rng.random(len(items)) < 0.5])
        ww = w.copy()
        ww.loc[ww.item_id.isin(flip), "model"] = ww.loc[ww.item_id.isin(flip), "model"].map(
            {"gemma_it": "gams3_it", "gams3_it": "gemma_it"})
        pl.append(fit_a(ww[ww.model == "gams3_it"]) - fit_a(ww[ww.model == "gemma_it"]))
    placebo = {}
    if pl:
        placebo["model_swap_G3_mean"] = float(np.mean(pl))
        placebo["model_swap_G3_sd"] = float(np.std(pl))
        placebo["model_swap_pass"] = bool(abs(np.mean(pl)) < 0.25)
    # placebo (ii): SL <-> EN_BT swapped within item x step at random (50 draws) -> mean lag ~ 0 in both models
    if len(w):
        lags = {"gemma_it": [], "gams3_it": []}
        for _ in range(50):
            ww = w.copy()
            sw = rng.random(len(ww)) < 0.5
            ww.loc[sw, ["EN_BT", "SL_MT"]] = ww.loc[sw, ["SL_MT", "EN_BT"]].values
            for m in lags:
                agg = ww[ww.model == m].groupby("lambda").agg(ken=("EN_BT", "sum"), ksl=("SL_MT", "sum"),
                                                               n=("EN_BT", "size"))
                pe, ps = (agg.ken + 0.5) / (agg.n + 1), (agg.ksl + 0.5) / (agg.n + 1)
                lags[m].append(float(np.mean(np.log(ps / (1 - ps)) - np.log(pe / (1 - pe)))))
        placebo["lang_swap_mean_logodds_gap"] = {m: float(np.mean(v)) for m, v in lags.items()}
        placebo["lang_swap_sd"] = {m: float(np.std(v)) for m, v in lags.items()}
        placebo["lang_swap_pass"] = bool(all(abs(np.mean(v)) < 0.15 for v in lags.values()))
    # placebo (iii): judge labels shuffled within cell -> kappa ~ 0
    mfile = LABELS / "labels_mistral24b_final.jsonl"
    if mfile.exists():
        mm = pd.DataFrame(jl(mfile)).drop_duplicates("key", keep="last")[["key", "label"]].rename(columns={"label": "lm"})
        gm = g.merge(mm, on="key").dropna(subset=["lq"])
        if len(gm) > 50:
            x = (gm.lq == "REFUSE").astype(int).values
            y = (gm.lm == "REFUSE").astype(int).values

            def kap(a1, b1):
                po = np.mean(a1 == b1)
                pe = np.mean(a1) * np.mean(b1) + (1 - np.mean(a1)) * (1 - np.mean(b1))
                return (po - pe) / (1 - pe)
            placebo["kappa_real_all"] = float(kap(x, y))
            ys = y.copy()
            rng.shuffle(ys)
            placebo["kappa_shuffled"] = float(kap(x, ys))
            placebo["kappa_shuffle_pass"] = bool(abs(placebo["kappa_shuffled"]) < 0.05)
    # 3. HARD SDT at lambda=1: Delta-c per model (identical estimator)
    for m in ("gemma_it", "gams3_it"):
        ref = A["sdt_lambda1"]["q_R"]["edit"].get(m, {})
        if "delta_c_SL" not in ref:
            continue
        s = g[(g.model == m) & (g.set == "hard") & (g.condition == "edit") & (g["lambda"] == 1.0)]
        cs = {}
        for arm in ("EN_BT", "SL_MT"):
            u = s[(s.arm == arm) & (s.is_harmful == True)].R.dropna()  # noqa: E712
            f = s[(s.arm == arm) & (s.is_harmful == False)].R.dropna()  # noqa: E712
            zh = norm.ppf((u.sum() + 0.5) / (len(u) + 1))
            zf = norm.ppf((f.sum() + 0.5) / (len(f) + 1))
            cs[arm] = -(zh + zf) / 2
        chk(f"delta_c_lam1|{m}", float(cs["EN_BT"] - cs["SL_MT"]), float(ref["delta_c_SL"]))
    # 4. C-EXT SL - EN_BT pp on PUB items
    pub = set(man["CURVE_rank"][:proto["subsets"]["pub_n"]])
    for m, r in A["public"]["q_R"].items():
        if not isinstance(r, dict) or "SL_minus_EN_pp" not in r:
            continue
        cond = "orig" if m == "gemma_it" else "public"
        s = g[(g.model == m) & (g.condition == cond) & (g.set == "refuseu_x") & g.item_id.isin(pub)]
        ww = s.pivot_table(index="item_id", columns="arm", values="R")
        if not {"EN_BT", "SL_MT"} <= set(ww.columns):
            continue
        ww = ww[["EN_BT", "SL_MT"]].dropna()
        chk(f"pub_SL_minus_EN|{m}", float(100 * (ww.SL_MT - ww.EN_BT).mean()), float(r["SL_minus_EN_pp"]))
    # 5. two-point L3 G3
    tp = A["two_point"]["q_R"]["L3"]
    if "G3_2pt" in tp:
        s = g[g.model.isin(["gemma_it", "gams3_it"]) & g.arm.isin(["EN_BT", "L3_MT"]) & (g.is_harmful == True)  # noqa: E712
              & (((g.condition == "orig") & (g["lambda"] == 0)) | ((g.condition == "edit") & (g["lambda"] == 1.0)))]
        s = s[s.item_id.isin(set(s[s.arm == "L3_MT"].item_id))]
        ww = s.pivot_table(index="item_id", columns=["model", "condition", "arm"], values="R").dropna()
        n = len(ww)

        def L(k):
            p = (k + 0.5) / (n + 1)
            return math.log(p / (1 - p))
        ch = {}
        for m in ("gemma_it", "gams3_it"):
            ch[m] = ((L(ww[(m, "edit", "L3_MT")].sum()) - L(ww[(m, "edit", "EN_BT")].sum()))
                     - (L(ww[(m, "orig", "L3_MT")].sum()) - L(ww[(m, "orig", "EN_BT")].sum())))
        chk("G3_L3_2pt_q_R", ch["gams3_it"] - ch["gemma_it"], tp["G3_2pt"])
    out = {"checks": checks, "n_checks": len(checks), "n_pass": sum(c["pass"] for c in checks), "placebos": placebo,
           "all_pass": all(c["pass"] for c in checks) and all(v for k, v in placebo.items() if k.endswith("_pass"))}
    (RESULTS / "audit.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: out[k] for k in ("n_checks", "n_pass", "all_pass")}), json.dumps(placebo)[:600])


if __name__ == "__main__":
    main()
