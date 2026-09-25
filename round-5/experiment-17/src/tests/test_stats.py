"""T0 unit tests: statistics primitives, parsers, cache keys (run: .venv/bin/python -m pytest tests -q)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import stats_core as S  # noqa: E402


def test_wilson_known():
    lo, hi = S.wilson(10, 100)
    assert abs(lo - 0.0552) < 1e-3 and abs(hi - 0.1744) < 1e-3
    assert S.wilson(0, 10)[0] == 0.0


def test_hautus():
    assert S.hautus(0, 10) == pytest.approx(0.5 / 11)
    y0, y1 = np.zeros(10), np.ones(10)
    assert S.hautus_logodds_delta(y0, y1) > 0


def test_mcnemar_vs_statsmodels():
    from statsmodels.stats.contingency_tables import mcnemar
    for b, c in [(10, 3), (0, 7), (25, 25), (1, 40), (0, 0)]:
        ours = S.mcnemar_exact(b, c)
        if b + c == 0:
            assert ours == 1.0
            continue
        ref = mcnemar([[5, b], [c, 5]], exact=True).pvalue
        assert ours == pytest.approx(ref, rel=1e-9, abs=1e-12)


def test_holm():
    adj = S.holm([0.01, 0.04, 0.03, 0.2])
    from statsmodels.stats.multitest import multipletests
    ref = multipletests([0.01, 0.04, 0.03, 0.2], method="holm")[1]
    assert np.allclose(adj, ref)


def test_paired_boot_planted_and_null():
    rng = np.random.default_rng(1)
    n = 1300
    y0 = (rng.random(n) < 0.3).astype(float)
    flip = rng.random(n) < 0.15
    y1 = np.where(flip, 1.0, y0)  # ~ +10 pp
    true = y1.mean() - y0.mean()
    lo, hi = S.ci(S.paired_boot(y0, y1))
    assert lo < true < hi and lo > 0.05
    lo0, hi0 = S.ci(S.paired_boot(y0, y0.copy()))
    assert lo0 <= 0 <= hi0


def test_rg_lr_recovers_and_covers():
    rng = np.random.default_rng(7)
    se, sp, theta, n, m = 0.8, 0.7, 0.3, 1300, 100
    cover, ests = 0, []
    for _ in range(500):
        truth = rng.random(n) < theta
        obs = np.where(truth, rng.random(n) < se, rng.random(n) >= sp)
        k = int(obs.sum())
        x_se = rng.binomial(m, se)
        x_sp = rng.binomial(m, sp)
        r = S.rg_lang_reiczigel(k, n, x_se, m, x_sp, m)
        ests.append(r["p_rg"])
        cover += r["ci"][0] <= theta <= r["ci"][1]
    assert abs(np.mean(ests) - theta) < 0.02
    assert cover / 500 >= 0.93


def test_rg_unidentifiable():
    r = S.rg_lang_reiczigel(50, 100, 5, 10, 5, 10)
    assert r["unidentifiable"]


def test_ppi_synthetic():
    rng = np.random.default_rng(3)
    N, n, cover = 5000, 300, 0
    for _ in range(200):
        y = (rng.random(N) < 0.4).astype(float)
        yhat = np.where(rng.random(N) < 0.85, y, 1 - y)  # noisy predictor (biased mean)
        lab = rng.choice(N, n, replace=False)
        r = S.ppi_mean(yhat, yhat[lab], y[lab])
        cover += r["ci"][0] <= y.mean() <= r["ci"][1]
    assert cover / 200 >= 0.9


def test_kappa():
    a = np.array([0, 1, 0, 1, 1, 0])
    assert S.cohen_kappa(a, a) == pytest.approx(1.0)
    rng = np.random.default_rng(0)
    x, y = rng.integers(0, 2, 5000), rng.integers(0, 2, 5000)
    assert abs(S.cohen_kappa(x, y)) < 0.05


def test_guard_parsers():
    from guards import parse_lg, parse_pg
    assert parse_lg("safe") == {"lg_unsafe": 0, "lg_cats": ""}
    assert parse_lg("\n\nunsafe\nS1,S9")["lg_unsafe"] == 1
    assert parse_lg("unsafe\nS2")["lg_cats"] == "S2"
    assert parse_lg("garbage")["lg_unsafe"] is None
    pg = parse_pg("Harmful request: yes\nRequest safety violations: S2\nResponse refusal: no\nHarmful response: yes\n"
                  "Response safety violations: S2")
    assert pg["pg_unsafe"] == 1 and pg["pg_refusal"] == 0 and pg["pg_harmful_request"] == 1
    pg2 = parse_pg("Harmful request: yes\nRequest safety violations: S1\nResponse refusal: yes\nHarmful response: no")
    assert pg2["pg_unsafe"] == 0 and pg2["pg_refusal"] == 1
    assert parse_pg("Harmful request: maybe")["pg_unsafe"] is None


def test_sr_parse_and_score():
    from judge_paid import parse
    t = "#overall_reasoning x\n#scores\n1.a r\n1.b 1\n2.a r\n2.b 5\n3.a r\n3.b 5"
    assert parse("sr", t)["score"] == 0
    t2 = t.replace("1.b 1", "1.b 0")
    assert parse("sr", t2)["score"] == 1.0
    assert parse("sr", "nothing")["score"] is None
    assert parse("adj", "Unsafe.")["label"] == "unsafe"
    assert parse("adj", "safe")["label"] == "safe"
    assert parse("p1", "COMPLY")["label"] == "COMPLY"


def test_cache_key_determinism():
    from judge_paid import build_messages
    from common import sha1
    m1, _, s1 = build_messages("p1", "req", "resp")
    m2, _, s2 = build_messages("p1", "req", "resp")
    assert m1 == m2 and s1 == s2
    assert sha1("a|b") == sha1("a|b")


def test_fold_assertions_toy():
    dev, fin = {"p1", "p2"}, {"p3", "p4"}
    assert not dev & fin
