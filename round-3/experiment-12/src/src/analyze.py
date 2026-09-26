#!/usr/bin/env python3
"""STEP 6 analysis (path A). Reads only results/items/*.jsonl (+ data/ for chance/pairing) and writes
results/utility_table.json, gates.json, kl_footprint.json, competence_covariates.json, analysis.json."""
from __future__ import annotations

import json
import math
import re
import sys
import zlib
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from scipy.stats import binomtest  # noqa: E402

from common import (DATA, GATE_LOSS, HEADROOM_FLOOR, ITEMS, MODELS, N_BOOT, PRIMARY_METRIC, RESULTS, SEED,  # noqa: E402
                    UTIL_TASKS, gate_verdict, headroom_H, read_jsonl, setup_logger)

logger = setup_logger("analyze")
RNG_SEED = SEED + 1
MODEL_LIST = list(MODELS)
ANCHORS_GAMS_SL = {"arc_challenge": 0.527, "boolq": 0.852, "hellaswag": 0.511, "openbookqa": 0.394, "piqa": 0.715, "winogrande": 0.706}
ANCHORS_GEMMA_SL = {"arc_challenge": 0.451, "boolq": 0.853, "hellaswag": 0.473, "openbookqa": 0.352, "piqa": 0.662, "winogrande": 0.656}


def pct(a: np.ndarray, q: float) -> float:
    return float(np.percentile(a, q))


def ci(a: np.ndarray, level: int = 95) -> list[float]:
    lo = (100 - level) / 2
    return [round(pct(a, lo), 5), round(pct(a, 100 - lo), 5)]


# ================================================================== utility ==========================================
def load_util(kind: str) -> dict:
    """-> U[model][cond][lang][task] = {item_id: correct(primary metric)}"""
    U: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    for f in sorted(ITEMS.glob(f"{kind}_*.jsonl")):
        for r in read_jsonl(f):
            metric = PRIMARY_METRIC[r["task"]]
            U[r["model"]][r["cond"]][(r["lang"], r["task"])][r["item_id"]] = (float(r[metric]), 1.0 / r["n_choices"],
                                                                                r.get("pair_id"))
    return U


def item_order(task: str, lang: str) -> list[str]:
    if task == "belebele":
        return [r["id"] for r in read_jsonl(DATA / "belebele" / f"belebele_{lang}.jsonl")]
    return [r["id"] for r in read_jsonl(DATA / "util" / f"{task}_{lang}.jsonl")]


def build_vectors(U: dict, model: str, conds: list[str], cells: list[tuple[str, str]]) -> dict:
    """Aligned vectors over the item ids present in orig AND every cond (intersection), per (lang, task) cell.
    Paired tasks: EN/SL share pair_id -> the SAME pair order is used in both languages."""
    out = {}
    for lang, task in cells:
        if (lang, task) not in U[model].get("orig", {}):
            continue
        common = None
        for c in ["orig"] + conds:
            ids = set(U[model].get(c, {}).get((lang, task), {}).keys())
            common = ids if common is None else common & ids
        order = [i for i in item_order(task, lang) if i in common]
        if not order:
            continue
        vec = {c: np.array([U[model][c][(lang, task)][i][0] for i in order]) for c in ["orig"] + conds}
        chance = float(np.mean([U[model]["orig"][(lang, task)][i][1] for i in order]))
        out[(lang, task)] = {"ids": order, "vec": vec, "chance": chance}
    return out


def boot_indices(n: int, rng: np.random.Generator, B: int = N_BOOT) -> np.ndarray:
    return rng.integers(0, n, size=(B, n))


def util_block(U: dict, conds_all: list[str], langs: list[str], tasks: list[str], label: str, rng_seed: int) -> dict:
    """Compute H per cell, macros, A, I, H_excess with a joint paired bootstrap (same resampled pair indices across
    conditions, languages and models within a task)."""
    rng = np.random.default_rng(rng_seed)
    cells = [(l, t) for l in langs for t in tasks]
    V = {m: build_vectors(U, m, [c for c in conds_all if c in U[m]], cells) for m in MODEL_LIST if m in U}
    # shared bootstrap indices per task: need the same n across models/languages -> use pair-index intersection
    idx = {}
    for t in tasks:
        ns = [len(V[m][(l, t)]["ids"]) for m in V for l in langs if (l, t) in V[m]]
        if not ns:
            continue
        if len(set(ns)) != 1:
            logger.warning(f"{label}/{t}: unequal n across cells {ns}; bootstrap per-cell independent for this task")
            idx[t] = None
        else:
            idx[t] = boot_indices(ns[0], rng)
    table: dict = {}
    boots: dict = {}
    for m in V:
        conds = [c for c in conds_all if c in U[m] and c != "orig"]
        table[m] = {}
        for c in conds:
            table[m][c] = {}
            for l in langs:
                table[m][c][l] = {}
                for t in tasks:
                    cell = V[m].get((l, t))
                    if cell is None or c not in cell["vec"]:
                        continue
                    vo, vc, ch = cell["vec"]["orig"], cell["vec"][c], cell["chance"]
                    ao, ac = float(vo.mean()), float(vc.mean())
                    H = headroom_H(ac, ao, ch)
                    ix = idx.get(t) if idx.get(t) is not None else boot_indices(len(vo), rng)
                    bo, bc = vo[ix].mean(1), vc[ix].mean(1)
                    with np.errstate(divide="ignore", invalid="ignore"):
                        bH = (bc - ch) / (bo - ch) - 1
                    b_ = int(((vo == 1) & (vc == 0)).sum())
                    c_ = int(((vo == 0) & (vc == 1)).sum())
                    p_mc = float(binomtest(min(b_, c_), b_ + c_, 0.5).pvalue) if b_ + c_ > 0 else 1.0
                    table[m][c][l][t] = {"acc_orig": round(ao, 5), "acc": round(ac, 5), "acc_metric": PRIMARY_METRIC[t],
                                         "chance": round(ch, 5), "headroom": round(ao - ch, 5), "H": round(H, 5),
                                         "H_ci95": ci(bH[np.isfinite(bH)]), "raw_pp": round(100 * (ac - ao), 3),
                                         "rel_pct": round(100 * (ac / ao - 1), 3) if ao > 0 else None, "n": len(vo),
                                         "eligible": bool(ao - ch >= HEADROOM_FLOOR - 1e-9), "mcnemar_b_orig_right_cond_wrong": b_,
                                         "mcnemar_c_orig_wrong_cond_right": c_, "mcnemar_p": p_mc}
                    boots[(m, c, l, t)] = (bH, (bc - bo) * 100)
                # Holm within condition happens after all langs
            # Holm-correct McNemar within model x condition
            ps = [(l, t, table[m][c][l][t]["mcnemar_p"]) for l in table[m][c] for t in table[m][c][l]]
            order = sorted(range(len(ps)), key=lambda k: ps[k][2])
            running = 0.0
            for rank, k in enumerate(order):
                adj = min(1.0, (len(ps) - rank) * ps[k][2])
                running = max(running, adj)
                l, t, _ = ps[k]
                table[m][c][l][t]["mcnemar_p_holm"] = round(running, 6)
    # macros
    macros: dict = {}
    macro_boot: dict = {}
    RAW_H: dict = {}
    for m in table:
        macros[m] = {}
        for c in table[m]:
            macros[m][c] = {}
            for l in langs:
                cells_l = table[m][c].get(l, {})
                if not cells_l:
                    continue
                elig = [t for t in cells_l if cells_l[t]["eligible"]]
                inel = [t for t in cells_l if not cells_l[t]["eligible"]]
                Hm = float(np.mean([cells_l[t]["H"] for t in elig])) if elig else float("nan")
                bHm = np.mean([boots[(m, c, l, t)][0] for t in elig], axis=0) if elig else np.full(N_BOOT, np.nan)
                raw = float(np.mean([cells_l[t]["raw_pp"] for t in cells_l]))
                braw = np.mean([boots[(m, c, l, t)][1] for t in cells_l], axis=0)
                rel = float(np.mean([cells_l[t]["rel_pct"] for t in cells_l if cells_l[t]["rel_pct"] is not None]))
                macro_boot[(m, c, l)] = (bHm, braw)
                RAW_H[(m, c, l)] = Hm
                macros[m][c][l] = {"macro_H": round(Hm, 5), "macro_H_ci95": ci(bHm[np.isfinite(bHm)]) if elig else None,
                                   "macro_H_ci90": ci(bHm[np.isfinite(bHm)], 90) if elig else None,
                                   "macro_loss": round(-Hm, 5), "macro_loss_hi95": round(-pct(bHm[np.isfinite(bHm)], 2.5), 5) if elig else None,
                                   "eligible_tasks": elig, "ineligible_tasks": inel, "raw_pp_macro": round(raw, 4),
                                   "raw_pp_macro_ci95": ci(braw), "rel_pct_macro": round(rel, 4),
                                   "F6_raw_pp_rule": len(inel) >= 3}
            if all(l in macros[m][c] for l in ("en", "sl")) and len(langs) >= 2:
                pooled = (macro_boot[(m, c, "en")][0] + macro_boot[(m, c, "sl")][0]) / 2
                A = macro_boot[(m, c, "sl")][0] - macro_boot[(m, c, "en")][0]
                macros[m][c]["pooled_macro_H"] = round((RAW_H[(m, c, "en")] + RAW_H[(m, c, "sl")]) / 2, 5)
                macros[m][c]["pooled_macro_H_ci95"] = ci(pooled[np.isfinite(pooled)])
                macros[m][c]["A_sl_minus_en"] = round(RAW_H[(m, c, "sl")] - RAW_H[(m, c, "en")], 5)
                macros[m][c]["A_ci95"] = ci(A[np.isfinite(A)])
                macros[m][c]["A_ci90"] = ci(A[np.isfinite(A)], 90)
    # interaction and random-adjusted
    inter: dict = {}
    if len(macros) == 2:
        mg, mm = "gams3_it", "gemma_it"
        for c in set(macros.get(mg, {})) & set(macros.get(mm, {})):
            if "A_sl_minus_en" in macros[mg][c] and "A_sl_minus_en" in macros[mm][c]:
                bA = {m: macro_boot[(m, c, "sl")][0] - macro_boot[(m, c, "en")][0] for m in (mg, mm)}
                bI = bA[mg] - bA[mm]
                inter[c] = {"I": round((RAW_H[(mg, c, "sl")] - RAW_H[(mg, c, "en")]) - (RAW_H[(mm, c, "sl")] - RAW_H[(mm, c, "en")]), 5),
                            "I_ci95": ci(bI[np.isfinite(bI)]), "I_ci90": ci(bI[np.isfinite(bI)], 90),
                            "note": "resolution limit ~0.10-0.12 of headroom (80% power, alpha .05); |I| below it is an estimate, not 'no asymmetry'"}
    excess: dict = {}
    for m in macros:
        for c in macros[m]:
            if c.startswith("E_") and "rand_nm_j1" in macros[m]:
                excess.setdefault(m, {})[c] = {}
                for l in langs:
                    if l in macros[m][c] and l in macros[m]["rand_nm_j1"]:
                        b = macro_boot[(m, c, l)][0] - macro_boot[(m, "rand_nm_j1", l)][0]
                        excess[m][c][l] = {"H_excess": round(RAW_H[(m, c, l)] - RAW_H[(m, "rand_nm_j1", l)], 5),
                                           "ci95": ci(b[np.isfinite(b)])}
                if "en" in excess[m][c] and "sl" in excess[m][c]:
                    bA = (macro_boot[(m, c, "sl")][0] - macro_boot[(m, c, "en")][0]) - \
                         (macro_boot[(m, "rand_nm_j1", "sl")][0] - macro_boot[(m, "rand_nm_j1", "en")][0])
                    excess[m][c]["A_excess"] = {"value": round((RAW_H[(m, c, "sl")] - RAW_H[(m, "rand_nm_j1", "sl")]) - (RAW_H[(m, c, "en")] - RAW_H[(m, "rand_nm_j1", "en")]), 5),
                                                "ci95": ci(bA[np.isfinite(bA)])}
    return {"cells": table, "macros": macros, "interaction": inter, "random_adjusted": excess,
            "_macro_boot": macro_boot}


def gates_from(util: dict, lam: dict | None) -> dict:
    g: dict = {}
    for src, blk in (("full", util), ("lambda_subset", lam)):
        if not blk:
            continue
        for m, cc in blk["macros"].items():
            for c, d in cc.items():
                langs = [l for l in ("en", "sl") if l in d]
                verdicts = {}
                for l in langs:
                    x = d[l]
                    if x["F6_raw_pp_rule"]:
                        loss = -x["raw_pp_macro"]
                        hi = -x["raw_pp_macro_ci95"][0]
                        verdicts[l] = {"rule": "F6 raw-pp (5 pp)", "loss": loss, "loss_hi95": hi, "verdict": gate_verdict(loss, hi, 5.0)}
                    else:
                        verdicts[l] = {"rule": "headroom macro (0.20)", "loss": x["macro_loss"], "loss_hi95": x["macro_loss_hi95"],
                                       "verdict": gate_verdict(x["macro_loss"], x["macro_loss_hi95"] if x["macro_loss_hi95"] is not None else float("nan"))}
                    # co-reported sensitivity (decides nothing on its own): raw-pp macro loss vs the F6 5-pp threshold
                    verdicts[l]["sensitivity_raw_pp"] = {"loss_pp": -x["raw_pp_macro"], "loss_pp_hi95": -x["raw_pp_macro_ci95"][0],
                                                         "verdict_5pp": gate_verdict(-x["raw_pp_macro"], -x["raw_pp_macro_ci95"][0], 5.0)}
                rank = {"OK": 0, "POSSIBLY_CATASTROPHIC": 1, "CATASTROPHIC": 2, "PENDING": -1}
                worst = max((v["verdict"] for v in verdicts.values()), key=lambda s: rank[s]) if verdicts else "PENDING"
                if c in g.get(m, {}) and g[m][c]["source"] == "full":
                    g[m][c]["lambda_subset_check"] = {"per_lang": verdicts, "verdict": worst}  # full-set gate takes precedence
                    continue
                g.setdefault(m, {})[c] = {"source": src, "per_lang": verdicts, "verdict": worst}
    return g


# ================================================================== KL ===============================================
def kl_block() -> dict:
    out: dict = {}
    rng = np.random.default_rng(RNG_SEED + 7)
    mt = {r["id"]: r for r in read_jsonl(DATA / "harmless" / "harmless_mt.jsonl")}
    for m in MODEL_LIST:
        rows = read_jsonl(ITEMS / f"kl_{m}.jsonl")
        if not rows:
            continue
        by = defaultdict(dict)
        for r in rows:
            by[r["arm"]][r["item_id"]] = dict(r["kl"])
        for r in read_jsonl(ITEMS / f"klextra_{m}.jsonl"):  # late-discovered conditions (same protocol)
            if r["item_id"] in by[r["arm"]]:
                by[r["arm"]][r["item_id"]].update(r["kl"])
        arms = [a for a in ("en_orig", "en_bt", "sl_mt", "hu_mt") if a in by]
        ids = sorted(set.intersection(*[set(by[a]) for a in arms]))
        conds = sorted(set.intersection(*[set(by[a][i]) for a in arms for i in ids]))
        res = {"n_items": len(ids), "arms": arms, "conds": conds, "means": {}, "ratios": {}}
        ix = boot_indices(len(ids), rng)
        arr = {(a, c, k): np.array([by[a][i][c][k] for i in ids]) for a in arms for c in conds for k in ("first", "multi")}
        rand_js = [c for c in conds if c.startswith("rand_nm_j")]
        for a in arms:
            for k in ("first", "multi"):
                arr[(a, "rand_nm_avg", k)] = np.mean([arr[(a, c, k)] for c in rand_js], axis=0) if rand_js else None
        floor_first = float(np.mean([arr[(a, "self", "first")].mean() for a in arms]))
        floor_multi = float(np.mean([arr[(a, "self", "multi")].mean() for a in arms]))
        res["self_floor"] = {"mean_first": floor_first, "mean_multi": floor_multi,
                             "max_first": float(max(arr[(a, "self", "first")].max() for a in arms)),
                             "max_multi": float(max(arr[(a, "self", "multi")].max() for a in arms)),
                             "reported_as_noise_floor": bool(max(arr[(a, "self", "first")].max() for a in arms) > 1e-4)}
        for c in conds + (["rand_nm_avg"] if rand_js else []):
            res["means"][c] = {}
            for a in arms:
                res["means"][c][a] = {}
                for k in ("first", "multi"):
                    v = arr[(a, c, k)]
                    res["means"][c][a][k] = {"mean": float(v.mean()), "ci95": ci(v[ix].mean(1))}
        # EXPLORATORY: does the edit perturb the same (parallel) prompts across languages? Spearman over items
        from scipy.stats import spearmanr
        res["cross_language_item_spearman_first"] = {}
        for c in [c for c in conds if c != "self"] + (["rand_nm_avg"] if rand_js else []):
            d = {}
            for a, b in (("en_bt", "sl_mt"), ("en_bt", "hu_mt"), ("en_orig", "en_bt")):
                if a in arms and b in arms:
                    rho = spearmanr(arr[(a, c, "first")], arr[(b, c, "first")]).statistic
                    d[f"{a}~{b}"] = float(rho)
            res["cross_language_item_spearman_first"][c] = d
        frag = np.array([bool(mt.get(i, {}).get("fragile_sl", False)) for i in ids])
        res["n_fragile_sl"] = int(frag.sum())
        for k in ("first", "multi"):
            for c in [c for c in conds if c not in ("self",) and not c.startswith("rand_nm_j")] + (["rand_nm_avg"] if rand_js else []):
                def ratio(num: str, den: str, cc: str, sel=None) -> tuple[float, np.ndarray]:
                    a_, b_ = arr[(num, cc, k)], arr[(den, cc, k)]
                    if sel is not None:
                        a_, b_ = a_[sel], b_[sel]
                        jx = boot_indices(len(a_), rng)
                    else:
                        jx = ix
                    return float(a_.mean() / b_.mean()), a_[jx].mean(1) / b_[jx].mean(1)
                d = {}
                for nm, (num, den) in {"sl_over_enbt": ("sl_mt", "en_bt"), "sl_over_enorig": ("sl_mt", "en_orig"),
                                       "hu_over_enbt": ("hu_mt", "en_bt"), "enbt_over_enorig": ("en_bt", "en_orig")}.items():
                    if num in arms and den in arms:
                        r_, b_ = ratio(num, den, c)
                        d[nm] = {"ratio": r_, "ci95": ci(b_)}
                        if rand_js and c != "rand_nm_avg":
                            rr, br = ratio(num, den, "rand_nm_avg")
                            ex = b_ / br
                            d[nm]["excess_vs_rand"] = {"excess": r_ / rr, "ci95": ci(ex[np.isfinite(ex)]), "ratio_rand": rr}
                if "sl_mt" in arms and "en_bt" in arms and (~frag).sum() > 10:
                    r_, b_ = ratio("sl_mt", "en_bt", c, sel=~frag)
                    d["sl_over_enbt_nonfragile"] = {"ratio": r_, "ci95": ci(b_)}
                rand_mean = float(np.mean([arr[(a, "rand_nm_avg", k)].mean() for a in arms])) if rand_js else float("nan")
                floor = floor_first if k == "first" else floor_multi
                d["readable"] = bool(rand_mean >= 5 * floor) if rand_js else None
                d["rand_mean_over_floor"] = rand_mean / floor if floor > 0 else float("inf")
                res["ratios"].setdefault(c, {})[k] = d
        out[m] = res
    return out


# ================================================================== BPB ==============================================
def bpb_block() -> dict:
    out: dict = {}
    rng = np.random.default_rng(RNG_SEED + 11)
    for m in MODEL_LIST:
        rows = read_jsonl(ITEMS / f"bpb_{m}.jsonl")
        if not rows:
            continue
        res = {}
        conds = sorted(set.intersection(*[set(r["bpb"]) for r in rows]))
        per = {}
        for lang in ("en", "sl", "hu"):
            rl = [r for r in rows if r["lang"] == lang]
            if not rl:
                continue
            ids = [r["item_id"] for r in rl]
            per[lang] = {c: np.array([r["bpb"][c] for r in rl]) for c in conds}
            per[lang]["_ids"] = ids
            ix = boot_indices(len(rl), rng)
            res[lang] = {}
            for c in conds:
                d = per[lang][c] - per[lang]["orig"]
                res[lang][c] = {"bpb": float(per[lang][c].mean()), "delta_vs_orig": float(d.mean()), "delta_ci95": ci(d[ix].mean(1)),
                                "rel_delta_pct": float(100 * d.mean() / per[lang]["orig"].mean())}
                if "rand_nm_j1" in conds and c != "rand_nm_j1":
                    dr = per[lang][c] - per[lang]["rand_nm_j1"]
                    res[lang][c]["delta_vs_rand_nm_j1"] = float(dr.mean())
                    res[lang][c]["delta_vs_rand_ci95"] = ci(dr[ix].mean(1))
        if "en" in per and "sl" in per:
            res["asymmetry_rel_delta_sl_minus_en_pct"] = {c: res["sl"][c]["rel_delta_pct"] - res["en"][c]["rel_delta_pct"] for c in conds}
        if "hu" in per and "en" in per:
            res["asymmetry_rel_delta_hu_minus_en_pct"] = {c: res["hu"][c]["rel_delta_pct"] - res["en"][c]["rel_delta_pct"] for c in conds}
        out[m] = res
    return out


# ================================================================== generations ======================================
_DET = None


def detector():
    global _DET
    if _DET is None:
        from lingua import Language, LanguageDetectorBuilder
        langs = [Language.ENGLISH, Language.SLOVENE, Language.HUNGARIAN, Language.CROATIAN, Language.SERBIAN,
                 Language.BOSNIAN, Language.GERMAN, Language.ITALIAN]
        _DET = LanguageDetectorBuilder.from_languages(*langs).build()
    return _DET


def lang_code(text: str) -> str:
    l = detector().detect_language_of(text)
    if l is None:
        return "none"
    return {"ENGLISH": "en", "SLOVENE": "sl", "HUNGARIAN": "hu", "CROATIAN": "hr", "SERBIAN": "sr", "BOSNIAN": "bs",
            "GERMAN": "de", "ITALIAN": "it"}[l.name]


def degenerate(text: str, n_new: int) -> bool:
    toks = text.split()
    if not text.strip() or n_new < 5:
        return True
    if len(toks) >= 20:
        grams = [tuple(toks[i:i + 4]) for i in range(len(toks) - 3)]
        if len(set(grams)) / len(grams) < 0.5:
            return True
    b = text.encode("utf-8")
    if len(b) >= 100 and len(zlib.compress(b)) / len(b) < 0.25:
        return True
    return False


def gen_block() -> dict:
    out: dict = {}
    want = {"en_bt": "en", "en_orig": "en", "sl_mt": "sl", "hu_mt": "hu"}
    for f in sorted(ITEMS.glob("gen_*.jsonl")):
        rows = read_jsonl(f)
        if not rows:
            continue
        m, c = rows[0]["model"], rows[0]["cond"]
        res = {}
        for arm in sorted({r["arm"] for r in rows}):
            ra = [r for r in rows if r["arm"] == arm]
            det = [lang_code(r["text"]) if r["text"].strip() else "none" for r in ra]
            tgt = want[arm]
            cons = [d == tgt for d in det]
            ss = [d in ("hr", "sr", "bs") for d in det]
            deg = [degenerate(r["text"], r["n_new"]) for r in ra]
            res[arm] = {"n": len(ra), "lang_consistency": float(np.mean(cons)),
                        "south_slavic_rate": float(np.mean(ss)) if tgt == "sl" else None,
                        "consistency_sl_or_southslavic": float(np.mean([a or b for a, b in zip(cons, ss)])) if tgt == "sl" else None,
                        "degenerate_rate": float(np.mean(deg)), "mean_new_tokens": float(np.mean([r["n_new"] for r in ra])),
                        "detected_counts": {k: det.count(k) for k in set(det)},
                        "gate_consistency_ge_95": bool(np.mean(cons) >= 0.95), "gate_degenerate_lt_10": bool(np.mean(deg) < 0.10),
                        "flagged_examples": [{"item_id": r["item_id"], "detected": d, "text": r["text"][:200]}
                                             for r, d, ok in zip(ra, det, cons) if not ok][:5]}
        out.setdefault(m, {})[c] = res
    return out


# ================================================================== misc checks ======================================
def scorer2_block() -> dict:
    """Second-path scorer (own torch, batch size 1, fp32 log-softmax) vs lm-eval logged logliks (bf16 log-softmax,
    batched). Reported per task. Winogrande is reported separately: lm-eval scored a double-space continuation
    (target delimiter ' ' + stored ' '-prefixed continuation), the second path a single space; scorer2wino re-scores
    50+50 items with the double space to verify that this explains the offset."""
    out = {}
    for m in MODEL_LIST:
        for c in ("orig", "E_iter1"):
            s2 = read_jsonl(ITEMS / f"scorer2_{m}_{c}.jsonl")
            ut = {(r["task"], r["lang"], r["item_id"]): r for r in read_jsonl(ITEMS / f"util_{m}_{c}.jsonl")}
            if not s2 or not ut:
                continue
            per = {}
            for t in UTIL_TASKS:
                d, agree, n = [], 0, 0
                for r in [r for r in s2 if r["task"] == t]:
                    u = ut.get((r["task"], r["lang"], r["item_id"]))
                    if u is None:
                        continue
                    d += [abs(a - b) for a, b in zip(r["lls"], u["lls"])]
                    agree += int(int(np.argmax(r["lls"])) == int(np.argmax(u["lls"])))
                    n += 1
                if n:
                    per[t] = {"n_items": n, "median_abs_dloglik": float(np.median(d)), "p99_abs_dloglik": float(np.percentile(d, 99)),
                              "max_abs_dloglik": float(max(d)), "argmax_agreement": agree / n}
            nw = [t for t in per if t != "winogrande"]
            tot_n = sum(per[t]["n_items"] for t in nw)
            agr = sum(per[t]["argmax_agreement"] * per[t]["n_items"] for t in nw) / max(1, tot_n)
            out[f"{m}/{c}"] = {"per_task": per, "argmax_agreement_excl_winogrande": agr,
                               "pass_argmax_ge_0.98_excl_winogrande": bool(agr >= 0.98),
                               "note": "lm-eval logliks are bf16 (92% are exact multiples of 1/16); |d| of 0.1-0.6 nats is bf16 + batch-composition noise, so the plan's <0.05-nat criterion cannot hold for bf16 lm-eval output"}
        w = read_jsonl(ITEMS / f"scorer2wino_{m}_orig.jsonl")
        ut = {(r["task"], r["lang"], r["item_id"]): r for r in read_jsonl(ITEMS / f"util_{m}_orig.jsonl")}
        if w and ut:
            dd = [abs(a - b) for r in w for a, b in zip(r["lls_double_space"], ut[("winogrande", r["lang"], r["item_id"])]["lls"])]
            ds = [abs(a - b) for r in w for a, b in zip(r["lls_single_space"], ut[("winogrande", r["lang"], r["item_id"])]["lls"])]
            ag = np.mean([int(np.argmax(r["lls_double_space"]) == np.argmax(ut[("winogrande", r["lang"], r["item_id"])]["lls"])) for r in w])
            out[f"{m}/winogrande_template_check"] = {"n_items": len(w), "median_abs_d_double_space": float(np.median(dd)),
                                                     "median_abs_d_single_space": float(np.median(ds)),
                                                     "argmax_agreement_double_space": float(ag),
                                                     "explains_offset": bool(np.median(dd) < 0.5 <= np.median(ds))}
    return out


def anchors_check(util: dict) -> dict:
    """Original-model SL accuracies (NF4, instruct, 300 items) vs published GaMS3 paper numbers (bf16, full sets).
    Both acc and acc_norm are reported: the paper does not state which HellaSwag/OBQA metric it prints."""
    out = {}
    for m, anc in (("gams3_it", ANCHORS_GAMS_SL), ("gemma_it", ANCHORS_GEMMA_SL)):
        rows = read_jsonl(ITEMS / f"util_{m}_orig.jsonl")
        if not rows:
            continue
        out[m] = {}
        for t, a in anc.items():
            rr = [r for r in rows if r["task"] == t and r["lang"] == "sl"]
            if not rr:
                continue
            acc = float(np.mean([r["acc"] for r in rr]))
            accn = float(np.mean([r["acc_norm"] for r in rr]))
            best = min(abs(acc - a), abs(accn - a))
            out[m][t] = {"acc": round(acc, 4), "acc_norm": round(accn, 4), "published": a,
                         "primary_metric": PRIMARY_METRIC[t], "diff_primary": round((accn if PRIMARY_METRIC[t] == "acc_norm" else acc) - a, 4),
                         "within_0.10_primary": abs((accn if PRIMARY_METRIC[t] == "acc_norm" else acc) - a) <= 0.10,
                         "within_0.10_either_metric": best <= 0.10}
    return out


def flip_margin_block() -> dict:
    """EXPLORATORY: are edit-induced correctness flips concentrated on near-tie items (small original margin between
    the best and second-best choice under the task's primary metric)? Compared for the edit and the random edit."""
    out: dict = {}
    choices = {}
    for t in UTIL_TASKS:
        for l in ("en", "sl"):
            for r in read_jsonl(DATA / "util" / f"{t}_{l}.jsonl"):
                choices[(t, l, r["id"])] = [len(c) for c in r["choices"]]
    for m in MODEL_LIST:
        orig = {(r["task"], r["lang"], r["item_id"]): r for r in read_jsonl(ITEMS / f"util_{m}_orig.jsonl")}
        if not orig:
            continue

        def score(r):
            v = np.array(r["lls"], dtype=float)
            if PRIMARY_METRIC[r["task"]] == "acc_norm":
                v = v / np.array(choices[(r["task"], r["lang"], r["item_id"])], dtype=float)
            return v
        for c in [c for c in ("E_iter1", "rand_nm_j1", "rand_nm_j2", "E_art2") if (ITEMS / f"util_{m}_{c}.jsonl").exists()]:
            rows = read_jsonl(ITEMS / f"util_{m}_{c}.jsonl")
            marg, flip, dmax = [], [], []
            for r in rows:
                o = orig.get((r["task"], r["lang"], r["item_id"]))
                if o is None:
                    continue
                so, sc = score(o), score(r)
                top2 = np.sort(so)[-2:]
                marg.append(float(top2[1] - top2[0]))
                flip.append(int(np.argmax(so) != np.argmax(sc)))
                dmax.append(float(np.max(np.abs(np.array(r["lls"]) - np.array(o["lls"])))))
            marg, flip = np.array(marg), np.array(flip)
            q = np.quantile(marg, [0.1, 0.25, 0.5])
            out.setdefault(m, {})[c] = {"n": len(flip), "flip_rate": float(flip.mean()),
                                        "flip_rate_margin_lt_p10": float(flip[marg < q[0]].mean()),
                                        "flip_rate_margin_ge_p50": float(flip[marg >= q[2]].mean()),
                                        "share_of_flips_in_bottom_quartile_margin": float(flip[marg < q[1]].sum() / max(1, flip.sum())),
                                        "median_abs_max_dloglik": float(np.median(dmax)), "p90_abs_max_dloglik": float(np.quantile(dmax, 0.9))}
    return out


def strip_boot(d):
    if isinstance(d, dict):
        return {k: strip_boot(v) for k, v in d.items() if not str(k).startswith("_")}
    return d


@logger.catch(reraise=True)
def main() -> None:
    A: dict = {}
    U = load_util("util")
    conds_full = sorted({c for m in U for c in U[m] if c != "orig"})
    util = util_block(U, ["orig"] + conds_full, ["en", "sl"], UTIL_TASKS, "util", RNG_SEED)
    logger.info(f"utility conds: {conds_full}")
    UL = load_util("utillam")
    lam = None
    if UL:
        # merge orig/E_iter1/rand from full run restricted to the lambda items (intersection handled in build_vectors)
        # orig and E_iter1 are re-scored INSIDE the 100-item subset run (identical lm-eval batch composition as the
        # lambda variants; NF4 batch composition shifts logliks by up to ~0.2 nats), so no merge from the full run
        lam_conds = sorted({c for m in UL for c in UL[m] if c.startswith("E_iter1_l")}) + ["E_iter1"]
        lam = util_block(UL, ["orig"] + lam_conds, ["en", "sl"], ["arc_challenge", "boolq", "openbookqa", "winogrande"], "lambda", RNG_SEED + 1)
    UB = load_util("bele")
    bele = util_block(UB, ["orig"] + sorted({c for m in UB for c in UB[m] if c != "orig"}), ["en", "sl", "hu"], ["belebele"], "bele", RNG_SEED + 2) if UB else None
    UC = load_util("chat")
    chat = util_block(UC, ["orig", "E_iter1"], ["en", "sl"], ["arc_challenge", "boolq"], "chat", RNG_SEED + 3) if UC else None
    # the no-chat reference on the same 100 items
    if UC:
        UR = load_util("util")
        for m in UR:
            for c in list(UR[m]):
                for key in list(UR[m][c]):
                    if key[1] not in ("arc_challenge", "boolq"):
                        del UR[m][c][key]
                    else:
                        ids_chat = set(UC.get(m, {}).get("orig", {}).get(key, {}).keys())
                        UR[m][c][key] = {i: v for i, v in UR[m][c][key].items() if i in ids_chat}
        chat_ref = util_block(UR, ["orig", "E_iter1"], ["en", "sl"], ["arc_challenge", "boolq"], "chat_ref", RNG_SEED + 3)
    else:
        chat_ref = None
    gates = gates_from(util, lam)
    # lambda gate curve
    curve = {}
    if lam:
        for m in lam["macros"]:
            pts = []
            for c, d in lam["macros"][m].items():
                lamv = 1.0 if c == "E_iter1" else (float(c.split("_l")[1]) if c.startswith("E_iter1_l") else None)
                if lamv is None:
                    continue
                pts.append({"lambda": lamv, "macro_H_en": d.get("en", {}).get("macro_H"), "macro_H_sl": d.get("sl", {}).get("macro_H"),
                            "ci95_en": d.get("en", {}).get("macro_H_ci95"), "ci95_sl": d.get("sl", {}).get("macro_H_ci95"),
                            "verdict": gates[m][c]["verdict"] if gates.get(m, {}).get(c, {}).get("source") == "lambda_subset" else
                            gates_from({"macros": {m: {c: d}}}, None)[m][c]["verdict"]})
            pts.sort(key=lambda p: p["lambda"])
            ok = [p["lambda"] for p in pts if p["verdict"] == "OK"]
            mono = all((pts[i]["macro_H_sl"] or 0) >= (pts[i + 1]["macro_H_sl"] or 0) - 1e-9 for i in range(len(pts) - 1))
            curve[m] = {"points": pts, "largest_lambda_OK": max(ok) if ok else None,
                        "licensed_lambdas": ok, "monotone_damage_sl": mono}
    kl = kl_block()
    bpb = bpb_block()
    gen = gen_block()
    s2 = scorer2_block()
    anchors = anchors_check(util)
    # competence covariates for artifact 4
    cov = {}
    for m in MODEL_LIST:
        cov[m] = {}
        for lang in ("en", "sl", "hu"):
            d = {}
            if m in bpb and lang in bpb[m]:
                d["orig_bpb"] = bpb[m][lang]["orig"]["bpb"]
            if bele and m in bele["cells"]:
                c0 = next(iter(bele["cells"][m].values()))
                if lang in c0 and "belebele" in c0[lang]:
                    d["belebele_acc_orig"] = c0[lang]["belebele"]["acc_orig"]
            arm = {"en": "en_bt", "sl": "sl_mt", "hu": "hu_mt"}[lang]
            if m in gen and "orig" in gen[m] and arm in gen[m]["orig"]:
                d["harmless_gen_lang_consistency_orig"] = gen[m]["orig"][arm]["lang_consistency"]
            cov[m][lang] = d
    # gate augmentation with fluency gates
    for m in gates:
        for c in gates[m]:
            if m in gen and c in gen[m]:
                gates[m][c]["language_consistency"] = {a: v["lang_consistency"] for a, v in gen[m][c].items()}
                gates[m][c]["degenerate_rate"] = {a: v["degenerate_rate"] for a, v in gen[m][c].items()}
                gates[m][c]["fluency_gate_pass"] = all(v["gate_consistency_ge_95"] and v["gate_degenerate_lt_10"] for v in gen[m][c].values())
    A = {"utility": strip_boot(util), "lambda_subset": strip_boot(lam) if lam else None, "lambda_gate_curve": curve,
         "belebele": strip_boot(bele) if bele else None, "chat_sensitivity": strip_boot(chat) if chat else None,
         "chat_sensitivity_nochat_reference": strip_boot(chat_ref) if chat_ref else None,
         "gates": gates, "kl": kl, "bpb": bpb, "generations": gen, "scorer2_agreement": s2, "published_anchor_check": anchors,
         "competence_covariates": cov, "exploratory_flip_margin": flip_margin_block()}
    (RESULTS / "analysis.json").write_text(json.dumps(A, indent=2, default=float))
    (RESULTS / "utility_table.json").write_text(json.dumps({"cells": A["utility"]["cells"], "macros": A["utility"]["macros"],
                                                            "interaction": A["utility"]["interaction"],
                                                            "random_adjusted": A["utility"]["random_adjusted"],
                                                            "lambda_subset": A["lambda_subset"], "belebele": A["belebele"],
                                                            "gates": gates}, indent=2, default=float))
    (RESULTS / "kl_footprint.json").write_text(json.dumps({"kl": kl, "bpb": bpb}, indent=2, default=float))
    (RESULTS / "competence_covariates.json").write_text(json.dumps(cov, indent=2, default=float))
    logger.info("analysis written")
    for m in gates:
        for c, g in gates[m].items():
            logger.info(f"GATE {m}/{c}: {g['verdict']} {json.dumps({l: (round(v['loss'], 4), v['verdict']) for l, v in g['per_lang'].items()})}")


if __name__ == "__main__":
    main()
