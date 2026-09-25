#!/usr/bin/env python3
"""Statistics primitives (unit-tested in tests/test_stats.py): Hautus rates, Wilson CI, SDT, exact McNemar, the G3
binomial-GLM fit, isotonic value at EN = 50%, Rogan-Gladen correction, bootstrap helpers."""
from __future__ import annotations

import math

import numpy as np
from scipy import optimize, stats


def hautus(k, n):
    return (np.asarray(k, float) + 0.5) / (np.asarray(n, float) + 1.0)


def logit(p):
    p = np.clip(np.asarray(p, float), 1e-9, 1 - 1e-9)
    return np.log(p / (1 - p))


def expit(x):
    return 1.0 / (1.0 + np.exp(-np.asarray(x, float)))


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def sdt(kh: int, nh: int, kf: int, nf: int) -> tuple[float, float]:
    """d' and c with Hautus-corrected rates. H = hit rate (refuse harmful), F = false alarm (refuse benign)."""
    zh = stats.norm.ppf(hautus(kh, nh))
    zf = stats.norm.ppf(hautus(kf, nf))
    return float(zh - zf), float(-(zh + zf) / 2)


def mcnemar_exact(b: int, c: int) -> float:
    """two-sided exact McNemar p on discordant counts b (0->1) and c (1->0)."""
    n = b + c
    if n == 0:
        return 1.0
    return float(min(1.0, stats.binomtest(min(b, c), n, 0.5).pvalue))


def glm_fit(k_sl, n_sl, p_en) -> tuple[float, float]:
    """binomial GLM k_SL ~ Bin(n, expit(a + b * logit(p_EN))); returns (a, b) by Newton/IRLS via scipy."""
    k_sl, n_sl = np.asarray(k_sl, float), np.asarray(n_sl, float)
    x = logit(np.asarray(p_en, float))

    def nll(th):
        eta = th[0] + th[1] * x
        return -np.sum(k_sl * eta - n_sl * np.logaddexp(0, eta))

    def grad(th):
        mu = expit(th[0] + th[1] * x)
        r = k_sl - n_sl * mu
        return -np.array([r.sum(), (r * x).sum()])

    r = optimize.minimize(nll, np.array([0.0, 1.0]), jac=grad, method="BFGS")
    return float(r.x[0]), float(r.x[1])


def isotonic_at_half(p_en, p_sl) -> float:
    """isotonic (increasing) fit of SL on EN rate, linear interpolation at EN = 0.5, returned as log-odds."""
    from sklearn.isotonic import IsotonicRegression
    p_en, p_sl = np.asarray(p_en, float), np.asarray(p_sl, float)
    iso = IsotonicRegression(increasing=True, out_of_bounds="clip").fit(p_en, p_sl)
    return float(logit(iso.predict([0.5])[0]))


def rogan_gladen(p_obs: float, se: float, sp: float) -> float:
    j = se + sp - 1
    if j <= 0.5:
        return float("nan")
    return float(np.clip((p_obs + sp - 1) / j, 0, 1))


def cohen_kappa(a, b) -> float:
    a, b = np.asarray(a), np.asarray(b)
    if len(a) == 0:
        return float("nan")
    cats = np.union1d(a, b)
    po = float(np.mean(a == b))
    pe = float(sum(np.mean(a == c) * np.mean(b == c) for c in cats))
    return float("nan") if pe >= 1 else (po - pe) / (1 - pe)


def ci(v, lo=2.5, hi=97.5):
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return [float("nan"), float("nan")]
    return [float(np.percentile(v, lo)), float(np.percentile(v, hi))]


def bca_ci(theta_hat: float, boots, jack, alpha: float = 0.05):
    boots = np.asarray(boots, float)
    boots = boots[np.isfinite(boots)]
    jack = np.asarray(jack, float)
    jack = jack[np.isfinite(jack)]
    if len(boots) < 50 or len(jack) < 5:
        return [float("nan"), float("nan")]
    z0 = stats.norm.ppf(np.clip(np.mean(boots < theta_hat), 1e-6, 1 - 1e-6))
    jm = jack.mean()
    num = np.sum((jm - jack) ** 3)
    den = 6 * (np.sum((jm - jack) ** 2) ** 1.5)
    acc = num / den if den > 0 else 0.0
    out = []
    for q in (alpha / 2, 1 - alpha / 2):
        zq = stats.norm.ppf(q)
        a = stats.norm.cdf(z0 + (z0 + zq) / (1 - acc * (z0 + zq)))
        out.append(float(np.percentile(boots, 100 * np.clip(a, 0, 1))))
    return out
