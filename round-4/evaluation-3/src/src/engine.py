"""Common curve engine. The GLM and Hautus smoothing are IMPORTED from the byte-identical vendored exp9 stats_core.py
(vendor/exp9/stats_core.py: glm_binom, hautus), i.e. the same estimator exp9 used; exp8/exp11/eval2 use the same model
(binomial logit GLM of SL counts on logit_H(EN) over steps) and each artifact's archived POINT headline is reproduced from
its archived label column by tests in eval.py (smoke tests). Bootstrap CIs use one generic item bootstrap ('engine substituted').
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import numpy as np
from scipy import stats as st
from scipy.special import expit, logit

_spec = importlib.util.spec_from_file_location("e9_stats_core", Path(__file__).resolve().parents[1] / "vendor/exp9/stats_core.py")
e9sc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(e9sc)
glm_binom = e9sc.glm_binom
hautus = e9sc.hautus


def _load_exp8_fit_glm():
    """exec ONLY the byte-identical fit_glm function of vendor/exp8/analysis.py (its module imports exp8 paths)."""
    import ast
    src = (Path(__file__).resolve().parents[1] / "vendor/exp8/analysis.py").read_text()
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "fit_glm")
    ns = {"np": np}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "vendor/exp8/analysis.py", "exec"), ns)
    return ns["fit_glm"]


FITTERS = {"exp9": glm_binom, "exp8": _load_exp8_fit_glm()}  # exp11/exp10/eval2: same model; exp11 glm_fit == exp9 IRLS to 1e-4

MODELS = ("gemma_it", "gams3_it")


def hlogit(k, n):
    return logit(hautus(k, n))


class Curve:
    """Y arrays per model x arm: yw [steps, items] = y*w (0 where missing), ww = w (0 where missing).
    Row weights w (e.g. inverse inclusion probability) default 1. Steps: sorted per model; items: union across models."""

    def __init__(self, df, ycol: str, wcol: str | None = None, steps: dict | None = None, items: list | None = None,
                 cells: dict | None = None):
        d = df[df.arm.isin(["en_bt", "sl_mt"])]
        d = d[d[ycol].notna()]
        self.items = sorted(d.item_id.unique()) if items is None else list(items)
        iidx = {it: j for j, it in enumerate(self.items)}
        self.steps = {m: sorted(d[d.model == m].step.unique()) for m in MODELS} if steps is None else steps
        self.yw, self.ww = {}, {}
        for m in MODELS:
            sidx = {s: i for i, s in enumerate(self.steps[m])}
            for arm in ("en_bt", "sl_mt"):
                A = np.zeros((len(self.steps[m]), len(self.items)))
                W = np.zeros_like(A)
                g = d[(d.model == m) & (d.arm == arm)]
                si = g.step.map(sidx)
                ii = g.item_id.map(iidx)
                ok = si.notna() & ii.notna()
                w = g[wcol].values[ok.values] if wcol else np.ones(int(ok.sum()))
                np.add.at(A, (si[ok].astype(int).values, ii[ok].astype(int).values), g[ycol].values[ok.values].astype(float) * w)
                np.add.at(W, (si[ok].astype(int).values, ii[ok].astype(int).values), w)
                self.yw[(m, arm)] = A
                self.ww[(m, arm)] = W

    def counts(self, m, bw=None):
        """bw: item multiplicities [n_items] or matrix [B, n_items] -> k, n arrays [(B,) steps]."""
        out = []
        for arm in ("en_bt", "sl_mt"):
            A, W = self.yw[(m, arm)], self.ww[(m, arm)]
            if bw is None:
                out += [A.sum(1), W.sum(1)]
            else:
                out += [bw @ A.T, bw @ W.T]
        return out  # kE, nE, kS, nS


def fit(kE, nE, kS, nS, fitter="exp9"):
    ok = (nE > 0) & (nS > 0)
    x = hlogit(kE[ok], nE[ok])
    a, b = FITTERS[fitter](x, kS[ok], nS[ok])
    return a, b, x, ok


def pct(a, q):
    a = np.asarray(a, float)
    a = a[np.isfinite(a)]
    return np.percentile(a, q).tolist() if len(a) > 10 else [float("nan")] * len(q)


def summarise(est, boots, m=0.675):
    b = np.asarray(boots, float)
    b = b[np.isfinite(b)]
    if len(b) < 20 or not np.isfinite(est):
        return {"est": float(est) if np.isfinite(est) else None, "n_boot_ok": int(len(b))}
    ci95 = np.percentile(b, [2.5, 97.5]).tolist()
    ci90 = np.percentile(b, [5, 95]).tolist()
    se = float((ci95[1] - ci95[0]) / (2 * 1.96))  # robust SE from the percentile interval (exp9 convention)
    mde = 2.8 * se
    if ci95[1] < -m:
        v = "CONFIRM-LAG"
    elif -m < ci90[0] and ci90[1] < m and mde <= 2 * m:
        v = "REFUTE-BOUND"
    else:
        v = "ESTIMATE"
    return {"est": float(est), "CI95": ci95, "CI90": ci90, "SE": se, "SE_sd": float(np.std(b, ddof=1)), "MDE": mde,
            "verdict": v, "excl0": bool(ci95[1] < 0 or ci95[0] > 0), "n_boot_ok": int(len(b))}


def curve_stats(cv: Curve, *, orig_step=0.0, B=2000, seed=20260926, corr=None, corr_draws=None, rule_min=2,
                fit_include_orig=True, m=0.675, fitter="exp9") -> dict:
    """G3, G3_orig, G3_edit (inside each draw), IG over the observed EN overlap, slopes, per-model rates.
    corr(model, arm, steps, kS_or_kE, n) -> corrected k (point); corr_draws(rng) -> list of B corr callables."""

    def one(bw, corr_f):
        res = {}
        ab, xr, g0 = {}, {}, {}
        for mm in MODELS:
            kE, nE, kS, nS = cv.counts(mm, bw)
            steps = np.array(cv.steps[mm])
            if corr_f is not None:
                kE = corr_f(mm, "en_bt", steps, kE, nE)
                kS = corr_f(mm, "sl_mt", steps, kS, nS)
            sel = np.ones(len(steps), bool) if fit_include_orig else steps != orig_step
            a, b, x, ok = fit(kE[sel], nE[sel], kS[sel], nS[sel], fitter)
            ab[mm] = (a, b)
            xr[mm] = x
            o = np.where(steps == orig_step)[0]
            g0[mm] = (hlogit(kS[o[0]], nS[o[0]]) - hlogit(kE[o[0]], nE[o[0]])) if len(o) and nS[o[0]] > 0 and nE[o[0]] > 0 else np.nan
            res[f"b_{mm}"] = b
            res[f"a_{mm}"] = a
        if any(len(xr[mm]) < 2 for mm in MODELS):
            raise ValueError("fewer than 2 usable steps")
        if any(abs(ab[mm][0]) > 30 or abs(ab[mm][1]) > 30 for mm in MODELS):
            raise ValueError("quasi-separation (|a| or |b| > 30)")
        res["G3"] = ab["gams3_it"][0] - ab["gemma_it"][0]
        res["G3_orig"] = g0["gams3_it"] - g0["gemma_it"]
        res["G3_edit"] = res["G3"] - res["G3_orig"]
        lo = max(xr[mm].min() for mm in MODELS)
        hi = min(xr[mm].max() for mm in MODELS)
        if hi > lo:
            grid = np.linspace(lo, hi, 21)
            res["IG"] = float(np.mean((ab["gams3_it"][0] + ab["gams3_it"][1] * grid) - (ab["gemma_it"][0] + ab["gemma_it"][1] * grid)))
        else:
            res["IG"] = np.nan
        res["_x"] = xr
        return res

    try:
        pt = one(None, corr)
    except ValueError as e:
        return {"status": f"point estimate unusable: {e}", "SEPARATED": True,
                "steps": {mm: [float(x) for x in cv.steps[mm]] for mm in MODELS}}
    rng = np.random.default_rng(seed)
    nI = len(cv.items)
    BW = np.stack([np.bincount(rng.integers(0, nI, nI), minlength=nI) for _ in range(B)]).astype(float)
    cds = corr_draws(rng, B) if corr_draws is not None else None
    keys = ["G3", "G3_orig", "G3_edit", "IG", "b_gemma_it", "b_gams3_it", "a_gemma_it", "a_gams3_it"]
    boots = {k: np.full(B, np.nan) for k in keys}
    for i in range(B):
        try:
            r = one(BW[i], cds[i] if cds is not None else corr)
        except (np.linalg.LinAlgError, ValueError, FloatingPointError):
            continue  # failed draw (separation / empty step); counted in n_boot_ok
        for k in keys:
            boots[k][i] = r[k]
    out = {"n_items": nI, "B": B, "steps": {mm: [float(s) for s in cv.steps[mm]] for mm in MODELS}}
    for k in keys:
        out[k] = summarise(pt[k], boots[k], m=m)
    out["_boot"] = {k: boots[k] for k in ("G3", "G3_edit", "G3_orig", "IG")}
    # support + per-model rates at the point
    for mm in MODELS:
        x = pt["_x"][mm]
        pE = expit(x)
        kE, nE, kS, nS = cv.counts(mm)
        steps = np.array(cv.steps[mm])
        if corr is not None:
            kE = corr(mm, "en_bt", steps, kE, nE)
            kS = corr(mm, "sl_mt", steps, kS, nS)
        out[f"per_model_{mm}"] = {"steps": steps.tolist(), "pEN": (kE / np.maximum(nE, 1e-9)).round(4).tolist(),
                                  "pSL": (kS / np.maximum(nS, 1e-9)).round(4).tolist(), "n": nE.round(1).tolist(),
                                  "n_lo": int(np.sum((pE >= 0.2) & (pE < 0.5))), "n_hi": int(np.sum((pE >= 0.5) & (pE <= 0.8))),
                                  "EN_range_p": [float(pE.min()), float(pE.max())]}
    lo = max(pt["_x"][mm].min() for mm in MODELS)
    hi = min(pt["_x"][mm].max() for mm in MODELS)
    out["IG_overlap_logit"] = [float(lo), float(hi)] if hi > lo else None
    out["IG_overlap_p"] = [float(expit(lo)), float(expit(hi))] if hi > lo else None
    out["on_support"] = bool(all(out[f"per_model_{mm}"]["n_lo"] >= rule_min and out[f"per_model_{mm}"]["n_hi"] >= rule_min
                                 for mm in MODELS))
    out["support_rule_min_per_side"] = rule_min
    return out


def point_g3(cv: Curve, fit_include_orig=True, orig_step=0.0, fitter="exp9") -> float:
    ab = {}
    for mm in MODELS:
        kE, nE, kS, nS = cv.counts(mm)
        steps = np.array(cv.steps[mm])
        sel = np.ones(len(steps), bool) if fit_include_orig else steps != orig_step
        ab[mm] = fit(kE[sel], nE[sel], kS[sel], nS[sel], fitter)[0]
    return float(ab["gams3_it"] - ab["gemma_it"])


# ---------------------------------------------------------------- operating point (exp10)
def op_point(df, ycol, B=2000, seed=20260926, corr=None, corr_draws=None, m=0.675):
    """G3_op = Lag_GaMS(E0) - Lag_Gemma(E0), Lag = logit_H(SL) - logit_H(EN_BT); also at O and the edit contrast."""
    items = sorted(df.item_id.unique())
    iidx = {it: j for j, it in enumerate(items)}
    Y = {}
    for (mm, cond, arm), g in df.groupby(["model", "condition", "arm"]):
        A = np.full(len(items), np.nan)
        A[g.item_id.map(iidx).values] = g[ycol].values.astype(float)
        Y[(mm, cond, arm)] = A

    def lag(bw, mm, cond, cf):
        r = {}
        for arm in ("en_bt", "sl_mt"):
            A = Y[(mm, cond, arm)]
            v = ~np.isnan(A)
            k = (bw * np.nan_to_num(A)).sum() if bw is not None else np.nansum(A)
            n = (bw * v).sum() if bw is not None else v.sum()
            if cf is not None:
                k = cf(mm, arm, np.array([0.0 if cond == "orig" else 1.0]), np.array([k]), np.array([n]))[0]
            r[arm] = (k, n)
        return hlogit(r["sl_mt"][0], r["sl_mt"][1]) - hlogit(r["en_bt"][0], r["en_bt"][1])

    def one(bw, cf):
        o = {}
        for cond, nm in (("edited", "G3_op"), ("orig", "G3_op_orig")):
            o[nm] = lag(bw, "gams3_it", cond, cf) - lag(bw, "gemma_it", cond, cf)
            o[f"Lag_{cond}_gemma_it"] = lag(bw, "gemma_it", cond, cf)
            o[f"Lag_{cond}_gams3_it"] = lag(bw, "gams3_it", cond, cf)
        o["G3_op_edit"] = o["G3_op"] - o["G3_op_orig"]
        return o

    pt = one(None, corr)
    rng = np.random.default_rng(seed)
    cds = corr_draws(rng, B) if corr_draws is not None else None
    bs = {k: [] for k in pt}
    for i in range(B):
        bw = np.bincount(rng.integers(0, len(items), len(items)), minlength=len(items)).astype(float)
        r = one(bw, cds[i] if cds is not None else corr)
        for k in pt:
            bs[k].append(r[k])
    out = {k: summarise(pt[k], bs[k], m=m) for k in pt}
    out["_boot"] = {k: np.array(bs[k]) for k in ("G3_op", "G3_op_edit")}
    out["n_items"] = len(items)
    return out


# ---------------------------------------------------------------- tipping (eval2 step5 logic)
def tipping(cv: Curve, stat="G3", m=0.675, fit_include_orig=True, orig_step=0.0, fitter="exp9"):
    base = {}
    for mm in MODELS:
        c = cv.counts(mm)
        sel = np.ones(len(cv.steps[mm]), bool) if fit_include_orig else np.array(cv.steps[mm]) != orig_step
        base[mm] = tuple(v[sel] for v in c)
    grid = None
    if stat == "IG":
        xs = {}
        for mm in MODELS:
            kE, nE, kS, nS = base[mm]
            xs[mm] = hlogit(kE[nE > 0], nE[nE > 0])
        lo, hi = max(xs[mm].min() for mm in MODELS), min(xs[mm].max() for mm in MODELS)
        grid = np.linspace(lo, hi, 21) if hi > lo else None

    def g3(delta=0.0, eps=0.0):
        ab = {}
        for mm in MODELS:
            kE, nE, kS, nS = base[mm]
            ok = (nE > 0) & (nS > 0)
            pS = kS[ok] / nS[ok]
            if mm == "gemma_it" and delta:
                pS = np.clip((pS - delta) / (1 - delta), 0, 1)
            if mm == "gams3_it" and eps:
                pS = np.clip(pS / (1 - eps), 0, 1)
            ab[mm] = FITTERS[fitter](hlogit(kE[ok], nE[ok]), pS * nS[ok], nS[ok])
        (aG, bG), (aM, bM) = ab["gemma_it"], ab["gams3_it"]
        if grid is not None:
            return float(np.mean((aM + bM * grid) - (aG + bG * grid)))
        return aM - aG

    rec = {"statistic": stat, "obs": g3()}
    gv = np.linspace(0.0, 0.95, 191)
    for tn, tv in (("minus_m", -m), ("zero", 0.0)):
        for nm, fn in (("delta_star_GemmaSL_false_REFUSE", lambda v: g3(delta=v)), ("eps_star_GaMSSL_false_COMPLY", lambda v: g3(eps=v))):
            vals = np.array([fn(v) for v in gv])
            if (vals[0] - tv) > 0:  # already above the target
                rec[f"{nm}|to_{tn}"] = 0.0
                continue
            cross = [gv[i] for i in range(len(gv) - 1) if (vals[i] - tv) * (vals[i + 1] - tv) <= 0]
            rec[f"{nm}|to_{tn}"] = float(cross[0]) if cross else None
    return rec


# ---------------------------------------------------------------- meta-analysis
def meta(y, se):
    y, se = np.asarray(y, float), np.asarray(se, float)
    k = len(y)
    v = se ** 2
    w = 1 / v
    mu_fe = float(np.sum(w * y) / np.sum(w))
    se_fe = float(math.sqrt(1 / np.sum(w)))
    Q = float(np.sum(w * (y - mu_fe) ** 2))
    I2 = max(0.0, (Q - (k - 1)) / Q) if Q > 0 else 0.0

    def reml_tau2():
        t = max(0.0, (Q - (k - 1)) / (np.sum(w) - np.sum(w ** 2) / np.sum(w)))
        for _ in range(200):
            wi = 1 / (v + t)
            mu = np.sum(wi * y) / np.sum(wi)
            t_new = max(0.0, np.sum(wi ** 2 * ((y - mu) ** 2 - v)) / np.sum(wi ** 2) + 1 / np.sum(wi))
            if abs(t_new - t) < 1e-10:
                return t_new
            t = t_new
        return t

    def pm_tau2():
        lo, hi = 0.0, max(10.0, 10 * np.var(y))
        f = lambda t: np.sum((y - np.sum(y / (v + t)) / np.sum(1 / (v + t))) ** 2 / (v + t)) - (k - 1)
        if f(0) <= 0:
            return 0.0
        for _ in range(200):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if f(mid) > 0 else (lo, mid)
        return (lo + hi) / 2

    out = {"k": k, "y": y.tolist(), "se": se.tolist(), "FE": {"est": mu_fe, "CI95": [mu_fe - 1.96 * se_fe, mu_fe + 1.96 * se_fe]},
           "Q": Q, "I2": I2}
    for nm, t2 in (("REML_HKSJ", reml_tau2()), ("PM_HKSJ", pm_tau2())):
        wi = 1 / (v + t2)
        mu = float(np.sum(wi * y) / np.sum(wi))
        q = float(np.sum(wi * (y - mu) ** 2) / (k - 1)) if k > 1 else 1.0
        se_hk = math.sqrt(q / np.sum(wi))
        tq = st.t.ppf(0.975, k - 1) if k > 1 else float("nan")
        se_re = math.sqrt(1 / np.sum(wi))
        tpi = st.t.ppf(0.975, k - 2) if k > 2 else float("nan")
        out[nm] = {"tau2": float(t2), "est": mu, "SE_HKSJ": se_hk, "CI95": [mu - tq * se_hk, mu + tq * se_hk],
                   "CI90": [mu - st.t.ppf(0.95, k - 1) * se_hk, mu + st.t.ppf(0.95, k - 1) * se_hk] if k > 1 else None,
                   "PI95": [mu - tpi * math.sqrt(t2 + se_re ** 2), mu + tpi * math.sqrt(t2 + se_re ** 2)] if k > 2 else None,
                   "PI_note": "t with k-2=1 df at k=3: nearly uninformative"}
    return out


# ---------------------------------------------------------------- agreement / error rates
def wilson(k, n, z=1.96):
    if n <= 0:
        return [float("nan"), float("nan")]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(max(p * (1 - p) / n + z * z / (4 * n * n), 0)) / d
    return [max(0.0, c - h), min(1.0, c + h)]


def kappa(a, b):
    a, b = np.asarray(a), np.asarray(b)
    if len(a) == 0:
        return float("nan")
    po = float(np.mean(a == b))
    cats = np.union1d(a, b)
    pe = sum(float(np.mean(a == c)) * float(np.mean(b == c)) for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def se_sp_w(judge, ref, w):
    """HT-weighted Se/Sp with Wilson CIs on Kish effective n."""
    judge, ref, w = np.asarray(judge, float), np.asarray(ref, float), np.asarray(w, float)
    out = {}
    for nm, mask, tgt in (("Se", ref == 1, 1), ("Sp", ref == 0, 0)):
        ww = w[mask]
        if len(ww) == 0:
            out[nm], out[f"{nm}_CI"], out[f"n_{nm}"], out[f"neff_{nm}"] = None, None, 0, 0
            continue
        p = float(np.sum(ww * (judge[mask] == tgt)) / np.sum(ww))
        neff = float(np.sum(ww) ** 2 / np.sum(ww ** 2))
        out[nm], out[f"{nm}_CI"], out[f"n_{nm}"], out[f"neff_{nm}"] = p, wilson(p * neff, neff), int(mask.sum()), neff
    return out


def ppi_shift(f_all, f_gold, y_gold, w_gold=None):
    """PPI++ mean rectifier: returns (p_ppi, lambda_hat, shift) with power-tuned lambda clipped to [0,1]."""
    f_all, f_gold, y_gold = (np.asarray(v, float) for v in (f_all, f_gold, y_gold))
    w = np.ones(len(f_gold)) if w_gold is None else np.asarray(w_gold, float)
    w = w / w.sum()
    n, N = len(f_gold), len(f_all)
    if n < 3:
        return float(np.mean(f_all)), 0.0, 0.0
    mf, my = np.sum(w * f_gold), np.sum(w * y_gold)
    cov = np.sum(w * (f_gold - mf) * (y_gold - my))
    var = np.sum(w * (f_gold - mf) ** 2)
    lam = float(np.clip(cov / ((1 + n / N) * var), 0, 1)) if var > 1e-12 else 0.0
    # PPI++ mean: lam*mean_f(all) + (mean_gold(Y) - lam*mean_gold(f)) = mean_f(all) + (my - lam*mf) - (1-lam)*mean_f(all)
    p = lam * np.mean(f_all) + my - lam * mf
    return float(p), lam, float(p - np.mean(f_all))
