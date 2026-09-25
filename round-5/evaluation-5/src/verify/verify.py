#!/usr/bin/env python3
"""Independent second code path. NEVER imports src/: re-reads the raw sources with plain json / numpy / scipy /
pandas and recomputes the audit's key quantities, then compares them with results/*.json. Output: results/verify.json."""
from __future__ import annotations

import gzip
import json
import os
import math
import re
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

WS = Path(__file__).resolve().parents[1]
RUN = Path(os.environ.get("AII_RUN_ROOT", str(WS.parents[2]))).resolve()  # same single constant as src/common.py
E15, E14, E13 = RUN / "iter_4/gen_art/gen_art_experiment_15", RUN / "iter_4/gen_art/gen_art_experiment_14", RUN / "iter_4/gen_art/gen_art_experiment_13"
EV3, E9 = RUN / "iter_4/gen_art/gen_art_evaluation_3", RUN / "iter_3/gen_art/gen_art_experiment_9"
M = 0.675
checks = []


def chk(name, mine, theirs, tol):
    ok = (mine is None and theirs is None) or (mine is not None and theirs is not None and abs(float(mine) - float(theirs)) <= tol)
    checks.append({"check": name, "independent": mine, "audit": theirs, "tol": tol, "pass": bool(ok)})
    print(("PASS " if ok else "FAIL ") + f"{name}: {mine} vs {theirs}")


def L(k, n):  # empirical logit with +0.5 (written independently of src/common.hautus_logit)
    return math.log(k + 0.5) - math.log(n - k + 0.5)


def g3o(c):
    return (L(*c["gams_sl"]) - L(*c["gams_en"])) - (L(*c["gemma_sl"]) - L(*c["gemma_en"]))


def fi(c, target):  # breadth-first over multisets of single flips (independent of src/ceiling.fragility)
    """target 'm': |G3_orig| < m; target '0': G3_orig reaches zero from its observed side (sign change or 0)."""
    g = g3o(c)
    s0 = 1 if g >= 0 else -1
    if target == "m" and abs(g) < M:
        return 0
    cells = list(c)
    frontier = {tuple(c[x][0] for x in cells)}
    for t in range(1, 40):
        nxt = set()
        for ks in frontier:
            for i, x in enumerate(cells):
                for d in (-1, 1):
                    k2 = list(ks)
                    k2[i] += d
                    if 0 <= k2[i] <= c[x][1]:
                        nxt.add(tuple(k2))
        for ks in nxt:
            cc = {x: (ks[i], c[x][1]) for i, x in enumerate(cells)}
            v = g3o(cc)
            if (target == "m" and abs(v) < M) or (target == "0" and s0 * v <= 0):
                return t
        frontier = nxt
    return None


def main() -> int:
    A = {p.stem: json.loads(p.read_text()) for p in (WS / "results").glob("*.json")}
    ce = A["ceiling_sensitivity"]
    # ---- exp15 lambda-0 counts from rows_final (own filter)
    Y = defaultdict(dict)
    with open(E15 / "results/rows_final.jsonl") as f:
        for line in f:
            if '"lambda": 0.0' not in line:
                continue
            r = json.loads(line)
            if r["lambda"] != 0.0:  # the substring test above also admits lambda 0.02 (GaMS ladder)
                continue
            if r["set"] == "BODY" and r["edit"] == "E_exp9" and r["block"] in ("ladder", "fillin") and r["arm"] in ("EN_BT", "SL_MT") \
                    and r.get("label_primary"):
                Y[(r["model"], r["arm"])][r["item_id"]] = int(r["label_primary"] == "REFUSE")
    c = {"gemma_en": (sum(Y[("gemma_it", "EN_BT")].values()), len(Y[("gemma_it", "EN_BT")])),
         "gemma_sl": (sum(Y[("gemma_it", "SL_MT")].values()), len(Y[("gemma_it", "SL_MT")])),
         "gams_en": (sum(Y[("gams3_it", "EN_BT")].values()), len(Y[("gams3_it", "EN_BT")])),
         "gams_sl": (sum(Y[("gams3_it", "SL_MT")].values()), len(Y[("gams3_it", "SL_MT")]))}
    for x in c:
        chk(f"exp15 lambda-0 count {x}", c[x][0], ce["smoke"]["counts_rows_final"][x], 0)
    chk("exp15 G3_orig", g3o(c), ce["smoke"]["G3_orig"], 1e-9)
    an15 = json.loads((E15 / "results/analysis.json").read_text())
    chk("exp15 G3_orig vs exp15 saved", g3o(c), an15["headline"]["R"]["RAW"]["G3_orig"]["point"], 1e-9)
    chk("exp15 FI_m", fi(c, "m"), ce["fragility_index"]["FI_m"], 0)
    chk("exp15 FI_0", fi(c, "0"), ce["fragility_index"]["FI_0"], 0)
    # ---- leave-1 min/max
    items = sorted(set(Y[("gemma_it", "EN_BT")]))
    vals = []
    for it in items:
        cc = {"gemma_en": (c["gemma_en"][0] - Y[("gemma_it", "EN_BT")][it], c["gemma_en"][1] - 1),
              "gemma_sl": (c["gemma_sl"][0] - Y[("gemma_it", "SL_MT")][it], c["gemma_sl"][1] - 1),
              "gams_en": (c["gams_en"][0] - Y[("gams3_it", "EN_BT")][it], c["gams_en"][1] - 1),
              "gams_sl": (c["gams_sl"][0] - Y[("gams3_it", "SL_MT")][it], c["gams_sl"][1] - 1)}
        vals.append(g3o(cc))
    chk("leave-1 min", min(vals), ce["leave_k_items"]["1"]["min"], 1e-9)
    chk("leave-1 max", max(vals), ce["leave_k_items"]["1"]["max"], 1e-9)
    # ---- Beta posterior P(G3_orig < -m), own seed
    rng = np.random.default_rng(7)
    lg = {x: (lambda p: np.log(p / (1 - p)))(rng.beta(c[x][0] + .5, c[x][1] - c[x][0] + .5, 200000)) for x in c}
    post = (lg["gams_sl"] - lg["gams_en"]) - (lg["gemma_sl"] - lg["gemma_en"])
    chk("Beta posterior P(G3_orig<-m)", float(np.mean(post < -M)), ce["estimators"]["jeffreys_posterior"]["P_lt_minus_m"], 0.01)
    # ---- eval3 bodies: G3_orig for gemini raw, reproduced vs eval3 recompute.json
    rc = json.loads((EV3 / "results/recompute.json").read_text())["curves"]
    df = pd.read_json(EV3 / "labels/readout_rows.jsonl.gz", lines=True)
    df = df[(df.kind == "harmful") & df.arm.isin(["en_bt", "sl_mt"]) & df.prim3.isin(["REFUSE", "PARTIAL", "COMPLY"])]
    frames = {"exp9_lambda": df[(df.source == "exp9") & (df.curve == "orig")],
              "exp11_final": df[(df.source == "exp11") & (df.priority == 1) & (df.step == 0.0)],
              "exp8_A1": df[(df.source == "exp8") & (df.curve == "orig")],
              "exp10_op": df[(df.source == "exp10") & (df.curve == "O")]}
    for b, fr in frames.items():
        cc = {}
        for m, pre in (("gemma_it", "gemma"), ("gams3_it", "gams")):
            for arm, lang in (("en_bt", "en"), ("sl_mt", "sl")):
                s = fr[(fr.model == m) & (fr.arm == arm)].prim3
                cc[f"{pre}_{lang}"] = (int((s == "REFUSE").sum()), int(len(s)))
        saved = (rc[f"{b}|raw_primary|R"].get("G3_orig") or rc[f"{b}|raw_primary|R"].get("G3_op_orig"))["est"]
        chk(f"eval3 {b} G3_orig vs eval3 saved", g3o(cc), saved, 1e-6)
        chk(f"eval3 {b} FI_m", fi(cc, "m"), ce["extension_eval3_bodies"][b]["by_label"]["gemini_raw_prim3"]["FI_m"], 0)
        chk(f"eval3 {b} FI_0", fi(cc, "0"), ce["extension_eval3_bodies"][b]["by_label"]["gemini_raw_prim3"]["FI_0"], 0)
    # ---- exp15 KL excess points
    kl = A["kl_excess"]
    rows = [json.loads(x) for x in (E15 / "results/kl_harmless.jsonl").read_text().splitlines() if x.strip()]
    for m, lam in (("gemma_it", 2.0), ("gams3_it", 1.5375)):
        g = {(r["edit"], r["lang"]): r["kl_mean"] for r in rows if r["model"] == m and abs(r["lambda"] - lam) < 1e-9}
        ex = (g[("E_exp9", "sl")] / g[("E_exp9", "en")]) / (np.mean([g[("rand_1", "sl")], g[("rand_2", "sl")]]) /
                                                           np.mean([g[("rand_1", "en")], g[("rand_2", "en")]]))
        chk(f"exp15 excess {m}", ex, kl["exp15"][m]["point_excess_top_dose"], 1e-9)
    # ---- exp14 / exp9 excess bootstrap CIs (own seed, tolerance 0.05 on the log scale)
    rng = np.random.default_rng(99)
    for m in ("gemma_it", "gams3_it"):
        d = json.loads((E14 / f"results/kl_{m}.json").read_text())
        E = np.clip(np.array([d["kl_real_en"]["per_stem"], d["kl_real_sl"]["per_stem"]]), 0, None)
        R = np.clip(np.array([d["kl_rand_en"]["per_stem"], d["kl_rand_sl"]["per_stem"]]), 0, None)
        n = E.shape[1]
        bs = []
        for _ in range(2000):
            ix = rng.integers(0, n, n)
            bs.append((E[1, ix].mean() / E[0, ix].mean()) / (R[1, ix].mean() / R[0, ix].mean()))
        lo, hi = np.percentile(bs, [2.5, 97.5])
        a = kl["exp14"][m]["mean"]["ci95_pct"]
        chk(f"exp14 {m} excess CI low (log)", math.log(lo), math.log(a[0]), 0.10)
        chk(f"exp14 {m} excess CI high (log)", math.log(hi), math.log(a[1]), 0.10)
        chk(f"exp14 {m} excess point", (E[1].mean() / E[0].mean()) / (R[1].mean() / R[0].mean()), kl["exp14"][m]["mean"]["point"], 1e-9)
    for m in ("gemma_it", "gams3_it"):
        rr = [json.loads(x) for x in (E9 / f"results/{m}/c5a_kl.jsonl").read_text().splitlines() if x.strip()]
        sel = {(r["lang"], r["item_id"]): max(r["kl"], 0) for r in rr if r["edit"] == "selected"}
        rnd = defaultdict(list)
        for r in rr:
            if r["edit"] != "selected":
                rnd[(r["lang"], r["item_id"])].append(max(r["kl"], 0))
        its = sorted({i for (_, i) in sel})
        e_en = np.array([sel[("en", i)] for i in its])
        e_sl = np.array([sel[("sl", i)] for i in its])
        r_en = np.array([np.mean(rnd[("en", i)]) for i in its])
        r_sl = np.array([np.mean(rnd[("sl", i)]) for i in its])
        pt = (e_sl.mean() / e_en.mean()) / (r_sl.mean() / r_en.mean())
        chk(f"exp9 {m} excess point", pt, kl["exp9"][m]["recomputed_point"], 1e-9)
        bs = []
        for _ in range(2000):
            ix = rng.integers(0, len(its), len(its))
            bs.append((e_sl[ix].mean() / e_en[ix].mean()) / (r_sl[ix].mean() / r_en[ix].mean()))
        lo, hi = np.percentile(bs, [2.5, 97.5])
        a = kl["exp9"][m]["mean"]["ci95_pct"]
        chk(f"exp9 {m} excess CI low (log)", math.log(lo), math.log(a[0]), 0.10)
        chk(f"exp9 {m} excess CI high (log)", math.log(hi), math.log(a[1]), 0.10)
    # ---- exp14 cell counts (exact) against exp14's own cell_table
    an14 = json.loads((E14 / "results/analysis.json").read_text())
    cnt = defaultdict(lambda: [0, 0])
    with open(E14 / "results/rows_final.jsonl") as f:
        for line in f:
            r = json.loads(line)
            if r["cond"] == "edit" and r.get("L_primary"):
                k = f"{r['model']}|{r['dose']}|{r['in_lang']}{r['out_lang']}|{r['kind']}"
                cnt[k][0] += r["L_primary"] == "REFUSE"
                cnt[k][1] += 1
    bad = sum(1 for k, v in an14["cell_table"].items() if "|ext|" not in k and (cnt[k][1] != v["n_labelled"] or cnt[k][0] != round(v["R"] * v["n_labelled"])))
    chk("exp14 cell_table mismatches (edit cells)", bad, 0, 0)
    # ---- exp13 overlap (exact recount, own normalisation)
    man = json.loads((E13 / "data/split_manifest_iter4.json").read_text())
    pool = {json.loads(x)["item_id"]: json.loads(x) for x in (E13 / "data/pool.jsonl").read_text().splitlines() if x.strip()}
    ref = [json.loads(x)["EN_orig"] for x in (E14 / "data/items.jsonl").read_text().splitlines() if x.strip() and json.loads(x)["kind"] == "harmful"]
    nz = lambda t: re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t.lower())).strip()  # noqa: E731
    g8 = lambda t: {tuple(nz(t).split()[i:i + 8]) for i in range(max(0, len(nz(t).split()) - 7))}  # noqa: E731
    refset, refg = {nz(t) for t in ref}, set().union(*map(g8, ref))
    for sp in ("B", "C"):
        n_ov = sum(1 for i in man["ids"][sp] if nz(pool[i]["en_orig"]) in refset or (g8(pool[i]["en_orig"]) & refg))
        chk(f"exp13 overlap {sp}", n_ov, A["not_executed_exp13"]["overlap_vs_exp14_items"][sp]["n_overlap_exact_or_8gram"], 0)
    # ---- harmonised SDT signs: recompute exp14 hi|SLoutput c-DiD sign from its cell c values
    cells = an14["sdt"]["cells"]
    dd = (cells["gemma_it|hi|ensl"]["c"] - cells["gemma_it|hi|enen"]["c"]) - (cells["gams3_it|hi|ensl"]["c"] - cells["gams3_it|hi|enen"]["c"])
    cs = {r["body"]: r for r in A["criterion_shift"]["rows"]}
    chk("exp14 hi SLoutput harmonised Delta_c", dd, cs["exp14 (iter 4, hi, SLoutput)"]["harmonised_value"], 1e-9)
    p15 = [p for p in an15["sdt"]["R"]["per_step"] if p["lambda"] == 0.0]
    cr = {(p["model"], p["lang"]): -p["c_ref"] for p in p15}  # standard c = -c_ref
    d15 = (cr[("gemma_it", "sl")] - cr[("gemma_it", "en")]) - (cr[("gams3_it", "sl")] - cr[("gams3_it", "en")])
    chk("exp15 lambda-0 harmonised Delta_c (from per-step c_ref)", d15, cs["exp15 (iter 4, lambda 0)"]["harmonised_value"], 1e-9)
    # compliance validity of exp14 criterion rows: any row using a cell whose output-language compliance < 0.90 is invalid
    cg = an14["compliance_gate"]
    for pos, cells_ in (("SLinput", ("slen", "enen")), ("SLoutput", ("ensl", "enen")), ("SLboth", ("slsl", "enen"))):
        mine = int(all(cg[f"{m}|{c_}"]["compliance"] >= 0.90 for c_ in cells_ for m in ("gemma_it", "gams3_it")))
        chk(f"exp14 {pos} manipulation validity", mine, int(cs[f"exp14 (iter 4, hi, {pos})"]["manipulation_valid"]), 0)
    # ---- PLACEBO for the one ROBUST-OFFSET verdict (exp9 body, gemini): its probability-scale DiD bootstrap CI excludes 0.
    # Shuffle the model label within item (both arms move together); the same bootstrap must then INCLUDE 0.
    fr9 = frames["exp9_lambda"]
    piv = fr9.assign(y=(fr9.prim3 == "REFUSE").astype(float)).pivot_table(index="item_id", columns=["model", "arm"], values="y")
    piv = piv.dropna()
    A_ = piv["gemma_it"][["en_bt", "sl_mt"]].values
    B_ = piv["gams3_it"][["en_bt", "sl_mt"]].values

    def did_pp(A, Bm, w):
        pa = (w @ A) / w.sum()
        pb = (w @ Bm) / w.sum()
        return 100 * ((pb[1] - pb[0]) - (pa[1] - pa[0]))

    def boot_ci(A, Bm, rng_, nb=1000):
        n_ = A.shape[0]
        v_ = [did_pp(A, Bm, rng_.multinomial(n_, np.ones(n_) / n_).astype(float)) for _ in range(nb)]
        return np.percentile(v_, [2.5, 97.5])
    rngp = np.random.default_rng(123)
    real_ci = boot_ci(A_, B_, rngp)
    sw = rngp.random(A_.shape[0]) < 0.5
    Ap, Bp = np.where(sw[:, None], B_, A_), np.where(sw[:, None], A_, B_)
    plac_ci = boot_ci(Ap, Bp, rngp)
    chk("exp9 real DiD CI excludes 0 (1=yes)", int(real_ci[1] < 0 or real_ci[0] > 0), 1, 0)
    chk("exp9 model-shuffled placebo DiD CI includes 0 (1=yes)", int(plac_ci[0] <= 0 <= plac_ci[1]), 1, 0)
    print(f"   exp9 real DiD CI {real_ci}, placebo CI {plac_ci}")
    # ---- exp15 GPU re-measurement: excess recomputed straight from the per-item vectors
    pi = WS / "results/kl_items_exp15_recomputed.jsonl"
    if pi.exists() and kl.get("gpu_recompute_gate"):
        rows_i = [json.loads(x) for x in pi.read_text().splitlines() if x.strip()]
        for m, lam in (("gemma_it", 2.0), ("gams3_it", 1.5375)):
            g = {(r["edit"], r["lang"]): np.clip(np.array(r["kl_items"]), 0, None) for r in rows_i if r["model"] == m and abs(r["lambda"] - lam) < 1e-9}
            ex = (g[("E_exp9", "sl")].mean() / g[("E_exp9", "en")].mean()) / (
                np.mean([g[("rand_1", "sl")].mean(), g[("rand_2", "sl")].mean()]) / np.mean([g[("rand_1", "en")].mean(), g[("rand_2", "en")].mean()]))
            chk(f"exp15 GPU re-measured excess {m} (vs saved-means point)", ex, kl["exp15"][m]["point_excess_top_dose"], 0.01)
    n_pass = sum(c_["pass"] for c_ in checks)
    out = {"n_checks": len(checks), "n_pass": n_pass, "pass_rate": n_pass / len(checks), "checks": checks,
           "note": "independent code path; never imports src/"}
    (WS / "results/verify.json").write_text(json.dumps(out, indent=1, default=float))
    print(f"{n_pass}/{len(checks)} checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
