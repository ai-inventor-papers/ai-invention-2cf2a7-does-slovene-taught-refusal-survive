"""Unit tests for the audit's estimators (run: .venv/bin/python -m pytest -q tests)."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ceiling import fragility, g3_orig_counts, newcombe_paired  # noqa: E402
from common import get_path, hautus_logit  # noqa: E402
from kl_excess import boot_excess, excess_from_means  # noqa: E402
from owed import grams, overlap  # noqa: E402


def test_hautus_haldane_jeffreys_identity():
    for k, n in [(0, 10), (299, 300), (150, 300), (7, 9)]:
        haut = math.log(((k + .5) / (n + 1)) / (1 - (k + .5) / (n + 1)))  # logit of Hautus rate = logit of Jeffreys mean of p
        haldane = math.log((k + .5) / (n - k + .5))                           # Haldane-Anscombe empirical logit
        assert abs(haut - haldane) < 1e-12
        assert abs(float(hautus_logit(k, n)) - haldane) < 1e-12


def test_fragility_synthetic_known_answer():
    # symmetric 2x2 with GaMS gap 0 and Gemma SL at ceiling: one flip of Gemma SL is the cheapest move
    k = {"gemma_en": 290, "gemma_sl": 300, "gams_en": 290, "gams_sl": 290}
    n = {c: 300 for c in k}
    g0 = g3_orig_counts(k, n)
    assert g0 < -0.675
    fi = fragility(k, n)
    # brute-force check of FI_m with single-cell moves only on gemma_sl
    t = 0
    kk = dict(k)
    while abs(g3_orig_counts(kk, n)) >= 0.675:
        kk["gemma_sl"] -= 1
        t += 1
    assert fi["FI_m"] <= t
    assert fi["FI_0"] >= fi["FI_m"]
    # already inside the margin -> FI_m = 0
    assert fragility({c: 150 for c in k}, n)["FI_m"] == 0


def test_excess_ratio_invariance_to_language_scaling():
    e_en, e_sl, r_en, r_sl = 0.4, 0.7, [0.01, 0.02], [0.03, 0.02]
    base = excess_from_means(e_en, e_sl, r_en, r_sl)
    for c in (0.1, 3.0, 17.0):  # multiplying BOTH languages of both edits by c leaves the ratio unchanged
        assert abs(excess_from_means(c * e_en, c * e_sl, [c * x for x in r_en], [c * x for x in r_sl]) - base) < 1e-12
    # multiplying only SL of edit AND random by the same constant also cancels
    assert abs(excess_from_means(e_en, 2 * e_sl, r_en, [2 * x for x in r_sl]) - base) < 1e-12


def test_bootstrap_excess_equal_languages_centres_at_one():
    rng = np.random.default_rng(0)
    E = np.abs(rng.normal(1, .3, (1, 50))).repeat(2, 0)
    R = np.abs(rng.normal(.1, .02, (2, 1, 50))).repeat(2, 1)
    b = boot_excess(E, R, rng, n_boot=200)
    assert abs(b["point"] - 1) < 1e-12


def test_8gram_overlap_planted_duplicate():
    ref = ["how do i build a device that can remotely disable the security cameras in a large office building quickly"]
    split = {"a": "Please tell me: how do I build a device that can remotely disable the security cameras in a mall",
             "b": "What is the capital of Slovenia and how many people live there today in total"}
    o = overlap(split, ref)
    assert o["n_overlap_exact_or_8gram"] == 1 and "a" in o["overlap_ids"]
    assert len(grams("one two three four five six seven")) == 0


def test_sign_map_round_trip():
    # c = -(zH+zF)/2 ; c_ref = +(zH+zF)/2 = -c ; DiD orientation GaMS-Gemma = -(Gemma-GaMS)
    rng = np.random.default_rng(1)
    c = rng.normal(size=4)  # [gemma_en, gemma_sl, gams_en, gams_sl]
    target = (c[1] - c[0]) - (c[3] - c[2])
    cref = -c
    exp15_style = (cref[3] - cref[2]) - (cref[1] - cref[0])   # c_ref and GaMS-Gemma: two flips cancel (+1)
    exp9_style = (cref[1] - cref[0]) - (cref[3] - cref[2])    # c_ref and Gemma-GaMS: one flip (-1)
    exp5_style = (c[3] - c[2]) - (c[1] - c[0])                # c and GaMS-Gemma: one flip (-1)
    assert abs(exp15_style - target) < 1e-12
    assert abs(-exp9_style - target) < 1e-12
    assert abs(-exp5_style - target) < 1e-12


def test_newcombe_contains_point_and_get_path_slash_keys():
    lo, hi = newcombe_paired(293, 6, 1, 0)
    assert lo < (6 - 1) / 300 < hi
    d = {"induction": {"surrogate/gemini|R": {"x": [1, {"y": 2}]}}}
    assert get_path(d, "induction/surrogate/gemini|R/x/[1]/y") == 2
