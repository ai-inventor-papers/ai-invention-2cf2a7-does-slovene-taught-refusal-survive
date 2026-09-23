#!/usr/bin/env python3
"""Step 2 ($0, CPU): build every item table, freeze all hash-based splits BEFORE any labelling.

Outputs (work/): eval_items.parquet, calib_items.parquet, hard_items.parquet, dose_rows.parquet,
nemotron_prompts.parquet; outputs/: split_manifest.json (hash-only folds, written first),
refuseu_overlap_recheck.json, dose_sampling_frame.json."""
import json
import re
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from loguru import logger

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.common import (CATS, DS, OUT, PROMPTS, ROOT, S0, WORK, setup_logging, sha1_hex, sha1_int,  # noqa: E402
                        sha256_file, sha256_text)

setup_logging("s2_prepare")
SEED = 20260923
R = DS / "NASK-PIB__RefusEU"


def user_text(conv) -> str:
    return [t["content"] for t in conv if t["role"] == "user"][0]


def grams(t: str, n: int = 8) -> set:
    w = re.findall(r"\w+", t.lower())
    return {" ".join(w[i:i + n]) for i in range(max(len(w) - n + 1, 1))}


def build_eval() -> pd.DataFrame:
    ev = pd.read_parquet(R / "evaluation/eval-00000-of-00001.parquet")
    e = ev[ev.lang.isin(["en", "sl"])].copy()
    en, sl = set(e[e.lang == "en"].row_id), set(e[e.lang == "sl"].row_id)
    assert e.groupby("lang").row_id.apply(lambda s: s.is_unique).all(), "row_id not unique within language"
    both = en & sl
    orphans = sorted(en ^ sl)
    logger.info(f"eval: EN {len(en)} SL {len(sl)} paired {len(both)} orphans {len(orphans)}")
    e = e[e.row_id.isin(both)].copy()
    e["pair_id"] = e.row_id.map(lambda r: f"refuseu_eval_{r}")
    order = sorted(e.pair_id.unique(), key=sha1_int)
    dev = set(order[:100])
    e["fold"] = np.where(e.pair_id.isin(dev), "refuseu_eval_DEV", "refuseu_eval_FINAL")
    e["item_id"] = e.pair_id + "_" + e.lang
    return e[["item_id", "pair_id", "row_id", "lang", "prompt", "fold"]].reset_index(drop=True), orphans


def build_calib() -> pd.DataFrame:
    rows = []
    for split in ["test", "train"]:
        d = {l: pd.read_parquet(R / f"lang_{l}/{split}-00000-of-00001.parquet") for l in ["en", "sl"]}
        # pair EN<->SL by row POSITION: the numeric id prefix (== row_id) is not unique, but the two parquet files are
        # position-aligned (identical id prefixes, row_ids and category sequences), asserted here
        for l in d:
            d[l] = d[l].reset_index(drop=True)
            d[l]["idx"] = d[l].index
        assert (d["en"].row_id.values == d["sl"].row_id.values).all()
        assert (d["en"].category.values == d["sl"].category.values).all()
        m = d["en"].merge(d["sl"], on="idx", suffixes=("_en", "_sl"))
        if split == "train":  # 11 per category, lowest sha1 -> 154 pairs
            m["h"] = m.idx.map(lambda i: sha1_int(f"gold_train_{i}"))
            m = m.sort_values("h").groupby("category_en").head(11)
        for _, r in m.iterrows():
            for l in ["en", "sl"]:
                rows.append({"item_id": f"refuseu_gold_{split}_{r.idx}_{l}", "gold_pair_id": f"refuseu_gold_{split}_{r.idx}",
                             "gold_split": split, "lang": l, "row_id": int(r[f"row_id_{l}"]), "hf_id": r[f"id_{l}"],
                             "prompt": user_text(r[f"chosen_{l}"]), "gold": r[f"category_{l}"]})
    c = pd.DataFrame(rows)
    logger.info(f"calib items: {c.groupby(['gold_split', 'lang']).size().to_dict()}")
    return c


def overlap_recheck(ev: pd.DataFrame) -> dict:
    res = {}
    for lang in ["en", "sl"]:
        e = ev[ev.lang == lang].prompt.tolist()
        eg = set().union(*[grams(t) for t in e])
        es = {t.strip() for t in e}
        for split in ["train", "test"]:
            d = pd.read_parquet(R / f"lang_{lang}/{split}-00000-of-00001.parquet")
            ps = d.chosen.map(user_text).tolist()
            res[f"{lang}_{split}"] = {"n": len(ps), "exact_in_eval": int(sum(p.strip() in es for p in ps)),
                                      "gt50pct_8gram_overlap_with_eval": int(sum(len(grams(p) & eg) / max(len(grams(p)), 1) > 0.5 for p in ps))}
    res["stage0b_reference"] = "<=3 exact and <=9 near-duplicates per language (iter_3 stage0b/refuseu_overlap.json)"
    return res


def build_hard() -> pd.DataFrame:
    x = pd.read_csv(DS / "Paul__XSTest/xstest_prompts.csv")
    assert (x.label == "safe").sum() == 250 and (x.label == "unsafe").sum() == 200
    fragile_types = {"homonyms", "figurative_language", "safe_targets", "safe_contexts", "definitions"}
    xs = pd.DataFrame({"source": "xstest", "prompt": x.prompt, "source_category": x.type, "xstest_type": x.type,
                       "xstest_focus": x.focus, "xstest_note": x.note, "is_harmful": x.label == "unsafe",
                       "mt_fragile": x.type.map(lambda t: t.replace("contrast_", "") in fragile_types)})
    h = pd.read_csv(DS / "bench-llm__or-bench/or-bench-hard-1k.csv")
    oh = pd.DataFrame({"source": "orbench_hard1k", "prompt": h.prompt, "source_category": h.category, "is_harmful": False,
                       "mt_fragile": False})
    t = pd.read_csv(DS / "bench-llm__or-bench/or-bench-toxic.csv")
    t["h"] = t.prompt.map(lambda p: sha1_int("orbtox_" + p))
    counts = t.category.value_counts()
    alloc = {c: max(10, int(round(300 * n / len(t)))) for c, n in counts.items()}
    while sum(alloc.values()) > 300:  # trim largest allocations down to exactly 300 (floor 10 kept)
        c = max(alloc, key=lambda k: alloc[k]); alloc[c] -= 1
    while sum(alloc.values()) < 300:
        c = max(alloc, key=lambda k: counts[k] - alloc[k]); alloc[c] += 1
    ts = pd.concat([g.sort_values("h").head(alloc[c]) for c, g in t.groupby("category")])
    ot = pd.DataFrame({"source": "orbench_toxic", "prompt": ts.prompt.values, "source_category": ts.category.values,
                       "is_harmful": True, "mt_fragile": False})
    hard = pd.concat([xs, oh, ot], ignore_index=True)
    hard["prompt"] = hard.prompt.astype(str).str.strip()
    n0 = len(hard)
    hard = hard.drop_duplicates("prompt", keep="first").reset_index(drop=True)
    logger.info(f"hard: {n0} -> {len(hard)} after exact dedup; alloc toxic {alloc}")
    hard["item_id"] = hard.source + "_" + hard.prompt.map(lambda p: sha1_hex(p)[:12])
    assert hard.item_id.is_unique
    hard["fold"] = "hard_FINAL"
    for _, g in hard.groupby(["source", "is_harmful"]):
        order = sorted(g.item_id, key=sha1_int)
        k = int(round(0.3 * len(order)))
        hard.loc[hard.item_id.isin(order[:k]), "fold"] = "hard_DEV"
    return hard, alloc


def build_dose() -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    nem = pd.read_parquet(DS / "cjvt__GaMS-Nemotron-Chat/data/train-00000-of-00001.parquet")
    n_raw = len(nem)
    mult = nem.conversation_id.value_counts()  # duplicates are exact copies (same user+assistant text), checked in README
    nem = nem.drop_duplicates("conversation_id", keep="first").reset_index(drop=True)
    nem["multiplicity"] = nem.conversation_id.map(mult).astype(int)
    logger.info(f"nemotron {n_raw} -> {len(nem)} after conversation_id dedup ({n_raw - len(nem)} dups)")
    nem["user"] = nem.prompt.map(lambda c: [t["content"] for t in c if t["role"] == "user"][0] if len(c) else "")
    nem["resp"] = nem.completion.map(lambda c: next((t["content"] for t in c if t["role"] == "assistant"), ""))
    flagged = set(pd.read_json(S0 / "regex_flagged.jsonl", lines=True).conversation_id)
    prior = pd.read_json(S0 / "judge_labels.jsonl", lines=True)
    prior_unflag = set(prior[~prior.flag].conversation_id)
    nem["flag"] = nem.conversation_id.isin(flagged)
    kw = json.loads((PROMPTS / "hazard_keywords_v1.json").read_text())
    pat = "|".join(p.replace("(", "(?:") for k, v in kw.items() if not k.startswith("_") for p in v)
    nem["keyword_hit"] = nem.user.str.lower().str.contains(pat, regex=True)
    parts, frame = [nem[nem.flag].assign(stratum="flagged", weight=1.0)], {}
    for lang in ["en", "sl"]:
        d = nem[(nem.language == lang) & ~nem.flag]
        keep = d[d.conversation_id.isin(prior_unflag)]
        rest = d[~d.conversation_id.isin(prior_unflag)].sample(1000 - len(keep), random_state=SEED)
        srs = pd.concat([keep, rest])
        pool = d[d.keyword_hit & ~d.conversation_id.isin(srs.conversation_id)]
        over = pool.sample(min(400, len(pool)), random_state=SEED)
        N_hit, N_no = int(d.keyword_hit.sum()), int((~d.keyword_hit).sum())
        n_hit = int(srs.keyword_hit.sum()) + len(over)
        n_no = int((~srs.keyword_hit).sum())
        w_hit, w_no = N_hit / n_hit, N_no / n_no
        s = srs.assign(stratum="unflagged_srs")
        s["weight"] = np.where(s.keyword_hit, w_hit, w_no)
        o = over.assign(stratum="unflagged_kw_oversample", weight=w_hit)
        parts += [s, o]
        frame[lang] = {"N_total_dedup": int((nem.language == lang).sum()), "N_flagged": int((nem.flag & (nem.language == lang)).sum()),
                       "N_unflagged": len(d), "N_kw_hit": N_hit, "N_kw_nohit": N_no, "srs_n": len(srs),
                       "srs_from_stage0": len(keep), "srs_kw_hits": int(srs.keyword_hit.sum()), "oversample_n": len(over),
                       "n_kw_hit_total": n_hit, "n_kw_nohit": n_no, "weight_kw_hit": w_hit, "weight_kw_nohit": w_no}
    rows = pd.concat(parts, ignore_index=True)
    rows = rows[["conversation_id", "language", "category", "identity", "user", "resp", "flag", "keyword_hit", "stratum", "weight", "multiplicity"]]
    safe = json.loads((DS / "GaMS-Instruct-SAFE_0.5.json").read_text())
    sdf = pd.DataFrame({"conversation_id": [s["pair_id"] for s in safe], "language": "sl",
                        "category": [s["safety_topic_en"] for s in safe], "identity": False,
                        "user": [s["prompt"] for s in safe], "resp": [s["response"] for s in safe],
                        "flag": True, "keyword_hit": False, "stratum": "gams_safe05", "weight": 1.0, "multiplicity": 1})
    rows = pd.concat([rows, sdf], ignore_index=True)
    rows["row_key"] = rows.stratum.str[:3] + "_" + rows.conversation_id.astype(str)
    assert rows.row_key.is_unique
    frame["n_rows_to_label"] = rows.stratum.value_counts().to_dict()
    frame["keyword_lexicon_sha256"] = sha256_file(PROMPTS / "hazard_keywords_v1.json")
    frame["released_vs_trained_note"] = ("The GaMS3 checkpoint card reports 88,126 training rows; the released dataset has "
                                         f"{n_raw} rows ({len(nem)} after conversation_id dedup). Dose = public mix, not proven exposure.")
    frame["n_raw"], frame["n_dedup"] = n_raw, len(nem)
    frame["duplicate_copies_by_flag_lang"] = {f"{'flagged' if f else 'unflagged'}_{l}": int((g.multiplicity - 1).sum())
                                             for (f, l), g in nem.groupby(["flag", "language"])}
    frame["max_multiplicity"] = int(nem.multiplicity.max())
    nprompts = nem[["conversation_id", "language", "identity", "user"]]
    return rows, frame, nprompts


def main() -> None:
    WORK.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)
    ev, orphans = build_eval()
    hard, alloc = build_hard()
    # ---- FREEZE hash-only splits FIRST (before any label exists) ----
    def lst(s):
        s = sorted(s)
        return {"n": len(s), "sha256": sha256_text("\n".join(s)), "ids": s}
    man = {"frozen_at_utc": datetime.now(timezone.utc).isoformat(), "stage": "hash-only folds, written before any labelling",
           "refuseu_eval": {"rule": "DEV = 100 pair_ids with lowest int(sha1(pair_id)); FINAL = rest",
                            "eval_parquet_sha256": sha256_file(R / "evaluation/eval-00000-of-00001.parquet"),
                            "refuseu_commit": "5523ce30b9b6af59e95ade9c610b8b974412a6bb", "orphan_row_ids": orphans,
                            "DEV": lst(ev[ev.fold == "refuseu_eval_DEV"].pair_id.unique()),
                            "FINAL": lst(ev[ev.fold == "refuseu_eval_FINAL"].pair_id.unique()),
                            "note": "no generation by any study model (GaMS3 / Gemma-3) was run on these items in iter 1"},
           "hard": {"rule": "within source x is_harmful: lowest 30% int(sha1(item_id)) -> hard_DEV, rest hard_FINAL",
                    "DEV": lst(hard[hard.fold == "hard_DEV"].item_id), "FINAL": lst(hard[hard.fold == "hard_FINAL"].item_id),
                    "orbench_toxic_alloc": alloc}}
    (OUT / "split_manifest.json").write_text(json.dumps(man, indent=1))
    logger.info("split_manifest.json frozen (hash-only folds)")
    calib = build_calib()
    (OUT / "refuseu_overlap_recheck.json").write_text(json.dumps(overlap_recheck(ev), indent=1))
    dose, frame, nprompts = build_dose()
    (OUT / "dose_sampling_frame.json").write_text(json.dumps(frame, indent=1))
    ev.to_parquet(WORK / "eval_items.parquet"); calib.to_parquet(WORK / "calib_items.parquet")
    hard.to_parquet(WORK / "hard_items.parquet"); dose.to_parquet(WORK / "dose_rows.parquet")
    nprompts.to_parquet(WORK / "nemotron_prompts.parquet")
    logger.info(f"eval {len(ev)} calib {len(calib)} hard {len(hard)} dose {len(dose)} | frame {json.dumps(frame)[:600]}")


if __name__ == "__main__":
    main()
