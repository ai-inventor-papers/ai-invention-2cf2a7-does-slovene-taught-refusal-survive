#!/usr/bin/env python3
"""RQ4 (frozen-core debt) CHECK: is harmful/harmless information still decodable after the edit?

Per model x state {O, E1 (lambda=1), Estar (lambda*) [, Edir2]} x arm {en_bt, sl_mt, en_orig} x position {post, inst} x
layer (every 4th + L*): 5-fold stratified CV logistic probe (standardise -> PCA-128 fit inside the folds -> L2, C=1) AUROC,
shuffled-label control (selectivity = AUROC - AUROC_shuffled), ceiling flag (> .99); d' of the projection onto the
ORIGINAL model's own-language construct direction (fixed probe; out-of-sample: P200 + rq4_harmless were never used to
build the direction); EN<->SL probe transfer (train one arm, test another, same state); cosine between the state's own
difference of means and the original's. 1000-draw bootstrap CIs at L* (AUROC over out-of-fold scores; d').

Usage: .venv/bin/python src/rq4.py --model gemma_it
"""
from __future__ import annotations

import argparse
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"  # one BLAS thread per process (many threads on tiny matrices spin pathologically)
import json
import multiprocessing as mp
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402

from common import ACTS, RESULTS, SEED  # noqa: E402

ARMS = ["en_bt", "sl_mt", "en_orig"]


def _load(M, st, arm, pos, layer):
    a = np.load(ACTS / M / f"rq4_{st}_harm_{arm}_{pos}.npy", mmap_mode="r")[:, layer, :].astype(np.float32)
    b = np.load(ACTS / M / f"rq4_{st}_harmless_{arm}_{pos}.npy", mmap_mode="r")[:, layer, :].astype(np.float32)
    X = np.concatenate([a, b])
    y = np.concatenate([np.ones(len(a)), np.zeros(len(b))])
    return X, y


def _pipe():
    from sklearn.decomposition import PCA
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return make_pipeline(StandardScaler(), PCA(n_components=128, random_state=SEED), LogisticRegression(C=1.0, max_iter=2000))


def _boot_auc(y, s, n=300):
    from sklearn.metrics import roc_auc_score
    rng = np.random.default_rng(SEED)
    out = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if len(set(y[i])) < 2:
            continue
        out.append(roc_auc_score(y[i], s[i]))
    return [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))]


def job(M, st, pos, layer, is_lstar, dirs_path):
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import StratifiedKFold
    dirs = np.load(dirs_path)
    res = {"state": st, "pos": pos, "layer": layer}
    data = {arm: _load(M, st, arm, pos, layer) for arm in ARMS}
    orig = {arm: _load(M, "O", arm, pos, layer) for arm in ARMS} if st != "O" else data
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    rng = np.random.default_rng(SEED + layer)
    for arm in ARMS:
        X, y = data[arm]
        oof = np.zeros(len(y))
        oof_sh = np.zeros(len(y))
        ysh = rng.permutation(y)
        for tr, te in skf.split(X, y):
            p = _pipe().fit(X[tr], y[tr])
            oof[te] = p.decision_function(X[te])
        for tr, te in skf.split(X, ysh):
            p = _pipe().fit(X[tr], ysh[tr])
            oof_sh[te] = p.decision_function(X[te])
        auc = roc_auc_score(y, oof)
        auc_sh = roc_auc_score(ysh, oof_sh)
        r = {"auroc": float(auc), "auroc_shuffled": float(auc_sh), "selectivity": float(auc - auc_sh), "ceiling": bool(auc > 0.99)}
        if is_lstar:
            r["auroc_ci"] = _boot_auc(y, oof)
        # fixed probe: ORIGINAL model's own-language construct direction (post-position file for both positions' layer)
        key = "rSL" if arm == "sl_mt" else ("rENo" if arm == "en_orig" else "rEN")
        rdir = dirs[key][layer]
        pr = X @ rdir
        a, b = pr[y == 1], pr[y == 0]
        r["dprime_fixed_probe"] = float((a.mean() - b.mean()) / np.sqrt((a.var() + b.var()) / 2))
        # cross-language fixed probe: EN direction applied to this arm (M-a readout, out of sample)
        pr2 = X @ dirs["rEN"][layer]
        a2, b2 = pr2[y == 1], pr2[y == 0]
        r["dprime_along_rEN"] = float((a2.mean() - b2.mean()) / np.sqrt((a2.var() + b2.var()) / 2))
        pr3 = X @ dirs["rSL"][layer]
        a3, b3 = pr3[y == 1], pr3[y == 0]
        r["dprime_along_rSL"] = float((a3.mean() - b3.mean()) / np.sqrt((a3.var() + b3.var()) / 2))
        if is_lstar:
            bs = []
            for _ in range(300):
                ia = rng.integers(0, len(a2), len(a2))
                ib = rng.integers(0, len(b2), len(b2))
                bs.append((a2[ia].mean() - b2[ib].mean()) / np.sqrt((a2[ia].var() + b2[ib].var()) / 2))
            r["dprime_along_rEN_ci"] = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
        # own diff-of-means cosine vs original state's
        Xo, yo = orig[arm]
        d_st = X[y == 1].mean(0) - X[y == 0].mean(0)
        d_o = Xo[yo == 1].mean(0) - Xo[yo == 0].mean(0)
        r["cos_dm_vs_original"] = float(d_st @ d_o / (np.linalg.norm(d_st) * np.linalg.norm(d_o) + 1e-12))
        res[arm] = r
    # transfer (train on one arm, test on another; same state)
    tr_pairs = [("en_bt", "sl_mt"), ("sl_mt", "en_bt"), ("en_orig", "sl_mt")]
    res["transfer"] = {}
    for a_, b_ in tr_pairs:
        Xa, ya = data[a_]
        Xb, yb = data[b_]
        p = _pipe().fit(Xa, ya)
        res["transfer"][f"{a_}->{b_}"] = float(roc_auc_score(yb, p.decision_function(Xb)))
    return res


def _job_star(j):
    return job(*j)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    M = a.model
    dec = json.loads((RESULTS / "dev" / M / "dev_decisions.json").read_text())
    L = dec["layer"]["L_star"]
    states = [s for s in ("O", "E1", "Estar", "Edir2") if (ACTS / M / f"rq4_{s}_harm_en_bt_post.npy").exists()]
    nL = np.load(ACTS / M / "rq4_O_harm_en_bt_post.npy", mmap_mode="r").shape[1]
    layers = sorted(set([8, 12, 20, 28, 36, 44, L]))  # CHECK: representative layers + L* (kept small; RQ4 is a check)
    jobs = [(M, st, pos, l, l == L, str(RESULTS / M / f"directions_{pos}.npz")) for st in states for pos in ("post", "inst") for l in layers]
    import time
    out = []
    t0 = time.time()
    # fork pool of single-threaded workers (spawn workers hung on the shared FS; multi-threaded BLAS spun)
    with mp.get_context("fork").Pool(a.workers) as pool:
        for i, r in enumerate(pool.imap_unordered(_job_star, jobs)):
            out.append(r)
            print(f"  rq4 {M}: {i + 1}/{len(jobs)} ({time.time() - t0:.0f}s)", flush=True)
    out.sort(key=lambda r: (r["state"], r["pos"], r["layer"]))
    summ = {"model": M, "L_star": L, "layers": layers, "states": states, "rows": out}
    at = {f"{r['state']}|{r['pos']}": {arm: r[arm] for arm in ARMS} | {"transfer": r["transfer"]} for r in out if r["layer"] == L}
    summ["at_Lstar"] = at
    p = RESULTS / "rq4.json"
    allr = json.loads(p.read_text()) if p.exists() else {}
    allr[M] = summ
    p.write_text(json.dumps(allr, indent=1))
    print(json.dumps(at, indent=1)[:3000])


if __name__ == "__main__":
    main()
