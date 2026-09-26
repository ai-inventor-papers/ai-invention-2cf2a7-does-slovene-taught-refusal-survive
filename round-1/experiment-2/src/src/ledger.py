"""OpenRouter client with a resumable JSONL cost ledger and a hard spend cap (SCREEN-SPEC v1 (8))."""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

import aiohttp
from loguru import logger

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "results/shared/openrouter_ledger.jsonl"
HARD_CAP_USD = 9.0  # global hard stop (artifact budget $10)
URL = "https://openrouter.ai/api/v1/chat/completions"


class BudgetExceeded(RuntimeError):
    pass


class DailyLimit(RuntimeError):
    pass


def ledger_rows() -> list[dict]:
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def spent(purpose: str | None = None) -> float:
    return sum(r.get("cost", 0.0) or 0.0 for r in ledger_rows() if purpose is None or r.get("purpose") == purpose)


def done_keys(purpose: str) -> dict[str, dict]:
    return {r["key"]: r for r in ledger_rows() if r.get("purpose") == purpose and r.get("ok")}


class Client:
    def __init__(self, purpose: str, cap_usd: float, concurrency: int = 8, model: str = "google/gemini-2.5-flash"):
        self.purpose, self.cap, self.model = purpose, cap_usd, model
        self.sem = asyncio.Semaphore(concurrency)
        self.spent_purpose = spent(purpose)
        self.spent_total = spent()
        self.key = os.environ["OPENROUTER_API_KEY"]
        self.lock = asyncio.Lock()
        self.daily_limit_hit = False

    async def call(self, session: aiohttp.ClientSession, key: str, messages: list[dict], max_tokens: int = 400,
                   json_mode: bool = False) -> str | None:
        if self.daily_limit_hit:
            return None
        if self.spent_purpose >= self.cap or self.spent_total >= HARD_CAP_USD:
            raise BudgetExceeded(f"{self.purpose}: spent {self.spent_purpose:.3f} (cap {self.cap}), total {self.spent_total:.3f}")
        body = {"model": self.model, "messages": messages, "temperature": 0, "max_tokens": max_tokens,
                "usage": {"include": True}, "reasoning": {"enabled": False, "max_tokens": 0}}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        async with self.sem:
            for attempt in range(4):
                try:
                    t0 = time.time()
                    async with session.post(URL, json=body, headers={"Authorization": f"Bearer {self.key}"},
                                            timeout=aiohttp.ClientTimeout(total=120)) as r:
                        txt = await r.text()
                        if r.status in (402, 403):
                            logger.error(f"OpenRouter {r.status}: {txt[:300]}")
                            self.daily_limit_hit = True
                            await self._log(key, ok=False, err=f"{r.status}:{txt[:200]}")
                            return None
                        if r.status != 200:
                            raise aiohttp.ClientError(f"status {r.status}: {txt[:200]}")
                        js = json.loads(txt)
                        content = js["choices"][0]["message"]["content"] or ""
                        u = js.get("usage", {}) or {}
                        cost = float(u.get("cost", 0.0) or 0.0)
                        await self._log(key, ok=True, cost=cost, pt=u.get("prompt_tokens"), ct=u.get("completion_tokens"),
                                        content=content, dt=round(time.time() - t0, 2))
                        return content
                except (aiohttp.ClientError, asyncio.TimeoutError, KeyError, json.JSONDecodeError) as e:
                    logger.warning(f"{self.purpose} {key} attempt {attempt}: {repr(e)[:200]}")
                    await asyncio.sleep(2 ** attempt)
            await self._log(key, ok=False, err="retries exhausted")
            return None

    async def _log(self, key: str, ok: bool, cost: float = 0.0, **kw) -> None:
        async with self.lock:
            self.spent_purpose += cost
            self.spent_total += cost
            LEDGER.parent.mkdir(parents=True, exist_ok=True)
            with LEDGER.open("a") as f:
                f.write(json.dumps({"purpose": self.purpose, "key": key, "ok": ok, "cost": cost, "model": self.model,
                                    "ts": time.time(), **kw}, ensure_ascii=False) + "\n")
