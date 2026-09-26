#!/usr/bin/env python3
"""AM2 scheduler for the free-model phase: ONE process, a global rolling-window rate limiter (the OpenRouter free tier
allows 20 requests/min per key across all ':free' models), and a single priority queue:

  tier 1  decisive cells at hi (Gemma/GaMS x EN->SL/EN->EN; 50 rows each): adjudicator A, adjudicator B,
          StrongREJECT rubric on the original reply (SR_orig) and, for SL-output rows, on the NLLB translation (SR_tr)
  tier 2  the same at lo
  tier 3  Gemma SL->EN hi (40), Gemma/GaMS SL->SL hi (25 each): A, B, SR_orig (+SR_tr)
  tier 4  zero-dose decisive rows (10 each), exp15 window rows, extras (benign twins, eval3 bridge), retest
Tie-breaks (third model) are enqueued at top priority as soon as A and B disagree on a row.
All results append to labels/adjudication.jsonl and labels/sr_gemini.jsonl (same format as api_work.py)."""
from __future__ import annotations

import asyncio
import heapq
import itertools
import json
import sys
import time
from collections import defaultdict, deque
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent))
import api_work as aw
from common import E14, LABELS, PROMPTS, RESULTS, ORClient, append_jsonl, load_items, read_jsonl, setup_logging

RPM = 19
DEADLINE_MIN = float(sys.argv[1]) if len(sys.argv) > 1 else 100.0


class Limiter:
    def __init__(self, rpm: int):
        self.rpm = rpm
        self.t = deque()
        self.lock = asyncio.Lock()

    async def wait(self):
        async with self.lock:
            while True:
                now = time.time()
                while self.t and now - self.t[0] > 61:
                    self.t.popleft()
                if len(self.t) < self.rpm:
                    self.t.append(now)
                    return
                await asyncio.sleep(61 - (now - self.t[0]) + 0.05)


def tier_of(r: dict) -> int:
    s = r["stratum"]
    if r.get("retest_task"):
        return 9
    if s.startswith("core|") and ("|enen|" in s or "|ensl|" in s):
        return {"hi": 1, "lo": 3, "zero": 5}[s.split("|")[-1]]
    if s in ("core|gemma_it|slen|hi", "core|gemma_it|slsl|hi", "core|gams3_it|slsl|hi"):
        return 4
    if s.startswith("extra|benign0|"):  # AM3: zero-dose benign twins (FA validation for the lambda-0 criterion claim)
        return 0.6 if s.startswith("extra|benign0|gams3_it|enen") else 0.5  # AM6/AM10: first (hi rows have the sonnet ref)
    if s.startswith("core|e15"):
        return 6
    return 7


async def main_async() -> None:
    t_end = time.time() + DEADLINE_MIN * 60
    c = ORClient(concurrency=12)
    lim = Limiter(RPM)
    orig_call = c.call

    async def limited_call(*a, **k):
        # each HTTP attempt goes through the limiter (cached answers do not)
        return await orig_call(*a, **k)

    # patch the client's HTTP create with a limiter
    create = c.client.chat.completions.create

    async def lim_create(*a, **k):
        await lim.wait()
        return await create(*a, **k)

    c.client.chat.completions.create = lim_create
    tt = json.loads((RESULTS / "tier_table.json").read_text())
    pair = tt["adjudicators"]["pair"]
    A, B, C, CF = pair["A"], pair["B"], pair["third"], pair.get("third_fallback")
    BF = pair.get("B_fallback")
    rubric = (PROMPTS / "adjudication_rubric_v3.md").read_text()
    frame = aw.load_frame()
    items = load_items()
    tr = {r["key"]: r["translation"] for r in read_jsonl(E14 / "results/labels/ttj_translations.jsonl")}
    for r in read_jsonl(LABELS / "translations_new.jsonl"):
        tr[r["key"]] = r["translation"]
    done_adj = {(r["key"], r["rater"]) for r in read_jsonl(aw.ADJ_F) if r.get("label")}
    lab = defaultdict(dict)
    for r in read_jsonl(aw.ADJ_F):
        if r.get("label"):
            lab[r["key"]][r["rater"]] = r["label"]
    done_sr = {(r["key"], r["variant"]) for r in read_jsonl(aw.SRG_F) if r.get("parsed")}
    cnt = itertools.count()
    pq: list = []

    def push(pri, task):
        heapq.heappush(pq, (pri, next(cnt), task))

    only = __import__("os").environ.get("ONLY_STRATUM")
    if only:  # AM11: restrict the queue to one stratum
        frame = [r for r in frame if r["stratum"] == only]
    for r in frame:
        t = tier_of(r)
        for rater in ("A", "B"):
            if (r["key"], rater) not in done_adj:
                push((t, 0), ("adj", rater, r))
        if r["body"] == "exp14" and r["kind"] == "harmful" and t <= 5:
            fp = items[r["item_id"]]["EN_orig"]
            # AM5: the free Nemotron rubric now runs after AM3 and the lo-dose adjudication (gemini is the SR judge)
            if (r["key"], "orig") not in done_sr:
                push((max(t, 4) + 0.5, 1), ("sr", "orig", r, fp, r["reply"]))
            if r["out_lang"] != "en" and r["key"] in tr and (r["key"], "tr") not in done_sr:
                push((max(t, 4) + 0.5, 2), ("sr", "tr", r, fp, tr[r["key"]]))
        if r.get("retest") and (r["key"], "A_retest") not in done_adj:
            push((9, 0), ("adj", "A_retest", r))
    logger.info(f"free scheduler: {len(pq)} tasks queued; deadline {DEADLINE_MIN} min")

    def maybe_third(r):
        a, b = aw.binaries(lab[r["key"]].get("A")), aw.binaries(lab[r["key"]].get("B"))
        if a is None or b is None or "C" in lab[r["key"]]:
            return
        if any(a[x] != b[x] for x in ("R_any", "R_explicit", "U")) or lab[r["key"]]["A"]["class"] != lab[r["key"]]["B"]["class"]:
            push((0, 0), ("adj", "C", r))

    for r in frame:
        maybe_third(r)

    async def run_task(task):
        kind = task[0]
        if kind == "adj":
            rater, r = task[1], task[2]
            m = {"A": A, "B": B, "C": C, "A_retest": A}[rater]
            temp = 0.3 if rater == "A_retest" else 0.0
            o = await aw.adj_call(c, m, r, rubric, temperature=temp, nonce="retest" if rater == "A_retest" else "")
            if o["parsed"] is None and rater == "C" and CF:
                m = CF
                o = await aw.adj_call(c, m, r, rubric)
            if o["parsed"] is None and rater == "B" and BF:
                m = BF
                o = await aw.adj_call(c, m, r, rubric)
            append_jsonl(aw.ADJ_F, [{"key": r["key"], "fid": r["fid"], "rater": rater, "model": m, "label": o["parsed"],
                                     "raw": o["raw"] if o["parsed"] is None else None}])
            if o["parsed"] is not None and rater in ("A", "B", "C"):
                lab[r["key"]][rater] = o["parsed"]
                if rater in ("A", "B"):
                    maybe_third(r)
        else:
            _, variant, r, fp, resp = task
            o = await aw.sr_call(c, aw.FREE_SR, "full", fp, resp, f"sr|{r['key']}|{variant}")
            append_jsonl(aw.SRG_F, [{"key": r["key"], "variant": variant, "pri": "ADJ", "tier": "free_full",
                                     **(o["parsed"] or {}), "parsed": o["parsed"] is not None, "blocked": o["blocked"],
                                     "error": o.get("error")}])

    active: set = set()
    n_done = 0
    while (pq or active) and time.time() < t_end:
        while pq and len(active) < 12:
            _, _, task = heapq.heappop(pq)
            active.add(asyncio.create_task(run_task(task)))
        if not active:
            break
        done, active = await asyncio.wait(active, return_when=asyncio.FIRST_COMPLETED)
        for d in done:
            n_done += 1
            if d.exception():
                logger.error(f"task error: {d.exception()!r}")
        if n_done % 20 == 0:
            logger.info(f"free scheduler: {n_done} done, {len(pq)} queued, {len(active)} active")
    for a in active:
        a.cancel()
    logger.info(f"free scheduler stopped: {n_done} done, {len(pq)} left (deadline reached: {time.time() >= t_end})")


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("free_sched")
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
