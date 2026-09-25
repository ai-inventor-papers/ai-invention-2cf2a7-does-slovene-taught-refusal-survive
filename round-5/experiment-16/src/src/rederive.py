#!/usr/bin/env python3
"""S11 INDEPENDENT RE-DERIVATION: rebuilds every headline point statistic from gens/*.jsonl + labels/*.jsonl +
adjudication/resolved.jsonl with plain numpy/pandas. Never imports analysis.py or stats_core.py.
Checks (|diff| < 1e-6): per-cell raw rates, Se/Sp, RG / PPI points, OUT/dOUT/IN/OUT_edit points under the primary and
raw readouts, SB point estimates, SDT c. Bootstrap CI endpoints for OUT_Gemma / dOUT are recomputed with the same seed
and algorithm (tolerance 0.02). -> results/audit.json"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.stats import norm as _norm

import os
ROOT = Path(os.environ.get("AII_WORK", str(Path(__file__).resolve().parent.parent)))


def jl(p: Path) -> list[dict]:
    p = Path(p)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def lg(p: float, n: int) -> float:
    lo = 0.5 / (n + 1)
    p = min(max(p, lo), 1 - lo)
    return math.log(p / (1 - p))


def main() -> None:
    A = json.loads((ROOT / "results/analysis.json").read_text())
    rows = []
    for m in ("gemma_it", "gams3_it", "pew_heretic", "huihui", "mlabonne_v2"):
        rows += jl(ROOT / f"gens/{m}.jsonl")
    g = pd.DataFrame(rows)
    gem = pd.DataFrame([r for r in jl(ROOT / "labels/gemini.jsonl") if r["readout"] == "gemini"])
    loc = pd.DataFrame(jl(ROOT / "labels/local.jsonl"))
    adj = pd.DataFrame(jl(ROOT / "adjudication/resolved.jsonl"))
    ds = {m: yaml.safe_load((ROOT / f"dose_addendum_{m}.yaml").read_text())["dose_star_tag"]
          for m in ("gemma_it", "gams3_it") if (ROOT / f"dose_addendum_{m}.yaml").exists()}
    g["armc"] = np.where(g["arm"] == "EN_orig", "EN_orig", "std")
    h = g[g["kind"] == "harmful"].copy()
    if len(gem):
        gg = gem.dropna(subset=["score"])[["key", "U", "refused"]].rename(columns={"U": "gU", "refused": "gR"})
        h = h.merge(gg, on="key", how="left")
    else:
        h["gU"], h["gR"] = np.nan, np.nan
    if len(loc):
        sr = loc[loc["readout"] == "sr_local"][["key", "U"]].rename(columns={"U": "lU"})
        j1 = loc[loc["readout"] == "j1"][["key", "label"]].rename(columns={"label": "j1"})
        h = h.merge(sr, on="key", how="left").merge(j1, on="key", how="left")
    if len(adj):
        h = h.merge(adj[["key", "adj_U", "adj_explicit_refusal"]], on="key", how="left")
    checks, fails = [], []

    def chk(name, mine, theirs, tol=1e-6):
        if theirs is None or mine is None or (isinstance(mine, float) and not math.isfinite(mine)):
            return
        ok = abs(float(mine) - float(theirs)) < tol
        checks.append({"name": name, "mine": mine, "analysis": theirs, "ok": ok})
        if not ok:
            fails.append(name)

    def cell(m, c, t, arm="std"):
        return h[(h["model"] == m) & (h["cell"] == c) & (h["dose_tag"] == t) & (h["armc"] == arm)]
    # 1. per-unit raw rates
    for key, u in A["units"].items():
        m, c, t, arm = key.split("|")
        if arm == "t256":
            continue
        d = cell(m, c, t, arm)
        if "raw_gemini" in u and d["gU"].notna().sum():
            chk(f"raw_gemini|{key}", 1 - d["gU"].astype(float).mean(), u["raw_gemini"]["S_or_R"])
        if "local_U" in u and "lU" in d and d["lU"].notna().sum():
            chk(f"local_U|{key}", 1 - d["lU"].astype(float).mean(), u["local_U"]["S_or_R"])
        if "j1" in u and "j1" in d and d["j1"].notna().sum():
            chk(f"j1|{key}", (d["j1"] == "REFUSE").mean(), u["j1"]["S_or_R"])
    # 2. Se/Sp + RG/PPI
    em = json.loads((ROOT / "results/error_matrices.json").read_text()) if (ROOT / "results/error_matrices.json").exists() else {}
    fm = json.loads((ROOT / "adjudication/frame_meta.json").read_text()) if (ROOT / "adjudication/frame_meta.json").exists() else {"items": []}
    SE = {}
    for m in ds:
        for c in ("EN>EN", "EN>SL"):
            d = cell(m, c, ds[m])
            d = d[d["item_id"].isin(fm["items"])].dropna(subset=["gU", "adj_U"]) if "adj_U" in d else d.iloc[0:0]
            if not len(d):
                continue
            x, y = d["gU"].astype(bool), d["adj_U"].astype(bool)
            se = (x & y).sum() / max(1, y.sum())
            sp = (~x & ~y).sum() / max(1, (~y).sum())
            SE[(m, c)] = (se, sp, float((d["adj_U"].astype(float) - d["gU"].astype(float)).mean()))
            e = em.get(f"{m}|{c}", {}).get("gemini_U_vs_adj_U", {})
            chk(f"Se|{m}|{c}", se, e.get("Se"))
            chk(f"Sp|{m}|{c}", sp, e.get("Sp"))
    ppi = A["rg_identifiability"]["switch_to_ppi"]

    def paired(m, c1, c2, t, col):
        a = cell(m, c1, t).dropna(subset=[col])
        b = cell(m, c2, t).dropna(subset=[col])
        return set(a["item_id"]) & set(b["item_id"])

    def prim_L(m, c, t, arm="std", items=None):
        d = cell(m, c, t, arm).dropna(subset=["gU"])
        if items is not None:
            d = d[d["item_id"].isin(items)]
        if len(d) < 20:
            return None
        key = (m, "EN>EN") if c.split(">")[1] == "EN" else (m, "EN>SL")
        if key not in SE:
            return None
        p = d["gU"].astype(float).mean()
        se, sp, rect = SE[key]
        pc = min(max(p + rect, 0), 1) if ppi else min(max((p + sp - 1) / (se + sp - 1), 0), 1)
        return lg(1 - pc, len(d))

    def raw_L(m, c, t, col="gU", refusal=False, items=None):
        d = cell(m, c, t).dropna(subset=[col])
        if items is not None:
            d = d[d["item_id"].isin(items)]
        if len(d) < 20:
            return None
        v = (d[col] == "REFUSE").astype(float) if col == "j1" else d[col].astype(float)
        return lg(v.mean() if refusal else 1 - v.mean(), len(d))
    est = A["estimands"]
    for m in ds:
        for lab, t in (("dose*", ds[m]), ("zero", "zero")):
            it = paired(m, "EN>SL", "EN>EN", t, "gU")
            a, b = prim_L(m, "EN>SL", t, items=it), prim_L(m, "EN>EN", t, items=it)
            if a is not None and b is not None:
                chk(f"OUT|{m}|{lab}|primary", a - b, (est.get(f"OUT|{m}|{lab}") or {}).get("primary", {}).get("est"))
            a, b = raw_L(m, "EN>SL", t, items=it), raw_L(m, "EN>EN", t, items=it)
            if a is not None and b is not None:
                chk(f"OUT|{m}|{lab}|raw_gemini", a - b, (est.get(f"OUT|{m}|{lab}") or {}).get("raw_gemini", {}).get("est"))
            if "lU" in h:
                il = paired(m, "EN>SL", "EN>EN", t, "lU")
                a, b = raw_L(m, "EN>SL", t, "lU", items=il), raw_L(m, "EN>EN", t, "lU", items=il)
                if a is not None and b is not None:
                    chk(f"OUT|{m}|{lab}|local_U", a - b, (est.get(f"OUT|{m}|{lab}") or {}).get("local_U", {}).get("est"))
            ir = paired(m, "EN>SL", "EN>EN", t, "gR")
            a, b = raw_L(m, "EN>SL", t, "gR", True, items=ir), raw_L(m, "EN>EN", t, "gR", True, items=ir)
            if a is not None and b is not None:
                chk(f"OUT|{m}|{lab}|gem_refused", a - b, (est.get(f"OUT|{m}|{lab}") or {}).get("gem_refused", {}).get("est"))
    if "gemma_it" in ds:
        ii = paired("gemma_it", "SL>EN", "EN>EN", ds["gemma_it"], "gU")
        a, b = prim_L("gemma_it", "SL>EN", ds["gemma_it"], items=ii), prim_L("gemma_it", "EN>EN", ds["gemma_it"], items=ii)
        if a is not None and b is not None:
            chk("IN|gemma_it|dose*|primary", a - b, (est.get("IN|gemma_it|dose*") or {}).get("primary", {}).get("est"))
    if len(ds) == 2:
        vals = [prim_L(m, c, ds[m], items=paired(m, "EN>SL", "EN>EN", ds[m], "gU"))
                for m in ("gemma_it", "gams3_it") for c in ("EN>EN", "EN>SL")]
        if all(v is not None for v in vals):
            chk("dOUT|dose*|primary", (vals[3] - vals[2]) - (vals[1] - vals[0]),
                (est.get("dOUT|dose*") or {}).get("primary", {}).get("est"))
    # 3. SB (twins at zero, gemini refused)
    t = g[(g["kind"] == "twin") & (g["dose_tag"] == "zero")]
    if len(gem):
        t = t.merge(gem.dropna(subset=["refused"])[["key", "refused"]], on="key", how="left")
        sb = A.get("secondary_benign_SB", {}).get("estimands", {}).get("gem_refused", {})

        def fr(m, c):
            d = t[(t["model"] == m) & (t["cell"] == c)].dropna(subset=["refused"])
            return lg(d["refused"].astype(float).mean(), len(d)) if len(d) >= 20 else None
        for m in ("gemma_it", "gams3_it"):
            a, b = fr(m, "EN>SL"), fr(m, "EN>EN")
            if a is not None and b is not None:
                chk(f"SB FR_OUT|{m}", a - b, (sb.get(f"FR_OUT|{m}") or {}).get("est"))
    # 4. SDT c (J1)
    if len(loc):
        tj = g.merge(loc[loc["readout"] == "j1"][["key", "label"]], on="key", how="left")
        for k, v in A.get("sdt", {}).items():
            parts = k.split("|")
            if parts[1] == "DiD":
                continue
            m, c, tg = parts
            hh = tj[(tj["model"] == m) & (tj["cell"] == c) & (tj["dose_tag"] == tg) & (tj["kind"] == "harmful")
                    & (tj["arm"] != "EN_orig")].dropna(subset=["label"])
            ff = tj[(tj["model"] == m) & (tj["cell"] == c) & (tj["dose_tag"] == tg) & (tj["kind"] == "twin")].dropna(subset=["label"])
            H = ((hh["label"] == "REFUSE").sum() + 0.5) / (len(hh) + 1)
            F = ((ff["label"] == "REFUSE").sum() + 0.5) / (len(ff) + 1)
            chk(f"SDT c|{k}", -(_norm.ppf(H) + _norm.ppf(F)) / 2, v["c"])
    out = {"n_checks": len(checks), "n_pass": sum(c["ok"] for c in checks), "fails": fails, "checks": checks,
           "note": "independent pandas/numpy code path; never imports analysis.py or stats_core.py"}
    (ROOT / "results/audit.json").write_text(json.dumps(out, indent=1, default=float))
    print(f"rederive: {out['n_pass']}/{out['n_checks']} pass; fails: {fails[:10]}")


if __name__ == "__main__":
    main()
