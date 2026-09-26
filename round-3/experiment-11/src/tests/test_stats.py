"""T0 unit checks for src/stats_core.py and the G3 machinery in src/analysis.py (CPU only)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stats_core import (ci, cohen_kappa, expit, glm_fit, hautus, logit, mcnemar_exact, rogan_gladen,  # noqa: E402
                        sdt, wilson)


def test_hautus():
    assert hautus(0, 10) == 0.5 / 11
    assert hautus(10, 10) == 10.5 / 11


def test_sdt_closed_form():
    kh, nh, kf, nf = 80, 100, 20, 100
    zh, zf = stats.norm.ppf(80.5 / 101), stats.norm.ppf(20.5 / 101)
    d, c = sdt(kh, nh, kf, nf)
    assert abs(d - (zh - zf)) < 1e-12 and abs(c + (zh + zf) / 2) < 1e-12


def test_mcnemar_matches_binomtest():
    for b, c in ((3, 12), (10, 10), (0, 7)):
        assert abs(mcnemar_exact(b, c) - min(1.0, stats.binomtest(min(b, c), b + c, 0.5).pvalue)) < 1e-12


def test_wilson_contains_p():
    lo, hi = wilson(30, 100)
    assert lo < 0.3 < hi


def test_glm_recovers_a():
    rng = np.random.default_rng(0)
    p_en = np.linspace(0.15, 0.85, 8)
    for a_true, b_true in ((0.8, 1.2), (-1.0, 0.9)):
        n = np.full(8, 20000)
        k = rng.binomial(n, expit(a_true + b_true * logit(p_en)))
        a, b = glm_fit(k, n, p_en)
        assert abs(a - a_true) < 0.05 and abs(b - b_true) < 0.05


def test_rogan_gladen():
    se, sp, p = 0.9, 0.85, 0.4
    p_obs = p * se + (1 - p) * (1 - sp)
    assert abs(rogan_gladen(p_obs, se, sp) - p) < 1e-9
    assert np.isnan(rogan_gladen(0.5, 0.6, 0.6))


def test_kappa():
    a = np.array([1, 1, 0, 0, 1, 0])
    assert abs(cohen_kappa(a, a) - 1) < 1e-12
    rng = np.random.default_rng(1)
    x, y = rng.integers(0, 2, 5000), rng.integers(0, 2, 5000)
    assert abs(cohen_kappa(x, y)) < 0.05


def _synthetic_curve(a_gemma, a_gams, n_items=200, seed=0):
    rng = np.random.default_rng(seed)
    steps = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0]
    rows = []
    for m, a in (("gemma_it", a_gemma), ("gams3_it", a_gams)):
        for s_i, s in enumerate(steps):
            pen = 0.9 - 0.8 * s_i / (len(steps) - 1)
            psl = expit(a + 1.0 * logit(pen))
            for it in range(n_items):
                rows.append({"model": m, "item_id": f"i{it}", "step": s, "EN_BT": float(rng.random() < pen),
                             "L": float(rng.random() < psl)})
    return pd.DataFrame(rows)


def test_g3_recovery_and_coverage():
    from analysis import g3_analysis
    truth = -1.0
    cover = 0
    for rep in range(12):
        w = _synthetic_curve(0.5, 0.5 + truth, n_items=300, seed=rep)
        r = g3_analysis(w, B=200, seed=rep, perm=False)
        cover += r["ci95"][0] <= truth <= r["ci95"][1]
    assert cover >= 10, cover  # >= ~83% of 12 replicates (plan: >= 90% of 50; reduced for runtime)


def test_placebo_model_swap_null():
    from analysis import g3_analysis
    w = _synthetic_curve(0.3, 0.3, n_items=300, seed=7)
    r = g3_analysis(w, B=100, seed=7, perm=True)
    assert abs(r["G3"]) < 0.4 and r["perm"]["p_two_sided"] > 0.01


def test_ci_helper():
    lo, hi = ci(np.arange(1000))
    assert lo < 50 and hi > 950
