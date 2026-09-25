"""(copied from iter-3 exp9 src/orclient.py; ledger path + cap changed, gpt reasoning off)
OpenRouter client: async calls, append-only ledger (results/judge_ledger.jsonl), HARD $ cap checked before every call.

Every paid call of this artifact (key probe, twin rewrites, SAFE screens, judge labels) goes through `run_jobs`, so the
ledger is the single source of truth for spend. Resumable: a job whose `key` already has a valid ledger row is skipped.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time

import aiohttp

from common import RESULTS, append_jsonl, read_jsonl

BASE = os.environ.get("OPENROUTER_BASE_URL", "").rstrip("/")
URL = f"{BASE}/chat/completions"
LEDGER = RESULTS / "ledger.jsonl"
HARD_CAP = 0.45  # A4: run key limit reached ($12.00 total, $0.199 left at 19:05 UTC); plan S7 stop was $4.75
SOFT_ALARM = 4.0
LAB = ["REFUSE", "PARTIAL", "COMPLY"]


def parse_label(text: str) -> str:
    """first word that starts like one of the 3 labels (case/whitespace/punctuation tolerant)."""
    for w in re.sub(r"[^A-Za-z]", " ", text or "").upper().split():
        for lab in LAB:
            if w.startswith(lab[:4]):
                return lab
    return "UNPARSED"


def parse_safe(text: str) -> str:
    for w in re.sub(r"[^A-Za-z]", " ", text or "").upper().split():
        if w.startswith("UNSAFE"):
            return "UNSAFE"
        if w.startswith("SAFE"):
            return "SAFE"
    return "UNPARSED"


def ledger_rows() -> list[dict]:
    return read_jsonl(LEDGER)


def spent_total() -> float:
    return float(sum(float(r.get("cost") or 0.0) for r in ledger_rows()))


def done_keys(valid: set[str] | None = None) -> dict:
    out = {}
    for r in ledger_rows():
        if r.get("status") == 200 and r.get("parsed") not in (None, "UNPARSED"):
            out[r["key"]] = r
        elif r.get("status") == 200 and r["key"] not in out and r.get("attempt_final"):
            out[r["key"]] = r  # parsed UNPARSED twice -> final
    return out


async def call(session, model: str, messages: list[dict], max_tokens: int = 5, temperature: float = 0.0) -> dict:
    headers = {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "Content-Type": "application/json"}
    body = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens,
            "usage": {"include": True}}
    if "gemini" in model:
        body["reasoning"] = {"max_tokens": 0}
    err = ""
    for attempt in range(5):
        try:
            async with session.post(URL, headers=headers, json=body, timeout=aiohttp.ClientTimeout(total=120)) as r:
                txt = await r.text()
                if r.status == 200:
                    j = json.loads(txt)
                    if "choices" not in j or not j["choices"]:
                        err = txt[:200]
                        await asyncio.sleep(2 ** attempt)
                        continue
                    msg = j["choices"][0]["message"].get("content") or ""
                    u = j.get("usage") or {}
                    rt = (u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
                    return {"status": 200, "raw": msg, "cost": float(u.get("cost") or 0.0),
                            "finish": j["choices"][0].get("finish_reason"), "reasoning_tokens": int(rt),
                            "prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens")}
                low = txt.lower()
                if r.status == 402 or "key limit" in low or "daily limit" in low or "insufficient" in low:
                    return {"status": r.status, "limit": True, "raw": txt[:200], "cost": 0.0}
                if r.status == 403:
                    return {"status": 403, "blocked": True, "raw": txt[:200], "cost": 0.0}
                if r.status in (408, 429, 500, 502, 503, 504):
                    err = txt[:200]
                    await asyncio.sleep(2 ** attempt + 1)
                    continue
                return {"status": r.status, "raw": txt[:200], "cost": 0.0}
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as e:
            err = str(e)[:200]
            await asyncio.sleep(2 ** attempt)
    return {"status": -1, "raw": err, "cost": 0.0, "retry_exhausted": True}


async def _run(jobs: list[dict], conc: int, cap: float, logger, parser) -> dict:
    done = done_keys()
    spent = spent_total()
    todo = [j for j in jobs if j["key"] not in done]
    if logger:
        logger.info(f"orclient: {len(jobs)} jobs, {len(todo)} to do; ledger spent ${spent:.4f} (cap ${cap})")
    state = {"spent": spent, "stop": False, "n": 0, "limit_hits": 0, "capped": 0}
    sem = asyncio.Semaphore(conc)
    buf: list[dict] = []
    results: dict = {k: v for k, v in done.items() if k in {j["key"] for j in jobs}}

    async def one(session, j):
        async with sem:
            if state["stop"]:
                return
            if state["spent"] >= cap:
                state["capped"] += 1
                return
            msgs = j.get("messages") or [{"role": "user", "content": j["content"]}]
            res = await call(session, j["judge"], msgs, j.get("max_tokens", 5))
            p = parser(res.get("raw", "")) if (res.get("status") == 200 and parser) else None
            final, extra = False, 0.0
            if res.get("status") == 200 and p == "UNPARSED":  # one retry, then final UNPARSED
                res2 = await call(session, j["judge"], msgs, j.get("max_tokens", 5))
                extra = float(res.get("cost") or 0.0)
                if res2.get("status") == 200:
                    res = res2
                    p = parser(res2.get("raw", ""))
                final = True
            if res.get("limit"):
                state["limit_hits"] += 1
                if state["limit_hits"] >= 3:
                    state["stop"] = True
            c = float(res.get("cost") or 0.0) + extra
            state["spent"] += c
            row = {"key": j["key"], "row_key": j.get("row_key"), "judge": j["judge"], "kind": j.get("kind"),
                   "parsed": p, "raw": (res.get("raw") or "")[:(4000 if j.get("keep_raw") else 40)],
                   "status": res.get("status"), "cost": c, "reasoning_tokens": res.get("reasoning_tokens"),
                   "prompt_tokens": res.get("prompt_tokens"), "attempt_final": final, "ts": round(time.time(), 1)}
            buf.append(row)
            if res.get("status") == 200:
                results[j["key"]] = row
            state["n"] += 1
            if len(buf) >= 200:
                append_jsonl(LEDGER, buf[:])
                buf.clear()
            if logger and state["n"] % 1000 == 0:
                logger.info(f"  orclient {state['n']} calls; spent ${state['spent']:.4f}")

    async with aiohttp.ClientSession() as session:
        for i in range(0, len(todo), 4000):
            await asyncio.gather(*[one(session, j) for j in todo[i:i + 4000]])
            if buf:
                append_jsonl(LEDGER, buf[:])
                buf.clear()
            if state["stop"]:
                break
    if logger:
        logger.info(f"orclient done: {state['n']} calls; spent ${state['spent']:.4f}; stop={state['stop']} "
                    f"capped={state['capped']}")
    state["results"] = results
    return state


def run_jobs(jobs: list[dict], conc: int = 32, cap: float = HARD_CAP, logger=None, parser=parse_label) -> dict:
    return asyncio.run(_run(jobs, conc, cap, logger, parser))
