#!/usr/bin/env python3
"""F7 fallback MT (OpenRouter key hit its DAILY limit, 403 on 2026-09-23 14:36): EN->SL with a local NLLB-200
checkpoint (facebook/nllb-200-distilled-1.3B, already in the shared cache; the plan named the 600M variant),
greedy (num_beams=1), then SL->EN back-translation with the same model and chrF QC (< 35 -> replaced from reserve).
NOT GaMS/Gemma (would bias the model comparison). Assigns CONSTRUCT-harmless / SCORE-harmless / INDUCTION roles."""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

import torch
from loguru import logger
from sacrebleu.metrics import CHRF
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
REPO = "facebook/nllb-200-distilled-1.3B"
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add(ROOT / "logs/mt_nllb.log", rotation="30 MB", level="DEBUG")


@torch.inference_mode()
def translate(model, tok, texts: list[str], src: str, tgt: str, bs: int = 32) -> list[str]:
    tok.src_lang = src
    out = []
    for i in range(0, len(texts), bs):
        enc = tok(texts[i:i + bs], return_tensors="pt", padding=True, truncation=True, max_length=256).to("cuda")
        g = model.generate(**enc, forced_bos_token_id=tok.convert_tokens_to_ids(tgt), num_beams=1, do_sample=False,
                           max_new_tokens=256)
        out += tok.batch_decode(g, skip_special_tokens=True)
    return out


def main() -> None:
    items = [json.loads(l) for l in (ROOT / "data/alpaca_sample_pre_mt.jsonl").read_text().splitlines()]
    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(REPO)
    model = AutoModelForSeq2SeqLM.from_pretrained(REPO, dtype=torch.float16).cuda().eval()
    sl = translate(model, tok, [r["en"] for r in items], "eng_Latn", "slv_Latn")
    bt = translate(model, tok, sl, "slv_Latn", "eng_Latn")
    chrf = CHRF()
    out = []
    for r, s, b in zip(items, sl, bt):
        sc = chrf.sentence_score(b, [r["en"]]).score
        out.append({**r, "sl": s.strip(), "backtrans_en": b.strip(), "chrF": round(sc, 2),
                    "mt_source": f"{REPO} greedy (F7 fallback; OpenRouter daily limit)", "valid": bool(sc >= 35 and s.strip())})
    val = [r for r in out if r["valid"]]
    assert len(val) >= 400, f"only {len(val)} valid"
    for r in out:
        r["role"], r["induction"] = "RESERVE", False
    for i, r in enumerate(val[:400]):  # items are sorted by sha1(instruction)
        r["role"] = "CONSTRUCT" if i < 200 else "SCORE"
    for r in val[200:300]:
        r["induction"] = True
    with (ROOT / "data/alpaca_harmless.jsonl").open("w") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    logger.info(f"MT done in {time.time()-t0:.0f}s: {len(out)} items, valid {len(val)}, median chrF "
                f"{statistics.median(r['chrF'] for r in out):.1f}, invalid {sum(not r['valid'] for r in out)}")
    for r in out[:5]:
        logger.info(f"  {r['en'][:80]} || {r['sl'][:80]} || chrF {r['chrF']}")


if __name__ == "__main__":
    main()
