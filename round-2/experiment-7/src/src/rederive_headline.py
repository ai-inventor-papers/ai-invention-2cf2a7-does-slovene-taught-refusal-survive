#!/usr/bin/env python3
"""Independent re-derivation of the headline numbers straight from gens/ + labels/ (no import of analyze/stats/audit).

Kappa is written out by hand from a 2x2 table; the bootstrap is a fresh numpy loop. Placebo checks: the dk and FP-cal
statistics must collapse to ~0 when one system's labels are shuffled across items (pairing destroyed), and the
side-taking statistic must stay ~0 under a random coin-flip 'GaMS'. Writes results/rederive_headline.json.
Usage: python rederive_headline.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
rd = lambda p: [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]  # noqa: E731


def k2(a: np.ndarray, b: np.ndarray) -> float:
    n = len(a)
    n11 = float(np.sum((a == 1) & (b == 1)))
    n00 = float(np.sum((a == 0) & (b == 0)))
    po = (n11 + n00) / n
    pa, pb = a.mean(), b.mean()
    pe = pa * pb + (1 - pa) * (1 - pb)
    return (po - pe) / (1 - pe)


def main() -> None:
    items = {i["item_id"]: i for i in rd(ROOT / "data/items.jsonl")}
    lab = {r["key"]: r["label"] for r in rd(ROOT / "labels/refusal_local.jsonl")}
    blocked = set()
    y: dict[tuple, dict] = {}
    for s in ("gams", "gemma", "q14", "q235", "out"):
        for g in rd(ROOT / f"gens/{s}.jsonl"):
            if g.get("blocked_generation"):
                blocked.add(g["key"])
                continue
            L = lab.get(g["key"])
            if L in ("REFUSE", "PARTIAL", "COMPLY"):
                y.setdefault((s, g["set"], g["lang_arm"], g["condition"]), {})[g["item_id"]] = int(L == "REFUSE")
    out: dict = {}
    rng = np.random.default_rng(20260924)

    def mat(systems, arm):
        ds = [y.get((s, "H", arm, "k0"), {}) for s in systems]
        ids = sorted(set.intersection(*(set(d) for d in ds)))
        return ids, np.array([[d[i] for d in ds] for i in ids])

    for arm in ("en_orig", "sl_mt"):
        ids, M = mat(["gams", "gemma", "q14", "q235"], arm)
        g, ge, q14, q = M.T
        dk = k2(g, q) - k2(g, ge)
        fp = k2(q14, q) - k2(q14, ge)
        B = [rng.integers(0, len(ids), len(ids)) for _ in range(2000)]
        dks = np.array([k2(g[b], q[b]) - k2(g[b], ge[b]) for b in B])
        fps = np.array([k2(q14[b], q[b]) - k2(q14[b], ge[b]) for b in B])
        # placebo: shuffle the teacher's labels across items -> teacher agreement is pure prevalence -> dk must fall
        # to about -kappa(GaMS,Gemma) and FP-cal to about -kappa(Q14,Gemma), i.e. NO 'teacher resemblance' detected
        qs = rng.permutation(q)
        pl = {"dk_teacher_shuffled": k2(g, qs) - k2(g, ge), "k_gams_q235_shuffled": k2(g, qs),
              "fpcal_teacher_shuffled": k2(q14, qs) - k2(q14, ge)}
        # placebo 2: shuffle BOTH comparators identically-independently -> dk distribution centred at 0
        null = []
        for _ in range(500):
            null.append(k2(g, rng.permutation(q)) - k2(g, rng.permutation(ge)))
        pl["dk_both_shuffled_mean"] = float(np.mean(null))
        pl["dk_both_shuffled_q95"] = [float(np.quantile(null, 0.025)), float(np.quantile(null, 0.975))]
        ido, Mo = mat(["gams", "q235", "out"], arm)
        t1b = k2(Mo[:, 0], Mo[:, 1]) - k2(Mo[:, 0], Mo[:, 2])
        out[f"H_{arm}"] = {
            "n_core": len(ids), "dk": dk, "dk_ci95": [float(np.quantile(dks, .025)), float(np.quantile(dks, .975))],
            "fpcal": fp, "fpcal_ci95": [float(np.quantile(fps, .025)), float(np.quantile(fps, .975))],
            "n_out": len(ido), "t1b": t1b,
            "pairwise": {f"{a}~{b}": k2(M[:, i], M[:, j]) for (i, a) in enumerate(["gams", "gemma", "q14", "q235"])
                         for (j, b) in enumerate(["gams", "gemma", "q14", "q235"]) if i < j},
            "placebo": pl}
        if arm == "en_orig":
            # side-taking on discordant teacher/Gemma items, and a coin-flip placebo 'GaMS'
            ido2, M2 = mat(["gams", "gemma", "q235", "out"], arm)
            d = M2[:, 1] != M2[:, 2]
            ps = (M2[d, 0] == M2[d, 2]).mean() - (M2[d, 3] == M2[d, 2]).mean()
            coin = rng.integers(0, 2, d.sum())
            out["side_taking"] = {"n_discordant": int(d.sum()), "gams_minus_out": float(ps),
                                  "placebo_coin_minus_out": float((coin == M2[d, 2]).mean() - (M2[d, 3] == M2[d, 2]).mean())}
    # T2 DiffGap point estimate (items with all four systems in both arms)
    ie, Me = mat(["gams", "gemma", "q14", "q235"], "en_orig")
    isl, Ms = mat(["gams", "gemma", "q14", "q235"], "sl_mt")
    both = sorted(set(ie) & set(isl))
    pe, ps_ = {i: r for i, r in zip(ie, Me)}, {i: r for i, r in zip(isl, Ms)}
    E = np.array([pe[i] for i in both])
    S = np.array([ps_[i] for i in both])
    out["diffgap"] = {"n": len(both), "est": (k2(E[:, 0], E[:, 3]) - k2(E[:, 0], E[:, 1])) -
                      (k2(S[:, 0], S[:, 3]) - k2(S[:, 0], S[:, 1]))}
    # safe-item refusal SL - EN per system
    safe = [i for i in both if not items[i]["is_harmful"]]
    out["safe_refusal_sl_minus_en"] = {s: float(np.mean([ps_[i][k] for i in safe]) - np.mean([pe[i][k] for i in safe]))
                                       for k, s in enumerate(["gams", "gemma", "q14", "q235"])}
    out["safe_refusal_en"] = {s: float(np.mean([pe[i][k] for i in safe])) for k, s in enumerate(["gams", "gemma", "q14", "q235"])}
    out["safe_refusal_sl"] = {s: float(np.mean([ps_[i][k] for i in safe])) for k, s in enumerate(["gams", "gemma", "q14", "q235"])}
    # teacher test-retest (retest rows carry condition 'retest' or a separate key; find them generically)
    rt = {}
    for g in rd(ROOT / "gens/q235.jsonl"):
        if "retest" in g["condition"] and g["key"] in lab and lab[g["key"]] in ("REFUSE", "PARTIAL", "COMPLY"):
            rt[g["item_id"]] = int(lab[g["key"]] == "REFUSE")
    base = y.get(("q235", "H", "en_orig", "k0"), {})
    common = sorted(set(rt) & set(base))
    if common:
        out["retest"] = {"n": len(common), "kappa": k2(np.array([base[i] for i in common]), np.array([rt[i] for i in common]))}
    # T3: verbatim first-sentence share of GaMS EN refusals in the SFT refusal texts (own crude splitter)
    def first_sent(t: str) -> str:
        t = re.sub(r"^[\s*#>_`\-]+", "", t or "").strip()
        return re.split(r"(?<=[.!?])\s|\n", t, maxsplit=1)[0].strip().lower()
    ref = rd(ROOT / "data/ref_sft.jsonl")
    tkey = next(k for k in ("text", "response", "refusal") if k in ref[0])
    lkey = next(k for k in ("lang", "language") if k in ref[0])
    refset = {l: {first_sent(r[tkey]) for r in ref if r[lkey] == l} for l in ("en", "sl")}
    shares = {}
    for s in ("gams", "gemma", "q235", "out"):
        for arm, l in (("en_orig", "en"), ("sl_mt", "sl")):
            fs = [first_sent(g["response"]) for g in rd(ROOT / f"gens/{s}.jsonl")
                  if g["condition"] == "k0" and g["lang_arm"] == arm and g["set"] in ("H", "R")
                  and lab.get(g["key"]) == "REFUSE"]
            if fs:
                shares[f"{s}|{l}"] = {"n": len(fs), "p": float(np.mean([f in refset[l] for f in fs]))}
    out["first_sentence_in_ref_sft"] = shares
    (ROOT / "results/rederive_headline.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float)[:6000])


if __name__ == "__main__":
    main()


def classifier_check() -> dict:
    """T3(d) re-derived through a different model (char 2-5 TF-IDF without word boundaries + linear SVM, not the
    analysis' char_wb + logistic regression), with a label-shuffle placebo that must drop to chance."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    from sklearn.pipeline import make_pipeline
    from sklearn.svm import LinearSVC
    lab = {r["key"]: r["label"] for r in rd(ROOT / "labels/refusal_local.jsonl")}
    tx: dict[str, list[str]] = {}
    for s in ("gams", "gemma", "q14", "q235", "out"):
        tx[s] = [g["response"][:300] for g in rd(ROOT / f"gens/{s}.jsonl")
                 if g["condition"] == "k0" and g["lang_arm"] in ("en_orig", "en_bt") and g["set"] in ("H", "R")
                 and lab.get(g["key"]) == "REFUSE" and g.get("response")]
    X = tx["q235"] + tx["gemma"] + tx["out"]
    y = np.array(["q235"] * len(tx["q235"]) + ["gemma"] * len(tx["gemma"]) + ["out"] * len(tx["out"]))
    mk = lambda: make_pipeline(TfidfVectorizer(analyzer="char", ngram_range=(2, 5), min_df=2, sublinear_tf=True),  # noqa: E731
                               LinearSVC(C=0.5, class_weight="balanced"))
    cv = StratifiedKFold(5, shuffle=True, random_state=7)
    rng = np.random.default_rng(7)
    ys = rng.permutation(y)
    res = {"n_train": {c: int((y == c).sum()) for c in ("q235", "gemma", "out")},
           "cv_acc": float(cross_val_score(mk(), X, y, cv=cv).mean()),
           "placebo_cv_acc_shuffled_labels": float(cross_val_score(mk(), X, ys, cv=cv).mean()),
           "majority_class_rate": float(max((y == c).mean() for c in ("q235", "gemma", "out")))}
    m, mp = mk().fit(X, y), mk().fit(X, ys)
    for s in ("gams", "q14"):
        p, pp = m.predict(tx[s]), mp.predict(tx[s])
        res[f"share_q235|{s}"] = {"n": len(tx[s]), "p": float((p == "q235").mean()),
                                  "placebo_p": float((pp == "q235").mean())}
    return res


if __name__ == "__main__":
    o = json.loads((ROOT / "results/rederive_headline.json").read_text())
    o["classifier_en_independent"] = classifier_check()
    (ROOT / "results/rederive_headline.json").write_text(json.dumps(o, indent=1, default=float))
    print(json.dumps(o["classifier_en_independent"], indent=1))
