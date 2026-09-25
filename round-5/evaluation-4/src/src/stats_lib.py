#!/usr/bin/env python3
"""Primary-path statistics: Hautus, logit, Wilson, Kish n_eff, HT-weighted Se/Sp, Rogan-Gladen, Lang-Reiczigel
interval, PPI++ (power-tuned) prevalence, kappa/PABAK, SDT, binomial GLM, Newcombe difference CI, tipping solver.
Unit-tested in tests/test_stats.py. src/rederive.py re-implements these independently."""
from __future__ import annotations

import math

import numpy as np
from scipy import optimize, stats


def hautus(k, n):
    return (np.asarray(k, float) + 0.5) / (np.asarray(n, float) + 1.0)


def logit(p, eps=1e-6):
    p = np.clip(np.asarray(p, float), eps, 1 - eps)
    return np.log(p / (1 - p))


def expit(x):
    return 1.0 / (1.0 + np.exp(-np.asarray(x, float)))


def wilson(k: float, n: float, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return (float("nan"), float("nan"))
    p = min(1.0, max(0.0, k / n))
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(max(0.0, p * (1 - p) / n + z * z / (4 * n * n))) / d
    return (max(0.0, c - h), min(1.0, c + h))


def kish_neff(w) -> float:
    w = np.asarray(w, float)
    return float(w.sum() ** 2 / (w ** 2).sum()) if len(w) and (w ** 2).sum() > 0 else 0.0


def ht_se_sp(pred, truth, w) -> dict:
    """HT-weighted Se/Sp with Wilson CIs on the Kish effective n of the positive / negative class."""
    pred, truth, w = np.asarray(pred, int), np.asarray(truth, int), np.asarray(w, float)
    out = {"n": int(len(pred))}
    for name, cls, hit in (("Se", 1, 1), ("Sp", 0, 0)):
        m = truth == cls
        n = int(m.sum())
        if n == 0:
            out.update({name: None, f"{name}_ci": [None, None], f"n_{name}": 0, f"neff_{name}": 0.0})
            continue
        ww = w[m]
        est = float((ww * (pred[m] == hit)).sum() / ww.sum())
        ne = kish_neff(ww)
        out.update({name: est, f"{name}_ci": list(wilson(est * ne, ne)), f"n_{name}": n, f"neff_{name}": ne})
    out["prevalence_w"] = float((w * truth).sum() / w.sum()) if len(w) else None
    out["judge_rate_w"] = float((w * pred).sum() / w.sum()) if len(w) else None
    if out.get("Se") is not None and out.get("Sp") is not None:
        out["J"] = out["Se"] + out["Sp"] - 1
    else:
        out["J"] = None
    out["kappa"] = cohen_kappa(pred, truth)
    out["pabak"] = 2 * float(np.mean(pred == truth)) - 1 if len(pred) else None
    out["agree"] = float(np.mean(pred == truth)) if len(pred) else None
    return out


def cohen_kappa(a, b) -> float:
    a, b = np.asarray(a), np.asarray(b)
    if len(a) == 0:
        return float("nan")
    cats = np.union1d(a, b)
    po = float(np.mean(a == b))
    pe = float(sum(np.mean(a == c) * np.mean(b == c) for c in cats))
    return float("nan") if pe >= 1 else (po - pe) / (1 - pe)


def rogan_gladen(q, se, sp, lo=0.005, hi=0.995):
    j = np.asarray(se, float) + np.asarray(sp, float) - 1
    with np.errstate(divide="ignore", invalid="ignore"):
        p = (np.asarray(q, float) + np.asarray(sp, float) - 1) / j
    p = np.where(j > 0, p, np.nan)
    return np.clip(p, lo, hi)


def lang_reiczigel(x: int, n: int, se_k: int, se_n: int, sp_k: int, sp_n: int, alpha: float = 0.05) -> dict:
    """Lang & Reiczigel (2014) confidence interval for true prevalence with Se/Sp estimated from validation
    samples (asht::prevSeSp algorithm): adjusted Wald on the RG estimator with add-(z^2/4) corrections.
    Returns point (RG on raw), lower, upper, clipped to [0, 1]."""
    z = stats.norm.ppf(1 - alpha / 2)
    # add z^2/4 successes and failures to each sample (Agresti-Coull-type adjustment used in prevSeSp)
    a = z * z / 4
    nt, ns, nsp = n + 2 * a, se_n + 2 * a, sp_n + 2 * a
    qt, set_, spt = (x + a) / nt, (se_k + a) / ns, (sp_k + a) / nsp
    j = set_ + spt - 1
    q, se, sp = x / n, se_k / se_n, sp_k / sp_n
    jr = se + sp - 1
    point = float(np.clip((q + sp - 1) / jr, 0, 1)) if jr > 0 else float("nan")
    if j <= 0:
        return {"est": point, "lo": float("nan"), "hi": float("nan"), "identifiable": False}
    pt = (qt + spt - 1) / j
    var = (qt * (1 - qt) / nt + pt ** 2 * set_ * (1 - set_) / ns + (1 - pt) ** 2 * spt * (1 - spt) / nsp) / j ** 2
    h = z * math.sqrt(var)
    return {"est": point, "lo": float(np.clip(pt - h, 0, 1)), "hi": float(np.clip(pt + h, 0, 1)),
            "adj_center": float(pt), "identifiable": True}


def ppi_pp_mean(y_lab, f_lab, f_unlab, w_lab=None) -> dict:
    """PPI++ mean estimate (Angelopoulos et al. 2023) with power-tuned lambda:
    theta = lambda * mean(f_unlab) + mean(y_lab - lambda * f_lab); lambda* = Cov(y,f)/((1 + n/N) Var(f))."""
    y, f, fu = np.asarray(y_lab, float), np.asarray(f_lab, float), np.asarray(f_unlab, float)
    w = np.ones_like(y) if w_lab is None else np.asarray(w_lab, float)
    w = w / w.sum()
    n, N = len(y), len(fu)
    if n < 2 or N < 2:
        return {"est": float("nan"), "se": float("nan"), "lam": float("nan")}
    my, mf = (w * y).sum(), (w * f).sum()
    cov = (w * (y - my) * (f - mf)).sum()
    vf = (w * (f - mf) ** 2).sum()
    lam = float(np.clip(cov / ((1 + n / N) * vf), 0, 1)) if vf > 0 else 0.0
    rect = y - lam * f
    mr = (w * rect).sum()
    est = lam * fu.mean() + mr
    neff = kish_neff(w)
    se = math.sqrt(lam ** 2 * fu.var(ddof=1) / N + (w * (rect - mr) ** 2).sum() / max(1.0, neff - 1))
    return {"est": float(est), "se": float(se), "lam": lam}


def sdt(kh, nh, kf, nf):
    zh = stats.norm.ppf(hautus(kh, nh))
    zf = stats.norm.ppf(hautus(kf, nf))
    return zh - zf, -(zh + zf) / 2


def glm_fit(k_sl, n_sl, p_en) -> tuple[float, float]:
    k_sl, n_sl = np.asarray(k_sl, float), np.asarray(n_sl, float)
    x = logit(np.asarray(p_en, float), 1e-9)

    def nll(th):
        eta = th[0] + th[1] * x
        return -np.sum(k_sl * eta - n_sl * np.logaddexp(0, eta))

    def grad(th):
        mu = expit(th[0] + th[1] * x)
        r = k_sl - n_sl * mu
        return -np.array([r.sum(), (r * x).sum()])

    r = optimize.minimize(nll, np.array([0.0, 1.0]), jac=grad, method="BFGS")
    return float(r.x[0]), float(r.x[1])


def newcombe_diff(k1, n1, k2, n2, z=1.96) -> tuple[float, float, float]:
    """Newcombe (1998) hybrid score interval for p1 - p2 (independent-sample form; conservative for paired data)."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1, z)
    l2, u2 = wilson(k2, n2, z)
    d = p1 - p2
    lo = d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return d, lo, hi


def pct_ci(v, lo=2.5, hi=97.5):
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    if len(v) < 10:
        return [None, None]
    return [float(np.percentile(v, lo)), float(np.percentile(v, hi))]


def tipping_fp(q_non: float, q_en: float, target: float) -> float:
    """Extra false-positive rate e in the non-English-output cell that brings logit(q_non') - logit(q_en) to `target`
    when observed q_non = t + e (1 - t) (a judge adding false 'positives' at rate e among true negatives).
    Solve t: logit(t) = logit(q_en) + target, then e = (q_non - t)/(1 - t). Returns nan if not reachable (e<0)."""
    t = float(expit(logit(q_en) + target))
    if q_non <= t:
        return float("nan")
    return float((q_non - t) / (1 - t))


def tipping_fn(q_non: float, q_en: float, target: float) -> float:
    """False-negative rate f in the English-output cell that would hide positives: observed q_en = t (1 - f), so
    true t_en = q_en / (1 - f). Solve logit(q_non) - logit(t_en) = target -> t_en = expit(logit(q_non) - target)."""
    t = float(expit(logit(q_non) - target))
    if t <= q_en or t >= 1:
        return float("nan")
    return float(1 - q_en / t)
