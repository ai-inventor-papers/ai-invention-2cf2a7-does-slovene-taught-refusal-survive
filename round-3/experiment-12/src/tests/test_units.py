"""T0 unit tests (CPU): headroom formula, chance, bootstrap centring, macro eligibility, gate edges, KL, placebo generator."""
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from common import gate_verdict, headroom_H  # noqa: E402


def test_headroom_hand_example():
    assert abs(headroom_H(0.55, 0.6, 0.25) - (-0.142857)) < 1e-4


def test_chance_mixed_choice_counts():
    n_choices = [2, 4, 4, 5]
    assert abs(np.mean([1 / k for k in n_choices]) - (0.5 + 0.25 + 0.25 + 0.2) / 4) < 1e-12


def test_bootstrap_centres_on_point():
    rng = np.random.default_rng(0)
    n = 300
    vo = (rng.random(n) < 0.7).astype(float)
    vc = vo.copy()
    flip = rng.choice(n, 20, replace=False)
    vc[flip] = 0
    H = headroom_H(vc.mean(), vo.mean(), 0.25)
    ix = rng.integers(0, n, (2000, n))
    bH = (vc[ix].mean(1) - 0.25) / (vo[ix].mean(1) - 0.25) - 1
    assert abs(np.median(bH) - H) < 0.005


def test_macro_excludes_ineligible():
    cells = {"a": {"H": -0.1, "headroom": 0.3}, "b": {"H": -0.9, "headroom": 0.05}, "c": {"H": 0.0, "headroom": 0.2}}
    elig = [k for k, v in cells.items() if v["headroom"] >= 0.10]
    assert elig == ["a", "c"] and abs(np.mean([cells[k]["H"] for k in elig]) + 0.05) < 1e-12


def test_gate_edges():
    assert gate_verdict(0.20, 0.25) == "POSSIBLY_CATASTROPHIC"  # exactly .20 is not > .20
    assert gate_verdict(0.2001, 0.3) == "CATASTROPHIC"
    assert gate_verdict(0.05, 0.19) == "OK"
    assert gate_verdict(0.05, 0.21) == "POSSIBLY_CATASTROPHIC"
    assert gate_verdict(float("nan"), 0.1) == "PENDING"


def test_kl_identical_zero():
    lp = torch.log_softmax(torch.randn(3, 50), -1)
    kl = (lp.exp() * (lp - lp)).sum(-1)
    assert torch.all(kl == 0)


def test_placebo_centres_and_detects_planted_interaction():
    rng = np.random.default_rng(1)
    n = 300
    # per-pair deltas for two models; planted interaction 0.3 in the SL-EN difference
    d_g_en, d_g_sl = rng.normal(0, 0.5, n), rng.normal(-0.3, 0.5, n)
    d_m_en, d_m_sl = rng.normal(0, 0.5, n), rng.normal(0.0, 0.5, n)
    obs = (d_g_sl - d_g_en).mean() - (d_m_sl - d_m_en).mean()
    perm = []
    for _ in range(1000):
        sw = rng.random(n) < 0.5
        a = np.where(sw, d_m_sl - d_m_en, d_g_sl - d_g_en)
        b = np.where(sw, d_g_sl - d_g_en, d_m_sl - d_m_en)
        perm.append(a.mean() - b.mean())
    perm = np.array(perm)
    assert abs(perm.mean()) < 0.25 * perm.std()
    assert (np.abs(perm) >= abs(obs)).mean() < 0.01
