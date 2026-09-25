"""T0 unit tests for the statistics used by src/analysis.py (run: uv run pytest -q tests)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stats_core import cohen_kappa, glm_fit, hautus, logit, rogan_gladen, sdt  # noqa: E402


def test_hautus():
    assert abs(float(hautus(0, 10)) - 0.5 / 11) < 1e-12
    assert abs(float(hautus(10, 10)) - 10.5 / 11) < 1e-12


def test_rogan_gladen_inverse():
    se, sp, p_true = 0.9, 0.85, 0.3
    p_obs = p_true * se + (1 - p_true) * (1 - sp)
    assert abs(rogan_gladen(p_obs, se, sp) - p_true) < 1e-9


def test_kappa_vs_sklearn():
    from sklearn.metrics import cohen_kappa_score
    rng = np.random.default_rng(0)
    a = rng.choice(["R", "P", "C"], 300)
    b = np.where(rng.random(300) < 0.7, a, rng.choice(["R", "P", "C"], 300))
    assert abs(cohen_kappa(a, b) - cohen_kappa_score(a, b)) < 1e-9


def _synth(a_off: float, b: float = 1.0, n: int = 400, steps: int = 12, seed: int = 0, m0_off: float = 0.0):
    rng = np.random.default_rng(seed)
    p_en = np.linspace(0.12, 0.88, steps)
    x = logit(p_en)
    k_en = rng.binomial(n, p_en)
    k_sl = rng.binomial(n, 1 / (1 + np.exp(-(a_off + b * x))))
    return k_en, k_sl, n


def _g3(a_gams: float, a_gemma: float, seed: int = 0) -> float:
    ke1, ks1, n = _synth(a_gemma, seed=seed)
    ke2, ks2, _ = _synth(a_gams, seed=seed + 1)
    a1, _ = glm_fit(ks1, np.full(12, n), hautus(ke1, n))
    a2, _ = glm_fit(ks2, np.full(12, n), hautus(ke2, n))
    return a2 - a1


def test_g3_lockstep_zero():
    vals = [_g3(0.0, 0.0, seed=s) for s in range(20)]
    assert abs(np.mean(vals)) < 0.08


def test_g3_planted_offset_recovered():
    vals = [_g3(-1.0, 0.0, seed=s) for s in range(20)]
    assert abs(np.mean(vals) + 1.0) < 0.1


def test_rbase_parallel_offset():
    """pre-edit offset carried in parallel: G3 = G3_orig, G3_edit ~ 0 (margin constant along the curve)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from analysis import g3_from_counts
    n = 4000
    lams = {"gemma_it": [0.0] + list(np.linspace(0.2, 2, 12)), "gams3_it": [0.0] + list(np.linspace(0.2, 2, 12))}
    p_en = np.array([0.93] + list(np.linspace(0.88, 0.12, 12)))
    ck = {}
    for m, off in (("gemma_it", 0.0), ("gams3_it", -0.8)):
        p_sl = 1 / (1 + np.exp(-(logit(p_en) + off)))
        ck[m] = (np.vstack([p_en * n, p_sl * n]), np.full((2, 13), float(n)))
    g = g3_from_counts(ck, lams)
    assert abs(g["G3"] + 0.8) < 0.05 and abs(g["G3_edit"]) < 0.05
    # edit-induced divergence: margin grows with dose in GaMS only -> G3_edit < 0
    ck2 = dict(ck)
    p_sl = 1 / (1 + np.exp(-(logit(p_en) - 0.8 * np.r_[0, np.linspace(0.2, 2, 12)])))
    ck2["gams3_it"] = (np.vstack([p_en * n, p_sl * n]), np.full((2, 13), float(n)))
    ck2["gemma_it"] = (np.vstack([p_en * n, p_en * n]), np.full((2, 13), float(n)))
    assert g3_from_counts(ck2, lams)["G3_edit"] < -0.3


def test_sdt_closed_form():
    from scipy import stats
    d, c = sdt(80, 100, 20, 100)
    zh, zf = stats.norm.ppf(80.5 / 101), stats.norm.ppf(20.5 / 101)
    assert abs(d - (zh - zf)) < 1e-9 and abs(c + (zh + zf) / 2) < 1e-9


def test_ppi_unbiased_and_lower_variance():
    from analysis import ppi_params
    rng = np.random.default_rng(1)
    est_ppi, est_rg = [], []
    for _ in range(300):
        y = (rng.random(5000) < 0.4).astype(float)
        f = np.where(y == 1, rng.random(5000) < 0.9, rng.random(5000) < 0.25).astype(float)
        lab = rng.choice(5000, 120, replace=False)
        lam, rect = ppi_params({"c": (f[lab], y[lab])}, {"c": 5000})["c"]
        est_ppi.append(lam * f.mean() + rect)
        fj, gl = f[lab], y[lab]
        se = (((fj == 1) & (gl == 1)).sum() + .5) / ((gl == 1).sum() + 1)
        sp = (((fj == 0) & (gl == 0)).sum() + .5) / ((gl == 0).sum() + 1)
        est_rg.append(np.clip((f.mean() + sp - 1) / (se + sp - 1), 0, 1))
    assert abs(np.mean(est_ppi) - 0.4) < 0.01
    assert np.var(est_ppi) < np.var(est_rg)


def test_bootstrap_coverage():
    """percentile bootstrap of a binomial logit-rate difference covers ~95% on 200 synthetic replicates."""
    rng = np.random.default_rng(2)
    cover = 0
    for _ in range(200):
        y = rng.random(300) < 0.3
        th = float(logit(hautus(y.sum(), 300)))
        bs = [float(logit(hautus(y[rng.integers(0, 300, 300)].sum(), 300))) for _ in range(300)]
        lo, hi = np.percentile(bs, [2.5, 97.5])
        cover += lo <= float(logit(0.3)) <= hi
        _ = th
    assert 0.90 <= cover / 200 <= 0.99


def test_placebo_centres_at_zero():
    rng = np.random.default_rng(3)
    a = rng.random(400) < 0.5
    b = rng.random(400) < 0.5
    diffs = []
    for _ in range(500):
        sw = rng.random(400) < 0.5
        diffs.append(np.where(sw, b, a).mean() - np.where(sw, a, b).mean())
    assert abs(np.mean(diffs)) < 0.1 * np.std(diffs) + 1e-3
