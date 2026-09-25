#!/usr/bin/env python3
"""T8: analysis dry run on SYNTHETIC per-item data using the real SCORE pair/category structure.

(a) planted D = +0.8 log-odds: bootstrap CI should cover it;
(b) planted null (all DiD = 0): |D| < m in ~most of 50 datasets (rate reported, not asserted to 90%, because m is
    fixed by the base rate and SE(D) is set by n -- this documents the screen's power instead);
(c) planted zEN slope in the per-category DiD: meta-regression should recover it.
Results -> results/synthetic_T8.json
"""
from __future__ import annotations

import json

import numpy as np

from analysis import CAT_ORDER, RES, dose_table
from common import DATA, HIGH_EN, LOW_EN, SEED, read_jsonl, setup_logging
from stats_core import Bootstrap, did_suite, m_from_p0, meta_regression
from loguru import logger


def simulate(cats: np.ndarray, did_by_cat: dict[str, float], rng, base=-0.2, lang_eff=-0.3, model_eff=0.2):
    n = len(cats)
    item = rng.normal(0, 1.0, n)  # shared item difficulty (prompt effect common to both models)
    Y = np.zeros((n, 4))
    for i, c in enumerate(cats):
        eta = np.array([base, base + lang_eff, base + model_eff, base + model_eff + lang_eff + did_by_cat[c]]) + item[i]
        Y[i] = rng.random(4) < 1 / (1 + np.exp(-eta))
    return Y


def main() -> None:
    setup_logging("test_synthetic")
    pairs = [p for p in read_jsonl(DATA / "pairs.jsonl") if p["role"] == "SCORE"]
    cats = np.array([p["category"] for p in pairs])
    rng = np.random.default_rng(SEED)
    dt = dose_table()
    out = {}
    # (a) planted D = +0.8 (low set +0.8, high set 0, others 0)
    planted = {c: (0.8 if c in LOW_EN else 0.0) for c in CAT_ORDER}
    Y = simulate(cats, planted, rng)
    bs = Bootstrap(cats, SEED)
    su = did_suite(Y, cats, bs, list(LOW_EN), list(HIGH_EN))
    m = m_from_p0(float(Y.mean()))
    out["planted_D_0.8"] = {"D_est": su["D"]["est"], "ci95": su["D"]["ci95"], "se": su["D"]["se"], "m": m,
                            "covers": su["D"]["ci95"][0] <= 0.8 <= su["D"]["ci95"][1],
                            "note": "log-odds DiD on the Hautus scale is attenuated by the random item effect "
                                    "(non-collapsibility); coverage of the conditional 0.8 is not guaranteed"}
    # (b) null x 50
    hits, Ds = 0, []
    for k in range(50):
        Yn = simulate(cats, {c: 0.0 for c in CAT_ORDER}, np.random.default_rng(SEED + 1000 + k))
        mk = m_from_p0(float(Yn.mean()))
        bsn = Bootstrap(cats, SEED + k, B=400)
        sn = did_suite(Yn, cats, bsn, list(LOW_EN), list(HIGH_EN))
        Ds.append(sn["D"]["est"])
        hits += abs(sn["D"]["est"]) < mk
    out["null_50"] = {"frac_absD_lt_m": hits / 50, "mean_D": float(np.mean(Ds)), "sd_D": float(np.std(Ds)),
                      "m_typical": m}
    # (c) planted slope: DiD_c = 0.5 * zEN(c)
    planted = {c: 0.5 * float(dt.loc[c, "zEN"]) for c in CAT_ORDER}
    Ys = simulate(cats, planted, rng)
    su = did_suite(Ys, cats, bs, list(LOW_EN), list(HIGH_EN))
    present = [c for c in CAT_ORDER if c in su["per_category"]]
    y = np.array([su["per_category"][c]["est"] for c in present])
    v = np.array([su["per_category"][c]["var"] for c in present])
    X = np.column_stack([np.ones(len(y)), dt.loc[present, "zEN"], dt.loc[present, "zSL"]])
    mr = meta_regression(y, v, X, ["intercept", "zEN", "zSL"])
    out["planted_zEN_slope_0.5"] = {"zEN": mr["coef"]["zEN"], "zSL": mr["coef"]["zSL"], "tau2": mr["tau2"],
                                    "covers": mr["coef"]["zEN"]["ci95_kh"][0] <= 0.5 <= mr["coef"]["zEN"]["ci95_kh"][1],
                                    "corr_zEN_zSL": float(np.corrcoef(dt.loc[present, "zEN"], dt.loc[present, "zSL"])[0, 1])}
    mr1 = meta_regression(y, v, X[:, :2], ["intercept", "zEN"])
    out["planted_zEN_slope_0.5"]["zEN_only_model"] = mr1["coef"]["zEN"]
    # repeat (c) 30 times to get recovery rates of the two-covariate and one-covariate models
    rec2 = rec1 = 0
    for k in range(30):
        Yk = simulate(cats, planted, np.random.default_rng(SEED + 5000 + k))
        sk = did_suite(Yk, cats, Bootstrap(cats, SEED + k, B=300), list(LOW_EN), list(HIGH_EN))
        yk = np.array([sk["per_category"][c]["est"] for c in present])
        vk = np.array([sk["per_category"][c]["var"] for c in present])
        a = meta_regression(yk, vk, X, ["i", "zEN", "zSL"])["coef"]["zEN"]["ci95_kh"]
        b = meta_regression(yk, vk, X[:, :2], ["i", "zEN"])["coef"]["zEN"]["ci95_kh"]
        rec2 += a[0] > 0
        rec1 += b[0] > 0
    out["planted_zEN_slope_0.5"]["power_zEN_ci_excludes_0_two_covariate"] = rec2 / 30
    out["planted_zEN_slope_0.5"]["power_zEN_ci_excludes_0_zEN_only"] = rec1 / 30
    (RES / "synthetic_T8.json").write_text(json.dumps(out, indent=2, default=float))
    logger.info(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
