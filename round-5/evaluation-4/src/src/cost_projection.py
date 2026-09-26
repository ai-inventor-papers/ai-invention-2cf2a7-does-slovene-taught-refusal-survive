#!/usr/bin/env python3
"""Step 0.6: live per-token prices from the OpenRouter /models endpoint -> results/cost_projection.json."""
import json, os, sys
from pathlib import Path
from openai import OpenAI
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, dump

WANT = ["google/gemini-2.5-flash", "google/gemini-2.5-flash-lite", "anthropic/claude-sonnet-4.5",
        "anthropic/claude-haiku-4.5", "openai/gpt-4.1", "openai/gpt-5-mini", "openai/gpt-4.1-mini",
        "deepseek/deepseek-chat-v3.1"]
cl = OpenAI(base_url=os.environ["OPENROUTER_BASE_URL"], api_key=os.environ["OPENROUTER_API_KEY"])
price = {}
for m in cl.models.list().data:
    if m.id in WANT:
        p = m.model_extra.get("pricing", {})
        price[m.id] = {"prompt": float(p["prompt"]), "completion": float(p["completion"])}


def c(m, i, o):
    return price[m]["prompt"] * i + price[m]["completion"] * o


pc = {"sr_flash_compact": c("google/gemini-2.5-flash", 1000, 25), "sr_flash_full": c("google/gemini-2.5-flash", 1000, 300),
      "sr_lite_compact": c("google/gemini-2.5-flash-lite", 1000, 25),
      "adj_haiku": c("anthropic/claude-haiku-4.5", 1500, 90), "adj_sonnet": c("anthropic/claude-sonnet-4.5", 1500, 90),
      "adj_gpt41": c("openai/gpt-4.1", 1400, 80), "adj_gpt5mini": c("openai/gpt-5-mini", 1400, 250),
      "adj_deepseek": c("deepseek/deepseek-chat-v3.1", 1400, 90),
      "p1_flash": c("google/gemini-2.5-flash", 300, 2), "p1_g41m": c("openai/gpt-4.1-mini", 300, 2)}
proj = {"prices_per_token": price, "per_call": pc,
        "token_rule": "chars/3.2 for SL/HU, chars/4 for EN; about 1000 input tokens per SR call including the rubric",
        "calls": {"SR_P-A": 1800, "SR_P-B": 4800, "SR_P-C": 5100, "SR_P-D": 1800, "adj_rows": 740, "p1_rows": 740}}
proj["projection_usd"] = {
    "pilot": 60 * (pc["adj_haiku"] + pc["adj_sonnet"] + pc["adj_gpt41"] + pc["adj_gpt5mini"])
    + 90 * (pc["sr_flash_full"] + pc["sr_flash_compact"] + pc["sr_lite_compact"]),
    "SR_PA_PB_compact": 6600 * pc["sr_flash_compact"], "SR_PA_PB_full": 6600 * pc["sr_flash_full"],
    "SR_PC_compact": 5100 * pc["sr_flash_compact"], "SR_PD_compact": 1800 * pc["sr_flash_compact"],
    "adj_cheap_pair": 740 * (pc["adj_haiku"] + pc["adj_gpt5mini"]) + 0.3 * 740 * pc["adj_deepseek"] + 50 * pc["adj_haiku"],
    "adj_expensive_pair": 740 * (pc["adj_sonnet"] + pc["adj_gpt41"]) + 0.3 * 740 * pc["adj_deepseek"] + 50 * pc["adj_sonnet"],
    "p1": 740 * (pc["p1_flash"] + pc["p1_g41m"])}
dump(proj, ROOT / "results/cost_projection.json")
print(json.dumps(proj["projection_usd"], indent=1))
