"""Async OpenRouter client: Semaphore(24), temperature 0 (unless given), JSON output, gemini reasoning disabled,
cost from usage.cost into the shared ledger, resumable JSONL caches keyed by item key."""
import asyncio
import json
import os
import re
from pathlib import Path

import aiohttp
from loguru import logger

from lib.ledger import BudgetExhausted, Ledger

URL = "https://openrouter.ai/api/v1/chat/completions"
PRICE = {"openai/gpt-4.1-mini": (0.40, 1.60), "google/gemini-2.5-flash": (0.30, 2.50),
         "meta-llama/llama-3.3-70b-instruct": (0.10, 0.32)}  # $/M tokens (checked 2026-09-23 via /api/v1/models)


def est_cost(model: str, n_in_chars: int, max_out: int) -> float:
    pi, po = PRICE[model]
    return (n_in_chars / 3.2 * pi + max_out * po) / 1e6


def parse_json(txt: str):
    txt = txt.strip()
    txt = re.sub(r"^```(?:json)?|```$", "", txt, flags=re.M).strip()
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        m = re.search(r"(\{.*\}|\[.*\])", txt, re.S)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                return None
    return None


class Judge:
    def __init__(self, step: str, concurrency: int = 24):
        self.step, self.ledger = step, Ledger()
        self.sem = asyncio.Semaphore(concurrency)
        self.limit_fail = 0

    async def call(self, session, model: str, messages: list[dict], key: str, max_tokens: int = 120,
                   temperature: float = 0.0, json_mode: bool = True, validate=None, seed: int | None = None):
        body = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens,
                "usage": {"include": True}}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if seed is not None:
            body["seed"] = seed
        if model.startswith("google/gemini-2.5"):
            body["reasoning"] = {"enabled": False}
        est = est_cost(model, sum(len(m["content"]) for m in messages), max_tokens)
        err = None
        async with self.sem:
            for attempt in range(4):
                self.ledger.check(self.step, est)
                try:
                    async with session.post(URL, json=body, timeout=aiohttp.ClientTimeout(total=120),
                                            headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"}) as r:
                        status = r.status
                        j = await r.json(content_type=None)
                    if status in (402, 403, 429) or (isinstance(j, dict) and "error" in j and status >= 400):
                        err = f"http {status}: {str(j)[:200]}"
                        if status in (402, 403) or "limit" in str(j).lower():
                            self.limit_fail += 1
                            logger.warning(f"limit-type failure {self.limit_fail}: {err}")
                            if self.limit_fail >= 6:
                                return {"key": key, "model": model, "error": "limit_exhausted"}
                            await asyncio.sleep(60)
                        else:
                            await asyncio.sleep(3 * (attempt + 1))
                        continue
                    self.ledger.add(self.step, model, key, j.get("usage", {}))
                    txt = j["choices"][0]["message"]["content"] or ""
                    parsed = parse_json(txt) if json_mode else txt
                    if json_mode and (parsed is None or (validate and not validate(parsed))):
                        err = f"invalid: {txt[:200]}"
                        continue
                    self.limit_fail = 0
                    return {"key": key, "model": model, "raw": txt, "parsed": parsed}
                except BudgetExhausted:
                    raise
                except (aiohttp.ClientError, asyncio.TimeoutError, KeyError, IndexError, TypeError, ValueError) as e:
                    err = repr(e)[:200]
                    await asyncio.sleep(2 * (attempt + 1))
        return {"key": key, "model": model, "error": err}


def load_cache(p: Path) -> dict:
    out = {}
    if p.exists():
        for l in p.open():
            if l.strip():
                r = json.loads(l)
                if "error" not in r:
                    out[r["key"]] = r
    return out


async def run_many(judge: Judge, jobs: list[dict], cache: Path, log_every: int = 500) -> dict:
    """jobs: dicts with key, model, messages, (max_tokens, validate, json_mode, temperature, seed)."""
    done = load_cache(cache)
    todo = [j for j in jobs if j["key"] not in done]
    logger.info(f"{cache.name}: {len(done)} cached, {len(todo)} to call (spent so far ${judge.ledger.total:.3f})")
    cache.parent.mkdir(parents=True, exist_ok=True)
    async with aiohttp.ClientSession() as session:
        tasks = [asyncio.create_task(judge.call(session, j["model"], j["messages"], j["key"], j.get("max_tokens", 120),
                                                j.get("temperature", 0.0), j.get("json_mode", True), j.get("validate"),
                                                j.get("seed"))) for j in todo]
        n_err = 0
        with cache.open("a") as f:
            for i, fut in enumerate(asyncio.as_completed(tasks)):
                try:
                    res = await fut
                except BudgetExhausted as e:
                    logger.error(f"BUDGET: {e}")
                    for t in tasks:
                        t.cancel()
                    break
                f.write(json.dumps(res, ensure_ascii=False) + "\n")
                f.flush()
                if "error" in res:
                    n_err += 1
                else:
                    done[res["key"]] = res
                if i % log_every == 0:
                    logger.info(f"{cache.name}: {i}/{len(todo)} errors={n_err} spent=${judge.ledger.total:.3f} step={judge.ledger.by_step.get(judge.step, 0):.3f}")
    logger.info(f"{cache.name}: finished, {len(done)} ok, errors={n_err}, spent=${judge.ledger.total:.3f}")
    return done
