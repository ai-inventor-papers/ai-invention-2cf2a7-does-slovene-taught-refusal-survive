#!/usr/bin/env python3
"""Poll the shared OpenRouter key (via the run's base-URL proxy) every 120 s with one 5-token gemini call (~$0.00002)
until it no longer answers 'Key limit exceeded', then exit 0. Exit 1 at the UTC deadline hh:mm (argv[1], default 03:30).
The proxy's own /key endpoint reports the per-run key, not the shared upstream daily limit, so a real call is used."""
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request

deadline = sys.argv[1] if len(sys.argv) > 1 else "03:30"
URL = os.environ["OPENROUTER_BASE_URL"].rstrip("/") + "/chat/completions"
H = {"Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"], "Content-Type": "application/json",
     "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) aii-gen-art/1.0"}
BODY = json.dumps({"model": "google/gemini-2.5-flash", "messages": [{"role": "user", "content": "Say OK"}],
                   "max_tokens": 3, "reasoning": {"max_tokens": 0}}).encode()
while True:
    now = dt.datetime.now(dt.timezone.utc)
    try:
        r = urllib.request.urlopen(urllib.request.Request(URL, data=BODY, headers=H), timeout=60)
        print(f"{now:%H:%M:%S} key OK status={r.status}", flush=True)
        sys.exit(0)
    except urllib.error.HTTPError as e:
        print(f"{now:%H:%M:%S} HTTP {e.code} {e.read()[:90]!r}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"{now:%H:%M:%S} probe error {e!r}", flush=True)
    if now.strftime("%H:%M") >= deadline and now.hour < 12:
        sys.exit(1)
    time.sleep(120)
