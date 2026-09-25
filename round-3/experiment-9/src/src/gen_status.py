#!/usr/bin/env python3
"""Generation progress and ETA from results/{model}/gen_timing.json + gens.jsonl."""
import json, sys
from pathlib import Path
WS = Path(__file__).resolve().parent.parent
for m in ("gemma_it", "gams3_it"):
    p = WS / "results" / m
    t = json.loads((p / "gen_timing.json").read_text()) if (p / "gen_timing.json").exists() else {}
    n = sum(1 for _ in (p / "gens.jsonl").open()) if (p / "gens.jsonl").exists() else 0
    rate = (sum(v["n"] for v in t.values()) / max(1e-9, sum(v["s"] for v in t.values()))) if t else 0
    print(f"{m}: {n} rows, {len(t)} steps done, {rate:.1f} items/s, "
          f"{sum(v['s'] for v in t.values())/60:.1f} min spent")
