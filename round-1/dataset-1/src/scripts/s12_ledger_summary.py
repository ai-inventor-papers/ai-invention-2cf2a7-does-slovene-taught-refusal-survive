#!/usr/bin/env python3
"""Summarise ledger/ledger.jsonl (every OpenRouter call, cost from usage.cost) into ledger/summary.json."""
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rows = [json.loads(l) for l in (ROOT / "ledger/ledger.jsonl").open() if l.strip()]
by_step, by_model, by_group = defaultdict(float), defaultdict(float), defaultdict(float)
n_step = defaultdict(int)
for r in rows:
    by_step[r["step"]] += r["cost_usd"]; n_step[r["step"]] += 1
    by_model[r["model"]] += r["cost_usd"]; by_group[r["step"][0]] += r["cost_usd"]
env = json.loads((ROOT / "logs/env.json").read_text())
out = {"cap_usd": 9.50, "spent_usd": round(sum(by_step.values()), 4), "n_calls": len(rows),
       "sub_caps_planned_usd": {"A": 2.6, "D": 0.5, "B": 3.6, "C": 2.3},
       "spent_by_priority_group": {k: round(v, 4) for k, v in sorted(by_group.items())},
       "spent_by_step": {k: {"usd": round(v, 4), "calls": n_step[k]} for k, v in sorted(by_step.items())},
       "spent_by_model": {k: round(v, 4) for k, v in by_model.items()},
       "deviations": [
           "A exceeded its 2.6 sub-cap (2.78): the eval run started before a bug in the sub-cap check (per-step instead of per-group) was fixed; the fixed ledger then blocked the one remaining eval retry.",
           "B sub-cap raised 3.6 -> 4.3 mid-run (gemini dose batches cost ~2x the estimate); B spent 4.15.",
           "Plan failure scenario 7 triggered (> $8 before step C finished): HARD labelled GPT-EN + GPT-SL + TF-IDF (+Llama-Guard), GEM-EN skipped.",
           "H = taxonomy harmonisation of dose-row hazards with the eval labeller/prompt (not in the plan; see README), ~$0.28.",
           "Many gpt HARD batch retries (strict batch validation, fixed mid-run to lenient) wasted ~$0.8."],
       "key_status_at_module_start": env.get("openrouter_key"),
       "history": ("At module start (14:21 UTC) the shared key was exhausted; after a restart (15:13 UTC) it had $46.4 left "
                   "and every LLM step ran on the plan's OpenRouter models. No local-fallback LLM labels are in the deliverable.")}
(ROOT / "ledger/summary.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
