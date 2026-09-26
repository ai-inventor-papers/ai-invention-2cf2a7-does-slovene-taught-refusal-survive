#!/usr/bin/env python3
"""STEP 1c (GPU): NLLB-200-distilled-1.3B MT of the fresh Dolly harmless set.
EN -> slv_Latn (SL-MT), SL-MT -> eng_Latn (EN-BT), EN -> hun_Latn (HU-MT), HU-MT -> eng_Latn (HU-BT, chrF only).
Per-item chrF(back-translation vs EN); gate median >= 60; items with chrF < 40 flagged fragile (sensitivity).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
import torch  # noqa: E402
from sacrebleu.metrics import CHRF  # noqa: E402
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer  # noqa: E402

from common import DATA, read_jsonl, setup_logger, write_jsonl  # noqa: E402

logger = setup_logger("prep_mt")
REPO = "facebook/nllb-200-distilled-1.3B"


@torch.no_grad()
def translate(model, tok, texts: list[str], src: str, tgt: str, bs: int = 32) -> list[str]:
    tok.src_lang = src
    out = []
    for i in range(0, len(texts), bs):
        enc = tok(texts[i:i + bs], return_tensors="pt", padding=True, truncation=True, max_length=256).to(model.device)
        gen = model.generate(**enc, forced_bos_token_id=tok.convert_tokens_to_ids(tgt), num_beams=4, do_sample=False,
                             max_new_tokens=256)
        out += tok.batch_decode(gen, skip_special_tokens=True)
    return [o.strip() for o in out]


@logger.catch(reraise=True)
def main() -> None:
    t = time.time()
    rows = read_jsonl(DATA / "harmless" / "dolly_en.jsonl")
    tok = AutoTokenizer.from_pretrained(REPO)
    model = AutoModelForSeq2SeqLM.from_pretrained(REPO, dtype=torch.bfloat16).to("cuda").eval()
    en = [r["en"] for r in rows]
    sl = translate(model, tok, en, "eng_Latn", "slv_Latn")
    hu = translate(model, tok, en, "eng_Latn", "hun_Latn")
    en_bt = translate(model, tok, sl, "slv_Latn", "eng_Latn")
    hu_bt = translate(model, tok, hu, "hun_Latn", "eng_Latn")
    chrf = CHRF()
    out = []
    for r, s, h, b, hb in zip(rows, sl, hu, en_bt, hu_bt):
        cs = chrf.sentence_score(b, [r["en"]]).score
        ch = chrf.sentence_score(hb, [r["en"]]).score
        out.append({"id": r["id"], "category": r["category"], "spare": r["spare"], "en_orig": r["en"], "sl_mt": s,
                    "en_bt": b, "hu_mt": h, "hu_bt": hb, "chrf_sl": round(cs, 2), "chrf_hu": round(ch, 2),
                    "fragile_sl": cs < 40, "fragile_hu": ch < 40})
    write_jsonl(DATA / "harmless" / "harmless_mt.jsonl", out)
    main_rows = [o for o in out if not o["spare"]]
    rep = {"model": REPO, "decoding": "beam 4, greedy (no sampling), max 256 new tokens",
           "n": len(out), "median_chrf_sl_bt": float(np.median([o["chrf_sl"] for o in main_rows])),
           "median_chrf_hu_bt": float(np.median([o["chrf_hu"] for o in main_rows])),
           "n_fragile_sl": sum(o["fragile_sl"] for o in main_rows), "n_fragile_hu": sum(o["fragile_hu"] for o in main_rows),
           "seconds": round(time.time() - t, 1)}
    rep["gate_median_ge_60"] = rep["median_chrf_sl_bt"] >= 60 and rep["median_chrf_hu_bt"] >= 60
    (DATA / "harmless" / "mt_report.json").write_text(json.dumps(rep, indent=2))
    for o in main_rows[:3]:
        logger.info(f"EN={o['en_orig']!r}\n  SL={o['sl_mt']!r}\n  BT={o['en_bt']!r}\n  HU={o['hu_mt']!r}")
    logger.info(f"MT report: {rep}")


if __name__ == "__main__":
    main()
