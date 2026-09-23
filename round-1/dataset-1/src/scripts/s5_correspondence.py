#!/usr/bin/env python3
"""Step 5 ($0, GPU): ROW_ID CORRESPONDENCE CHECK. Are RefusEU EN/SL items that share a row_id translations, same-topic
variants, or unrelated? (i) gold same-category share for EN/SL pairs in lang_*/train+test (by position and by row_id join);
(ii) LaBSE cosine for eval pairs, gold pairs, a shuffled-pair baseline and an MT-pair reference (NLLB EN->SL of 50 gold EN
prompts; the 1,400 RefusEU-X MT pairs are a robustness reference); (iii) grade T/S/U per eval pair."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.common import DS, OUT, WORK, setup_logging  # noqa: E402

setup_logging("s5_correspondence")
R = DS / "NASK-PIB__RefusEU"


def user_text(conv) -> str:
    return [t["content"] for t in conv if t["role"] == "user"][0]


def pct(a) -> dict:
    a = np.asarray(a)
    return {"n": int(len(a)), "mean": round(float(a.mean()), 4), "p05": round(float(np.percentile(a, 5)), 4),
            "p50": round(float(np.percentile(a, 50)), 4), "p95": round(float(np.percentile(a, 95)), 4)}


@logger.catch(reraise=True)
def main() -> None:
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer("sentence-transformers/LaBSE", device="cuda")
    enc = lambda xs: m.encode(list(xs), batch_size=128, normalize_embeddings=True, show_progress_bar=False)  # noqa: E731
    rng = np.random.default_rng(20260923)
    res = {"model": "sentence-transformers/LaBSE"}
    # ---- (i) gold same-category share ----
    gold = {}
    for split in ["train", "test"]:
        e = pd.read_parquet(R / f"lang_en/{split}-00000-of-00001.parquet").reset_index(drop=True)
        s = pd.read_parquet(R / f"lang_sl/{split}-00000-of-00001.parquet").reset_index(drop=True)
        j = e.merge(s, on="row_id", suffixes=("_en", "_sl"))
        gold[split] = (e, s)
        res[f"gold_{split}_same_category"] = {
            "by_position_pairs": float((e.category.values == s.category.values).mean()), "n_position_pairs": len(e),
            "by_row_id_join_all_combinations": round(float((j.category_en == j.category_sl).mean()), 4),
            "n_row_id_join": len(j), "row_id_unique_within_lang": bool(e.row_id.is_unique),
            "note": "row_id is NOT unique within a language in the gold splits; position pairs share id prefix and row_id"}
    # ---- (ii) cosines ----
    ev = pd.read_parquet(WORK / "eval_items.parquet")
    en = ev[ev.lang == "en"].sort_values("row_id"); sl = ev[ev.lang == "sl"].sort_values("row_id")
    assert (en.row_id.values == sl.row_id.values).all()
    Ee, Es = enc(en.prompt), enc(sl.prompt)
    cos_eval = (Ee * Es).sum(1)
    perm = rng.permutation(len(Es))
    shuf_eval = (Ee * Es[perm]).sum(1)
    ge, gs = pd.concat([gold["train"][0], gold["test"][0]]), pd.concat([gold["train"][1], gold["test"][1]])
    Ge, Gs = enc(ge.chosen.map(user_text)), enc(gs.chosen.map(user_text))
    cos_gold = (Ge * Gs).sum(1)
    gperm = rng.permutation(len(Gs))
    shuf_gold = (Ge * Gs[gperm]).sum(1)
    same_cat = ge.category.values == gs.category.values[gperm]
    ref = pd.read_parquet(WORK / "gold_mt_ref.parquet")
    cos_mt = (enc(ref.prompt_en) * enc(ref.prompt_sl)).sum(1)
    rx = pd.read_parquet(WORK / "refuseu_x_mt.parquet")
    cos_rx = (enc(rx.prompt_en) * enc(rx.prompt_sl)).sum(1)
    t_thr, s_thr = float(np.percentile(cos_mt, 5)), float(np.percentile(shuf_eval, 95))
    grade = np.where(cos_eval >= t_thr, "T", np.where(cos_eval > s_thr, "S", "U"))
    res["cosine"] = {"eval_same_row_id": pct(cos_eval), "eval_shuffled": pct(shuf_eval), "gold_position_pairs": pct(cos_gold),
                     "gold_shuffled": pct(shuf_gold), "gold_shuffled_same_category_only": pct(shuf_gold[same_cat]),
                     "gold_shuffled_diff_category_only": pct(shuf_gold[~same_cat]),
                     "mt_reference_50_gold": pct(cos_mt), "mt_reference_refuseu_x_1400": pct(cos_rx)}
    res["thresholds"] = {"T_if_cos_ge (p05 of MT reference)": round(t_thr, 4), "S_if_cos_gt (p95 of shuffled eval)": round(s_thr, 4)}
    res["eval_grade_counts"] = {g: int((grade == g).sum()) for g in "TSU"}
    res["eval_grade_T_share"] = round(float((grade == "T").mean()), 4)
    same_cat_ok = res["gold_train_same_category"]["by_position_pairs"] >= 0.95
    res["verdict"] = {
        "pair_level_labels_valid": bool(same_cat_ok),
        "items_are_translations": bool(res["eval_grade_T_share"] >= 0.5),
        "text": ("Gold EN/SL position pairs share the gold category by construction (100%), so a pair-level category is "
                 "defined; but with T-share = {:.1%} the same-row_id EN/SL eval items are {} . Category labels are therefore "
                 "PRIMARY per language item; within-model SL-EN contrasts are item-matched only on grade-T pairs or RefusEU-X. "
                 "The cross-model DiD needs no translation matching (both models see the identical EN and SL sets)."
                 ).format(res["eval_grade_T_share"], "mostly translation-like" if res["eval_grade_T_share"] >= 0.5 else
                          "mostly NOT translations (per-language generated variants), correcting the hypothesis wording 'EN and SL are DeepL translations'")}
    (OUT / "refuseu_correspondence.json").write_text(json.dumps(res, indent=1))
    pd.DataFrame({"pair_id": en.pair_id.values, "labse_cos": np.round(cos_eval, 4), "corr_grade": grade}).to_parquet(WORK / "eval_corr.parquet")
    logger.info(json.dumps({k: res[k] for k in ["thresholds", "eval_grade_counts", "verdict"]}, indent=1))
    logger.info(json.dumps(res["cosine"], indent=0))


if __name__ == "__main__":
    main()
