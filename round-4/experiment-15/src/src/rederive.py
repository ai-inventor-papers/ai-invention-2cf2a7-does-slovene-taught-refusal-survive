#!/usr/bin/env python3
"""S11 AUDIT: independent re-derivation of the headline numbers from results/rows_final.jsonl.

Never imports analysis.py or stats_core.py. Uses pandas for the counting and statsmodels' IRLS binomial GLM (a different
optimiser from analysis.py's BFGS). Tolerances: closed-form quantities (rates, margins M0, G3_orig, RG-corrected rates,
SDT DiDs) 1e-6; GLM intercepts (G3, G3_edit) 1e-4 (optimiser tolerance). Writes results/audit.json.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import norm

from common import RESULTS, setup_logging

logger = setup_logging("rederive")
M = ["gemma_it", "gams3_it"]


def hz(k, n):
    return (k + 0.5) / (n + 1.0)


def lg(p):
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return np.log(p / (1 - p))


@logger.catch(reraise=True)
def main() -> None:
    A = json.loads((RESULTS / "analysis.json").read_text())
    df = pd.read_json(RESULTS / "rows_final.jsonl", lines=True)
    df = df[df["label_primary"].isin(["REFUSE", "PARTIAL", "COMPLY"])]
    df["y"] = (df["label_primary"] == "REFUSE").astype(float)
    df["lam"] = df["lambda"].round(4)
    body = df[(df["set"] == "BODY") & (df["edit"] == "E_exp9") & df["block"].isin(["ladder", "fillin"])
              & df["arm"].isin(["EN_BT", "SL_MT"])]
    checks, out = [], {}
    tab = body.groupby(["model", "lam", "arm"])["y"].agg(["sum", "count"]).reset_index()
    per = {}
    for m in M:
        t = tab[tab["model"] == m].pivot(index="lam", columns="arm", values=["sum", "count"])
        lam = t.index.values
        ke, ne = t[("sum", "EN_BT")].values, t[("count", "EN_BT")].values
        ks, ns = t[("sum", "SL_MT")].values, t[("count", "SL_MT")].values
        for s, l in enumerate(lam):
            a_row = [r for r in A["steps_R"][m] if abs(r["lambda"] - l) < 1e-6][0]
            checks.append(("rate_en", m, l, abs(a_row["p_en"] - ke[s] / ne[s]), 1e-6))
            checks.append(("rate_sl", m, l, abs(a_row["p_sl"] - ks[s] / ns[s]), 1e-6))
        f = lam > 0
        x = lg(hz(ke[f], ne[f]))
        glm = sm.GLM(np.column_stack([ks[f], ns[f] - ks[f]]), sm.add_constant(x), family=sm.families.Binomial()).fit(
            tol=1e-12, maxiter=200)
        z = np.where(lam == 0)[0][0]
        M0 = lg(hz(ks[z], ns[z])) - lg(hz(ke[z], ne[z]))
        per[m] = {"a": float(glm.params[0]), "b": float(glm.params[1]), "M0": float(M0)}
    G3 = per["gams3_it"]["a"] - per["gemma_it"]["a"]
    G3o = per["gams3_it"]["M0"] - per["gemma_it"]["M0"]
    raw = A["headline"]["R"]["RAW"]
    checks += [("G3", "", "", abs(G3 - raw["G3"]["point"]), 1e-4),
               ("G3_orig", "", "", abs(G3o - raw["G3_orig"]["point"]), 1e-6),
               ("G3_edit", "", "", abs((G3 - G3o) - raw["G3_edit"]["point"]), 1e-4)]
    for m in M:
        checks.append((f"b_{m}", "", "", abs(per[m]["b"] - A["headline"]["R"]["per_model"][m]["b"]["point"]), 1e-4))
    out["rederived"] = {"G3": G3, "G3_orig": G3o, "G3_edit": G3 - G3o, "per_model": per}
    # RG-corrected rates: re-derive Se/Sp per cell from adjudicated rows and compare the parameters
    adj = df[df["label_adjudication"].isin(["REFUSE", "PARTIAL", "COMPLY"])].copy()
    if len(adj) and "RG" in A["headline"]["R"]:
        adj["cell"] = adj["model"] + "|" + adj["lang"] + "|" + np.where((adj["lambda"] == 0) | (adj["edit"] == "none"),
                                                                        "orig", "edited")
        adj["j"] = adj["label_primary"] == "REFUSE"
        adj["g"] = adj["label_adjudication"] == "REFUSE"
        for c, g in adj.groupby("cell"):
            se = ((g.j & g.g).sum() + .5) / (g.g.sum() + 1)
            sp = ((~g.j & ~g.g).sum() + .5) / ((~g.g).sum() + 1)
            a_se, a_sp = A["headline"]["R"]["correction_params"]["RG_Se_Sp"][c]
            checks += [(f"RG_Se_{c}", "", "", abs(se - a_se), 1e-6), (f"RG_Sp_{c}", "", "", abs(sp - a_sp), 1e-6)]
    # SDT DiD at lambda 0 (R coding)
    sd = df[(df["edit"] == "E_exp9") & df["block"].isin(["ladder", "fillin"]) & df["set"].isin(["BODY", "TWIN"])
            & df["arm"].isin(["EN_BT", "SL_MT"]) & (df["lam"] == 0)]
    v = {}
    for m in M:
        for lang in ("en", "sl"):
            h = sd[(sd.model == m) & (sd.lang == lang) & (sd.set == "BODY")]["y"]
            fa = sd[(sd.model == m) & (sd.lang == lang) & (sd.set == "TWIN")]["y"]
            zh, zf = norm.ppf(hz(h.sum(), len(h))), norm.ppf(hz(fa.sum(), len(fa)))
            v[(m, lang)] = (zh - zf, (zh + zf) / 2)
    did_d = (v[("gams3_it", "sl")][0] - v[("gams3_it", "en")][0]) - (v[("gemma_it", "sl")][0] - v[("gemma_it", "en")][0])
    did_c = (v[("gams3_it", "sl")][1] - v[("gams3_it", "en")][1]) - (v[("gemma_it", "sl")][1] - v[("gemma_it", "en")][1])
    checks += [("SDT_DiD_dprime_lam0", "", "", abs(did_d - A["sdt"]["R"]["DiD_d_prime_lam0"]), 1e-6),
               ("SDT_DiD_c_lam0", "", "", abs(did_c - A["sdt"]["R"]["DiD_c_ref_lam0"]), 1e-6)]
    # independent model-swap placebo (300 permutations, own RNG): must centre at ~0
    rng = np.random.default_rng(99)
    piv = {m: body[body.model == m].pivot_table(index="item_id", columns=["arm", "lam"], values="y") for m in M}
    items = sorted(set(piv[M[0]].index) & set(piv[M[1]].index))
    ncom = min(len(piv[m].columns) // 2 for m in M)
    arr = {}
    for m in M:
        cols_en = [c for c in piv[m].columns if c[0] == "EN_BT"][:ncom]
        cols_sl = [c for c in piv[m].columns if c[0] == "SL_MT"][:ncom]
        arr[m] = (piv[m].loc[items, cols_en].values, piv[m].loc[items, cols_sl].values)

    def g3(E1, S1, E2, S2):
        aa = []
        for E, S in ((E1, S1), (E2, S2)):
            ke, ne = np.nansum(E, 0), (~np.isnan(E)).sum(0)
            ks, ns = np.nansum(S, 0), (~np.isnan(S)).sum(0)
            x = lg(hz(ke[1:], ne[1:]))
            aa.append(sm.GLM(np.column_stack([ks[1:], ns[1:] - ks[1:]]), sm.add_constant(x),
                             family=sm.families.Binomial()).fit().params[0])
        return aa[1] - aa[0]
    ps = []
    for _ in range(300):
        sw = (rng.random(len(items)) < 0.5)[:, None]
        (E1, S1), (E2, S2) = arr[M[0]], arr[M[1]]
        ps.append(g3(np.where(sw, E2, E1), np.where(sw, S2, S1), np.where(sw, E1, E2), np.where(sw, S1, S2)))
    out["placebo_model_swap_independent"] = {"mean": float(np.mean(ps)), "sd": float(np.std(ps)), "n": 300,
                                             "centred": bool(abs(np.mean(ps)) < 0.1 * np.std(ps) + 0.02)}
    out["checks"] = [{"what": c[0], "model": c[1], "lambda": c[2], "abs_diff": float(c[3]), "tol": c[4],
                      "pass": bool(c[3] <= c[4])} for c in checks]
    out["all_pass"] = all(c["pass"] for c in out["checks"]) and out["placebo_model_swap_independent"]["centred"]
    (RESULTS / "audit.json").write_text(json.dumps(out, indent=1, default=float))
    logger.info(f"audit: {sum(c['pass'] for c in out['checks'])}/{len(out['checks'])} checks pass; "
                f"placebo {out['placebo_model_swap_independent']}; all_pass={out['all_pass']}")


if __name__ == "__main__":
    main()
