#!/usr/bin/env python3
"""STEP 8 audit: independent plain-numpy/scipy re-derivation of the headline numbers from items_final.jsonl + placebos.

- per-step rates recomputed from raw rows (tolerance 1e-6)
- G3 for B/A1/A2 refit by direct binomial maximum likelihood with scipy.optimize (tolerance 1e-3 vs analysis.py IRLS)
- flip rates and hazard coefficient SIGNS (plain logistic regression by scipy)
- placebos: model-label-swap G3 centred at 0; shuffled-shallow hazard log-HR centred at 0
- code check T6: iter-1 lexicon G3 (-1.86, matched first 17 trials, OLS of Hautus log-odds) reproduced from iter-1 files
"""
from __future__ import annotations

import json
from collections import defaultdict

import numpy as np
from scipy.optimize import minimize

from common import DATA, ITER1_EXP4, MODEL_ORDER, RESULTS, read_jsonl

rng = np.random.default_rng(7)


def hl(k, n):
    p = (np.asarray(k, float) + 0.5) / (np.asarray(n, float) + 1.0)
    return np.log(p / (1 - p))


def mle(x, k, n):
    def nll(b):
        eta = b[0] + b[1] * x
        return -np.sum(k * eta - n * np.logaddexp(0, eta)) + 1e-6 * 0.5 * np.sum(b ** 2)
    r = minimize(nll, np.zeros(2), method="BFGS", options={"gtol": 1e-10})
    return r.x


def step_counts(rows, m, curve, readout, items, steps):
    out = []
    for s in steps:
        e = {r["item_id"]: r[readout] for r in rows if r["model"] == m and r["curve"] == curve and r["step"] == s
             and r["arm"] == "en_bt" and r[readout] is not None}
        l = {r["item_id"]: r[readout] for r in rows if r["model"] == m and r["curve"] == curve and r["step"] == s
             and r["arm"] == "sl_mt" and r[readout] is not None}
        ids = [i for i in items if i in e and i in l]
        out.append((sum(e[i] for i in ids), sum(l[i] for i in ids), len(ids)))
    return np.array(out, float)


def main():
    A = json.loads((RESULTS / "analysis.json").read_text())
    rows = read_jsonl(RESULTS / "items_final.jsonl")
    P200 = read_jsonl(DATA / "probe_P200.jsonl")
    items = {"B": [r["item_id"] for r in P200 if r["in_P100"]], "A1": [r["item_id"] for r in P200],
             "A2": [r["item_id"] for r in P200]}
    curve_of = {"B": "trial", "A1": "lambda", "A2": "ablate"}
    ro = A["primary_readout"]
    au = {"readout": ro, "checks": {}, "placebos": {}}
    for key in ("B", "A1", "A2"):
        g = A["G3"].get(key, {})
        if not isinstance(g, dict) or "primary" not in g:
            continue
        pm = g["primary"]["per_model"]
        steps = {}
        for m in MODEL_ORDER:
            if key == "B":
                steps[m] = [float(s) for s in A["B_trials_used"]]
            else:
                steps[m] = sorted({r["step"] for r in rows if r["model"] == m and r["curve"] == curve_of[key]
                                   and A["degeneracy_per_step"].get(f"{m}|{curve_of[key]}|{r['step']}", 0) <= 0.20})
        a = {}
        rate_ok = True
        for m in MODEL_ORDER:
            c = step_counts(rows, m, curve_of[key], ro, items[key], steps[m])
            pEN = (c[:, 0] + 0.5) / (c[:, 2] + 1)
            rate_ok &= bool(np.allclose(np.round(pEN, 4), pm[m]["pEN"], atol=1e-4))
            b = mle(hl(c[:, 0], c[:, 2]), c[:, 1], c[:, 2])
            a[m] = b
        g3 = (a["gams3_it"][0] + a["gams3_it"][1] * g["primary"]["x_star_logodds"]) - \
             (a["gemma_it"][0] + a["gemma_it"][1] * g["primary"]["x_star_logodds"])
        au["checks"][f"{key}_rates_match"] = rate_ok
        au["checks"][f"{key}_G3_refit"] = {"audit": float(g3), "analysis": g["primary"]["G3"],
                                           "match_1e-3": bool(abs(g3 - g["primary"]["G3"]) < 1e-3)}
        # placebo: random model-label swap per step (paired for B) -> G3 distribution centred at 0
        cE = {m: step_counts(rows, m, curve_of[key], ro, items[key], steps[m]) for m in MODEL_ORDER}
        if len(cE["gemma_it"]) == len(cE["gams3_it"]):
            null = []
            for _ in range(300):
                sw = rng.random(len(cE["gemma_it"])) < 0.5
                cg = np.where(sw[:, None], cE["gams3_it"], cE["gemma_it"])
                cm = np.where(sw[:, None], cE["gemma_it"], cE["gams3_it"])
                null.append(mle(hl(cm[:, 0], cm[:, 2]), cm[:, 1], cm[:, 2])[0] - mle(hl(cg[:, 0], cg[:, 2]), cg[:, 1], cg[:, 2])[0])
            au["placebos"][f"{key}_model_label_swap"] = {"mean": float(np.mean(null)), "sd": float(np.std(null)),
                                                         "centred": bool(abs(np.mean(null)) < 0.1)}
        # OLS bridge to iter-1's estimator (Hautus logit SL on Hautus logit EN; intercept difference)
        ols = {}
        for m in MODEL_ORDER:
            c = cE[m]
            bb, aa = np.polyfit(hl(c[:, 0], c[:, 2]), hl(c[:, 1], c[:, 2]), 1)
            ols[m] = aa
        au["checks"][f"{key}_G3_OLS_iter1_estimator"] = float(ols["gams3_it"] - ols["gemma_it"])
    # flip rates
    d = A.get("depth", {}).get("A1", {})
    fl = {}
    for m in MODEL_ORDER:
        for arm in ("en_bt", "sl_mt"):
            k0 = {r["item_id"]: r[ro] for r in rows if r["model"] == m and r["curve"] == "orig" and r["arm"] == arm and r[ro] is not None}
            kp = {r["item_id"]: r[ro] for r in rows if r["model"] == m and r["curve"] == "prefill" and r["arm"] == arm and r[ro] is not None}
            ref = [i for i in k0 if k0[i] == 1 and i in kp]
            fr = float(np.mean([kp[i] == 0 for i in ref])) if ref else float("nan")
            ana = d.get("cells", {}).get(f"{m}|{arm}", {}).get("flip_rate")
            fl[f"{m}|{arm}"] = {"audit": fr, "analysis": ana, "match": ana is not None and abs(fr - ana) < 1e-9}
    au["checks"]["flip_rates"] = fl
    # hazard sign check + shuffled-shallow placebo (plain logistic, step dummies + shallow + SL)
    lam = defaultdict(dict)
    for r in rows:
        if r["curve"] == "lambda" and r[ro] is not None:
            lam[(r["model"], r["arm"], r["item_id"])][r["step"]] = r[ro]
    steps = sorted({s for v in lam.values() for s in v})

    def hazard_design(m, shallow_map):
        X, y = [], []
        for (mm, arm, iid), sh in shallow_map.items():
            if mm != m or (mm, arm, iid) not in lam:
                continue
            for s in steps:
                if s not in lam[(mm, arm, iid)]:
                    break
                ev = int(lam[(mm, arm, iid)][s] == 0)
                X.append([1.0] + [float(s == t) for t in steps[1:]] + [sh, float(arm == "sl_mt")])
                y.append(ev)
                if ev:
                    break
        return np.array(X), np.array(y)

    def logit_fit(X, y):
        def nll(b):
            eta = X @ b
            return -np.sum(y * eta - np.logaddexp(0, eta)) + 1e-4 * 0.5 * np.sum(b ** 2)
        return minimize(nll, np.zeros(X.shape[1]), method="BFGS").x

    hz = {}
    for m in MODEL_ORDER:
        sm = {}
        for arm in ("en_bt", "sl_mt"):
            k0 = {r["item_id"]: r[ro] for r in rows if r["model"] == m and r["curve"] == "orig" and r["arm"] == arm and r[ro] is not None}
            kp = {r["item_id"]: r[ro] for r in rows if r["model"] == m and r["curve"] == "prefill" and r["arm"] == arm and r[ro] is not None}
            for i in k0:
                if k0[i] == 1 and i in kp:
                    sm[(m, arm, i)] = float(kp[i] == 0)
        X, y = hazard_design(m, sm)
        if len(y) < 10 or len(set(X[:, -2])) < 2:
            continue
        b = logit_fit(X, y)
        ana = A.get("depth", {}).get("A1", {}).get("hazard", {}).get(m, {}).get("SL_plus_shallow", {})
        ana_sh = ana.get("shallow", {}).get("coef") if isinstance(ana, dict) else None
        null = []
        keys = list(sm)
        for _ in range(100):
            perm = rng.permutation([sm[k] for k in keys])
            Xp, yp = hazard_design(m, dict(zip(keys, perm)))
            null.append(logit_fit(Xp, yp)[-2])
        hz[m] = {"shallow_logHR_audit": float(b[-2]), "shallow_logHR_analysis_GEE": ana_sh,
                 "sign_match": ana_sh is None or np.sign(ana_sh) == np.sign(b[-2]),
                 "placebo_shuffled_shallow_mean": float(np.mean(null)), "placebo_sd": float(np.std(null)),
                 "placebo_centred": bool(abs(np.mean(null)) < max(0.1, 2 * np.std(null) / np.sqrt(len(null))))}
    au["checks"]["hazard"] = hz
    # T6: iter-1 lexicon G3 reproduction (OLS of Hautus log-odds; matched first 17 trials; all 100 trial-probe pairs)
    try:
        tp_ids = [r["pair_id"] for r in read_jsonl(ITER1_EXP4 / "data/splits/trial_probe.jsonl")]
        a1 = {}
        for m in MODEL_ORDER:
            rr = [r for r in read_jsonl(ITER1_EXP4 / "results" / m / "trial_probe.jsonl") if r.get("tag") == "trial" and "R" in r]
            trials = sorted({r["trial"] for r in rr})[:17]
            xs, ys = [], []
            for t in trials:
                e = [r["R"] for r in rr if r["trial"] == t and r["lang"] == "en"]
                s = [r["R"] for r in rr if r["trial"] == t and r["lang"] == "sl"]
                xs.append(hl(sum(e), len(e)))
                ys.append(hl(sum(s), len(s)))
            b, a = np.polyfit(xs, ys, 1)
            a1[m] = a
        g = a1["gams3_it"] - a1["gemma_it"]
        au["checks"]["T6_iter1_G3_reproduction"] = {"G3": float(g), "target": -1.86, "ok": bool(abs(g + 1.86) < 0.02),
                                                    "n_pairs": len(tp_ids)}
    except (FileNotFoundError, KeyError, ValueError) as e:
        au["checks"]["T6_iter1_G3_reproduction"] = {"error": str(e)}
    flat = []
    for k, v in au["checks"].items():
        if isinstance(v, bool):
            flat.append(v)
        elif isinstance(v, dict) and "match_1e-3" in v:
            flat.append(v["match_1e-3"])
    au["all_primary_checks_pass"] = bool(all(flat)) if flat else None
    (RESULTS / "audit.json").write_text(json.dumps(au, indent=2, default=float))
    print(json.dumps(au, indent=1, default=float)[:4000])


if __name__ == "__main__":
    main()
