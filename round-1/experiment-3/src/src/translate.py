#!/usr/bin/env python3
"""EN->SL machine translation with facebook/nllb-200-distilled-1.3B (local; replaces the planned gemini-2.5-flash
translation because the OpenRouter key hit its DAILY limit, HTTP 403, on 2026-09-23).
(1) alpaca harmless set (200) -> data/harmless.jsonl prompt_sl
(2) SCORE-400 EN prompts -> data/score400_mt_sl.jsonl (translation-matched SL robustness cell 'slmt')."""
from __future__ import annotations

import json

import torch
from loguru import logger
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from common import DATA, read_jsonl, setup_logging, write_jsonl

REPO = "facebook/nllb-200-distilled-1.3B"


def translate(texts: list[str], tok, model, bs: int = 16) -> list[str]:
    out = [None] * len(texts)
    order = sorted(range(len(texts)), key=lambda i: -len(texts[i]))
    tgt = tok.convert_tokens_to_ids("slv_Latn")
    for k in range(0, len(order), bs):
        idx = order[k:k + bs]
        enc = tok([texts[i] for i in idx], return_tensors="pt", padding=True, truncation=True, max_length=400).to("cuda")
        with torch.no_grad():
            gen = model.generate(**enc, forced_bos_token_id=tgt, max_new_tokens=512, num_beams=4)
        for i, t in zip(idx, tok.batch_decode(gen, skip_special_tokens=True)):
            out[i] = t
    return out


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("translate")
    tok = AutoTokenizer.from_pretrained(REPO, src_lang="eng_Latn")
    model = AutoModelForSeq2SeqLM.from_pretrained(REPO, torch_dtype=torch.float16).cuda().eval()
    hp = DATA / "harmless.jsonl"
    rows = read_jsonl(hp)
    todo = [r for r in rows if not r.get("prompt_sl")]
    if todo:
        tr = translate([r["prompt_en"] for r in todo], tok, model)
        for r, t in zip(todo, tr):
            r["prompt_sl"] = t
            r["sl_source"] = f"MT:{REPO}"
        write_jsonl(hp, rows)
    logger.info(f"harmless translated; e.g. {rows[0]['prompt_en']!r} -> {rows[0]['prompt_sl']!r}")
    mp = DATA / "score400_mt_sl.jsonl"
    if not mp.exists():
        s4 = read_jsonl(DATA / "score400.jsonl")
        # translate sentence-by-sentence-agnostic whole prompt (NLLB max 400 source tokens; longer ones truncated, flagged)
        tr = translate([p["prompt_en"].strip().strip('"') for p in s4], tok, model, bs=8)
        n_trunc = sum(len(tok(p["prompt_en"])["input_ids"]) > 400 for p in s4)
        write_jsonl(mp, [{"pair_id": p["pair_id"], "prompt_slmt": t} for p, t in zip(s4, tr)])
        logger.info(f"SCORE-400 MT done ({n_trunc} source prompts truncated at 400 tokens); e.g. {tr[0][:200]!r}")
    (DATA / "translation_meta.json").write_text(json.dumps({"model": REPO, "beams": 4, "max_src_tokens": 400,
                                                             "reason": "OpenRouter daily limit (HTTP 403)"}, indent=1))


if __name__ == "__main__":
    main()
