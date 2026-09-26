#!/usr/bin/env python3
"""Statistics primitives (unit-tested in tests/test_core.py). PROVENANCE: hautus / logit / wilson / sdt / mcnemar /
cohen_kappa / ci adapted from iter_4 exp14 src/stats_core.py; added Rogan-Gladen with the Lang-Reiczigel adjusted
interval and the PPI mean.

Lang & Reiczigel (2014, Prev Vet Med 113:13-22) 'adjusted' interval for a prevalence corrected by an imperfectly
known Se/Sp: an Agresti-Coull-style adjusted estimate of the apparent prevalence and of Se/Sp (each count + z^2/2
successes out of n + z^2 trials; implemented with z^2/4 per cell as in the paper's recommended 'adjusted' variant),
Rogan-Gladen on the adjusted quantities, and a delta-method variance that includes the Se/Sp validation-sample
variances. Clipped to [0, 1]."""
from __future__ import annotations

import math

import numpy as np
from scipy import stats


def hautus(k, n):
    return (np.asarray(k, float) + 0.5) / (np.asarray(n, float) + 1.0)


def hautus_bound(p, n):
    """bound a rate (possibly corrected, possibly 0/1) into [0.5/(n+1), 1 - 0.5/(n+1)]."""
    lo = 0.5 / (np.asarray(n, float) + 1.0)
    return np.clip(np.asarray(p, float), lo, 1 - lo)


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
    """d' and c with Hautus-corrected rates. H = refusal of harmful, F = refusal of benign twins."""
    zh = stats.norm.ppf(hautus(kh, nh))
    zf = stats.norm.ppf(hautus(kf, nf))
    return float(zh - zf), float(-(zh + zf) / 2)


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    return float(min(1.0, stats.binomtest(min(b, c), n, 0.5).pvalue))


def rogan_gladen(p_obs, se, sp):
    """vectorised RG: (p_obs + sp - 1)/(se + sp - 1), clipped to [0,1]; NaN where Youden J <= 0."""
    p_obs, se, sp = np.asarray(p_obs, float), np.asarray(se, float), np.asarray(sp, float)
    j = se + sp - 1
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.where(j > 0, (p_obs + sp - 1) / j, np.nan)
    return np.clip(r, 0, 1)


def rg_clipped(p_obs, se, sp) -> np.ndarray:
    """True where the unclipped RG estimate falls outside [0,1] (or J <= 0)."""
    p_obs, se, sp = np.asarray(p_obs, float), np.asarray(se, float), np.asarray(sp, float)
    j = se + sp - 1
    with np.errstate(divide="ignore", invalid="ignore"):
        r = (p_obs + sp - 1) / j
    return (j <= 0) | (r < 0) | (r > 1)


def lang_reiczigel(k: int, n: int, k_se: int, n_se: int, k_sp: int, n_sp: int, alpha: float = 0.05):
    """Lang-Reiczigel adjusted CI for the RG-corrected prevalence. k/n = apparent positives; k_se/n_se = judge-positive
    among reference-positive; k_sp/n_sp = judge-negative among reference-negative."""
    z = stats.norm.ppf(1 - alpha / 2)
    if min(n, n_se, n_sp) == 0:
        return (float("nan"), float("nan"), float("nan"))
    na, nse, nsp = n + z * z / 2, n_se + z * z / 2, n_sp + z * z / 2
    ap = (k + z * z / 4) / na
    se = (k_se + z * z / 4) / nse
    sp = (k_sp + z * z / 4) / nsp
    j = se + sp - 1
    if j <= 0:
        return (float("nan"), float("nan"), float("nan"))
    p = (ap + sp - 1) / j
    var = (ap * (1 - ap) / na + p * p * se * (1 - se) / nse + (1 - p) ** 2 * sp * (1 - sp) / nsp) / (j * j)
    h = z * math.sqrt(max(var, 0.0))
    return (float(np.clip(p, 0, 1)), float(np.clip(p - h, 0, 1)), float(np.clip(p + h, 0, 1)))


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


def sesp(pred, ref) -> dict:
    """Se/Sp of a binary judge vs a binary reference, with Wilson CIs and counts."""
    pred, ref = np.asarray(pred, bool), np.asarray(ref, bool)
    tp, fn = int((pred & ref).sum()), int((~pred & ref).sum())
    tn, fp = int((~pred & ~ref).sum()), int((pred & ~ref).sum())
    se = tp / (tp + fn) if tp + fn else float("nan")
    sp = tn / (tn + fp) if tn + fp else float("nan")
    return {"tp": tp, "fn": fn, "tn": tn, "fp": fp, "Se": se, "Sp": sp, "Se_ci": wilson(tp, tp + fn),
            "Sp_ci": wilson(tn, tn + fp), "J": se + sp - 1 if np.isfinite(se) and np.isfinite(sp) else float("nan"),
            "n": len(pred)}
