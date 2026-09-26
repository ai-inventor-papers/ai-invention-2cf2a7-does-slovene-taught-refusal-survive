"""Resumable OpenRouter client with a cost ledger (hard cap) — used for translation and judging."""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path

import aiohttp
from loguru import logger

from common import RES, append_jsonl, read_jsonl, sha1

LEDGER = RES / "judge_ledger.jsonl"
URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-2.5-flash"
PRICE_IN, PRICE_OUT = 0.30e-6, 2.50e-6  # USD/token (fallback if usage.cost missing)
SOFT_CAP, HARD_CAP = 6.0, 9.5


class DailyLimit(RuntimeError):
    pass


def ledger_rows() -> list[dict]:
    return read_jsonl(LEDGER)


def spent() -> float:
    return float(sum(r.get("cost", 0.0) for r in ledger_rows()))


def _cached() -> dict[str, dict]:
    return {r["key"]: r for r in ledger_rows() if r.get("ok")}


def parse_json(txt: str) -> dict | None:
    m = re.search(r"\{.*\}", txt or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


async def _one(session: aiohttp.ClientSession, sem: asyncio.Semaphore, key: str, messages: list[dict],
               tag: str, max_tokens: int, state: dict, model: str = MODEL) -> dict:
    async with sem:
        if state["stop"]:
            return {"key": key, "ok": False, "err": "stopped"}
        body = {"model": model, "messages": messages, "temperature": 0, "max_tokens": max_tokens,
                "usage": {"include": True}}
        if model.startswith("google/"):
            body["reasoning"] = {"max_tokens": 0, "enabled": False}
        hdr = {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "Content-Type": "application/json"}
        for attempt in range(5):
            try:
                async with session.post(URL, json=body, headers=hdr, timeout=aiohttp.ClientTimeout(total=90)) as r:
                    txt = await r.text()
                    if r.status in (402, 403) or (r.status == 429 and "day" in txt.lower()):
                        state["stop"] = True
                        logger.error(f"OpenRouter daily/credit limit: HTTP {r.status} {txt[:300]}")
                        return {"key": key, "ok": False, "err": f"http{r.status}"}
                    if r.status != 200:
                        logger.warning(f"HTTP {r.status} attempt {attempt}: {txt[:200]}")
                        await asyncio.sleep(2 * (attempt + 1))
                        continue
                    d = json.loads(txt)
                    out = d["choices"][0]["message"].get("content") or ""
                    u = d.get("usage", {}) or {}
                    cost = u.get("cost")
                    if cost is None:
                        cost = u.get("prompt_tokens", 0) * PRICE_IN + u.get("completion_tokens", 0) * PRICE_OUT
                    row = {"key": key, "tag": tag, "ok": True, "out": out, "cost": float(cost),
                           "ptok": u.get("prompt_tokens"), "ctok": u.get("completion_tokens"), "t": time.time()}
                    append_jsonl(LEDGER, [row])
                    state["spent"] += float(cost)
                    if state["spent"] > HARD_CAP:
                        state["stop"] = True
                        logger.error(f"HARD CAP reached: ${state['spent']:.3f}")
                    logger.debug(f"[{tag}] {messages[-1]['content'][:120]!r} -> {out[:160]!r}")
                    return row
            except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError, KeyError) as e:
                logger.warning(f"request error attempt {attempt}: {e!r}")
                await asyncio.sleep(2 * (attempt + 1))
        return {"key": key, "ok": False, "err": "retries"}


async def _run(jobs: list[tuple[str, list[dict]]], tag: str, max_tokens: int, conc: int, model: str = MODEL) -> dict[str, dict]:
    cache = _cached()
    todo = [(k, m) for k, m in jobs if k not in cache]
    state = {"stop": False, "spent": spent()}
    logger.info(f"[{tag}] {len(jobs)} jobs, {len(jobs) - len(todo)} cached, {len(todo)} to call; spent so far ${state['spent']:.3f}")
    if state["spent"] > SOFT_CAP and todo:
        logger.error(f"SOFT CAP ${SOFT_CAP} exceeded; not calling")
        todo = []
    sem = asyncio.Semaphore(conc)
    async with aiohttp.ClientSession() as s:
        res = await asyncio.gather(*[_one(s, sem, k, m, tag, max_tokens, state, model) for k, m in todo])
    for r in res:
        if r.get("ok"):
            cache[r["key"]] = r
    if state["stop"] and any(not r.get("ok") for r in res):
        logger.error(f"[{tag}] stopped early; {sum(not r.get('ok') for r in res)} calls missing")
    logger.info(f"[{tag}] done; total spent ${spent():.3f}")
    return {k: cache[k] for k, _ in jobs if k in cache}


def call_many(jobs: list[tuple[str, list[dict]]], tag: str, max_tokens: int = 300, conc: int = 8,
              model: str = MODEL) -> dict[str, dict]:
    """jobs: list of (ledger_key, messages). Returns {key: ledger_row} for the successful ones (resumable)."""
    return asyncio.run(_run(jobs, tag, max_tokens, conc, model))


def key_for(*parts: str) -> str:
    return sha1("|".join(parts))
