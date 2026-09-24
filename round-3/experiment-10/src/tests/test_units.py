"""T0 unit tests (CPU): Hautus/logit, Gram-Schmidt orthogonality, variance-ratio filter logic, alpha50 recovery,
censoring, Rogan-Gladen, cut(), judge-label parser, degeneracy / language helpers."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import stats as S  # noqa: E402
from common import degenerate, lang_ok, parse_label  # noqa: E402


def test_hautus_logit():
    assert S.hautus(0, 10) == pytest.approx(0.5 / 11)
    assert S.hlogit(5, 10) == pytest.approx(0.0)
    assert S.logit(0.5) == pytest.approx(0.0)


def test_orth():
    import torch
    torch.manual_seed(0)
    from geomlib import orth, unit
    d = 64
    b = [torch.randn(d) for _ in range(4)]
    v = unit(orth(torch.randn(d), b))
    for x in b:
        assert abs(float(v @ x) / float(x.norm())) < 1e-5


def test_alpha50_recovery():
    rng = np.random.default_rng(0)
    x = np.array([0, 0.2, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 2.5, 0.35])
    a_true, b_true = -2.6, 2.0  # alpha50 = 1.3
    est = []
    for rep in range(50):
        n = np.full(len(x), 48)
        k = rng.binomial(48, 1 / (1 + np.exp(-(a_true + b_true * x))))
        a, b = S.fit_logistic_counts(x, k, n)
        v, c = S.alpha50_from_fit(a, b, 3.0)
        est.append(float(v))
    assert abs(np.median(est) - 1.3) < 0.1


def test_censoring():
    v, c = S.alpha50_from_fit(-5.0, 0.5, 3.0)  # alpha50 = 10 > 3
    assert bool(c) and float(v) == 3.0
    v, c = S.alpha50_from_fit(-1.0, -0.5, 3.0)  # decreasing curve
    assert bool(c)


def test_batched_fit():
    x = np.array([0, 1, 2, 3.0])
    k = np.array([[1, 10, 30, 45], [2, 5, 20, 40]])
    n = np.full((2, 4), 48)
    a, b = S.fit_logistic_counts(x, k, n)
    for i in range(2):
        ai, bi = S.fit_logistic_counts(x, k[i], n[i])
        assert a[i] == pytest.approx(ai, abs=1e-5) and b[i] == pytest.approx(bi, abs=1e-5)


def test_rogan_gladen():
    assert S.rogan_gladen(0.5, 0.9, 0.9) == pytest.approx(0.5)
    assert S.rogan_gladen(0.26, 0.9, 0.8) == pytest.approx((0.26 + 0.8 - 1) / 0.7)


def test_cut():
    lag_e0, lag_c = 2.0, 0.8
    assert (lag_e0 - lag_c) / lag_e0 == pytest.approx(0.6)


def test_parser():
    cases = {"REFUSE": "REFUSE", "REFUSE.": "REFUSE", "refuse": "REFUSE", " Partial": "PARTIAL", "COMPLY\n": "COMPLY",
             "**REFUSE**": "REFUSE", "Comply.": "COMPLY", "PARTIAL - hedges": "PARTIAL", "": "UNPARSED", "maybe": "UNPARSED",
             "Refused": "REFUSE", "COMPLIES": "COMPLY", "partially": "PARTIAL", "REFUSE, because": "REFUSE",
             "Answer: COMPLY": "COMPLY", "  refuse  ": "REFUSE", "COMPLY!": "COMPLY", "PART": "PARTIAL", "REFU": "REFUSE",
             "xyz": "UNPARSED"}
    for s, e in cases.items():
        assert parse_label(s) == e, (s, parse_label(s))


def test_degenerate_lang():
    assert degenerate("") == 1
    assert degenerate("a b c d a b c d a b c d") == 1
    assert degenerate("Here is a normal answer with no repetition at all.") == 0
    assert lang_ok("I cannot help with that request because it is dangerous.", "en")[1] == 1
    assert lang_ok("Žal ne morem pomagati pri tej prošnji, ker je lahko nevarna za vas in druge.", "sl")[1] == 1


def test_switch_point():
    assert S.switch_point([0, 1, 2, 3], [0, 0, 1, 1]) == 2
    assert S.switch_point([0, 1, 2, 3], [0, 1, 0, 1]) == 3
    assert S.switch_point([0, 1, 2, 3], [0, 0, 0, 0]) is None
