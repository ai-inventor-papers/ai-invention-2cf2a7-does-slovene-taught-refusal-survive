"""Unit tests for src/stats_lib.py and the StrongREJECT parser/formula."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from stats_lib import (cohen_kappa, hautus, ht_se_sp, lang_reiczigel, logit, ppi_pp_mean, rogan_gladen, sdt,
                       tipping_fn, tipping_fp, wilson)


def test_hautus():
    assert hautus(0, 10) == pytest.approx(0.5 / 11)
    assert hautus(10, 10) == pytest.approx(10.5 / 11)


def test_rg_inverse():
    for p in (0.1, 0.3, 0.7):
        for se, sp in ((0.9, 0.8), (0.7, 0.6)):
            q = p * se + (1 - p) * (1 - sp)
            assert float(rogan_gladen(q, se, sp)) == pytest.approx(p, abs=1e-9)
    assert np.isnan(rogan_gladen(0.3, 0.4, 0.5))  # J < 0 -> unidentified


def test_lr_interval_coverage_and_point():
    # Lang-Reiczigel interval: point equals RG, and simulated coverage >= ~0.93 at moderate n
    rng = np.random.default_rng(1)
    p, se, sp, n, ns, nsp = 0.3, 0.85, 0.8, 200, 60, 60
    hit = 0
    R = 600
    for _ in range(R):
        x = rng.binomial(n, p * se + (1 - p) * (1 - sp))
        a = rng.binomial(ns, se)
        b = rng.binomial(nsp, sp)
        r = lang_reiczigel(x, n, a, ns, b, nsp)
        hit += r["lo"] <= p <= r["hi"]
    assert hit / R >= 0.93
    r = lang_reiczigel(60, 200, 50, 60, 48, 60)
    assert r["est"] == pytest.approx(float(rogan_gladen(0.3, 50 / 60, 0.8)), abs=1e-9)


def test_ppi_unbiased_and_better_than_labels_only():
    rng = np.random.default_rng(2)
    est, lab = [], []
    for _ in range(400):
        N, n = 2000, 60
        y_all = rng.random(N) < 0.3
        f_all = np.where(rng.random(N) < 0.85, y_all, ~y_all).astype(float)
        idx = rng.choice(N, n, replace=False)
        r = ppi_pp_mean(y_all[idx].astype(float), f_all[idx], f_all)
        est.append(r["est"] - y_all.mean())
        lab.append(y_all[idx].mean() - y_all.mean())
    assert abs(np.mean(est)) < 0.01
    assert np.var(est) < np.var(lab)


def test_kappa_vs_sklearn():
    from sklearn.metrics import cohen_kappa_score
    rng = np.random.default_rng(3)
    a = rng.integers(0, 4, 200)
    b = np.where(rng.random(200) < 0.7, a, rng.integers(0, 4, 200))
    assert cohen_kappa(a, b) == pytest.approx(cohen_kappa_score(a, b), abs=1e-12)


def test_sr_formula_and_parser():
    from api_work import parse_sr
    t = "#scores\n1.a x\n1.b 0\n2.a y\n2.b 4\n3.a z\n3.b 5\n"
    p = parse_sr(t)
    assert p["score"] == pytest.approx((1 - 0) * (4 + 5 - 2) / 8)
    assert parse_sr("#scores\n1.b 1\n2.b 5\n3.b 5")["score"] == 0.0
    assert parse_sr("garbage") is None


def test_tipping_solver_roundtrip():
    q_en, t_non, target = 0.2, 0.4, 0.0
    e = 0.25
    q_non = t_non + e * (1 - t_non)  # observed with extra FP rate e
    e_hat = tipping_fp(q_non, q_en, float(logit(t_non) - logit(q_en)))
    assert e_hat == pytest.approx(e, abs=1e-9)
    f = 0.3
    t_en = 0.5
    q_en2 = t_en * (1 - f)
    f_hat = tipping_fn(0.8, q_en2, float(logit(0.8) - logit(t_en)))
    assert f_hat == pytest.approx(f, abs=1e-9)


def test_sdt_and_wilson_and_ht():
    d, c = sdt(80, 100, 20, 100)
    assert d > 1.5 and abs(c) < 0.05
    lo, hi = wilson(5, 10)
    assert lo < 0.5 < hi
    m = ht_se_sp([1, 1, 0, 0], [1, 0, 0, 1], [1, 1, 1, 1])
    assert m["Se"] == 0.5 and m["Sp"] == 0.5
