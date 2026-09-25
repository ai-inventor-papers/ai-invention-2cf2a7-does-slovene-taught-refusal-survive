#!/usr/bin/env python3
"""Vacuity check for the headline tests: rerun each on SHUFFLED input with plain numpy (not eval.py's code), and confirm
it FAILS there. A test that still 'passes' on shuffled input would prove nothing. Writes work/placebo_check.json."""
from __future__ import annotations

import json
import math
import sys

import numpy as np

from common import EXP1, LABELS, WORK, jdump, read_jsonl

rng = np.random.default_rng(777)


def hl(k, n):
    p = (k + 0.5) / (n + 1)
    return math.log(p / (1 - p))


def did(Y):  # Y (n,4): gemma en, gemma sl, gams en, gams sl
    n = len(Y)
    k = Y.sum(0)
    return (hl(k[3], n) - hl(k[2], n)) - (hl(k[1], n) - hl(k[0], n))


def boot_ci(Y, B=1000):
    n = len(Y)
    b = [did(Y[rng.integers(0, n, n)]) for _ in range(B)]
    return np.percentile(b, [2.5, 97.5])


def exp1_Y():
    lab = {(r["model"], r["key"]): r["label"] for r in read_jsonl(EXP1 / "outputs/judge_gemini.jsonl")}
    by = {}
    for j, (m, l) in enumerate([("gemma_it", "en"), ("gemma_it", "sl"), ("gams3_it", "en"), ("gams3_it", "sl")]):
        for r in read_jsonl(EXP1 / f"outputs/gen_{m}.jsonl"):
            if r["lang"] == l and (m, r["key"]) in lab:
                by.setdefault(r["pair_id"], [None] * 4)[j] = int(lab[(m, r["key"])] == "REFUSE")
    return np.array([v for v in by.values() if None not in v], float)


def main():
    out = {}
    # 1. exp1 GaMS Slovene deficit DiD: real CI excludes 0; with model labels shuffled within item it must not
    Y = exp1_Y()
    real = (did(Y), boot_ci(Y).tolist())
    s = rng.random(len(Y)) < 0.5
    Ys = np.where(s[:, None], Y[:, [2, 3, 0, 1]], Y)
    shuf = (did(Ys), boot_ci(Ys).tolist())
    out["exp1_DiD"] = {"real": real, "real_excludes_0": bool(real[1][1] < 0 or real[1][0] > 0),
                       "model_shuffled": shuf, "shuffled_excludes_0": bool(shuf[1][1] < 0 or shuf[1][0] > 0)}
    # 2. C1 identity DiD_id: real passes m_id=.43 with CI>0; shuffled must not
    lab = {(r["model"], r["key"]): r["label"] for r in read_jsonl(EXP1 / "outputs/judge_idname.jsonl")}
    items = [r["iid"] for r in read_jsonl(EXP1 / "data/identity_items.jsonl") if r["type"] == "identity"]
    own = {"gemma_it": "Gemma", "gams3_it": "GaMS"}
    I = np.array([[float(lab.get((m, f"{i}|{l}")) == own[m]) for (m, l) in
                   [("gemma_it", "en"), ("gemma_it", "sl"), ("gams3_it", "en"), ("gams3_it", "sl")]] for i in items])
    r1 = (did(I), boot_ci(I).tolist())
    s = rng.random(len(I)) < 0.5
    Is = np.where(s[:, None], I[:, [2, 3, 0, 1]], I)
    # own-name must be re-scored after swapping: a swapped model's "own" name differs, so shuffle languages instead
    Il = I.copy()
    for c in ((0, 1), (2, 3)):
        t = rng.random(len(I)) < 0.5
        Il[t, c[0]], Il[t, c[1]] = I[t, c[1]], I[t, c[0]]
    r2 = (did(Il), boot_ci(Il).tolist())
    out["C1_DiD_id"] = {"real": r1, "real_passes": bool(r1[0] > 0.43 and r1[1][0] > 0),
                        "language_shuffled": r2, "shuffled_passes": bool(r2[0] > 0.43 and r2[1][0] > 0)}
    # 3. prefill adjudication: best readout kappa vs gold; with gold shuffled kappa must collapse to ~0
    g = json.loads((LABELS / "author_gold_prefill5.json").read_text())["labels_by_spotcheck_index"]
    uids = json.loads((WORK / "spotcheck_uids.json").read_text())
    po = {r["uid"]: r for r in read_jsonl(LABELS / "pooled_surrogate.jsonl.gz")}
    a, b = [], []
    for i, u in enumerate(uids):
        if g[str(i)] != "AMBIG":
            a.append(int(g[str(i)] == "REFUSE"))
            b.append(po[u]["R_pool"])
    a, b = np.array(a), np.array(b)

    def kappa(x, y):
        po_ = (x == y).mean()
        pe = x.mean() * y.mean() + (1 - x.mean()) * (1 - y.mean())
        return (po_ - pe) / (1 - pe)
    ks = [kappa(rng.permutation(a), b) for _ in range(1000)]
    out["prefill_gold_kappa_pooled"] = {"real": float(kappa(a, b)), "shuffled_mean": float(np.mean(ks)),
                                        "shuffled_p95": float(np.percentile(ks, 95)),
                                        "perm_p": float((1 + sum(k >= kappa(a, b) for k in ks)) / 1001)}
    ok = (out["exp1_DiD"]["real_excludes_0"] and not out["exp1_DiD"]["shuffled_excludes_0"] and
          out["C1_DiD_id"]["real_passes"] and not out["C1_DiD_id"]["shuffled_passes"] and
          abs(out["prefill_gold_kappa_pooled"]["shuffled_mean"]) < 0.1)
    out["all_placebos_fail_as_they_should"] = bool(ok)
    jdump(out, WORK / "placebo_check.json")
    print(json.dumps(out, indent=1))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
