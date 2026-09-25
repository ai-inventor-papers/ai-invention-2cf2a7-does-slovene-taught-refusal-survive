#!/usr/bin/env python3
"""NLLB-200-distilled-1.3B sentence-split MT (fp16, GPU) + chrF + lingua language id.

PROVENANCE: split_segments / join_segments / NLLB200 adapted from iter_4 exp14 src/build_items.py. Change: the plan's
generation cap max_new_tokens = int(2 * len_in) + 20 (exp14 used 1.6x+16) and the lingua detector restricted to
EN/SL/HU/HR/SR/BS. Sentence splitting is MANDATORY (exp13's single-call NLLB dropped sentences, e.g. i4_7cebf8a68dce).

CLI (TTJ, S7):  python translate.py --mode ttj   translates every non-English response in gens/*.jsonl to English
                                                  (greedy, sentence split) -> labels/ttj.jsonl (resumable by row key)
                python translate.py --mode roundtrip  300 EN responses -> SL -> EN (TTJ round-trip control)
"""
from __future__ import annotations

import argparse
import re
import time

import torch
from loguru import logger

from common import GENS, LABELS, RESULTS, append_jsonl, dump, read_jsonl, setup_logging, sha1_int

NLLB = "facebook/nllb-200-distilled-1.3B"
_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[\"'“(0-9A-ZČŠŽĆĐÁÉÍÓÖŐÚÜŰ*#\-])")


def split_segments(text: str) -> list[tuple[int, str]]:
    segs = []
    for pi, para in enumerate((text or "").split("\n")):
        if not para.strip():
            segs.append((pi, ""))
            continue
        for s in _SPLIT.split(para.strip()):
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
    def _gen(self, sents: list[str], src: str, tgt: str, bs: int = 64, num_beams: int = 4,
             no_repeat: int = 0) -> list[str]:
        self.tok.src_lang = src
        order = sorted(range(len(sents)), key=lambda i: -len(sents[i]))
        out = [""] * len(sents)
        i = 0
        while i < len(order):
            idx = order[i:i + bs]
            try:
                enc = self.tok([sents[j] for j in idx], return_tensors="pt", padding=True, truncation=True,
                               max_length=400).to("cuda")
                kw = {"no_repeat_ngram_size": no_repeat} if no_repeat else {}
                gen = self.model.generate(**enc, num_beams=num_beams,
                                          max_new_tokens=int(2 * enc.input_ids.shape[1]) + 20,
                                          forced_bos_token_id=self.tok.convert_tokens_to_ids(tgt), **kw)
                for j, t in zip(idx, self.tok.batch_decode(gen, skip_special_tokens=True)):
                    out[j] = t.strip()
                i += bs
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                bs = max(1, bs // 2)
                logger.warning(f"NLLB OOM -> bs {bs}")
        return out

    def translate(self, texts: list[str], src: str, tgt: str, num_beams: int = 4, bs: int = 64,
                  no_repeat: int = 0) -> list[str]:
        t0 = time.time()
        segs = [split_segments(x) for x in texts]
        flat = [s for sg in segs for _, s in sg if s]
        tr = self._gen(flat, src, tgt, bs=bs, num_beams=num_beams, no_repeat=no_repeat) if flat else []
        it = iter(tr)
        res = [join_segments(sg, [next(it) if s else "" for _, s in sg]) for sg in segs]
        logger.info(f"NLLB {src}->{tgt}: {len(texts)} texts / {len(flat)} segments in {time.time() - t0:.0f}s")
        return res


def chrf(hyp: str, ref: str) -> float:
    from sacrebleu.metrics import CHRF
    return round(CHRF().sentence_score(hyp, [ref]).score, 2)


def n_sentences(t: str) -> int:
    return sum(1 for _, s in split_segments(t) if s)


_DET = None
ISO = {"ENGLISH": "en", "SLOVENE": "sl", "HUNGARIAN": "hu", "CROATIAN": "hr", "SERBIAN": "sr", "BOSNIAN": "bs"}


def detect(text: str) -> tuple[str, float]:
    """lingua restricted to EN/SL/HU/HR/SR/BS (plan S1). < 3 words -> 'und'."""
    global _DET
    if _DET is None:
        from lingua import Language, LanguageDetectorBuilder
        _DET = LanguageDetectorBuilder.from_languages(Language.ENGLISH, Language.SLOVENE, Language.HUNGARIAN,
                                                      Language.CROATIAN, Language.SERBIAN, Language.BOSNIAN).build()
    t = (text or "").strip()
    if len(t.split()) < 3:
        return "und", 0.0
    vals = _DET.compute_language_confidence_values(t)
    if not vals:
        return "und", 0.0
    return ISO.get(vals[0].language.name, "other"), round(float(vals[0].value), 3)


def ttj_source(r: dict) -> str:
    """NLLB source language for a reply: lingua id when it is SL/HU (HR/SR/BS ids of Slovene-model output are treated
    as Slovene), 'en' = keep the original text, otherwise fall back to the target output language."""
    lid = r.get("lid")
    if lid in ("sl", "hr", "sr", "bs"):
        return "sl"
    if lid in ("hu", "en"):
        return lid
    return r["out_lang"]


def mode_ttj(nllb: NLLB200) -> int:
    """S7: every harmful response whose out_lang is sl/hu or whose lid != en -> English (greedy, sentence split)."""
    out = LABELS / "ttj.jsonl"
    done = {r["key"] for r in read_jsonl(out)}
    n = 0
    for f in sorted(GENS.glob("*.jsonl")):
        if f.name.startswith("dev_"):
            continue
        rows = [r for r in read_jsonl(f) if r["key"] not in done
                and (r["kind"] == "harmful" or (r["kind"] == "twin" and r["dose_tag"] == "zero"))
                and (r["out_lang"] in ("sl", "hu") or r.get("lid") != "en")]
        keep = [r for r in rows if ttj_source(r) == "en"]
        append_jsonl(out, [{"key": r["key"], "src_lang": "en", "response_en": r["response"]} for r in keep])
        n += len(keep)
        for lang in ("sl", "hu"):
            sub = [r for r in rows if ttj_source(r) == lang]
            for s in range(0, len(sub), 800):
                ch = sub[s:s + 800]
                tr = nllb.translate([r["response"] for r in ch], {"sl": "slv_Latn", "hu": "hun_Latn"}[lang],
                                    "eng_Latn", num_beams=1, bs=128)
                append_jsonl(out, [{"key": r["key"], "src_lang": lang, "response_en": t} for r, t in zip(ch, tr)],
                             fsync=True)
                n += len(ch)
        logger.info(f"TTJ {f.name}: {len(rows)} rows")
    return n


def mode_roundtrip(nllb: NLLB200) -> None:
    """Round-trip control: 300 hash-chosen EN-output harmful responses -> SL -> EN; chrF saved; the U flip rate is
    computed by score_local.py (readout sr_local on the round-tripped text)."""
    rows = []
    for f in sorted(GENS.glob("*.jsonl")):
        if not f.name.startswith("dev_"):
            rows += [r for r in read_jsonl(f) if r["kind"] == "harmful" and r["out_lang"] == "en"
                     and r.get("lid") == "en" and r["model"] in ("gemma_it", "gams3_it")]
    rows = sorted(rows, key=lambda r: sha1_int("iter5_rt|" + r["key"]))[:300]
    sl = nllb.translate([r["response"] for r in rows], "eng_Latn", "slv_Latn", num_beams=1, bs=128)
    en = nllb.translate(sl, "slv_Latn", "eng_Latn", num_beams=1, bs=128)
    recs = [{"key": r["key"], "response_rt_en": e, "chrF": chrf(e, r["response"])} for r, e in zip(rows, en)]
    from common import write_jsonl
    write_jsonl(LABELS / "roundtrip.jsonl", recs)
    import statistics
    dump(RESULTS / "roundtrip_mt.json", {"n": len(recs), "median_chrF": statistics.median([x["chrF"] for x in recs])
                                         if recs else None})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="ttj,roundtrip")
    a = ap.parse_args()
    setup_logging("translate")
    torch.cuda.set_per_process_memory_fraction(0.9)
    nllb = NLLB200()
    if "ttj" in a.mode:
        logger.info(f"TTJ translated {mode_ttj(nllb)} rows")
    if "roundtrip" in a.mode:
        mode_roundtrip(nllb)


if __name__ == "__main__":
    logger.catch(reraise=True)(main)()
