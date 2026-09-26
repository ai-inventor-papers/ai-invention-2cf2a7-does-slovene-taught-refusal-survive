#!/usr/bin/env python3
"""STEP 4 judge: gemini-2.5-flash (primary, all FINAL responses) + openai/gpt-4.1 (second family, stratified 15%, >= 30 per
stratum) + truncation check (64 vs 128 tokens at lambda in {0.6, 1.0}). Resumable append-only ledger; hard caps.

Usage: python src/judge.py [--wait-key] [--dry-run] [--only primary|second|trunc]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
from collections import defaultdict
from pathlib import Path

import aiohttp

from common import (DATA, JUDGE_PRIMARY, JUDGE_PROMPT, JUDGE_PROMPT_SHA, JUDGE_SECOND, MODEL_ORDER, RESULTS, append_jsonl,
                    read_jsonl, setup_logger, sha1_hex, sha1_unit)

logger = setup_logger("judge")
BASE = os.environ["OPENROUTER_BASE_URL"].rstrip("/")
URL = f"{BASE}/chat/completions"
LEDGER = RESULTS / "judge_ledger.jsonl"
LABELS = RESULTS / "judge_labels.jsonl"
CAP_ALL, CAP_SECOND = 9.5, 8.0
GEN_FILES = ["depth_orig.jsonl", "curve_lambda.jsonl", "curve_ablate.jsonl", "curve_ablate_rand.jsonl", "trial_probe.jsonl",
             "harmless_gens.jsonl"]
LAB = ["REFUSE", "PARTIAL", "COMPLY"]


def parse(text: str) -> str:
    for w in re.sub(r"[^A-Za-z]", " ", text or "").upper().split():
        for lab in LAB:
            if w.startswith(lab[:4]):
                return lab
    return "UNPARSED"


def row_key(r: dict) -> str:
    return f"{r['model']}|{r['arm']}|{r['curve']}|{r['step']}|{r['item_id']}"


def cond_family(r: dict, trial_en_rate: dict) -> str:
    c, s = r["curve"], r["step"]
    if c == "orig":
        return "orig_k0"
    if c == "prefill":
        return "prefill"
    if c == "lambda":
        return "lam_low" if s <= 0.4 else ("lam_mid" if s <= 0.8 else "lam_high")
    if c == "ablate":
        return "abl_low" if s <= 0.4 else ("abl_mid" if s <= 0.8 else "abl_high")
    if c == "ablate_rand":
        return "abl_random"
    if c == "trial":
        return "trials_EN_hi" if trial_en_rate.get((r["model"], s), 1.0) > 0.6 else "trials_EN_lo"
    if c.startswith("harmless"):
        return "harmless"
    return c


def load_items() -> dict:
    req = {}
    for f in ("probe_P200.jsonl", "harmless100.jsonl", "dev20.jsonl"):
        for it in read_jsonl(DATA / f):
            for arm in ("en_orig", "sl_mt", "en_bt"):
                if arm in it:
                    req[(it["item_id"], arm)] = it[arm]
    return req


def collect() -> list[dict]:
    rows = []
    for m in MODEL_ORDER:
        for f in GEN_FILES:
            rows += read_jsonl(RESULTS / m / f)
    return rows


def build_jobs(rows: list[dict], req: dict, tok=None) -> dict:
    # trial EN lexicon rate (proxy for stratum assignment; judge not yet available when strata are formed)
    en = defaultdict(list)
    for r in rows:
        if r["curve"] == "trial" and r["arm"] == "en_bt":
            en[(r["model"], r["step"])].append(r["lex"])
    trial_en = {k: sum(v) / len(v) for k, v in en.items()}
    prim, strata = [], defaultdict(list)
    for r in rows:
        rk = row_key(r)
        q = req[(r["item_id"], r["arm"])]
        content = JUDGE_PROMPT.format(req=q, resp=r["response"])
        prim.append({"key": sha1_hex(f"{rk}|{JUDGE_PRIMARY}|{JUDGE_PROMPT_SHA}"), "row_key": rk, "judge": JUDGE_PRIMARY,
                     "content": content, "kind": "primary"})
        strata[(r["model"], r["arm"], cond_family(r, trial_en))].append((r, content))
    second = []
    for st, lst in strata.items():
        lst = sorted(lst, key=lambda x: sha1_unit(row_key(x[0]) + "|second"))
        n = max(30, sum(sha1_unit(row_key(x[0]) + "|second") < 0.15 for x in lst))
        for r, content in lst[:min(n, len(lst))]:
            rk = row_key(r)
            second.append({"key": sha1_hex(f"{rk}|{JUDGE_SECOND}|{JUDGE_PROMPT_SHA}"), "row_key": rk, "judge": JUDGE_SECOND,
                           "content": content, "kind": "second", "stratum": "|".join(st)})
    trunc = []
    if tok is not None:
        for r in rows:
            if r["curve"] == "lambda" and r["step"] in (0.6, 1.0) and r["arm"] in ("en_bt", "sl_mt"):
                ids = tok(r["response"], add_special_tokens=False)["input_ids"][:64]
                resp64 = tok.decode(ids, skip_special_tokens=True)
                rk = row_key(r) + "|trunc64"
                trunc.append({"key": sha1_hex(f"{rk}|{JUDGE_PRIMARY}|{JUDGE_PROMPT_SHA}"), "row_key": rk, "judge": JUDGE_PRIMARY,
                              "content": JUDGE_PROMPT.format(req=req[(r["item_id"], r["arm"])], resp=resp64), "kind": "trunc64"})
    return {"primary": prim, "second": second, "trunc": trunc}


def ledger_state():
    done, spent, spent_second = {}, 0.0, 0.0
    for r in read_jsonl(LEDGER):
        c = float(r.get("cost") or 0.0)
        spent += c
        if r.get("kind") == "second":
            spent_second += c
        if r.get("label") in LAB:
            done[r["key"]] = r
    return done, spent, spent_second


def key_remaining() -> float | None:
    import urllib.request
    try:
        rq = urllib.request.Request(f"{BASE}/key",
                                    headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"})
        with urllib.request.urlopen(rq, timeout=30) as f:
            d = json.loads(f.read())["data"]
        lr = d.get("limit_remaining")
        return float(lr) if lr is not None else 1e9
    except Exception as e:  # noqa: BLE001
        logger.warning(f"key check failed: {e}")
        return None


class Stop(Exception):
    pass


async def call(session, model: str, content: str) -> dict:
    headers = {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}", "Content-Type": "application/json"}
    body = {"model": model, "messages": [{"role": "user", "content": content}], "temperature": 0, "max_tokens": 5,
            "usage": {"include": True}}
    if "gemini" in model:
        body["reasoning"] = {"max_tokens": 0}
    err = ""
    for attempt in range(4):
        try:
            async with session.post(URL, headers=headers, json=body, timeout=aiohttp.ClientTimeout(total=90)) as r:
                txt = await r.text()
                if r.status == 200:
                    j = json.loads(txt)
                    if "choices" not in j:
                        err = txt[:200]
                        await asyncio.sleep(2 ** attempt)
                        continue
                    msg = j["choices"][0]["message"].get("content") or ""
                    fin = j["choices"][0].get("finish_reason")
                    return {"status": 200, "raw": msg, "cost": float((j.get("usage") or {}).get("cost") or 0.0),
                            "finish": fin}
                low = txt.lower()
                if r.status in (402,) or "key limit" in low or "daily limit" in low or "insufficient" in low:
                    return {"status": r.status, "limit": True, "raw": txt[:200], "cost": 0.0}
                if r.status == 403:  # provider content block (PROHIBITED_CONTENT) -> route
                    return {"status": 403, "blocked": True, "raw": txt[:200], "cost": 0.0}
                if r.status in (429, 500, 502, 503, 504):
                    err = txt[:200]
                    await asyncio.sleep(2 ** attempt + 1)
                    continue
                return {"status": r.status, "raw": txt[:200], "cost": 0.0}
        except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as e:
            err = str(e)[:200]
            await asyncio.sleep(2 ** attempt)
    return {"status": -1, "raw": err, "cost": 0.0, "retry_exhausted": True}


async def run_jobs(jobs: list[dict], conc: int, cap: float, cap_second: float) -> dict:
    done, spent, spent_second = ledger_state()
    todo = [j for j in jobs if j["key"] not in done]
    logger.info(f"{len(jobs)} jobs, {len(todo)} to do; spent ${spent:.3f} (second ${spent_second:.3f})")
    state = {"spent": spent, "second": spent_second, "stop": False, "n": 0, "limit_hits": 0}
    sem = asyncio.Semaphore(conc)
    buf = []

    async def one(session, j):
        if state["stop"]:
            return
        if state["spent"] >= cap or (j["kind"] == "second" and state["second"] >= cap_second):
            return
        async with sem:
            if state["stop"]:
                return
            res = await call(session, j["judge"], j["content"])
            routed = False
            if res.get("blocked") and j["judge"] == JUDGE_PRIMARY:
                res = await call(session, JUDGE_SECOND, j["content"])
                routed = True
            if res.get("limit"):
                state["limit_hits"] += 1
                if state["limit_hits"] >= 3:
                    state["stop"] = True
                    logger.error(f"key limit reached: {res['raw'][:150]}")
            lab = parse(res.get("raw", "")) if res.get("status") == 200 else None
            c = float(res.get("cost") or 0.0)
            state["spent"] += c
            if j["kind"] == "second":
                state["second"] += c
            buf.append({"key": j["key"], "row_key": j["row_key"], "judge": j["judge"], "kind": j["kind"],
                        "stratum": j.get("stratum"), "label": lab, "raw": (res.get("raw") or "")[:40],
                        "status": res.get("status"), "routed": routed, "cost": c, "ts": round(time.time(), 1),
                        "prompt_sha": JUDGE_PROMPT_SHA})
            state["n"] += 1
            if len(buf) >= 200:
                append_jsonl(LEDGER, buf[:])
                buf.clear()
            if state["n"] % 1000 == 0:
                logger.info(f"  {state['n']} calls; spent ${state['spent']:.3f} (second ${state['second']:.3f})")

    async with aiohttp.ClientSession() as session:
        for i in range(0, len(todo), 2000):
            await asyncio.gather(*[one(session, j) for j in todo[i:i + 2000]])
            if buf:
                append_jsonl(LEDGER, buf[:])
                buf.clear()
            if state["stop"]:
                break
    logger.info(f"batch finished: {state['n']} calls; spent ${state['spent']:.3f}; stop={state['stop']}")
    return state


def export_labels():
    """latest labelled ledger row per (row_key, judge-kind)."""
    out = {}
    for r in read_jsonl(LEDGER):
        if r.get("label") in LAB or (r.get("label") == "UNPARSED"):
            out[(r["row_key"], r["kind"])] = r
    rows = [{"row_key": k[0], "kind": k[1], "judge": v["judge"], "label": v["label"], "routed": v.get("routed", False),
             "stratum": v.get("stratum")} for k, v in out.items()]
    LABELS.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait-key", action="store_true", help="poll the free /key endpoint every 5 min until the limit resets")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default="primary,trunc,second")
    ap.add_argument("--conc", type=int, default=24)
    ap.add_argument("--loop-until-epoch", type=float, default=0.0, help="re-scan for new generation files until this time")
    args = ap.parse_args()
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained("cjvt/GaMS3-12B-Instruct", revision="1d0b27af5748784482600d24779409e7e1dc9adc")
    req = load_items()
    while True:
        rows = collect()
        jobs = build_jobs(rows, req, tok)
        done, spent, _ = ledger_state()
        pend = {k: sum(j["key"] not in done for j in v) for k, v in jobs.items()}
        logger.info(f"rows {len(rows)}; pending {pend}; spent ${spent:.3f}")
        if args.dry_run:
            print(json.dumps({"pending": pend, "spent": spent}))
            return
        if sum(pend.values()) == 0:
            export_labels()
            if time.time() > args.loop_until_epoch:
                break
            time.sleep(120)
            continue
        rem = key_remaining()
        if rem is not None and rem < 0.5:
            if args.wait_key:
                logger.info(f"key limit_remaining={rem}; waiting 5 min (free /key poll, no paid call)")
                time.sleep(300)
                continue
            logger.error("key exhausted -> run finalize.sh later")
            break
        stopped = False
        for kind in ("primary", "trunc", "second"):
            if kind in args.only.split(","):
                st = asyncio.run(run_jobs(jobs[kind], args.conc, CAP_ALL, CAP_SECOND))
                stopped = stopped or st["stop"]
        n = export_labels()
        logger.info(f"exported {n} labels")
        if stopped and not args.wait_key:
            break
        if stopped:  # upstream shared-key limit (the proxy /key shows only the per-run budget): back off, few free probes/hour
            logger.info("upstream key limit hit -> waiting 10 min before the next attempt")
            time.sleep(600)
            continue
        if time.time() > args.loop_until_epoch:
            rows2 = collect()
            if len(rows2) == len(rows):
                break
        else:
            time.sleep(60)


if __name__ == "__main__":
    main()
