#!/usr/bin/env python3
"""T6 AUDIT: independent re-derivation of headline numbers from the raw per-item JSONL through a DIFFERENT code path
(pandas groupby / np.polyfit instead of analyze.py's matrix + hand OLS), plus placebo/permutation checks that must FAIL
to show an effect. Writes results/audit.json."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from common import RESULTS, SPLITS

A = json.loads((RESULTS / "analysis.json").read_text())
out = {"checks": [], "placebo": {}}
rng = np.random.default_rng(12345)  # deliberately different seed from the analysis
MODELS = [m for m in ("gemma_it", "gams3_it") if (RESULTS / m / "orig_score400.jsonl").exists()]
BOTH = len(MODELS) == 2
out["models"] = MODELS


def lo(k, n):
    p = (k + 0.5) / (n + 1)
    return np.log(p) - np.log1p(-p)


def check(name, mine, theirs, tol=1e-9):
    ok = bool(np.isclose(mine, theirs, atol=tol, rtol=0)) if (mine is not None and theirs is not None) else False
    out["checks"].append({"name": name, "audit": mine, "analysis": theirs, "match": ok})
    print(("OK  " if ok else "BAD ") + f"{name}: audit={mine} analysis={theirs}")


def jl(p):
    return pd.read_json(p, lines=True)


PRIMARY = A.get("primary_readout", "lexicon")
JDF = jl(RESULTS / "judge.jsonl") if (RESULTS / "judge.jsonl").exists() else None
out["primary_readout"] = PRIMARY


def lab(df, m, cell):
    """Primary-readout labels via an independent pandas join (judge: R = 1[judge == 'refuse'])."""
    df = df.copy()
    if PRIMARY != "judge":
        if "R" not in df and "R_cont" in df:
            df["R"] = df["R_cont"]
        return df
    j = JDF[JDF["model"] == m].copy()
    if callable(cell):
        df["_cell"] = df.apply(cell, axis=1)
    else:
        df["_cell"] = cell
    if "trial" not in df:
        df["trial"] = -1
    df["trial"] = df["trial"].fillna(-1).astype(int)
    j = j.rename(columns={"cell": "_cell"})[["_cell", "lang", "pair_id", "trial", "judge"]]
    df = df.merge(j, on=["_cell", "lang", "pair_id", "trial"], how="inner")
    df = df[df["judge"].notna()]
    df["R"] = (df["judge"] == "refuse").astype(int)
    return df


def ref0_filter(q, m):
    if PRIMARY != "judge":
        return q
    o = lab(jl(RESULTS / m / "orig_score400.jsonl"), m, "orig")
    keep = set(map(tuple, o.loc[o["R"] == 1, ["pair_id", "lang"]].values))
    return q[[(a_, b_) in keep for a_, b_ in zip(q["pair_id"], q["lang"])]]


# ---- 1. original / selected refusal rates ----
for m in MODELS:
    o = lab(jl(RESULTS / m / "orig_score400.jsonl"), m, "orig")
    for lang, g in o.groupby("lang"):
        check(f"R_orig {m} {lang}", float(g["R"].mean()), A["P0_descriptives"][f"{m}|orig|{lang}"]["R"])
    s = jl(RESULTS / m / "selected_score400.jsonl")
    s = s[s["s"].notna()] if "s" in s else s
    s = lab(s, m, "selected")
    for lang, g in s.groupby("lang"):
        check(f"R_selected {m} {lang}", float(g["R"].mean()), A["P0_descriptives"][f"{m}|selected|{lang}"]["R"])

# ---- 2. DiD_ref overall on SCORE-400 ----
tab = {}
for m in MODELS:
    o = lab(jl(RESULTS / m / "orig_score400.jsonl"), m, "orig")
    k = o.groupby("lang")["R"].sum()
    n = o.groupby("lang")["R"].count()
    tab[m] = lo(k["sl"], n["sl"]) - lo(k["en"], n["en"])
if BOTH:
    check("P0 DiD_ref overall", float(tab["gams3_it"] - tab["gemma_it"]), A["P0_DiD_ref_overall"]["est"])

# ---- 3. C3 G3 via polyfit on pandas pivot ----
def trial_xy(m, pair_filter=None):
    t = jl(RESULTS / m / "trial_probe.jsonl")
    t = t[(t["tag"] == "trial") & t["R"].notna()]
    t = lab(t, m, "trialpool")
    if pair_filter is not None:
        t = t[t["pair_id"].isin(pair_filter)]
    g = t.groupby(["trial", "lang"])["R"].agg(["sum", "count"]).unstack("lang")
    x = lo(g[("sum", "en")], g[("count", "en")])
    y = lo(g[("sum", "sl")], g[("count", "sl")])
    return x.values, y.values


a = {}
C3V = A.get("selection", {}).get("c3_variant_used", "all_trials")
KMIN = min(len({r["trial"] for r in jl(RESULTS / m / "trial_probe.jsonl").query("tag == 'trial'").to_dict("records")})
           for m in MODELS) if BOTH else 0
for m in MODELS if BOTH else []:
    x, y = trial_xy(m)
    if C3V == "matched_first_k_trials":
        x, y = x[:KMIN], y[:KMIN]
    b1, b0 = np.polyfit(x, y, 1)
    a[m] = b0
    check(f"C3 slope {m}", float(b1), A["C3"][C3V]["all_pairs"]["b_slope"][m]["est"], tol=1e-7)
G3 = (a["gams3_it"] - a["gemma_it"]) if BOTH else float("nan")
if BOTH:
    check(f"C3 G3 ({C3V})", float(G3), A["C3"][C3V]["all_pairs"]["G3"]["est"], tol=1e-7)

# placebo 1: permute trials between models (null: no model difference) -> G3 distribution around 0
xy = {m: trial_xy(m) for m in MODELS} if BOTH else {}
if BOTH:
    X = np.concatenate([xy[m][0] for m in MODELS])
    Y = np.concatenate([xy[m][1] for m in MODELS])
    n0 = len(xy["gemma_it"][0])
    perm = []
    for _ in range(2000):
        idx = rng.permutation(len(X))
        g0, g1 = idx[:n0], idx[n0:]
        perm.append(np.polyfit(X[g1], Y[g1], 1)[1] - np.polyfit(X[g0], Y[g0], 1)[1])
    perm = np.array(perm)
    out["placebo"]["C3_G3_trial_label_permutation"] = {
        "observed": float(G3), "perm_mean": float(perm.mean()), "perm_sd": float(perm.std()),
        "p_two_sided": float((np.abs(perm) >= abs(G3)).mean()),
        "note": "null distribution of G3 when trials are randomly re-assigned to models; observed effect is 'real' only if p small"}
# placebo 2: break the EN-SL pairing within model (shuffle y across trials) -> slope ~ 0
sl = []
xy.setdefault("gemma_it", trial_xy("gemma_it"))
for _ in range(500):
    x, y = xy["gemma_it"]
    sl.append(np.polyfit(x, rng.permutation(y), 1)[0])
out["placebo"]["C3_slope_shuffled_y_gemma"] = {"observed_slope": float(np.polyfit(*xy["gemma_it"], 1)[0]),
                                                "shuffled_mean": float(np.mean(sl)), "shuffled_sd": float(np.std(sl))}

# ---- 4. C5a excess ratio (norm-matched) via pandas ----
for m in MODELS:
    s = jl(RESULTS / m / "selected_score400.jsonl")
    s = s[s.get("kind") == "kl"]
    ev = s.groupby("lang")["kl"].mean()
    pk = jl(RESULTS / m / "posthoc_kl.jsonl")
    for v, pre in (("norm_matched", "rand_nm_"), ("en_kl_matched", "rand_klm_")):
        r = pk[pk["tag"].str.startswith(pre) & (pk["set"] == "eval")]
        if r.empty or m not in A["C5a"] or v not in A["C5a"][m]:
            continue
        rr = r.groupby("lang")["kl"].mean()
        exc = (ev["sl"] / ev["en"]) / (rr["sl"] / rr["en"])
        check(f"C5a excess {m} {v}", float(exc), A["C5a"][m][v]["excess"]["est"], tol=1e-9)

# ---- 5. ALT-4 prefill signature ----
F = {}
for m in MODELS:
    p = jl(RESULTS / m / "prefill.jsonl")
    p = p[p["k"] == 5]
    p = lab(p, m, "prefill5")
    p = ref0_filter(p, m) if PRIMARY == "judge" else p
    p["flip"] = 1 - p["R"] if PRIMARY == "judge" else p["flip"]
    F[m] = {lang: lo(g["flip"].sum(), len(g)) for lang, g in p.groupby("lang")}
for lang in ("en", "sl") if BOTH else []:
    check(f"ALT4 Sig_{lang}", float(F["gams3_it"][lang] - F["gemma_it"][lang]), A["ALT4"]["prefill_signature"]["Sig"][lang]["est"])
# placebo: swap model labels per item among items refused by both (paired sign-flip) -> Sig ~ 0
pp = {}
for m in MODELS:
    q = ref0_filter(lab(jl(RESULTS / m / "prefill.jsonl").query("k == 5"), m, "prefill5"), m)
    q["flip"] = 1 - q["R"] if PRIMARY == "judge" else q["flip"]
    pp[m] = q
for lang in ("en", "sl") if BOTH else []:
    a0 = pp["gemma_it"][(pp["gemma_it"]["k"] == 5) & (pp["gemma_it"]["lang"] == lang)].set_index("pair_id")["flip"]
    a1 = pp["gams3_it"][(pp["gams3_it"]["k"] == 5) & (pp["gams3_it"]["lang"] == lang)].set_index("pair_id")["flip"]
    common_ids = a0.index.intersection(a1.index)
    v0, v1 = a0.loc[common_ids].values, a1.loc[common_ids].values
    obs = lo(v1.sum(), len(v1)) - lo(v0.sum(), len(v0))
    null = []
    for _ in range(2000):
        sw = rng.random(len(v0)) < 0.5
        u0, u1 = np.where(sw, v1, v0), np.where(sw, v0, v1)
        null.append(lo(u1.sum(), len(u1)) - lo(u0.sum(), len(u0)))
    null = np.array(null)
    out["placebo"][f"ALT4_Sig_{lang}_paired_label_swap"] = {"n_common_refused": int(len(common_ids)), "observed_on_common": float(obs),
                                                           "null_mean": float(null.mean()), "null_sd": float(null.std()),
                                                           "p_two_sided": float((np.abs(null) >= abs(obs)).mean())}

# ---- 6. C5b gain ----
for m in MODELS:
    if m not in A.get("C5b", {}):
        continue
    c = A["C5b"][m]
    tk = jl(RESULTS / m / "trial_kl.jsonl")
    tk = tk[(tk["tag"] == "trial") & (tk["set"] == "eval") & (tk["lang"] == "sl")]
    kp = tk[tk["trial"] == c["pick"]]["kl"].mean()
    kr = tk[tk["trial"] == c["resel"]]["kl"].mean()
    check(f"C5b gain {m}", float(1 - kr / kp), c["gain"]["est"])

# ---- 7. no evaluation-split ids in data ----
bad = [p.name for p in SPLITS.parent.rglob("*.jsonl") if "refuseu_eval" in p.read_text()]
out["no_eval_split_ids_in_data"] = not bad
out["n_checks"] = len(out["checks"])
out["n_match"] = sum(c["match"] for c in out["checks"])
(RESULTS / "audit.json").write_text(json.dumps(out, indent=2, default=float))
print(f"audit: {out['n_match']}/{out['n_checks']} match; placebo: {json.dumps(out['placebo'], default=float)[:800]}")
