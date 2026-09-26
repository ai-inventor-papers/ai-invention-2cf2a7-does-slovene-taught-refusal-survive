#!/usr/bin/env python3
"""R-JUDGE arm, translation half: NLLB-200-distilled-1.3B (fp16, beam 4, sentence split; exp11 build_items.py settings)
translates SL (and HU) responses of the TTJ frame to English, plus the MT-noise control (600 EN_BT responses EN->SL->EN).
Outputs work/ttj_translations.jsonl (append-only, resumable): {key, kind: 'ttj'|'rt', src_lang, text_en, text_sl?}.
"""
from __future__ import annotations

import json
import re
import resource
import sys
import time

import numpy as np
import pandas as pd
import torch
from loguru import logger

from common import SEED, WORK, setup_logger

NLLB = "facebook/nllb-200-distilled-1.3B"
CODE = {"sl": "slv_Latn", "hu": "hun_Latn", "en": "eng_Latn"}
OUT = WORK / "ttj_translations.jsonl"


def split_segments(text: str) -> list[tuple[int, str]]:  # verbatim logic of exp11 src/build_items.py
    segs = []
    for pi, para in enumerate(text.split("\n")):
        if not para.strip():
            segs.append((pi, ""))
            continue
        for s in re.split(r"(?<=[.!?])\s+(?=[\"'“A-ZČŠŽÁÉÍÓÖŐÚÜŰ0-9(])", para.strip()):
            if s.strip():
                segs.append((pi, s.strip()))
    return segs


def join_segments(segs, outs) -> str:
    paras: dict[int, list[str]] = {}
    for (pi, _), o in zip(segs, outs):
        paras.setdefault(pi, []).append(o)
    return "\n".join(" ".join(x for x in paras[k] if x) for k in sorted(paras))


class NLLB200:
    def __init__(self):
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        self.tok = AutoTokenizer.from_pretrained(NLLB)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(NLLB, torch_dtype=torch.float16).cuda().eval()

    @torch.inference_mode()
    def _gen(self, sents, src, tgt, bs=96, num_beams=4):
        self.tok.src_lang = src
        order = sorted(range(len(sents)), key=lambda i: -len(sents[i]))
        out = [""] * len(sents)
        i = 0
        while i < len(order):
            idx = order[i:i + bs]
            try:
                enc = self.tok([sents[j] for j in idx], return_tensors="pt", padding=True, truncation=True,
                               max_length=256).to("cuda")
                gen = self.model.generate(**enc, num_beams=num_beams, max_new_tokens=int(enc.input_ids.shape[1] * 1.6 + 16),
                                          forced_bos_token_id=self.tok.convert_tokens_to_ids(tgt))
                for j, t in zip(idx, self.tok.batch_decode(gen, skip_special_tokens=True)):
                    out[j] = t.strip()
                i += bs
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                bs = max(1, bs // 2)
                logger.warning(f"NLLB OOM -> bs {bs}")
        return out

    def translate(self, texts, src, tgt):
        t0 = time.time()
        segs = [split_segments(x or "") for x in texts]
        flat = [s for sg in segs for _, s in sg if s]
        tr = self._gen(flat, src, tgt) if flat else []
        it = iter(tr)
        res = [join_segments(sg, [next(it) if s else "" for _, s in sg]) for sg in segs]
        logger.info(f"NLLB {src}->{tgt}: {len(texts)} texts / {len(flat)} segments in {time.time() - t0:.0f}s")
        return res


def ttj_frame(df: pd.DataFrame) -> pd.DataFrame:
    """P1 decisive curves (exp9 orig+lambda harmful, exp11 FINAL curve) + exp10 op points: every non-EN row."""
    m = (((df.source == "exp9") & df.curve.isin(["orig", "lambda"]) & (df.kind == "harmful"))
         | ((df.source == "exp11") & (df.priority == 1)))
    return df[m & (df.lang != "en")]


@logger.catch(reraise=True)
def main():
    setup_logger("nllb_ttj")
    resource.setrlimit(resource.RLIMIT_AS, (60 * 1024 ** 3, 60 * 1024 ** 3))
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    df = pd.read_parquet(WORK / "frame.parquet")
    done = set()
    if OUT.exists():
        for line in OUT.read_text().splitlines():
            r = json.loads(line)
            done.add((r["key"], r["kind"]))
    fr = ttj_frame(df)
    # order: exp9, exp11 first (decisive), then exp10, exp8
    fr = fr.assign(_o=fr.source.map({"exp9": 0, "exp11": 1, "exp10": 2, "exp8": 3}))
    try:  # bracket-step rows (the ones the TTJ judge pass uses, AM1) first
        from label_passes import ttj_rows
        need = set(ttj_rows(df).key)
        fr = fr.assign(_o=np.where(fr.key.isin(need), fr._o, fr._o + 10))
    except (FileNotFoundError, KeyError, ImportError) as e:
        logger.warning(f"bracket ordering unavailable: {e}")
    fr = fr.sort_values(["_o", "key"])
    rt_pool = df[(df.arm == "en_bt") & (((df.source == "exp9") & df.curve.isin(["orig", "lambda"]) & (df.kind == "harmful"))
                                        | ((df.source == "exp11") & (df.priority == 1)))]
    rt = rt_pool.sample(n=600, random_state=SEED)
    jobs = [("ttj", r.key, r.lang, r.response) for r in fr.itertuples() if (r.key, "ttj") not in done]
    jobs_rt = [("rt", r.key, "en", r.response) for r in rt.itertuples() if (r.key, "rt") not in done]
    if limit:
        jobs, jobs_rt = jobs[:limit], jobs_rt[:max(1, limit // 5)]
    logger.info(f"TTJ frame {len(fr)} rows ({len(jobs)} to do); round-trip {len(jobs_rt)} to do")
    mt = NLLB200()
    # round trip first (small) so the MT-noise floor exists early
    CH = 400
    for i in range(0, len(jobs_rt), CH):
        ch = jobs_rt[i:i + CH]
        sl = mt.translate([c[3] for c in ch], CODE["en"], CODE["sl"])
        en = mt.translate(sl, CODE["sl"], CODE["en"])
        with OUT.open("a") as f:
            for c, s, e in zip(ch, sl, en):
                f.write(json.dumps({"key": c[1], "kind": "rt", "src_lang": "en", "text_sl": s, "text_en": e}) + "\n")
    for lang in ("sl", "hu"):
        jl = [j for j in jobs if j[2] == lang]
        for i in range(0, len(jl), CH):
            ch = jl[i:i + CH]
            en = mt.translate([c[3] for c in ch], CODE[lang], CODE["en"])
            with OUT.open("a") as f:
                for c, e in zip(ch, en):
                    f.write(json.dumps({"key": c[1], "kind": "ttj", "src_lang": lang, "text_en": e}) + "\n")
            logger.info(f"{lang}: {min(i + CH, len(jl))}/{len(jl)}")
    logger.info("NLLB done")


if __name__ == "__main__":
    main()
