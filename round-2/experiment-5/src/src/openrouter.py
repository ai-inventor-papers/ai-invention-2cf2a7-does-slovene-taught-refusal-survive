#!/usr/bin/env python3
"""Async OpenRouter client with resumable, cost-capped JSONL ledgers (adapted from iter-1 openrouter.py).

- Every call is appended to outputs/ledgers/ledger_<name>.jsonl keyed by a caller key; done keys are skipped.
- A global cap over ALL ledgers (AII_COST_CAP, default $9.00) stops new dispatches.
- Key-limit errors (402/403 with 'Key limit'/'credits') set KEY_DOWN and stop cleanly (F5); a 403 PROHIBITED_CONTENT is
  a content block, never KEY_DOWN (the item is rerouted by the caller).
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import aiohttp
from loguru import logger

from common import LEDGERS, read_jsonl, truncate

URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/") + "/chat/completions"
COST_CAP_USD = float(os.environ.get("AII_COST_CAP", "9.0"))
PRICES = {"google/gemini-2.5-flash": (0.30, 2.50), "openai/gpt-4.1": (2.00, 8.00)}
KEY_DOWN_FLAG = LEDGERS / "KEY_DOWN.json"


class KeyDown(Exception):
    pass


class ContentBlocked(Exception):
    pass


def _is_block(txt: str) -> bool:
    t = txt.upper()
    return ("PROHIBITED_CONTENT" in t or "CONTENT_POLICY" in t or "CONTENT_FILTER" in t
            or ("SAFETY" in t and "BLOCK" in t))


def _is_key_limit(txt: str) -> bool:
    t = txt.lower()
    return "key limit" in t or "credits" in t or "daily limit" in t


def total_spent() -> float:
    tot = 0.0
    for p in LEDGERS.glob("ledger_*.jsonl"):
        for r in read_jsonl(p):
            tot += float(r.get("cost") or 0.0)
    return tot


class Ledger:
    def __init__(self, name: str):
        self.path = LEDGERS / f"ledger_{name}.jsonl"
        self.rows = {r["key"]: r for r in read_jsonl(self.path) if r.get("label") is not None}
        self.lock = asyncio.Lock()
        self.spent_global = total_spent()
        self.stop = False
        self.stop_reason = ""

    def done(self, key: str) -> bool:
        return key in self.rows

    async def append(self, row: dict[str, Any]) -> None:
        async with self.lock:
            row["ts"] = datetime.now(timezone.utc).isoformat()
            self.rows[row["key"]] = row
            self.spent_global += float(row.get("cost") or 0.0)
            with self.path.open("a") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            if self.spent_global >= COST_CAP_USD:
                self.stop, self.stop_reason = True, f"cost cap {COST_CAP_USD} reached ({self.spent_global:.3f})"


def payload(model: str, messages: list[dict], max_tokens: int) -> dict:
    p: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.0,
                         "usage": {"include": True}}
    if model.startswith("google/gemini-2.5"):
        p["reasoning"] = {"max_tokens": 0}
    return p


async def call(session: aiohttp.ClientSession, model: str, messages: list[dict], max_tokens: int,
               retries: int = 6) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "Content-Type": "application/json"}
    last = ""
    for attempt in range(retries):
        try:
            async with session.post(URL, headers=headers, json=payload(model, messages, max_tokens),
                                    timeout=aiohttp.ClientTimeout(total=90)) as r:
                txt = await r.text()
                if r.status in (402, 403) and _is_key_limit(txt):
                    raise KeyDown(f"HTTP {r.status}: {truncate(txt, 200)}")
                if _is_block(txt):
                    raise ContentBlocked(truncate(txt, 200))
                if r.status == 429:
                    last = f"429 {truncate(txt, 150)}"
                    await asyncio.sleep(2 ** attempt + 1)
                    continue
                if r.status >= 500:
                    last = f"{r.status} {truncate(txt, 150)}"
                    # the AII proxy's budget meter can be briefly unreadable ("retry shortly"): back off longer
                    await asyncio.sleep(min(60, 5 * 2 ** attempt) if "meter_unavailable" in txt else 2 ** attempt)
                    continue
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}: {truncate(txt, 300)}")
                d = json.loads(txt)
                if "error" in d:
                    if _is_block(json.dumps(d["error"])):
                        raise ContentBlocked(str(d["error"])[:200])
                    last = str(d["error"])[:200]
                    await asyncio.sleep(2 ** attempt)
                    continue
                ch = d["choices"][0]
                if ch.get("finish_reason") in ("content_filter",) or ch.get("native_finish_reason") == "PROHIBITED_CONTENT":
                    raise ContentBlocked(f"finish_reason={ch.get('finish_reason')}")
                msg = ch["message"]
                usage = d.get("usage") or {}
                cost = usage.get("cost")
                if cost is None:
                    pin, pout = PRICES.get(model, (2.0, 8.0))
                    cost = (usage.get("prompt_tokens", 0) * pin + usage.get("completion_tokens", 0) * pout) / 1e6
                return {"text": (msg.get("content") or "").strip(), "prompt_tokens": usage.get("prompt_tokens"),
                        "completion_tokens": usage.get("completion_tokens"), "cost": float(cost),
                        "model_used": d.get("model")}
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError, KeyError, IndexError) as e:
            last = f"{type(e).__name__}: {e}"
            await asyncio.sleep(2 ** attempt)
    raise RuntimeError(f"failed after {retries} retries: {last}")


async def run_jobs(ledger: Ledger, jobs: list[dict[str, Any]], parse: Callable[[str], Any],
                   concurrency: int = 16) -> dict[str, int]:
    """jobs: {key, model, messages, max_tokens, meta}. parse(text)->label (str) or tuple."""
    sem = asyncio.Semaphore(concurrency)
    stats = {"done": 0, "skipped": 0, "failed": 0, "blocked": 0}
    t0 = time.time()
    async with aiohttp.ClientSession() as session:
        async def one(job):
            if ledger.done(job["key"]):
                stats["skipped"] += 1
                return
            async with sem:
                if ledger.stop:
                    return
                try:
                    res = await call(session, job["model"], job["messages"], job["max_tokens"])
                except ContentBlocked as e:
                    await ledger.append({"key": job["key"], "judge": job["model"], "label": "BLOCKED",
                                         "raw": str(e)[:200], "cost": 0.0, **job.get("meta", {})})
                    stats["blocked"] += 1
                    return
                except KeyDown as e:
                    if not ledger.stop:
                        ledger.stop, ledger.stop_reason = True, f"KEY_DOWN: {e}"
                        logger.error(ledger.stop_reason)
                        KEY_DOWN_FLAG.write_text(json.dumps({"utc": datetime.now(timezone.utc).isoformat(),
                                                             "error": str(e)[:300]}))
                    return
                except RuntimeError as e:
                    stats["failed"] += 1
                    logger.warning(f"{job['key']}: {e}")
                    return
                lab = parse(res["text"])
                row = {"key": job["key"], "judge": job["model"], "raw": truncate(res["text"], 200),
                       **{k: res[k] for k in ("prompt_tokens", "completion_tokens", "cost")}, **job.get("meta", {})}
                if isinstance(lab, tuple):
                    row["label"], row["label2"] = lab
                else:
                    row["label"] = lab
                await ledger.append(row)
                stats["done"] += 1
                if stats["done"] % 1000 == 0:
                    logger.info(f"[{ledger.path.name}] {stats} spent_global=${ledger.spent_global:.3f} "
                                f"{time.time() - t0:.0f}s")
        await asyncio.gather(*(one(j) for j in jobs))
    logger.info(f"[{ledger.path.name}] finished {stats} spent_global=${ledger.spent_global:.3f} "
                f"stop={ledger.stop_reason or 'none'}")
    return stats


def probe() -> dict:
    """The one-call rule: a single tiny call to each family; returns status per model."""
    async def _p():
        out = {}
        async with aiohttp.ClientSession() as s:
            for m in ("google/gemini-2.5-flash", "openai/gpt-4.1"):
                try:
                    r = await call(s, m, [{"role": "user", "content": "Reply with OK"}], 16, retries=1)
                    out[m] = {"ok": True, "text": r["text"], "cost": r["cost"]}
                except KeyDown as e:
                    out[m] = {"ok": False, "key_down": True, "err": str(e)[:200]}
                except (RuntimeError, ContentBlocked) as e:
                    out[m] = {"ok": False, "key_down": False, "err": str(e)[:200]}
        return out
    return asyncio.run(_p())


if __name__ == "__main__":
    print(json.dumps(probe(), indent=1))
