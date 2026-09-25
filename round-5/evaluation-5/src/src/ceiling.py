#!/usr/bin/env python3
"""STEP 1 - ceiling sensitivity of the lambda-0 baseline component G3_orig (exp15 + every eval3 body).

G3_orig = M0_GaMS - M0_Gemma, M0 = logit_H(SL refusal) - logit_H(EN refusal) at lambda 0 (R coding).
Fragility index (Walsh 2014), paired exact view, leave-k-items, genuinely different extreme-proportion estimators,
item bootstrap + model-label permutation, expected judge-error count, extension to eval3 bodies.
"""
from __future__ import annotations

import itertools
import math
from collections import defaultdict

import numpy as np
import pandas as pd
from loguru import logger
from scipy import special, stats

from common import (B, EVAL3, EXP15, M, MODELS, RES, SEED, clean, hautus_logit, pct_ci, read_json, read_jsonl, rel,
                    setup_logging, wilson, write_json)

CELLS = ("gemma_en", "gemma_sl", "gams_en", "gams_sl")


# ------------------------------------------------------------------ core formulas
def g3_orig_counts(k: dict, n: dict, est: str = "hautus") -> float:
    """k, n keyed by CELLS. Estimators on the logit scale."""
    def L(kk, nn):
        if est == "hautus":
            return float(hautus_logit(kk, nn))
        if est == "laplace":
            p = (kk + 1) / (nn + 2)
            return math.log(p / (1 - p))
        if est == "half_n":  # 1/(2N) rule, only for cells at 0 or n (Macmillan & Kaplan 1985)
            p = kk / nn
            if kk <= 0:
                p = 1 / (2 * nn)
            elif kk >= nn:
                p = 1 - 1 / (2 * nn)
            return math.log(p / (1 - p))
        if est == "jeffreys_logit_mean":  # E[logit p] under Beta(k+.5, n-k+.5)
            return float(special.digamma(kk + 0.5) - special.digamma(nn - kk + 0.5))
        raise ValueError(est)
    m_gemma = L(k["gemma_sl"], n["gemma_sl"]) - L(k["gemma_en"], n["gemma_en"])
    m_gams = L(k["gams_sl"], n["gams_sl"]) - L(k["gams_en"], n["gams_en"])
    return m_gams - m_gemma


def prob_did(k: dict, n: dict) -> float:
    """probability-scale DiD in percentage points: (pS-pE)_GaMS - (pS-pE)_Gemma."""
    d = lambda a, b: k[a] / n[a] - k[b] / n[b]  # noqa: E731
    return 100 * (d("gams_sl", "gams_en") - d("gemma_sl", "gemma_en"))


def fragility(k: dict, n: dict, est: str = "hautus", max_flips: int = 40) -> dict:
    """Exact minimum number of single-label flips (REFUSE <-> non-REFUSE, k bounded to [0, n]) that bring G3_orig
    inside (-m, +m) [FI_m] and to zero from its observed side, i.e. a sign change [FI_0]; plus the best reachable G3_orig per flip budget (trajectory)."""
    g0 = g3_orig_counts(k, n, est)
    sign = 1.0 if g0 < 0 else -1.0  # move toward zero
    res = {"G3_orig": g0, "FI_m": None, "FI_0": None, "trajectory": [], "path_at_FI_m": None, "path_at_FI_0": None}
    if abs(g0) < M:
        res["FI_m"] = 0
    if (g0 >= 0 and sign > 0) or (g0 <= 0 and sign < 0):
        res["FI_0"] = 0
    for t in range(0, max_flips + 1):
        best, best_d = -np.inf, None
        # all 4-tuples of signed deltas with sum |d| = t
        for parts in _compositions(t, 4):
            for signs in itertools.product((-1, 1), repeat=4):
                if any(p == 0 and s < 0 for p, s in zip(parts, signs)):
                    continue
                d = {c: s * p for c, p, s in zip(CELLS, parts, signs)}
                kk = {c: k[c] + d[c] for c in CELLS}
                if any(kk[c] < 0 or kk[c] > n[c] for c in CELLS):
                    continue
                g = sign * g3_orig_counts(kk, n, est)
                if g > best:
                    best, best_d = g, d
        gval = sign * best
        res["trajectory"].append({"flips": t, "best_G3_orig": gval, "deltas": best_d})
        if res["FI_m"] is None and abs(gval) < M:
            res["FI_m"], res["path_at_FI_m"] = t, best_d
        if res["FI_0"] is None and sign * gval >= 0:
            res["FI_0"], res["path_at_FI_0"] = t, best_d
        if res["FI_m"] is not None and res["FI_0"] is not None and t >= res["FI_0"] + 1:
            break
    return res


def _compositions(t: int, parts: int):
    if parts == 1:
        yield (t,)
        return
    for i in range(t + 1):
        for rest in _compositions(t - i, parts - 1):
            yield (i,) + rest


# ------------------------------------------------------------------ exp15 lambda-0 matrices
def exp15_matrices() -> tuple[dict, list[str], dict]:
    """Y[model] = [items, 2] (EN_BT, SL_MT) binary REFUSE at lambda 0 using analysis.py's Cube filter."""
    rows = read_jsonl(EXP15 / "results/rows_final.jsonl")
    sel = [r for r in rows if r["set"] == "BODY" and r["edit"] == "E_exp9" and r["block"] in ("ladder", "fillin")
           and r["arm"] in ("EN_BT", "SL_MT") and round(r["lambda"], 4) == 0.0 and r.get("label_primary") is not None]
    del rows
    items = sorted({r["item_id"] for r in sel})
    ii = {x: i for i, x in enumerate(items)}
    Y = {m: np.full((len(items), 2), np.nan) for m in MODELS}
    adj = {m: np.full((len(items), 2), np.nan) for m in MODELS}
    for r in sel:
        a = 0 if r["arm"] == "EN_BT" else 1
        Y[r["model"]][ii[r["item_id"]], a] = float(r["label_primary"] == "REFUSE")
        if r.get("label_adjudication") in ("REFUSE", "PARTIAL", "COMPLY", "OFF_TASK"):
            adj[r["model"]][ii[r["item_id"]], a] = float(r["label_adjudication"] in ("REFUSE", "OFF_TASK"))
    return Y, items, adj


def counts_of(Y: dict, w: np.ndarray | None = None) -> tuple[dict, dict]:
    k, n = {}, {}
    for m, pre in (("gemma_it", "gemma"), ("gams3_it", "gams")):
        y = Y[m]
        obs = ~np.isnan(y)
        ww = np.ones(y.shape[0]) if w is None else w
        k[f"{pre}_en"] = float(ww @ np.where(obs[:, 0], y[:, 0], 0))
        k[f"{pre}_sl"] = float(ww @ np.where(obs[:, 1], y[:, 1], 0))
        n[f"{pre}_en"] = float(ww @ obs[:, 0])
        n[f"{pre}_sl"] = float(ww @ obs[:, 1])
    return k, n


def paired_view(Y: dict) -> dict:
    out = {}
    for m in MODELS:
        y = Y[m]
        ok = ~np.isnan(y).any(1)
        en, sl = y[ok, 0], y[ok, 1]
        b = int(((sl == 1) & (en == 0)).sum())
        c = int(((en == 1) & (sl == 0)).sum())
        nn = int(ok.sum())
        p_mc = float(stats.binomtest(b, b + c, 0.5).pvalue) if b + c > 0 else 1.0
        diff = (sl.sum() - en.sum()) / nn
        out[m] = {"n_pairs": nn, "b_SLrefuse_ENnot": b, "c_ENrefuse_SLnot": c,
                  "a_both_refuse": int(((sl == 1) & (en == 1)).sum()), "d_neither": int(((sl == 0) & (en == 0)).sum()),
                  "mcnemar_exact_p": p_mc, "pp_SL_minus_EN": 100 * diff,
                  "newcombe_paired_ci_pp": [100 * x for x in newcombe_paired(int(((sl == 1) & (en == 1)).sum()), b, c,
                                                                         int(((sl == 0) & (en == 0)).sum()))],
                  "cond_logit_ln_b_over_c": _lnor(b, c), "cond_logit_exact_ci": _lnor_ci(b, c)}
    return out


def newcombe_paired(a: int, b: int, c: int, d: int, z: float = 1.96) -> list[float]:
    """Newcombe (1998) method 10: paired difference p1 - p2 with p1 = (a+b)/n (SL), p2 = (a+c)/n (EN)."""
    n = a + b + c + d
    p1, p2 = (a + b) / n, (a + c) / n
    l1, u1 = wilson(a + b, n, z)
    l2, u2 = wilson(a + c, n, z)
    num = (a + b) * (c + d) * (a + c) * (b + d)
    if num == 0:
        phi = 0.0
    else:
        A = a * d - b * c
        A = max(A - n / 2, 0) if A > 0 else A
        phi = A / math.sqrt(num)
    dd = p1 - p2
    dl = math.sqrt(max((p1 - l1) ** 2 - 2 * phi * (p1 - l1) * (u2 - p2) + (u2 - p2) ** 2, 0))
    du = math.sqrt(max((u1 - p1) ** 2 - 2 * phi * (u1 - p1) * (p2 - l2) + (p2 - l2) ** 2, 0))
    return [dd - dl, dd + du]


def _lnor(b: float, c: float) -> float:
    return math.log((b + 0.5) / (c + 0.5)) if (b == 0 or c == 0) else math.log(b / c)


def _lnor_ci(b: int, c: int) -> list[float | None]:
    """exact CI for ln(b/c) from the Clopper-Pearson interval of b/(b+c)."""
    nn = b + c
    if nn == 0:
        return [None, None]
    lo = stats.beta.ppf(0.025, b, c + 1) if b > 0 else 0.0
    hi = stats.beta.ppf(0.975, b + 1, c) if c > 0 else 1.0
    f = lambda p: (math.log(p / (1 - p)) if 0 < p < 1 else (-math.inf if p <= 0 else math.inf))  # noqa: E731
    return [f(lo), f(hi)]


# ------------------------------------------------------------------ leave-k
def leave_k(Y: dict, rng: np.random.Generator, n_random: int, ks=(1, 2, 3, 4, 5)) -> dict:
    """Remove k ITEMS (from both models and both arms); G3_orig (Hautus) distribution over subsets."""
    nI = Y["gemma_it"].shape[0]
    # per-item contributions to the 4 cells
    C = np.stack([np.nan_to_num(Y["gemma_it"][:, 0]), np.nan_to_num(Y["gemma_it"][:, 1]),
                  np.nan_to_num(Y["gams3_it"][:, 0]), np.nan_to_num(Y["gams3_it"][:, 1])], 1)
    O = np.stack([~np.isnan(Y["gemma_it"][:, 0]), ~np.isnan(Y["gemma_it"][:, 1]),
                  ~np.isnan(Y["gams3_it"][:, 0]), ~np.isnan(Y["gams3_it"][:, 1])], 1).astype(float)
    K, N = C.sum(0), O.sum(0)

    def g_of(kk, nn):
        L = hautus_logit(kk, nn)
        return (L[..., 3] - L[..., 2]) - (L[..., 1] - L[..., 0])

    out = {}
    disc_b = np.where((Y["gemma_it"][:, 1] == 1) & (Y["gemma_it"][:, 0] == 0))[0]
    for k in ks:
        if k <= 2:
            idx = np.array(list(itertools.combinations(range(nI), k)))
            mode = "exhaustive"
        else:
            idx = np.array([rng.choice(nI, k, replace=False) for _ in range(n_random)])
            mode = f"random_{n_random}"
        kk = K[None, :] - C[idx].sum(1)
        nn = N[None, :] - O[idx].sum(1)
        g = g_of(kk, nn)
        wc_items = disc_b[:k] if len(disc_b) >= k else disc_b
        wc = None
        if len(wc_items):
            wc = float(g_of(K - C[wc_items].sum(0), N - O[wc_items].sum(0)))
        out[str(k)] = {"mode": mode, "n_subsets": int(len(g)), "min": float(g.min()),
                       "p05": float(np.percentile(g, 5)), "p50": float(np.percentile(g, 50)),
                       "p95": float(np.percentile(g, 95)), "max": float(g.max()),
                       "share_inside_m": float(np.mean(np.abs(g) < M)), "share_ge_0": float(np.mean(g >= 0)),
                       "worst_case_remove_gemma_discordant_b": wc,
                       "worst_case_items_removed": int(len(wc_items))}
    return out


# ------------------------------------------------------------------ estimators, bootstrap, permutation
def estimator_sweep(k: dict, n: dict, rng: np.random.Generator, n_draws: int = 200_000) -> dict:
    est = {"i_hautus_loglinear": g3_orig_counts(k, n, "hautus"),
           "ii_laplace_add1": g3_orig_counts(k, n, "laplace"),
           "iii_half_n_rule_extreme_cells_only": g3_orig_counts(k, n, "half_n"),
           "iv_jeffreys_posterior_mean_of_logit": g3_orig_counts(k, n, "jeffreys_logit_mean")}
    draws = {c: rng.beta(k[c] + 0.5, n[c] - k[c] + 0.5, n_draws) for c in CELLS}
    lg = {c: np.log(draws[c] / (1 - draws[c])) for c in CELLS}
    post = (lg["gams_sl"] - lg["gams_en"]) - (lg["gemma_sl"] - lg["gemma_en"])
    posterior = {"n_draws": n_draws, "mean": float(post.mean()), "median": float(np.median(post)),
                 "cri95": [float(np.percentile(post, 2.5)), float(np.percentile(post, 97.5))],
                 "P_lt_minus_m": float(np.mean(post < -M)), "P_lt_0": float(np.mean(post < 0))}
    return {"point": est, "jeffreys_posterior": posterior,
            "identity_note": "Hautus log-linear, the Jeffreys posterior MEAN of p and the Haldane-Anscombe empirical "
                             "logit give the SAME logit ln((k+.5)/(n-k+.5)); they are one estimator, not three."}


def bootstrap_all(Y: dict, rng: np.random.Generator, n_boot: int = B) -> dict:
    nI = Y["gemma_it"].shape[0]
    dr = defaultdict(list)
    for _ in range(n_boot):
        w = rng.multinomial(nI, np.ones(nI) / nI).astype(float)
        k, n = counts_of(Y, w)
        for e in ("hautus", "laplace", "half_n", "jeffreys_logit_mean"):
            dr[e].append(g3_orig_counts(k, n, e))
        dr["prob_did_pp"].append(prob_did(k, n))
        lo = {}
        for m in MODELS:
            y = Y[m]
            b = float(w @ ((y[:, 1] == 1) & (y[:, 0] == 0)))
            c = float(w @ ((y[:, 0] == 1) & (y[:, 1] == 0)))
            lo[m] = _lnor(b, c)
        dr["cond_logit_diff"].append(lo["gams3_it"] - lo["gemma_it"])
    return {e: {"ci95": pct_ci(v), "ci90": pct_ci(v, 5, 95), "se": float(np.nanstd(v, ddof=1)),
                "share_draws_inside_m": float(np.mean(np.abs(np.asarray(v)) < M)) if e != "prob_did_pp" else None}
            for e, v in dr.items()}


def permutation(Y: dict, rng: np.random.Generator, n_perm: int = 5000) -> dict:
    """swap the model label within item (both arms move together)."""
    k0, n0 = counts_of(Y)
    obs = g3_orig_counts(k0, n0)
    A, Bm = Y["gemma_it"], Y["gams3_it"]
    null = []
    for _ in range(n_perm):
        s = rng.random(A.shape[0]) < 0.5
        YA = np.where(s[:, None], Bm, A)
        YB = np.where(s[:, None], A, Bm)
        k, n = counts_of({"gemma_it": YA, "gams3_it": YB})
        null.append(g3_orig_counts(k, n))
    null = np.array(null)
    return {"observed": obs, "n_perm": n_perm, "null_mean": float(null.mean()), "null_sd": float(null.std(ddof=1)),
            "p_two_sided": float((np.sum(np.abs(null) >= abs(obs)) + 1) / (n_perm + 1))}


def verdict_of(fi_m: int | None, est_range: list[float], did_ci: list | None, g0: float) -> str:
    if abs(g0) < M or g0 >= 0:
        return "NOT-OUTSIDE-MARGIN"
    spans = min(est_range) < -M < max(est_range)
    if (fi_m is not None and fi_m <= 2) or spans:
        return "CEILING-ARTEFACT"
    did_excl0 = did_ci is not None and None not in did_ci and (did_ci[0] > 0 or did_ci[1] < 0)
    if fi_m is not None and fi_m >= 5 and did_excl0 and max(est_range) < -M:
        return "ROBUST-OFFSET"
    return "FRAGILE"


# ------------------------------------------------------------------ judge error (1f)
def judge_error(an15: dict, k: dict, n: dict) -> dict:
    cells = an15.get("judge_validity", {}).get("cells", {})
    out = {"source": rel(EXP15 / "results/analysis.json") + " :: judge_validity/cells/*|orig/primary_R",
           "adjudicator": "author model, NOT human", "per_cell": {}}
    tot = 0.0
    ok = True
    for m, pre in (("gemma_it", "gemma"), ("gams3_it", "gams")):
        for lang in ("en", "sl"):
            c = cells.get(f"{m}|{lang}|orig", {}).get("primary_R")
            if not c:
                ok = False
                continue
            p = k[f"{pre}_{lang}"] / n[f"{pre}_{lang}"]
            e = n[f"{pre}_{lang}"] * (p * (1 - c["Se"]) + (1 - p) * (1 - c["Sp"]))
            out["per_cell"][f"{m}|{lang}|orig"] = {"Se": c["Se"], "Sp": c["Sp"], "n_pos": c["n_pos"], "n_neg": c["n_neg"],
                                                   "Sp_ci": c.get("Sp_ci"), "expected_mislabels_per_cell": e}
            tot += e
    # pooled over the 4 unedited cells (more stable)
    tp = sum(round(v["Se"] * v["n_pos"]) for v in out["per_cell"].values())
    npos = sum(v["n_pos"] for v in out["per_cell"].values())
    tn = sum(round(v["Sp"] * v["n_neg"]) for v in out["per_cell"].values())
    nneg = sum(v["n_neg"] for v in out["per_cell"].values())
    if npos and nneg:
        se_p, sp_p = tp / npos, tn / nneg
        pooled = {}
        for pre in ("gemma_en", "gemma_sl", "gams_en", "gams_sl"):
            p = k[pre] / n[pre]
            pooled[pre] = n[pre] * (p * (1 - se_p) + (1 - p) * (1 - sp_p))
        out["pooled_unedited"] = {"Se": se_p, "Sp": sp_p, "n_pos": npos, "n_neg": nneg,
                                  "Sp_ci_wilson": wilson(tn, nneg), "expected_mislabels_per_cell": pooled,
                                  "expected_mislabels_total_4cells": sum(pooled.values())}
    out["available"] = ok
    out["caveat"] = ("Unedited-cell specificity rests on only 1-2 adjudicated NON-refusals per cell (Sp CI spans most of "
                     "[0,1]); the expected-mislabel count is therefore an order-of-magnitude comparison, not an estimate.")
    return out


# ------------------------------------------------------------------ eval3 bodies (1g)
LABEL_COLS = {"gemini_raw_prim3": "prim3", "gpt41mini_sec3": "sec3", "ttj3": "ttj3", "arch_j1": "arch_j1",
              "arch_j2": "arch_j2", "arch_q14": "arch_q14", "arch_m24": "arch_m24", "arch_llama8b": "arch_llama8b",
              "arch_gemini": "arch_gemini", "arch_lex": "arch_lex"}


def _R(s: pd.Series) -> pd.Series:
    if not pd.api.types.is_numeric_dtype(s):
        return s.map(lambda v: 1.0 if v == "REFUSE" else (0.0 if v in ("PARTIAL", "COMPLY") else np.nan))
    return pd.to_numeric(s, errors="coerce")


def eval3_bodies() -> dict[str, pd.DataFrame]:
    df = pd.read_parquet(EVAL3 / "work/frame.parquet", columns=["key", "in_P100"]) if (EVAL3 / "work/frame.parquet").exists() else None
    rr = pd.read_json(EVAL3 / "labels/readout_rows.jsonl.gz", lines=True)
    if df is not None:
        rr = rr.merge(df, on="key", how="left")
    h = rr[(rr.kind == "harmful") & rr.arm.isin(["en_bt", "sl_mt"])]
    f = {"exp9_lambda": h[(h.source == "exp9") & (h.curve == "orig")],
         "exp11_final": h[(h.source == "exp11") & (h.priority == 1) & (h.step == 0.0)],
         "exp8_A1": h[(h.source == "exp8") & (h.curve == "orig")],
         "exp10_op": h[(h.source == "exp10") & (h.curve == "O")]}
    if "in_P100" in h:
        f["exp8_B"] = h[(h.source == "exp8") & (h.curve == "orig") & (h.in_P100 == 1)]
    return f


def body_counts(fr: pd.DataFrame, col: str) -> tuple[dict, dict] | None:
    y = _R(fr[col])
    k, n = {}, {}
    for m, pre in (("gemma_it", "gemma"), ("gams3_it", "gams")):
        for arm, lang in (("en_bt", "en"), ("sl_mt", "sl")):
            s = y[(fr.model == m).values & (fr.arm == arm).values]
            s = s[s.notna()]
            if len(s) < 20:
                return None
            k[f"{pre}_{lang}"], n[f"{pre}_{lang}"] = float(s.sum()), float(len(s))
    return k, n


def body_matrix(fr: pd.DataFrame, col: str) -> dict:
    """items x (en_bt, sl_mt) binary matrices per model (NaN where the label is missing)."""
    y = _R(fr[col]).values
    items = sorted(fr.item_id.unique())
    ii = {x: i for i, x in enumerate(items)}
    Y = {m: np.full((len(items), 2), np.nan) for m in MODELS}
    for it, m, arm, v in zip(fr.item_id.values, fr.model.values, fr.arm.values, y):
        Y[m][ii[it], 0 if arm == "en_bt" else 1] = v
    return Y


def extension(rc: dict) -> dict:
    F = eval3_bodies()
    out = {}
    for body, fr in F.items():
        saved_key = f"{body}|raw_primary|R"
        sv = rc.get("curves", {}).get(saved_key, {})
        saved = (sv.get("G3_orig") or sv.get("G3_op_orig") or {}).get("est")
        rows = {}
        for name, col in LABEL_COLS.items():
            if col not in fr:
                continue
            kn = body_counts(fr, col)
            if kn is None:
                continue
            k, n = kn
            fi = fragility(k, n, max_flips=30)
            ests = [g3_orig_counts(k, n, e) for e in ("hautus", "laplace", "half_n", "jeffreys_logit_mean")]
            Yb = body_matrix(fr, col)
            rngb = np.random.default_rng(SEED + 11)
            nI = Yb["gemma_it"].shape[0]
            dd = []
            for _ in range(1000):
                w = rngb.multinomial(nI, np.ones(nI) / nI).astype(float)
                kb, nb = counts_of(Yb, w)
                if min(nb.values()) > 0:
                    dd.append(prob_did(kb, nb))
            did_ci = pct_ci(dd)
            rows[name] = {"counts_k": k, "counts_n": n, "G3_orig_hautus": fi["G3_orig"], "FI_m": fi["FI_m"],
                          "FI_0": fi["FI_0"], "estimator_range": [min(ests), max(ests)],
                          "prob_did_pp": prob_did(k, n), "prob_did_pp_ci95_item_boot_1000": did_ci,
                          "verdict": verdict_of(fi["FI_m"], ests, did_ci, fi["G3_orig"])}
        smoke = None
        if saved is not None and "gemini_raw_prim3" in rows:
            smoke = {"saved_G3_orig": saved, "recomputed": rows["gemini_raw_prim3"]["G3_orig_hautus"],
                     "abs_diff": abs(saved - rows["gemini_raw_prim3"]["G3_orig_hautus"]),
                     "pass_1e-6": abs(saved - rows["gemini_raw_prim3"]["G3_orig_hautus"]) < 1e-6}
        out[body] = {"n_rows_lambda0": int(len(fr)), "smoke_vs_eval3_recompute": smoke, "saved_key": saved_key,
                     "by_label": rows if (smoke is None or smoke["pass_1e-6"]) else {},
                     "status": ("OK" if smoke and smoke["pass_1e-6"] else
                                ("UNTRACEABLE: smoke test failed; fragility not reported" if smoke else
                                 "NO SAVED G3_orig TO SMOKE-TEST (recomputed values reported as unverified)"))}
        if smoke is None:
            out[body]["by_label"] = rows
        logger.info(f"1g {body}: smoke={smoke} n_labels={len(rows)}")
    return out


def main() -> dict:
    setup_logging("ceiling")
    rng = np.random.default_rng(SEED)
    an = read_json(EXP15 / "results/analysis.json")
    st = {s["lambda"]: s for s in an["steps_R"]["gemma_it"]}[0.0], {s["lambda"]: s for s in an["steps_R"]["gams3_it"]}[0.0]
    k_saved = {"gemma_en": st[0]["k_en"], "gemma_sl": st[0]["k_sl"], "gams_en": st[1]["k_en"], "gams_sl": st[1]["k_sl"]}
    n_saved = {"gemma_en": st[0]["n_en"], "gemma_sl": st[0]["n_sl"], "gams_en": st[1]["n_en"], "gams_sl": st[1]["n_sl"]}
    Y, items, adj = exp15_matrices()
    k, n = counts_of(Y)
    g0 = g3_orig_counts(k, n)
    saved_g0 = an["headline"]["R"]["RAW"]["G3_orig"]["point"]
    smoke = {"counts_saved_steps_R": k_saved, "n_saved": n_saved, "counts_rows_final": k, "n_rows_final": n,
             "counts_equal": all(abs(k[c] - k_saved[c]) < 1e-9 and abs(n[c] - n_saved[c]) < 1e-9 for c in CELLS),
             "M0_gemma": float(hautus_logit(k["gemma_sl"], n["gemma_sl"]) - hautus_logit(k["gemma_en"], n["gemma_en"])),
             "M0_gams": float(hautus_logit(k["gams_sl"], n["gams_sl"]) - hautus_logit(k["gams_en"], n["gams_en"])),
             "G3_orig": g0, "G3_orig_saved": saved_g0, "abs_diff": abs(g0 - saved_g0)}
    smoke["pass"] = smoke["counts_equal"] and smoke["abs_diff"] < 1e-9
    logger.info(f"smoke: {smoke}")
    if not smoke["pass"]:
        raise RuntimeError("exp15 lambda-0 smoke test failed")
    fi = fragility(k, n)
    fi_alt = {e: {kk: v for kk, v in fragility(k, n, e).items() if kk in ("G3_orig", "FI_m", "FI_0")}
              for e in ("laplace", "half_n", "jeffreys_logit_mean")}
    paired = paired_view(Y)
    lk = leave_k(Y, rng, 20000)
    sweep = estimator_sweep(k, n, rng)
    boot = bootstrap_all(Y, rng)
    perm = permutation(Y, rng)
    did_pp = prob_did(k, n)
    cl = {m: paired[m]["cond_logit_ln_b_over_c"] for m in MODELS}
    sweep["point"]["v_paired_conditional_logit_diff"] = cl["gams3_it"] - cl["gemma_it"]
    sweep["point"]["vi_probability_scale_pp"] = did_pp
    je = judge_error(an, k, n)
    ests = [sweep["point"][e] for e in ("i_hautus_loglinear", "ii_laplace_add1", "iii_half_n_rule_extreme_cells_only",
                                        "iv_jeffreys_posterior_mean_of_logit")]
    verdict = verdict_of(fi["FI_m"], ests, boot["prob_did_pp"]["ci95"], g0)
    exp_mis = je.get("pooled_unedited", {}).get("expected_mislabels_total_4cells")
    sentence = (f"exp15's baseline component is '{verdict}': {fi['FI_m']} flip(s) move it inside the margin "
                f"(G3_orig {g0:.2f}; {fi['FI_0']} flip(s) reach zero; the probability-scale DiD is {did_pp:.1f} pp, "
                f"95% CI [{boot['prob_did_pp']['ci95'][0]:.1f}, {boot['prob_did_pp']['ci95'][1]:.1f}]"
                + (f"; J1's pooled unedited error rates imply about {exp_mis:.1f} mislabelled items across the four "
                   f"lambda-0 cells" if exp_mis is not None else "") + ").")
    # adjudicated subsample at lambda 0 (author model): counts only
    adj_counts = {m: {"n_adj_en": int((~np.isnan(adj[m][:, 0])).sum()), "n_adj_sl": int((~np.isnan(adj[m][:, 1])).sum())}
                  for m in MODELS}
    try:
        rc = read_json(EVAL3 / "results/recompute.json")
        ext = extension(rc)
    except (FileNotFoundError, KeyError, ValueError) as e:
        logger.error(f"1g extension failed: {e}")
        ext = {"status": f"UNTRACEABLE: {e}"}
    res = {"target": "exp15 G3_orig = M0_GaMS - M0_Gemma (lambda 0, R coding, J1 raw, Hautus logits)",
           "m": M, "source": {"file": rel(EXP15 / "results/rows_final.jsonl"),
                              "filter": "set==BODY & edit==E_exp9 & block in (ladder,fillin) & arm in (EN_BT,SL_MT) & lambda==0 (analysis.py Cube)",
                              "saved": rel(EXP15 / "results/analysis.json") + " :: steps_R/*/[lambda=0], headline/R/RAW/G3_orig"},
           "smoke": smoke, "fragility_index": fi, "fragility_other_estimators": fi_alt, "paired_exact": paired,
           "leave_k_items": lk, "estimators": sweep, "bootstrap": boot, "permutation_model_label": perm,
           "judge_error": je, "adjudicated_lambda0_rows": adj_counts, "verdict": verdict, "paper_sentence": sentence,
           "extension_eval3_bodies": ext, "post_hoc_label": "POST-HOC sensitivity analysis (thresholds frozen in protocol_eval.yaml); can downgrade, cannot confirm"}
    write_json(RES / "ceiling_sensitivity.json", res)
    return res


if __name__ == "__main__":
    main()
