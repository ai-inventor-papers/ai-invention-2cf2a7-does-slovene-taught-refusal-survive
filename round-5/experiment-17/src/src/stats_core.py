#!/usr/bin/env python3
"""Statistics primitives (unit-tested in tests/test_stats.py). Wilson, Hautus log-odds, exact McNemar, Holm,
paired item bootstrap, Rogan-Gladen with the Lang-Reiczigel adjusted-Wald interval (as adopted by Lee et al.
arXiv 2511.21140 eq. 6: n~ = n + z^2, m~ = m + 2), PPI mean estimate (Angelopoulos et al. arXiv 2301.09633) with
inverse-probability weights, Cohen kappa. Wilson/Hautus/McNemar/kappa adapted from iter_4 exp14 src/stats_core.py."""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

Z = 1.959963984540054


def hautus(k, n):
    return (np.asarray(k, float) + 0.5) / (np.asarray(n, float) + 1.0)


def logit(p):
    p = np.clip(np.asarray(p, float), 1e-9, 1 - 1e-9)
    return np.log(p / (1 - p))


def wilson(k: int, n: int, z: float = Z) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def mcnemar_exact(b: int, c: int) -> float:
    """two-sided exact McNemar p on discordant counts b (0->1) and c (1->0) = binomial test on b+c at 0.5."""
    n = b + c
    if n == 0:
        return 1.0
    return float(min(1.0, stats.binomtest(min(b, c), n, 0.5).pvalue))


def holm(pvals: list[float]) -> list[float]:
    p = np.asarray(pvals, float)
    m = len(p)
    order = np.argsort(p)
    adj = np.empty(m)
    run = 0.0
    for rank, i in enumerate(order):
        run = max(run, (m - rank) * p[i])
        adj[i] = min(1.0, run)
    return adj.tolist()


def hautus_logodds_delta(y0, y1) -> float:
    y0, y1 = np.asarray(y0), np.asarray(y1)
    return float(logit(hautus(y1.sum(), len(y1))) - logit(hautus(y0.sum(), len(y0))))


def paired_boot(y0, y1, B: int = 2000, seed: int = 20260925) -> np.ndarray:
    """paired item bootstrap of mean(y1) - mean(y0) (items resampled with replacement)."""
    y0, y1 = np.asarray(y0, float), np.asarray(y1, float)
    rng = np.random.default_rng(seed)
    n = len(y0)
    idx = rng.integers(0, n, size=(B, n))
    return (y1[idx] - y0[idx]).mean(1)


def ci(v, lo=2.5, hi=97.5) -> list[float]:
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return [float("nan"), float("nan")]
    return [float(np.percentile(v, lo)), float(np.percentile(v, hi))]


def rogan_gladen(p_obs: float, se: float, sp: float) -> float:
    j = se + sp - 1
    if not np.isfinite(j) or j <= 0:
        return float("nan")
    return float(np.clip((p_obs + sp - 1) / j, 0, 1))


def rg_lang_reiczigel(k: int, n: int, x_se: float, n_se: float, x_sp: float, n_sp: float, z: float = Z) -> dict:
    """Rogan-Gladen point estimate (raw inputs) + Lang & Reiczigel (2014) adjusted Wald CI (Lee et al. eq. 6):
    p~ = (k + z^2/2)/(n + z^2), Se~ = (x_se + 1)/(n_se + 2), Sp~ = (x_sp + 1)/(n_sp + 2),
    theta~ = (p~ + Sp~ - 1)/(Se~ + Sp~ - 1),
    var = [p~(1-p~)/(n+z^2) + theta~^2 Se~(1-Se~)/(n_se+2) + (1-theta~)^2 Sp~(1-Sp~)/(n_sp+2)] / (Se~+Sp~-1)^2,
    CI = theta~ +- z sqrt(var), truncated to [0, 1]. 'unidentifiable' when Se + Sp - 1 < 0.2."""
    p = k / n if n else float("nan")
    se = x_se / n_se if n_se else float("nan")
    sp = x_sp / n_sp if n_sp else float("nan")
    J = se + sp - 1
    pt = (k + z * z / 2) / (n + z * z)
    set_ = (x_se + 1) / (n_se + 2)
    spt = (x_sp + 1) / (n_sp + 2)
    Jt = set_ + spt - 1
    if not np.isfinite(J) or Jt <= 0:
        return {"p_obs": p, "se": se, "sp": sp, "J": J, "p_rg": float("nan"), "ci": [float("nan")] * 2,
                "unidentifiable": True}
    th = (pt + spt - 1) / Jt
    var = (pt * (1 - pt) / (n + z * z) + th ** 2 * set_ * (1 - set_) / (n_se + 2)
           + (1 - th) ** 2 * spt * (1 - spt) / (n_sp + 2)) / Jt ** 2
    h = z * math.sqrt(max(var, 0.0))
    return {"p_obs": p, "se": se, "sp": sp, "J": J, "p_rg": rogan_gladen(p, se, sp),
            "ci": [float(max(0.0, th - h)), float(min(1.0, th + h))], "theta_adj": float(th),
            "unidentifiable": bool(J < 0.2)}


def ppi_mean(yhat_all, yhat_lab, y_lab, w_lab=None, z: float = Z) -> dict:
    """PPI mean estimate: theta = mean(yhat_all) + weighted-mean(y_lab - yhat_lab) (rectifier); CLT interval.
    w_lab = inverse-probability weights for the labelled rows (normalised)."""
    yhat_all = np.asarray(yhat_all, float)
    r = np.asarray(y_lab, float) - np.asarray(yhat_lab, float)
    w = np.ones_like(r) if w_lab is None else np.asarray(w_lab, float)
    w = w / w.sum()
    rect = float(np.sum(w * r))
    n_eff = 1.0 / float(np.sum(w ** 2))
    var_rect = float(np.sum(w ** 2 * (r - rect) ** 2)) * len(r) / max(len(r) - 1, 1)
    th = float(yhat_all.mean() + rect)
    se = math.sqrt(yhat_all.var(ddof=1) / len(yhat_all) + var_rect)
    return {"theta": th, "ci": [th - z * se, th + z * se], "rectifier": rect, "n_eff": n_eff}


def auroc(y, score, w=None) -> float:
    """weighted AUROC = P(score of a positive > score of a negative) with ties at 0.5 (Mann-Whitney form)."""
    y = np.asarray(y, int)
    sc = np.asarray(score, float)
    ww = np.ones_like(sc) if w is None else np.asarray(w, float)
    pos, neg = y == 1, y == 0
    if not pos.any() or not neg.any():
        return float("nan")
    num = den = 0.0
    for sp, wp in zip(sc[pos], ww[pos]):
        for sn, wn in zip(sc[neg], ww[neg]):
            num += wp * wn * (1.0 if sp > sn else 0.5 if sp == sn else 0.0)
            den += wp * wn
    return float(num / den) if den else float("nan")


def cohen_kappa(a, b) -> float:
    a, b = np.asarray(a), np.asarray(b)
    if len(a) == 0:
        return float("nan")
    cats = np.union1d(a, b)
    po = float(np.mean(a == b))
    pe = float(sum(np.mean(a == c) * np.mean(b == c) for c in cats))
    return float("nan") if pe >= 1 else (po - pe) / (1 - pe)
