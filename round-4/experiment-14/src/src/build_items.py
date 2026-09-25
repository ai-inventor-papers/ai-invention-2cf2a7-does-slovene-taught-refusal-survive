#!/usr/bin/env python3
"""0.3 ITEMS: NLLB-200-distilled-1.3B MT with exp11's settings (fp16, sentence split, beam 4, max_length 400;
functions copied from iter_3/gen_art/gen_art_experiment_11/src/build_items.py):
  EN_orig -> SL_MT (slv_Latn), EN_orig -> HU_MT (hun_Latn), SL_MT -> EN_BT, HU_MT -> EN_BT_hu (chrF only)
chrF(EN_BT, EN_orig) and chrF(EN_BT_hu, EN_orig); GATE median >= 60 per language; fragile = chrF < 40 or length ratio
outside [0.5, 2]. lingua check that SL_MT is Slovene and HU_MT is Hungarian. The English INPUT arm is EN_BT.
Also: DEV items (60 exp9 P300 EN_BT, never confirmation), the 32 KL stems (exp8 harmless_dev32 EN + NLLB SL), the
suffix back-translation QA (0.4), and the TTJ mode (translate SL/HU responses to English, greedy, 256 tokens).
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from collections import Counter

import torch
from loguru import logger

from common import (DATA, E8, E9, GENS, LABELS, RESULTS, SEED, SUFFIX, SUFFIX_BACKUP, dump, read_jsonl, setup_logging,
                    sha1_int, sha256_file, write_jsonl, append_jsonl)

NLLB = "facebook/nllb-200-distilled-1.3B"


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

    def translate(self, texts: list[str], src: str, tgt: str, num_beams: int = 4, bs: int = 64) -> list[str]:
        t0 = time.time()
        segs = [split_segments(x) for x in texts]
        flat = [s for sg in segs for _, s in sg if s]
        tr = self._gen(flat, src, tgt, bs=bs, num_beams=num_beams) if flat else []
        it = iter(tr)
        res = [join_segments(sg, [next(it) if s else "" for _, s in sg]) for sg in segs]
        logger.info(f"NLLB {src}->{tgt}: {len(texts)} texts / {len(flat)} segments in {time.time() - t0:.0f}s")
        return res


def chrf(hyp: str, ref: str) -> float:
    from sacrebleu.metrics import CHRF
    return round(CHRF().sentence_score(hyp, [ref]).score, 2)


def lingua_detector():
    from lingua import Language, LanguageDetectorBuilder
    langs = [Language.ENGLISH, Language.SLOVENE, Language.HUNGARIAN, Language.CROATIAN, Language.SERBIAN,
             Language.BOSNIAN, Language.GERMAN, Language.ITALIAN, Language.SLOVAK, Language.CZECH, Language.POLISH,
             Language.SPANISH, Language.FRENCH, Language.PORTUGUESE, Language.RUSSIAN, Language.ROMANIAN,
             Language.DUTCH]
    return LanguageDetectorBuilder.from_languages(*langs).build()


ISO = {"ENGLISH": "en", "SLOVENE": "sl", "HUNGARIAN": "hu"}


def detect(det, text: str) -> tuple[str, float]:
    t = (text or "").strip()
    if len(t.split()) < 3:
        return "und", 0.0
    vals = det.compute_language_confidence_values(t)
    if not vals:
        return "und", 0.0
    top = vals[0]
    name = top.language.name
    return ISO.get(name, name.lower()[:5]), round(float(top.value), 3)


def mode_items(nllb: NLLB200) -> None:
    harm = read_jsonl(DATA / "pool_harmful.jsonl")
    ben = read_jsonl(DATA / "pool_benign.jsonl")
    items = [{"item_id": r["item_id"], "kind": r["kind"], "source": r["src"], "category": r.get("category"),
              "twin_of": r.get("twin_of"), "benign_origin": r.get("benign_origin"), "EN_orig": r["text"]}
             for r in harm + ben]
    en = [x["EN_orig"] for x in items]
    sl = nllb.translate(en, "eng_Latn", "slv_Latn")
    hu = nllb.translate(en, "eng_Latn", "hun_Latn")
    bt = nllb.translate(sl, "slv_Latn", "eng_Latn")
    bth = nllb.translate(hu, "hun_Latn", "eng_Latn")
    det = lingua_detector()
    for x, a, b, c, d in zip(items, sl, hu, bt, bth):
        x.update({"SL_MT": a, "HU_MT": b, "EN_BT": c, "EN_BT_hu": d, "chrF_sl": chrf(c, x["EN_orig"]),
                  "chrF_hu": chrf(d, x["EN_orig"])})
        lr_sl = len(a) / max(1, len(x["EN_orig"]))
        lr_hu = len(b) / max(1, len(x["EN_orig"]))
        x["fragile_sl"] = bool(x["chrF_sl"] < 40 or not 0.5 <= lr_sl <= 2)
        x["fragile_hu"] = bool(x["chrF_hu"] < 40 or not 0.5 <= lr_hu <= 2)
        x["fragile"] = x["fragile_sl"] or x["fragile_hu"]
        x["lid_sl"] = detect(det, a)[0]
        x["lid_hu"] = detect(det, b)[0]
    write_jsonl(DATA / "items.jsonl", items)
    qc = {}
    for lang in ("sl", "hu"):
        v = [x[f"chrF_{lang}"] for x in items]
        qc[lang] = {"median_chrF": statistics.median(v), "mean": sum(v) / len(v), "n_fragile":
                    sum(x[f"fragile_{lang}"] for x in items), "gate_median_ge_60": statistics.median(v) >= 60,
                    "lingua_ok_share": sum(x[f"lid_{lang}"] == lang for x in items) / len(items),
                    "lingua_fail_ids": [x["item_id"] for x in items if x[f"lid_{lang}"] != lang]}
    qc["n_items"] = len(items)
    qc["by_kind"] = dict(Counter(x["kind"] for x in items))
    qc["items_sha256"] = sha256_file(DATA / "items.jsonl")
    dump(RESULTS / "mt_qc.json", qc)
    logger.info(f"MT QC {json.dumps({k: v for k, v in qc.items() if k != 'lingua_fail_ids'}, default=str)[:600]}")


def mode_aux(nllb: NLLB200) -> None:
    # DEV: 60 exp9 P300 items (EN_BT present?) - SCREEN evidence only, used ONLY for the lambda choice
    p300 = read_jsonl(E9 / "data/probe_P300.jsonl")
    src = "exp9_P300"
    if not p300:
        p300 = read_jsonl(E8 / "data/probe_P200.jsonl")
        src = "exp8_P200 (fallback)"
    p300 = sorted(p300, key=lambda r: sha1_int(str(r["item_id"]) + str(SEED)))[:60]
    have_bt = all(r.get("en_bt") for r in p300)
    if not have_bt:
        bts = nllb.translate([r["sl_mt"] for r in p300], "slv_Latn", "eng_Latn")
        for r, b in zip(p300, bts):
            r["en_bt"] = b
    dev = [{"item_id": f"dev:{r['item_id']}", "kind": "harmful", "source": src, "EN_orig": r["en_orig"],
            "SL_MT": r.get("sl_mt"), "EN_BT": r["en_bt"], "HU_MT": None} for r in p300]
    write_jsonl(DATA / "dev_items.jsonl", dev)
    # KL stems
    st = read_jsonl(E8 / "data/harmless_dev32.jsonl")[:32]
    sl = nllb.translate([r["en"] for r in st], "eng_Latn", "slv_Latn")
    write_jsonl(DATA / "kl_stems.jsonl", [{"item_id": r["item_id"], "en": r["en"], "sl": s} for r, s in zip(st, sl)])
    # suffix QA
    qa = []
    for i, d in (("sl", SUFFIX["sl"]), ("hu", SUFFIX["hu"])):
        for o, s in d.items():
            qa.append({"in": i, "out": o, "suffix": s, "set": "primary"})
    for i, d in SUFFIX_BACKUP.items():
        if i == "en":
            continue
        for o, s in d.items():
            qa.append({"in": i, "out": o, "suffix": s, "set": "backup"})
    for lang in ("sl", "hu"):
        sub = [q for q in qa if q["in"] == lang]
        bt = nllb.translate([q["suffix"] for q in sub], {"sl": "slv_Latn", "hu": "hun_Latn"}[lang], "eng_Latn")
        for q, b in zip(sub, bt):
            q["back_translation"] = b
    dump(RESULTS / "suffix_qa.json", {"dev_source": src, "dev_had_en_bt": have_bt, "suffix_backtranslation": qa})
    logger.info(f"suffix QA: {[(q['in'], q['out'], q['back_translation']) for q in qa]}")


def mode_ttj(nllb: NLLB200, models: list[str], only_edited: bool) -> None:
    """translate-then-judge: NLLB response -> EN (greedy, bs 96) for SL/HU-output grid rows; cached by row key."""
    out = LABELS / "ttj_translations.jsonl"
    done = {r["key"] for r in read_jsonl(out)}
    for m in models:
        rows = [r for r in read_jsonl(GENS / f"{m}.jsonl") if r["out_lang"] in ("sl", "hu") and r["key"] not in done
                and r["cond"] in ("edit", "ext") and (not only_edited or r["lambda"] > 0 or r["cond"] == "ext")]
        logger.info(f"TTJ {m}: {len(rows)} rows to translate")
        for lang in ("sl", "hu"):
            sub = [r for r in rows if r["out_lang"] == lang]
            for s in range(0, len(sub), 600):
                ch = sub[s:s + 600]
                tr = nllb.translate([r["response"] for r in ch], {"sl": "slv_Latn", "hu": "hun_Latn"}[lang],
                                    "eng_Latn", num_beams=1, bs=128)
                append_jsonl(out, [{"key": r["key"], "src_lang": lang, "translation": t} for r, t in zip(ch, tr)])


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="items,aux")
    ap.add_argument("--models", default="gemma_it")
    ap.add_argument("--only_edited", action="store_true")
    args = ap.parse_args()
    setup_logging("build_items")
    torch.cuda.set_per_process_memory_fraction(0.45)
    nllb = NLLB200()
    if "items" in args.mode:
        mode_items(nllb)
    if "aux" in args.mode:
        mode_aux(nllb)
    if "ttj" in args.mode:
        mode_ttj(nllb, args.models.split(","), args.only_edited)


if __name__ == "__main__":
    main()
