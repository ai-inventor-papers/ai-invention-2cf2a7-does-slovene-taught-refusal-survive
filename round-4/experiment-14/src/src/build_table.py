#!/usr/bin/env python3
"""Merge generations + labels + lingua language ID + adjudication into results/rows_final.jsonl (one row per
generation key). Response text is kept in full (<= 128 tokens)."""
from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp

from loguru import logger

from common import ADJ, GENS, LABELS, MODELS, RESULTS, read_jsonl, setup_logging, write_jsonl


def _detect_chunk(texts: list[str]) -> list[tuple[str, float]]:
    from build_items import detect, lingua_detector
    det = lingua_detector()
    return [detect(det, t) for t in texts]


def dose_tag(model: str, lam: float, cond: str) -> str:
    if cond == "ext":
        return "ext"
    if lam == 0:
        return "zero"
    p = RESULTS / f"lambda_steps_{model}.json"
    if p.exists():
        s = json.loads(p.read_text())
        if abs(lam - s["lambda_lo"]) < 1e-9:
            return "lo"
        if abs(lam - s["lambda_hi"]) < 1e-9:
            return "hi"
    return "other"


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("build_table")
    rows = []
    for m in MODELS:
        rows += read_jsonl(GENS / f"{m}.jsonl")
    logger.info(f"{len(rows)} generation rows")
    lid_cache_f = RESULTS / "lid_cache.jsonl"
    lid = {r["key"]: (r["lang"], r["conf"]) for r in read_jsonl(lid_cache_f)}
    todo = [r for r in rows if r["key"] not in lid]
    if todo:
        chunks = [todo[i:i + 400] for i in range(0, len(todo), 400)]
        with ProcessPoolExecutor(max_workers=16, mp_context=mp.get_context("spawn")) as ex:
            res = list(ex.map(_detect_chunk, [[r["response"] for r in c] for c in chunks]))
        new = []
        for c, rr in zip(chunks, res):
            for r, (lg, cf) in zip(c, rr):
                lid[r["key"]] = (lg, cf)
                new.append({"key": r["key"], "lang": lg, "conf": cf})
        with lid_cache_f.open("a") as f:
            for x in new:
                f.write(json.dumps(x) + "\n")
    labs: dict[str, dict] = {}
    for x in read_jsonl(LABELS / "labels.jsonl"):
        d = labs.setdefault(x["key"], {})
        if x["readout"] == "asr":
            d["asr"] = {k: x.get(k) for k in ("refused", "convincing", "specific", "score")}
        else:
            d[x["readout"]] = x["label"]
    ttj = {r["key"]: r["translation"] for r in read_jsonl(LABELS / "ttj_translations.jsonl")}
    adj_lab, adj_key = {}, {}
    for f in sorted(ADJ.glob("author_labels_*.json")):
        adj_lab.update(json.loads(f.read_text()))
    for f in sorted(ADJ.glob("_key_*.json")):
        adj_key.update(json.loads(f.read_text()))
    gold = {adj_key[u]: l for u, l in adj_lab.items() if u in adj_key}
    out = []
    for r in rows:
        lb = labs.get(r["key"], {})
        lg, cf = lid.get(r["key"], ("und", 0.0))
        out.append({k: r[k] for k in ("key", "item_id", "kind", "source", "model", "in_lang", "out_lang", "lambda",
                                      "cond", "arm", "text", "response", "n_new_tokens", "hit_eos", "degenerate")}
                   | {"dose": dose_tag(r["model"], r["lambda"], r["cond"]), "lang_detected": lg, "lang_conf": cf,
                      # amendment A4: primary readout = J1 (local gemini-distilled); paid flash kept as L_flash
                      "L_primary": lb.get("j1"), "L_flash": lb.get("primary"), "L_second": lb.get("second"),
                      "L_ttj": lb.get("ttj_j1") or lb.get("ttj"),
                      "asr": lb.get("asr"), "translated_response": ttj.get(r["key"]), "L_adj": gold.get(r["key"])})
    write_jsonl(RESULTS / "rows_final.jsonl", out)
    logger.info(f"rows_final: {len(out)} rows; primary labelled {sum(o['L_primary'] is not None for o in out)}; "
                f"adjudicated {sum(o['L_adj'] is not None for o in out)}")


if __name__ == "__main__":
    main()
