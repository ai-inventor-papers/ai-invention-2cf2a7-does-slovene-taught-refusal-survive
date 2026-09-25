#!/usr/bin/env python3
"""S0 OpenRouter steps (run after the key recovered from its 403 daily limit): harmless_alpaca[400:600] -> Slovene MT
and T/R/U pair-correspondence grades. Splits are NOT rebuilt (frozen in protocol.json)."""
import asyncio
import random
from collections import Counter

from common import DATA, SEED, SPLITS, read_jsonl, write_jsonl
from prep_data import build_harmless, grade_pairs, logger, translate_harmless

harmless = build_harmless()  # uses v2 MT prompt (see prep_data.translate_harmless)
mt = asyncio.run(translate_harmless(harmless))
write_jsonl(DATA / "harmless_sl_mt.jsonl", mt)
logger.info(f"harmless SL-MT: {len(mt)}/200")
s400 = read_jsonl(SPLITS / "score400.jsonl")
probe = read_jsonl(SPLITS / "trial_probe.jsonl")
ids = {p["pair_id"] for p in probe}
rng = random.Random(SEED)
extra = rng.sample([p for p in s400 if p["pair_id"] not in ids], 100)
grades = asyncio.run(grade_pairs(probe + extra))
for g in grades:
    g["set"] = "trial_probe" if g["pair_id"] in ids else "score400_random"
    g["grader"] = "google/gemini-2.5-flash"
write_jsonl(DATA / "pair_grades.jsonl", grades)
logger.info(f"pair grades: {Counter((g['set'], g['grade']) for g in grades)}")
