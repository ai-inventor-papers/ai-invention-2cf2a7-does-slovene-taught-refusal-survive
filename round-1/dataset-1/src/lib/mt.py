"""Local MT (fallback for the unavailable OpenRouter gemini/gpt MT): forward EN->SL with facebook/nllb-200-distilled-1.3B
(Meta), back-translation SL->EN with Helsinki-NLP/opus-mt-tc-big-zls-en (Marian/OPUS; a different model family, so the
round trip is not self-consistent), chrF2 (sacrebleu) of back-translation vs original. Texts are split into sentences
(NLLB is sentence-level) and re-joined; paragraph breaks are preserved."""
import re
import time

import torch
from loguru import logger
from sacrebleu.metrics import CHRF

FWD = "facebook/nllb-200-distilled-1.3B"
BWD = "Helsinki-NLP/opus-mt-tc-big-zls-en"
_chrf = CHRF()


def chrf(hyp: str, ref: str) -> float:
    return round(_chrf.sentence_score(hyp, [ref]).score, 2)


def split_segments(text: str) -> list[tuple[int, str]]:
    segs = []
    for pi, para in enumerate(text.split("\n")):
        if not para.strip():
            segs.append((pi, ""))
            continue
        for s in re.split(r"(?<=[.!?])\s+(?=[\"'“A-ZČŠŽ0-9(])", para.strip()):
            if s.strip():
                segs.append((pi, s.strip()))
    return segs


def join_segments(segs: list[tuple[int, str]], outs: list[str]) -> str:
    paras: dict[int, list[str]] = {}
    for (pi, _), o in zip(segs, outs):
        paras.setdefault(pi, []).append(o)
    return "\n".join(" ".join(x for x in paras[k] if x) for k in sorted(paras))


class Translator:
    def __init__(self, direction: str):
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        self.direction = direction
        repo = FWD if direction == "en-sl" else BWD
        kw = {"src_lang": "eng_Latn"} if direction == "en-sl" else {}
        self.tok = AutoTokenizer.from_pretrained(repo, **kw)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(repo, torch_dtype=torch.float16).cuda().eval()
        self.repo = repo
        logger.info(f"loaded {repo}")

    @torch.inference_mode()
    def _gen(self, sents: list[str], num_beams: int, bs: int, rep_pen: float) -> list[str]:
        order = sorted(range(len(sents)), key=lambda i: -len(sents[i]))
        out = [""] * len(sents)
        i = 0
        while i < len(order):
            idx = order[i:i + bs]
            batch = [sents[j] for j in idx]
            try:
                enc = self.tok(batch, return_tensors="pt", padding=True, truncation=True, max_length=400).to("cuda")
                kw = dict(num_beams=num_beams, max_new_tokens=int(enc.input_ids.shape[1] * 1.6 + 16),
                          repetition_penalty=rep_pen)
                if self.direction == "en-sl":
                    kw["forced_bos_token_id"] = self.tok.convert_tokens_to_ids("slv_Latn")
                gen = self.model.generate(**enc, **kw)
                for j, t in zip(idx, self.tok.batch_decode(gen, skip_special_tokens=True)):
                    out[j] = t.strip()
                i += bs
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                bs = max(1, bs // 2)
                logger.warning(f"OOM -> bs {bs}")
        return out

    def translate(self, texts: list[str], num_beams: int = 4, bs: int = 48, rep_pen: float = 1.0) -> list[str]:
        t = time.time()
        segs = [split_segments(x) for x in texts]
        flat = [s for sg in segs for _, s in sg if s]
        tr = self._gen(flat, num_beams, bs, rep_pen) if flat else []
        it = iter(tr)
        res = [join_segments(sg, [next(it) if s else "" for _, s in sg]) for sg in segs]
        logger.info(f"{self.repo}: {len(texts)} texts / {len(flat)} segments in {time.time() - t:.0f}s")
        return res

    def unload(self) -> None:
        del self.model
        torch.cuda.empty_cache()


def round_trip(texts_en: list[str], retry_below: float = 40.0) -> list[dict]:
    """EN->SL (beam 4), SL->EN, chrF; items < retry_below get ONE forward retry (beam 8, repetition_penalty 1.15, whole
    text unsplit); the retry is kept only if its round-trip chrF is higher."""
    fwd = Translator("en-sl")
    sl = fwd.translate(texts_en)
    bwd = Translator("sl-en")
    bt = bwd.translate(sl)
    recs = [{"prompt_sl": s, "prompt_bt": b, "bt_chrf": chrf(b, e), "mt_retry": False} for e, s, b in zip(texts_en, sl, bt)]
    low = [i for i, r in enumerate(recs) if r["bt_chrf"] < retry_below]
    logger.info(f"round trip: {len(low)}/{len(recs)} below chrF {retry_below} -> retry")
    if low:
        bwd.model.cpu()
        fwd.model.cuda()
        sl2 = [fwd._gen([texts_en[i]], 8, 1, 1.15)[0] for i in low]
        fwd.model.cpu()
        bwd.model.cuda()
        bt2 = bwd.translate(sl2)
        for i, s2, b2 in zip(low, sl2, bt2):
            c2 = chrf(b2, texts_en[i])
            recs[i]["mt_retry"] = True
            recs[i]["bt_chrf_first"] = recs[i]["bt_chrf"]
            if c2 > recs[i]["bt_chrf"]:
                recs[i].update({"prompt_sl": s2, "prompt_bt": b2, "bt_chrf": c2})
    fwd.unload(); bwd.unload()
    for r in recs:
        r["mt_empty"] = not r["prompt_sl"].strip()
        r["mt_by"] = f"{FWD} (fwd) / {BWD} (bt)"
    return recs
