#!/usr/bin/env python3
"""PHASE 4 frame: drawn (seed 20260926) from the GENERATION files only - no label file is opened here - by simple
random sampling within strata; inclusion probabilities stored for PPI. Blind file: request (EN source) + response,
judge labels stripped, model / lambda / cell hidden, row order shuffled. The executor (author model, NOT human) labels
REFUSE / PARTIAL / COMPLY with the P1 definitions into adjudication/author_labels.json.

  --mode draw   write adjudication/blind_items_<tag>.jsonl, _key_<tag>.json, frame_<tag>.json (one frame per model
                block, drawn as soon as that block's generations are complete: tag g = Gemma, s = GaMS, x = C-EXT)
  --mode batch  print blind batch k (for reading)"""
from __future__ import annotations

import argparse
import json
import random

from loguru import logger

from common import ADJ, DATA, GENS, SEED, dump, read_jsonl, setup_logging, write_jsonl
from build_table import dose_tag

STRATA = [  # (name, model, out_lang filter, dose filter, n, input split)
    ("gemma|sl|edited", "gemma_it", "sl", ("lo", "hi"), 60, ("sl", "en")),
    ("gams|sl|edited", "gams3_it", "sl", ("lo", "hi"), 60, ("sl", "en")),
    ("gemma|en|edited", "gemma_it", "en", ("lo", "hi"), 30, None),
    ("gams|en|edited", "gams3_it", "en", ("lo", "hi"), 30, None),
    ("gemma|hu|edited", "gemma_it", "hu", ("lo", "hi"), 30, None),
    ("gams|hu|edited", "gams3_it", "hu", ("lo", "hi"), 30, None),
]


def draw(ext_models: list[str], models: list[str], tag: str) -> None:
    rng = random.Random(f"{SEED}|{tag}")
    items = {r["item_id"]: r for r in read_jsonl(DATA / "items.jsonl")}
    pool = {}
    for m in (*models, *ext_models):
        for r in read_jsonl(GENS / f"{m}.jsonl"):
            if r["kind"] == "harmful" and r["cond"] in ("edit", "ext"):
                r["dose"] = dose_tag(m, r["lambda"], r["cond"])
                pool.setdefault(m, []).append(r)
    frame, meta = [], {}
    for name, m, o, doses, n, split in STRATA:
        if m not in models:
            continue
        cand = sorted([r for r in pool.get(m, []) if r["out_lang"] == o and r["dose"] in doses], key=lambda r: r["key"])
        if split:
            pick = []
            for i in split:
                sub = [r for r in cand if r["in_lang"] == i]
                pick += rng.sample(sub, min(n // 2, len(sub)))
                meta[f"{name}|in={i}"] = {"N": len(sub), "n": min(n // 2, len(sub))}
        else:
            pick = rng.sample(cand, min(n, len(cand)))
            meta[name] = {"N": len(cand), "n": len(pick)}
        for r in pick:
            stratum = f"{name}|in={r['in_lang']}" if split else name
            frame.append((stratum, r))
    for m in ext_models:
        for o in ("sl", "en"):
            cand = sorted([r for r in pool.get(m, []) if r["out_lang"] == o], key=lambda r: r["key"])
            pick = rng.sample(cand, min(10, len(cand)))
            meta[f"{m}|{o}|ext"] = {"N": len(cand), "n": len(pick)}
            frame += [(f"{m}|{o}|ext", r) for r in pick]
    zero = sorted([r for m in models for r in pool.get(m, []) if r["dose"] == "zero"], key=lambda r: r["key"])
    pick = rng.sample(zero, min(15 * len(models), len(zero)))
    meta["lambda0"] = {"N": len(zero), "n": len(pick)}
    frame += [("lambda0", r) for r in pick]
    rng.shuffle(frame)
    blind, key = [], {}
    for k, (st, r) in enumerate(frame):
        uid = f"{tag}{k:03d}"
        blind.append({"uid": uid, "request_en_source": items[r["item_id"]]["EN_orig"], "response": r["response"]})
        key[uid] = r["key"]
        meta.setdefault("_rows", {})[uid] = {"stratum": st, "N": meta.get(st, {}).get("N"), "n": meta.get(st, {}).get("n")}
    write_jsonl(ADJ / f"blind_items_{tag}.jsonl", blind)
    dump(ADJ / f"_key_{tag}.json", key)
    dump(ADJ / f"frame_{tag}.json", meta)
    logger.info(f"frame {len(blind)} rows: " + ", ".join(f"{k}={v['n']}/{v['N']}" for k, v in meta.items()
                                                          if k != "_rows"))


def batch(k: int, size: int, tag: str) -> None:
    b = read_jsonl(ADJ / f"blind_items_{tag}.jsonl")[k * size:(k + 1) * size]
    for r in b:
        print(f"### {r['uid']}\nREQ: {r['request_en_source']}\nRESP: {r['response']}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="draw")
    ap.add_argument("--ext", default="")
    ap.add_argument("--models", default="gemma_it")
    ap.add_argument("--tag", default="g")
    ap.add_argument("--k", type=int, default=0)
    ap.add_argument("--size", type=int, default=30)
    a = ap.parse_args()
    setup_logging("adjudicate_frame")
    if a.mode == "draw":
        draw([x for x in a.ext.split(",") if x], [x for x in a.models.split(",") if x], a.tag)
    else:
        batch(a.k, a.size, a.tag)
