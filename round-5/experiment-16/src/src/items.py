#!/usr/bin/env python3
"""S1 ITEMS: the never-generated confirmation body (CONF), DEV, twins, dedup re-verification, and NLLB arms.

CONF = exp13 pool items with split in B u C, minus any item whose item_id or norm(en_orig) appears in exp14's items /
rows_final.jsonl, then re-deduplicated against EVERY reference of the plan (exact norm() match, or 8-gram containment
|8g(item) & 8g(ref)| / |8g(item)| > 0.5 against any single reference text; items < 8 tokens: exact only).
DEV = exp13 DEV ids minus exp14/exp15 id/text overlap and dedup hits (dose calibration + compliance gate ONLY).
TWINS = exp13 twins (keep=true, twin_of in CONF, not in exp14 rows) + JBB benign rows matched to CONF JBB items.
ARMS (sentence-split NLLB-1.3B, beam 4): SL_MT, HU_MT, EN_BT = SL_MT->EN, HU_BT = HU_MT->EN; chrF; lingua.

Outputs: data/items_conf.jsonl, data/items_dev.jsonl, data/twins_conf.jsonl, results/dedup_recheck.json,
results/mt_qc.json. Every reference is logged with its n_ref (n_ref == 0 is a hard error).
"""
from __future__ import annotations

import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from loguru import logger

from common import (DATA, DS1, E8, E9, E10, E11, E13, E14, E15, RESULTS, dump, norm, read_jsonl, setup_logging,
                    sha1, sha1_int, sha256_file, write_jsonl)

TEXT_KEYS = ("en_orig", "EN_orig", "en_bt", "EN_BT", "EN_BT_hu", "text", "request", "prompt", "goal", "behavior",
             "en", "input", "Behavior", "forbidden_prompt", "instruction")


def texts_of(row: dict) -> list[str]:
    out = []
    for k in TEXT_KEYS:
        v = row.get(k)
        if isinstance(v, str) and len(v.split()) >= 3:
            out.append(v)
    return out


def load_refs() -> dict[str, list[str]]:
    """reference name -> list of texts (request texts only, never model responses)."""
    refs: dict[str, list[str]] = {}

    def add_jsonl(name: str, p: Path) -> None:
        rows = read_jsonl(p)
        refs.setdefault(name, [])
        for r in rows:
            refs[name] += texts_of(r)

    add_jsonl("exp14_items", E14 / "data/items.jsonl")
    add_jsonl("exp14_dev_items", E14 / "data/dev_items.jsonl")
    add_jsonl("exp14_rows_final", E14 / "results/rows_final.jsonl")
    add_jsonl("exp15_items", E15 / "data/items.jsonl")
    add_jsonl("exp15_rows_final", E15 / "results/rows_final.jsonl")
    for f in ("probe_P200.jsonl", "dev20.jsonl", "harmless100.jsonl", "construct_A2.jsonl", "harmless_dev32.jsonl"):
        add_jsonl("exp8_probes", E8 / "data" / f)
    for f in ("probe_P300.jsonl", "twins_T150.jsonl", "dev12.jsonl", "gate_harmless40.jsonl"):
        add_jsonl("exp9_probes", E9 / "data" / f)
    for f in ("hard_test.jsonl", "hard_dev.jsonl", "construct_harm.jsonl", "p200_test160.jsonl", "p200_dev40.jsonl",
              "induce_test.jsonl", "induce_dev.jsonl", "rq4_harmless.jsonl"):
        add_jsonl("exp10_probes", E10 / "data" / f)
    add_jsonl("exp11_items", E11 / "data/items.jsonl")
    # dependency art_EG6OpEkGvysx (RefusEU eval DEV/FINAL, gold calib, HARD blocks)
    try:
        d = json.loads((DS1 / "full_data_out.json").read_text())
        n = 0
        refs["art_EG6_full_data_out"] = []
        for ds in d.get("datasets", []):
            for ex in ds.get("examples", []):
                inp = ex.get("input")
                if isinstance(inp, str) and len(inp.split()) >= 3:
                    refs["art_EG6_full_data_out"].append(inp)
                    n += 1
        del d
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"art_EG6 full_data_out unreadable: {e}")
        refs["art_EG6_full_data_out"] = []
    # RefusEU all EN/SL splits @5523ce30b9 (HF datasets cache)
    try:
        from datasets import load_dataset
        refs["refuseu_lang_en_sl"] = []
        for cfg in ("lang_en", "lang_sl", "evaluation"):
            ds = load_dataset("NASK-PIB/RefusEU", cfg, revision="5523ce30b9b6af59e95ade9c610b8b974412a6bb")
            for split in ds:
                for r in ds[split]:
                    refs["refuseu_lang_en_sl"] += [v for v in r.values() if isinstance(v, str) and len(v.split()) >= 3]
    except Exception as e:  # noqa: BLE001 - dataset access problems are logged and recorded, not fatal
        logger.error(f"RefusEU load failed: {type(e).__name__}: {str(e)[:200]}")
        refs.setdefault("refuseu_lang_en_sl", [])
    # AdvBench = mlabonne/harmful_behaviors (exp14 saved the canonical csv)
    import csv
    p = E14 / "data/raw/harmful_behaviors.csv"
    refs["advbench_harmful_behaviors"] = []
    if p.exists():
        with p.open() as f:
            for r in csv.DictReader(f):
                refs["advbench_harmful_behaviors"] += [v for v in r.values() if v and len(v.split()) >= 3]
    return refs


def grams8(t: str) -> set[tuple[str, ...]]:
    w = norm(t).split()
    return {tuple(w[i:i + 8]) for i in range(len(w) - 7)}


class RefIndex:
    def __init__(self, refs: dict[str, list[str]]):
        self.exact: dict[str, str] = {}
        self.inv: dict[tuple, set[int]] = defaultdict(set)
        self.meta: list[tuple[str, str]] = []
        for name, texts in refs.items():
            for t in texts:
                nt = norm(t)
                self.exact.setdefault(nt, name)
                rid = len(self.meta)
                self.meta.append((name, t[:120]))
                for g in grams8(t):
                    self.inv[g].add(rid)

    def hit(self, text: str) -> dict | None:
        nt = norm(text)
        if nt in self.exact:
            return {"how": "exact", "ref": self.exact[nt], "score": 1.0}
        g = grams8(text)
        if len(nt.split()) < 8 or not g:
            return None
        cnt: Counter = Counter()
        for x in g:
            for rid in self.inv.get(x, ()):
                cnt[rid] += 1
        if not cnt:
            return None
        rid, c = cnt.most_common(1)[0]
        sc = c / len(g)
        if sc > 0.5:
            return {"how": "8gram", "ref": self.meta[rid][0], "ref_text": self.meta[rid][1], "score": round(sc, 3)}
        return None


def build_sets() -> tuple[list[dict], list[dict], list[dict], dict]:
    pool = read_jsonl(E13 / "data/pool.jsonl")
    man = json.loads((E13 / "data/split_manifest_iter4.json").read_text())["ids"]
    e14_ids = {r["item_id"] for r in read_jsonl(E14 / "results/rows_final.jsonl")} | \
        {r["item_id"] for r in read_jsonl(E14 / "data/items.jsonl")}
    e14_txt = {norm(r["EN_orig"]) for r in read_jsonl(E14 / "data/items.jsonl")} | \
        {norm(r["EN_orig"]) for r in read_jsonl(E14 / "data/dev_items.jsonl")}
    e15_ids = {r["item_id"] for r in read_jsonl(E15 / "data/items.jsonl")}
    e15_txt = {norm(r.get("en_orig", "")) for r in read_jsonl(E15 / "data/items.jsonl")}
    refs = load_refs()
    nref = {k: len(v) for k, v in refs.items()}
    logger.info(f"reference sizes {nref}")
    empty = [k for k, v in nref.items() if v == 0]
    if empty:
        raise RuntimeError(f"n_ref == 0 for references {empty} (plan T1: hard error)")
    idx = RefIndex(refs)
    bc = set(man["B"]) | set(man["C"])
    drops, conf = [], []
    for r in pool:
        if r["item_id"] not in bc:
            continue
        if r["item_id"] in e14_ids or norm(r["en_orig"]) in e14_txt:
            drops.append({"item_id": r["item_id"], "reason": "exp14_overlap"})
            continue
        h = idx.hit(r["en_orig"])
        if h:
            drops.append({"item_id": r["item_id"], "reason": "dedup", **h})
            continue
        conf.append(r)
    dev, dev_drops = [], []
    for r in pool:
        if r["item_id"] not in set(man["DEV"]):
            continue
        if r["item_id"] in e14_ids | e15_ids or norm(r["en_orig"]) in e14_txt | e15_txt:
            dev_drops.append({"item_id": r["item_id"], "reason": "exp14/15_overlap"})
            continue
        h = idx.hit(r["en_orig"])
        if h:
            dev_drops.append({"item_id": r["item_id"], "reason": "dedup", **h})
            continue
        dev.append(r)
    # twins
    conf_ids = {r["item_id"] for r in conf}
    e14_rows_txt = e14_txt | {norm(re.sub(r"\n\n[^\n]*$", "", r.get("text", ""))) for r in
                              read_jsonl(E14 / "results/rows_final.jsonl") if r.get("kind") == "benign"}
    tw = [t for t in read_jsonl(E13 / "data/twins.jsonl") if t.get("keep") and t["twin_of"] in conf_ids
          and norm(t["en_orig"]) not in e14_rows_txt]
    tw_txt = {norm(t["en_orig"]) for t in tw}
    jbb_conf = {r["jbb_index"]: r["item_id"] for r in conf if r["source"] == "jbb" and r.get("jbb_index") is not None}
    jb = read_jsonl(E13 / "data/jbb_benign.jsonl")
    twins = [{"item_id": t["twin_id"], "twin_of": t["twin_of"], "en_orig": t["en_orig"], "how": t["how"],
              "matched": True} for t in tw]
    for j in jb:
        if j["jbb_index"] in jbb_conf and norm(j["text"]) not in e14_rows_txt and norm(j["text"]) not in tw_txt:
            twins.append({"item_id": f"jbbb_{j['jbb_index']}", "twin_of": jbb_conf[j["jbb_index"]],
                          "en_orig": j["text"], "how": "jbb_benign", "matched": True})
            tw_txt.add(norm(j["text"]))
    n_raw_twins = len(twins)
    if len(twins) > 160:
        twins = sorted(twins, key=lambda t: sha1_int("iter5_twin|" + t["en_orig"]))[:120]
    elif len(twins) < 100:
        used = {norm(t["en_orig"]) for t in twins}
        extra = sorted([j for j in jb if norm(j["text"]) not in used and norm(j["text"]) not in e14_rows_txt],
                       key=lambda j: sha1_int("iter5_twin|" + j["text"]))
        for j in extra[:100 - len(twins)]:
            twins.append({"item_id": f"jbbb_{j['jbb_index']}", "twin_of": None, "en_orig": j["text"],
                          "how": "jbb_benign_unmatched", "matched": False})
    info = {"n_conf": len(conf), "per_source": dict(Counter(r["source"] for r in conf)),
            "per_split": dict(Counter(r["split"] for r in conf)), "n_dev": len(dev), "n_twins": len(twins),
            "n_twins_before_cap": n_raw_twins, "twins_matched_share": sum(t["matched"] for t in twins) / max(1, len(twins)),
            "twins_by_how": dict(Counter(t["how"] for t in twins)), "n_ref_per_source": nref,
            "conf_drops": drops, "dev_drops": dev_drops,
            "drops_by_reason": dict(Counter((d["reason"], d.get("ref")) for d in drops).most_common()),
            "reduced_body": len(conf) < 260,
            "gate_n_conf_ge_260": len(conf) >= 260}
    info["drops_by_reason"] = {f"{k[0]}|{k[1]}": v for k, v in info["drops_by_reason"].items()}
    # assert zero overlap with exp14 / exp15 rows (T1)
    e15_rows_txt = {norm(r.get("request", "")) for r in read_jsonl(E15 / "results/rows_final.jsonl")}
    ov = [r["item_id"] for r in conf if r["item_id"] in e14_ids | e15_ids or norm(r["en_orig"]) in e14_txt | e15_rows_txt]
    assert not ov, f"CONF overlaps exp14/exp15: {ov[:5]}"
    info["assert_zero_overlap_exp14_exp15"] = True
    return conf, dev, twins, info


def make_arms(rows: list[dict], nllb) -> dict:
    from translate import chrf, detect, n_sentences
    en = [r["en_orig"] for r in rows]
    sl = nllb.translate(en, "eng_Latn", "slv_Latn")
    hu = nllb.translate(en, "eng_Latn", "hun_Latn")
    bt = nllb.translate(sl, "slv_Latn", "eng_Latn")
    bth = nllb.translate(hu, "hun_Latn", "eng_Latn")
    for r, a, b, c, d in zip(rows, sl, hu, bt, bth):
        r.update({"EN_orig": r["en_orig"], "SL_MT": a, "HU_MT": b, "EN_BT": c, "HU_BT": d,
                  "chrF_sl": chrf(c, r["en_orig"]), "chrF_hu": chrf(d, r["en_orig"]),
                  "n_sent_en": n_sentences(r["en_orig"]), "n_sent_sl": n_sentences(a), "n_sent_hu": n_sentences(b),
                  "lid_sl": detect(a)[0], "lid_hu": detect(b)[0]})
        r["mt_fragile_sl"] = r["chrF_sl"] < 40
        r["mt_fragile_hu"] = r["chrF_hu"] < 40
        r["mt_fragile"] = r["mt_fragile_sl"] or r["mt_fragile_hu"]
        r["sent_mismatch"] = not (r["n_sent_en"] == r["n_sent_sl"] == r["n_sent_hu"])
    return {"median_chrF_sl": statistics.median([r["chrF_sl"] for r in rows]),
            "median_chrF_hu": statistics.median([r["chrF_hu"] for r in rows])}


def main() -> None:
    setup_logging("items")
    import torch
    torch.cuda.set_per_process_memory_fraction(0.9)
    conf, dev, twins, info = build_sets()
    logger.info(f"CONF {info['n_conf']} {info['per_source']}; DEV {info['n_dev']}; twins {info['n_twins']} "
                f"{info['twins_by_how']}")
    from translate import NLLB200
    nllb = NLLB200()
    qc = {}
    for name, rows in (("conf", conf), ("dev", dev), ("twins", twins)):
        qc[name] = make_arms(rows, nllb)
        logger.info(f"MT {name}: {qc[name]}")
    gate = qc["conf"]["median_chrF_sl"] >= 60 and qc["conf"]["median_chrF_hu"] >= 60
    qc["gate_median_chrF_ge_60"] = gate
    if not gate:  # fallback: beam 5 + no-repeat-ngram 3 for the failing language, recorded
        logger.warning("chrF gate failed -> beam 5 / no_repeat_ngram 3 re-translation of CONF")
        qc["fallback_beam5"] = True
        for rows in (conf, dev, twins):
            sl = nllb.translate([r["en_orig"] for r in rows], "eng_Latn", "slv_Latn", num_beams=5, no_repeat=3)
            hu = nllb.translate([r["en_orig"] for r in rows], "eng_Latn", "hun_Latn", num_beams=5, no_repeat=3)
            bt = nllb.translate(sl, "slv_Latn", "eng_Latn", num_beams=5, no_repeat=3)
            bth = nllb.translate(hu, "hun_Latn", "eng_Latn", num_beams=5, no_repeat=3)
            from translate import chrf
            for r, a, b, c, d in zip(rows, sl, hu, bt, bth):
                r.update({"SL_MT": a, "HU_MT": b, "EN_BT": c, "HU_BT": d, "chrF_sl": chrf(c, r["en_orig"]),
                          "chrF_hu": chrf(d, r["en_orig"])})
                r["mt_fragile"] = r["chrF_sl"] < 40 or r["chrF_hu"] < 40
        qc["conf_after_fallback"] = {"median_chrF_sl": statistics.median([r["chrF_sl"] for r in conf]),
                                     "median_chrF_hu": statistics.median([r["chrF_hu"] for r in conf])}
    for r in conf + dev:
        r["kind"] = "harmful"
    for r in twins:
        r["kind"] = "twin"
    write_jsonl(DATA / "items_conf.jsonl", conf)
    write_jsonl(DATA / "items_dev.jsonl", dev)
    write_jsonl(DATA / "twins_conf.jsonl", twins)
    for name, rows in (("conf", conf), ("twins", twins)):
        qc[name].update({"n": len(rows), "n_fragile": sum(r["mt_fragile"] for r in rows),
                         "lid_sl_ok": sum(r["lid_sl"] == "sl" for r in rows) / len(rows),
                         "lid_hu_ok": sum(r["lid_hu"] == "hu" for r in rows) / len(rows),
                         "sentence_count_mismatch": sum(r["sent_mismatch"] for r in rows)})
    eye = sorted(conf, key=lambda r: sha1_int("iter5_eye|" + r["item_id"]))[:5]
    qc["eyeball_5"] = [{k: r[k] for k in ("item_id", "EN_orig", "SL_MT", "HU_MT", "EN_BT", "chrF_sl", "chrF_hu",
                                          "n_sent_en", "n_sent_sl", "n_sent_hu")} for r in eye]
    tr = next((r for r in conf + dev if r["item_id"] == "i4_7cebf8a68dce"), None)
    qc["exp13_truncation_case_i4_7cebf8a68dce"] = ({k: tr[k] for k in ("EN_orig", "SL_MT", "EN_BT", "chrF_sl",
                                                                       "n_sent_en", "n_sent_sl")} if tr else "not in sets")
    dump(RESULTS / "mt_qc.json", qc)
    info["hashes"] = {f: sha256_file(DATA / f) for f in ("items_conf.jsonl", "items_dev.jsonl", "twins_conf.jsonl")}
    dump(RESULTS / "dedup_recheck.json", info)
    logger.info(f"done: {json.dumps({k: v for k, v in qc.items() if k not in ('eyeball_5',)}, default=str)[:800]}")


if __name__ == "__main__":
    logger.catch(reraise=True)(main)()
