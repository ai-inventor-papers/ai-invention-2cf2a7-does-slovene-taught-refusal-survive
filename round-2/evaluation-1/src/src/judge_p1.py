#!/usr/bin/env python3
"""PAID PIPELINE (planned Tiers A/B/C; NOT executed in this session because the shared OpenRouter key was exhausted,
limit_remaining = 0 until 2026-09-24T00:00Z). Resumable, append-only, cost-capped. Run via ../run_all.sh.

  --tier A : gemini-2.5-flash, P1 verbatim, on every registry row WITHOUT a real P1 label (both models, all artifacts),
             queued model-interleaved per cell (a key outage never leaves a cell judged for one model only).
  --tier B : openai/gpt-4.1 under P1 on a stratified sample per cell: n = max(ceil(.15 n), min(n, 40)), gemini minority
             class topped up to >= min(10, available), seed 20260924; + the 480 identity answers under ID_PROMPT;
             + 1,000 exp2 induction rows under exp2's OWN prompt (verbatim), stratified by cell.
  --tier C : (i) prefill continuation-only P1 relabel (gemini); (ii) M3 translate-then-judge: 400 SL responses
             (100 per model x {exp1 natural SL, exp1 SL-MT arm}, stratified by P1 label) + their requests translated to
             English by gemini-2.5-flash, then P1-judged; (iii) exp4 JP2 for GaMS cells (so both models have JP2).
Ledger: labels/ledger.jsonl, key = sha1(prompt_version|judge|req|resp); cost from usage.cost; hard stop at $9.0 total.
Before any tier: GET /api/v1/key; if limit_remaining < $8 only Tier A runs; if it is 0 nothing runs (exit code 3).
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import json
import math
import os
import random
import re
import sys
import time

import aiohttp
from loguru import logger

from common import (EXP1, EXP2, EXP4, JUDGE_PROMPT, ID_PROMPT, LABELS, WORK, parse_refusal, read_jsonl, setup_logging,
                    sha1)

URL = "https://openrouter.ai/api/v1/chat/completions"
CAP_TOTAL = 9.0
LEDGER = LABELS / "ledger.jsonl"
GEMINI, GPT41 = "google/gemini-2.5-flash", "openai/gpt-4.1"
EXP2_PROMPT = (EXP2 / "src/judge.py").read_text().split('PROMPT = """', 1)[1].split('"""', 1)[0]  # verbatim
import ast as _ast
JP2 = next(_ast.literal_eval(n.value) for n in _ast.parse((EXP4 / "src/judge.py").read_text()).body
           if isinstance(n, _ast.Assign) and getattr(n.targets[0], "id", "") == "JP2")  # verbatim exp4 JP2
ID_LABELS = ["GaMS", "Gemma", "ChatGPT", "Qwen", "Claude", "other", "none"]


def parse_id(text: str) -> str:
    t = text.strip().strip(".*'\"").lower()
    for lab in ID_LABELS:
        if t.startswith(lab.lower()):
            return lab
    for lab in ID_LABELS:
        if lab.lower() in t:
            return lab
    return "ChatGPT" if ("openai" in t or "gpt" in t) else "UNPARSED"


def parse_json_label(text: str) -> str:
    m = re.search(r'"label"\s*:\s*"(refuse|partial|comply)"', text or "", re.I)
    return m.group(1).upper() if m else parse_refusal(text or "")


class Ledger:
    def __init__(self) -> None:
        self.rows = {r["key"]: r for r in read_jsonl(LEDGER)}
        self.spent = sum(float(r.get("cost") or 0) for r in self.rows.values())
        self.lock = asyncio.Lock()
        self.stop = ""

    async def add(self, row: dict) -> None:
        async with self.lock:
            self.rows[row["key"]] = row
            self.spent += float(row.get("cost") or 0)
            with LEDGER.open("a") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            if self.spent >= CAP_TOTAL:
                self.stop = f"cost cap ${CAP_TOTAL} reached ({self.spent:.3f})"


def key_probe() -> float:
    import urllib.request
    req = urllib.request.Request("https://openrouter.ai/api/v1/key", headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"})
    d = json.loads(urllib.request.urlopen(req, timeout=30).read())["data"]
    rem = d.get("limit_remaining")
    logger.info(f"key probe: limit {d.get('limit')} remaining {rem} usage_daily {d.get('usage_daily')}")
    return float("inf") if rem is None else float(rem)


async def call(session, model: str, content: str, max_tokens: int) -> dict:
    payload = {"model": model, "messages": [{"role": "user", "content": content}], "max_tokens": max_tokens,
               "temperature": 0, "usage": {"include": True}}
    if model.startswith("google/gemini-2.5"):
        payload["reasoning"] = {"max_tokens": 0}
    hdr = {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"}
    last = ""
    for att in range(5):
        try:
            async with session.post(URL, json=payload, headers=hdr, timeout=aiohttp.ClientTimeout(total=90)) as r:
                txt = await r.text()
                if "PROHIBITED_CONTENT" in txt.upper():
                    return {"blocked": True}
                if r.status in (402, 403) or (r.status == 429 and "day" in txt.lower()):
                    return {"dead": f"HTTP {r.status}: {txt[:200]}"}
                if r.status == 429 or r.status >= 500:
                    last = f"{r.status}"
                    await asyncio.sleep(2 ** att)
                    continue
                d = json.loads(txt)
                if "error" in d:
                    last = str(d["error"])[:200]
                    await asyncio.sleep(2 ** att)
                    continue
                u = d.get("usage") or {}
                return {"text": (d["choices"][0]["message"].get("content") or "").strip(), "cost": float(u.get("cost") or 0.0),
                        "pt": u.get("prompt_tokens"), "ct": u.get("completion_tokens")}
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError, KeyError) as e:
            last = f"{type(e).__name__}: {e}"
            await asyncio.sleep(2 ** att)
    return {"error": last}


async def run(jobs: list[dict], led: Ledger, conc: int = 32) -> collections.Counter:
    st = collections.Counter()
    sem = asyncio.Semaphore(conc)
    t0 = time.time()
    async with aiohttp.ClientSession() as s:
        async def one(j):
            if j["key"] in led.rows or led.stop:
                st["skipped"] += 1
                return
            async with sem:
                if led.stop:
                    return
                res = await call(s, j["model"], j["content"], j["max_tokens"])
                if "dead" in res:
                    led.stop = res["dead"]
                    return
                if res.get("blocked") and j.get("fallback_model"):
                    res = await call(s, j["fallback_model"], j["content"], j["max_tokens"])
                    res["fallback"] = True
                if "text" not in res:
                    st["failed"] += 1
                    return
                lab = j["parse"](res["text"])
                if lab == "UNPARSED" and not j.get("retried"):
                    res = await call(s, j["model"], j["content"] + "\nAnswer with ONE word only.", j["max_tokens"])
                    lab = j["parse"](res.get("text", "")) if "text" in res else "UNPARSED"
                await led.add({"key": j["key"], "uid": j.get("uid"), "task": j["task"], "judge": j["model"], "label": lab,
                               "raw": res.get("text", "") if j["task"] == "C_translate" else res.get("text", "")[:120], "fallback": bool(res.get("fallback")), "cost": res.get("cost", 0.0),
                               "prompt_tokens": res.get("pt"), "completion_tokens": res.get("ct")})
                st["done"] += 1
                if st["done"] == 200:
                    per = led.spent / max(1, st["done"])
                    logger.info(f"$/call after 200: {per:.6f}; projected tier cost ${per * len(jobs):.2f}")
                    if led.spent + per * (len(jobs) - 200) > CAP_TOTAL:
                        led.stop = "projection exceeds cap"
                if st["done"] % 1000 == 0:
                    logger.info(f"{st['done']} done, ${led.spent:.3f}, {time.time() - t0:.0f}s")
        await asyncio.gather(*(one(j) for j in jobs))
    st["stop_reason"] = led.stop or "completed"
    return st


def p1_job(r: dict, model: str, task: str, resp: str | None = None, req: str | None = None) -> dict:
    req = req if req is not None else r["req"]
    resp = resp if resp is not None else r["resp"]
    return {"key": sha1(f"P1|{model}|{req}|{resp}"), "uid": r["uid"], "task": task, "model": model,
            "content": JUDGE_PROMPT.format(req=req, resp=resp), "max_tokens": 5, "parse": parse_refusal,
            "fallback_model": GPT41 if model == GEMINI else None}


def interleave(rows: list[dict]) -> list[dict]:
    """per (artifact, cell, lang) cell, alternate the two models so a stop never leaves a one-model cell."""
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in rows:
        by[(r["artifact"], r["cell"], r["lang"])][r["model"]].append(r)
    out = []
    for k in sorted(by):
        a, b = by[k].get("gemma_it", []), by[k].get("gams3_it", [])
        for i in range(max(len(a), len(b))):
            out += ([a[i]] if i < len(a) else []) + ([b[i]] if i < len(b) else [])
    return out


def tier_a(R):
    order = {"exp4": 0, "exp3": 1, "exp1": 2, "exp2": 3}
    rows = sorted([r for r in R if r.get("label_P1_real") is None], key=lambda r: order[r["artifact"]])
    return [p1_job(r, GEMINI, "A_census") for r in interleave(rows)]


def tier_b(R):
    rng = random.Random(20260924)
    by = collections.defaultdict(list)
    for r in R:
        by[(r["artifact"], r["model"], r["cell"].split(":")[0], r["lang"])].append(r)
    jobs = []
    for k, rows in sorted(by.items()):
        n = len(rows)
        take = max(math.ceil(0.15 * n), min(n, 40))
        rows = sorted(rows, key=lambda r: r["uid"])
        rng.shuffle(rows)
        pick = rows[:take]
        mino = [r for r in rows[take:] if r.get("gem_label") in ("COMPLY", "PARTIAL")]
        need = max(0, min(10, len([r for r in rows if r.get("gem_label") in ("COMPLY", "PARTIAL")])) -
                   len([r for r in pick if r.get("gem_label") in ("COMPLY", "PARTIAL")]))
        pick += mino[:need]
        jobs += [dict(p1_job(r, GPT41, "B_second_family"), weight=n / take) for r in pick]
    items = {r["iid"]: r for r in read_jsonl(EXP1 / "data/identity_items.jsonl")}
    for mk in ("gemma_it", "gams3_it"):
        for r in read_jsonl(EXP1 / f"outputs/identity_{mk}.jsonl"):
            q = items[r["iid"]][f"text_{r['lang']}"]
            jobs.append({"key": sha1(f"ID|{GPT41}|{mk}|{r['key']}|{r['response']}"), "uid": f"id|{mk}|{r['key']}", "task": "B_identity",
                         "model": GPT41, "content": ID_PROMPT.format(q=q, resp=r["response"]), "max_tokens": 5, "parse": parse_id})
    alp = {a["hid"]: a for a in read_jsonl(EXP2 / "data/alpaca_harmless.jsonl")}
    ind = []
    for m in ("gemma", "gams"):
        ind += [dict(r, m=m) for r in read_jsonl(EXP2 / f"results/inst_{m}/induction.jsonl") if r.get("alpha_k", -1) >= 0]
    rng.shuffle(ind)
    ind = sorted(ind, key=lambda r: (r["direction"] != "pt", r["m"], r["lang"]))[:1000]
    for r in ind:
        c = EXP2_PROMPT.format(req=alp[r["hid"]][r["lang"]][:3000], resp=r["text"][:2000] or "(empty)")
        jobs.append({"key": sha1(f"EXP2|{GPT41}|{r['m']}|{r['direction']}|{r['alpha_k']}|{r['hid']}|{r['lang']}"),
                     "uid": f"ind|{r['m']}|{r['direction']}|{r['alpha_k']}|{r['hid']}|{r['lang']}", "task": "B_induction",
                     "model": GPT41, "content": c, "max_tokens": 60, "parse": parse_json_label})
    return jobs


def tier_c(R, led: Ledger):
    jobs = [p1_job(r, GEMINI, "C_prefill_cont", resp=r["cont"]) for r in interleave([r for r in R if r.get("cont")])]
    jobs += [{"key": sha1(f"JP2|{GEMINI}|{r['req']}|{r['resp']}"), "uid": r["uid"], "task": "C_jp2_gams", "model": GEMINI,
              "content": JP2.format(req=r["req"], resp=r["resp"]), "max_tokens": 20, "parse": parse_json_label}
             for r in R if r["artifact"] == "exp4" and r["model"] == "gams3_it"]
    return jobs


async def tier_c_translate(R, led: Ledger) -> None:
    """M3: translate 400 SL responses + requests to EN (gemini), then P1-judge the translated pair."""
    rng = random.Random(20260924)
    pool = collections.defaultdict(list)
    for r in R:
        if r["artifact"] == "exp1" and r["lang"] in ("sl", "slmt") and r.get("label_P1_real"):
            pool[(r["model"], r["cell"])].append(r)
    pick = []
    for k, rows in sorted(pool.items()):
        ref = [r for r in rows if r["label_P1_real"] == "REFUSE"]
        non = [r for r in rows if r["label_P1_real"] != "REFUSE"]
        rng.shuffle(ref)
        rng.shuffle(non)
        pick += non[:50] + ref[:100 - min(50, len(non))]
    tr = lambda t: ("Translate the following text faithfully into English. Do not answer it, do not add anything. "
                    f"Text: <<<{t}>>>")
    jobs = []
    for r in pick:
        for part in ("req", "resp"):
            jobs.append({"key": sha1(f"TR|{GEMINI}|{r[part]}"), "uid": f"{r['uid']}|{part}", "task": "C_translate",
                         "model": GEMINI, "content": tr(r[part]), "max_tokens": 400, "parse": lambda t: t})
    await run(jobs, led, 16)
    tx = {r["key"]: r for r in led.rows.values() if r["task"] == "C_translate"}
    jj = []
    for r in pick:
        a, b = tx.get(sha1(f"TR|{GEMINI}|{r['req']}")), tx.get(sha1(f"TR|{GEMINI}|{r['resp']}"))
        if a and b:
            jj.append(p1_job(r, GEMINI, "C_translated_P1", resp=b["raw"], req=a["raw"]))
    await run(jj, led, 16)


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", choices=["A", "B", "C", "ALL"], default="ALL")
    a = ap.parse_args()
    setup_logging("judge_p1")
    rem = key_probe()
    if rem <= 0.05:
        logger.error("key exhausted (limit_remaining ~ 0): nothing run; statistics stay on $0 readouts, cells PENDING")
        sys.exit(3)
    R = read_jsonl(WORK / "registry.jsonl.gz")
    led = Ledger()
    gem = {r["uid"]: r["label"] for r in led.rows.values() if r["task"] == "A_census"}
    for r in R:
        r["label_P1_real"] = r.get("label_P1_exact") or (r["native_label"] if r["artifact"] == "exp1" else None)
        r["gem_label"] = r["label_P1_real"] or gem.get(r["uid"])
    tiers = ["A", "B", "C"] if a.tier == "ALL" else [a.tier]
    if rem < 8.0 and a.tier == "ALL":
        tiers = ["A"]
        logger.warning(f"remaining limit ${rem:.2f} < $8: Tier A only (pre-registered)")
    for t in tiers:
        jobs = tier_a(R) if t == "A" else tier_b(R) if t == "B" else tier_c(R, led)
        logger.info(f"tier {t}: {len(jobs)} jobs; spent so far ${led.spent:.3f}")
        st = asyncio.run(run(jobs, led))
        logger.info(f"tier {t}: {dict(st)}")
        if t == "C" and not led.stop and led.spent < 8.0:
            asyncio.run(tier_c_translate(R, led))
        if led.stop:
            logger.error(f"STOP: {led.stop}; rerun resumes from {LEDGER}")
            break


if __name__ == "__main__":
    main()
