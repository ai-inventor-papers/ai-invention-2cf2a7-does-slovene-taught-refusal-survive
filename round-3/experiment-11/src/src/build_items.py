#!/usr/bin/env python3
"""S1 ITEMS: third-language (L3 = Hungarian) NLLB MT from the SAME English source as the Slovene arm, chrF QC, fixed
seeded subsets (nested so that a pre-registered cut takes a prefix), Belebele items. Writes:
  data/items.jsonl              one row per prompt (set, split, item_id, pair_id, arm, prompt_lang, text, meta)
  data/split_manifest_iter3.json  subset id lists (ranked; prefixes are the reduced sizes) + sha256
  data/belebele.jsonl, data/flores_passages.jsonl
  results/l3_mt_qc.json
Source of the EN / SL_MT / EN_BT texts: iter-2 exp5 data/{refuseu_x,hard,identity}.jsonl (READ-ONLY), built from the
dataset artifact art_EG6OpEkGvysx; the refuseu_x EN originals are the dataset's refuseu_eval EN rows.
"""
from __future__ import annotations

import argparse
import gc
import json
import re
import time
from collections import Counter, defaultdict

import torch
from loguru import logger

from common import (DATA, DS_DIR, E5, L3_CODE, RESULTS, SEED, append_jsonl, read_jsonl, setup_logging, sha1_int,
                    sha256_file, write_jsonl)

NLLB = "facebook/nllb-200-distilled-1.3B"


# ---- NLLB with the dataset artifact's lib/mt.py settings (sentence split, beam 4, max_length 400) ----
def split_segments(text: str) -> list[tuple[int, str]]:
    segs = []
    for pi, para in enumerate(text.split("\n")):
        if not para.strip():
            segs.append((pi, ""))
            continue
        for s in re.split(r"(?<=[.!?])\s+(?=[\"'“A-ZČŠŽÁÉÍÓÖŐÚÜŰ0-9(])", para.strip()):
            if s.strip():
                segs.append((pi, s.strip()))
    return segs


def join_segments(segs: list[tuple[int, str]], outs: list[str]) -> str:
    paras: dict[int, list[str]] = {}
    for (pi, _), o in zip(segs, outs):
        paras.setdefault(pi, []).append(o)
    return "\n".join(" ".join(x for x in paras[k] if x) for k in sorted(paras))


class NLLB200:
    def __init__(self):
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        self.tok = AutoTokenizer.from_pretrained(NLLB)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(NLLB, dtype=torch.float16).cuda().eval()

    @torch.inference_mode()
    def _gen(self, sents: list[str], src: str, tgt: str, bs: int = 64, num_beams: int = 4) -> list[str]:
        self.tok.src_lang = src
        order = sorted(range(len(sents)), key=lambda i: -len(sents[i]))
        out = [""] * len(sents)
        i = 0
        while i < len(order):
            idx = order[i:i + bs]
            try:
                enc = self.tok([sents[j] for j in idx], return_tensors="pt", padding=True, truncation=True,
                               max_length=400).to("cuda")
                gen = self.model.generate(**enc, num_beams=num_beams,
                                          max_new_tokens=int(enc.input_ids.shape[1] * 1.6 + 16),
                                          forced_bos_token_id=self.tok.convert_tokens_to_ids(tgt))
                for j, t in zip(idx, self.tok.batch_decode(gen, skip_special_tokens=True)):
                    out[j] = t.strip()
                i += bs
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                bs = max(1, bs // 2)
                logger.warning(f"NLLB OOM -> bs {bs}")
        return out

    def translate(self, texts: list[str], src: str, tgt: str) -> list[str]:
        t0 = time.time()
        segs = [split_segments(x) for x in texts]
        flat = [s for sg in segs for _, s in sg if s]
        tr = self._gen(flat, src, tgt) if flat else []
        it = iter(tr)
        res = [join_segments(sg, [next(it) if s else "" for _, s in sg]) for sg in segs]
        logger.info(f"NLLB {src}->{tgt}: {len(texts)} texts / {len(flat)} segments in {time.time() - t0:.0f}s")
        return res


def chrf(hyp: str, ref: str) -> float:
    from sacrebleu.metrics import CHRF
    return round(CHRF().sentence_score(hyp, [ref]).score, 2)


def ranked(ids_with_strata: list[tuple[str, str]], salt: str) -> list[str]:
    """Stratified systematic ranking: within each stratum order by sha1(id+salt); global order by (position+0.5)/size
    so that ANY prefix is approximately proportionally stratified (nested subsets)."""
    by = defaultdict(list)
    for iid, st in ids_with_strata:
        by[st].append(iid)
    keyed = []
    for st, v in by.items():
        v = sorted(v, key=lambda i: sha1_int(i + salt))
        for pos, iid in enumerate(v):
            keyed.append(((pos + 0.5) / len(v), sha1_int(iid + salt + "tb"), iid))
    return [x[2] for x in sorted(keyed)]


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mini", action="store_true", help="translate only 20 items (T2 smoke)")
    args = ap.parse_args()
    setup_logging("build_items")
    x5 = read_jsonl(E5 / "data/refuseu_x.jsonl")
    h5 = read_jsonl(E5 / "data/hard.jsonl")
    id5 = read_jsonl(E5 / "data/identity.jsonl")
    ds = json.loads((DS_DIR / "full_data_out.json").read_text())
    blocks = {b["dataset"]: b["examples"] for b in ds["datasets"]}
    en_src = {e["metadata_pair_id"]: e["input"] for e in blocks["refuseu_eval"] if e["metadata_lang"] == "en"}
    del ds, blocks
    gc.collect()

    # ---------------- RefusEU-x items (item = pair_id) ----------------
    xitems: dict[str, dict] = {}
    for r in x5:
        it = xitems.setdefault(r["pair_id"], {k: r[k] for k in ("set", "split", "pair_id", "label", "group", "pure",
                                                                 "bt_chrf")})
        it["item_id"] = r["pair_id"]
        it["exp5_item_id"] = r["item_id"]
        it[r["arm"]] = r["text"]
    for pid, it in xitems.items():
        it["EN_orig"] = en_src[pid]
    xs = [it for it in xitems.values() if it["split"] in ("FINAL", "DEV")]
    c = Counter(it["split"] for it in xs)
    logger.info(f"refuseu_x items {dict(c)}; with EN_BT: {Counter(it['split'] for it in xs if 'EN_BT' in it)}")
    assert c["FINAL"] == 1296, c

    # ---------------- HARD items (FINAL only) ----------------
    hitems: dict[str, dict] = {}
    for r in h5:
        if r["split"] != "FINAL":
            continue
        it = hitems.setdefault(r["item_id"], {k: r[k] for k in ("set", "split", "item_id", "pair_id", "source",
                                                                 "is_harmful", "category", "group", "mt_fragile",
                                                                 "bt_chrf", "xstest_type")})
        it[r["arm"]] = r["text"]
    hs = list(hitems.values())
    logger.info(f"HARD FINAL items {len(hs)}: {Counter((h['source'], h['is_harmful']) for h in hs)}")
    assert len(hs) == 1442

    # ---------------- subsets (ranked, nested) ----------------
    fin = [it for it in xs if it["split"] == "FINAL"]
    safe = [h for h in hs if not h["is_harmful"]]
    unsafe = [h for h in hs if h["is_harmful"]]
    safe_rank = ranked([(h["item_id"], f"{h['source']}|{h['group']}") for h in safe], f"hardsafe{SEED}")
    hardsafe50 = safe_rank[:547]
    unsafe_rank = ranked([(h["item_id"], f"{h['source']}|{h['group']}") for h in unsafe], f"hardunsafe{SEED}")

    # L3 translation needed for: RefusEU-x FINAL + DEV EN_orig, HARD unsafe + HARDSAFE50 EN_orig
    todo_x = xs if not args.mini else xs[:10]
    hs_need = [h for h in hs if h["is_harmful"] or h["item_id"] in set(hardsafe50)]
    todo_h = hs_need if not args.mini else hs_need[:10]
    mt_cache_p = DATA / "l3_mt_cache.jsonl"
    cache = {r["key"]: r for r in read_jsonl(mt_cache_p)}
    need = [(f"x|{it['pair_id']}", it["EN_orig"]) for it in todo_x] + \
           [(f"h|{h['item_id']}", h["EN_orig"]) for h in todo_h]
    need = [(k, t) for k, t in need if k not in cache]
    if need:
        mt = NLLB200()
        hu = mt.translate([t for _, t in need], "eng_Latn", L3_CODE["nllb"])
        bt = mt.translate(hu, L3_CODE["nllb"], "eng_Latn")
        # T2 reproduction check: NLLB EN->SL on 20 items vs the saved SL_MT (same system, same settings)
        repro = []
        if not (DATA / "sl_repro_check.json").exists():
            sub = sorted(fin, key=lambda i: sha1_int(i["pair_id"] + "repro"))[:20]
            sl_re = mt.translate([i["EN_orig"] for i in sub], "eng_Latn", "slv_Latn")
            repro = [{"pair_id": i["pair_id"], "chrf_vs_saved_SL_MT": chrf(s, i["SL_MT"])} for i, s in zip(sub, sl_re)]
            vals = sorted(r["chrf_vs_saved_SL_MT"] for r in repro)
            (DATA / "sl_repro_check.json").write_text(json.dumps(
                {"n": len(repro), "median_chrf": vals[len(vals) // 2], "min": vals[0], "rows": repro,
                 "note": "EN_orig re-translated with NLLB-1.3B beam 4 sentence-split (dataset lib/mt.py settings) vs "
                         "the saved refuseu_x SL_MT; high chrF confirms EN_orig is the true source"}, indent=1))
            logger.info(f"SL reproduction chrF median {vals[len(vals) // 2]} min {vals[0]}")
        del mt
        gc.collect()
        torch.cuda.empty_cache()
        rows = []
        for (k, en), h_, b_ in zip(need, hu, bt):
            ratio = len(h_) / max(1, len(en))
            rows.append({"key": k, "L3_MT": h_, "L3_BT": b_, "l3_chrf": chrf(b_, en), "len_ratio": round(ratio, 3),
                         "bt_len_ratio": round(len(b_) / max(1, len(en)), 3)})
        append_jsonl(mt_cache_p, rows)
        cache.update({r["key"]: r for r in rows})

    # language ID of the L3 MT
    from lingua import Language, LanguageDetectorBuilder
    det = LanguageDetectorBuilder.from_languages(Language.ENGLISH, Language.SLOVENE, Language.HUNGARIAN,
                                                 Language.CROATIAN).build()

    def attach(it: dict, key: str) -> None:
        r = cache.get(key)
        if not r:
            return
        it["L3_MT"], it["L3_BT"], it["l3_chrf"] = r["L3_MT"], r["L3_BT"], r["l3_chrf"]
        it["l3_len_ratio"], it["l3_bt_len_ratio"] = r["len_ratio"], r["bt_len_ratio"]
        it["l3_fragile"] = bool(r["l3_chrf"] < 40 or not (0.5 <= r["len_ratio"] <= 2.0))
        it["l3_bt_halluc"] = bool(r["bt_len_ratio"] > 1.5)
        lg = det.detect_language_of(r["L3_MT"])
        it["l3_langid"] = lg.name if lg else "NONE"

    for it in xs:
        attach(it, f"x|{it['pair_id']}")
    for h in hs:
        attach(h, f"h|{h['item_id']}")
    if args.mini:
        done = [it for it in xs + hs if "L3_MT" in it]
        for it in done[:6]:
            logger.info(f"MINI {it['item_id']}: chrF {it['l3_chrf']} lid {it['l3_langid']} :: {it['L3_MT'][:160]!r}")
        return

    # CURVE / PUB ranking on FINAL RefusEU-x (exclude SL bt_chrf < 40 or L3 chrF < 40; need EN_BT)
    elig = [it for it in fin if "EN_BT" in it and (it.get("bt_chrf") or 0) >= 40 and it.get("l3_chrf", 0) >= 40]
    curve_rank = ranked([(it["pair_id"], f"{it['group']}|{it['pure']}") for it in elig], f"curve{SEED}")
    hs100 = hardsafe50[:100]
    hard150_safe = hardsafe50[:150]
    dev_x = [it["pair_id"] for it in xs if it["split"] == "DEV" and "EN_BT" in it]
    manifest = {
        "seed": SEED,
        "note": "ranked lists: a pre-registered cut to size k takes the first k ids (stratified systematic ranking)",
        "CURVE_rank": curve_rank, "CURVE300": curve_rank[:300], "CURVE200": curve_rank[:200],
        "PUB400": curve_rank[:400],
        "REFUSEU_X_FINAL": sorted(it["pair_id"] for it in fin),
        "REFUSEU_X_FINAL_with_EN_BT": sorted(it["pair_id"] for it in fin if "EN_BT" in it),
        "HARDSAFE_rank": safe_rank, "HARDSAFE50": hardsafe50, "HARDSAFE50_cut273": hardsafe50[:273],
        "HARDSAFE100": hs100, "HARDSAFE100_cut50": hs100[:50],
        "HARD_UNSAFE_rank": unsafe_rank, "HARD150_unsafe": unsafe_rank[:150], "HARD150_safe": hard150_safe,
        "DEV100": sorted(dev_x),
        "counts": {"refuseu_x_FINAL": len(fin), "eligible_curve": len(elig), "hard_safe": len(safe),
                   "hard_unsafe": len(unsafe), "DEV": len(dev_x)},
    }
    for k in list(manifest):
        if isinstance(manifest[k], list):
            manifest[f"{k}__sha256"] = __import__("hashlib").sha256("\n".join(manifest[k]).encode()).hexdigest()
    (DATA / "split_manifest_iter3.json").write_text(json.dumps(manifest, indent=1))

    # ---------------- prompt rows ----------------
    rows = []
    for it in xs:
        meta = {k: it.get(k) for k in ("label", "group", "pure", "bt_chrf", "l3_chrf", "l3_fragile", "exp5_item_id")}
        for arm in ("EN_orig", "EN_BT", "SL_MT", "L3_MT"):
            if it.get(arm):
                rows.append({"set": "refuseu_x", "split": it["split"], "item_id": it["pair_id"],
                             "pair_id": it["pair_id"], "arm": arm, "prompt_lang": {"L3_MT": "hu", "SL_MT": "sl"}.get(arm, "en"),
                             "text": it[arm], "is_harmful": True, **meta})
    for h in hs:
        meta = {k: h.get(k) for k in ("source", "category", "group", "mt_fragile", "bt_chrf", "l3_chrf", "l3_fragile",
                                      "xstest_type")}
        for arm in ("EN_orig", "EN_BT", "SL_MT", "L3_MT"):
            if h.get(arm):
                rows.append({"set": "hard", "split": "FINAL", "item_id": h["item_id"], "pair_id": h["item_id"],
                             "arm": arm, "prompt_lang": {"L3_MT": "hu", "SL_MT": "sl"}.get(arm, "en"), "text": h[arm],
                             "is_harmful": h["is_harmful"], **meta})
    for r in id5:
        if r["split"] == "FINAL":
            rows.append({"set": "identity", "split": "FINAL", "item_id": r["item_id"], "pair_id": r["pair_id"],
                         "arm": r["arm"], "prompt_lang": r["prompt_lang"], "text": r["text"], "is_harmful": False,
                         "kind": r["kind"], "facet": r["facet"]})
    for r in rows:
        r["gid"] = f"{r['set']}|{r['arm']}|{r['item_id']}"
    assert len({r["gid"] for r in rows}) == len(rows), "duplicate gid"
    write_jsonl(DATA / "items.jsonl", rows)
    logger.info(f"items.jsonl {len(rows)} rows: {Counter((r['set'], r['split'], r['arm']) for r in rows)}")

    # ---------------- L3 MT QC ----------------
    def q(vals):
        v = sorted(vals)
        return {"n": len(v), "median": v[len(v) // 2] if v else None, "p10": v[len(v) // 10] if v else None,
                "share_lt40": round(sum(x < 40 for x in v) / max(1, len(v)), 4)}
    xq = [it for it in xs if "l3_chrf" in it]
    hq = [h for h in hs if "l3_chrf" in h]
    qc = {"l3": L3_CODE, "mt_system": f"{NLLB} beam 4, sentence-split (dataset lib/mt.py settings); BT = same NLLB "
                                         "hun->eng (QC only; a self-consistent round trip, so chrF is optimistic)",
          "refuseu_x_chrf": q([it["l3_chrf"] for it in xq]), "hard_chrf": q([h["l3_chrf"] for h in hq]),
          "refuseu_x_SL_bt_chrf_reference": q([it["bt_chrf"] for it in xq if it.get("bt_chrf") is not None]),
          "n_l3_fragile": sum(it["l3_fragile"] for it in xq + hq),
          "n_bt_halluc_gt1.5x": sum(it["l3_bt_halluc"] for it in xq + hq),
          "langid": dict(Counter(it["l3_langid"] for it in xq + hq)),
          "gate_median_ge_60": q([it["l3_chrf"] for it in xq])["median"] >= 60}
    (RESULTS / "l3_mt_qc.json").write_text(json.dumps(qc, indent=1))
    logger.info(f"L3 QC: {qc}")

    # ---------------- Belebele (same 200 question ids in EN / SL / L3) + FLORES passages ----------------
    from datasets import load_dataset
    bb = {}
    for code in ("eng_Latn", "slv_Latn", L3_CODE["belebele"]):
        d = load_dataset("facebook/belebele", code, split="test")
        bb[code] = {f"{r['link']}|{r['question_number']}": r for r in d}
    common_ids = sorted(set.intersection(*[set(v) for v in bb.values()]), key=lambda i: sha1_int(i + str(SEED)))
    qids = common_ids[:200]
    brow, prow, seen = [], [], set()
    for code, lang in (("eng_Latn", "en"), ("slv_Latn", "sl"), (L3_CODE["belebele"], "hu")):
        for qid in qids:
            r = bb[code][qid]
            brow.append({"qid": qid, "lang": lang, "passage": r["flores_passage"], "question": r["question"],
                         "options": [r[f"mc_answer{i}"] for i in range(1, 5)], "answer": int(r["correct_answer_num"])})
    plinks = []
    for qid in common_ids:
        link = qid.split("|")[0]
        if link not in seen:
            seen.add(link)
            plinks.append(qid)
        if len(plinks) == 200:
            break
    for code, lang in (("eng_Latn", "en"), ("slv_Latn", "sl"), (L3_CODE["belebele"], "hu")):
        for qid in plinks:
            prow.append({"passage_id": qid.split("|")[0], "lang": lang, "text": bb[code][qid]["flores_passage"]})
    write_jsonl(DATA / "belebele.jsonl", brow)
    write_jsonl(DATA / "flores_passages.jsonl", prow)
    logger.info(f"belebele {len(brow)} rows, passages {len(prow)}")
    hashes = {p.name: sha256_file(p) for p in sorted(DATA.glob("*.json*"))}
    (DATA / "data_hashes.json").write_text(json.dumps(hashes, indent=1))


if __name__ == "__main__":
    main()
