#!/usr/bin/env python3
"""T6 audit: re-derive headline numbers from the RAW per-item files through DIFFERENT code paths (pandas /
statsmodels / scipy.curve_fit / raw residual arrays) and compare with results/analysis/analysis.json; run placebo
versions (shuffled labels) that must FAIL. Also checks protocol hash and that RefusEU evaluation/ was never read.
Writes results/analysis/audit.json."""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.optimize import curve_fit

ROOT = Path(__file__).resolve().parents[1]
rng = np.random.default_rng(12345)


def rj(p):
    return pd.read_json(p, lines=True)


def dp(a, b):
    a, b = pd.Series(a), pd.Series(b)
    return (a.mean() - b.mean()) / math.sqrt((a.var() + b.var()) / 2)


def main() -> None:
    A = json.loads((ROOT / "results/analysis/analysis.json").read_text())
    out = {"checks": {}, "placebos": {}}

    def chk(name, mine, theirs, tol):
        ok = (mine is None and theirs is None) or (mine is not None and theirs is not None and abs(mine - theirs) <= tol)
        out["checks"][name] = {"audit": mine, "analysis": theirs, "tol": tol, "match": bool(ok)}

    # ---------- S1: d' from raw residual arrays (recompute directions from scratch) for pt/gb at L_pt
    L = A["S1"]["L_pt"]
    dps = {}
    for m in ["pt", "gb"]:
        idx = rj(ROOT / f"results/base_{m}/resid_index.jsonl")
        # raw last-token residuals at L_pt, kept in the repo as row-split parts (<100 MB each); the full all-layer
        # cache scratch/resid_{m}.npy is regenerable (src/base_geometry.py) and not kept
        parts = sorted((ROOT / f"results/base_{m}").glob(f"resid_L{L}_part_*.npy"))
        npy = ROOT / f"scratch/resid_{m}.npy"
        if parts:
            XL = np.concatenate([np.load(p) for p in parts]).astype(np.float64)
            src = f"raw residuals ({len(parts)} split parts)"
        elif npy.exists():
            XL = np.array(np.load(npy, mmap_mode="r")[:, L, :], dtype=np.float64)
            src = "raw residuals (scratch cache)"
        else:
            XL = None
            src = "missing"
        if XL is not None:
            assert len(XL) == len(idx), (len(XL), len(idx))
        for la in ["en", "sl"]:
            if XL is None:
                continue
            g = lambda k, r: XL[((idx.kind == k) & (idx.role == r) & (idx.lang == la)).values]
            d_la = g("harm", "CONSTRUCT").mean(0) - g("harmless", "CONSTRUCT").mean(0)
            dps.setdefault(m, {})[f"dir_{la}"] = d_la
        if XL is not None:
            r = (dps[m]["dir_en"] + dps[m]["dir_sl"]) / 2
            r = r / np.linalg.norm(r)
            for la in ["en", "sl"]:
                h = XL[((idx.kind == "harm") & (idx.role == "SCORE") & (idx.lang == la)).values] @ r
                b = XL[((idx.kind == "harmless") & (idx.role == "SCORE") & (idx.lang == la)).values] @ r
                dps[m][la] = dp(h, b)
                if m == "pt" and la == "sl":
                    lab = np.r_[np.ones(len(h)), np.zeros(len(b))]
                    v = np.r_[h, b]
                    perm = rng.permutation(lab)
                    out["placebos"]["dprime_SL_pt_shuffled_labels"] = float(dp(v[perm == 1], v[perm == 0]))
        out["checks"][f"S1_source_{m}"] = src
    if "pt" in dps and "gb" in dps:
        chk("Delta_dprime_SL_Lpt", float(dps["gb"]["sl"] - dps["pt"]["sl"]), A["S1"]["Lpt"]["Delta_dprime_SL"], 1e-3)
        chk("dprime_pt_en_Lpt", float(dps["pt"]["en"]), A["S1"]["Lpt"]["dprime"]["pt_en"], 1e-3)
        did = (dps["gb"]["sl"] - dps["gb"]["en"]) - (dps["pt"]["sl"] - dps["pt"]["en"])
        chk("DiD_dprime_Lpt", float(did), A["S1"]["Lpt"]["DiD_dprime"], 1e-3)

    # ---------- S2: SCORE-400 refusal rates + DiD (pandas)
    r4 = pd.concat([rj(ROOT / f"results/inst_{m}/r_score400.jsonl") for m in ["gemma", "gams"]])
    for (m, la), g in r4.groupby(["model", "lang"]):
        chk(f"R_{m}_{la}", float(g.R_lex.mean()), A["S2"]["cells"][f"{m}_{la}"]["R"], 1e-9)
    piv = r4.pivot_table(index="pair_id", columns=["model", "lang"], values="R_lex")
    hl = lambda s: math.log(((s.sum() + .5) / (len(s) + 1)) / (1 - (s.sum() + .5) / (len(s) + 1)))
    did = (hl(piv[("gams", "sl")]) - hl(piv[("gams", "en")])) - (hl(piv[("gemma", "sl")]) - hl(piv[("gemma", "en")]))
    chk("DiD_R_all", did, A["S2"]["DiD"]["all_did_R"]["est"], 1e-9)

    # ---------- S3: regression via statsmodels from raw s + item_proj
    S = pd.concat([rj(ROOT / f"results/inst_{m}/s_score.jsonl") for m in ["gemma", "gams"]])
    Sh = S[S.kind == "harm"].pivot_table(index="item", columns=["model", "lang"], values="s")
    y = (Sh[("gams", "sl")] - Sh[("gams", "en")]) - (Sh[("gemma", "sl")] - Sh[("gemma", "en")])
    P = pd.concat([rj(ROOT / f"results/base_{m}/item_proj.jsonl").assign(bm=m) for m in ["pt", "gb"]])
    P = P[(P.layer_name == "Lpt") & (P.dir == "pooled") & (P.kind == "harm")]
    Z = P.pivot_table(index="item", columns=["bm", "lang"], values="harm_z")
    Z.columns = [f"{a}_{b}" for a, b in Z.columns]
    df = pd.DataFrame({"y": y}).join(Z, how="inner").dropna()
    cat = S[S.kind == "harm"].drop_duplicates("item").set_index("item").category
    df["cat"] = cat.reindex(df.index)
    G = df[["gb_sl", "gb_en", "pt_sl", "pt_en"]]
    G = (G - G.mean()) / G.std(ddof=0)
    fe = pd.get_dummies(df["cat"], drop_first=True, dtype=float)
    mg = sm.OLS(df["y"], sm.add_constant(G)).fit()
    mf = sm.OLS(df["y"], sm.add_constant(pd.concat([G, fe], axis=1))).fit()
    share = mg.rsquared_adj / mf.rsquared_adj
    chk("geometry_share_s", float(share), A["S3"]["s"]["geometry_share"], 1e-6)
    chk("R2adj_fullcat_s", float(mf.rsquared_adj), A["S3"]["s"]["R2adj_fullcat"], 1e-6)
    out["checks"]["S3_n_items"] = {"audit": int(len(df)), "analysis": A["S3"]["n_items"], "match": int(len(df)) == A["S3"]["n_items"]}
    yp = df["y"].sample(frac=1, random_state=1).values
    out["placebos"]["R2adj_geometry_permuted_y"] = float(sm.OLS(yp, sm.add_constant(G)).fit().rsquared_adj)
    out["placebos"]["R2adj_fullcat_permuted_y"] = float(sm.OLS(yp, sm.add_constant(pd.concat([G, fe], axis=1))).fit().rsquared_adj)

    # ---------- S4: alpha50 via scipy.curve_fit (different optimiser, unweighted) + shuffled-alpha placebo
    for m in ["gemma", "gams"]:
        ind = rj(ROOT / f"results/inst_{m}/induction.jsonl")
        if ind.empty:
            continue
        for d in ["pt", "own_pooled", "langid"]:
            for la in ["en", "sl"]:
                c = ind[(ind.direction == d) & (ind.lang == la) & (ind.alpha_k != -1)]
                if c.empty:
                    continue
                agg = c.groupby("alpha_abs").agg(R=("R_lex", "mean"), deg=("degenerate", "mean")).reset_index()
                agg = agg[agg.deg <= 0.5].sort_values("alpha_abs").reset_index(drop=True)
                if agg.R.max() < 0.5:
                    agg = agg.iloc[:0]
                else:  # rising limb: up to the first alpha within 0.02 of the peak (same estimand as analyze.py D15)
                    agg = agg.iloc[: int(np.argmax(agg.R.values >= agg.R.max() - 0.02)) + 1]
                x, yv = np.log(agg.alpha_abs.values), agg.R.values
                if len(agg) < 4:
                    theirs = A["S4"]["cells"].get(f"{m}|{d}|{la}", {}).get("a50")
                    out["checks"][f"a50_{m}|{d}|{la}"] = {"audit_curve_fit": None, "analysis": theirs, "match": theirs is None,
                                                         "note": "NR (peak < 0.5) or < 4 rising-limb alphas"}
                    continue
                key = f"{m}|{d}|{la}"
                theirs = A["S4"]["cells"].get(key, {}).get("a50")
                f = lambda x, b, t, h, lc: b + (t - b) / (1 + np.exp(-h * (x - lc)))
                mine = None
                try:
                    p, _ = curve_fit(f, x, yv, p0=[max(0, yv.min()), min(1, yv.max()), 2, np.median(x)],
                                     bounds=([0, 0, 0.3, x.min() - 2], [1, 1, 15, x.max() + 2]), maxfev=20000)
                    b, t, h, lc = p
                    if b < 0.5 < t:
                        a = math.exp(lc + math.log((t - b) / (0.5 - b) - 1) / h)
                        if math.exp(x.min()) / 2 <= a <= 2 * math.exp(x.max()):
                            mine = a
                except (RuntimeError, ValueError):
                    pass
                # empirical crossing by log-linear interpolation (model-free)
                emp = None
                for j in range(1, len(yv)):
                    if yv[j - 1] < 0.5 <= yv[j]:
                        emp = math.exp(x[j - 1] + (0.5 - yv[j - 1]) * (x[j] - x[j - 1]) / (yv[j] - yv[j - 1]))
                        break
                ratio = (mine / theirs) if (mine and theirs) else None
                their_i = A["S4"]["cells"].get(key, {}).get("a50_interp")
                out["checks"][f"a50_{key}"] = {"audit_curve_fit": mine, "audit_empirical_interp": emp, "analysis": theirs,
                                               "analysis_interp": their_i, "ratio": ratio,
                                               "interp_match": bool(isinstance(their_i, float) and emp is not None and abs(emp / their_i - 1) < 1e-6),
                                               "match": bool((mine is None and theirs is None) or (ratio is not None and 0.8 <= ratio <= 1.25))}
                if d == "own_pooled":
                    rising = c[c.alpha_abs <= agg.alpha_abs.max()]
                    sh = rising.copy()
                    sh["alpha_abs"] = rng.permutation(sh.alpha_abs.values)
                    ag2 = sh.groupby("alpha_abs").R_lex.mean()
                    rho = pd.Series(ag2.values).corr(pd.Series(np.log(ag2.index.values)), method="spearman")
                    rho0 = pd.Series(yv).corr(pd.Series(x), method="spearman")
                    out["placebos"][f"spearman_R_vs_alpha_rising_{m}_own_{la}"] = {"real": float(rho0), "shuffled_alpha": float(rho)}
    # ---------- judge readout (pandas from judge_labels.jsonl, independent of analyze.py)
    J = rj(ROOT / "results/shared/judge_labels.jsonl")
    J["ref"] = ((J.label == "refuse") & (~J.incoherent)).astype(int)
    parts = J.key.str.split("|", expand=True)
    J["kind"], J["model"], J["lang"] = parts[0], parts[1], parts[2]
    o = J[J.kind == "orig"].copy()
    o["pid"] = J.loc[o.index, "key"].str.split("|").str[3:].str.join("|")
    keep = o.groupby("pid").size()
    keep = set(keep[keep == 4].index)
    o = o[o.pid.isin(keep)]
    r4d = r4.set_index(["model", "lang", "pair_id"]).degenerate
    o["refd"] = [int(rf and not r4d[(m, l, p)]) for rf, m, l, p in zip(o.ref, o.model, o.lang, o.pid)]
    for (m, la), g in o.groupby(["model", "lang"]):
        chk(f"R_judge_{m}_{la}", float(g.refd.mean()), A.get("S2_judge", {}).get("cells", {}).get(f"{m}_{la}", {}).get("R"), 1e-9)
    ind_all = pd.concat([rj(ROOT / f"results/inst_{m}/induction.jsonl") for m in ["gemma", "gams"]])
    ind_all["key"] = [f"{'ind_pt' if d == 'pt' else 'ind_ctrl'}|{m}|{l}|{d}|{k}|{h}" for d, m, l, k, h in
                      zip(ind_all.direction, ind_all.model, ind_all.lang, ind_all.alpha_k, ind_all.hid)]
    jj = J.set_index("key").ref
    ind_all = ind_all[ind_all.key.isin(jj.index)]
    ind_all["Rj"] = [int(jj[k] and not dg) for k, dg in zip(ind_all.key, ind_all.degenerate)]
    a50j = {}
    for (m, d, la), c in ind_all[(ind_all.direction == "own_pooled") & (ind_all.alpha_k != -1)].groupby(["model", "direction", "lang"]):
        agg = c.groupby("alpha_abs").agg(R=("Rj", "mean"), deg=("degenerate", "mean")).reset_index().sort_values("alpha_abs")
        agg = agg[agg.deg <= 0.5].reset_index(drop=True)
        agg = agg.iloc[: int(np.argmax(agg.R.values >= agg.R.max() - 0.02)) + 1]
        x, yv = np.log(agg.alpha_abs.values), agg.R.values
        emp = None
        for j in range(1, len(yv)):
            if yv[j - 1] < 0.5 <= yv[j]:
                emp = math.exp(x[j - 1] + (0.5 - yv[j - 1]) * (x[j] - x[j - 1]) / (yv[j] - yv[j - 1]))
                break
        a50j[(m, la)] = emp
        chk(f"a50_interp_judge_{m}_own_{la}", emp, A.get("S4_judge", {}).get("cells", {}).get(f"{m}|own_pooled|{la}", {}).get("a50_interp"), 1e-6)
    pt_peak = ind_all[(ind_all.direction == "pt") & (ind_all.alpha_k != -1)].groupby(["model", "lang", "alpha_k"]).Rj.mean().groupby(["model", "lang"]).max()
    out["checks"]["pt_judge_peak_R_all_below_0.5"] = {"audit": {f"{a}_{b}": float(v) for (a, b), v in pt_peak.items()},
                                                     "match": bool((pt_peak < 0.5).all())}
    own = A["S4"]["cells"]
    lr = lambda m: math.log(own[f"{m}|own_pooled|sl"]["a50"] / own[f"{m}|own_pooled|en"]["a50"])
    chk("Delta_C4_own_pooled_lexicon", lr("gams") - lr("gemma"), A["S4"]["Delta"]["own_pooled"]["Delta_C4"], 1e-9)

    # ---------- integrity
    proto = ROOT / "config/protocol.json"
    out["protocol_sha256_matches"] = hashlib.sha256(proto.read_bytes()).hexdigest() == (ROOT / "config/protocol.sha256").read_text().split()[0]
    gl = subprocess.run(["git", "log", "--format=%cI %s", "--reverse"], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    out["git_first_commit"] = gl[0] if gl else None
    firsts = [lg.read_text().splitlines()[0][:23] for lg in (ROOT / "logs").glob("base_geometry_*.log")]
    out["first_base_forward_log_ts"] = min(firsts) if firsts else None
    hits = subprocess.run(["grep", "-rl", "evaluation/", str(ROOT / "data"), str(ROOT / "logs"), str(ROOT / "src")],
                          capture_output=True, text=True).stdout.split()
    out["evaluation_split_references"] = [h for h in hits if not h.endswith(("audit.py", "data_build.py", "make_protocol.py", "ledger.py"))]
    evdir = Path("../../../../.shared_cache/hf/hub/datasets--NASK-PIB--RefusEU/snapshots")
    out["refuseu_eval_in_shared_cache_note"] = [str(p) for p in evdir.glob("*/evaluation*")]
    out["all_checks_match"] = all(v.get("match", True) for v in out["checks"].values() if isinstance(v, dict))
    (ROOT / "results/analysis/audit.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float)[:4000])


if __name__ == "__main__":
    main()
