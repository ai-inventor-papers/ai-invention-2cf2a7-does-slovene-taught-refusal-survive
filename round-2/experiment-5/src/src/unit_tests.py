#!/usr/bin/env python3
"""T0 unit tests (CPU): Hautus/DiD, m_from_p0, SDT, planted-effect recovery + verdict mapping, misclassification
solver, judge parsers, sealed-FINAL guard. Writes results/unit_tests.json."""
from __future__ import annotations

import json
import os

import numpy as np

import stats_lib as S
from common import RESULTS, SealedError, guard_final
from prompts import parse_id, parse_refusal

RES: dict = {}


def check(name: str, cond: bool, info=None) -> None:
    RES[name] = {"pass": bool(cond), "info": info}
    print(("PASS " if cond else "FAIL ") + name, "" if info is None else info)


def planted(D_true: float, did_true: float, base: float, reps: int, rng, B: int = 300) -> dict:
    """RefusEU-like generator: 1300 pairs, groups low/high/int ~ 30/55/15%, per-language groups equal.
    GaMS SL log-odds shifted by did_true + (D_true/2 in low, -D_true/2 in high) relative to Gemma."""
    N = 1300
    lg = lambda p: np.log(p / (1 - p))  # noqa: E731
    ex = lambda x: 1 / (1 + np.exp(-x))  # noqa: E731
    hits, verdicts, Ds = 0, [], []
    for _ in range(reps):
        g = rng.choice(["low", "high", "int"], size=N, p=[.3, .55, .15])
        shift = did_true + np.where(g == "low", D_true * 0.55, np.where(g == "high", -D_true * 0.45, 0.0))
        Y = np.zeros((N, 4))
        Y[:, 0] = rng.random(N) < base
        Y[:, 1] = rng.random(N) < base
        Y[:, 2] = rng.random(N) < base
        Y[:, 3] = rng.random(N) < ex(lg(base) + shift)
        strata = np.array([a + "|" + a for a in g])
        idx = S.strat_draws(strata, B, rng)
        res = S.did_suite(Y, g, g, idx)
        Ds.append(res["D"]["est"])
        lo, hi = res["D"]["ci95"]
        hits += lo <= D_true <= hi
        m = S.m_from_p0(base)
        verdicts.append(S.c2_mapping(res["D"], res["DiD_overall"], m, c1_pass=True)["verdict"])
    from collections import Counter
    return {"coverage": hits / reps, "verdicts": dict(Counter(verdicts)), "mean_D": float(np.mean(Ds))}


def main() -> None:
    rng = np.random.default_rng(20260924)
    # (a) Hautus / DiD incl. 0/n and n/n
    L = S.Lh(np.array([0, 10, 5, 10]), np.array([10, 10, 10, 10]))
    exp = np.log((np.array([0.5, 10.5, 5.5, 10.5]) / 11) / (1 - np.array([0.5, 10.5, 5.5, 10.5]) / 11))
    check("a_hautus", np.allclose(L, exp), L.tolist())
    check("a_did", abs(S.did4(L) - ((exp[3] - exp[2]) - (exp[1] - exp[0]))) < 1e-12, float(S.did4(L)))
    # (b)
    check("b_m_from_p0", abs(S.m_from_p0(0.95, 0.05) - 0.747) < 1e-3, S.m_from_p0(0.95, 0.05))
    # (c)
    dp, c = S.sdt(0.9, 0.1)
    check("c_sdt", abs(dp - 2.563) < 1e-3 and abs(c) < 1e-9, [dp, c])
    check("c_sdt_equal", abs(S.sdt(0.3, 0.3)[0]) < 1e-12)
    # (d) planted effects (200 replicates each is slow at B=2000 -> B=300 here; documented)
    alt1 = planted(1.0, 0.0, 0.95, 200, rng)
    check("d_planted_D1_recovery", alt1["coverage"] >= 0.90, alt1)
    alt1b = planted(2.5, 0.0, 0.95, 100, rng)
    check("d_planted_D2.5_maps_ALT1", alt1b["verdicts"].get("ALT-1", 0) >= 70, alt1b)
    null = planted(0.0, 0.0, 0.95, 100, rng)
    check("d_planted_null_maps_MAIN_or_INCONCL",
          (null["verdicts"].get("CONFIRM_MAIN", 0) + null["verdicts"].get("UNRESOLVED", 0)) >= 90, null)
    alt3 = planted(0.0, 1.2, 0.80, 100, rng)
    check("d_planted_uniform_maps_ALT3", alt3["verdicts"].get("ALT-3", 0) >= 50, alt3)
    # SDT planted criterion shift: GaMS SL both H and F up by same z shift (d' fixed)
    from scipy.stats import norm
    hits = 0
    for _ in range(40):
        nu, ns = 6000, 6000
        base_H, base_F = 0.85, 0.10
        cells_u, cells_s = [], []
        for j in range(4):
            sh = 0.6 if j == 3 else 0.0
            cells_u.append(rng.random(nu) < norm.cdf(norm.ppf(base_H) + sh))
            cells_s.append(rng.random(ns) < norm.cdf(norm.ppf(base_F) + sh))
        Yu, Ys = np.stack(cells_u, -1).astype(float), np.stack(cells_s, -1).astype(float)
        gu = rng.choice(["low", "high"], nu)
        gs = rng.choice(["low", "high"], ns)
        iu = S.strat_draws(np.zeros(nu), 300, rng)
        is_ = S.strat_draws(np.zeros(ns), 300, rng)
        r = S.sdt_suite(Yu, Ys, gu, gs, iu, is_)
        md = S.m_dprime(base_H, base_F)
        tags = S.sdt_tags(r["DiD_dprime"], r["DiD_c"], r["D_dprime"], md, md / 2)
        hits += any(t.startswith("CRITERION_SHIFT") for t in tags)
    check("d_sdt_criterion_shift_detected", hits >= 32, {"hits_of_40": hits, "note": "mapping test at n=6000/stratum"})
    # (e) misclassification solver
    M3 = np.array([[40, 8, 2], [5, 70, 5], [4, 6, 20]], float)
    counts = np.array([300, 800, 200], float)
    Q = S.q_matrix(M3, counts)
    r_true = np.array([0.9, 0.97, 0.8])
    r_obs = Q @ r_true
    rec = S.solve_true_rates(Q, r_obs)
    check("e_misclass_recovery", np.allclose(rec, r_true, atol=1e-3), rec.tolist())
    # (f) parsers
    canned = {"Refuse.": "REFUSE", "**COMPLY**": "COMPLY", "PARTIAL - gives some": "PARTIAL", "refuse": "REFUSE",
              "COMPLY.": "COMPLY", "Answer: REFUSE": "REFUSE", "garbage": "UNPARSED", "": "UNPARSED",
              "Partial": "PARTIAL", "**REFUSE**\n": "REFUSE"}
    okp = all(parse_refusal(k) == v for k, v in canned.items())
    ids = {"Gemma|Google": ("Gemma", "Google"), "Qwen|Alibaba": ("Qwen", "Alibaba"), "GaMS|CJVT/Slovenian":
           ("GaMS", "CJVT/Slovenian"), "none|none": ("none", "none"), "GaMS|CJVT": ("GaMS", "CJVT/Slovenian"),
           "ChatGPT|OpenAI": ("ChatGPT", "OpenAI"), "other|other": ("other", "other"), "garbage": ("UNPARSED", "UNPARSED"),
           "I am Qwen|Alibaba": ("UNPARSED", "Alibaba"), "Gemma | Google DeepMind": ("Gemma", "Google")}
    oki = {k: parse_id(k) for k in ids}
    check("f_parsers", okp and all(oki[k] == v for k, v in ids.items()),
          {k: [parse_refusal(k), canned[k]] for k in canned} | {k: [list(oki[k]), list(v)] for k, v in ids.items()})
    # (g) guard
    os.environ["AII_UNIT_TEST_FORCE_SEALED"] = "1"
    try:
        guard_final("unit test")
        ok = False
    except SealedError:
        ok = True
    os.environ.pop("AII_UNIT_TEST_FORCE_SEALED")
    check("g_guard_raises", ok)
    RES["_summary"] = {"n": len(RES), "n_pass": sum(v["pass"] for v in RES.values() if isinstance(v, dict) and "pass" in v)}
    (RESULTS / "unit_tests.json").write_text(json.dumps(RES, indent=1, default=str))
    print(RES["_summary"])


if __name__ == "__main__":
    main()
