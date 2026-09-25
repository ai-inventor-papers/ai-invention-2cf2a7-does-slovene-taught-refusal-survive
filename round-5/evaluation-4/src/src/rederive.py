#!/usr/bin/env python3
"""Independent second path (never imports analysis.py, stats_lib.py or common.py): re-derives the headline numbers
from the raw files with pandas and its own formulas, then compares them with results/*.json.
Tolerances: point estimates <= 1e-6; bootstrap CI endpoints <= 0.02 (own bootstrap with the same seed scheme)."""
from __future__ import annotations

import gzip
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RUNI4 = Path(__import__("os").environ.get("AII_DEPS_ROOT", str(Path(__file__).resolve().parents[4]))) / "round-4"
E14 = RUNI4 / "gen_art_experiment_14"
SEED = 20260925
B = 2000


def jl(p):
    p = Path(p)
    if not p.exists():
        return []
    with (gzip.open(p, "rt") if p.suffix == ".gz" else open(p)) as f:
        return [json.loads(x) for x in f if x.strip()]


def lg(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p) - np.log1p(-p)


def rate(k, n):
    return (k + 0.5) / (n + 1.0)


def kap(a, b):
    a, b = np.asarray(a), np.asarray(b)
    cats = sorted(set(a.tolist()) | set(b.tolist()))
    po = (a == b).mean()
    pe = sum((a == c).mean() * (b == c).mean() for c in cats)
    return float("nan") if pe >= 1 else float((po - pe) / (1 - pe))


def main() -> int:
    rows = pd.DataFrame(jl(E14 / "results/rows_final.jsonl"))
    srft = {r["jk"]: r["sr_ft"] for r in jl(ROOT / "labels/sr_ft.jsonl")}
    h = rows[(rows.kind == "harmful")].copy()
    h["R"] = (h.L_primary == "REFUSE").astype(float)
    h["U"] = [(srft.get(k + ("|en" if o == "en" else "|tr")) or np.nan) for k, o in zip(h.key, h.out_lang)]
    h.loc[h.U.notna(), "U"] = (h.loc[h.U.notna(), "U"] >= 0.5).astype(float)
    # U is NaN where SR_ft is missing
    h["U"] = [np.nan if (k + ("|en" if o == "en" else "|tr")) not in srft else float(srft[k + ("|en" if o == "en" else "|tr")] >= 0.5)
              for k, o in zip(h.key, h.out_lang)]
    gem = {}
    for r in jl(ROOT / "labels/sr_gemini_paid.jsonl"):
        if r.get("parsed"):
            gem[(r["key"], r["variant"])] = float(r["score"] >= 0.5)
    h["G"] = [gem.get((k, "orig"), np.nan) for k in h.key]
    items = sorted(h.item_id.unique())
    pos = {x: i for i, x in enumerate(items)}
    rng = np.random.default_rng(SEED)
    W = np.vstack([np.ones(len(items)), rng.multinomial(len(items), np.full(len(items), 1 / len(items)), size=B)])

    def cellvec(model, dose, i, o, col):
        d = h[(h.model == model) & (h.cond == "edit") & (h.dose == dose) & (h.in_lang == i) & (h.out_lang == o)]
        v = np.full(len(items), np.nan)
        for it, y in zip(d.item_id, d[col]):
            v[pos[it]] = y
        return v

    def L(model, dose, i, o, col, safe):
        v = cellvec(model, dose, i, o, col)
        m = np.isfinite(v)
        k, n = W @ np.where(m, v, 0), W @ m
        p = rate(k, n)
        return lg(1 - p) if safe else lg(p)

    mine = {}
    for col, safe, name in (("R", False, "R_J1"), ("U", True, "U_ft"), ("G", True, "U_orig")):
        if col in ("U", "G") and h[col].notna().sum() == 0:
            continue
        for m in ("gemma_it", "gams3_it"):
            for d in ("zero", "lo", "hi"):
                mine[f"{name}|OUT|{m}|{d}"] = L(m, d, "en", "sl", col, safe) - L(m, d, "en", "en", col, safe)
                mine[f"{name}|SLSL|{m}|{d}"] = L(m, d, "sl", "sl", col, safe) - L(m, d, "en", "en", col, safe)
            if True:
                for d in ("zero", "lo", "hi"):
                    pass
        for d in ("zero", "lo", "hi"):
            if name != "U_orig":
                mine[f"{name}|dOUT|{d}"] = mine[f"{name}|OUT|gams3_it|{d}"] - mine[f"{name}|OUT|gemma_it|{d}"]
                mine[f"{name}|IN|gemma_it|{d}"] = L("gemma_it", d, "sl", "en", col, safe) - L("gemma_it", d, "en", "en", col, safe)
        if name == "U_orig":
            mine["U_orig|dOUT|hi"] = mine["U_orig|OUT|gams3_it|hi"] - mine["U_orig|OUT|gemma_it|hi"]
    s1 = json.loads((ROOT / "results/step1_harmful_content.json").read_text())
    checks = []
    for k, arr in mine.items():
        ro, stat = k.split("|", 1)
        ref = s1["readouts"][ro]["contrasts"].get(stat)
        if ref is None or ref.get("est") is None:
            continue
        p_ok = abs(arr[0] - ref["est"]) <= 1e-6
        lo, hi = np.percentile(arr[1:][np.isfinite(arr[1:])], [2.5, 97.5])
        ci_ok = abs(lo - ref["ci95"][0]) <= 0.02 and abs(hi - ref["ci95"][1]) <= 0.02
        checks.append({"stat": k, "point_ref": ref["est"], "point_mine": float(arr[0]), "point_ok": bool(p_ok),
                       "ci_ref": ref["ci95"], "ci_mine": [float(lo), float(hi)], "ci_ok": bool(ci_ok)})
    # adjudication kappa A vs B (pooled)
    adj = pd.DataFrame([r for r in jl(ROOT / "labels/adjudication.jsonl") if r.get("label")])
    s2 = json.loads((ROOT / "results/step2_adjudication.json").read_text())
    if len(adj):
        last = adj.drop_duplicates(["key", "rater"], keep="last")
        piv = last.pivot(index="key", columns="rater", values="label")
        both = piv.dropna(subset=["A", "B"]) if {"A", "B"} <= set(piv.columns) else piv.iloc[0:0]
        frame = {r["key"] for r in jl(ROOT / "results/adj_frame.jsonl")}
        both = both[both.index.isin(frame)]
        if len(both):
            a = [int(x["class"] != "COMPLIANCE") for x in both.A]
            b = [int(x["class"] != "COMPLIANCE") for x in both.B]
            ref = s2["A_vs_B|pooled"]["R_any"]["kappa"]
            checks.append({"stat": "kappa_AB_pooled_R_any", "point_ref": ref, "point_mine": kap(a, b),
                           "point_ok": abs(kap(a, b) - ref) <= 1e-6, "ci_ok": True})
    # SDT DiD_c hi / zero (J1) point
    from scipy.stats import norm
    b_ = rows[(rows.cond == "edit")]
    def zr(m, d, i, o, kind):
        x = b_[(b_.model == m) & (b_.dose == d) & (b_.in_lang == i) & (b_.out_lang == o) & (b_.kind == kind)]
        return norm.ppf(rate((x.L_primary == "REFUSE").sum(), len(x)))
    sdt = json.loads((ROOT / "results/sdt.json").read_text())
    for d in ("zero", "hi"):
        per = {}
        for m in ("gemma_it", "gams3_it"):
            c1 = -(zr(m, d, "en", "sl", "harmful") + zr(m, d, "en", "sl", "benign")) / 2
            c0 = -(zr(m, d, "en", "en", "harmful") + zr(m, d, "en", "en", "benign")) / 2
            per[m] = c1 - c0
        mine_v = per["gemma_it"] - per["gams3_it"]
        ref = sdt["DiD"][f"{d}|SLoutput|c"]["DiD_gemma_minus_gams"]["est"]
        checks.append({"stat": f"SDT_DiD_c_{d}_SLoutput", "point_ref": ref, "point_mine": float(mine_v),
                       "point_ok": abs(mine_v - ref) <= 1e-6, "ci_ok": True})
    # benign zero-dose adjudicated rates (AM3)
    bz = json.loads((ROOT / "results/benign_zero_dose.json").read_text())
    if len(adj):
        fr = pd.DataFrame(jl(ROOT / "results/adj_frame.jsonl")).set_index("key")
        for c, v in bz["cells"].items():
            if not v.get("adj_R_any"):
                continue
            m, io = c.split("|")
            st = f"extra|benign0|{m}|{io}|zero"
            keys = fr.index[fr.stratum == st]
            vals = []
            for k in keys:
                if k in piv.index and isinstance(piv.loc[k].get("A"), dict) and isinstance(piv.loc[k].get("B"), dict):
                    a1 = int(piv.loc[k]["A"]["class"] != "COMPLIANCE")
                    b1 = int(piv.loc[k]["B"]["class"] != "COMPLIANCE")
                    if a1 == b1:
                        vals.append(a1)
                    elif "C" in piv.columns and isinstance(piv.loc[k].get("C"), dict):
                        c1 = int(piv.loc[k]["C"]["class"] != "COMPLIANCE")
                        vals.append(int(a1 + b1 + c1 >= 2))
            if vals:
                checks.append({"stat": f"benign0_adj_R_any_{c}", "point_ref": v["adj_R_any"]["rate"],
                               "point_mine": float(np.mean(vals)),
                               "point_ok": abs(np.mean(vals) - v["adj_R_any"]["rate"]) <= 1e-6, "ci_ok": True})
    npass = sum(c["point_ok"] and c["ci_ok"] for c in checks)
    out = {"n_checks": len(checks), "n_pass": npass, "all_pass": npass == len(checks), "checks": checks,
           "note": "independent pandas path; same seed/multinomial scheme for the item bootstrap"}
    (ROOT / "results/rederive.json").write_text(json.dumps(out, indent=1, default=float))
    print(f"rederive: {npass}/{len(checks)} checks pass")
    for c in checks:
        if not (c["point_ok"] and c["ci_ok"]):
            print("FAIL", c)
    return 0 if out["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
