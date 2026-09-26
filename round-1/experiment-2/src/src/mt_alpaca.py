#!/usr/bin/env python3
"""MT of the alpaca harmless sample EN->SL with gemini-2.5-flash (T=0), back-translation SL->EN, chrF QC.
Resumable from the OpenRouter ledger; MT cap $1. Assigns CONSTRUCT-harmless / SCORE-harmless / INDUCTION roles."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import aiohttp
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ledger import Client, done_keys  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add(ROOT / "logs/mt_alpaca.log", rotation="30 MB", level="DEBUG")

FWD = "Translate the following text into natural Slovene. Output only the translation.\n\n{t}"
BWD = "Translate the following text into natural English. Output only the translation.\n\n{t}"


async def run_all() -> None:
    items = [json.loads(l) for l in (ROOT / "data/alpaca_sample_pre_mt.jsonl").read_text().splitlines()]
    cli = Client("mt_alpaca", cap_usd=1.0, concurrency=16)
    async with aiohttp.ClientSession() as s:
        prev = done_keys("mt_alpaca")
        todo = [r for r in items if f"fwd:{r['hid']}" not in prev]
        logger.info(f"forward MT todo {len(todo)}")
        await asyncio.gather(*[cli.call(s, f"fwd:{r['hid']}", [{"role": "user", "content": FWD.format(t=r["en"])}])
                               for r in todo])
        prev = done_keys("mt_alpaca")
        todo = [r for r in items if f"fwd:{r['hid']}" in prev and f"bwd:{r['hid']}" not in prev]
        logger.info(f"back MT todo {len(todo)}")
        await asyncio.gather(*[cli.call(s, f"bwd:{r['hid']}", [{"role": "user", "content": BWD.format(
            t=prev[f"fwd:{r['hid']}"]["content"].strip())}]) for r in todo])
    logger.info(f"MT spend so far ${cli.spent_purpose:.4f}")


def finalize() -> None:
    from sacrebleu.metrics import CHRF
    chrf = CHRF()
    items = [json.loads(l) for l in (ROOT / "data/alpaca_sample_pre_mt.jsonl").read_text().splitlines()]
    prev = done_keys("mt_alpaca")
    out, valid = [], []
    for r in items:  # already sorted by sha1(instruction)
        f, b = prev.get(f"fwd:{r['hid']}"), prev.get(f"bwd:{r['hid']}")
        if not f or not b:
            continue
        sl, bt = f["content"].strip(), b["content"].strip()
        score = chrf.sentence_score(bt, [r["en"]]).score
        rec = {**r, "sl": sl, "backtrans_en": bt, "chrF": round(score, 2), "mt_source": "google/gemini-2.5-flash T=0"}
        rec["valid"] = bool(score >= 35 and sl)
        out.append(rec)
    val = [r for r in out if r["valid"]]
    assert len(val) >= 400, f"only {len(val)} valid MT items"
    for i, r in enumerate(out):
        r["role"] = "RESERVE"
    for i, r in enumerate(val[:400]):
        r["role"] = "CONSTRUCT" if i < 200 else "SCORE"
    score_items = [r for r in val[200:400]]
    for r in score_items[:100]:  # lowest-sha1 100 of SCORE-harmless
        r["induction"] = True
    with (ROOT / "data/alpaca_harmless.jsonl").open("w") as fo:
        for r in out:
            r.setdefault("induction", False)
            fo.write(json.dumps(r, ensure_ascii=False) + "\n")
    import statistics
    logger.info(f"finalized {len(out)} MT items; valid {len(val)}; median chrF {statistics.median(x['chrF'] for x in out):.1f}; "
                f"replaced (invalid) {sum(not r['valid'] for r in out)}")


if __name__ == "__main__":
    if "--finalize" not in sys.argv:
        asyncio.run(run_all())
    else:
        finalize()
