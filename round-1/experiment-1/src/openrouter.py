#!/usr/bin/env python3
"""Minimal async OpenRouter client with a resumable, cost-capped JSONL ledger.

Every call is appended to a ledger file keyed by a caller-supplied key; keys already present are skipped.
A global cumulative-cost cap (over ALL ledgers of this artifact) stops new calls cleanly.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

import aiohttp
from loguru import logger

from common import OUT, read_jsonl, truncate

URL = "https://openrouter.ai/api/v1/chat/completions"
LEDGERS = sorted  # placeholder for type checkers
COST_CAP_USD = float(os.environ.get("AII_COST_CAP", "4.0"))  # this artifact's own cap (hard cap for run: $10)
# price table ($/M tokens) used only when usage.cost is missing
PRICES = {"google/gemini-2.5-flash": (0.30, 2.50), "openai/gpt-4.1-mini": (0.40, 1.60),
          "google/gemini-2.0-flash-001": (0.10, 0.40), "meta-llama/llama-3.3-70b-instruct": (0.13, 0.40)}


class DailyLimit(Exception):
    pass


class ContentBlocked(Exception):
    pass


def _is_block(txt: str) -> bool:
    t = txt.upper()
    return "PROHIBITED_CONTENT" in t or "CONTENT_POLICY" in t or "SAFETY" in t and "BLOCK" in t


def total_spent() -> float:
    tot = 0.0
    for p in OUT.glob("ledger_*.jsonl"):
        for r in read_jsonl(p):
            tot += float(r.get("cost") or 0.0)
    return tot


class Ledger:
    def __init__(self, name: str):
        self.path = OUT / f"ledger_{name}.jsonl"
        self.rows = {r["key"]: r for r in read_jsonl(self.path) if "key" in r and r.get("label") is not None}
        self.lock = asyncio.Lock()
        self.spent_global = total_spent()
        self.stop = False
        self.stop_reason = ""

    def done(self, key: str) -> bool:
        return key in self.rows

    async def append(self, row: dict[str, Any]) -> None:
        async with self.lock:
            self.rows[row["key"]] = row
            self.spent_global += float(row.get("cost") or 0.0)
            with self.path.open("a") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            if self.spent_global >= COST_CAP_USD:
                self.stop, self.stop_reason = True, f"cost cap {COST_CAP_USD} reached ({self.spent_global:.3f})"


def _payload(model: str, messages: list[dict], max_tokens: int, temperature: float = 0.0) -> dict:
    p: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature,
                         "usage": {"include": True}}
    if model.startswith("google/gemini-2.5"):
        p["reasoning"] = {"max_tokens": 0}
    return p


async def call(session: aiohttp.ClientSession, model: str, messages: list[dict], max_tokens: int,
               temperature: float = 0.0, retries: int = 5) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "Content-Type": "application/json"}
    last = ""
    for attempt in range(retries):
        try:
            async with session.post(URL, headers=headers, json=_payload(model, messages, max_tokens, temperature),
                                    timeout=aiohttp.ClientTimeout(total=90)) as r:
                txt = await r.text()
                if _is_block(txt):
                    raise ContentBlocked(truncate(txt, 200))
                if r.status in (402, 403):
                    raise DailyLimit(f"HTTP {r.status}: {truncate(txt, 300)}")
                if r.status == 429:
                    if "day" in txt.lower() or "daily" in txt.lower():
                        raise DailyLimit(f"HTTP 429 daily: {truncate(txt, 300)}")
                    last = f"429 {truncate(txt, 200)}"
                    await asyncio.sleep(2 ** attempt + 1)
                    continue
                if r.status >= 500:
                    last = f"{r.status} {truncate(txt, 200)}"
                    await asyncio.sleep(2 ** attempt)
                    continue
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}: {truncate(txt, 300)}")
                d = json.loads(txt)
                if "error" in d:
                    last = str(d["error"])[:200]
                    await asyncio.sleep(2 ** attempt)
                    continue
                msg = d["choices"][0]["message"]
                usage = d.get("usage") or {}
                cost = usage.get("cost")
                if cost is None:
                    pin, pout = PRICES.get(model, (1.0, 4.0))
                    cost = (usage.get("prompt_tokens", 0) * pin + usage.get("completion_tokens", 0) * pout) / 1e6
                return {"text": (msg.get("content") or "").strip(), "prompt_tokens": usage.get("prompt_tokens"),
                        "completion_tokens": usage.get("completion_tokens"),
                        "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                        "cost": float(cost), "model_used": d.get("model")}
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError, KeyError) as e:
            last = f"{type(e).__name__}: {e}"
            await asyncio.sleep(2 ** attempt)
    raise RuntimeError(f"failed after {retries} retries: {last}")


async def run_jobs(ledger: Ledger, jobs: list[dict[str, Any]], parse, concurrency: int = 16) -> dict[str, int]:
    """jobs: {key, model, messages, max_tokens, meta}. parse(text)->label. Returns counters."""
    sem = asyncio.Semaphore(concurrency)
    stats = {"done": 0, "skipped": 0, "failed": 0}
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
                    row = {"key": job["key"], "judge": job["model"], "label": "BLOCKED", "raw": str(e)[:200],
                           "prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0, "cost": 0.0,
                           **job.get("meta", {})}
                    await ledger.append(row)
                    stats["blocked"] = stats.get("blocked", 0) + 1
                    return
                except DailyLimit as e:
                    ledger.stop, ledger.stop_reason = True, f"daily_limit: {e}"
                    logger.error(ledger.stop_reason)
                    return
                except RuntimeError as e:
                    stats["failed"] += 1
                    logger.warning(f"{job['key']}: {e}")
                    return
                label = parse(res["text"])
                row = {"key": job["key"], "judge": job["model"], "label": label, "raw": truncate(res["text"], 300),
                       **{k: res[k] for k in ("prompt_tokens", "completion_tokens", "reasoning_tokens", "cost")},
                       **job.get("meta", {})}
                await ledger.append(row)
                stats["done"] += 1
                if stats["done"] % 500 == 0:
                    logger.info(f"[{ledger.path.name}] {stats} spent_global=${ledger.spent_global:.3f} "
                                f"{time.time() - t0:.0f}s")
        await asyncio.gather(*(one(j) for j in jobs), return_exceptions=False)
    logger.info(f"[{ledger.path.name}] finished {stats} spent_global=${ledger.spent_global:.3f} stop={ledger.stop_reason}")
    return stats
