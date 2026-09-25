#!/usr/bin/env python3
"""Async OpenRouter client with an append-only ledger (labels/ledger.jsonl), cache key
sha1(judge | prompt_sha | request | response_truncated) == sha1(judge | prompt_sha | content), resume on restart,
cumulative-$ printout every 200 calls and a HARD STOP at COST_CAP (default $8.00) summed over the WHOLE ledger.

Job dict: {cache: str, key: str (frame key), judge: model id, pass: str, content: str, max_tokens: int, prompt_sha: str}
"""
from __future__ import annotations

import asyncio
import json
import os
import time

import aiohttp
from loguru import logger

from common import COST_CAP, LABELS, parse3

LEDGER = LABELS / "ledger.jsonl"
URL = os.environ.get("OPENROUTER_BASE_URL", "").rstrip("/") + "/chat/completions"
HEADERS = {"Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY', '')}", "Content-Type": "application/json",
           "User-Agent": "aii-eval3/1.0 (python-aiohttp)"}  # Cloudflare in front of the proxy rejects UA-less requests


class CostCapReached(RuntimeError):
    pass


def ledger_load() -> tuple[dict, float]:
    done, cost = {}, 0.0
    if LEDGER.exists():
        for line in LEDGER.read_text().splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            cost += float(r.get("cost") or 0.0)
            if r.get("status") == "ok":
                done[r["cache"]] = r
    return done, cost


async def _call(session, judge: str, content: str, max_tokens: int, temperature: float = 0.0) -> dict:
    body = {"model": judge, "messages": [{"role": "user", "content": content}], "temperature": temperature,
            "max_tokens": max_tokens, "usage": {"include": True}}
    if "gemini" in judge:
        body["reasoning"] = {"max_tokens": 0}  # thinking OFF, as in exp8 judge.py
    err = ""
    for attempt in range(4):
        try:
            async with session.post(URL, headers=HEADERS, json=body, timeout=aiohttp.ClientTimeout(total=120)) as r:
                txt = await r.text()
                if r.status == 200:
                    j = json.loads(txt)
                    if "choices" not in j:
                        err = f"no choices: {txt[:200]}"
                        await asyncio.sleep(1 + attempt)
                        continue
                    ch = j["choices"][0]
                    msg = (ch.get("message") or {}).get("content") or ""
                    return {"text": msg, "finish": ch.get("finish_reason"), "cost": float((j.get("usage") or {}).get("cost") or 0.0),
                            "usage": {k: (j.get("usage") or {}).get(k) for k in ("prompt_tokens", "completion_tokens")},
                            "provider": j.get("provider"), "model_served": j.get("model")}
                err = f"HTTP {r.status}: {txt[:200]}"
                if r.status in (400, 401, 402, 403):
                    break
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as e:
            err = f"{type(e).__name__}: {e}"
        await asyncio.sleep(2 ** attempt)
    return {"text": "", "error": err, "cost": 0.0}


async def run_jobs(jobs: list[dict], conc: int = 32, cap: float = COST_CAP, parser=parse3, tag: str = "") -> dict:
    done, spent = ledger_load()
    todo = [j for j in jobs if j["cache"] not in done]
    logger.info(f"[{tag}] {len(jobs)} jobs, {len(jobs) - len(todo)} cached, {len(todo)} to call; ledger spend ${spent:.4f}")
    state = {"spent": spent, "n": 0, "stop": False, "t0": time.time()}
    sem = asyncio.Semaphore(conc)
    lock = asyncio.Lock()
    fh = LEDGER.open("a")

    async def one(session, j):
        if state["stop"]:
            return
        async with sem:
            if state["stop"]:
                return
            if state["spent"] >= cap:
                state["stop"] = True
                return
            res = await _call(session, j["judge"], j["content"], j["max_tokens"], j.get("temperature", 0.0))
            lab = parser(res.get("text", ""))
            if lab == "UNPARSEABLE" and not res.get("error"):  # retry once
                res2 = await _call(session, j["judge"], j["content"], j["max_tokens"], j.get("temperature", 0.0))
                res2["cost"] = res2.get("cost", 0.0) + res.get("cost", 0.0)
                res = res2
                lab = parser(res.get("text", ""))
            rec = {"cache": j["cache"], "key": j["key"], "judge": j["judge"], "pass": j["pass"], "prompt_sha": j["prompt_sha"],
                   "label_raw": res.get("text", "")[:400], "label": lab, "cost": res.get("cost", 0.0),
                   "usage": res.get("usage"), "finish": res.get("finish"), "error": res.get("error"),
                   "status": "ok" if not res.get("error") else "error", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
            async with lock:
                fh.write(json.dumps(rec) + "\n")
                state["spent"] += rec["cost"]
                state["n"] += 1
                if state["n"] % 200 == 0:
                    fh.flush()
                    rate = state["n"] / max(time.time() - state["t0"], 1e-6)
                    logger.info(f"[{tag}] {state['n']}/{len(todo)} calls, cumulative ${state['spent']:.4f}, {rate:.1f}/s")
                if state["spent"] >= cap:
                    state["stop"] = True
                    logger.error(f"HARD STOP: cumulative ${state['spent']:.4f} >= cap ${cap}")

    conn = aiohttp.TCPConnector(limit=conc * 2)
    async with aiohttp.ClientSession(connector=conn) as session:
        await asyncio.gather(*(one(session, j) for j in todo), return_exceptions=False)
    fh.close()
    logger.info(f"[{tag}] finished {state['n']} calls; cumulative ${state['spent']:.4f}")
    if state["stop"]:
        raise CostCapReached(f"cost cap reached at ${state['spent']:.4f}")
    return state


def labels_for(judge: str, pass_: str | None = None) -> dict:
    """cache -> ledger record for one judge (latest ok)."""
    done, _ = ledger_load()
    return {c: r for c, r in done.items() if r["judge"] == judge and (pass_ is None or r["pass"] == pass_)}
