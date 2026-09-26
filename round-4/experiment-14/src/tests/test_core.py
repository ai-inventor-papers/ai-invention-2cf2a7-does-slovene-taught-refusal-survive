"""T0 unit tests: Hautus, Rogan-Gladen, PPI++ recovery, kappa vs sklearn, two-point interpolation vs GLM, lockstep
synthetic (OUT = IN = INT = G3 = 0), planted output-only lag, placebo centring, suffix/cell builder, cache key."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from analysis import apply_rg, lag_stats, logit  # noqa: E402
from common import CELLS, SUFFIX, user_turn  # noqa: E402
from stats_core import cohen_kappa, glm_fit, hautus  # noqa: E402


def test_hautus():
    assert abs(hautus(0, 10) - 0.5 / 11) < 1e-12
    assert abs(hautus(10, 10) - 10.5 / 11) < 1e-12


def test_rogan_gladen():
    se, sp, p = 0.9, 0.7, 0.4
    obs = p * se + (1 - p) * (1 - sp)
    assert abs(float(apply_rg(np.array([obs]), np.array([se]), np.array([sp]))[0]) - p) < 1e-9


def test_kappa_vs_sklearn():
    from sklearn.metrics import cohen_kappa_score
    rng = np.random.default_rng(0)
    a = rng.integers(0, 3, 300)
    b = np.where(rng.random(300) < 0.7, a, rng.integers(0, 3, 300))
    assert abs(cohen_kappa(a, b) - cohen_kappa_score(a, b)) < 1e-9


def test_ppi_recovers_truth():
    rng = np.random.default_rng(1)
    N, n, truth = 20000, 400, 0.30
    y_all = rng.random(N) < truth
    f_all = np.where(y_all, rng.random(N) < 0.95, rng.random(N) < 0.35)  # judge over-calls
    gold = rng.choice(N, n, replace=False)
    f, y = f_all[gold].astype(float), y_all[gold].astype(float)
    lam = np.clip(np.cov(y, f)[0, 1] / ((1 + n / N) * f.var(ddof=1)), 0, 1)
    theta = y.mean() + lam * (f_all.mean() - f.mean())  # PPI++ (Angelopoulos et al. 2023)
    theta1 = f_all.mean() + (y.mean() - f.mean())  # classic PPI rectifier (lambda = 1), used across cells
    assert abs(theta1 - truth) < 0.05
    assert abs(theta - truth) < 0.05
    assert abs(f_all.mean() - truth) > 0.15  # the naive estimate is biased


def _synthetic_Y(lag_out: float = 0.0, lag_in: float = 0.0, model_shift: float = 0.0):
    Y = {}
    xs = {"zero": 2.0, "lo": 0.8, "hi": -0.9}
    for m in ("gemma_it", "gams3_it"):
        for d, x in xs.items():
            for (i, o) in CELLS:
                e = 0.0 if d == "zero" else 1.0
                add = e * (lag_out * (o != "en") + lag_in * (i != "en")) + (model_shift if m == "gams3_it" else 0)
                Y[(m, d, i, o)] = np.array([x + add])
    return Y


def test_lockstep_zero():
    S = lag_stats(_synthetic_Y())
    for k in ("OUT_SL|gemma_it", "IN_SL|gemma_it", "INT_SL|gemma_it", "G3|slsl", "G3edit|slsl"):
        assert abs(float(S[k][0])) < 1e-9, k


def test_planted_output_lag():
    S = lag_stats(_synthetic_Y(lag_out=1.0))
    assert abs(float(S["OUT_SL|gemma_it"][0]) - 1.0) < 1e-9
    assert abs(float(S["IN_SL|gemma_it"][0])) < 1e-9
    S = lag_stats(_synthetic_Y(lag_in=1.0))
    assert abs(float(S["IN_SL|gemma_it"][0]) - 1.0) < 1e-9
    assert abs(float(S["OUT_SL|gemma_it"][0])) < 1e-9


def test_interpolation_matches_glm_on_linear_curve():
    # exact linear logit relation y = a + x; GLM intercept recovers a with large n; two-point interpolation exactly
    a_true = 0.7
    xs = np.array([2.0, 0.8, -0.9])
    p_en = 1 / (1 + np.exp(-xs))
    p_sl = 1 / (1 + np.exp(-(a_true + xs)))
    n = np.array([1e6, 1e6, 1e6])
    a_glm, b_glm = glm_fit(p_sl * n, n, p_en)
    yl, yh = logit(p_sl[1]), logit(p_sl[2])
    a_int = yl + (0 - xs[1]) * (yh - yl) / (xs[2] - xs[1])
    assert abs(a_glm - a_true) < 1e-3 and abs(a_int - a_true) < 1e-9


def test_placebo_centres():
    rng = np.random.default_rng(2)
    a = (rng.random(200) < 0.5).astype(float)
    b = (rng.random(200) < 0.5).astype(float)
    sw = rng.random((3000, 200)) < 0.5
    null = np.where(sw, b, a).mean(1) - np.where(sw, a, b).mean(1)
    assert abs(null.mean()) < 0.01


def test_cells_and_suffix():
    turns = {user_turn("PROMPT", i, o) for (i, o) in CELLS}
    assert len(turns) == 9
    for (i, o) in CELLS:
        assert user_turn("P", i, o).endswith("\n\n" + SUFFIX[i][o])


def test_cache_key_deterministic():
    from judge_paid import build_messages
    from common import sha1, JUDGE_PROMPT_SHA
    m1, _, s1 = build_messages("p1", "req", "resp")
    m2, _, s2 = build_messages("p1", "req", "resp")
    assert m1 == m2 and s1 == s2 == JUDGE_PROMPT_SHA
    assert sha1("x|" + s1) == sha1("x|" + s2)
