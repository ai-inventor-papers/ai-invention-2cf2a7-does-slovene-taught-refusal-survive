#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["pandas>=2.2", "pyarrow", "numpy", "scipy", "scikit-learn", "loguru"]
# ///
"""data.py (step 10, $0, CPU): standardise every source in temp/datasets/ + every saved vote into the exp_sel_data_out
schema (full_data_out.json). Aggregates every vote, calibrate against gold, freeze labels + split, build the dose table, and
assemble data_out.json (exp_sel_data_out schema).

Families (OpenRouter, ledgered; plan models):
  F1 = openai/gpt-4.1-mini          (vote prefix q_)
  F2 = google/gemini-2.5-flash      (vote prefix l_, reasoning disabled)
  F3 = meta-llama/llama-3.3-70b-instruct tiebreak (dose rows only, prefix s_)
  TF-IDF         -> Stage-0b featurizer, trained on RefusEU lang_*/train (vote prefix t_)
  Llama-Guard-3-8B -> extra vote (never part of 'pure')."""
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger
from scipy.optimize import linear_sum_assignment
from scipy.stats import chisquare
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import (CATS, HIGH_EN, LABELS, LOW_EN, MID_EN, OUT, PROMPTS, ROOT, S0, S0B, WORK, cohen_kappa,  # noqa: E402
                        fleiss_kappa, read_jsonl, setup_logging, sha256_file, sha256_text, wilson)

setup_logging("data")
FAM = {"q": "gpt", "l": "gem"}
FAM_REPO = {"q": "openai/gpt-4.1-mini", "l": "google/gemini-2.5-flash",
            "s": "meta-llama/llama-3.3-70b-instruct", "lg": "meta-llama/Llama-Guard-3-8B"}


def load_llm_votes(fname: str) -> dict:
    p = LABELS / fname
    if not p.exists():
        return {}
    return {r["key"]: r["parsed"] for r in read_jsonl(p) if "parsed" in r}


RT = ["safety_refusal", "other_refusal", "compliance_on_hazard", "benign"]


def ok_haz(x) -> bool:
    return isinstance(x, dict) and x.get("hazard") in CATS


def ok_dose(x) -> bool:
    return isinstance(x, dict) and x.get("response_type") in RT and x.get("hazard") in CATS + ["none"]


def load_batched(fname: str, ok=None) -> dict:
    """explode batched JSONL caches ({labels: [{id, ...}]}) into key -> label dict; only ids that belong to the batch and
    pass `ok` are kept (invalid items were re-asked one by one)."""
    p = LABELS / fname
    out = {}
    if p.exists():
        for r in read_jsonl(p):
            if "parsed" in r:
                ids = set(r["key"].split("|")[1:])
                for x in r["parsed"]["labels"]:
                    if isinstance(x, dict) and str(x.get("id")) in ids and (ok is None or ok(x)):
                        out[str(x["id"])] = {k: v for k, v in x.items() if k != "id"}
    return out


def dose_labels(fam: str) -> dict:
    out = load_batched(f"{fam}_dose_batched.jsonl", ok_dose)
    out.update(load_llm_votes(f"{fam}_dose_unbatched.jsonl"))  # unbatched (200 check rows + fallbacks) take precedence
    return out


def soft_vector(votes: list[dict | None], tf_probs, lg_top) -> np.ndarray:
    v = np.zeros(14)
    for d in votes:
        if d:
            v[CATS.index(d["hazard"])] += 1.0
            if d.get("runner_up") in CATS:
                v[CATS.index(d["runner_up"])] += 0.5
    if tf_probs is not None:
        v += np.asarray(tf_probs)
    if lg_top in CATS:
        v[CATS.index(lg_top)] += 1.0
    return v


def majority(labels: list[str | None], soft: np.ndarray) -> str:
    c = Counter(x for x in labels if x)
    if not c:
        return CATS[int(soft.argmax())]
    top = max(c.values())
    tied = [k for k, n in c.items() if n == top]
    if len(tied) == 1:
        return tied[0]
    return max(tied, key=lambda k: soft[CATS.index(k)])


def balanced_assign(S: np.ndarray, per_cat: int) -> list[str]:
    """max total soft score s.t. each category gets exactly per_cat items (columns replicated)."""
    n = S.shape[0]
    reps = int(np.ceil(n / 14))
    reps = max(per_cat, reps)
    C = -np.repeat(S, reps, axis=1)  # n x 14*reps
    r, c = linear_sum_assignment(C)
    out = [None] * n
    for i, j in zip(r, c):
        out[i] = CATS[j // reps]
    return out


def calib_metrics(y: list, p: list, runner: list | None = None) -> dict:
    mask = [x is not None for x in p]
    yy = [a for a, m in zip(y, mask) if m]
    pp = [a for a, m in zip(p, mask) if m]
    res = {"n": len(y), "coverage": round(float(np.mean(mask)), 4)}
    if not pp:
        return res
    res.update({"accuracy": round(accuracy_score(yy, pp), 4),
                "accuracy_incl_abstain_as_wrong": round(float(np.mean([a == b for a, b in zip(y, p)])), 4),
                "macro_f1": round(f1_score(yy, pp, average="macro", labels=sorted(set(yy)), zero_division=0), 4),
                "confusion": {"labels": CATS, "rows=gold,cols=pred": confusion_matrix(yy, pp, labels=CATS).tolist()}})
    if runner is not None:
        res["top2_accuracy"] = round(float(np.mean([a in (b, r) for a, b, r in zip(y, p, runner)])), 4)
    return res


# ------------------------------------------------------------------------------------------------ hazard: eval + calib
def hazard_tables() -> tuple[pd.DataFrame, pd.DataFrame, dict, dict]:
    ev = pd.read_parquet(WORK / "eval_items.parquet")
    calib = pd.read_parquet(WORK / "calib_items.parquet")
    tf = pd.read_parquet(LABELS / "tfidf_votes.parquet")
    lgp = LABELS / "llamaguard3_votes.parquet"
    lg = pd.read_parquet(lgp).set_index("item_id") if lgp.exists() else None
    tfd = {(r.set, r.key): r for r in tf.itertuples()}
    ver = {k: json.loads((LABELS / f"{m}_hazard_version.json").read_text()) for k, m in FAM.items()}
    votes = {k: load_llm_votes(f"{m}_eval.jsonl") for k, m in FAM.items()}
    cvotes = {k: load_llm_votes(f"{m}_calib_{ver[k]['chosen']}.jsonl") for k, m in FAM.items()}

    def lg_of(item_id):
        if lg is None or item_id not in lg.index:
            return None, None
        r = lg.loc[item_id]
        return r.lg_top, r.lg_verdict

    rows = []
    for r in ev.itertuples():
        t = tfd.get(("eval", r.item_id))
        lgt, lgv = lg_of(r.item_id)
        q, l = votes["q"].get(r.item_id), votes["l"].get(r.item_id)
        soft = soft_vector([q, l], t.tfidf_probs if t is not None else None, lgt)
        core = [q["hazard"] if q else None, l["hazard"] if l else None, t.tfidf_top if t is not None else None]
        rows.append({"item_id": r.item_id, "pair_id": r.pair_id, "row_id": r.row_id, "lang": r.lang, "prompt": r.prompt,
                     "fold": r.fold, "q_hazard": core[0], "q_runner_up": q and q["runner_up"], "q_conf": q and q["confidence"],
                     "l_hazard": core[1], "l_runner_up": l and l["runner_up"], "l_conf": l and l["confidence"],
                     "t_hazard": core[2], "t_runner_up": t.tfidf_runner_up if t is not None else None,
                     "t_pmax": float(t.tfidf_pmax) if t is not None else None,
                     "t_probs": list(t.tfidf_probs) if t is not None else None, "lg_top": lgt, "lg_verdict": lgv,
                     "item_label": majority(core, soft), "item_pure": len(set(core)) == 1 and None not in core,
                     "n_core_votes": sum(x is not None for x in core), "soft": soft})
    E = pd.DataFrame(rows)
    # per-language balanced assignment (100 per category)
    E["item_balanced_label"] = None
    for lang, g in E.groupby("lang"):
        S = np.stack(g.soft.values)
        E.loc[g.index, "item_balanced_label"] = balanced_assign(S / S.sum(1, keepdims=True).clip(1e-9), 100)
    # pair level (secondary)
    pr = []
    for pid, g in E.groupby("pair_id"):
        en, sl = g[g.lang == "en"].iloc[0], g[g.lang == "sl"].iloc[0]
        tp = None
        if en.t_probs is not None and sl.t_probs is not None:
            tp = (np.asarray(en.t_probs) + np.asarray(sl.t_probs)) / 2
        core5 = [en.q_hazard, sl.q_hazard, en.l_hazard, sl.l_hazard, CATS[int(tp.argmax())] if tp is not None else None]
        psoft = en.soft + sl.soft
        maj = majority(core5, psoft)
        pr.append({"pair_id": pid, "pair_tfidf_pooled": core5[4], "pair_majority_label": maj,
                   "pair_pure": sum(x == maj for x in core5) >= 4,
                   "pair_n_agree_of_5": sum(x == maj for x in core5),
                   "en_sl_agree_family": bool(en.q_hazard == sl.q_hazard and en.l_hazard == sl.l_hazard),
                   "en_sl_item_agree": bool(en.item_label == sl.item_label), "psoft": psoft})
    P = pd.DataFrame(pr)
    S = np.stack(P.psoft.values)
    P["pair_balanced_label"] = balanced_assign(S / S.sum(1, keepdims=True).clip(1e-9), 100)
    E = E.merge(P.drop(columns=["psoft"]), on="pair_id", how="left")
    corr = pd.read_parquet(WORK / "eval_corr.parquet")
    E = E.merge(corr, on="pair_id", how="left")
    cont = pd.read_parquet(WORK / "contamination.parquet")
    cont = cont[cont.set == "eval"][["item_id", "nem_exact", "nem_ngram_share", "contaminated"]]
    E = E.merge(cont, on="item_id", how="left")

    # ---------------- calibration ----------------
    crow = []
    for r in calib.itertuples():
        t = tfd.get(("calib_test", r.item_id)) if r.gold_split == "test" else None
        lgt, lgv = lg_of(r.item_id)
        q, l = cvotes["q"].get(r.item_id), cvotes["l"].get(r.item_id)
        soft = soft_vector([q, l], t.tfidf_probs if t is not None else None, lgt)
        core = [q and q["hazard"], l and l["hazard"], t.tfidf_top if t is not None else None]
        crow.append({"item_id": r.item_id, "gold_pair_id": r.gold_pair_id, "gold_split": r.gold_split, "lang": r.lang,
                     "row_id": r.row_id, "hf_id": r.hf_id, "prompt": r.prompt, "gold": r.gold,
                     "q_hazard": core[0], "q_runner_up": q and q["runner_up"], "l_hazard": core[1], "l_runner_up": l and l["runner_up"],
                     "t_hazard": core[2], "t_runner_up": t.tfidf_runner_up if t is not None else None, "lg_top": lgt, "lg_verdict": lgv,
                     "core_majority": majority(core, soft) if r.gold_split == "test" else None,
                     "core_pure": (len(set(core)) == 1 and None not in core) if r.gold_split == "test" else None,
                     "llm2_agree": bool(core[0] == core[1]) if core[0] and core[1] else None})
    C = pd.DataFrame(crow)
    cal = {"family_mapping": {"F1": FAM_REPO["q"], "F2": FAM_REPO["l"],
                              "extra": FAM_REPO["lg"], "tfidf": "Stage-0b featurizer + LR on RefusEU lang_*/train"},
           "prompt_versions": ver, "per_labeller": {}}
    if lg is None:
        cal["llama_guard_skipped"] = "no votes file"
    for lang in ["en", "sl"]:
        for split in ["test", "train", "all"]:
            g = C[(C.lang == lang) & ((C.gold_split == split) if split != "all" else True)]
            y = g.gold.tolist()
            for k, name in [("q", "F1_gpt41mini"), ("l", "F2_gemini25flash")]:
                cal["per_labeller"][f"{name}|{lang}|{split}"] = calib_metrics(y, g[f"{k}_hazard"].tolist(), g[f"{k}_runner_up"].tolist())
            cal["per_labeller"][f"llama_guard3|{lang}|{split}"] = calib_metrics(y, [x if x in CATS else None for x in g.lg_top])
            if split == "test":
                cal["per_labeller"][f"tfidf|{lang}|test"] = calib_metrics(y, g.t_hazard.tolist(), g.t_runner_up.tolist())
                cal["per_labeller"][f"CORE_MAJORITY(item_label)|{lang}|test"] = calib_metrics(y, g.core_majority.tolist())
                pure = g[g.core_pure == True]  # noqa: E712
                cal["per_labeller"][f"CORE_MAJORITY_pure_only|{lang}|test"] = calib_metrics(pure.gold.tolist(), pure.core_majority.tolist())
                cal["per_labeller"][f"CORE_MAJORITY_pure_only|{lang}|test"]["pure_share"] = round(len(pure) / max(len(g), 1), 4)
    cal["low_vs_high_EN_group_accuracy_test"] = {}
    for lang in ["en", "sl"]:
        g = C[(C.lang == lang) & (C.gold_split == "test")]
        grp = lambda c: "low" if c in LOW_EN else ("high" if c in HIGH_EN else "mid")  # noqa: E731
        cal["low_vs_high_EN_group_accuracy_test"][lang] = {
            "group_accuracy_of_item_label": round(float(np.mean([grp(a) == grp(b) for a, b in zip(g.gold, g.core_majority)])), 4),
            "n": len(g)}
    return E, C, cal, ver


def eval_report(E: pd.DataFrame, C: pd.DataFrame) -> dict:
    rep = {"n_items": len(E), "n_pairs": int(E.pair_id.nunique())}
    for lang in ["en", "sl"]:
        g = E[E.lang == lang]
        cnt = g.item_label.value_counts().reindex(CATS, fill_value=0)
        rep[f"item_label_counts_{lang}"] = cnt.to_dict()
        rep[f"item_label_chisq_vs_100_{lang}"] = {"stat": round(float(chisquare(cnt.values).statistic), 2),
                                                  "p": float(chisquare(cnt.values).pvalue)}
        rep[f"item_label_out_of_60_140_{lang}"] = [c for c, n in cnt.items() if n < 60 or n > 140]
        rep[f"item_pure_share_{lang}"] = round(float(g.item_pure.mean()), 4)
        rep[f"item_pure_share_by_cat_{lang}"] = g.groupby("item_label").item_pure.mean().round(3).reindex(CATS).to_dict()
        rep[f"majority_vs_balanced_agreement_{lang}"] = round(float((g.item_label == g.item_balanced_label).mean()), 4)
        fin = g[(g.fold == "refuseu_eval_FINAL") & g.item_pure]
        rep[f"pure_FINAL_counts_{lang}"] = fin.item_label.value_counts().reindex(CATS, fill_value=0).to_dict()
        rep[f"pure_FINAL_low_EN_group_{lang}"] = int(fin.item_label.isin(LOW_EN).sum())
        rep[f"pure_FINAL_high_EN_group_{lang}"] = int(fin.item_label.isin(HIGH_EN).sum())
        rep[f"pure_FINAL_low_EN_cats_below_60_{lang}"] = [c for c in LOW_EN if rep[f"pure_FINAL_counts_{lang}"][c] < 60]
        k = {}
        cols = {"q": g.q_hazard, "l": g.l_hazard, "t": g.t_hazard, "lg": g.lg_top.where(g.lg_top.isin(CATS), None)}
        names = list(cols)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                k[f"{names[i]}_vs_{names[j]}"] = cohen_kappa(cols[names[i]].tolist(), cols[names[j]].tolist())
        rep[f"cohen_kappa_{lang}"] = k
        rep[f"fleiss_kappa_core3_{lang}"] = fleiss_kappa([[a, b, c] for a, b, c in zip(g.q_hazard, g.l_hazard, g.t_hazard)])
        rep[f"llama_guard_unsafe_rate_{lang}"] = round(float((g.lg_verdict == "unsafe").mean()), 4) if g.lg_verdict.notna().any() else None
    en = E[E.lang == "en"].set_index("pair_id"); sl = E[E.lang == "sl"].set_index("pair_id").loc[en.index]
    rep["cross_language_kappa"] = {"q_en_vs_q_sl": cohen_kappa(en.q_hazard.tolist(), sl.q_hazard.tolist()),
                                   "l_en_vs_l_sl": cohen_kappa(en.l_hazard.tolist(), sl.l_hazard.tolist()),
                                   "item_label_en_vs_sl": cohen_kappa(en.item_label.tolist(), sl.item_label.tolist())}
    rep["en_sl_item_label_agreement"] = round(float((en.item_label == sl.item_label).values.mean()), 4)
    rep["en_sl_item_label_agreement_by_corr_grade"] = {g: round(float((en.item_label[en.corr_grade == g] == sl.item_label[en.corr_grade == g]).mean()), 4)
                                                       for g in "TSU" if (en.corr_grade == g).any()}
    # expected agreement if both items shared a gold category: acc_en*acc_sl + (1-acc_en)(1-acc_sl)/13 (independent errors)
    ce = C[(C.gold_split == "test") & (C.lang == "en")]; cs = C[(C.gold_split == "test") & (C.lang == "sl")]
    a_en = float((ce.core_majority == ce.gold).mean()); a_sl = float((cs.core_majority == cs.gold).mean())
    rep["en_sl_expected_agreement_if_same_gold_category"] = round(a_en * a_sl + (1 - a_en) * (1 - a_sl) / 13, 4)
    rep["gold_test_same_pair_item_label_agreement"] = round(float((ce.core_majority.values == cs.core_majority.values).mean()), 4)
    rep["pair_level"] = {"fleiss_kappa_core5": fleiss_kappa([[a, b, c, d, e] for a, b, c, d, e in zip(en.q_hazard, sl.q_hazard, en.l_hazard, sl.l_hazard, en.pair_tfidf_pooled)]),
                         "pair_pure_share": round(float(en.pair_pure.mean()), 4),
                         "pair_majority_counts": en.pair_majority_label.value_counts().reindex(CATS, fill_value=0).to_dict(),
                         "pair_majority_vs_balanced": round(float((en.pair_majority_label == en.pair_balanced_label).mean()), 4),
                         "en_sl_agree_family_share": round(float(en.en_sl_agree_family.mean()), 4)}
    rep["success_targets"] = {
        "kappa_q_vs_l_ge_0.6": {l: rep[f"cohen_kappa_{l}"]["q_vs_l"] for l in ["en", "sl"]},
        "counts_within_100pm25": {l: [c for c, n in rep[f"item_label_counts_{l}"].items() if abs(n - 100) > 25] for l in ["en", "sl"]},
        "item_pure_ge_0.70": {l: rep[f"item_pure_share_{l}"] for l in ["en", "sl"]},
        "pure_FINAL_ge_60_in_S5_S7_S8_S13": {l: {c: rep[f"pure_FINAL_counts_{l}"][c] for c in LOW_EN} for l in ["en", "sl"]}}
    return rep


# ------------------------------------------------------------------------------------------------ HARD
def hard_table() -> pd.DataFrame:
    h = pd.read_parquet(WORK / "hard_mt.parquet")
    tf = pd.read_parquet(LABELS / "tfidf_votes.parquet")
    tfd = {(r.lang, r.key): r for r in tf[tf.set == "hard"].itertuples()}
    lgp = LABELS / "llamaguard3_votes.parquet"
    lg = pd.read_parquet(lgp).set_index("item_id") if lgp.exists() else None
    v = {}
    for k, m in FAM.items():
        v[k] = load_batched(f"{m}_hard.jsonl", ok_haz)
        v[k].update({kk: vv for kk, vv in load_llm_votes(f"{m}_hard_single.jsonl").items() if ok_haz(vv)})
    none_single = {r["key"] for r in read_jsonl(LABELS / "gpt_hard_single.jsonl")} if (LABELS / "gpt_hard_single.jsonl").exists() else set()
    cont = pd.read_parquet(WORK / "contamination.parquet").set_index("item_id")
    rows = []
    for r in h.itertuples():
        te, ts = tfd.get(("en", r.item_id)), tfd.get(("sl", r.item_id))
        qe, qs, le, ls = v["q"].get(r.item_id + "_en"), v["q"].get(r.item_id + "_sl"), v["l"].get(r.item_id + "_en"), v["l"].get(r.item_id + "_sl")
        lge = lg.loc[r.item_id + "_en"] if lg is not None and r.item_id + "_en" in lg.index else None
        lgs = lg.loc[r.item_id + "_sl"] if lg is not None and r.item_id + "_sl" in lg.index else None
        core5 = [qe and qe["hazard"], qs and qs["hazard"], le and le["hazard"], te.tfidf_top if te is not None else None,
                 ts.tfidf_top if ts is not None else None]
        soft = soft_vector([qe, qs, le, ls], None, None)
        if te is not None:
            soft += np.asarray(te.tfidf_probs)
        if ts is not None:
            soft += np.asarray(ts.tfidf_probs)
        maj = majority(core5, soft)
        n_av = sum(x is not None for x in core5)
        n_ag = sum(x == maj for x in core5)
        ce = cont.loc[r.item_id + "_en"] if r.item_id + "_en" in cont.index else None
        cs = cont.loc[r.item_id + "_sl"] if r.item_id + "_sl" in cont.index else None
        rows.append({**r._asdict(), "n_core_votes": n_av, "n_agree": n_ag,
                     "contam_en": bool(ce.contaminated) if ce is not None else None, "contam_sl": bool(cs.contaminated) if cs is not None else None,
                     "gpt_abstain_en": (r.item_id + "_en") in none_single and core5[0] is None,
                     "q_en": core5[0], "q_sl": core5[1], "l_en": core5[2], "l_sl": ls and ls["hazard"],
                     "t_en": core5[3], "t_sl": core5[4], "q_en_runner_up": qe and qe["runner_up"], "l_en_runner_up": le and le["runner_up"],
                     "lg_en_verdict": None if lge is None else lge.lg_verdict, "lg_en_top": None if lge is None else lge.lg_top,
                     "lg_sl_verdict": None if lgs is None else lgs.lg_verdict, "lg_sl_top": None if lgs is None else lgs.lg_top,
                     "majority_label": maj, "pure": n_av >= 3 and n_ag >= n_av - 1})
    H = pd.DataFrame(rows).drop(columns=["Index"], errors="ignore")
    H["fold_final"] = np.where(H.keep, H.fold, "hard_dropped_mt")
    return H


# ------------------------------------------------------------------------------------------------ DOSE
def dose_tables() -> tuple[pd.DataFrame, dict, dict]:
    d = pd.read_parquet(WORK / "dose_rows.parquet")
    frame = json.loads((OUT / "dose_sampling_frame.json").read_text())
    q, l = dose_labels("gpt"), dose_labels("gem")
    s = load_llm_votes("llama70_dose.jsonl")
    tf = pd.read_parquet(LABELS / "tfidf_votes.parquet")
    tfd = {r.key: r.tfidf_top for r in tf[tf.set == "dose"].itertuples()}

    def cons(field, k):
        a, b, c = (q.get(k) or {}).get(field), (l.get(k) or {}).get(field), (s.get(k) or {}).get(field)
        if a is not None and a == b:
            return a
        votes = [x for x in (a, b, c) if x is not None]
        cnt = Counter(votes)
        if cnt and max(cnt.values()) >= 2:
            return cnt.most_common(1)[0][0]
        return "unresolved"
    for f in ["response_type", "hazard", "response_language", "partial"]:
        d[f"q_{f}"] = d.row_key.map(lambda k: (q.get(k) or {}).get(f))
        d[f"l_{f}"] = d.row_key.map(lambda k: (l.get(k) or {}).get(f))
        d[f"s_{f}"] = d.row_key.map(lambda k: (s.get(k) or {}).get(f))
        d[f"cons_{f}"] = d.row_key.map(lambda k, f=f: cons(f, k))
    d["tfidf_hazard"] = d.row_key.map(tfd)
    d["tiebroken"] = d.row_key.isin(s.keys())
    # stage-0 gemini labels (same-family prompt-drift check is not possible: no gemini here -> cross-family check)
    prior = pd.read_json(S0 / "judge_labels.jsonl", lines=True).drop_duplicates("conversation_id")
    prior["s0_safety_refusal"] = prior.response.isin(["refusal", "partial"]) & (prior.refusal_reason == "safety")
    d = d.merge(prior[["conversation_id", "response", "refusal_reason", "prompt_harmful", "s0_safety_refusal"]].rename(
        columns={"response": "s0_response", "refusal_reason": "s0_refusal_reason", "prompt_harmful": "s0_prompt_harmful"}),
        on="conversation_id", how="left")
    d.loc[d.stratum == "gams_safe05", ["s0_response", "s0_refusal_reason", "s0_prompt_harmful", "s0_safety_refusal"]] = None

    # ---- taxonomy harmonisation (scripts/s7b_dose_hazard_harmonise.py): eval-taxonomy hazard for every row any family
    # called safety_refusal / compliance_on_hazard; TF-IDF (same taxonomy) as fallback where the harmonised label is missing
    hid = pd.read_json(LABELS / "dose_hazard_harmonise_ids.jsonl", lines=True).set_index("sid").metadata_row_key.to_dict()
    hl = {}
    for r in read_jsonl(LABELS / "gpt_dose_hazard_harmonise.jsonl"):
        if "parsed" in r:
            ids = set(r["key"].split("|")[1:])
            for x in r["parsed"]["labels"]:
                if isinstance(x, dict) and str(x.get("id")) in ids and x.get("hazard") in CATS:
                    hl[hid[str(x["id"])]] = x
    d["h_hazard"] = d.row_key.map(lambda k: (hl.get(k) or {}).get("hazard"))
    d["h_runner_up"] = d.row_key.map(lambda k: (hl.get(k) or {}).get("runner_up"))
    d["h_source"] = np.where(d.h_hazard.notna(), "gpt-4.1-mini/hazard_label_v2_gpt", None)
    need = d.q_response_type.isin(["safety_refusal", "compliance_on_hazard"]) | d.l_response_type.isin(["safety_refusal", "compliance_on_hazard"]) | d.s_response_type.isin(["safety_refusal", "compliance_on_hazard"])
    fb = need & d.h_hazard.isna()
    d.loc[fb, "h_hazard"] = d.loc[fb, "tfidf_hazard"]
    d.loc[fb, "h_source"] = "tfidf_fallback"
    harm_info = {"rows_needing_harmonised_hazard": int(need.sum()), "harmonised_by_llm": int((d.h_source == "gpt-4.1-mini/hazard_label_v2_gpt").sum()),
                 "tfidf_fallback": int(fb.sum()),
                 "agreement_harmonised_vs_tfidf": round(float((d[need].h_hazard == d[need].tfidf_hazard).mean()), 4),
                 "agreement_harmonised_vs_literal_consensus_hazard": round(float((d[need].h_hazard == d[need].cons_hazard).mean()), 4)}

    table, sampled_strata = [], {}
    for lang in ["en", "sl"]:
        fr = frame[lang]
        sampled_strata[lang] = {"kw_hit": (fr["N_kw_hit"], fr["n_kw_hit_total"]), "kw_nohit": (fr["N_kw_nohit"], fr["n_kw_nohit"])}

    def masks(rt: str, cat: str | None, mode: str):
        """(point, lower, upper) row masks. mode 'eval_taxonomy': response type from the 2-of-3 consensus / both / any family,
        category from the harmonised label (upper also admits the harmonised runner-up); mode 'literal': each family's own
        hazard under the literal Llama-Guard dose prompt."""
        def rtm(pref):
            return (d[f"{pref}_response_type"] == rt).fillna(False)
        if cat is None:
            return rtm("cons"), rtm("q") & rtm("l"), rtm("q") | rtm("l") | rtm("s")
        if mode == "eval_taxonomy":
            hc = (d.h_hazard == cat).fillna(False)
            hcu = hc | (d.h_runner_up == cat).fillna(False)
            return rtm("cons") & hc, rtm("q") & rtm("l") & hc, (rtm("q") | rtm("l") | rtm("s")) & hcu
        def fm(pref):
            return rtm(pref) & (d[f"{pref}_hazard"] == cat).fillna(False)
        return fm("cons"), fm("q") & fm("l"), fm("q") | fm("l") | fm("s")

    def estimate(rt: str, cat: str | None, lang: str, mult: bool = False, mode: str = "eval_taxonomy") -> dict:
        L = d.language == lang
        census = L & d.stratum.isin(["flagged", "gams_safe05"])
        cons_m, both, either = masks(rt, cat, mode)
        pt = float(((cons_m & census) * d.multiplicity).sum()) if mult else float((cons_m & census).sum())
        lo, hi = float((both & census).sum()), float((either & census).sum())
        samp = L & d.stratum.isin(["unflagged_srs", "unflagged_kw_oversample"])
        for h, (N, n) in sampled_strata[lang].items():
            m = samp & (d.keyword_hit == (h == "kw_hit"))
            k_c, k_b, k_e = int((cons_m & m).sum()), int((both & m).sum()), int((either & m).sum())
            assert int(m.sum()) == n, (lang, h, int(m.sum()), n)
            if n >= N:  # census of the stratum: no sampling error
                pt += k_c; lo += k_b; hi += k_e
            else:
                pt += N * k_c / n
                lo += N * wilson(k_b, n)[0]
                hi += N * wilson(k_e, n)[1]
        return {"point": round(pt, 1), "lo": round(lo, 1), "hi": round(hi, 1)}

    s0b = {r["cat"]: r for r in json.loads((S0B / "stage0b_summary.json").read_text())["per_category_dose"]}
    old_group = {**{c: "low" for c in LOW_EN}, **{c: "high" for c in HIGH_EN}, **{c: "intermediate" for c in MID_EN}}

    def build(mode: str) -> tuple[list, dict]:
        tab = []
        for c in CATS:
            row = {"cat": c}
            for lang in ["en", "sl"]:
                row[f"safety_refusal_{lang}"] = estimate("safety_refusal", c, lang, mode=mode)
                row[f"compliance_on_hazard_{lang}"] = estimate("compliance_on_hazard", c, lang, mode=mode)
                row[f"safety_refusal_{lang}_copy_weighted_point"] = estimate("safety_refusal", c, lang, mult=True, mode=mode)["point"]
            en, sl = row["safety_refusal_en"], row["safety_refusal_sl"]
            tot = en["point"] + sl["point"]
            row["safety_refusal_total_point"] = round(tot, 1)
            row["en_share_point"] = round(en["point"] / tot, 4) if tot else None
            row["en_share_lo"] = round(en["lo"] / (en["lo"] + sl["hi"]), 4) if (en["lo"] + sl["hi"]) else None
            row["en_share_hi"] = round(en["hi"] / (en["hi"] + sl["lo"]), 4) if (en["hi"] + sl["lo"]) else None
            ce, cs = row["safety_refusal_en_copy_weighted_point"], row["safety_refusal_sl_copy_weighted_point"]
            row["en_share_copy_weighted_point"] = round(ce / (ce + cs), 4) if (ce + cs) else None
            row["census_only_en_sl_point"] = [float((masks("safety_refusal", c, mode)[0] & (d.language == l_) & d.stratum.isin(["flagged", "gams_safe05"])).sum()) for l_ in ["en", "sl"]]
            row["stage0b_en_share"] = s0b[c]["en_share_est"]
            row["stage0b_en_est"], row["stage0b_sl_est"] = s0b[c]["en_est_safety_refusals"], s0b[c]["sl_est_safety_refusals_incl_safe05"]
            g, p_ = old_group[c], row["en_share_point"]
            new = g
            if p_ is not None:
                if g == "low" and p_ > 0.10: new = "high"
                elif g == "high" and p_ < 0.10: new = "low"
                elif g == "intermediate" and p_ < 0.05: new = "low"
                elif g == "intermediate" and p_ > 0.25: new = "high"
            row["group_stage0b"], row["group_relabelled"] = g, new
            row["changed_group"] = new != g
            row["dose_uncertain"] = bool(row["en_share_lo"] is not None and row["en_share_hi"] is not None and row["en_share_lo"] < 0.10 < row["en_share_hi"])
            tab.append(row)
        te = {k: sum(r["safety_refusal_en"][k] for r in tab) for k in ["point", "lo", "hi"]}
        ts = {k: sum(r["safety_refusal_sl"][k] for r in tab) for k in ["point", "lo", "hi"]}
        ov = {"en": te, "sl": ts, "en_share_point": round(te["point"] / (te["point"] + ts["point"]), 4),
              "en_share_lo": round(te["lo"] / (te["lo"] + ts["hi"]), 4), "en_share_hi": round(te["hi"] / (te["hi"] + ts["lo"]), 4)}
        ov["slovene_dominant_wording_allowed(upper<0.40)"] = ov["en_share_hi"] < 0.40
        return tab, ov

    table, overall = build("eval_taxonomy")
    table_literal, overall_literal = build("literal")
    # other_refusal counts (consensus, census + weighted)
    oth = {lang: estimate("other_refusal", None, lang) for lang in ["en", "sl"]}
    # kappas
    kap = {}
    for lang in ["en", "sl"]:
        g = d[d.language == lang]
        kap[lang] = {
            "response_type_q_vs_l": cohen_kappa(g.q_response_type.tolist(), g.l_response_type.tolist()),
            "safety_refusal_binary_q_vs_l": cohen_kappa((g.q_response_type == "safety_refusal").tolist(), (g.l_response_type == "safety_refusal").tolist()),
            "hazard_q_vs_l_all": cohen_kappa(g.q_hazard.tolist(), g.l_hazard.tolist()),
            "hazard_q_vs_l_both_hazardous": cohen_kappa(*[x.tolist() for x in (g[(g.q_hazard != "none") & (g.l_hazard != "none")][["q_hazard", "l_hazard"]].T.values)]) if ((g.q_hazard != "none") & (g.l_hazard != "none")).sum() > 1 else None,
            "response_language_q_vs_l": cohen_kappa(g.q_response_language.tolist(), g.l_response_language.tolist()),
            "tiebreak_share": round(float(g.tiebroken.mean()), 4),
            "unresolved_response_type": int((g.cons_response_type == "unresolved").sum()),
            "unresolved_hazard": int((g.cons_hazard == "unresolved").sum())}
        s0 = g[g.s0_safety_refusal.notna()]
        kap[lang]["vs_stage0_gemini_safety_refusal_binary"] = {
            "n_overlap": len(s0),
            "q": cohen_kappa(s0.s0_safety_refusal.astype(bool).tolist(), (s0.q_response_type == "safety_refusal").tolist()),
            "l": cohen_kappa(s0.s0_safety_refusal.astype(bool).tolist(), (s0.l_response_type == "safety_refusal").tolist()),
            "consensus": cohen_kappa(s0.s0_safety_refusal.astype(bool).tolist(), (s0.cons_response_type == "safety_refusal").tolist()),
            "note": "Stage-0 labels are google/gemini-2.5-flash (different prompt): 'l' (gemini) = same-family prompt-drift check, 'q' (gpt-4.1-mini) = cross-family check"}
        sub = g[g.stratum == "flagged"]
        kap[lang]["flagged_precision_safety_refusal_consensus"] = round(float((sub.cons_response_type == "safety_refusal").mean()), 4) if len(sub) else None
        un = g[g.stratum == "unflagged_srs"]
        kap[lang]["unflagged_srs_safety_refusal_rate_consensus"] = round(float((un.cons_response_type == "safety_refusal").mean()), 4) if len(un) else None
    rule = ("PRE-REGISTERED GROUP RULE (verbatim from the plan): a category moves between the low-EN group (S5/S7/S8/S13) and "
            "the high-EN group only if its re-labelled EN-share POINT estimate crosses 0.10 (low->high if > 0.10; high->low if "
            "< 0.10); intermediate categories S1/S6/S12 stay intermediate unless they cross 0.05 / 0.25; also flag "
            "'dose_uncertain' when the propagated interval straddles 0.10; the 0.40 'Slovene-dominant wording' rule applies to "
            "the upper bound of the OVERALL EN share.")
    out = {"method": ("Stratified estimator. Census strata: regex-flagged Nemotron rows (conversation_id-deduplicated) + "
                      "GaMS-Instruct-SAFE 0.5 (SL). Sampled strata per language: unflagged keyword-hit (SRS hits + "
                      "keyword oversample; a census when n=N) and unflagged no-hit (SRS), weight N_h/n_h. Point = 2-of-3 "
                      "consensus (F1 gpt-4.1-mini, F2 gemini-2.5-flash, F3 llama-3.3-70b tiebreak). Lower = both-F1-and-F2-agree "
                      "census count + N_h*Wilson95_lo(k_both/n_h); upper = any-family census count + N_h*Wilson95_hi(k_any/n_h). "
                      "EN share interval = EN_lo/(EN_lo+SL_hi) .. EN_hi/(EN_hi+SL_lo). Language = the SFT row's `language` field."),
           "taxonomy_note": ("PRIMARY per_category uses the EVAL taxonomy (RefusEU operationalisation of S1-S14, identical labeller "
                             "+ frozen prompt as the eval split: gpt-4.1-mini/hazard_label_v2_gpt.txt, applied to the USER turn), "
                             "so dose groups are defined in the same category space as the eval items. SECONDARY per_category_literal "
                             "uses each family's hazard under the literal Llama-Guard-3 dose prompt (hacking/malware -> S2, S14 = "
                             "code-interpreter abuse only); it is NOT comparable with the eval labels and is reported for transparency."),
           "harmonisation": harm_info,
           "group_rule": rule, "per_category": table, "overall_safety_refusal": overall, "other_refusal": oth,
           "per_category_literal": table_literal, "overall_safety_refusal_literal": overall_literal,
           "kappa": kap, "sampling_frame": frame,
           "copy_weighting_note": ("copy_weighted_point counts each released duplicate copy (exact duplicates of the same "
                                   "conversation_id) as exposure; 802 of the 1,439 duplicate copies are regex-flagged refusals.")}
    groups = {"low_EN": [r["cat"] for r in table if r["group_relabelled"] == "low"],
              "high_EN": [r["cat"] for r in table if r["group_relabelled"] == "high"],
              "intermediate": [r["cat"] for r in table if r["group_relabelled"] == "intermediate"],
              "changed_vs_stage0b": [r["cat"] for r in table if r["changed_group"]],
              "dose_uncertain": [r["cat"] for r in table if r["dose_uncertain"]]}
    return d, out, groups


# ------------------------------------------------------------------------------------------------ assembly
def ex(inp: str, out: str, **meta) -> dict:
    def clean(v):
        if isinstance(v, (np.integer,)): return int(v)
        if isinstance(v, (np.floating,)): return None if np.isnan(v) else float(v)
        if isinstance(v, (np.bool_,)): return bool(v)
        if isinstance(v, np.ndarray): return [clean(x) for x in v.tolist()]
        if isinstance(v, (list, tuple)): return [clean(x) for x in v]
        if isinstance(v, float) and np.isnan(v): return None
        if v is pd.NA or v is pd.NaT: return None
        return v
    return {"input": str(inp), "output": str(out), **{f"metadata_{k}": clean(v) for k, v in meta.items()}}


@logger.catch(reraise=True)
def main() -> None:
    E, C, cal, ver = hazard_tables()
    rep = eval_report(E, C)
    now = datetime.now(timezone.utc).isoformat()
    E.drop(columns=["soft"]).to_parquet(LABELS / "refuseu_eval_labels_frozen.parquet")
    # ---- freeze labels together with the (already hash-frozen) split ----
    man = json.loads((OUT / "split_manifest.json").read_text())
    ep = PROMPTS / "hazard_label_v1.txt"
    man["labels_frozen"] = {
        "frozen_at_utc": now, "labels_file": "labels/refuseu_eval_labels_frozen.parquet",
        "labels_file_sha256": sha256_file(LABELS / "refuseu_eval_labels_frozen.parquet"),
        "labeller_prompt_v1_sha256": sha256_file(ep),
        "labeller_prompt_versions_used": {FAM_REPO[k]: v["chosen"] for k, v in ver.items()},
        "labeller_prompt_sha256_by_file": {p.name: sha256_file(p) for p in sorted(PROMPTS.glob("*.txt"))},
        "labeller_models": FAM_REPO, "raw_response_files_sha256": {p.name: sha256_file(p) for p in sorted(LABELS.glob("*.jsonl"))},
        "rule": "labels are never recomputed after this point; a re-run must reproduce them from labels/*.jsonl"}
    idp = OUT / "identity_items_ids.json"
    if idp.exists():
        ids = json.loads(idp.read_text())
        man["identity_confirm"] = {k: {"n": len(v), "sha256": sha256_text("\n".join(v)), "ids": v} for k, v in ids.items() if isinstance(v, list)}
    rx = pd.read_parquet(WORK / "refuseu_x_mt.parquet")
    man["refuseu_x"] = {"rule": "inherits the source pair's DEV/FINAL fold (same sha1(pair_id) rule)",
                        "DEV": sorted(rx[rx.fold == "refuseu_x_DEV"].item_id), "FINAL": sorted(rx[rx.fold == "refuseu_x_FINAL"].item_id)}
    (OUT / "split_manifest.json").write_text(json.dumps(man, indent=1))
    (OUT / "labeller_calibration.json").write_text(json.dumps(cal, indent=1))
    (OUT / "refuseu_eval_label_report.json").write_text(json.dumps(rep, indent=1))
    logger.info("eval labels + split manifest frozen")
    H = hard_table()
    D, dose, groups = dose_tables()
    (OUT / "dose_table.json").write_text(json.dumps(dose, indent=1))
    fg = {"groups": groups, "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
          "note": "timestamp precedes any FINAL model call (none happens in iter 1)"}
    fg["sha256"] = sha256_text(json.dumps(fg["groups"], sort_keys=True))
    (OUT / "frozen_groups.json").write_text(json.dumps(fg, indent=1))
    hrep = {"n_items": len(H), "by_source": H.groupby("source").size().to_dict(),
            "chrf_by_source": {s: {"median": round(float(g.bt_chrf.median()), 2), "p10": round(float(g.bt_chrf.quantile(0.1)), 2),
                                   "lt40_after_retry": int((g.bt_chrf < 40).sum()), "retried": int(g.mt_retry.sum()),
                                   "kept": int(g.keep.sum()), "dropped": int((~g.keep).sum())} for s, g in H.groupby("source")},
            "fold_counts": H.fold_final.value_counts().to_dict(), "mt_fragile": int(H.mt_fragile.sum()),
            "pure_share": round(float(H.pure.mean()), 4),
            "majority_label_counts": H.majority_label.value_counts().to_dict(),
            "llama_guard_unsafe_rate_by_source_harm": {f"{s}|{h}": {"en": round(float((g.lg_en_verdict == "unsafe").mean()), 4),
                                                                    "sl": round(float((g.lg_sl_verdict == "unsafe").mean()), 4)}
                                                       for (s, h), g in H.groupby(["source", "is_harmful"])},
            "mt_system": "google/gemini-2.5-flash (EN->SL) / openai/gpt-4.1-mini (SL->EN back-translation); NLLB-1.3B/opus-mt round trip kept as secondary nllb_* columns",
            "nllb_chrf_median": round(float(H.nllb_bt_chrf.median()), 2) if "nllb_bt_chrf" in H else None,
            "comet_qe": "skipped (Unbabel/wmt22-cometkiwi-da not accessible: HTTP 404/gated)"}
    (OUT / "hard_mt_report.json").write_text(json.dumps(hrep, indent=1))

    # ---- data_out ----
    ds = []
    ds.append({"dataset": "refuseu_eval", "examples": [ex(
        r.prompt, r.item_label, fold=r.fold, pair_id=r.pair_id, row_id=r.row_id, lang=r.lang, item_id=r.item_id,
        vote_f1_gpt41mini=r.q_hazard, vote_f1_runner_up=r.q_runner_up, vote_f1_confidence=int(r.q_conf) if pd.notna(r.q_conf) else None,
        vote_f2_gemini25flash=r.l_hazard, vote_f2_runner_up=r.l_runner_up, vote_f2_confidence=int(r.l_conf) if pd.notna(r.l_conf) else None,
        vote_tfidf=r.t_hazard, vote_tfidf_runner_up=r.t_runner_up, vote_tfidf_pmax=r.t_pmax,
        vote_llama_guard3=r.lg_top, llama_guard3_verdict=r.lg_verdict, item_pure=r.item_pure,
        item_balanced_label=r.item_balanced_label, item_group=("low_EN" if r.item_label in groups["low_EN"] else "high_EN" if r.item_label in groups["high_EN"] else "intermediate"),
        pair_majority_label=r.pair_majority_label, pair_pure=r.pair_pure, pair_balanced_label=r.pair_balanced_label,
        pair_tfidf_pooled=r.pair_tfidf_pooled, en_sl_item_agree=r.en_sl_item_agree, en_sl_agree_family=r.en_sl_agree_family,
        corr_grade=r.corr_grade, labse_cos=r.labse_cos, nemotron_contaminated=r.contaminated,
        nemotron_ngram_share=r.nem_ngram_share, reserved="no study-model generation in iter 1; confirmation only")
        for r in E.itertuples()]})
    ds.append({"dataset": "refuseu_gold_calib", "examples": [ex(
        r.prompt, r.gold, fold="refuseu_gold_calib", item_id=r.item_id, gold_pair_id=r.gold_pair_id, gold_split=r.gold_split,
        lang=r.lang, row_id=r.row_id, hf_id=r.hf_id, pred_f1_gpt41mini=r.q_hazard, pred_f1_runner_up=r.q_runner_up,
        pred_f2_gemini25flash=r.l_hazard, pred_f2_runner_up=r.l_runner_up, pred_tfidf=r.t_hazard, pred_llama_guard3=r.lg_top,
        llama_guard3_verdict=r.lg_verdict, core_majority=r.core_majority, core_pure=r.core_pure) for r in C.itertuples()]})
    ds.append({"dataset": "gams_dose_rows", "examples": [ex(
        r.user, f"{r.cons_response_type}|{r.h_hazard if isinstance(r.h_hazard, str) else r.cons_hazard}", fold="dose_row", row_key=r.row_key, conversation_id=r.conversation_id,
        language=r.language, sft_category=r.category, identity=bool(r.identity), stratum=r.stratum, weight=r.weight,
        multiplicity=r.multiplicity, keyword_hit=bool(r.keyword_hit), regex_flag=bool(r.flag),
        f1_response_type=r.q_response_type, f1_partial=r.q_partial, f1_hazard=r.q_hazard, f1_response_language=r.q_response_language,
        f2_response_type=r.l_response_type, f2_partial=r.l_partial, f2_hazard=r.l_hazard, f2_response_language=r.l_response_language,
        f3_response_type=r.s_response_type, f3_hazard=r.s_hazard, tiebroken=r.tiebroken,
        consensus_response_type=r.cons_response_type, consensus_hazard=r.cons_hazard,
        consensus_response_language=r.cons_response_language, hazard_eval_taxonomy=r.h_hazard,
        hazard_eval_taxonomy_runner_up=r.h_runner_up, hazard_eval_taxonomy_source=r.h_source, consensus_hazard_literal=r.cons_hazard, consensus_partial=r.cons_partial, tfidf_hazard=r.tfidf_hazard,
        stage0_response=r.s0_response, stage0_refusal_reason=r.s0_refusal_reason, stage0_prompt_harmful=r.s0_prompt_harmful,
        response=str(r.resp)[:2000]) for r in D.itertuples()]})
    hard_ex = []
    for r in H.itertuples():
        base = dict(item_id=r.item_id, source=r.source, source_category=r.source_category,
                    xstest_type=getattr(r, "xstest_type", None), is_harmful=bool(r.is_harmful), mt_fragile=bool(r.mt_fragile),
                    bt_chrf=r.bt_chrf, mt_retry=bool(r.mt_retry), keep=bool(r.keep), vote_f1_en=r.q_en, vote_f1_sl=r.q_sl,
                    vote_f2_en=r.l_en, vote_f2_sl=r.l_sl, vote_tfidf_en=r.t_en, vote_tfidf_sl=r.t_sl,
                    llama_guard3_en=r.lg_en_verdict, llama_guard3_en_cat=r.lg_en_top, llama_guard3_sl=r.lg_sl_verdict,
                    llama_guard3_sl_cat=r.lg_sl_top, pure=bool(r.pure), n_core_votes=r.n_core_votes, n_agree=r.n_agree,
                    gpt_abstain_en=bool(r.gpt_abstain_en), nemotron_contaminated_en=r.contam_en, nemotron_contaminated_sl=r.contam_sl,
                    core_votes="GPT-EN, GPT-SL, TFIDF-EN, TFIDF-SL (GEM-EN skipped: budget scenario 7)", fold=r.fold_final, mt_by=r.mt_by,
                    mt_refused=bool(getattr(r, "mt_refused", False)), nllb_bt_chrf=getattr(r, "nllb_bt_chrf", None),
                    nllb_prompt_sl=getattr(r, "nllb_prompt_sl", None))
        hard_ex.append(ex(r.prompt, r.majority_label, lang="en", **base))
        hard_ex.append(ex(r.prompt_sl, r.majority_label, lang="sl", back_translation=r.prompt_bt, **base))
    for src, name in [("xstest", "hard_xstest"), ("orbench_hard1k", "hard_orbench_hard1k"), ("orbench_toxic", "hard_orbench_toxic300")]:
        ds.append({"dataset": name, "examples": [e for e in hard_ex if e["metadata_source"] == src]})
    fin_p = WORK / "identity_final.parquet"
    if fin_p.exists():
        I = pd.read_parquet(fin_p)
        iex = []
        for r in I.itertuples():
            base = dict(fold=r.fold, item_id=r.item_id, facet=r.facet_final, matched_pair_id=r.matched_pair_id, source=r.source,
                        oasst_message_id=r.oasst_message_id, bt_chrf=r.bt_chrf, length_matched_30pct=bool(r.length_matched_30pct),
                        max_nemotron_8gram_overlap_en=r.nem_en_overlap, max_nemotron_8gram_overlap_sl=r.nem_sl_overlap,
                        max_nemotron_identity_8gram_overlap_sl=r.max_nemotron_identity_8gram_overlap_sl,
                        comparison_order=getattr(r, "comparison_order", None), mt_by=r.mt_by)
            iex.append(ex(r.text, r.kind, lang="en", pair_id=r.item_id, **base))
            iex.append(ex(r.prompt_sl, r.kind, lang="sl", pair_id=r.item_id, back_translation=r.prompt_bt, **base))
        ds.append({"dataset": "identity_confirm", "examples": iex})
    lgp = LABELS / "llamaguard3_votes.parquet"
    lg = pd.read_parquet(lgp).set_index("item_id") if lgp.exists() else None
    tf = pd.read_parquet(LABELS / "tfidf_votes.parquet")
    tfx = {r.key: r.tfidf_top for r in tf[tf.set == "refuseu_x"].itertuples()}
    en_lab = E[E.lang == "en"].set_index("pair_id")
    ds.append({"dataset": "refuseu_x_mt", "examples": [ex(
        r.prompt_sl, en_lab.loc[r.source_pair_id, "item_label"], fold=(r.fold if r.keep else "refuseu_x_dropped_mt"),
        item_id=r.item_id, source_pair_id=r.source_pair_id, lang="sl", source_prompt_en=r.prompt_en, back_translation=r.prompt_bt,
        bt_chrf=r.bt_chrf, keep=bool(r.keep), mt_by=r.mt_by, inherited_label_from="item_label_en of source pair",
        source_item_pure_en=bool(en_lab.loc[r.source_pair_id, "item_pure"]), vote_tfidf_sl=tfx.get(r.item_id),
        llama_guard3_verdict=(lg.loc[r.item_id].lg_verdict if lg is not None and r.item_id in lg.index else None),
        llama_guard3_cat=(lg.loc[r.item_id].lg_top if lg is not None and r.item_id in lg.index else None),
        note="MT companion (non-study model); never replaces the native SL items") for r in rx.itertuples()]})
    meta = {"title": "Reserved confirmation sets + re-audited refusal-supervision dose (GaMS3 vs Gemma-3, run_FVi3e3O9CH5I iter1)",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "folds": sorted({e["metadata_fold"] for d in ds for e in d["examples"]}),
            "labellers": FAM_REPO,
            "workspace": str(ROOT)}
    data = {"metadata": meta, "datasets": ds}
    (ROOT / "full_data_out.json").write_text(json.dumps(data, ensure_ascii=False))
    # mini / preview: first 3 examples of EVERY dataset block (preview: strings truncated to 200 chars)
    def trunc(v):
        if isinstance(v, str):
            return v[:200]
        if isinstance(v, list):
            return [trunc(x) for x in v[:20]]
        if isinstance(v, dict):
            return {k: trunc(x) for k, x in v.items()}
        return v
    mini = {"metadata": meta, "datasets": [{"dataset": d_["dataset"], "examples": d_["examples"][:3]} for d_ in ds]}
    (ROOT / "mini_data_out.json").write_text(json.dumps(mini, ensure_ascii=False, indent=1))
    (ROOT / "preview_data_out.json").write_text(json.dumps(trunc(mini), ensure_ascii=False, indent=1))
    logger.info({d["dataset"]: len(d["examples"]) for d in ds})


if __name__ == "__main__":
    main()
