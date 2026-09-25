"""Async OpenRouter client with a resumable, cost-tracking ledger and a hard budget cap."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path

import aiohttp

from common import RESULTS, append_jsonl, read_jsonl

URL = "https://openrouter.ai/api/v1/chat/completions"
LEDGER = Path(os.environ.get("AII_LEDGER", str(RESULTS / "judge_ledger.jsonl")))  # override only for tests
HARD_CAP_USD = 8.0  # stop judging here; artifact budget is $10


def ledger_key(*parts) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()


def ledger_state() -> tuple[dict, float]:
    rows = read_jsonl(LEDGER)
    done = {r["key"]: r for r in rows if r.get("ok")}
    spent = sum(float(r.get("cost", 0.0) or 0.0) for r in rows)
    return done, spent


async def _call(session, sem, model, messages, max_tokens, extra) -> dict:
    headers = {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "Content-Type": "application/json"}
    body = {"model": model, "messages": messages, "temperature": 0, "max_tokens": max_tokens,
            "usage": {"include": True}}
    body.update(extra)
    async with sem:
        for attempt in range(5):
            try:
                async with session.post(URL, headers=headers, json=body, timeout=aiohttp.ClientTimeout(total=120)) as r:
                    txt = await r.text()
                    if r.status in (429, 500, 502, 503, 504):
                        await asyncio.sleep(2 ** attempt + 1)
                        continue
                    if r.status != 200:
                        return {"ok": False, "status": r.status, "error": txt[:300]}
                    j = json.loads(txt)
                    if "choices" not in j:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    content = j["choices"][0]["message"].get("content") or ""
                    cost = float((j.get("usage") or {}).get("cost", 0.0) or 0.0)
                    return {"ok": True, "content": content, "cost": cost, "usage": j.get("usage")}
            except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as e:
                await asyncio.sleep(2 ** attempt)
                err = str(e)
        return {"ok": False, "status": -1, "error": "retries exhausted"}


async def run_batch(jobs: list[dict], model: str = "google/gemini-2.5-flash", max_tokens: int = 300,
                    concurrency: int = 24, logger=None, fallback_model: str = "openai/gpt-4.1-mini") -> dict:
    """jobs: [{key, messages, meta}] -> {key: content}. Skips keys already in the ledger."""
    done, spent = ledger_state()
    out = {k: v["content"] for k, v in done.items()}
    todo = [j for j in jobs if j["key"] not in done]
    if logger:
        logger.info(f"OpenRouter: {len(jobs)} jobs, {len(todo)} to do, spent so far ${spent:.4f}")
    if not todo:
        return out
    sem = asyncio.Semaphore(concurrency)
    extra = {"reasoning": {"max_tokens": 0}} if "gemini-2.5-flash" in model else {}
    blocked = False
    async with aiohttp.ClientSession() as session:
        chunk = 96
        for i in range(0, len(todo), chunk):
            if spent >= HARD_CAP_USD:
                if logger:
                    logger.warning(f"Hard cap ${HARD_CAP_USD} reached; stopping.")
                break
            part = todo[i:i + chunk]
            use_model = fallback_model if blocked else model
            use_extra = {} if blocked else extra
            res = await asyncio.gather(*[_call(session, sem, use_model, j["messages"], max_tokens, use_extra) for j in part])
            rows = []
            n403 = 0
            for j, r in zip(part, res):
                row = {"key": j["key"], "model": use_model, "ok": r["ok"], "cost": r.get("cost", 0.0),
                       "meta": j.get("meta", {})}
                if r["ok"]:
                    row["content"] = r["content"]
                    out[j["key"]] = r["content"]
                else:
                    row["error"] = r.get("error")
                    row["status"] = r.get("status")
                    if r.get("status") in (402, 403):
                        n403 += 1
                rows.append(row)
                spent += float(r.get("cost", 0.0) or 0.0)
            append_jsonl(LEDGER, rows)
            if n403 > len(part) // 2 and not blocked:
                if logger:
                    logger.warning(f"{n403} x 402/403 from {model}: switching to fallback {fallback_model}")
                blocked = True
            if logger:
                logger.info(f"  chunk {i // chunk}: ok={sum(r['ok'] for r in res)}/{len(part)}  spent=${spent:.4f}")
    return out
