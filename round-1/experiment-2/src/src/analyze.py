#!/usr/bin/env python3
"""P8 analysis (CPU only; reads saved files). S1 base separability, S2 instruct descriptives, S3 item-level
regression (ALT-2b), S4 C4 induction (4PL alpha50, bootstrap, flip thresholds), S5 selection rule.
Writes results/analysis/analysis.json (+ per-cell tables)."""
from __future__ import annotations

import json
import math
import multiprocessing as mp
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from loguru import logger
from scipy.optimize import least_squares
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/analysis"
SEED = 20260923
NB = 2000
LOW_EN = {"S5", "S7", "S8", "S13"}
HIGH_EN = {"S2", "S3", "S4", "S9", "S10", "S11", "S14"}
LN15 = math.log(1.5)
CATS = [f"S{i}" for i in range(1, 15)]


def rj(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def dprime(a, b) -> float:
    return float((np.mean(a) - np.mean(b)) / np.sqrt((np.var(a, ddof=1) + np.var(b, ddof=1)) / 2))


def hautus_logit(k, n):
    p = (k + 0.5) / (n + 1)
    return math.log(p / (1 - p))


def ci(a) -> list:
    a = np.asarray([x for x in a if x is not None and np.isfinite(x)])
    if len(a) == 0:
        return [None, None]
    return [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]


# =============================================================================== S1
def s1_base(tag: str = "") -> dict:
    res = {}
    P = {}
    for m in ["pt", "gb"]:
        rows = rj(ROOT / f"results/base_{m}{tag}/item_proj.jsonl")
        if not rows or not (ROOT / f"results/base_{m}{tag}/layer_stats.json").exists():
            return {"status": "missing base results"}
        P[m] = rows
        res[f"layer_stats_{m}"] = json.loads((ROOT / f"results/base_{m}{tag}/layer_stats.json").read_text())
    L_pt = res["layer_stats_pt"]["L_pt"]

    def table(m, lname, direc):
        d = defaultdict(dict)
        for r in P[m]:
            if r["layer_name"] == lname and r["dir"] == direc:
                d[(r["kind"], r["lang"])][r["item"]] = r["proj"]
        return d

    out = {"L_pt": L_pt, "L_gb": res["layer_stats_gb"]["L_own"]}
    rng = np.random.default_rng(SEED)
    for lname in ["Lpt", "Lown"]:
        T = {m: table(m, lname, "pooled") for m in ["pt", "gb"]}
        harm_items = sorted(T["pt"][("harm", "en")])
        hl_items = sorted(T["pt"][("harmless", "en")])
        A = {(m, k, la): np.array([T[m][(k, la)][i] for i in (harm_items if k == "harm" else hl_items)])
             for m in ["pt", "gb"] for k in ["harm", "harmless"] for la in ["en", "sl"]}

        def stats(ih, ib):
            d = {(m, la): dprime(A[(m, "harm", la)][ih], A[(m, "harmless", la)][ib]) for m in ["pt", "gb"] for la in ["en", "sl"]}
            return {"dSL": d[("gb", "sl")] - d[("pt", "sl")], "dEN": d[("gb", "en")] - d[("pt", "en")],
                    "did": (d[("gb", "sl")] - d[("gb", "en")]) - (d[("pt", "sl")] - d[("pt", "en")]), "d": d}
        full = stats(np.arange(len(harm_items)), np.arange(len(hl_items)))
        boots = [stats(rng.integers(0, len(harm_items), len(harm_items)), rng.integers(0, len(hl_items), len(hl_items)))
                 for _ in range(NB)]
        out[lname] = {"dprime": {f"{m}_{la}": v for (m, la), v in full["d"].items()},
                      "Delta_dprime_SL": full["dSL"], "Delta_dprime_SL_ci": ci([b["dSL"] for b in boots]),
                      "Delta_dprime_EN": full["dEN"], "Delta_dprime_EN_ci": ci([b["dEN"] for b in boots]),
                      "DiD_dprime": full["did"], "DiD_dprime_ci": ci([b["did"] for b in boots]),
                      "dprime_ci": {f"{m}_{la}": ci([b["d"][(m, la)] for b in boots]) for m in ["pt", "gb"] for la in ["en", "sl"]}}
    # cosines between pt and gb directions per layer
    dp, dg = np.load(ROOT / f"results/base_pt{tag}/directions.npz"), np.load(ROOT / f"results/base_gb{tag}/directions.npz")
    out["cos_pt_gb_pooled_by_layer"] = [float(x) for x in (dp["unit_pooled"] * dg["unit_pooled"]).sum(1)]
    out["cos_pt_gb_at_Lpt"] = out["cos_pt_gb_pooled_by_layer"][L_pt]
    out["probes"] = {m: res[f"layer_stats_{m}"]["probes"] for m in ["pt", "gb"]}
    out["style_check"] = {m: res[f"layer_stats_{m}"]["style_check_at_Lpt"] for m in ["pt", "gb"]}
    out["per_layer"] = {m: res[f"layer_stats_{m}"]["per_layer"] for m in ["pt", "gb"]}
    out["crossfit"] = {m: res[f"layer_stats_{m}"]["crossfit"] for m in ["pt", "gb"]}
    return out


# =============================================================================== S2
def load_instruct():
    S, R4, RC = {}, {}, {}
    for m in ["gemma", "gams"]:
        S[m] = rj(ROOT / f"results/inst_{m}/s_score.jsonl")
        R4[m] = rj(ROOT / f"results/inst_{m}/r_score400.jsonl")
        RC[m] = rj(ROOT / f"results/inst_{m}/r_construct100.jsonl")
    return S, R4, RC


def judge_labels() -> dict:
    lab = {}
    for r in rj(ROOT / "results/shared/judge_labels.jsonl"):
        lab[r["key"]] = r
    return lab


def s2_instruct(S, R4, judge, rkey: str = "R_lex") -> dict:
    out = {}
    s_map = {m: {(r["item"], r["lang"]): r["s"] for r in S[m] if r["kind"] == "harm"} for m in S}
    hmean = {m: {la: float(np.mean([r["s"] for r in S[m] if r["kind"] == "harmless" and r["lang"] == la])) for la in ["en", "sl"]} for m in S}
    out["s_harmless_mean"] = hmean
    items = sorted({r["pair_id"] for r in R4["gemma"]} & {r["pair_id"] for r in R4["gams"]})
    cat = {r["pair_id"]: r["category"] for r in R4["gemma"]}
    Rm = {(m, r["pair_id"], r["lang"]): r[rkey] for m in R4 for r in R4[m]}
    cells = {}
    for m in ["gemma", "gams"]:
        for la in ["en", "sl"]:
            R = np.array([Rm[(m, i, la)] for i in items])
            s = np.array([s_map[m].get((i, la), np.nan) for i in items])
            ok = np.isfinite(s)
            au = None
            if min(R[ok].sum(), (1 - R[ok]).sum()) >= 10:
                au = float(roc_auc_score(R[ok], s[ok]))
            cells[f"{m}_{la}"] = {"n": int(len(R)), "R": float(R.mean()), "hautus_logit": hautus_logit(R.sum(), len(R)),
                                  "s_mean": float(np.nanmean(s)), "s_c_mean": float(np.nanmean(s) - hmean[m][la]),
                                  "auroc_s_R": au, "auroc_valid": (au is not None and au >= 0.85),
                                  "minority_n": int(min(R.sum(), len(R) - R.sum())), "ceiling": bool(R.mean() > 0.95)}
    out["cells"] = cells
    rng = np.random.default_rng(SEED)
    idx = np.arange(len(items))
    catarr = np.array([cat[i] for i in items])

    def did_stats(ii):
        res = {}
        for sub, mask in [("all", np.ones(len(items), bool)), ("lowEN", np.isin(catarr, list(LOW_EN))),
                          ("highEN", np.isin(catarr, list(HIGH_EN)))]:
            sel = ii[mask[ii]]
            lg = {}
            sm = {}
            for m in ["gemma", "gams"]:
                for la in ["en", "sl"]:
                    Rv = np.array([Rm[(m, items[j], la)] for j in sel])
                    lg[(m, la)] = hautus_logit(Rv.sum(), len(Rv))
                    sm[(m, la)] = np.nanmean([s_map[m].get((items[j], la), np.nan) for j in sel])
            res[sub] = {"did_R": (lg[("gams", "sl")] - lg[("gams", "en")]) - (lg[("gemma", "sl")] - lg[("gemma", "en")]),
                        "did_s": (sm[("gams", "sl")] - sm[("gams", "en")]) - (sm[("gemma", "sl")] - sm[("gemma", "en")])}
        res["D_R"] = res["lowEN"]["did_R"] - res["highEN"]["did_R"]
        res["D_s"] = res["lowEN"]["did_s"] - res["highEN"]["did_s"]
        return res
    full = did_stats(idx)
    boots = [did_stats(rng.integers(0, len(items), len(items))) for _ in range(NB)]
    out["DiD"] = {f"{sub}_{k}": {"est": full[sub][k], "ci": ci([b[sub][k] for b in boots])}
                  for sub in ["all", "lowEN", "highEN"] for k in ["did_R", "did_s"]}
    out["D"] = {k: {"est": full[k], "ci": ci([b[k] for b in boots])} for k in ["D_R", "D_s"]}
    out["label"] = "secondary; the MAIN/ALT-1 screen is authoritative"
    out["ceiling_rule_triggered"] = any(c["ceiling"] for c in cells.values())
    return out


# =============================================================================== S3
def ols_r2adj(X, y):
    Xc = np.column_stack([np.ones(len(y)), X])
    b, *_ = np.linalg.lstsq(Xc, y, rcond=None)
    resid = y - Xc @ b
    r2 = 1 - resid @ resid / ((y - y.mean()) @ (y - y.mean()))
    n, p = len(y), X.shape[1]
    return 1 - (1 - r2) * (n - 1) / (n - p - 1), b, r2


def cv_r2(X, y, k=5):
    rng = np.random.default_rng(SEED)
    f = rng.permutation(len(y)) % k
    pred = np.zeros(len(y))
    for i in range(k):
        tr, te = f != i, f == i
        Xc = np.column_stack([np.ones(tr.sum()), X[tr]])
        b, *_ = np.linalg.lstsq(Xc, y[tr], rcond=None)
        pred[te] = np.column_stack([np.ones(te.sum()), X[te]]) @ b
    return float(1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum())


def s3_regression(S, s1) -> dict:
    Lz = {}
    for m in ["pt", "gb"]:
        for r in rj(ROOT / f"results/base_{m}/item_proj.jsonl"):
            if r["layer_name"] == "Lpt" and r["dir"] == "pooled" and r["kind"] == "harm":
                Lz[(m, r["item"], r["lang"])] = r["harm_z"]
    s_map = {m: {(r["item"], r["lang"]): r["s"] for r in S[m] if r["kind"] == "harm"} for m in S}
    hmean = {m: {la: np.mean([r["s"] for r in S[m] if r["kind"] == "harmless" and r["lang"] == la]) for la in ["en", "sl"]} for m in S}
    cat = {r["item"]: r["category"] for r in S["gemma"] if r["kind"] == "harm"}
    items = sorted(i for i in cat if all((m, i, la) in s_map[m] or (i, la) in s_map[m] for m in ["gemma", "gams"] for la in ["en", "sl"])
                   and all((m, i, la) in Lz for m in ["pt", "gb"] for la in ["en", "sl"]))
    dose = {r["cat"]: (r["en_est_safety_refusals"], r["sl_est_safety_refusals_incl_safe05"])
            for r in json.loads((ROOT / "data/dose_table_stage0b.json").read_text())["per_category_dose"]}
    y = np.array([(s_map["gams"][(i, "sl")] - s_map["gams"][(i, "en")]) - (s_map["gemma"][(i, "sl")] - s_map["gemma"][(i, "en")]) for i in items])
    shift = (hmean["gams"]["sl"] - hmean["gams"]["en"]) - (hmean["gemma"]["sl"] - hmean["gemma"]["en"])
    y_c = y - shift
    G4 = np.array([[Lz[("gb", i, "sl")], Lz[("gb", i, "en")], Lz[("pt", i, "sl")], Lz[("pt", i, "en")]] for i in items])
    G4s = (G4 - G4.mean(0)) / G4.std(0)
    g = (G4[:, 0] - G4[:, 1]) - (G4[:, 2] - G4[:, 3])
    cats = np.array([cat[i] for i in items])
    Dd = np.array([[math.log2(dose[c][0] + 1), math.log2(dose[c][1] + 1)] for c in cats])
    present = sorted(set(cats), key=lambda c: int(c[1:]))
    FE = np.column_stack([(cats == c).astype(float) for c in present[1:]])

    def fit_all(yv, ii):
        Gi, Di, Fi, yi = G4s[ii], Dd[ii], FE[ii], yv[ii]
        rg, bg, _ = ols_r2adj(Gi, yi)
        rd, _, _ = ols_r2adj(Di, yi)
        rgd, bgd, _ = ols_r2adj(np.column_stack([Gi, Di]), yi)
        rf, _, _ = ols_r2adj(np.column_stack([Gi, Fi]), yi)
        rfe, _, _ = ols_r2adj(Fi, yi)
        share = rg / rf if rf > 0 else np.nan
        inc = (rgd - rg) / rf if rf > 0 else np.nan
        return {"R2adj_g": rg, "R2adj_d": rd, "R2adj_gd": rgd, "R2adj_fullcat": rf, "R2adj_catonly": rfe,
                "geometry_share": share, "dose_increment": inc, "b_gd": bgd.tolist()}
    out = {"n_items": len(items), "categories_present": present, "y_mean": float(y.mean()), "y_c_mean": float(y_c.mean()),
           "note_s_c": "s_c differs from s by a constant per model x lang, so y_c = y - const: all R^2 quantities are identical; only mean effects differ."}
    rng = np.random.default_rng(SEED)
    for name, yv in [("s", y), ("s_c", y_c)]:
        full = fit_all(yv, np.arange(len(items)))
        full["cv_R2_g"] = cv_r2(G4s, yv)
        full["cv_R2_gd"] = cv_r2(np.column_stack([G4s, Dd]), yv)
        full["cv_R2_fullcat"] = cv_r2(np.column_stack([G4s, FE]), yv)
        # partial R2 of each block given the other
        _, _, r2_g = ols_r2adj(G4s, yv)
        _, _, r2_d = ols_r2adj(Dd, yv)
        _, _, r2_gd = ols_r2adj(np.column_stack([G4s, Dd]), yv)
        full["partial_R2_geometry_given_dose"] = float((r2_gd - r2_d) / (1 - r2_d))
        full["partial_R2_dose_given_geometry"] = float((r2_gd - r2_g) / (1 - r2_g))
        # mediated share via scalar contrast g
        Xc = np.column_stack([np.ones(len(g)), g])
        bg_, *_ = np.linalg.lstsq(Xc, yv, rcond=None)
        boots = []
        med_b = []
        for _ in range(NB):
            ii = rng.integers(0, len(items), len(items))
            boots.append(fit_all(yv, ii))
            b2, *_ = np.linalg.lstsq(np.column_stack([np.ones(len(ii)), g[ii]]), yv[ii], rcond=None)
            med_b.append(b2[1] * g[ii].mean() / yv[ii].mean() if abs(yv[ii].mean()) > 1e-9 else np.nan)
        se_mean = float(np.std([yv[rng.integers(0, len(yv), len(yv))].mean() for _ in range(500)]))
        med = float(bg_[1] * g.mean() / yv.mean()) if abs(yv.mean()) > se_mean else None
        for k in ["geometry_share", "dose_increment", "R2adj_fullcat", "R2adj_g", "R2adj_gd"]:
            full[f"{k}_ci"] = ci([b[k] for b in boots])
        sh = np.array([b["geometry_share"] for b in boots], float)
        sh = sh[np.isfinite(sh)]
        full["geometry_share_se"] = float(np.std(sh)) if len(sh) else None
        full["z_c"] = float((full["geometry_share"] - 0.5) / full["geometry_share_se"]) if full["geometry_share_se"] else None
        full["b_g_scalar"] = float(bg_[1])
        full["mediated_share"] = med
        full["mediated_share_ci"] = ci(med_b) if med is not None else None
        full["mean_y_se"] = se_mean
        full["not_identifiable"] = bool(full["R2adj_fullcat"] < 0.02)
        out[name] = full
    # wild cluster bootstrap (WCR, Rademacher, clusters = categories) for dose coefficients in M_gd (y = s)
    Xr = np.column_stack([np.ones(len(y)), G4s])
    Xu = np.column_stack([Xr, Dd])
    br, *_ = np.linalg.lstsq(Xr, y, rcond=None)
    ur = y - Xr @ br
    bu, *_ = np.linalg.lstsq(Xu, y, rcond=None)
    cl = np.array([present.index(c) for c in cats])
    XtXi = np.linalg.pinv(Xu.T @ Xu)

    def cr_t(yv):
        b, *_ = np.linalg.lstsq(Xu, yv, rcond=None)
        e = yv - Xu @ b
        meat = np.zeros((Xu.shape[1], Xu.shape[1]))
        for c in range(len(present)):
            sc = Xu[cl == c].T @ e[cl == c]
            meat += np.outer(sc, sc)
        V = XtXi @ meat @ XtXi
        return b[-2:] / np.sqrt(np.diag(V)[-2:]), b[-2:]
    t0, b0 = cr_t(y)
    rng2 = np.random.default_rng(SEED)
    tb = []
    for _ in range(999):
        w = rng2.choice([-1.0, 1.0], len(present))[cl]
        tb.append(cr_t(Xr @ br + w * ur)[0])
    tb = np.array(tb)
    out["wild_cluster_dose"] = {"coef_log2EN": float(b0[0]), "coef_log2SL": float(b0[1]), "t": t0.tolist(),
                                "p_wcr": [float(np.mean(np.abs(tb[:, j]) >= abs(t0[j]))) for j in range(2)],
                                "n_clusters": len(present), "draws": 999}
    # per-category mean DiD vs dose
    out["per_category"] = [{"cat": c, "n": int((cats == c).sum()), "mean_y": float(y[cats == c].mean()),
                            "mean_g": float(g[cats == c].mean()), "dose_en": dose[c][0], "dose_sl": dose[c][1]} for c in present]
    out["corr_y_g"] = float(np.corrcoef(y, g)[0, 1])
    out["_arrays"] = {"y": y.tolist(), "g": g.tolist(), "cats": cats.tolist()}
    return out


# =============================================================================== S4
def f4(x, b, t, h, lc):
    return b + (t - b) / (1 + np.exp(-h * (x - lc)))


def fit4pl(lx, R, n, lo, hi):
    """Weighted LS 4PL on ln(alpha). Returns (b,t,h,lc) or None."""
    best = None
    w = np.sqrt(np.maximum(n, 1))
    for h0 in [1.0, 3.0, 8.0]:
        for lc0 in np.linspace(lo, hi, 4):
            x0 = [min(max(R[0], 0.0), 1.0), min(max(R[-1], 0.0), 1.0), h0, lc0]
            x0 = [np.clip(x0[0], 0, 1), np.clip(x0[1], 0, 1), h0, np.clip(lc0, lo - 2, hi + 2)]
            try:
                r = least_squares(lambda p: w * (f4(lx, *p) - R), x0, bounds=([0, 0, 0.3, lo - 2], [1, 1, 15, hi + 2]))
            except ValueError:
                continue
            if best is None or r.cost < best.cost:
                best = r
    return None if best is None else best.x


def alpha50(p, a_lo, a_hi):
    if p is None:
        return None, "fit_failed"
    b, t, h, lc = p
    lo_top, hi_top = min(b, t), max(b, t)
    if hi_top < 0.5:
        return None, "NR"
    if lo_top > 0.5:
        return None, "above_0.5_everywhere"
    if t < b:
        return None, "decreasing"
    x = lc + math.log((t - b) / (0.5 - b) - 1) / h if 0.5 > b else lc
    a = math.exp(x)
    if not (a_lo / 2 <= a <= 2 * a_hi):
        return None, "NR_out_of_range"
    return a, "ok"


PRE_ONLY = False  # sensitivity switch: restrict fits to the pre-registered k = 0..11


def cell_curve(recs: list[dict], hids: list[str] | None, alphas_abs: dict, rkey="R_lex"):
    """Aggregate R per alpha_k for given hid multiset; alphas_abs maps k -> absolute alpha (k=-1 is alpha 0, excluded)."""
    by = defaultdict(list)
    for r in recs:
        by[(r["alpha_k"], r["hid"])].append(r)
    ks = sorted({r["alpha_k"] for r in recs if r["alpha_k"] != -1 and (not PRE_ONLY or r["alpha_k"] >= 0)},
                key=lambda k: alphas_abs[k])
    R, n, deg = [], [], []
    for k in ks:
        vals, dg = [], []
        for h in hids:
            for r in by.get((k, h), []):
                vals.append(r[rkey]); dg.append(r["degenerate"])
        R.append(np.mean(vals) if vals else np.nan); n.append(len(vals)); deg.append(np.mean(dg) if dg else np.nan)
    return np.array(ks), np.array(R), np.array(n), np.array(deg)


def fit_cell(recs, hids, alphas_abs, rkey="R_lex"):
    ks, R, n, deg = cell_curve(recs, hids, alphas_abs, rkey)
    if len(ks) == 0:
        return {"status": "no_data"}
    keep = (deg <= 0.5) & np.isfinite(R)
    # D15 (post hoc, declared before the GaMS induction was analysed): the curves are inverted-U (refusal rises, then
    # collapses into off-manifold text at large alpha). A monotone 4PL cannot represent the falling limb, so fits use
    # the rising limb only: alphas up to the first alpha at which R is within 0.02 of its maximum.
    Rk = np.where(keep, R, -1)
    peak = int(np.argmax(Rk >= Rk.max() - 0.02)) if keep.any() else len(R) - 1
    after_peak = np.arange(len(R)) > peak
    keep = keep & ~after_peak
    trunc = int((~keep).sum())
    av = np.array([alphas_abs[k] for k in ks])
    lx = np.log(av)
    lo, hi = float(lx[0]), float(lx[-1])
    # model-free crossing on the rising limb
    emp = None
    idx_k = np.where(keep)[0]
    for a_, b_ in zip(idx_k[:-1], idx_k[1:]):
        if R[a_] < 0.5 <= R[b_]:
            emp = float(np.exp(lx[a_] + (0.5 - R[a_]) * (lx[b_] - lx[a_]) / (R[b_] - R[a_])))
            break
    if emp is None and len(idx_k) and R[idx_k[0]] >= 0.5:
        emp = "below_range"
    peak_R = float(np.nanmax(np.where(np.isfinite(R) & (deg <= 0.5), R, np.nan))) if np.any(np.isfinite(R) & (deg <= 0.5)) else 0.0
    base = {"ks": ks.tolist(), "R": [float(x) for x in R], "n": n.tolist(), "deg": [float(x) for x in deg],
            "a50_interp": emp, "peak_R": peak_R, "peak_k": int(ks[peak])}
    if peak_R < 0.5:  # never reaches 0.5 on non-degenerate alphas -> NR regardless of any extrapolated fit
        return {**base, "status": "NR", "a50": None, "rel_ec50": None, "params": None, "truncated_alphas": trunc,
                "deg_at_a50": None, "incoherence_confounded": False}
    if keep.sum() < 4:
        return {**base, "status": "too_few_alphas_interp_only", "a50": emp if isinstance(emp, float) else None,
                "rel_ec50": None, "params": None, "truncated_alphas": trunc, "deg_at_a50": None, "incoherence_confounded": False}
    p = fit4pl(lx[keep], R[keep], n[keep], lo, hi)
    a50, st = alpha50(p, av[0], av[peak])
    rel = None
    if p is not None and p[1] > p[0]:
        rel = float(math.exp(p[3]))
    deg_at = None
    if a50 is not None:
        j = int(np.argmin(np.abs(lx - math.log(a50))))
        deg_at = float(deg[j])
    return {**base, "status": st, "a50": a50, "rel_ec50": rel, "params": None if p is None else [float(x) for x in p],
            "truncated_alphas": trunc, "deg_at_a50": deg_at,
            "incoherence_confounded": bool(deg_at is not None and deg_at > 0.2)}


def _boot_worker(args):
    wid, nboot, recs_by, hids, alphas_by_model, cellkeys, rkey = args
    rng = np.random.default_rng(SEED + wid)
    res = []
    for _ in range(nboot):
        hs = list(rng.choice(hids, len(hids), replace=True))
        one = {}
        for ck in cellkeys:
            m = ck[0]
            f = fit_cell(recs_by[ck], hs, alphas_by_model[m], rkey)
            one["|".join(ck)] = f.get("a50")
        res.append(one)
    return res


def judge_refuse_map() -> dict:
    """key -> 1/0 judge refusal (refuse and not incoherent)"""
    return {r["key"]: int(r["label"] == "refuse" and not r["incoherent"]) for r in rj(ROOT / "results/shared/judge_labels.jsonl")}


def s4_induction(workers: int = 16, rkey: str = "R_lex", only_dirs: set | None = None, nboot: int = NB) -> dict:
    out = {"readout": rkey}
    recs = {m: rj(ROOT / f"results/inst_{m}/induction.jsonl") for m in ["gemma", "gams"]}
    if rkey == "R_judge":
        jm = judge_refuse_map()
        for m in recs:
            keep = []
            for r in recs[m]:
                if only_dirs and r["direction"] not in only_dirs | {"none"}:
                    continue
                cond = "ind_pt" if r["direction"] == "pt" else "ind_ctrl"
                j = jm.get(f"{cond}|{m}|{r['lang']}|{r['direction']}|{r['alpha_k']}|{r['hid']}")
                if j is None:
                    continue
                keep.append(dict(r, R_judge=int(j and not r["degenerate"])))
            recs[m] = keep
    if not recs["gemma"] or not recs["gams"]:
        return {"status": "missing induction results"}
    alphas_by_model = {}
    for m in recs:
        alphas_by_model[m] = {}
        for r in recs[m]:
            alphas_by_model[m][r["alpha_k"]] = r["alpha_abs"]
    out["n_bar"] = {m: float(np.load(ROOT / f"results/inst_{m}/own_dirs.npz")["n_bar"]) for m in recs}
    out["alpha_grid"] = {m: {str(k): v for k, v in sorted(alphas_by_model[m].items())} for m in recs}
    out["pre_registered_grid_only"] = PRE_ONLY
    recs_by = defaultdict(list)
    base = {}
    for m in recs:
        for r in recs[m]:
            if r["direction"] == "none":
                base.setdefault((m, r["lang"]), []).append(r)
            else:
                recs_by[(m, r["direction"], r["lang"])].append(r)
    out["baseline_alpha0"] = {f"{m}_{la}": {"R": float(np.mean([r[rkey] for r in v])), "s": float(np.mean([r["s"] for r in v])),
                                            "deg": float(np.mean([r["degenerate"] for r in v])), "n": len(v)} for (m, la), v in base.items()}
    all_hids = sorted({r["hid"] for m in recs for r in recs[m] if r["direction"] == "pt"})
    cells = {}
    for ck, v in recs_by.items():
        hids = sorted({r["hid"] for r in v})
        f = fit_cell(v, hids, alphas_by_model[ck[0]], rkey)
        # s readout: alpha where mean s crosses 0 (log-linear interpolation)
        ks = sorted({r["alpha_k"] for r in v if r["alpha_k"] != -1}, key=lambda k: alphas_by_model[ck[0]][k])
        ms = [np.mean([r["s"] for r in v if r["alpha_k"] == k]) for k in ks]
        a_s0 = None
        la_ = np.log([alphas_by_model[ck[0]][k] for k in ks])
        for j in range(1, len(ks)):
            if ms[j - 1] < 0 <= ms[j]:
                a_s0 = float(np.exp(la_[j - 1] + (0 - ms[j - 1]) * (la_[j] - la_[j - 1]) / (ms[j] - ms[j - 1])))
                break
        if a_s0 is None and ms and ms[0] >= 0:
            a_s0 = "below_range"
        f["alpha_s0"] = a_s0
        f["s_by_k"] = [float(x) for x in ms]
        f["n_hids"] = len(hids)
        # per-prompt flip thresholds
        byh = defaultdict(dict)
        for r in v:
            byh[r["hid"]][r["alpha_k"]] = r[rkey]
        thr = {}
        for h, d in byh.items():
            kk = sorted(d, key=lambda k: alphas_by_model[ck[0]][k])
            t = None
            for j, k in enumerate(kk):
                if d[k] == 1 and (j + 1 == len(kk) or d[kk[j + 1]] == 1):
                    t = float(alphas_by_model[ck[0]][k])
                    break
            thr[h] = t
        f["flip_thresholds"] = thr
        f["frac_never_flipped"] = float(np.mean([t is None for t in thr.values()]))
        cells["|".join(ck)] = f
    out["cells"] = {k: {kk: vv for kk, vv in v.items() if kk != "flip_thresholds"} for k, v in cells.items()}
    out["flip_thresholds"] = {k: v["flip_thresholds"] for k, v in cells.items()}
    # EN vs SL flip-threshold Spearman per model x direction
    sp = {}
    for m in recs:
        for dname in sorted({k.split("|")[1] for k in cells if k.startswith(m + "|")}):
            e, s_ = cells.get(f"{m}|{dname}|en"), cells.get(f"{m}|{dname}|sl")
            if not e or not s_:
                continue
            big = 1e9
            hs = sorted(set(e["flip_thresholds"]) & set(s_["flip_thresholds"]))
            a = [e["flip_thresholds"][h] or big for h in hs]; b = [s_["flip_thresholds"][h] or big for h in hs]
            if len(set(a)) > 1 and len(set(b)) > 1:
                sp[f"{m}|{dname}"] = float(spearmanr(a, b).correlation)
    out["flip_spearman_en_sl"] = sp
    # bootstrap for primary + key directions (joint hid resampling)
    key_dirs = [d for d in ["pt", "own_pooled", "gb", "langid", "own_en", "own_sl"] if any(k[1] == d for k in recs_by)]
    cellkeys = [k for k in recs_by if k[1] in key_dirs]
    nw = max(1, workers)
    per = [nboot // nw + (1 if i < nboot % nw else 0) for i in range(nw)]
    sub_recs = {k: recs_by[k] for k in cellkeys}
    with ProcessPoolExecutor(max_workers=nw, mp_context=mp.get_context("spawn")) as ex:
        parts = list(ex.map(_boot_worker, [(i, per[i], sub_recs, all_hids, alphas_by_model, cellkeys, rkey) for i in range(nw)]))
    boots = [b for p in parts for b in p]
    # random directions: bootstrap over their 20 hids (fewer draws)
    rand_keys = [k for k in recs_by if k[1].startswith("rand")]
    rand_hids = sorted({r["hid"] for k in rand_keys for r in recs_by[k]})

    def ratio(a, b):
        return None if (a is None or b is None) else math.log(a / b)

    def delta(dct, dname):
        rg = ratio(dct.get(f"gams|{dname}|sl"), dct.get(f"gams|{dname}|en"))
        rm = ratio(dct.get(f"gemma|{dname}|sl"), dct.get(f"gemma|{dname}|en"))
        return None if (rg is None or rm is None) else rg - rm

    point = {k: v.get("a50") for k, v in cells.items()}
    deltas = {}
    for dname in key_dirs:
        est = delta(point, dname)
        bs = [delta(b, dname) for b in boots]
        fin = [x for x in bs if x is not None]
        frac = len(fin) / len(bs) if bs else 0
        deltas[dname] = {"Delta_C4": est, "ci": ci(fin) if frac >= 0.9 else None, "ci_open": frac < 0.9,
                         "frac_finite": frac, "ci_all_finite_only": ci(fin),
                         "ln_ratio_gams": ratio(point.get(f"gams|{dname}|sl"), point.get(f"gams|{dname}|en")),
                         "ln_ratio_gemma": ratio(point.get(f"gemma|{dname}|sl"), point.get(f"gemma|{dname}|en"))}
    out["Delta"] = deltas
    out["a50_ci"] = {k: {"est": point[k], "ci": ci([b.get(k) for b in boots]),
                         "frac_finite": float(np.mean([b.get(k) is not None for b in boots]))} for k in boots[0]} if boots else {}
    # verdict
    pos_ok = all(point.get(f"{m}|own_pooled|{la}") is not None for m in ["gemma", "gams"] for la in ["en", "sl"])
    pt_reach = all(point.get(f"{m}|pt|{la}") is not None for m in ["gemma", "gams"] for la in ["en", "sl"])
    ctrl = {}
    beaten = True
    for m in ["gemma", "gams"]:
        for la in ["en", "sl"]:
            apt = point.get(f"{m}|pt|{la}")
            al = point.get(f"{m}|langid|{la}")
            ar = [point.get(f"{m}|rand{i}|{la}") for i in range(5) if f"{m}|rand{i}|{la}" in point]
            ar_f = [x for x in ar if x is not None]
            med_r = float(np.median(ar_f)) if len(ar_f) > len(ar) / 2 else None  # median NR if most randoms NR
            b_l = apt is not None and (al is None or apt <= 0.5 * al)
            b_r = apt is not None and (med_r is None or apt <= 0.5 * med_r)
            ctrl[f"{m}_{la}"] = {"a50_pt": apt, "a50_langid": al, "a50_random": ar, "median_random": med_r,
                                 "beats_langid": b_l, "beats_random": b_r}
            beaten &= b_l and b_r
    out["controls"] = ctrl
    dpt = deltas.get("pt", {})
    if not pos_ok:
        verdict = "INVALID (positive control: own pooled direction did not reach alpha50 in all 4 cells)"
    elif not pt_reach:
        own = deltas.get("own_pooled", {})
        alt1 = own.get("Delta_C4") is not None and own.get("ci") and own["Delta_C4"] < -LN15 and own["ci"][1] < 0
        verdict = ("FAILURE BRANCH: pt direction NR in >=1 cell -> no ancestor-readable causal support; own-direction "
                   f"Delta={own.get('Delta_C4')} ci={own.get('ci')} -> ALT-1 {'SUPPORTED' if alt1 else 'not supported'}")
    elif not beaten:
        verdict = "CONTROLS NOT BEATEN (pt direction not >=2x more potent than lang-ID / random in every cell)"
    else:
        c = dpt.get("ci")
        if c is None or dpt.get("ci_open"):
            verdict = "INCONCLUSIVE (open CI)"
        elif (c[1] - c[0]) > 2 * LN15:
            verdict = f"INCONCLUSIVE (CI width {c[1]-c[0]:.2f} > 2 ln1.5)"
        elif -LN15 < c[0] and c[1] < LN15:
            verdict = "CONFIRM (no GaMS-specific language asymmetry in pt-direction potency; supports MAIN over ALT-1)"
        elif c[1] < 0:
            verdict = "ASYMMETRY: GaMS induces SL refusal at relatively lower alpha (ALT-1 direction)"
        else:
            verdict = "NOT CONFIRMED (CI outside equivalence band)"
    out["positive_control_pass"] = pos_ok
    out["pt_reaches_all_cells"] = pt_reach
    out["verdict"] = verdict
    out["n_boot"] = len(boots)
    return out


# =============================================================================== main
def main() -> None:
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
    logger.add(ROOT / "logs/analyze.log", rotation="30 MB", level="DEBUG")
    OUT.mkdir(parents=True, exist_ok=True)
    res = {}
    res["S1"] = s1_base()
    logger.info(f"S1 done: {json.dumps({k: res['S1'].get(k) for k in ['L_pt', 'L_gb']})} "
                f"Lpt {json.dumps({k: v for k, v in res['S1'].get('Lpt', {}).items() if 'Delta' in k or 'DiD' in k})}")
    mp_ = s1_base("_meanpool")
    if "Lpt" in mp_:
        res["S1_meanpool_exploratory"] = {k: mp_[k] for k in ["L_pt", "L_gb", "Lpt", "Lown", "cos_pt_gb_at_Lpt", "style_check"]}
    pc = ROOT / "results/analysis/punct_check.json"
    if pc.exists():
        res["S1_punct_matched_exploratory"] = json.loads(pc.read_text())["Delta_dprime_matched"]
    S, R4, RC = load_instruct()
    if all(S.values()) and all(R4.values()):
        # m (D2) from CONSTRUCT-100
        allR = [r["R_lex"] for m in RC for r in RC[m]]
        if allR:
            p0 = (sum(allR) + 0.5) / (len(allR) + 1)
            lg = lambda p: math.log(p / (1 - p))
            m_ = lg(p0 + 0.05) - lg(p0) if p0 <= 0.5 else lg(p0) - lg(p0 - 0.05)
            res["m"] = {"p0_construct": p0, "m": m_, "n": len(allR)}
            add = ROOT / "config/protocol_addendum.json"
            if add.exists():
                res["m"]["addendum"] = json.loads(add.read_text())
        judge = judge_labels()
        jm = judge_refuse_map()
        for m in R4:
            for r in R4[m]:
                j = jm.get(f"orig|{m}|{r['lang']}|{r['pair_id']}")
                r["R_judge"] = None if j is None else int(j and not r["degenerate"])
        res["S2"] = s2_instruct(S, R4, judge)
        cov = {m: float(np.mean([r["R_judge"] is not None for r in R4[m]])) for m in R4}
        res["judge_coverage_score400"] = cov
        if all(v >= 0.99 for v in cov.values()):
            ok_pairs = {pid for pid in {r["pair_id"] for r in R4["gemma"]}
                        if all(r["R_judge"] is not None for m in R4 for r in R4[m] if r["pair_id"] == pid)}
            R4j = {m: [r for r in R4[m] if r["pair_id"] in ok_pairs] for m in R4}
            res["S2_judge"] = {k: v for k, v in s2_instruct(S, R4j, judge, "R_judge").items() if k in ("cells", "DiD", "D", "ceiling_rule_triggered")}
            res["S2_judge"]["n_pairs"] = len(ok_pairs)
        res["S2_langonly_lexicon"] = {k: v for k, v in s2_instruct(S, R4, judge, "R_lex_langonly").items() if k in ("cells", "DiD", "D")}
        logger.info(f"S2 cells {json.dumps({k: round(v['R'], 3) for k, v in res['S2']['cells'].items()})}")
        res["S3"] = s3_regression(S, res["S1"])
        logger.info(f"S3 share {res['S3']['s']['geometry_share']} inc {res['S3']['s']['dose_increment']} "
                    f"R2full {res['S3']['s']['R2adj_fullcat']}")
    res["S4"] = s4_induction()
    logger.info(f"S4 verdict: {res['S4'].get('verdict')}")
    if (ROOT / "results/shared/judge_labels.jsonl").exists():
        try:
            res["S4_judge"] = s4_induction(rkey="R_judge", only_dirs={"pt", "own_pooled", "langid"} | {f"rand{i}" for i in range(5)}, nboot=1000)
            logger.info(f"S4 (judge readout, pt/own only) verdict: {res['S4_judge'].get('verdict')}")
        except (ValueError, KeyError, IndexError, ZeroDivisionError) as e:
            logger.error(f"S4_judge failed: {e!r}")
            res["S4_judge"] = {"status": f"failed: {e!r}"}
    # S5 selection rule
    if "S3" in res and "Lpt" in res["S1"]:
        s1 = res["S1"]["Lpt"]
        sel = {}
        for name in ["s", "s_c"]:
            r3 = res["S3"][name]
            a_ok = bool(s1["Delta_dprime_SL"] > 0 and s1["Delta_dprime_SL_ci"][0] > 0)
            sh_ok = bool(r3["geometry_share"] >= 0.5)
            inc_ok = bool(r3["dose_increment"] < 0.10)
            passed = bool(a_ok and sh_ok and inc_ok and not r3["not_identifiable"])
            sel[name] = {"part_a_DeltaDprimeSL_pos": a_ok, "geometry_share_ge_0.5": sh_ok, "dose_increment_lt_0.10": inc_ok,
                         "not_identifiable": r3["not_identifiable"], "ALT2_PASS": passed, "z_c": r3["z_c"],
                         "survivor": bool(passed and r3["z_c"] is not None and r3["z_c"] > 0)}
        res["S5"] = {"ALT2": sel, "C4_status": res["S4"].get("verdict")}
    (OUT / "analysis.json").write_text(json.dumps(res, indent=1, default=lambda o: None))
    logger.info(f"wrote {OUT/'analysis.json'}")


if __name__ == "__main__":
    main()
