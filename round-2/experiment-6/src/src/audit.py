#!/usr/bin/env python3
"""T4 independent audit: re-derives key statistics from the raw JSONL + ledgers with plain python + numpy (no shared
helper code with analysis.py) and compares with results/analysis.json. Tolerances: 1e-6 rates/points, 1e-2 bootstrap
CIs (same seed and resampling scheme). Also runs placebos. Writes results/audit.json."""
import json
import math
import os
from pathlib import Path

import numpy as np

WS = Path(__file__).resolve().parent.parent
R = Path(os.environ.get("AII_RESULTS", str(WS / "results")))
SEED = 20260924
BN = 2000


def rj(p):
    out = []
    p = Path(p)
    if not p.exists():
        return out
    for line in p.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def labels():
    """independent re-implementation of labels.load_labels(): primary = the LOCAL judge of record (amendment 5/6),
    second reader = gemini-2.5-flash, third = gpt-4.1. No cross-judge fallback inside a cell."""
    loc, g, p = {}, {}, {}
    for r in rj(R / "judge" / "local_ledger.jsonl"):
        if r.get("ok") and r.get("judge_model") == "Qwen/Qwen3-14B":
            loc[r["key"]] = r["label"]
    for r in rj(R / "judge" / "gemini_ledger.jsonl"):
        if r.get("ok"):
            g[r["key"]] = r["label"]
    for f in ("gpt41_ledger.jsonl", "select/openai__gpt-4.1.jsonl"):
        for r in rj(R / "judge" / f):
            if r.get("ok"):
                p[r["key"]] = r["label"]
    return loc, g, p


def hlog(k, n):
    q = (k + 0.5) / (n + 1.0)
    return math.log(q / (1 - q))


def main():
    A = json.loads((R / "analysis.json").read_text())
    fin, g, p = labels()
    out = {"checks": [], "placebo": {}}

    def chk(name, mine, theirs, tol):
        ok = (mine is None and theirs is None) or (mine is not None and theirs is not None and abs(mine - theirs) <= tol)
        out["checks"].append({"name": name, "audit": mine, "analysis": theirs, "tol": tol, "ok": bool(ok)})

    per_model = {}
    for m in A["models_present"]:
        rows = rj(R / m / "final_gen.jsonl")
        tab = {}
        for r in rows:
            tab[(r["item_id"], r["arm"], r["cond"])] = fin.get(r["key"])
        items = sorted({r["item_id"] for r in rows})
        meta = {json.loads(l)["item_id"]: json.loads(l) for l in (WS / "data" / "depth600.jsonl").read_text().splitlines() if l.strip()}
        J = [i for i in items if tab.get((i, "sl_mt", "k0")) == "REFUSE" and tab.get((i, "en_bt", "k0")) == "REFUSE"]
        chk(f"{m}.J", len(J), A["primary"][m]["J"], 0)

        def fl(its, arm, cond):
            v = []
            for i in its:
                L = tab.get((i, arm, cond))
                v.append(np.nan if L is None else (0.0 if L == "REFUSE" else 1.0))
            return np.array(v)

        def est(a, b):
            ka, na = np.nansum(a), np.sum(~np.isnan(a))
            kb, nb = np.nansum(b), np.sum(~np.isnan(b))
            return hlog(ka, na) - hlog(kb, nb)

        fs, fe = fl(J, "sl_mt", "P5"), fl(J, "en_bt", "P5")
        dg = est(fs, fe)
        chk(f"{m}.DG", dg, A["primary"][m]["DG"]["est"], 1e-6)
        chk(f"{m}.flip_rate_SL_P5", float(np.nanmean(fs)), A["primary"][m]["DG"]["a"]["rate"], 1e-6)
        chk(f"{m}.flip_rate_ENBT_P5", float(np.nanmean(fe)), A["primary"][m]["DG"]["b"]["rate"], 1e-6)
        # same resampling scheme -> CI within 1e-2
        idx = np.random.default_rng(SEED).integers(0, len(J), size=(BN, len(J)))
        bs = []
        for row in idx:
            a, b = fs[row], fe[row]
            bs.append(hlog(np.nansum(a), np.sum(~np.isnan(a))) - hlog(np.nansum(b), np.sum(~np.isnan(b))))
        chk(f"{m}.DG_ci_lo", float(np.percentile(bs, 2.5)), A["primary"][m]["DG"]["ci95"][0], 1e-2)
        chk(f"{m}.DG_ci_hi", float(np.percentile(bs, 97.5)), A["primary"][m]["DG"]["ci95"][1], 1e-2)
        dgn = est(fl(J, "sl_mt", "N5"), fl(J, "en_bt", "N5"))
        chk(f"{m}.DGN", dgn, A["primary"][m]["DGN"]["est"], 1e-6)
        chk(f"{m}.DDG", dg - dgn, A["primary"][m]["DDG"]["est"], 1e-6)
        Jen = [i for i in items if tab.get((i, "en_orig", "k0")) == "REFUSE" and tab.get((i, "en_bt", "k0")) == "REFUSE"]
        chk(f"{m}.MT_noise_P5", est(fl(Jen, "en_bt", "P5"), fl(Jen, "en_orig", "P5")), A["primary"][m]["MT_noise_P5"]["est"], 1e-6)
        J3 = [i for i in J if meta[i]["in_d300"]]
        c2 = A["primary"][m].get("cross_2x2") or {}
        if c2:
            L = {k: (lambda v: hlog(np.nansum(v), np.sum(~np.isnan(v))))(fl(J3, a, c)) for k, (a, c) in
                 {"ss": ("sl_mt", "P5"), "se": ("sl_mt", "X5"), "ee": ("en_bt", "P5"), "es": ("en_bt", "X5")}.items()}
            chk(f"{m}.2x2_prompt", ((L["ss"] - L["es"]) + (L["se"] - L["ee"])) / 2, c2["prompt_effect"]["est"], 1e-6)
            chk(f"{m}.2x2_prefix", ((L["ss"] - L["se"]) + (L["es"] - L["ee"])) / 2, c2["prefix_effect"]["est"], 1e-6)
        # AUC over k/20
        auc = A["primary"][m].get("AUC", {}).get("tokens")
        if auc:
            def aucv(arm):
                xs = [0, 3 / 20, 5 / 20, 10 / 20, 1.0]
                ys = [float(np.nanmean(fl(J3, arm, c))) for c in ("k0", "P3", "P5", "P10", "P20")]
                return sum((xs[i + 1] - xs[i]) * (ys[i] + ys[i + 1]) / 2 for i in range(4))
            chk(f"{m}.AUC_SL", aucv("sl_mt"), auc["AUC_SL"], 1e-6)
            chk(f"{m}.AUC_ENBT", aucv("en_bt"), auc["AUC_EN_BT"], 1e-6)
        # per-cell refusal rates + kappa (binary R)
        for key, c in A["cells"].items():
            mm, arm, cond = key.split("|")
            if mm != m:
                continue
            rs = [r for r in rows if r["arm"] == arm and r["cond"] == cond]
            labs = [fin.get(r["key"]) for r in rs]
            labs = [x for x in labs if x]
            if labs:
                chk(f"{key}.refuse_rate", sum(x == "REFUSE" for x in labs) / len(labs), c["refuse_rate"], 1e-6)
            pairs = [(g[r["key"]] == "REFUSE", p[r["key"]] == "REFUSE") for r in rs if r["key"] in g and r["key"] in p]
            if pairs and c.get("kappa_R") is not None:
                a = np.array([x for x, _ in pairs]); b = np.array([y for _, y in pairs])
                po = np.mean(a == b); pe = np.mean(a) * np.mean(b) + np.mean(~a) * np.mean(~b)
                kap = (po - pe) / (1 - pe) if pe < 1 else (1.0 if po == 1 else 0.0)
                chk(f"{key}.kappa_R", float(kap), c["kappa_R"], 1e-6)
        # placebo 1: swap arm labels within item -> DG distribution centred at 0
        rng = np.random.default_rng(SEED + 1)
        pl = []
        for _ in range(500):
            sw = rng.random(len(J)) < 0.5
            a = np.where(sw, fe, fs); b = np.where(sw, fs, fe)
            pl.append(est(a, b))
        out["placebo"][f"{m}.arm_swap_DG"] = {"mean": float(np.mean(pl)), "ci95": [float(np.percentile(pl, 2.5)), float(np.percentile(pl, 97.5))],
                                               "observed": dg}
        # placebo 3: shuffle flips vs projection -> AUROC ~ 0.5
        li = A["mechanism"][m]["layers"].index(A["mechanism"][m]["lstar"])
        prs = [(r["proj"]["ref_last"][li], 0.0 if fin.get(r["key"]) == "REFUSE" else 1.0) for r in rows
               if r["arm"] == "sl_mt" and r["cond"] == "P5" and r["item_id"] in set(J) and "proj" in r and fin.get(r["key"])]
        if prs and 0 < sum(y for _, y in prs) < len(prs):
            s = np.array([x for x, _ in prs]); y = np.array([t for _, t in prs])
            aucs = []
            for _ in range(200):
                yy = rng.permutation(y)
                pos, neg = -s[yy == 1], -s[yy == 0]
                aucs.append(float(np.mean(pos[:, None] > neg[None, :]) + 0.5 * np.mean(pos[:, None] == neg[None, :])))
            out["placebo"][f"{m}.shuffled_auroc"] = {"mean": float(np.mean(aucs)), "ci95": [float(np.percentile(aucs, 2.5)), float(np.percentile(aucs, 97.5))]}
        per_model[m] = {"tab": tab, "J": J, "fl": fl}
    # placebo 2: swap model labels -> Sig distribution centred at 0
    if len(per_model) == 2:
        a, b = per_model["gams3_it"], per_model["gemma_it"]
        U = sorted(set(a["J"]) & set(b["J"]))
        fa, fb = a["fl"](U, "sl_mt", "P5"), b["fl"](U, "sl_mt", "P5")
        rng = np.random.default_rng(SEED + 2)
        pl = []
        for _ in range(500):
            sw = rng.random(len(U)) < 0.5
            x, y = np.where(sw, fb, fa), np.where(sw, fa, fb)
            pl.append(hlog(np.nansum(x), np.sum(~np.isnan(x))) - hlog(np.nansum(y), np.sum(~np.isnan(y))))
        out["placebo"]["model_swap_Sig_SL"] = {"mean": float(np.mean(pl)), "ci95": [float(np.percentile(pl, 2.5)), float(np.percentile(pl, 97.5))],
                                               "n_items_J_both_models": len(U)}
        ea, eg = A["primary"]["gams3_it"]["DG"]["est"], A["primary"]["gemma_it"]["DG"]["est"]
        chk("DiD_depth", (ea - eg) if (ea is not None and eg is not None) else None,
            A["cross_model"]["DiD_depth"]["est"], 1e-6)
    out["n_checks"] = len(out["checks"])
    out["n_ok"] = sum(c["ok"] for c in out["checks"])
    out["all_ok"] = out["n_ok"] == out["n_checks"]
    (R / "audit.json").write_text(json.dumps(out, indent=1))
    print(f"audit: {out['n_ok']}/{out['n_checks']} checks ok; placebos: {json.dumps(out['placebo'])[:600]}")


if __name__ == "__main__":
    main()
