"""Statistics helpers shared by analysis.py and the unit tests (audit.py deliberately does NOT import this module)."""
from __future__ import annotations

import math

import numpy as np
from scipy.stats import norm


def hautus(k, n):
    return (np.asarray(k, dtype=float) + 0.5) / (np.asarray(n, dtype=float) + 1.0)


def logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-9, 1 - 1e-9)
    return np.log(p / (1 - p))


def hlogit(k, n):
    return logit(hautus(k, n))


def dprime_c(k_hit, n_hit, k_fa, n_fa):
    h, f = hautus(k_hit, n_hit), hautus(k_fa, n_fa)
    zh, zf = norm.ppf(h), norm.ppf(f)
    return float(zh - zf), float(-(zh + zf) / 2)


def rogan_gladen(p_obs, sens, spec):
    d = sens + spec - 1
    if d <= 0.05:
        return float("nan")
    return float(np.clip((p_obs + spec - 1) / d, 0, 1))


def kappa_bin(a, b) -> float:
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if len(a) == 0:
        return float("nan")
    po = (a == b).mean()
    pe = a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean())
    return float((po - pe) / (1 - pe)) if pe < 1 - 1e-12 else float("nan")


def pabak(a, b) -> float:
    a, b = np.asarray(a), np.asarray(b)
    return float(2 * (a == b).mean() - 1) if len(a) else float("nan")


def fit_logistic_counts(x, k, n, iters: int = 50, ridge: float = 1e-4):
    """ML logistic fit P = expit(a + b x) on grouped binomial counts via IRLS (tiny ridge for separation).
    x, k, n: [G] or batched [B, G]. Returns a, b arrays."""
    x = np.asarray(x, dtype=float)
    k = np.asarray(k, dtype=float)
    n = np.asarray(n, dtype=float)
    single = k.ndim == 1
    if single:
        k, n = k[None], n[None]
    if x.ndim == 1:
        x = np.broadcast_to(x, k.shape)
    B = k.shape[0]
    beta = np.zeros((B, 2))
    X = np.stack([np.ones_like(x), x], -1)  # [B, G, 2]
    for _ in range(iters):
        eta = beta[:, 0:1] + beta[:, 1:2] * x
        p = 1 / (1 + np.exp(-np.clip(eta, -30, 30)))
        W = n * p * (1 - p) + 1e-9
        g = np.einsum("bgi,bg->bi", X, k - n * p) - ridge * beta
        H = np.einsum("bgi,bg,bgj->bij", X, W, X) + ridge * np.eye(2)[None]
        step = np.linalg.solve(H, g[..., None])[..., 0]
        step = np.clip(step, -5, 5)
        beta = beta + step
        if np.abs(step).max() < 1e-8:
            break
    a, b = beta[:, 0], beta[:, 1]
    return (a[0], b[0]) if single else (a, b)


def alpha50_from_fit(a, b, xmax: float):
    """alpha50 = -a/b if b > 0 and 0 < alpha50 <= xmax; else right-censored at xmax (returned value xmax, flag True).
    If the curve already starts above .5 at x=0 (a > 0, b > 0) alpha50 is 0 (flag 'left')."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        x50 = np.where(b > 1e-9, -a / b, np.inf)
    cens = ~(x50 <= xmax)
    val = np.where(cens, xmax, np.maximum(x50, 0.0))
    return val, cens


def auc_grid(x, rate) -> float:
    """mean refusal over the grid (trapezoid in x units, normalised by range)."""
    x, r = np.asarray(x, dtype=float), np.asarray(rate, dtype=float)
    o = np.argsort(x)
    x, r = x[o], r[o]
    return float(np.trapezoid(r, x) / (x[-1] - x[0]))


def switch_point(x, y):
    """smallest x from which the prompt refuses at ALL higher x (y binary, x sorted asc); None if it never switches."""
    x, y = np.asarray(x), np.asarray(y)
    o = np.argsort(x)
    x, y = x[o], y[o]
    if not y[-1]:
        return None
    i = len(y) - 1
    while i > 0 and y[i - 1]:
        i -= 1
    return float(x[i])


def pct_ci(v, lo=2.5, hi=97.5):
    v = np.asarray(v, dtype=float)
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return [float("nan"), float("nan")]
    return [float(np.percentile(v, lo)), float(np.percentile(v, hi))]


def safe(x):
    if isinstance(x, (np.floating, float)):
        return None if not math.isfinite(float(x)) else float(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x
