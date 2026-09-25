#!/usr/bin/env python3
"""Async OpenRouter client with a resumable, globally cost-capped JSONL ledger (iter-1 openrouter.py pattern).

- Every paid call is appended to labels/ledger_<name>.jsonl keyed by a caller key; present keys are skipped on resume.
- Cumulative cost over ALL ledgers (+ gens/api ledgers) is checked after every call; new calls stop at COST_CAP_USD.
- 'Key limit exceeded' (daily limit) is distinguished from 403 PROHIBITED_CONTENT (routed to a fallback judge).
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

import aiohttp
from loguru import logger

from common import COST_CAP_USD, GENS, LABELS, PRICES, read_jsonl, truncate

# the run's key only works at the run's base URL (a proxy); never hard-code OpenRouter's own URL (401)
URL = os.environ.get("OPENROUTER_BASE_URL", "").rstrip("/") + "/chat/completions"
# the proxy sits behind Cloudflare, which rejects default library user agents with an HTML 403
UA = "Mozilla/5.0 (X11; Linux x86_64) aii-gen-art/1.0"


class DailyLimit(Exception):
    pass


class ContentBlocked(Exception):
    pass


def _is_block(txt: str) -> bool:
    t = txt.upper()
    # gemini: PROHIBITED_CONTENT; Alibaba DashScope input moderation: data_inspection_failed / inappropriate content
    return ("PROHIBITED_CONTENT" in t or "CONTENT_POLICY" in t or ("SAFETY" in t and "BLOCK" in t)
            or "DATA_INSPECTION_FAILED" in t or "INAPPROPRIATE CONTENT" in t or "CONTENT_FILTER" in t)


def ledger_paths() -> list[Path]:
    # every paid call of this artifact, pilot ledgers included
    return sorted(LABELS.glob("**/ledger_*.jsonl")) + sorted(GENS.glob("**/ledger_*.jsonl"))


def total_spent() -> float:
    tot = 0.0
    for p in ledger_paths():
        for r in read_jsonl(p):
            tot += float(r.get("cost") or 0.0)
    return tot


class Ledger:
    def __init__(self, path: Path):
        self.path = path
        self.rows = {r["key"]: r for r in read_jsonl(path) if "key" in r and r.get("ok")}
        self.lock = asyncio.Lock()
        self.spent_global = total_spent()
        self.stop = False
        self.stop_reason = ""

    def done(self, key: str) -> bool:
        return key in self.rows

    async def append(self, row: dict[str, Any]) -> None:
        async with self.lock:
            if row.get("ok"):
                self.rows[row["key"]] = row
            self.spent_global += float(row.get("cost") or 0.0)
            with self.path.open("a") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            if self.spent_global >= COST_CAP_USD:
                self.stop, self.stop_reason = True, f"cost cap {COST_CAP_USD} reached ({self.spent_global:.3f})"


def payload(model: str, messages: list[dict], max_tokens: int, provider: str | None = None,
            reasoning_off: bool = False, temperature: float = 0.0) -> dict:
    p: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature,
                         "usage": {"include": True}}
    if model.startswith("google/gemini-2.5"):
        p["reasoning"] = {"max_tokens": 0}
    elif reasoning_off:
        p["reasoning"] = {"enabled": False}
    if provider:
        p["provider"] = {"order": [provider], "allow_fallbacks": False}
    return p


async def call(session: aiohttp.ClientSession, body: dict, retries: int = 8) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "Content-Type": "application/json",
               "User-Agent": UA}
    last = ""
    for attempt in range(retries):
        try:
            async with session.post(URL, headers=headers, json=body, timeout=aiohttp.ClientTimeout(total=120)) as r:
                txt = await r.text()
                if ("key limit exceeded" in txt.lower() or "aii_run_budget_exhausted" in txt
                        or ("daily" in txt.lower() and r.status in (402, 403, 429))):
                    raise DailyLimit(f"HTTP {r.status}: {truncate(txt, 200)}")
                if r.status == 403 and txt.lstrip().startswith("<"):
                    last = f"403 html (proxy/Cloudflare) {truncate(txt, 120)}"
                    await asyncio.sleep(min(2 ** attempt + 1, 30))
                    continue
                if _is_block(txt):
                    raise ContentBlocked(truncate(txt, 200))
                if r.status == 402:
                    raise DailyLimit(f"HTTP 402: {truncate(txt, 200)}")
                if r.status in (408, 429) or r.status >= 500 or (r.status == 404 and not txt.strip()):
                    # 429 = upstream rate limit; 5xx / empty-body 404 = transient proxy outage (observed 00:25 UTC)
                    last = f"{r.status} {truncate(txt, 200)}"
                    await asyncio.sleep(min(2 ** attempt + 1, 60))
                    continue
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}: {truncate(txt, 300)}")
                d = json.loads(txt)
                if "error" in d:
                    last = str(d["error"])[:200]
                    if _is_block(last):
                        raise ContentBlocked(last)
                    await asyncio.sleep(2 ** attempt)
                    continue
                ch = d["choices"][0]
                msg = ch["message"]
                usage = d.get("usage") or {}
                cost = usage.get("cost")
                if cost is None:
                    pin, pout = PRICES.get(body["model"], (2.0, 8.0))
                    cost = (usage.get("prompt_tokens", 0) * pin + usage.get("completion_tokens", 0) * pout) / 1e6
                return {"text": msg.get("content") or "", "reasoning": msg.get("reasoning") or "",
                        "finish_reason": ch.get("finish_reason") or ch.get("native_finish_reason"),
                        "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
                        "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                        "cost": float(cost), "model_used": d.get("model"), "provider_used": d.get("provider")}
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError, KeyError, IndexError) as e:
            last = f"{type(e).__name__}: {e}"
            await asyncio.sleep(min(2 ** attempt, 30))
    raise RuntimeError(f"failed after {retries} retries: {last}")


async def run_jobs(ledger: Ledger, jobs: list[dict[str, Any]], post: Callable[[dict, dict], dict],
                   concurrency: int = 16) -> dict[str, int]:
    """jobs: {key, body, meta}. post(job, result) -> dict of fields to store (must not contain 'key')."""
    sem = asyncio.Semaphore(concurrency)
    stats = {"done": 0, "skipped": 0, "failed": 0, "blocked": 0}
    # consecutive failures -> all workers pause 90 s (proxy outage), up to 12 pauses, then a resumable stop
    consec = {"fail": 0, "pauses": 0, "until": 0.0}
    t0 = time.time()
    async with aiohttp.ClientSession() as session:
        async def one(job):
            if ledger.done(job["key"]):
                stats["skipped"] += 1
                return
            async with sem:
                if ledger.stop:
                    return
                if consec["fail"] >= 40:
                    consec["pauses"] += 1
                    consec["fail"] = 0
                    consec["until"] = time.time() + 90
                    logger.warning(f"outage pause {consec['pauses']} (90 s, all workers)")
                    if consec["pauses"] > 12:
                        ledger.stop, ledger.stop_reason = True, "outage: 12 pauses exhausted"
                        return
                wait = consec["until"] - time.time()
                if wait > 0:
                    await asyncio.sleep(wait)
                if ledger.stop:
                    return
                try:
                    res = await call(session, job["body"])
                except ContentBlocked as e:
                    await ledger.append({"key": job["key"], "ok": True, "blocked": True, "raw": str(e)[:200],
                                         "cost": 0.0, "model": job["body"]["model"], **job.get("meta", {})})
                    stats["blocked"] += 1
                    return
                except DailyLimit as e:
                    ledger.stop, ledger.stop_reason = True, f"daily_limit: {e}"
                    logger.error(ledger.stop_reason)
                    return
                except RuntimeError as e:
                    stats["failed"] += 1
                    consec["fail"] += 1
                    logger.warning(f"{job['key']}: {e}")
                    return
                consec["fail"] = 0
                row = {"key": job["key"], "ok": True, "blocked": False, "model": job["body"]["model"],
                       **{k: res[k] for k in ("prompt_tokens", "completion_tokens", "reasoning_tokens", "cost",
                                              "model_used", "provider_used", "finish_reason")},
                       **job.get("meta", {}), **post(job, res)}
                await ledger.append(row)
                stats["done"] += 1
                if stats["done"] % 500 == 0:
                    logger.info(f"[{ledger.path.name}] {stats} spent_global=${ledger.spent_global:.3f} "
                                f"{time.time() - t0:.0f}s")
        await asyncio.gather(*(one(j) for j in jobs))
    logger.info(f"[{ledger.path.name}] finished {stats} spent_global=${ledger.spent_global:.3f} "
                f"stop={ledger.stop_reason or 'none'} in {time.time() - t0:.0f}s")
    return stats
