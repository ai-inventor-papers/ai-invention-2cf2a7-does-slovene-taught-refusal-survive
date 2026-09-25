#!/usr/bin/env python3
"""Print a chunk of the BLIND adjudication file (aid, prompt, response only) for the author-model adjudicator.
Usage: adj_show.py MODEL START N. Labels are appended by the adjudicator to adjudication/labels.jsonl as
{"aid", "harmful": yes|no, "cls4": explicit_refusal|deflection|degraded_non_answer|compliance, "p1": REFUSE|PARTIAL|COMPLY}."""
import json
import sys
from pathlib import Path

ADJ = Path(__file__).resolve().parent.parent / "adjudication"
rows = [json.loads(line) for line in (ADJ / f"blind_{sys.argv[1]}.jsonl").open()]
s, n = int(sys.argv[2]), int(sys.argv[3])
for r in rows[s:s + n]:
    p = r["prompt"] if len(r["prompt"]) <= 700 else r["prompt"][:350] + " [...] " + r["prompt"][-350:]
    print(f"### {r['aid']}\nPROMPT: {p}\nRESPONSE: {r['response']}\n")
