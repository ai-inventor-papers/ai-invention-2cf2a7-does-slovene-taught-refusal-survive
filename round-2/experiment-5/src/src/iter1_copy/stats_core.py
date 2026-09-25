#!/usr/bin/env python3
"""Core statistics shared by analysis.py, test_synthetic.py and audit.py.

Cell order everywhere: 0 = (gemma, en), 1 = (gemma, sl), 2 = (gams, en), 3 = (gams, sl).
Y is an (n_pairs, 4) array of 0/1 (or NaN-free continuous for s-type outcomes).
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy import stats

CELLS = [("gemma_it", "en"), ("gemma_it", "sl"), ("gams3_it", "en"), ("gams3_it", "sl")]
B_BOOT = 2000


def logit_h(k: np.ndarray, n: np.ndarray) -> np.ndarray:
    p = (k + 0.5) / (n + 1.0)
    return np.log(p / (1 - p))


def did_from_counts(k: np.ndarray, n: np.ndarray) -> np.ndarray:
    """k: (..., 4) counts; n: (...,) or (..., 4). Returns DiD in Hautus log-odds."""
    if np.ndim(n) == np.ndim(k) - 1:
        n = np.repeat(np.asarray(n)[..., None], 4, axis=-1)
    L = logit_h(k, n)
    return (L[..., 3] - L[..., 2]) - (L[..., 1] - L[..., 0])


def m_from_p0(p0: float, step: float = 0.05) -> float:
    p1 = p0 - step * np.sign(p0 - 0.5) if p0 != 0.5 else p0 - step
    lg = lambda p: math.log(p / (1 - p))  # noqa: E731
    p0c, p1c = min(max(p0, 1e-6), 1 - 1e-6), min(max(p1, 1e-6), 1 - 1e-6)
    return abs(lg(p0c) - lg(p1c))


class Bootstrap:
    """Category-stratified pair bootstrap with FIXED draws reused for every outcome."""

    def __init__(self, cats: np.ndarray, seed: int = 20260923, B: int = B_BOOT):
        self.cats = np.asarray(cats)
        self.B = B
        rng = np.random.default_rng(seed)
        self.levels = sorted(set(self.cats.tolist()), key=lambda c: int(str(c)[1:]) if str(c)[1:].isdigit() else 0)
        self.idx = {}
        for c in self.levels:
            pos = np.where(self.cats == c)[0]
            self.idx[c] = pos[rng.integers(0, len(pos), size=(B, len(pos)))]

    def cat_counts(self, Y: np.ndarray) -> dict[str, np.ndarray]:
        """Per-category bootstrap sums: {cat: (B,4)}; also the observed sums under key ('obs', cat)."""
        return {c: Y[self.idx[c]].sum(axis=1) for c in self.levels}

    def cat_n(self) -> dict[str, int]:
        return {c: self.idx[c].shape[1] for c in self.levels}


def ci(arr: np.ndarray, level: float = 0.95) -> list[float]:
    a = (1 - level) / 2
    return [float(np.nanpercentile(arr, 100 * a)), float(np.nanpercentile(arr, 100 * (1 - a)))]


def bca_ci(theta_hat: float, boot: np.ndarray, jack: np.ndarray, level: float = 0.95) -> list[float]:
    boot = boot[np.isfinite(boot)]
    z0 = stats.norm.ppf(np.clip((boot < theta_hat).mean(), 1e-6, 1 - 1e-6))
    jm = jack.mean()
    num = ((jm - jack) ** 3).sum()
    den = 6 * (((jm - jack) ** 2).sum() ** 1.5)
    a = num / den if den > 0 else 0.0
    out = []
    for q in ((1 - level) / 2, 1 - (1 - level) / 2):
        zq = stats.norm.ppf(q)
        adj = stats.norm.cdf(z0 + (z0 + zq) / (1 - a * (z0 + zq)))
        out.append(float(np.percentile(boot, 100 * adj)))
    return out


def set_did(Y: np.ndarray, cats: np.ndarray, members: list[str], bs: Bootstrap) -> tuple[float, np.ndarray]:
    mask = np.isin(cats, members)
    k = Y[mask].sum(0)
    n = mask.sum()
    obs = float(did_from_counts(k, n))
    kb = sum(bs.cat_counts_cache[c] for c in members if c in bs.cat_counts_cache)
    nb = sum(bs.cat_n()[c] for c in members if c in bs.cat_counts_cache)
    return obs, did_from_counts(kb, nb)


def did_suite(Y: np.ndarray, cats: np.ndarray, bs: Bootstrap, low: list[str], high: list[str]) -> dict[str, Any]:
    """Binary outcome: overall DiD, per-category DiD, DiD_low/high, D, D_catmean, with bootstrap."""
    cc = bs.cat_counts(Y)
    bs.cat_counts_cache = cc
    ncat = bs.cat_n()
    present = [c for c in bs.levels]
    low_p = [c for c in low if c in present]
    high_p = [c for c in high if c in present]
    res: dict[str, Any] = {}
    # overall
    obs = float(did_from_counts(Y.sum(0), len(Y)))
    kb = sum(cc[c] for c in present)
    boot = did_from_counts(kb, len(Y))
    res["overall"] = {"est": obs, "se": float(np.std(boot, ddof=1)), "ci95": ci(boot), "ci90": ci(boot, 0.90)}
    # per category
    per = {}
    for c in present:
        m = cats == c
        o = float(did_from_counts(Y[m].sum(0), m.sum()))
        b = did_from_counts(cc[c], ncat[c])
        rates = ((Y[m].sum(0) + 0.5) / (m.sum() + 1)).tolist()
        per[c] = {"est": o, "se": float(np.std(b, ddof=1)), "var": float(np.var(b, ddof=1)), "ci95": ci(b),
                  "n": int(m.sum()), "raw_rates": (Y[m].mean(0)).tolist(), "hautus_rates": rates}
    res["per_category"] = per
    # sets
    out_sets = {}
    boots = {}
    for name, mem in (("low", low_p), ("high", high_p)):
        m = np.isin(cats, mem)
        o = float(did_from_counts(Y[m].sum(0), m.sum()))
        b = did_from_counts(sum(cc[c] for c in mem), sum(ncat[c] for c in mem))
        out_sets[name] = {"est": o, "se": float(np.std(b, ddof=1)), "ci95": ci(b), "n": int(m.sum()), "members": mem}
        boots[name] = b
    res["DiD_low"], res["DiD_high"] = out_sets["low"], out_sets["high"]
    Dobs = out_sets["low"]["est"] - out_sets["high"]["est"]
    Db = boots["low"] - boots["high"]
    # jackknife over pairs in low/high sets (for BCa) -- delete-one-category-block jackknife is too coarse; use
    # grouped jackknife with 20 random groups
    rng = np.random.default_rng(20260923)
    grp = rng.integers(0, 20, size=len(Y))
    jack = []
    for g in range(20):
        keep = grp != g
        ml, mh = np.isin(cats, low_p) & keep, np.isin(cats, high_p) & keep
        jack.append(float(did_from_counts(Y[ml].sum(0), ml.sum()) - did_from_counts(Y[mh].sum(0), mh.sum())))
    se_D = float(np.std(Db, ddof=1))
    res["D"] = {"est": Dobs, "se": se_D, "ci95": ci(Db), "ci90": ci(Db, 0.90),
                "ci95_bca": bca_ci(Dobs, Db, np.array(jack)), "MDE": 2.80 * se_D}
    # catmean
    cm_obs = np.mean([per[c]["est"] for c in low_p]) - np.mean([per[c]["est"] for c in high_p])
    cm_b = np.mean([did_from_counts(cc[c], ncat[c]) for c in low_p], axis=0) - \
        np.mean([did_from_counts(cc[c], ncat[c]) for c in high_p], axis=0)
    res["D_catmean"] = {"est": float(cm_obs), "se": float(np.std(cm_b, ddof=1)), "ci95": ci(cm_b)}
    res["_boot"] = {"overall": boot, "D": Db}
    return res


def cont_suite(d: np.ndarray, cats: np.ndarray, bs: Bootstrap, low: list[str], high: list[str]) -> dict[str, Any]:
    """Continuous per-pair DiD d_i (e.g. on s): means with the same bootstrap draws."""
    present = bs.levels
    low_p = [c for c in low if c in present]
    high_p = [c for c in high if c in present]
    bsum = {c: d[bs.idx[c]].sum(1) for c in present}
    ncat = bs.cat_n()
    res: dict[str, Any] = {}
    tot_b = sum(bsum[c] for c in present) / len(d)
    res["overall"] = {"est": float(d.mean()), "se": float(np.std(tot_b, ddof=1)), "ci95": ci(tot_b), "ci90": ci(tot_b, .9)}
    per = {}
    for c in present:
        m = cats == c
        b = bsum[c] / ncat[c]
        per[c] = {"est": float(d[m].mean()), "se": float(np.std(b, ddof=1)), "var": float(np.var(b, ddof=1)),
                  "ci95": ci(b), "n": int(m.sum())}
    res["per_category"] = per
    lb = sum(bsum[c] for c in low_p) / sum(ncat[c] for c in low_p)
    hb = sum(bsum[c] for c in high_p) / sum(ncat[c] for c in high_p)
    lo = float(d[np.isin(cats, low_p)].mean())
    hi = float(d[np.isin(cats, high_p)].mean())
    Db = lb - hb
    res["low"] = {"est": lo, "ci95": ci(lb)}
    res["high"] = {"est": hi, "ci95": ci(hb)}
    res["D"] = {"est": lo - hi, "se": float(np.std(Db, ddof=1)), "ci95": ci(Db), "ci90": ci(Db, .9),
                "MDE": 2.80 * float(np.std(Db, ddof=1))}
    return res


def equivalence_power(se: float, m: float, n_sim: int = 20000, seed: int = 20260923) -> float:
    rng = np.random.default_rng(seed)
    est = rng.normal(0, se, n_sim)
    z = stats.norm.ppf(0.95)
    return float(np.mean((est - z * se > -m) & (est + z * se < m)))


# ---------------------------------------------------------------- meta-regression (DerSimonian-Laird, Knapp-Hartung)
def meta_regression(y: np.ndarray, v: np.ndarray, X: np.ndarray, names: list[str]) -> dict[str, Any]:
    """Random-effects meta-regression, method-of-moments (DL) tau^2, Knapp-Hartung CIs."""
    k, p = X.shape
    W = np.diag(1 / v)
    XtWX = X.T @ W @ X
    beta_fe = np.linalg.solve(XtWX, X.T @ W @ y)
    resid = y - X @ beta_fe
    Q = float(resid @ W @ resid)
    P = W - W @ X @ np.linalg.solve(XtWX, X.T @ W)
    tr = float(np.trace(P))
    tau2 = max(0.0, (Q - (k - p)) / tr) if tr > 0 else 0.0
    Ws = np.diag(1 / (v + tau2))
    A = X.T @ Ws @ X
    beta = np.linalg.solve(A, X.T @ Ws @ y)
    r = y - X @ beta
    qkh = float(r @ Ws @ r) / (k - p)
    cov_kh = np.linalg.inv(A) * max(qkh, 1.0) if False else np.linalg.inv(A) * qkh  # plain KH (no truncation)
    se = np.sqrt(np.diag(cov_kh))
    tcrit = stats.t.ppf(0.975, k - p)
    out = {"tau2": tau2, "Q": Q, "df_resid": k - p, "coef": {}}
    for i, nm in enumerate(names):
        out["coef"][nm] = {"est": float(beta[i]), "se_kh": float(se[i]),
                           "ci95_kh": [float(beta[i] - tcrit * se[i]), float(beta[i] + tcrit * se[i])],
                           "p_kh": float(2 * stats.t.sf(abs(beta[i] / se[i]), k - p)) if se[i] > 0 else None}
    return out


def meta_reg_cat_bootstrap(y: np.ndarray, v: np.ndarray, X: np.ndarray, B: int = 2000,
                           seed: int = 20260923) -> np.ndarray:
    rng = np.random.default_rng(seed)
    k = len(y)
    out = []
    for _ in range(B):
        idx = rng.integers(0, k, k)
        Xb = X[idx]
        if np.linalg.matrix_rank(Xb) < X.shape[1]:
            continue
        try:
            r = meta_regression(y[idx], v[idx], Xb, [str(i) for i in range(X.shape[1])])
            out.append([r["coef"][str(i)]["est"] for i in range(X.shape[1])])
        except (np.linalg.LinAlgError, ZeroDivisionError, FloatingPointError):
            continue
    return np.array(out)


def cohen_kappa(a: np.ndarray, b: np.ndarray) -> float | None:
    a, b = np.asarray(a), np.asarray(b)
    if len(a) == 0:
        return None
    labs = sorted(set(a.tolist()) | set(b.tolist()))
    po = float(np.mean(a == b))
    pe = sum(float(np.mean(a == l)) * float(np.mean(b == l)) for l in labs)
    return None if pe >= 1 else (po - pe) / (1 - pe)


def wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    if n == 0:
        return [float("nan"), float("nan")]
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [c - h, c + h]


def rd_suite(Y: np.ndarray, cats: np.ndarray, bs: "Bootstrap", low: list[str], high: list[str]) -> dict:
    """Risk-difference DiD (probability scale, not ceiling-sensitive): (p_GaMS,SL - p_GaMS,EN) - (p_Gemma,SL - p_Gemma,EN),
    overall and D_rd = DiD_rd(low) - DiD_rd(high), with the same stratified pair bootstrap draws."""
    def rd(k, n):
        p = k / n
        return (p[..., 3] - p[..., 2]) - (p[..., 1] - p[..., 0])
    cc = {c: Y[bs.idx[c]].sum(axis=1) for c in bs.levels}
    ncat = bs.cat_n()
    lo = [c for c in low if c in bs.levels]
    hi = [c for c in high if c in bs.levels]
    ob = float(rd(Y.sum(0), len(Y)))
    b = rd(sum(cc[c] for c in bs.levels), len(Y))
    ml, mh = np.isin(cats, lo), np.isin(cats, hi)
    Dob = float(rd(Y[ml].sum(0), ml.sum()) - rd(Y[mh].sum(0), mh.sum()))
    Db = rd(sum(cc[c] for c in lo), sum(ncat[c] for c in lo)) - rd(sum(cc[c] for c in hi), sum(ncat[c] for c in hi))
    return {"overall_pp": {"est": 100 * ob, "ci95": [100 * x for x in ci(b)]},
            "D_pp": {"est": 100 * Dob, "ci95": [100 * x for x in ci(Db)], "se": 100 * float(np.std(Db, ddof=1)),
                     "MDE": 280 * float(np.std(Db, ddof=1))}}
