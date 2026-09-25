"""Statistics used by eval.py: Hautus-logit DiDs, joint item-cluster bootstrap, small-k meta-analysis (GLS on a
bootstrap covariance, REML + modified HKSJ, Q-profile I^2 CI, prediction interval), permutation placebos, Holm."""
from __future__ import annotations

import importlib.util
import math

import numpy as np
from scipy import optimize, stats

from common import EXP1


def load_exp1_stats_core():
    """exp1 stats_core.py loaded under a private name (its sibling common.py would clash with ours)."""
    spec = importlib.util.spec_from_file_location("exp1_stats_core", EXP1 / "stats_core.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def hl(k, n):
    p = (np.asarray(k, float) + 0.5) / (np.asarray(n, float) + 1.0)
    return np.log(p / (1 - p))


def did_counts(K, N):
    """K (...,4) counts in cell order (gemma en, gemma sl, gams en, gams sl); N (...,) items. GaMS(SL-EN)-Gemma(SL-EN)."""
    N = np.asarray(N, float)[..., None] * np.ones(4)
    L = hl(K, N)
    return (L[..., 3] - L[..., 2]) - (L[..., 1] - L[..., 0])


def did_pp(K, N):
    N = np.asarray(N, float)[..., None] * np.ones(4)
    P = np.asarray(K, float) / np.maximum(N, 1)
    return 100 * ((P[..., 3] - P[..., 2]) - (P[..., 1] - P[..., 0]))


def summ(point, boots, level=0.95) -> dict:
    b = np.asarray(boots, float)
    b = b[np.isfinite(b)]
    a = (1 - level) / 2
    se = float(np.std(b, ddof=1)) if len(b) > 1 else float("nan")
    return {"est": float(point), "se": se, "ci95": [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))],
            "ci90": [float(np.percentile(b, 5)), float(np.percentile(b, 95))], "MDE": 2.8 * se, "n_boot": int(len(b))}


def pair_boot_did(Y: np.ndarray, rng: np.random.Generator, B: int = 2000) -> dict:
    """Y (n,4) 0/1 complete pairs; pair (item-cluster) bootstrap of the log-odds DiD and pp DiD."""
    n = len(Y)
    idx = rng.integers(0, n, size=(B, n))
    Kb = Y[idx].sum(1)
    out = summ(did_counts(Y.sum(0), n), did_counts(Kb, np.full(B, n)))
    out["pp"] = summ(did_pp(Y.sum(0), n), did_pp(Kb, np.full(B, n)))
    out["n_pairs"] = int(n)
    out["rates"] = {c: float(Y[:, i].mean()) for i, c in enumerate(["gemma|en", "gemma|sl", "gams|en", "gams|sl"])}
    return out


# ---------------------------------------------------------------- meta-analysis (k small, dependent estimates)
def reml_tau2(y, v) -> float:
    y, v = np.asarray(y, float), np.asarray(v, float)

    def nll(t2):
        w = 1 / (v + t2)
        mu = (w * y).sum() / w.sum()
        return 0.5 * (np.log(v + t2).sum() + np.log(w.sum()) + (w * (y - mu) ** 2).sum())
    hi = max(10 * np.var(y) + 10 * v.max(), 1e-6)
    r = optimize.minimize_scalar(nll, bounds=(0, hi), method="bounded")
    return float(max(r.x, 0.0)) if nll(0.0) > r.fun else 0.0


def q_profile_tau2_ci(y, v, level=0.95):
    k = len(y)
    y, v = np.asarray(y, float), np.asarray(v, float)

    def Q(t2):
        w = 1 / (v + t2)
        mu = (w * y).sum() / w.sum()
        return float((w * (y - mu) ** 2).sum())
    lo_c, hi_c = stats.chi2.ppf((1 + level) / 2, k - 1), stats.chi2.ppf((1 - level) / 2, k - 1)
    ub = 1e4
    lo = 0.0 if Q(0) <= lo_c else optimize.brentq(lambda t: Q(t) - lo_c, 0, ub)
    hi = 0.0 if Q(0) <= hi_c else optimize.brentq(lambda t: Q(t) - hi_c, 0, ub)
    return [float(lo), float(hi)]


def random_effects(y, v) -> dict:
    """REML tau^2; modified Knapp-Hartung (HKSJ, max(1,q)) t(k-1) CI; Q, I^2 with Q-profile CI; 95% prediction interval.
    Independence across estimates is ASSUMED here (labelled as such)."""
    y, v = np.asarray(y, float), np.asarray(v, float)
    k = len(y)
    w0 = 1 / v
    mu0 = (w0 * y).sum() / w0.sum()
    Q = float((w0 * (y - mu0) ** 2).sum())
    t2 = reml_tau2(y, v)
    w = 1 / (v + t2)
    mu = float((w * y).sum() / w.sum())
    q = float((w * (y - mu) ** 2).sum() / (k - 1))
    se_hksj = math.sqrt(max(1.0, q) / w.sum())
    tcrit = stats.t.ppf(0.975, k - 1)
    s2 = (k - 1) * w0.sum() / (w0.sum() ** 2 - (w0 ** 2).sum())  # Higgins-Thompson typical within-study variance
    t2ci = q_profile_tau2_ci(y, v)
    I2 = max(0.0, (Q - (k - 1)) / Q) if Q > 0 else 0.0
    pi_half = stats.t.ppf(0.975, k - 2) * math.sqrt(t2 + se_hksj ** 2) if k > 2 else float("nan")
    return {"k": k, "mu": mu, "se_hksj_mod": se_hksj, "ci95_hksj_mod": [mu - tcrit * se_hksj, mu + tcrit * se_hksj],
            "se_wald_DL_style": float(math.sqrt(1 / w.sum())), "tau2_reml": t2, "tau": math.sqrt(t2), "tau2_ci95_qprofile": t2ci,
            "Q": Q, "Q_df": k - 1, "Q_p": float(stats.chi2.sf(Q, k - 1)), "I2": I2,
            "I2_ci95_qprofile": [t2ci[0] / (t2ci[0] + s2), t2ci[1] / (t2ci[1] + s2)],
            "prediction_interval95": [mu - pi_half, mu + pi_half], "q_hksj": q,
            "assumption": "independent estimates (for reference; the covariance-aware GLS estimate is primary)"}


def gls_fixed(y, S) -> dict:
    y = np.asarray(y, float)
    Si = np.linalg.pinv(S)
    one = np.ones(len(y))
    den = one @ Si @ one
    w = Si @ one / den
    return {"mu": float(w @ y), "se": float(math.sqrt(1 / den)), "weights": w.tolist(),
            "ci95": [float(w @ y - 1.96 * math.sqrt(1 / den)), float(w @ y + 1.96 * math.sqrt(1 / den))]}


# ---------------------------------------------------------------- placebos
def perm_summary(obs: float, null: np.ndarray, se_obs: float) -> dict:
    null = np.asarray(null, float)
    null = null[np.isfinite(null)]
    p = (1 + np.sum(np.abs(null) >= abs(obs) - 1e-12)) / (1 + len(null))
    return {"obs": float(obs), "null_mean": float(null.mean()), "null_sd": float(null.std(ddof=1)), "p_two_sided": float(p),
            "n_perm": int(len(null)), "centred_check_|null_mean|<0.1SE": bool(abs(null.mean()) < 0.1 * se_obs) if se_obs else None}


def holm(ps: dict) -> dict:
    items = sorted(ps.items(), key=lambda kv: kv[1])
    m = len(items)
    out, run = {}, 0.0
    for i, (k, p) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p))
        out[k] = run
    return out


def wilson(k, n, z=1.96):
    if n == 0:
        return [float("nan"), float("nan")]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [c - h, c + h]
