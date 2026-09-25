#!/usr/bin/env python3
"""fallback (a): re-probe the OpenRouter key every 15 min (one 1-token call, cheapest tier) and log the outcome to
results/key_probe.jsonl; exits when a probe succeeds or after --max probes."""
from __future__ import annotations

import argparse
import json
import time

from common import RESULTS, append_jsonl
import judge_paid

ap = argparse.ArgumentParser()
ap.add_argument("--max", type=int, default=14)
ap.add_argument("--every", type=int, default=900)
a = ap.parse_args()
for k in range(a.max):
    judge_paid._cache = {}
    r = judge_paid.run([{"tier": "flash_lite", "task": "gen", "req": f"Reply OK. probe {time.time()}", "meta": {}}])[0]
    ok = not r.get("err")
    append_jsonl(RESULTS / "key_probe.jsonl", [{"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "ok": ok,
                                                "err": (r.get("err") or "")[:200]}])
    if ok:
        break
    time.sleep(a.every)
