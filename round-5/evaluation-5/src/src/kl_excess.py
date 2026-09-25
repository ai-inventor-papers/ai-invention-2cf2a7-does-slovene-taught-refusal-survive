#!/usr/bin/env python3
"""STEP 2 - C5a leakage ratio with intervals.

excess = [KL_E(SL)/KL_E(EN)] / [mean_s KL_R_s(SL) / mean_s KL_R_s(EN)]  (seed-pooled random ratio)
exp15 saved only per-condition MEANS (src/gen.py phase_kl stores kl_mean, kl_median, n) -> points + sensitivity ranges.
exp14 (per_stem, 32 stems) and exp9 (c5a_kl.jsonl, 100 items x 5 seeds) saved per-item KL -> item bootstrap.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from collections import defaultdict

import numpy as np
from loguru import logger
from scipy import stats

from common import (B, EXP4, EXP9, EXP12, EXP14, EXP15, MODELS, RES, SEED, bca_ci, get_path, pct_ci, read_json,
                    read_jsonl, rel, setup_logging, write_json)

NOT_SAMPLING = ("sensitivity range, NOT a sampling interval: exp15 src/gen.py phase_kl stores only kl_mean, kl_median "
                "and n per (model, edit, lambda, language); per-item KL was not saved")


def excess_from_means(e_en: float, e_sl: float, r_en: list[float], r_sl: list[float]) -> float:
    return (e_sl / e_en) / (np.mean(r_sl) / np.mean(r_en))


def verdict(ci: list | None) -> str:
    if ci is None or None in ci:
        return "POINT-ONLY"
    if ci[0] > 1:
        return "LEAKAGE"
    if ci[1] < 1:
        return "NO-LEAKAGE"
    return "UNDETERMINED"


# ------------------------------------------------------------------ 2a exp15
def exp15_points() -> dict:
    rows = read_jsonl(EXP15 / "results/kl_harmless.jsonl")
    idx = {(r["model"], r["edit"], round(r["lambda"], 4), r["lang"]): r for r in rows}
    out = {}
    for m in MODELS:
        lamR = sorted({round(r["lambda"], 4) for r in rows if r["model"] == m and r["edit"].startswith("rand_")})
        seeds = sorted({r["edit"] for r in rows if r["model"] == m and r["edit"].startswith("rand_")})
        per = []
        for lam in lamR:
            rec = {"lambda": lam}
            for stat in ("kl_mean", "kl_median"):
                E = {l: idx[(m, "E_exp9", lam, l)][stat] for l in ("en", "sl")}
                R = {s: {l: idx[(m, s, lam, l)][stat] for l in ("en", "sl")} for s in seeds}
                pooled = excess_from_means(E["en"], E["sl"], [R[s]["en"] for s in seeds], [R[s]["sl"] for s in seeds])
                per_seed = {s: (E["sl"] / E["en"]) / (R[s]["sl"] / R[s]["en"]) for s in seeds}
                suf = "" if stat == "kl_mean" else "_median"
                rec[f"E_ratio{suf}"] = E["sl"] / E["en"]
                rec[f"rand_ratio_pooled{suf}"] = np.mean([R[s]["sl"] for s in seeds]) / np.mean([R[s]["en"] for s in seeds])
                rec[f"excess_pooled{suf}"] = pooled
                rec[f"excess_per_seed{suf}"] = per_seed
                rec[f"excess_geomean_seeds{suf}"] = float(np.exp(np.mean(np.log(list(per_seed.values())))))
                if stat == "kl_mean":
                    rec["raw_E_en"], rec["raw_E_sl"] = E["en"], E["sl"]
                    rec["raw_R"] = R
            per.append(rec)
        top = per[-1]
        allv = [x for r in per for x in [r["excess_pooled"], *r["excess_per_seed"].values()]]
        out[m] = {"lambdas_with_random": lamR, "rand_seeds": seeds, "per_lambda": per, "top_dose": top,
                  "point_excess_top_dose": top["excess_pooled"],
                  "sensitivity_range_seed_and_dose": [min(allv), max(allv)],
                  "sensitivity_range_seed_top_dose": [min(top["excess_per_seed"].values()), max(top["excess_per_seed"].values())],
                  "sensitivity_range_dose_pooled": [min(r["excess_pooled"] for r in per), max(r["excess_pooled"] for r in per)],
                  "range_label": NOT_SAMPLING, "n_prompts": 40, "prompt_set": "exp9 data/gate_harmless40.jsonl (EN-BT vs SL-MT)",
                  "horizon": "first token", "edit": "E_exp9", "verdict": "POINT-ONLY",
                  "source": rel(EXP15 / "results/kl_harmless.jsonl")}
    return out


# ------------------------------------------------------------------ bootstrap helpers
def boot_excess(E: np.ndarray, R: np.ndarray, rng: np.random.Generator, n_boot: int = B, stat: str = "mean",
                resample_seeds: bool = False) -> dict:
    """E [2(en,sl), items]; R [seeds, 2, items]. Paired item bootstrap (items shared across EN/SL and E/random)."""
    def f(ix, sx, st=stat):
        if st == "mean":
            e = E[:, ix].mean(1)
            r = R[sx][:, :, ix].mean(axis=(0, 2))
        elif st == "trim10":
            e = np.array([stats.trim_mean(E[l, ix], 0.1) for l in (0, 1)])
            r = np.array([stats.trim_mean(R[sx][:, l, :][:, ix].ravel(), 0.1) for l in (0, 1)])
        elif st == "median":
            e = np.median(E[:, ix], 1)
            r = np.array([np.median(R[sx][:, l, :][:, ix]) for l in (0, 1)])
        else:
            raise ValueError(st)
        if e[0] <= 0 or r[0] <= 0 or r[1] <= 0:
            return np.nan
        return (e[1] / e[0]) / (r[1] / r[0])
    nI, nS = E.shape[1], R.shape[0]
    allix, alls = np.arange(nI), np.arange(nS)
    pt = f(allix, alls)
    bs = np.array([f(rng.integers(0, nI, nI), rng.integers(0, nS, nS) if resample_seeds else alls) for _ in range(n_boot)])
    jk = np.array([f(np.delete(allix, i), alls) for i in range(nI)])
    ok = bs[np.isfinite(bs)]
    return {"stat": stat, "point": pt, "ci95_pct": pct_ci(ok), "ci95_bca": bca_ci(pt, ok, jk) if np.isfinite(pt) else [None, None],
            "log_point": float(np.log(pt)) if np.isfinite(pt) and pt > 0 else None,
            "log_ci95_pct": pct_ci(np.log(ok[ok > 0])), "n_boot_finite": int(len(ok)),
            "leave_one_item_out_range": [float(np.nanmin(jk)), float(np.nanmax(jk))] if np.isfinite(jk).any() else [None, None],
            "resample_seeds": resample_seeds}


def lang_shuffle_placebo(E: np.ndarray, R: np.ndarray, rng: np.random.Generator, n: int = 1000) -> dict:
    """swap EN/SL within item (same swap for E and random) -> excess should centre at 1."""
    vals = []
    for _ in range(n):
        s = rng.random(E.shape[1]) < 0.5
        E2 = E.copy()
        E2[:, s] = E2[::-1][:, s]
        R2 = R.copy()
        R2[:, :, s] = R2[:, ::-1, :][:, :, s]
        e = E2.mean(1)
        r = R2.mean(axis=(0, 2))
        vals.append((e[1] / e[0]) / (r[1] / r[0]))
    v = np.log(np.array(vals))
    return {"n": n, "median_excess": float(np.exp(np.median(v))), "geomean_excess": float(np.exp(v.mean())),
            "log_sd": float(v.std(ddof=1)), "centred_at_1": bool(abs(np.median(v)) < 0.1)}


# ------------------------------------------------------------------ 2b exp14 / exp9
def exp14_boot(rng: np.random.Generator) -> dict:
    out = {}
    for m in MODELS:
        p = EXP14 / f"results/kl_{m}.json"
        if not p.exists():
            out[m] = {"status": "UNTRACEABLE: file missing"}
            continue
        d = read_json(p)
        E = np.array([d["kl_real_en"]["per_stem"], d["kl_real_sl"]["per_stem"]], float)
        R = np.array([[d["kl_rand_en"]["per_stem"], d["kl_rand_sl"]["per_stem"]]], float)
        E, R = np.clip(E, 0, None), np.clip(R, 0, None)  # rounded -0.0 entries
        pt_saved = (d["kl_real_sl"]["mean"] / d["kl_real_en"]["mean"]) / (d["kl_rand_sl"]["mean"] / d["kl_rand_en"]["mean"])
        res = {"lambda": d["lambda"], "n_stems": d["n_stems"], "n_random_seeds": 1,
               "saved_means": {k: d[k]["mean"] for k in ("kl_real_en", "kl_real_sl", "kl_rand_en", "kl_rand_sl")},
               "excess_from_saved_means": pt_saved,
               "mean": boot_excess(E, R, rng), "trim10": boot_excess(E, R, rng, stat="trim10"),
               "median": boot_excess(E, R, rng, stat="median"),
               "placebo_language_shuffle": lang_shuffle_placebo(E, R, rng),
               "per_stem_max": {"real_en": float(E[0].max()), "real_sl": float(E[1].max())},
               "note": "per_stem values are rounded to 5 decimals in the saved file; tiny rounding differences vs saved means",
               "prompt_set": "exp14 32 KL stems", "horizon": "first token", "edit": "E_exp9 (lambda-scaled hook)",
               "source": rel(p)}
        res["verdict"] = verdict(res["mean"]["ci95_pct"])
        out[m] = res
        logger.info(f"exp14 {m}: excess {res['mean']['point']:.3f} CI {res['mean']['ci95_pct']} ({res['verdict']})")
    return out


def exp9_boot(rng: np.random.Generator) -> dict:
    an = read_json(EXP9 / "results/analysis.json")["C5a"]
    out = {}
    for m in MODELS:
        p = EXP9 / f"results/{m}/c5a_kl.jsonl"
        if not p.exists():
            out[m] = {"status": "UNTRACEABLE: file missing"}
            continue
        kr = read_jsonl(p)
        sel, rnd = defaultdict(dict), defaultdict(lambda: defaultdict(dict))
        for r in kr:
            if r["edit"] == "selected":
                sel[r["lang"]][r["item_id"]] = r["kl"]
            else:
                rnd[r["seed"]][r["lang"]][r["item_id"]] = r["kl"]
        items = sorted(sel["en"])
        seeds = sorted(rnd)
        E = np.clip(np.array([[sel[l][i] for i in items] for l in ("en", "sl")]), 0, None)
        R = np.clip(np.array([[[rnd[s][l][i] for i in items] for l in ("en", "sl")] for s in seeds]), 0, None)
        e, r = E.mean(1), R.mean(axis=(0, 2))
        pt = (e[1] / e[0]) / (r[1] / r[0])
        res = {"n_items": len(items), "n_seeds": len(seeds), "saved_excess": an[m]["excess_ratio"],
               "saved_ci95": an[m]["ci95"], "recomputed_point": float(pt),
               "smoke_pass_1e-6": abs(pt - an[m]["excess_ratio"]) < 1e-6,
               "mean": boot_excess(E, R, rng), "mean_items_and_seeds": boot_excess(E, R, rng, resample_seeds=True),
               "trim10": boot_excess(E, R, rng, stat="trim10"), "median": boot_excess(E, R, rng, stat="median"),
               "per_seed_excess": [float((e[1] / e[0]) / (R[s, 1].mean() / R[s, 0].mean())) for s in range(len(seeds))],
               "placebo_language_shuffle": lang_shuffle_placebo(E, R, rng),
               "prompt_set": "exp8 eval_kl stems (100 items)", "horizon": "first token", "edit": "exp9 selected adapter (lambda 1)",
               "source": rel(p)}
        res["verdict"] = verdict(res["mean"]["ci95_pct"])
        out[m] = res
        logger.info(f"exp9 {m}: excess {pt:.4f} (saved {an[m]['excess_ratio']:.4f}) CI {res['mean']['ci95_pct']}")
    return out


# ------------------------------------------------------------------ 2c GPU gate
def gpu_status() -> dict:
    """Preconditions for the optional per-item recompute of exp15's 40-prompt KL; skipped if any fails."""
    st = {"gpu": False, "weights_in_local_cache": False, "hf_token": bool(os.environ.get("HF_TOKEN")),
          "exp9_adapters": (EXP9 / "selected/gemma_it/adapter").exists() and (EXP9 / "adapters/gemma_it/rand_1").exists()}
    if shutil.which("nvidia-smi"):
        try:
            st["gpu"] = "GPU" in subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True, timeout=20).stdout
        except (subprocess.SubprocessError, OSError):
            st["gpu"] = False
    hub = os.environ.get("HF_HUB_CACHE") or os.path.join(os.environ.get("HF_HOME", ""), "hub")
    need = {"models--google--gemma-3-12b-it": "96b6f1eccf38110c56df3a15bffe176da04bfd80",
            "models--cjvt--GaMS3-12B-Instruct": "1d0b27af5748784482600d24779409e7e1dc9adc"}
    detail = {}
    for n, rev in need.items():
        snap = os.path.join(hub, n, "snapshots", rev)
        idx = os.path.join(snap, "model.safetensors.index.json")
        ok, why = False, "snapshot dir missing"
        if os.path.isfile(idx):
            import json as _json
            shards = sorted(set(_json.load(open(idx))["weight_map"].values()))
            missing = [s for s in shards if not (os.path.exists(os.path.join(snap, s)) and os.path.getsize(os.path.join(snap, s)) > 1e8)]
            ok, why = not missing, (f"{len(missing)}/{len(shards)} weight shards missing or incomplete" if missing else "complete")
        elif os.path.isdir(snap):
            why = "snapshot present but no safetensors index (weights not downloaded)"
        detail[n] = why
        st.setdefault("weights_ok", {})[n] = ok
    st["weights_in_local_cache"] = all(st["weights_ok"].values())
    st["weights_detail"] = detail
    st["ran"] = (RES / "kl_items_exp15_recomputed.jsonl").exists()
    fails = [k for k in ("gpu", "weights_in_local_cache", "hf_token", "exp9_adapters") if not st[k]]
    st["status"] = ("SKIPPED: precondition(s) failed: " + ", ".join(fails) +
                    ". exp15 loaded the pinned Gemma-3-12B-IT@96b6f1ec / GaMS3-12B-Instruct@1d0b27af weights with "
                    "HF_HUB_OFFLINE=1 from the shared cache; at run time the cache did not hold complete weight shards "
                    "(see weights_detail; a concurrent job may be re-downloading them). Downloading ~48 GB is outside this "
                    "analysis-only artifact, so exp15 C5a stays POINT-ONLY."
                    ) if fails else ("preconditions met; recompute ran (see gpu_recompute_gate)" if st["ran"]
                                     else "preconditions met but recompute not run within the time box")
    return st


def exp15_recomputed(e15: dict, rng: np.random.Generator) -> dict | None:
    """Gate + item bootstrap on the optional GPU re-measurement (results/kl_items_exp15_recomputed.jsonl)."""
    p = RES / "kl_items_exp15_recomputed.jsonl"
    if not p.exists():
        return None
    rows = read_jsonl(p)
    saved = {(r["model"], r["edit"], round(r["lambda"], 4), r["lang"]): r["kl_mean"] for r in read_jsonl(EXP15 / "results/kl_harmless.jsonl")}
    out = {"file": rel(p), "per_model": {}}
    gate_ok = True
    for m in MODELS:
        rr = {(r["edit"], round(r["lambda"], 4), r["lang"]): r for r in rows if r["model"] == m}
        if not rr:
            out["per_model"][m] = {"status": "not run"}
            gate_ok = False
            continue
        lams = sorted({l for (_, l, _) in rr})
        top = lams[-1]
        g = {}
        for lang in ("en", "sl"):
            new_, old_ = rr[("E_exp9", top, lang)]["kl_mean"], saved[(m, "E_exp9", top, lang)]
            g[lang] = {"recomputed": new_, "saved": old_, "rel_diff": abs(new_ - old_) / old_, "pass_5pct": abs(new_ - old_) / old_ <= 0.05}
        agree = {f"{e}|{l}|{lang}": {"recomputed": r["kl_mean"], "saved": saved.get((m, e, l, lang))}
                 for (e, l, lang), r in rr.items()}
        per_l = []
        for lam in lams:
            E = np.clip(np.array([rr[("E_exp9", lam, "en")]["kl_items"], rr[("E_exp9", lam, "sl")]["kl_items"]]), 0, None)
            R = np.clip(np.array([[rr[(sd, lam, "en")]["kl_items"], rr[(sd, lam, "sl")]["kl_items"]] for sd in ("rand_1", "rand_2")]), 0, None)
            b = boot_excess(E, R, rng)
            per_l.append({"lambda": lam, "excess_recomputed": b["point"], "ci95_pct": b["ci95_pct"], "ci95_bca": b["ci95_bca"],
                          "trim10": boot_excess(E, R, rng, stat="trim10")["point"]})
        ok = all(v["pass_5pct"] for v in g.values())
        gate_ok = gate_ok and ok
        out["per_model"][m] = {"gate_top_dose_E_exp9": g, "gate_pass": ok, "per_lambda": per_l, "all_means_vs_saved": agree,
                               "top_dose_ci95": per_l[-1]["ci95_pct"], "top_dose_excess_recomputed": per_l[-1]["excess_recomputed"],
                               "saved_means_point": e15[m]["point_excess_top_dose"],
                               "verdict": verdict(per_l[-1]["ci95_pct"]) if ok else "POINT-ONLY (recompute not reproduced; CI is sensitivity only)"}
    out["pass"] = gate_ok
    return out


# ------------------------------------------------------------------ 2d reconciliation
def reconciliation(e15: dict, e14: dict, e9: dict, gate: dict | None = None) -> dict:
    rows = []
    try:
        a4 = read_json(EXP4 / "results/analysis.json")["C5a"]
        for m in MODELS:
            x = a4[m]["norm_matched"]["excess"]
            rows.append({"body": "exp4 (iter 1)", "model": m, "point": x["est"], "ci95": x["ci95"], "ci_type": "saved (item bootstrap)",
                         "prompt_set": "exp4 KL stems", "horizon": "first token", "lambda": 1.0, "edit": "iter-1 selected Heretic",
                         "source": rel(EXP4 / "results/analysis.json"), "json_path": f"C5a/{m}/norm_matched/excess"})
    except (FileNotFoundError, KeyError) as e:
        rows.append({"body": "exp4 (iter 1)", "status": f"UNTRACEABLE: {e}"})
    for m in MODELS:
        x = e9.get(m, {})
        if "mean" in x:
            rows.append({"body": "exp9 (iter 3)", "model": m, "point": x["recomputed_point"], "ci95": x["mean"]["ci95_pct"],
                         "ci_type": "item bootstrap (this artifact)", "saved_ci95": x["saved_ci95"], "prompt_set": x["prompt_set"],
                         "horizon": "first token", "lambda": 1.0, "edit": x["edit"], "source": x["source"], "json_path": "per-item rows"})
    try:
        k12 = read_json(EXP12 / "results/kl_footprint.json")
        for m in MODELS:
            for hz in ("first", "multi"):
                pth = f"kl/{m}/ratios/E_iter1/{hz}/sl_over_enbt/excess_vs_rand"
                x = get_path(k12, pth)
                rows.append({"body": f"exp12 (iter 3, {hz}-token)", "model": m, "point": x["excess"], "ci95": x["ci95"],
                             "ci_type": "saved (item bootstrap)", "prompt_set": "exp12 200 items (EN-BT vs SL-MT)",
                             "horizon": "first token" if hz == "first" else "32-token (multi)", "lambda": 1.0,
                             "edit": "E_iter1", "source": rel(EXP12 / "results/kl_footprint.json"), "json_path": pth})
    except (FileNotFoundError, KeyError) as e:
        rows.append({"body": "exp12", "status": f"UNTRACEABLE: {e}"})
    for m in MODELS:
        x = e14.get(m, {})
        if "mean" in x:
            rows.append({"body": "exp14 (iter 4)", "model": m, "point": x["mean"]["point"], "ci95": x["mean"]["ci95_pct"],
                         "ci_type": "stem bootstrap (this artifact)", "prompt_set": x["prompt_set"], "horizon": "first token",
                         "lambda": x["lambda"], "edit": x["edit"], "source": x["source"], "json_path": "per_stem"})
    for m in MODELS:
        x = e15[m]
        g = (gate or {}).get("per_model", {}).get(m, {})
        if g.get("gate_pass"):
            rows.append({"body": "exp15 (iter 4)", "model": m, "point": x["point_excess_top_dose"], "ci95": g["top_dose_ci95"],
                         "ci_type": "item bootstrap on the gated GPU re-measurement of the same 40 prompts (gate passed; "
                                    f"re-measured point {g['top_dose_excess_recomputed']:.3f})",
                         "prompt_set": x["prompt_set"], "horizon": "first token", "lambda": x["top_dose"]["lambda"],
                         "edit": x["edit"], "source": x["source"] + " + results/kl_items_exp15_recomputed.jsonl", "json_path": "kl_mean rows"})
            continue
        rows.append({"body": "exp15 (iter 4)", "model": m, "point": x["point_excess_top_dose"], "ci95": None,
                     "ci_type": "none (" + NOT_SAMPLING + ")", "sensitivity_range": x["sensitivity_range_seed_and_dose"],
                     "prompt_set": x["prompt_set"], "horizon": "first token", "lambda": x["top_dose"]["lambda"],
                     "edit": x["edit"], "source": x["source"], "json_path": "kl_mean rows"})
    for r in rows:
        if "point" in r:
            r["verdict"] = verdict(r.get("ci95"))
    ci_rows = [r for r in rows if r.get("verdict") in ("LEAKAGE", "NO-LEAKAGE", "UNDETERMINED")]
    all_no = all(r["verdict"] == "NO-LEAKAGE" for r in ci_rows)
    point_only = [f"{r['body']} {r['model']}" for r in rows if r.get("verdict") == "POINT-ONLY"]
    undet = [f"{r['body']} {r['model']}" for r in rows if r.get("verdict") == "UNDETERMINED"]
    leak = [f"{r['body']} {r['model']}" for r in rows if r.get("verdict") == "LEAKAGE"]
    if all_no and not point_only:
        sent = "'No Slovene-specific first-token leakage' holds in every body with a CI."
    else:
        sent = ("'No Slovene-specific leakage' is supported only in the bodies whose excess-ratio CI lies below 1 "
                f"({len([r for r in ci_rows if r['verdict'] == 'NO-LEAKAGE'])} of {len(ci_rows)} rows with a CI)"
                + (f"; UNDETERMINED in {', '.join(undet)}" if undet else "")
                + (f"; LEAKAGE in {', '.join(leak)}" if leak else "")
                + (f"; exp15 is POINT-ONLY ({', '.join(point_only)}) because per-item KL was not saved" if point_only else "")
                + ".")
    return {"rows": rows, "sentence": sent}


def main() -> dict:
    setup_logging("kl_excess")
    rng = np.random.default_rng(SEED + 2)
    e15 = exp15_points()
    g = e15["gemma_it"]["top_dose"]
    s = e15["gams3_it"]["top_dose"]
    smoke = {"gemma_top_E_ratio": g["E_ratio"], "gemma_top_rand_pooled": g["rand_ratio_pooled"], "gemma_top_excess": g["excess_pooled"],
             "gemma_per_seed": g["excess_per_seed"], "gams_top_E_ratio": s["E_ratio"], "gams_top_rand_pooled": s["rand_ratio_pooled"],
             "gams_top_excess": s["excess_pooled"], "gams_per_seed": s["excess_per_seed"],
             "expected_review_points": {"gemma": 0.959, "gams": 0.796},
             "pass": abs(g["excess_pooled"] - 0.959) < 0.0015 and abs(s["excess_pooled"] - 0.796) < 0.0015}
    logger.info(f"exp15 smoke: gemma {g['excess_pooled']:.4f} gams {s['excess_pooled']:.4f} pass={smoke['pass']}")
    e14 = exp14_boot(rng)
    e9 = exp9_boot(rng)
    gate = exp15_recomputed(e15, rng)
    rec = reconciliation(e15, e14, e9, gate)
    res = {"estimator": "excess = [KL_E(SL)/KL_E(EN)] / [mean_s KL_R_s(SL) / mean_s KL_R_s(EN)]",
           "smoke_exp15": smoke, "exp15": e15, "exp14": e14, "exp9": e9, "gpu_status": gpu_status(), "gpu_recompute_gate": gate,
           "reconciliation": rec, "post_hoc_label": "POST-HOC sensitivity analysis on already-seen data"}
    write_json(RES / "kl_excess.json", res)
    return res


if __name__ == "__main__":
    main()
