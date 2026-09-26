#!/usr/bin/env python3
"""S0/S1: input check + data build (Dolly harmless sets, NLLB SL-MT / EN-BT for every arm, P200 DEV40/TEST160,
HARD-DEV benign 130 -> hard_dev 30 / hard_test 100, overlap checks, sha256 manifest).

Reads (read-only): exp8 data/probe_P200.jsonl + data/construct_A2.jsonl; iter-1 dataset hard_xstest / hard_orbench_hard1k
(hard_DEV, is_harmful = 0 only; extracted to data/_hard_dev_pool.jsonl) and refuseu_eval TEXT (overlap check only).
Never opened: hard_FINAL, refuseu_eval generations, identity_confirm (reserved for dir4).

Usage: .venv/bin/python src/prep_data.py
"""
from __future__ import annotations

import gc
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (DATA, EXP8, ITER1_DATASET, ITER1_EXP4, LOGS, NLLB, SEED, EVAL1, langid_label, read_jsonl,  # noqa: E402
                    setup_logger, sha1_hex, sha256_file, write_jsonl)

logger = setup_logger("prep_data")

HARM_KW = ["kill", "murder", "bomb", "weapon", "gun", "drug", "suicide", "hack", "steal", "poison", "attack", "terror",
           "explosive", "abuse", "rape", "porn", "sex", "nude", "violence", "violent", "illegal", "crime", "criminal",
           "fraud", "scam", "cocaine", "heroin", "meth", "firearm", "knife", "hate", "racist", "nazi", "torture", "shoot",
           "assault", "blood", "dead", "death", "die ", "war", "kidnap", "extort", "launder", "counterfeit", "self-harm",
           "cutting", "overdose", "smuggl", "piracy", "malware", "virus", "exploit", "password", "slave", "genocide"]
DOLLY_CATS = {"open_qa", "general_qa", "brainstorming", "creative_writing", "classification"}


def check_inputs() -> dict:
    req = {
        "P200": (EXP8 / "data/probe_P200.jsonl", "e152fe5430810a82ba3686a736fe8e89ad4c7a530f0d849d52dc5e36a77b0d63"),
        "construct_A2": (EXP8 / "data/construct_A2.jsonl", "93c993566a4f496f79c84bbbf4ccc8961f0b45990d81c05d6a2a2e30bd672449"),
        "exp8_split_manifest": (EXP8 / "data/split_manifest.json", None),
        "exp8_provenance": (EXP8 / "data/provenance.json", None),
        "exp8_gpu_block": (EXP8 / "src/gpu_block.py", None),
        "exp8_probe": (EXP8 / "src/probe.py", None),
        "exp8_common": (EXP8 / "src/common.py", None),
        "exp8_judge": (EXP8 / "src/judge.py", None),
        "exp8_analysis": (EXP8 / "src/analysis.py", None),
        "exp8_protocol_amendments": (EXP8 / "results/protocol_amendments.json", None),
        "exp8_judge_labels": (EXP8 / "results/judge_labels.jsonl", None),
        "dataset_full": (ITER1_DATASET / "full_data_out.json", None),
        "adapter_gemma": (ITER1_EXP4 / "results/gemma_it/selected_adapter/adapter_model.safetensors", None),
        "adapter_gams": (ITER1_EXP4 / "results/gams3_it/selected_adapter/adapter_model.safetensors", None),
        "selection_pick_gemma": (ITER1_EXP4 / "results/gemma_it/selection_pick.json", None),
        "selection_pick_gams": (ITER1_EXP4 / "results/gams3_it/selection_pick.json", None),
        "m_json": (ITER1_EXP4 / "results/m.json", None),
        "harmonised_P1": (EVAL1 / "labels/harmonised_P1.jsonl.gz", None),
    }
    out = {}
    for k, (p, sha) in req.items():
        ex = p.exists()
        got = sha256_file(p) if ex and p.stat().st_size < 400e6 else None
        out[k] = {"path": str(p), "exists": ex, "sha256": got, "expected": sha,
                  "match": (got == sha) if (sha and got) else None}
        logger.info(f"input {k}: exists={ex} match={out[k]['match']}")
    # optional dir2 selection pick-up (iter-3 sibling artifacts)
    dir2 = []
    for d in sorted((ITER1_EXP4.parents[2] / "round-3").glob("*")):
        for sp in d.glob("**/selection_pick.json"):
            if (sp.parent / "selected_adapter").exists():
                dir2.append(str(sp))
    out["dir2_selection_candidates"] = dir2
    (LOGS / "inputs_check.json").write_text(json.dumps(out, indent=2))
    return out


def nllb_translate(texts: list[str], src: str, tgt: str, model, tok, bs: int = 24) -> list[str]:
    import torch
    order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
    out = [None] * len(texts)
    tok.src_lang = src
    bos = tok.convert_tokens_to_ids(tgt)
    for s in range(0, len(order), bs):
        idx = order[s:s + bs]
        enc = tok([texts[i] for i in idx], return_tensors="pt", padding=True, truncation=True,
                  max_length=NLLB["max_length"]).to(model.device)
        with torch.inference_mode():
            gen = model.generate(**enc, forced_bos_token_id=bos, num_beams=NLLB["num_beams"], max_length=NLLB["max_length"])
        dec = tok.batch_decode(gen, skip_special_tokens=True)
        for i, t in zip(idx, dec):
            out[i] = t
    return out


def ngrams(text: str, n: int = 8) -> set:
    w = re.findall(r"\w+", text.lower())
    return {tuple(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}


def overlap_report(sets: dict[str, list[str]], external: dict[str, list[str]]) -> dict:
    """exact duplicates and >50% 8-gram overlap between every pair of (set, set) and (set, external)."""
    index = defaultdict(set)
    names = []
    all_items = []
    for sn, texts in list(sets.items()) + list(external.items()):
        for i, t in enumerate(texts):
            gid = len(all_items)
            all_items.append((sn, i, t.strip().lower()))
            for g in ngrams(t):
                index[g].add(gid)
        names.append(sn)
    exact = defaultdict(list)
    for gid, (sn, i, t) in enumerate(all_items):
        exact[t].append(sn)
    rep = {"exact_dups_between_sets": Counter(), "ngram50_between_sets": Counter()}
    for t, sns in exact.items():
        if len(set(sns)) > 1:
            rep["exact_dups_between_sets"]["|".join(sorted(set(sns)))] += 1
    for gid, (sn, i, t) in enumerate(all_items):
        if sn in external:
            continue
        ng = ngrams(t)
        if not ng:
            continue
        cnt = Counter()
        for g in ng:
            for o in index[g]:
                if o != gid and all_items[o][0] != sn:
                    cnt[o] += 1
        for o, c in cnt.items():
            if c / len(ng) > 0.5:
                rep["ngram50_between_sets"][f"{sn}->{all_items[o][0]}"] += 1
    return {k: dict(v) for k, v in rep.items()}


@logger.catch(reraise=True)
def main():
    t0 = time.time()
    inp = check_inputs()
    assert inp["P200"]["match"] and inp["construct_A2"]["match"], "P200/construct sha mismatch"

    # ---------------- Dolly ----------------
    from datasets import load_dataset
    from huggingface_hub import HfApi
    dolly_sha = HfApi().dataset_info("databricks/databricks-dolly-15k").sha
    alp_sha = HfApi().dataset_info("tatsu-lab/alpaca").sha
    dolly = load_dataset("databricks/databricks-dolly-15k", split="train", revision=dolly_sha)
    alpaca = load_dataset("tatsu-lab/alpaca", split="train", revision=alp_sha)
    alp_set = {a.strip().lower() for a in alpaca["instruction"]}
    pool, seen, drops = [], set(), Counter()
    for i, r in enumerate(dolly):
        ins = (r["instruction"] or "").strip()
        if r["category"] not in DOLLY_CATS:
            drops["category"] += 1
            continue
        if (r["context"] or "").strip():
            drops["context"] += 1
            continue
        if not (15 <= len(ins) <= 300):
            drops["length"] += 1
            continue
        low = f" {ins.lower()} "
        if any(k in low for k in HARM_KW):
            drops["harm_kw"] += 1
            continue
        if ins.lower() in alp_set:
            drops["alpaca_exact"] += 1
            continue
        if ins.lower() in seen:
            drops["dup"] += 1
            continue
        seen.add(ins.lower())
        pool.append({"item_id": f"dolly:{i}", "category": r["category"], "en_orig": ins})
    pool.sort(key=lambda x: sha1_hex(x["en_orig"] + str(SEED)))
    logger.info(f"dolly pool {len(pool)} drops {dict(drops)}")
    ranges = {"harmless_construct": (0, 400), "rq4_harmless": (400, 600), "induce_test": (600, 648),
              "induce_dev": (648, 672), "addon_harmless": (672, 704), "kl_dev": (704, 736)}
    dsets = {k: [dict(x) for x in pool[a:b]] for k, (a, b) in ranges.items()}

    # ---------------- harmful construct (exp8 construct_A2) ----------------
    cons = [{"item_id": r["item_id"], "gold_cat": r["gold_cat"], "en_orig": r["en"].strip().strip('"').strip()}
            for r in read_jsonl(EXP8 / "data/construct_A2.jsonl")]
    # ---------------- P200 DEV40 / TEST160 (already translated by exp8 with the same NLLB config) ----------------
    p200 = read_jsonl(EXP8 / "data/probe_P200.jsonl")
    bycat = defaultdict(list)
    for r in p200:
        bycat[r["gold_cat"]].append(r)
    dev_ids = []
    cats = sorted(bycat)
    ranked = {c: sorted(bycat[c], key=lambda r: sha1_hex(r["item_id"] + "dev" + str(SEED))) for c in cats}
    k = 0
    while len(dev_ids) < 40:  # round-robin over categories, lowest sha1 first -> stratified by gold_cat
        c = cats[k % len(cats)]
        j = k // len(cats)
        if j < len(ranked[c]):
            dev_ids.append(ranked[c][j]["item_id"])
        k += 1
    dev40 = [r for r in p200 if r["item_id"] in set(dev_ids)]
    test160 = [r for r in p200 if r["item_id"] not in set(dev_ids)]
    assert len(dev40) == 40 and len(test160) == 160

    # ---------------- HARD-DEV benign ----------------
    hp = read_jsonl(DATA / "_hard_dev_pool.jsonl")
    hp = [h for h in hp if h["fold"] == "hard_DEV"]
    bys = defaultdict(list)
    for h in hp:
        bys[h["source"]].append(h)
    for s in bys:
        bys[s].sort(key=lambda h: sha1_hex(h["item_id"] + str(SEED)))
    hx, ho = bys["xstest"], bys["orbench_hard1k"]
    nx = min(65, len(hx))  # 50/50 by source (all XSTest-safe DEV if fewer; orbench fills the rest)
    hard_dev = hx[:15] + ho[:15]
    hard_test = hx[15:nx] + ho[15:15 + 100 - (nx - 15)]
    logger.info(f"hard pool xstest {len(hx)} orbench {len(ho)} -> hard_dev {len(hard_dev)} hard_test {len(hard_test)} "
                f"({Counter(h['source'] for h in hard_test)})")

    # ---------------- NLLB ----------------
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    torch.cuda.set_per_process_memory_fraction(0.5)
    ntok = AutoTokenizer.from_pretrained(NLLB["repo"], revision=NLLB["revision"])
    nmod = AutoModelForSeq2SeqLM.from_pretrained(NLLB["repo"], revision=NLLB["revision"], dtype=torch.float16).cuda().eval()
    to_tr = {"construct_harm": cons, "hard_dev": hard_dev, "hard_test": hard_test, **dsets}
    flat = [(sn, i) for sn, lst in to_tr.items() for i in range(len(lst))]
    texts = [to_tr[sn][i]["en_orig"] for sn, i in flat]
    tt = time.time()
    sl = nllb_translate(texts, "eng_Latn", "slv_Latn", nmod, ntok)
    bt = nllb_translate(sl, "slv_Latn", "eng_Latn", nmod, ntok)
    logger.info(f"NLLB {len(texts)} x 2 in {time.time() - tt:.0f}s")
    del nmod
    gc.collect()
    torch.cuda.empty_cache()
    import sacrebleu
    for (sn, i), s, b in zip(flat, sl, bt):
        r = to_tr[sn][i]
        r["sl_mt"], r["en_bt"] = s, b
        r["chrf"] = round(sacrebleu.sentence_chrf(b, [r["en_orig"]]).score, 2)
        r["mt_fragile"] = int(r["chrf"] < 40)
        r["sl_langid"] = langid_label(s)
    gates = {}
    for sn, lst in list(to_tr.items()) + [("P200", p200)]:
        ch = sorted(r["chrf"] for r in lst)
        med = ch[len(ch) // 2]
        sl_rate = sum(r["sl_langid"] == "sl" for r in lst) / len(lst)
        gates[sn] = {"n": len(lst), "chrf_median": med, "chrf_gate_ge60": med >= 60,
                     "mt_fragile": sum(r["mt_fragile"] for r in lst), "sl_langid_rate": round(sl_rate, 3),
                     "sl_langid_gate_ge95": sl_rate >= 0.95}
        logger.info(f"gate {sn}: {gates[sn]}")

    # ---------------- write ----------------
    files = {"construct_harm.jsonl": cons, "hard_dev.jsonl": hard_dev, "hard_test.jsonl": hard_test,
             "p200_dev40.jsonl": dev40, "p200_test160.jsonl": test160}
    for k2, v in dsets.items():
        files[f"{k2}.jsonl"] = v
    for fn, rows in files.items():
        write_jsonl(DATA / fn, rows)
    # ---------------- overlap checks ----------------
    ev = json.loads((DATA / "_refuseu_eval_text_for_overlap_only.json").read_text())
    sets_txt = {fn.replace(".jsonl", ""): [r["en_orig"] for r in rows] for fn, rows in files.items()}
    sets_txt_sl = {fn.replace(".jsonl", "") + "_sl": [r["sl_mt"] for r in rows] for fn, rows in files.items()}
    ov = overlap_report({**sets_txt, **sets_txt_sl}, {"refuseu_eval_text": ev})
    manifest = {"seed": SEED, "files": {fn: sha256_file(DATA / fn) for fn in files},
                "counts": {fn: len(r) for fn, r in files.items()}, "gates": gates, "overlap": ov,
                "dolly": {"repo": "databricks/databricks-dolly-15k", "revision": dolly_sha, "pool_after_filters": len(pool),
                          "drops": dict(drops), "categories": sorted(DOLLY_CATS), "ranges": ranges},
                "alpaca_exact_filter": {"repo": "tatsu-lab/alpaca", "revision": alp_sha},
                "p200_dev40_ids": sorted(dev_ids), "p200_dev40_cats": dict(Counter(r["gold_cat"] for r in dev40)),
                "hard": {"pool": {s: len(v) for s, v in bys.items()}, "hard_dev": dict(Counter(h["source"] for h in hard_dev)),
                         "hard_test": dict(Counter(h["source"] for h in hard_test)),
                         "note": "iter-1 dataset hard_DEV split, is_harmful = 0, EN text re-translated here with NLLB (the dataset's gemini SL MT is NOT used)"},
                "nllb": NLLB, "reserved_never_opened": ["hard_FINAL", "refuseu_eval generations/labels (text used for overlap only)", "identity_confirm"],
                "seconds": round(time.time() - t0, 1)}
    (DATA / "split_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    logger.info(f"overlap: {ov}")
    logger.info(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
