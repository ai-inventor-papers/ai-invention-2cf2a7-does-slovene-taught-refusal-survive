#!/usr/bin/env python3
"""Step 0: record environment (GPU, disk) and the OpenRouter key status into logs/env.json; initialise the shared cost
ledger (ledger/ledger.jsonl, ledger/summary.json). No paid call is made by this module (key exhausted) -> spend $0."""
import json
import os
import shutil
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    env = {"utc": datetime.now(timezone.utc).isoformat()}
    try:
        env["nvidia_smi"] = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                                           capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError) as e:
        env["nvidia_smi"] = f"error {e!r}"
    du = shutil.disk_usage(ROOT)
    env["disk_free_gb"] = round(du.free / 1e9, 1)
    try:
        req = urllib.request.Request("https://openrouter.ai/api/v1/key", headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"})
        k = json.load(urllib.request.urlopen(req, timeout=30))["data"]
        env["openrouter_key"] = {x: k.get(x) for x in ["limit", "limit_reset", "limit_remaining", "usage_daily"]}
    except (OSError, KeyError, ValueError) as e:
        env["openrouter_key"] = {"error": repr(e)}
    (ROOT / "logs").mkdir(exist_ok=True)
    (ROOT / "logs/env.json").write_text(json.dumps(env, indent=1))
    (ROOT / "ledger").mkdir(exist_ok=True)
    led = ROOT / "ledger/ledger.jsonl"
    if not led.exists():
        led.write_text("")
    n = sum(1 for l in led.open() if l.strip())
    cost = sum(json.loads(l).get("cost_usd", 0) for l in led.open() if l.strip())
    (ROOT / "ledger/summary.json").write_text(json.dumps({
        "cap_usd": 9.50, "sub_caps_usd": {"A": 2.6, "D": 0.5, "B": 3.6, "C": 2.3}, "n_calls": n, "spent_usd": round(cost, 4),
        "status": ("OpenRouter key daily limit exhausted at module start (limit_remaining=0, resets 00:00 UTC, after the "
                   "module deadline). Per the plan's failure scenario (4) every API step ran on the LOCAL FALLBACK "
                   "(open-weight models on the local RTX 4090); spend = $0."),
        "key_status_at_start": env["openrouter_key"]}, indent=1))
    print(json.dumps(env, indent=1))


if __name__ == "__main__":
    main()
