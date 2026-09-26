"""Vectorised statistics shared by analysis.py (primary code path).

Rate matrices: for a model m, arm a, kind k, a readout gives an outcome matrix Y[step, item] in {0, 1, nan} (nan = the item
was not scored at that step, e.g. rotating blocks). Bootstrap weights W[b, item] (item multiplicities) turn it into counts
k = W @ Y0^T and n = W @ S^T (Y0 = nan->0, S = scored mask), so every bootstrap draw reuses the same resampled items for
both models and both arms (paired design).
"""
from __future__ import annotations

import math

import numpy as np
from scipy.special import expit, logit
from scipy.stats import norm


def hautus(k, n):
    return (np.asarray(k, float) + 0.5) / (np.asarray(n, float) + 1.0)


def glm_binom(x: np.ndarray, k: np.ndarray, n: np.ndarray, iters: int = 50) -> tuple[float, float]:
    """binomial logit GLM k/n ~ a + b x by IRLS (with a tiny ridge for separation); returns (a, b)."""
    x, k, n = (np.asarray(v, float) for v in (x, k, n))
    ok = n > 0
    x, k, n = x[ok], k[ok], n[ok]
    X = np.column_stack([np.ones_like(x), x])
    beta = np.zeros(2)
    y = (k + 0.5) / (n + 1.0)
    beta[0] = float(np.mean(logit(y)))
    for _ in range(iters):
        eta = X @ beta
        mu = expit(eta)
        w = n * mu * (1 - mu) + 1e-9
        z = eta + (k - n * mu) / w
        A = X.T @ (w[:, None] * X) + 1e-6 * np.eye(2)
        new = np.linalg.solve(A, X.T @ (w * z))
        if np.max(np.abs(new - beta)) < 1e-10:
            beta = new
            break
        beta = new
    return float(beta[0]), float(beta[1])


def isotonic_at0(x: np.ndarray, ysl: np.ndarray, w: np.ndarray | None = None) -> float:
    """isotonic (increasing) fit of SL log-odds on x; linear interpolation at x = 0 (clamped to the range)."""
    from sklearn.isotonic import IsotonicRegression
    o = np.argsort(x)
    ir = IsotonicRegression(increasing=True, out_of_bounds="clip").fit(x[o], ysl[o], sample_weight=None if w is None else w[o])
    return float(ir.predict([0.0])[0])


def kappa(a, b) -> float:
    a, b = np.asarray(a), np.asarray(b)
    if len(a) == 0:
        return float("nan")
    cats = sorted(set(a.tolist()) | set(b.tolist()))
    po = float(np.mean(a == b))
    pe = sum(float(np.mean(a == c)) * float(np.mean(b == c)) for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def sdt(H: np.ndarray, F: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """d' = z(H) - z(F); c_ref = (z(H) + z(F)) / 2 (= -c; higher = more refusal-prone)."""
    zH, zF = norm.ppf(H), norm.ppf(F)
    return zH - zF, (zH + zF) / 2.0


def rogan_gladen(p, se, sp):
    den = se + sp - 1.0
    if den <= 0:
        return float("nan")
    return float(np.clip((p + sp - 1.0) / den, 0.0, 1.0))


def pct_ci(v: np.ndarray, level: float) -> list[float]:
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    a = (1 - level) / 2
    return [float(np.quantile(v, a)), float(np.quantile(v, 1 - a))] if len(v) else [math.nan, math.nan]


def verdict_g3(g3: float, ci90, ci95, mde: float, m: float) -> str:
    if g3 < -m and ci95[1] < 0:
        return "LAG_BEYOND_MARGIN"
    if ci90[0] > -m and ci90[1] < m and mde <= 2 * m:
        return "LOCKSTEP_EQUIVALENT"
    if ci95[1] < 0:
        return "LAG_CI_EXCLUDES_0_WITHIN_MARGIN"
    if ci95[0] > 0:
        return "REVERSE_CI_EXCLUDES_0"
    return "INCONCLUSIVE"
