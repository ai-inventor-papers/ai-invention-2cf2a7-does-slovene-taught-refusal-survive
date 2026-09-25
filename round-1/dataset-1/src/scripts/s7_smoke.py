#!/usr/bin/env python3
"""5-call smoke test per model (real per-call cost recorded in ledger/prices.json)."""
import asyncio, json, sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.common import LABELS, PROMPTS, ROOT, WORK, setup_logging  # noqa: E402
from lib.judge import PRICE, Judge, run_many  # noqa: E402
setup_logging("s7_smoke")


async def main():
    c = pd.read_parquet(WORK / "calib_items.parquet").head(5)
    v1 = (PROMPTS / "hazard_label_v1.txt").read_text()
    j = Judge("A_smoke")
    res = {}
    for m in PRICE:
        jobs = [{"key": f"{m}|{k}", "model": m, "messages": [{"role": "system", "content": v1}, {"role": "user", "content": "PROMPT:\n" + p}], "max_tokens": 60} for k, p in zip(c.item_id, c.prompt)]
        before = j.ledger.total
        out = await run_many(j, jobs, LABELS / "smoke.jsonl")
        res[m] = {"price_per_M_in_out": PRICE[m], "mean_cost_per_hazard_call": round((j.ledger.total - before) / 5, 6),
                  "sample": [out[x["key"]]["parsed"] for x in jobs if x["key"] in out][:2], "gold": c.gold.tolist()}
    (ROOT / "ledger/prices.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))

asyncio.run(main())
