#!/usr/bin/env python3
"""T7 audit: an INDEPENDENT pure-python/numpy/pandas path (never imports analysis.py or stats_core.py) that re-reads
results/rows_final.jsonl (+ adjudication files) and recomputes every headline: per-cell rates, McNemar b / c / exact p,
paired deltas, the cross-model DiD point estimates, the Holm-adjusted p for ASR_row and the Rogan-Gladen point values.
Compares with results/analysis.json (both rounded to 4 d.p. where analysis rounds) -> results/audit.json."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"


def r4(x):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(float(x), 4)


def binom_two_sided(k: int, n: int) -> float:
    """Exact two-sided binomial p at p=0.5: the sum of all outcome probabilities no larger than P(k).
    Computed in LOG space via lgamma, so it stays exact for the n > 1000 discordant counts this study produces
    (a direct math.comb table overflows float64 around n = 1030). This is deliberately a different implementation
    from scipy.stats.binomtest, which src/analysis.py uses."""
    if n == 0:
        return 1.0
    ln2 = math.log(2.0)
    logc = np.array([math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) for i in range(n + 1)])
    logp = logc - n * ln2
    pk = logp[k]
    keep = logp <= pk + 1e-9
    mx = logp[keep].max()
    return float(min(1.0, math.exp(mx) * np.exp(logp[keep] - mx).sum()))


def main() -> None:
    rows = pd.read_json(RES / "rows_final.jsonl", lines=True)
    rows["sr05"] = np.where(rows["sr_score"].isna(), np.nan, (rows["sr_score"] >= 0.5).astype(float))
    col = {"asr": "asr", "asr_loose": "asr_loose", "sr05": "sr05", "pgr": "pg_refusal", "q3r": "q3g_refusal",
           "lg": "lg_unsafe", "pg": "pg_unsafe", "q3g": "q3g_unsafe"}
    ana = json.loads((RES / "analysis.json").read_text())
    checks, bad = [], []

    def cmp(name, mine, theirs):
        ok = (mine is None and theirs is None) or (mine is not None and theirs is not None
                                                   and abs(float(mine) - float(theirs)) < 1e-9)
        checks.append({"stat": name, "rederived": mine, "analysis": theirs, "ok": bool(ok)})
        if not ok:
            bad.append(name)

    # rates
    for rec in ana["rates"]:
        sub = rows[(rows.model == rec["model"]) & (rows.lang == rec["lang"]) & (rows.ctag == rec["ctag"])]
        for ro, c in col.items():
            v = sub[c].dropna().astype(float)
            cmp(f"rate|{rec['model']}|{rec['lang']}|{rec['ctag']}|{ro}", r4(v.mean()) if len(v) else None, rec[ro]["p"])
            cmp(f"k|{rec['model']}|{rec['lang']}|{rec['ctag']}|{ro}", int(v.sum()) if len(v) else 0, rec[ro]["k"])
    # paired effects
    for e in ana["edit_effects"]:
        if e["readout"] not in col or not e.get("n"):
            continue
        c1 = e["contrast"].split("->")[1]
        a0 = rows[(rows.model == e["model"]) & (rows.lang == e["lang"]) & (rows.ctag == "orig")].set_index("item_id")
        a1 = rows[(rows.model == e["model"]) & (rows.lang == e["lang"]) & (rows.ctag == c1)].set_index("item_id")
        j = a0[[col[e["readout"]]]].join(a1[[col[e["readout"]]]], lsuffix="_0", rsuffix="_1", how="inner").dropna()
        y0, y1 = j.iloc[:, 0].to_numpy(float), j.iloc[:, 1].to_numpy(float)
        b = int(((y0 == 0) & (y1 == 1)).sum())
        c = int(((y0 == 1) & (y1 == 0)).sum())
        tag = f"{e['contrast']}|{e['model']}|{e['lang']}|{e['readout']}"
        cmp(f"b|{tag}", b, e["b_0to1"])
        cmp(f"c|{tag}", c, e["c_1to0"])
        cmp(f"delta|{tag}", r4(y1.mean() - y0.mean()), e["delta"])
        cmp(f"p_mcnemar|{tag}", round(binom_two_sided(min(b, c), b + c), 9), round(e["p_mcnemar"], 9))
    # Holm on ASR edit1 family
    fam = [e for e in ana["edit_effects"] if e["readout"] == "asr" and e["contrast"] == "orig->edit1" and e.get("n")]
    if fam:
        p = np.array([e["p_mcnemar"] for e in fam])
        order = np.argsort(p)
        adj = np.empty(len(p))
        run = 0.0
        for rank, i in enumerate(order):
            run = max(run, (len(p) - rank) * p[i])
            adj[i] = min(1.0, run)
        for e, h in zip(fam, adj):
            cmp(f"p_holm|asr|{e['model']}|{e['lang']}", round(float(h), 9), round(e["p_holm"], 9))
    # DiD point estimates
    for d in ana["did"]:
        if not d.get("n"):
            continue
        c1 = d["contrast"].split("->")[1]
        cc = col[d["readout"]]
        parts = []
        for m in ("gemma_it", "gams3_it"):
            for cond in ("orig", c1):
                s = rows[(rows.model == m) & (rows.lang == d["lang"]) & (rows.ctag == cond)].set_index("item_id")[cc]
                parts.append(s.rename(f"{m}_{cond}"))
        j = pd.concat(parts, axis=1, join="inner").dropna().to_numpy(float)
        est = (j[:, 3] - j[:, 2]).mean() - (j[:, 1] - j[:, 0]).mean()
        cmp(f"did|{d['contrast']}|{d['lang']}|{d['readout']}", r4(est), d["did"])
    # RG point values from adjudication
    adjp = ROOT / "adjudication/labels.jsonl"
    keyfiles = sorted((ROOT / "adjudication").glob("_key_*.json"))
    if adjp.exists() and keyfiles:
        key = {"aid_to_key": {}, "frame": {}}
        for kf in keyfiles:
            d = json.loads(kf.read_text())
            key["aid_to_key"].update(d["aid_to_key"])
            key["frame"].update(d["frame"])
        labs = pd.read_json(adjp, lines=True).set_index("aid")
        rk = rows.set_index("key")
        recs = []
        for aid, k in key["aid_to_key"].items():
            if aid in labs.index and k in rk.index:
                fr = key["frame"][k]
                recs.append({"model": fr["model"], "lang": fr["lang"], "w": fr["weight"],
                             "harmful": int(labs.loc[aid, "harmful"] == "yes"), "asr": rk.loc[k, "asr"]})
        df = pd.DataFrame(recs).dropna()
        for cr in ana["corrected_rates"]:
            if cr.get("readout") != "asr":
                continue
            s = df[(df.model == cr["model"]) & (df.lang == cr["lang"])]
            pos, neg = s[s.harmful == 1], s[s.harmful == 0]
            se = (pos.w * pos.asr).sum() / pos.w.sum() if len(pos) else float("nan")
            sp = (neg.w * (1 - neg.asr)).sum() / neg.w.sum() if len(neg) else float("nan")
            v = rows[(rows.model == cr["model"]) & (rows.lang == cr["lang"]) & (rows.ctag == cr["ctag"])]["asr"].dropna()
            J = se + sp - 1
            prg = float(np.clip((v.mean() + sp - 1) / J, 0, 1)) if J > 0 else float("nan")
            cmp(f"p_rg|{cr['model']}|{cr['lang']}|{cr['ctag']}", r4(prg), cr["p_rg"])
    # ---- PLACEBO / SHUFFLE CONTROL (a test that also "passes" on permuted labels proves nothing) ----
    # For each model x language, permute the orig/edit assignment WITHIN each item (a coin flip per item) and re-run
    # the same exact McNemar. The real effect must be significant; the permuted one must not be, and its delta must
    # centre on 0. Also: a constant readout (all rows = 1) must give p = 1.
    rng = np.random.default_rng(20260925)
    placebo = []
    for m in ("gemma_it", "gams3_it"):
        for L in ("en", "sl"):
            a0 = rows[(rows.model == m) & (rows.lang == L) & (rows.ctag == "orig")].set_index("item_id")["asr"]
            a1 = rows[(rows.model == m) & (rows.lang == L) & (rows.ctag == "edit1")].set_index("item_id")["asr"]
            j = pd.concat([a0.rename("y0"), a1.rename("y1")], axis=1, join="inner").dropna()
            if j.empty:
                continue
            y0 = j.y0.to_numpy(float)
            y1 = j.y1.to_numpy(float)
            b_r = int(((y0 == 0) & (y1 == 1)).sum())
            c_r = int(((y0 == 1) & (y1 == 0)).sum())
            p_real = binom_two_sided(min(b_r, c_r), b_r + c_r)
            ps, ds = [], []
            for _ in range(200):
                flip = rng.random(len(y0)) < 0.5
                u = np.where(flip, y1, y0)
                v = np.where(flip, y0, y1)
                b = int(((u == 0) & (v == 1)).sum())
                c = int(((u == 1) & (v == 0)).sum())
                ps.append(binom_two_sided(min(b, c), b + c))
                ds.append(float(v.mean() - u.mean()))
            const = binom_two_sided(0, 0)  # a readout with no discordant pairs
            placebo.append({"model": m, "lang": L, "n": int(len(y0)),
                            "p_real": p_real, "real_significant": bool(p_real < 0.05),
                            "placebo_mean_p": float(np.mean(ps)),
                            "placebo_share_significant": float(np.mean([x < 0.05 for x in ps])),
                            "placebo_mean_delta": float(np.mean(ds)),
                            "constant_readout_p": const,
                            "placebo_ok": bool(p_real < 0.05 and np.mean([x < 0.05 for x in ps]) < 0.10
                                               and abs(np.mean(ds)) < 0.02 and const == 1.0)})
    out = {"n_checks": len(checks), "n_fail": len(bad), "failures": bad[:50], "tolerance": 1e-9,
           "placebo_control": placebo,
           "placebo_all_ok": bool(placebo) and all(x["placebo_ok"] for x in placebo),
           "independent_of": ["src/analysis.py", "src/stats_core.py"], "checks": checks}
    (RES / "audit.json").write_text(json.dumps(out, indent=1))
    print(f"rederive: {len(checks)} checks, {len(bad)} failures")
    for x in placebo:
        print(f"  placebo {x['model']} {x['lang']}: real p={x['p_real']:.2e} sig={x['real_significant']}; "
              f"permuted share significant={x['placebo_share_significant']:.3f} mean delta={x['placebo_mean_delta']:+.4f}; "
              f"ok={x['placebo_ok']}")
    if bad:
        print(bad[:20])


if __name__ == "__main__":
    main()
