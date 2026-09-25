"""T0 unit checks (CPU): Hautus/logit, G3 recovery on simulated curves (known a_m difference -1.0 and 0), bootstrap
coverage under a planted null, SDT branch recovery (Delta-c = 0.5 / Delta-d' = 0 and the reverse), rotating-block rate
function uses identical item ids in both arms, paired bootstrap index reuse, Rogan-Gladen on a known confusion matrix,
judge-output parser. Run: .venv/bin/python -m pytest -q tests/"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.special import expit, logit
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from analysis import block_weights, counts, fit_curve  # noqa: E402
from orclient import parse_label, parse_safe  # noqa: E402
from stats_core import glm_binom, hautus, kappa, pct_ci, rogan_gladen, sdt  # noqa: E402


def test_hautus():
    assert abs(hautus(0, 10) - 0.5 / 11) < 1e-12
    assert abs(hautus(10, 10) - 10.5 / 11) < 1e-12


def simulate_curve(a, b, rng, steps=40, n=150):
    xs = rng.uniform(-2, 2, steps)
    kE = rng.binomial(n, expit(xs))
    kS = rng.binomial(n, expit(a + b * xs))
    return kE.astype(float), np.full(steps, n, float), kS.astype(float), np.full(steps, n, float)


def test_g3_recovery():
    rng = np.random.default_rng(0)
    for delta in (-1.0, 0.0):
        est = []
        for _ in range(60):
            a = {}
            for m, aa in (("gemma", 0.5), ("gams", 0.5 + delta)):
                kE, nE, kS, nS = simulate_curve(aa, 1.0, rng)
                a[m] = fit_curve(kE, nE, kS, nS)[0]
            est.append(a["gams"] - a["gemma"])
        assert abs(np.mean(est) - delta) < 0.12, (delta, np.mean(est))


def test_glm_exact():
    x = np.linspace(-2, 2, 30)
    n = np.full(30, 1e6)
    k = n * expit(0.3 + 1.2 * x)
    a, b = glm_binom(x, k, n)
    assert abs(a - 0.3) < 1e-3 and abs(b - 1.2) < 1e-3


def test_bootstrap_null_coverage():
    rng = np.random.default_rng(1)
    ids = [f"i{j}" for j in range(100)]
    blocks = {i: ("C" if j < 50 else "R") for j, i in enumerate(ids)}
    cover, sims = 0, 60
    for _ in range(sims):
        pE = expit(rng.uniform(-1.5, 1.5, 12))
        Y = {m: ((rng.random((12, 100)) < pE[:, None]).astype(float), (rng.random((12, 100)) < pE[:, None]).astype(float))
             for m in ("gemma", "gams")}

        def g3(w, mult):
            a = {}
            for m in Y:
                kE, nE = counts(Y[m][0], w)
                kS, nS = counts(Y[m][1], w)
                a[m] = fit_curve(kE, nE, kS, nS, mult)[0]
            return a["gams"] - a["gemma"]
        bs = [g3(block_weights(rng, ids, blocks), np.bincount(rng.integers(0, 12, 12), minlength=12).astype(float))
              for _ in range(150)]
        lo, hi = pct_ci(np.array(bs), 0.90)
        cover += int(lo <= 0 <= hi)
    assert 0.80 <= cover / sims <= 1.0, cover / sims


def test_sdt_branch_recovery():
    rng = np.random.default_rng(2)
    ok_c, ok_d, sims = 0, 0, 40
    for _ in range(sims):
        for mode in ("criterion", "geometry"):
            dc_all, dd_all = [], []
            for _s in range(10):  # window steps
                dprime, cref = 1.5, rng.uniform(-0.3, 0.3)
                cS, dS = (cref + 0.5, dprime) if mode == "criterion" else (cref, dprime + 0.5)
                res = {}
                for arm, (c, d) in (("en", (cref, dprime)), ("sl", (cS, dS))):
                    H = norm.cdf(c + d / 2)
                    F = norm.cdf(c - d / 2)
                    kH, kF = rng.binomial(300, H), rng.binomial(150, F)
                    res[arm] = sdt(hautus(kH, 300), hautus(kF, 150))
                dd_all.append(res["sl"][0] - res["en"][0])
                dc_all.append(res["sl"][1] - res["en"][1])
            dc, dd = np.mean(dc_all), np.mean(dd_all)
            if mode == "criterion":
                ok_c += int(dc > 0.3 and abs(dd) < 0.3)
            else:
                ok_d += int(dd > 0.3 and abs(dc) < 0.3)
    assert ok_c / sims >= 0.9 and ok_d / sims >= 0.9, (ok_c, ok_d)


def test_rotating_block_same_items():
    Y_en = np.array([[1, 0, np.nan, 1], [0, np.nan, 1, 1]], float)
    Y_sl = np.array([[1, 1, np.nan, 0], [1, np.nan, 0, 0]], float)
    assert (np.isfinite(Y_en) == np.isfinite(Y_sl)).all()
    kE, nE = counts(Y_en)
    kS, nS = counts(Y_sl)
    assert (nE == nS).all() and list(nE) == [3, 3]


def test_paired_bootstrap_reuse():
    rng = np.random.default_rng(3)
    ids = [f"i{j}" for j in range(20)]
    w = block_weights(rng, ids, {i: "C" for i in ids})
    Y = (rng.random((5, 20)) < 0.5).astype(float)
    k1, n1 = counts(Y, w)
    k2, n2 = counts(Y.copy(), w)
    assert np.allclose(k1, k2) and np.allclose(n1, n2) and w.sum() == 20


def test_rogan_gladen():
    true_p, se, sp = 0.4, 0.9, 0.8
    obs = true_p * se + (1 - true_p) * (1 - sp)
    assert abs(rogan_gladen(obs, se, sp) - true_p) < 1e-12


def test_kappa():
    assert abs(kappa([1, 0, 1, 0], [1, 0, 1, 0]) - 1.0) < 1e-12


def test_parsers():
    assert parse_label(" refuse.") == "REFUSE"
    assert parse_label("**PARTIAL**") == "PARTIAL"
    assert parse_label("Comply") == "COMPLY"
    assert parse_label("") == "UNPARSED"
    assert parse_safe("UNSAFE") == "UNSAFE" and parse_safe("Safe.") == "SAFE"
