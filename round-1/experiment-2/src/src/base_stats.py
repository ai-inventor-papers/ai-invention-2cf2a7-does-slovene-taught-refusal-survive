#!/usr/bin/env python3
"""P3/P4 statistics (CPU) from scratch/resid_{model}.npy: CONSTRUCT difference-of-means directions (EN, SL, pooled)
per layer, cross-fitted layer choice in the middle third (16..32), SCORE d' per layer x lang x source
(own-lang / pooled / other-lang), 5-fold CV probe AUROC (+ cross-language probe) with ceiling flag, per-item
harm-z projections at L_pt and the model's own L, style check (low- vs high-EN categories).
Usage: python src/base_stats.py --model pt   (must run first: fixes L_pt)   then --model gb"""
from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from loguru import logger

ROOT = Path(__file__).resolve().parents[1]
LOW_EN = {"S5", "S7", "S8", "S13"}
HIGH_EN = {"S2", "S3", "S4", "S9", "S10", "S11", "S14"}
MID = list(range(16, 33))
SEED = 20260923


def dprime(a: np.ndarray, b: np.ndarray) -> float:
    return float((a.mean() - b.mean()) / np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2))


def unit(v: np.ndarray) -> np.ndarray:
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-12)


def fold_bit(item: str, kind: str) -> int:
    h = int(hashlib.sha1(item.encode()).hexdigest(), 16)
    return (h >> 2) & 1 if kind == "harm" else h & 1  # harm CONSTRUCT items all have h%4==0 -> use bit 2


def probe_job(args):
    from sklearn.decomposition import PCA
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import StratifiedKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    layer, Xe, ye, Xs, ys = args

    def pipe():
        return make_pipeline(StandardScaler(), PCA(128, random_state=SEED),
                             LogisticRegression(C=1.0, max_iter=2000, class_weight="balanced"))
    out = {"layer": layer}
    for lang, X, y in [("en", Xe, ye), ("sl", Xs, ys)]:
        scores = np.zeros(len(y))
        for tr, te in StratifiedKFold(5, shuffle=True, random_state=SEED).split(X, y):
            m = pipe().fit(X[tr], y[tr])
            scores[te] = m.decision_function(X[te])
        out[f"auroc_{lang}"] = float(roc_auc_score(y, scores))
    m = pipe().fit(Xe, ye)
    out["auroc_en_to_sl"] = float(roc_auc_score(ys, m.decision_function(Xs)))
    m = pipe().fit(Xs, ys)
    out["auroc_sl_to_en"] = float(roc_auc_score(ye, m.decision_function(Xe)))
    for k in list(out):
        if k.startswith("auroc"):
            out[k.replace("auroc", "ceiling")] = out[k] > 0.99
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tag", default="")
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
    logger.add(ROOT / f"logs/base_stats_{a.model}{a.tag}.log", rotation="30 MB", level="DEBUG")
    out_dir = ROOT / f"results/base_{a.model}{a.tag}"
    idx = [json.loads(l) for l in (out_dir / "resid_index.jsonl").read_text().splitlines()]
    _cache = ROOT / f"scratch/resid_{a.model}{a.tag}.npy"
    if not _cache.exists():
        raise FileNotFoundError(f"{_cache} is a regenerable cache (not kept, >100 MB): run src/base_geometry.py first")
    X = np.load(_cache)  # into RAM (~5 GB); mmap fancy-indexing on the network FS is very slow
    NL = X.shape[1]
    kind = np.array([r["kind"] for r in idx]); lang = np.array([r["lang"] for r in idx])
    role = np.array([r["role"] for r in idx]); cat = np.array([r["category"] for r in idx])
    items = np.array([r["item"] for r in idx])
    fb = np.array([fold_bit(r["item"], r["kind"]) for r in idx])

    def sel(k, ro, la, extra=None):
        m = (kind == k) & (role == ro) & (lang == la)
        if extra is not None:
            m &= extra
        return np.where(m)[0]

    # ---------------- directions per layer (fp32)
    dirs = {}
    hmean = {}
    for la in ["en", "sl"]:
        mh = np.asarray(X[sel("harm", "CONSTRUCT", la)], dtype=np.float32).mean(0)
        mb = np.asarray(X[sel("harmless", "CONSTRUCT", la)], dtype=np.float32).mean(0)
        dirs[la] = mh - mb
        hmean[la] = mb
    dirs["pooled"] = (dirs["en"] + dirs["sl"]) / 2
    np.savez(out_dir / "directions.npz", **{f"raw_{k}": v for k, v in dirs.items()},
             **{f"unit_{k}": unit(v) for k, v in dirs.items()}, **{f"harmless_mean_{k}": v for k, v in hmean.items()})

    # ---------------- cross-fitted layer choice (pooled d', mid third)
    cf = {}
    for l in MID:
        vals = []
        for f in [0, 1]:
            dl = []
            for la in ["en", "sl"]:
                h_tr = sel("harm", "CONSTRUCT", la, fb == f); b_tr = sel("harmless", "CONSTRUCT", la, fb == f)
                dl.append(np.asarray(X[h_tr, l], np.float32).mean(0) - np.asarray(X[b_tr, l], np.float32).mean(0))
            r = unit((dl[0] + dl[1]) / 2)
            ds = []
            for la in ["en", "sl"]:
                h_te = sel("harm", "CONSTRUCT", la, fb != f); b_te = sel("harmless", "CONSTRUCT", la, fb != f)
                ds.append(dprime(np.asarray(X[h_te, l], np.float32) @ r, np.asarray(X[b_te, l], np.float32) @ r))
            vals.append(np.mean(ds))
        cf[l] = float(np.mean(vals))
    L_own = int(max(cf, key=cf.get))
    lc_path = ROOT / "results/base_pt/layer_choice.json"
    if a.model == "pt" and not a.tag:  # only the pre-registered last-token run fixes L_pt
        lc_path.write_text(json.dumps({"L_pt": L_own, "crossfit_pooled_dprime": cf}, indent=1))
    L_pt = json.loads(lc_path.read_text())["L_pt"] if lc_path.exists() else L_own
    logger.info(f"{a.model}: own L={L_own} (crossfit d'={cf[L_own]:.2f}); L_pt={L_pt}")

    # ---------------- SCORE d' per layer x lang x source
    layer_stats = {"model": a.model, "L_own": L_own, "L_pt": L_pt, "crossfit": cf, "per_layer": []}
    Ud = {k: unit(v) for k, v in dirs.items()}
    for l in range(NL):
        rec = {"layer": l}
        for la in ["en", "sl"]:
            H = np.asarray(X[sel("harm", "SCORE", la), l], np.float32)
            B = np.asarray(X[sel("harmless", "SCORE", la), l], np.float32)
            other = "sl" if la == "en" else "en"
            for src, key in [("own", la), ("pooled", "pooled"), ("transfer", other)]:
                r = Ud[key][l]
                rec[f"dprime_{la}_{src}"] = dprime(H @ r, B @ r)
        rec["cos_en_sl"] = float(Ud["en"][l] @ Ud["sl"][l])
        layer_stats["per_layer"].append(rec)

    # ---------------- probes
    L_gb = None
    gb_lc = ROOT / f"results/base_gb{a.tag}/layer_stats.json"
    if a.model == "gb":
        L_gb = L_own
    elif gb_lc.exists():
        L_gb = json.loads(gb_lc.read_text()).get("L_own")
    probe_layers = sorted(set(list(range(4, NL, 4)) + [L_pt, L_own] + ([L_gb] if L_gb else [])))
    jobs = []
    for l in probe_layers:
        he, be = sel("harm", "SCORE", "en"), sel("harmless", "SCORE", "en")
        hs, bs = sel("harm", "SCORE", "sl"), sel("harmless", "SCORE", "sl")
        Xe = np.asarray(X[np.r_[he, be], l], np.float32); ye = np.r_[np.ones(len(he)), np.zeros(len(be))]
        Xs = np.asarray(X[np.r_[hs, bs], l], np.float32); ys = np.r_[np.ones(len(hs)), np.zeros(len(bs))]
        jobs.append((l, Xe, ye, Xs, ys))
    with ProcessPoolExecutor(max_workers=min(a.workers, len(jobs)), mp_context=mp.get_context("spawn")) as ex:
        probes = list(ex.map(probe_job, jobs))
    layer_stats["probes"] = probes
    logger.info("probes: " + "; ".join(f"L{p['layer']} en {p['auroc_en']:.3f} sl {p['auroc_sl']:.3f} "
                                       f"x {p['auroc_en_to_sl']:.3f}/{p['auroc_sl_to_en']:.3f}" for p in probes))

    # ---------------- item projections (SCORE) + style check
    proj_rows = []
    for l_name, l in [("Lpt", L_pt), ("Lown", L_own)]:
        for la in ["en", "sl"]:
            b_idx = sel("harmless", "SCORE", la)
            for src in ["pooled", "own"]:
                r = Ud["pooled" if src == "pooled" else la][l]
                pb = np.asarray(X[b_idx, l], np.float32) @ r
                mu, sd = float(pb.mean()), float(pb.std(ddof=1))
                all_idx = np.r_[sel("harm", "SCORE", la), b_idx]
                p = np.asarray(X[all_idx, l], np.float32) @ r
                for i, pi in zip(all_idx, p):
                    proj_rows.append({"uid": idx[i]["uid"], "item": idx[i]["item"], "kind": idx[i]["kind"], "lang": la,
                                      "category": idx[i]["category"], "layer_name": l_name, "layer": l, "dir": src,
                                      "proj": float(pi), "harm_z": float((pi - mu) / sd)})
    with (out_dir / "item_proj.jsonl").open("w") as f:
        for r in proj_rows:
            f.write(json.dumps(r) + "\n")
    style = {}
    for la in ["en", "sl"]:
        r = Ud["pooled"][L_pt]
        lo = np.asarray(X[sel("harm", "SCORE", la, np.isin(cat, list(LOW_EN))), L_pt], np.float32) @ r
        hi = np.asarray(X[sel("harm", "SCORE", la, np.isin(cat, list(HIGH_EN))), L_pt], np.float32) @ r
        b = np.asarray(X[sel("harmless", "SCORE", la), L_pt], np.float32) @ r
        style[la] = {"dprime_lowEN_vs_highEN": dprime(lo, hi), "dprime_lowEN_vs_harmless": dprime(lo, b),
                     "dprime_highEN_vs_harmless": dprime(hi, b), "n_low": int(len(lo)), "n_high": int(len(hi))}
    layer_stats["style_check_at_Lpt"] = style
    (out_dir / "layer_stats.json").write_text(json.dumps(layer_stats, indent=1))
    pl = layer_stats["per_layer"]
    logger.info(f"{a.model} d' at L_pt={L_pt}: EN {pl[L_pt]['dprime_en_pooled']:.2f} SL {pl[L_pt]['dprime_sl_pooled']:.2f}; "
                f"at own L={L_own}: EN {pl[L_own]['dprime_en_pooled']:.2f} SL {pl[L_own]['dprime_sl_pooled']:.2f}; style {style}")


if __name__ == "__main__":
    main()
