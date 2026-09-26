#!/usr/bin/env python3
"""Vectorised statistics shared by analyze.py: binary kappa / PABAK / agreement, paired item bootstrap, Wilson,
Hautus log-odds, Jensen-Shannon distance, exact McNemar."""
from __future__ import annotations

import math

import numpy as np
from scipy import stats as st

from common import N_BOOT, SEED


def kappa(a: np.ndarray, b: np.ndarray) -> float:
    """Cohen's kappa for two binary vectors (NaN-free)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) == 0:
        return float("nan")
    po = np.mean(a == b)
    pa, pb = a.mean(), b.mean()
    pe = pa * pb + (1 - pa) * (1 - pb)
    return float((po - pe) / (1 - pe)) if pe < 1 else float("nan")


def kappa_rows(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """Row-wise kappa for bootstrap matrices A, B of shape (n_boot, n)."""
    po = (A == B).mean(1)
    pa, pb = A.mean(1), B.mean(1)
    pe = pa * pb + (1 - pa) * (1 - pb)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(pe < 1, (po - pe) / (1 - pe), np.nan)


def agree(a, b) -> float:
    return float(np.mean(np.asarray(a) == np.asarray(b))) if len(a) else float("nan")


def pabak(a, b) -> float:
    return 2 * agree(a, b) - 1


def boot_idx(n: int, n_boot: int = N_BOOT, seed: int = SEED) -> np.ndarray:
    return np.random.default_rng(seed).integers(0, n, size=(n_boot, n))


def ci(samples: np.ndarray, alpha: float = 0.05) -> tuple[float, float]:
    s = np.asarray(samples, float)
    s = s[np.isfinite(s)]
    if len(s) == 0:
        return (float("nan"), float("nan"))
    return (float(np.quantile(s, alpha / 2)), float(np.quantile(s, 1 - alpha / 2)))


def summarize(point: float, samples: np.ndarray) -> dict:
    lo, hi = ci(samples)
    s = np.asarray(samples, float)
    s = s[np.isfinite(s)]
    se = float(s.std(ddof=1)) if len(s) > 1 else float("nan")
    lo90, hi90 = ci(samples, alpha=0.10)
    return {"est": float(point), "ci_lo": lo, "ci_hi": hi, "se": se, "mde": 2.8 * se,
            "p_boot_le0": float(np.mean(s <= 0)) if len(s) else float("nan"), "ci90_lo": lo90, "ci90_hi": hi90}


def wilson(k: int, n: int, z: float = 1.96) -> dict:
    if n == 0:
        return {"k": 0, "n": 0, "p": float("nan"), "lo": float("nan"), "hi": float("nan")}
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return {"k": int(k), "n": int(n), "p": p, "lo": max(0.0, c - h), "hi": min(1.0, c + h)}


def hautus_logit(k: float, n: float) -> float:
    p = (k + 0.5) / (n + 1)
    return math.log(p / (1 - p))


def logit(p: float) -> float:
    p = min(max(p, 1e-9), 1 - 1e-9)
    return math.log(p / (1 - p))


def jsd(p: dict, q: dict) -> float:
    """Jensen-Shannon DISTANCE (sqrt of divergence, base 2) between two count dicts."""
    keys = sorted(set(p) | set(q))
    if not keys:
        return float("nan")
    P = np.array([p.get(k, 0) for k in keys], float)
    Q = np.array([q.get(k, 0) for k in keys], float)
    if P.sum() == 0 or Q.sum() == 0:
        return float("nan")
    P, Q = P / P.sum(), Q / Q.sum()
    M = 0.5 * (P + Q)

    def kl(x, y):
        m = x > 0
        return float(np.sum(x[m] * np.log2(x[m] / y[m])))
    return float(math.sqrt(max(0.0, 0.5 * kl(P, M) + 0.5 * kl(Q, M))))


def mcnemar_exact(a: np.ndarray, b: np.ndarray) -> dict:
    a, b = np.asarray(a, int), np.asarray(b, int)
    n01 = int(np.sum((a == 0) & (b == 1)))
    n10 = int(np.sum((a == 1) & (b == 0)))
    n = n01 + n10
    p = float(st.binomtest(n10, n, 0.5).pvalue) if n > 0 else 1.0
    return {"a_only": n10, "b_only": n01, "p_exact": p}
