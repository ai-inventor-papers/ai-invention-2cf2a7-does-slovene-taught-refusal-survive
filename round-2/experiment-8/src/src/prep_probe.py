#!/usr/bin/env python3
"""STEP 1 DATA: item-matched RefusEU-TRAIN probe (EN-orig / NLLB SL-MT / NLLB EN-BT), DEV20, harmless100, A2 construct sets.

The RefusEU 'evaluation' config is NEVER loaded (reserved for the FINAL confirmation artifacts). The candidate pool is iter-1
exp4's SCORE split of the RefusEU lang_en train+test rows (NASK-PIB/RefusEU @5523ce30b9, pairing and pair_id convention of
iter-1), minus iter-1's trial_probe and construct items, minus any exact/normalised match to mlabonne/harmful_behaviors
(Heretic's objective set), minus 8-gram-shingle collisions with nothing reserved (the eval split is not loaded here).
"""
from __future__ import annotations

import gc
import json
import re
import time
from collections import Counter, defaultdict

import torch
from datasets import load_dataset

from common import (DATA, ITER1_DATASET, ITER1_EXP4, SEED, dose_group, langid_sl, norm_text, read_jsonl, setup_logger,
                    sha1_hex, sha256_file, write_jsonl)

logger = setup_logger("prep_probe")
NLLB = "facebook/nllb-200-distilled-1.3B"
N_P200, N_P100, N_DEV = 200, 100, 20


def clean(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        s = s[1:-1].strip()
    return s


def mt(model, tok, texts: list[str], src: str, tgt: str, bs: int = 24) -> list[str]:
    tok.src_lang = src
    out = [None] * len(texts)
    order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
    tgt_id = tok.convert_tokens_to_ids(tgt)
    for s in range(0, len(order), bs):
        idx = order[s:s + bs]
        enc = tok([texts[i] for i in idx], return_tensors="pt", padding=True, truncation=True, max_length=512).to("cuda")
        with torch.inference_mode():
            gen = model.generate(**enc, forced_bos_token_id=tgt_id, num_beams=4, max_length=512)
        dec = tok.batch_decode(gen, skip_special_tokens=True)
        for i, d in zip(idx, dec):
            out[i] = d.strip()
    return out


@logger.catch(reraise=True)
def main():
    t0 = time.time()
    score = read_jsonl(ITER1_EXP4 / "data" / "splits" / "score.jsonl")
    tp = read_jsonl(ITER1_EXP4 / "data" / "splits" / "trial_probe.jsonl")
    construct = read_jsonl(ITER1_EXP4 / "data" / "splits" / "construct.jsonl")
    excl_ids = {p["pair_id"] for p in tp} | {p["pair_id"] for p in construct}
    excl_txt = {sha1_hex(norm_text(clean(p["en"]))) for p in tp + construct}
    mh = load_dataset("mlabonne/harmful_behaviors", split="train")
    mh_txt = {sha1_hex(norm_text(clean(t))) for t in mh["text"]}
    try:
        mh_test = load_dataset("mlabonne/harmful_behaviors", split="test")
        mh_txt |= {sha1_hex(norm_text(clean(t))) for t in mh_test["text"]}
    except (ValueError, KeyError) as e:
        logger.warning(f"mlabonne test split unavailable: {e}")
    logger.info(f"score pool {len(score)}; exclusion ids {len(excl_ids)}; mlabonne texts {len(mh_txt)}")
    pool, n_ex = [], Counter()
    seen_txt = set()
    for p in score:
        h = sha1_hex(norm_text(clean(p["en"])))
        if p["pair_id"] in excl_ids:
            n_ex["iter1_trial_probe_or_construct_id"] += 1
            continue
        if h in excl_txt:
            n_ex["iter1_text_dup"] += 1
            continue
        if h in mh_txt:
            n_ex["mlabonne_match"] += 1
            continue
        if h in seen_txt:
            n_ex["duplicate_text_in_pool"] += 1
            continue
        seen_txt.add(h)
        pool.append({"item_id": p["pair_id"], "gold_cat": p["category"], "dose_group": dose_group(p["category"]),
                     "en_orig": clean(p["en"]), "rank": sha1_hex(p["pair_id"] + str(SEED))})
    logger.info(f"pool after exclusions: {len(pool)}; excluded {dict(n_ex)}")
    bycat = defaultdict(list)
    for p in pool:
        bycat[p["gold_cat"]].append(p)
    for c in bycat:
        bycat[c].sort(key=lambda p: p["rank"])
    cats = sorted(bycat, key=lambda c: int(c[1:]))
    # round-robin by category in hash order -> a ranked list; candidates beyond 220 are MT spares for replacement
    ranked, depth = [], 0
    while len(ranked) < len(pool):
        prog = False
        for c in cats:
            if depth < len(bycat[c]):
                ranked.append(bycat[c][depth])
                prog = True
        depth += 1
        if not prog:
            break
    cand = ranked[:300]  # translate 300 so that replacements are available without a second MT pass

    # ---------------- harmless (tatsu-lab/alpaca, instruction-only, NOT Heretic's harmless_alpaca) ----------------
    alp = load_dataset("tatsu-lab/alpaca", split="train")
    alp = [r["instruction"].strip() for r in alp if not r["input"].strip() and 15 <= len(r["instruction"]) <= 300]
    alp = sorted(set(alp), key=lambda s: sha1_hex(s + str(SEED)))
    harmless100 = [{"item_id": f"alpaca:{sha1_hex(s)[:10]}", "en_orig": s} for s in alp[:100]]
    harmless_dir = [{"item_id": f"alpaca:{sha1_hex(s)[:10]}", "en": s} for s in alp[100:500]]  # A2 direction
    harmless_dev = [{"item_id": f"alpaca:{sha1_hex(s)[:10]}", "en": s} for s in alp[500:532]]  # DEV KL items

    # ---------------- NLLB MT ----------------
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(NLLB)
    model = AutoModelForSeq2SeqLM.from_pretrained(NLLB, dtype=torch.float16).to("cuda").eval()
    from huggingface_hub import HfApi
    try:
        nllb_sha = HfApi().model_info(NLLB).sha
    except Exception as e:  # noqa: BLE001
        nllb_sha = f"unavailable: {e}"[:120]
    t = time.time()
    src = [c["en_orig"] for c in cand] + [h["en_orig"] for h in harmless100]
    sl = mt(model, tok, src, "eng_Latn", "slv_Latn")
    bt = mt(model, tok, sl, "slv_Latn", "eng_Latn")
    logger.info(f"NLLB MT of {len(src)} items fwd+back in {time.time() - t:.0f}s")
    del model
    gc.collect()
    torch.cuda.empty_cache()
    import sacrebleu
    for i, c in enumerate(cand):
        c["sl_mt"], c["en_bt"] = sl[i], bt[i]
    for j, h in enumerate(harmless100):
        h["sl_mt"], h["en_bt"] = sl[len(cand) + j], bt[len(cand) + j]
    for c in cand + harmless100:
        c["chrf"] = round(sacrebleu.sentence_chrf(c["en_bt"], [c["en_orig"]]).score, 2)
        c["mt_fragile"] = int(c["chrf"] < 40)
        lab, ok = langid_sl(c["sl_mt"])
        c["sl_langid"], c["sl_lang_ok"] = lab, ok
        c["len_ratio"] = round(len(c["sl_mt"]) / max(1, len(c["en_orig"])), 3)
        c["mt_valid"] = int(ok == 1 and c["len_ratio"] >= 0.5)

    # ---------------- select P200 (category-balanced round robin over MT-valid candidates) + DEV20 ----------------
    valid = [c for c in cand if c["mt_valid"]]
    dropped = [c["item_id"] for c in cand if not c["mt_valid"]]
    logger.info(f"MT-valid {len(valid)}/{len(cand)}; dropped {len(dropped)}")
    vb = defaultdict(list)
    for c in valid:
        vb[c["gold_cat"]].append(c)
    p200, depth = [], 0
    while len(p200) < N_P200:
        prog = False
        for c in cats:
            if len(p200) < N_P200 and depth < len(vb[c]):
                p200.append(vb[c][depth])
                prog = True
        depth += 1
        if not prog:
            break
    chosen = {c["item_id"] for c in p200}
    rest = [c for c in valid if c["item_id"] not in chosen]
    dev20 = rest[:N_DEV]
    # P100: first 100 of P200 by the same hash, stratified (round robin by category over P200 in rank order)
    pb = defaultdict(list)
    for c in p200:
        pb[c["gold_cat"]].append(c)
    p100ids, depth = [], 0
    while len(p100ids) < N_P100:
        for c in cats:
            if len(p100ids) < N_P100 and depth < len(pb[c]):
                p100ids.append(pb[c][depth]["item_id"])
        depth += 1
    p100set = set(p100ids)
    keep = ["item_id", "gold_cat", "dose_group", "en_orig", "sl_mt", "en_bt", "chrf", "mt_fragile", "sl_langid", "len_ratio"]
    rows = [{**{k: c[k] for k in keep}, "in_P100": int(c["item_id"] in p100set)} for c in p200]
    write_jsonl(DATA / "probe_P200.jsonl", rows)
    write_jsonl(DATA / "dev20.jsonl", [{**{k: c[k] for k in keep}, "in_P100": 0} for c in dev20])
    write_jsonl(DATA / "harmless100.jsonl", [{k: h[k] for k in ("item_id", "en_orig", "sl_mt", "en_bt", "chrf", "mt_fragile")}
                                             for h in harmless100])
    write_jsonl(DATA / "harmless_dir400.jsonl", harmless_dir)
    write_jsonl(DATA / "harmless_dev32.jsonl", harmless_dev)
    cons_en = [{"item_id": p["pair_id"], "gold_cat": p["category"], "en": clean(p["en"])} for p in construct][:400]
    write_jsonl(DATA / "construct_A2.jsonl", cons_en)
    for name in ("sel_kl", "eval_kl"):
        (DATA / f"{name}.jsonl").write_text((ITER1_EXP4 / "data" / "splits" / f"{name}.jsonl").read_text())

    # ---------------- checks + manifest ----------------
    ids = {r["item_id"] for r in rows} | {c["item_id"] for c in dev20}
    assert not (ids & excl_ids), "overlap with iter-1 trial_probe/construct"
    assert not ({sha1_hex(norm_text(r["en_orig"])) for r in rows} & mh_txt), "overlap with mlabonne"
    chrfs = sorted(r["chrf"] for r in rows)
    med = chrfs[len(chrfs) // 2]
    cat_counts = Counter(r["gold_cat"] for r in rows)
    low_n = sum(r["dose_group"] == "low" for r in rows)
    logger.info(f"P200 categories {dict(sorted(cat_counts.items()))}; low-EN items {low_n}; median chrF {med}; "
                f"mt_fragile {sum(r['mt_fragile'] for r in rows)}; P100 {sum(r['in_P100'] for r in rows)}")
    for r in rows[:5]:
        logger.info(f"  EN: {r['en_orig'][:110]!r}\n  SL: {r['sl_mt'][:110]!r}\n  BT: {r['en_bt'][:110]!r}  chrF={r['chrf']}")
    files = ["probe_P200.jsonl", "dev20.jsonl", "harmless100.jsonl", "harmless_dir400.jsonl", "harmless_dev32.jsonl",
             "construct_A2.jsonl", "sel_kl.jsonl", "eval_kl.jsonl"]
    manifest = {"files": {f: sha256_file(DATA / f) for f in files},
                "counts": {"P200": len(rows), "P100": sum(r["in_P100"] for r in rows), "DEV20": len(dev20),
                           "harmless100": len(harmless100), "harmless_dir": len(harmless_dir), "construct_A2": len(cons_en)},
                "P200_categories": dict(sorted(cat_counts.items())), "P200_low_EN_items": low_n,
                "P100_categories": dict(sorted(Counter(r["gold_cat"] for r in rows if r["in_P100"]).items())),
                "chrf_median_P200": med, "chrf_quartiles": [chrfs[len(chrfs) // 4], med, chrfs[3 * len(chrfs) // 4]],
                "mt_fragile_P200": sum(r["mt_fragile"] for r in rows),
                "sl_langid_sl_rate": sum(r["sl_langid"] == "sl" for r in rows) / len(rows),
                "dropped_invalid_mt": dropped, "exclusions": dict(n_ex), "pool_after_exclusions": len(pool),
                "overlap_checks": {"iter1_trial_probe_construct": 0, "mlabonne_harmful_behaviors": 0}}
    (DATA / "split_manifest.json").write_text(json.dumps(manifest, indent=2))
    prov = {"refuseu": {"repo": "NASK-PIB/RefusEU", "revision": "5523ce30b9", "configs": ["lang_en (train+test) via iter-1 exp4 "
            "data/splits/score.jsonl"], "evaluation_split_loaded": False},
            "iter1_sources": {"score": str(ITER1_EXP4 / "data/splits/score.jsonl"),
                              "trial_probe_excluded": str(ITER1_EXP4 / "data/splits/trial_probe.jsonl"),
                              "construct": str(ITER1_EXP4 / "data/splits/construct.jsonl"),
                              "frozen_groups": str(ITER1_DATASET / "outputs/frozen_groups.json")},
            "mt": {"model": NLLB, "sha": nllb_sha, "dtype": "float16", "num_beams": 4, "max_length": 512,
                   "fwd": "eng_Latn->slv_Latn", "back": "slv_Latn->eng_Latn"},
            "harmless": {"source": "tatsu-lab/alpaca train, instruction-only (empty input), 15-300 chars, sha1(text+seed) order",
                         "harmless100": "ranks 0-99", "harmless_dir400": "ranks 100-499 (A2 direction)",
                         "harmless_dev32": "ranks 500-531 (A2 DEV KL)"},
            "text_cleaning": "wrapping double quotes of RefusEU prompts stripped for all arms",
            "seed": SEED, "seconds": round(time.time() - t0, 1)}
    (DATA / "provenance.json").write_text(json.dumps(prov, indent=2))
    logger.info(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
