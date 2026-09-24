"""T0 unit checks (CPU): hautus/logit, G3 fitter recovery, bootstrap coverage under a planted null, judge parser,
hazard sign recovery. Run: .venv/bin/python -m pytest -q tests/"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from analysis import fit_glm, hautus_logit  # noqa: E402
from common import degenerate, hautus, logit  # noqa: E402
from judge import parse  # noqa: E402


def test_hautus_logit():
    assert abs(hautus(0, 10) - 0.5 / 11) < 1e-12
    p = hautus(3, 10)
    assert abs(1 / (1 + math.exp(-logit(p))) - p) < 1e-12


def simulate(a_true, b_true, n_items=200, steps=10, rng=None):
    xs = np.linspace(-2, 2, steps)
    kE, kS, n = [], [], []
    for x in xs:
        pe = 1 / (1 + np.exp(-x))
        ps = 1 / (1 + np.exp(-(a_true + b_true * x)))
        kE.append(rng.binomial(n_items, pe))
        kS.append(rng.binomial(n_items, ps))
        n.append(n_items)
    return np.array(kE, float), np.array(kS, float), np.array(n, float)


def test_g3_recovery():
    rng = np.random.default_rng(0)
    est = []
    for _ in range(50):
        g = {}
        for m, a in (("gemma", 0.3), ("gams", -0.7)):
            kE, kS, n = simulate(a, 1.0, rng=rng)
            g[m] = fit_glm(hautus_logit(kE, n), kS, n)[0]
        est.append(g["gams"] - g["gemma"])
    assert abs(np.mean(est) - (-1.0)) < 0.1  # attenuation from noisy x is small at n=200


def test_bootstrap_null_coverage():
    rng = np.random.default_rng(1)
    cover = 0
    sims = 60
    for _ in range(sims):
        R = {}
        for m in ("gemma", "gams"):
            probs = 1 / (1 + np.exp(-np.linspace(-2, 2, 8)))
            E = (rng.random((8, 100)) < probs[:, None]).astype(float)
            S = (rng.random((8, 100)) < probs[:, None]).astype(float)
            R[m] = (E, S)

        def g3(w, sel):
            a = {}
            for m in R:
                E, S = R[m]
                kE, kS, n = (E[sel[m]] * w).sum(1), (S[sel[m]] * w).sum(1), np.full(len(sel[m]), w.sum())
                a[m] = fit_glm(hautus_logit(kE, n), kS, n)[0]
            return a["gams"] - a["gemma"]
        boots = []
        for _ in range(150):
            w = np.bincount(rng.integers(0, 100, 100), minlength=100).astype(float)
            boots.append(g3(w, {m: rng.integers(0, 8, 8) for m in R}))
        lo, hi = np.percentile(boots, [2.5, 97.5])
        cover += lo <= 0 <= hi
    assert cover / sims >= 0.85


def test_parser_and_degenerate():
    assert parse("REFUSE") == "REFUSE" and parse("partial.") == "PARTIAL" and parse("Comply") == "COMPLY"
    assert parse("I think") == "UNPARSED"
    assert degenerate("") == 1 and degenerate("a b c d " * 5) == 1 and degenerate("one two three four five") == 0


def test_hazard_sign():
    import pandas as pd
    import statsmodels.api as sm
    import statsmodels.formula.api as smf
    rng = np.random.default_rng(3)
    recs = []
    for i in range(300):
        sh = int(i % 2)
        for s in range(6):
            p = 1 / (1 + np.exp(-(-2 + 0.3 * s + 1.2 * sh)))
            ev = int(rng.random() < p)
            recs.append({"item": i, "step": s, "shallow": sh, "event": ev, "SL": int(i % 3 == 0)})
            if ev:
                break
    d = pd.DataFrame(recs)
    r = smf.gee("event ~ C(step) + shallow + SL", groups="item", data=d, family=sm.families.Binomial(),
                cov_struct=sm.cov_struct.Exchangeable()).fit()
    assert r.params["shallow"] > 0.5
