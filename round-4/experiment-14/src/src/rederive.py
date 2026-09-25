#!/usr/bin/env python3
"""PHASE 6 audit: an INDEPENDENT code path (pure pandas/numpy; never imports analysis.py or stats_core) that recomputes
from results/rows_final.jsonl the point estimates of R, a, L*, OUT, IN, INT, G3, G3_edit, d'/c, Rogan-Gladen-corrected
OUT/IN (posterior-mean Se/Sp) and compares them to results/analysis.json (|diff| < 1e-6) -> results/audit.json."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parent.parent
import os
RES = Path(os.environ.get("AII_RESULTS_DIR", str(ROOT / "results")))


def main() -> None:
    df = pd.read_json(RES / "rows_final.jsonl", lines=True)
    A = json.loads((RES / "analysis.json").read_text())
    h = df[(df.kind == "harmful") & (df.cond == "edit") & df.L_primary.notna()].copy()
    h["R"] = (h.L_primary == "REFUSE").astype(float)
    g = h.groupby(["model", "dose", "in_lang", "out_lang"]).R.agg(["sum", "count"]).reset_index()
    g["lg"] = np.log(((g["sum"] + 0.5) / (g["count"] + 1)) / (1 - (g["sum"] + 0.5) / (g["count"] + 1)))
    Y = {(r.model, r.dose, r.in_lang, r.out_lang): r.lg for r in g.itertuples()}
    checks = []

    def chk(name, mine, theirs):
        if theirs is None or mine is None or not np.isfinite(mine):
            checks.append({"stat": name, "mine": mine, "analysis": theirs, "pass": None})
            return
        checks.append({"stat": name, "mine": float(mine), "analysis": float(theirs),
                       "pass": bool(abs(mine - theirs) < 1e-6)})
    raw = A["readouts"]["raw_R"]
    Ls = {}
    for m in ("gemma_it", "gams3_it"):
        if (m, "lo", "en", "en") not in Y:
            continue
        xl, xh, x0 = Y[(m, "lo", "en", "en")], Y[(m, "hi", "en", "en")], Y[(m, "zero", "en", "en")]
        for i in ("en", "sl", "hu"):
            for o in ("en", "sl", "hu"):
                if (m, "lo", i, o) not in Y:
                    continue
                yl, yh, y0 = Y[(m, "lo", i, o)], Y[(m, "hi", i, o)], Y[(m, "zero", i, o)]
                t = -xl / (xh - xl)
                a = yl + t * (yh - yl)
                Ls[(m, i, o)] = (a, a - (y0 - x0))
                chk(f"a|{m}|{i}{o}", a, raw.get(f"a|{m}|{i}{o}", {}).get("est"))
                chk(f"Lstar|{m}|{i}{o}", a - (y0 - x0), raw.get(f"Lstar|{m}|{i}{o}", {}).get("est"))
        for L3 in ("sl", "hu"):
            try:
                f = lambda i, o: Ls[(m, i, o)][1]  # noqa: E731
                OUT = ((f("en", L3) - f("en", "en")) + (f(L3, L3) - f(L3, "en"))) / 2
                IN = ((f(L3, "en") - f("en", "en")) + (f(L3, L3) - f("en", L3))) / 2
                INT = f(L3, L3) - f(L3, "en") - f("en", L3) + f("en", "en")
            except KeyError:
                continue
            for nm, v in (("OUT", OUT), ("IN", IN), ("INT", INT)):
                chk(f"{nm}_{L3.upper()}|{m}", v, raw.get(f"{nm}_{L3.upper()}|{m}", {}).get("est"))
    for i in ("en", "sl", "hu"):
        for o in ("en", "sl", "hu"):
            if ("gemma_it", i, o) in Ls and ("gams3_it", i, o) in Ls:
                chk(f"G3|{i}{o}", Ls[("gams3_it", i, o)][0] - Ls[("gemma_it", i, o)][0], raw.get(f"G3|{i}{o}", {}).get("est"))
                chk(f"G3edit|{i}{o}", Ls[("gams3_it", i, o)][1] - Ls[("gemma_it", i, o)][1],
                    raw.get(f"G3edit|{i}{o}", {}).get("est"))
    # SDT d' / c
    b = df[(df.kind == "benign") & (df.cond == "edit") & df.L_primary.notna()].copy()
    b["R"] = (b.L_primary == "REFUSE").astype(float)
    gb = b.groupby(["model", "dose", "in_lang", "out_lang"]).R.agg(["sum", "count"])
    gh = h.groupby(["model", "dose", "in_lang", "out_lang"]).R.agg(["sum", "count"])
    for key, v in A["sdt"]["cells"].items():
        m, d, io = key.split("|")
        k = (m, d, io[:2], io[2:])
        if k in gb.index and k in gh.index:
            H = (gh.loc[k, "sum"] + .5) / (gh.loc[k, "count"] + 1)
            F = (gb.loc[k, "sum"] + .5) / (gb.loc[k, "count"] + 1)
            chk(f"dprime|{key}", norm.ppf(H) - norm.ppf(F), v["d'"])
            chk(f"c|{key}", -0.5 * (norm.ppf(H) + norm.ppf(F)), v["c"])
    # Rogan-Gladen point OUT/IN (posterior-mean Se/Sp per judge cell)
    if "rg_parameters" in A and "rg_R" in A["readouts"]:
        par = A["rg_parameters"]
        Yr = {}
        for r in g.itertuples():
            c = f"{r.model}|{r.out_lang}|{'edited' if r.dose in ('lo', 'hi') else r.dose}"
            p_ = par.get(c, par["_pooled"])
            se = (1 + p_["tp"]) / (2 + p_["tp"] + p_["fn"])
            sp = (1 + p_["tn"]) / (2 + p_["tn"] + p_["fp"])
            p = r[5] / r[6]  # itertuples: (Index, model, dose, in, out, sum, count, lg)
            q = np.clip((p + sp - 1) / (se + sp - 1), 0.001, 0.999) if se + sp - 1 > 0.05 else np.nan
            Yr[(r.model, r.dose, r.in_lang, r.out_lang)] = np.log(q / (1 - q))
        for m in ("gemma_it", "gams3_it"):
            try:
                xl, xh, x0 = Yr[(m, "lo", "en", "en")], Yr[(m, "hi", "en", "en")], Yr[(m, "zero", "en", "en")]
                Lr = {}
                for i in ("en", "sl"):
                    for o in ("en", "sl"):
                        yl, yh, y0 = Yr[(m, "lo", i, o)], Yr[(m, "hi", i, o)], Yr[(m, "zero", i, o)]
                        a = yl + (-xl / (xh - xl)) * (yh - yl)
                        Lr[(i, o)] = a - (y0 - x0)
                OUT = ((Lr[("en", "sl")] - Lr[("en", "en")]) + (Lr[("sl", "sl")] - Lr[("sl", "en")])) / 2
                IN = ((Lr[("sl", "en")] - Lr[("en", "en")]) + (Lr[("sl", "sl")] - Lr[("en", "sl")])) / 2
                chk(f"RG OUT_SL|{m}", OUT, A["readouts"]["rg_R"].get(f"OUT_SL|{m}", {}).get("est"))
                chk(f"RG IN_SL|{m}", IN, A["readouts"]["rg_R"].get(f"IN_SL|{m}", {}).get("est"))
            except KeyError:
                continue
    # placebo means should centre at 0
    plc = {k: v for k, v in A.get("placebos", {}).items()}
    pl_ok = {k: abs(v["null_mean"]) < 0.1 for k, v in plc.items()}
    out = {"n_checks": len(checks), "n_pass": sum(c["pass"] is True for c in checks),
           "n_fail": sum(c["pass"] is False for c in checks), "all_pass": all(c["pass"] is not False for c in checks),
           "placebo_null_means_below_0.1": pl_ok, "checks": checks}
    (RES / "audit.json").write_text(json.dumps(out, indent=1))
    print(f"audit: {out['n_pass']}/{out['n_checks']} pass, {out['n_fail']} fail; placebos centred: {all(pl_ok.values())}")


if __name__ == "__main__":
    main()
