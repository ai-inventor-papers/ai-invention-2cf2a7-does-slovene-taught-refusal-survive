#!/usr/bin/env python3
"""OpenRouter judge: gemini-2.5-flash (primary, all judged rows) + gpt-4.1-mini (second family, 20% stratified sample).
Frozen 3-way prompt (exp8 common.JUDGE_PROMPT verbatim; sha256 stored with every label). Append-only label file and
cost ledger; HARD STOP at $9.00 cumulative for this artifact. Resumable (a row+judge already labelled is never re-sent).

Usage:
  .venv/bin/python src/judge.py --probe                       # one call; asserts completion_tokens <= 5; logs cost
  .venv/bin/python src/judge.py --smoke                       # T2: re-judge 30 archived exp8 gemini rows (agreement >= .9)
  .venv/bin/python src/judge.py --model gemma_it --kind primary|second|both
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aiohttp  # noqa: E402

from common import (DATA, EXP8, JUDGE_PRIMARY, JUDGE_PROMPT, JUDGE_PROMPT_SHA, JUDGE_SECOND, LAB, RESULTS,  # noqa: E402
                    append_jsonl, parse_label, read_jsonl, row_key, setup_logger, sha1_unit)

from loguru import logger  # noqa: E402

BASE = os.environ.get("OPENROUTER_BASE_URL", "").rstrip("/")
URL = f"{BASE}/chat/completions"
LEDGER = RESULTS / "judge_ledger.jsonl"
LABELS = RESULTS / "judge_labels.jsonl"
CAP = 9.00
CONC = 16
rk = row_key
_REQ = None


def req_map() -> dict:
    global _REQ
    if _REQ is None:
        _REQ = {}
        for fp in DATA.glob("*.jsonl"):
            if fp.name.startswith("_"):
                continue
            for it in read_jsonl(fp):
                for arm in ("en_orig", "en_bt", "sl_mt"):
                    if arm in it:
                        _REQ[(it["item_id"], arm)] = it[arm]
    return _REQ


def ledger_spent() -> float:
    rows = read_jsonl(LEDGER)
    return float(rows[-1]["cum_cost"]) if rows else 0.0


def load_labels(judge: str | None = None) -> dict:
    """(row_key, judge) -> label (last valid wins)."""
    out = {}
    for r in read_jsonl(LABELS):
        if judge and r["judge"] != judge:
            continue
        out[(r["row_key"], r["judge"])] = r["label"]
    return out


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
                    u = j.get("usage") or {}
                    return {"status": 200, "raw": msg, "cost": float(u.get("cost") or 0.0),
                            "ptok": u.get("prompt_tokens"), "ctok": u.get("completion_tokens")}
                low = txt.lower()
                if r.status == 402 or "limit" in low and r.status in (401, 403, 429) and "rate" not in low:
                    return {"status": r.status, "limit": True, "raw": txt[:300], "cost": 0.0}
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
    return {"status": -1, "raw": err, "cost": 0.0}


async def run_jobs(jobs: list[dict], tag: str) -> dict:
    """jobs: {row_key, judge, content}. Returns counts; appends labels + ledger."""
    state = {"spent": ledger_spent(), "stop": False, "n": 0, "limit": 0}
    sem = asyncio.Semaphore(CONC)
    buf, t0 = [], time.time()

    async def one(session, j):
        if state["stop"]:
            return
        async with sem:
            if state["stop"] or state["spent"] >= CAP:
                state["stop"] = True
                return
            res = await call(session, j["judge"], j["content"])
            lab = parse_label(res.get("raw", "")) if res["status"] == 200 else ("BLOCKED" if res.get("blocked") else "ERROR")
            if res["status"] == 200 and lab == "UNPARSED":  # malformed -> 1 retry
                res2 = await call(session, j["judge"], j["content"])
                res["cost"] += res2.get("cost", 0.0)
                if res2["status"] == 200:
                    lab = parse_label(res2.get("raw", ""))
                    res["raw"] = res2.get("raw", "")
            if res.get("limit"):
                state["limit"] += 1
                if state["limit"] >= 3:
                    state["stop"] = True
                    logger.error(f"judge key limit hit: {res.get('raw')}")
                return
            state["spent"] += res.get("cost", 0.0)
            state["n"] += 1
            if lab in LAB or lab in ("UNPARSED", "BLOCKED"):
                buf.append({"row_key": j["row_key"], "judge": j["judge"], "label": lab, "raw": (res.get("raw") or "")[:40],
                            "cost": res.get("cost", 0.0), "prompt_sha": JUDGE_PROMPT_SHA})
            if len(buf) >= 200:
                flush()

    def flush():
        if not buf:
            return
        append_jsonl(LABELS, list(buf))
        append_jsonl(LEDGER, [{"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "tag": tag, "judge": buf[0]["judge"],
                               "n_rows": len(buf), "cost": sum(b["cost"] for b in buf), "cum_cost": state["spent"]}])
        buf.clear()

    async with aiohttp.ClientSession() as session:
        await asyncio.gather(*[one(session, j) for j in jobs], return_exceptions=False)
    flush()
    logger.info(f"judge {tag}: {state['n']} calls in {time.time() - t0:.0f}s, cum ${state['spent']:.3f} stop={state['stop']}")
    return state


def build_jobs(rows: list[dict], judge: str) -> list[dict]:
    have = load_labels(judge)
    req = req_map()
    jobs, seen = [], set()
    for r in rows:
        k = rk(r)
        if (k, judge) in have and have[(k, judge)] in LAB or k in seen:
            continue
        seen.add(k)
        q = req[(r["item_id"], r["arm"])]
        jobs.append({"row_key": k, "judge": judge, "content": JUDGE_PROMPT.format(req=q, resp=r["response"])})
    return jobs


def judge_rows_sync(rows: list[dict], block_name: str, judge: str = JUDGE_PRIMARY) -> dict:
    """judge (if needed) and return {row_key: label} for these rows. Missing labels -> 'ERROR'."""
    jobs = build_jobs(rows, judge)
    if jobs:
        asyncio.run(run_jobs(jobs, block_name))
    have = load_labels(judge)
    return {rk(r): have.get((rk(r), judge), "ERROR") for r in rows}


def family(r: dict) -> str:
    b, c = r["block"], r["cond"]
    if b == "induce":
        if c == "baseline":
            return "orig"
        return "induce_rand" if c.startswith("rand") else "induce_real"
    if b == "addon":
        if c == "O":
            return "orig"
        if c == "E0":
            return "edit"
        return "addon_rand" if c.startswith("R") else "addon_real"
    return b


def alpha_bin(r: dict) -> str:
    if r["block"] != "induce":
        return "na"
    s = float(r["step"])
    return "lo" if s <= 0.5 else ("mid" if s <= 1.5 else "hi")


def second_sample(rows: list[dict], frac: float = 0.10, min_cell: int = 60) -> list[dict]:  # 20% -> 10% (time; Qwen ~5 rows/s)
    strata = defaultdict(list)
    for r in rows:
        strata[(r["model"], r["lang"], family(r), alpha_bin(r))].append(r)
    out = []
    for st, lst in strata.items():
        lst = sorted(lst, key=lambda x: sha1_unit(rk(x) + "|second"))
        n = max(int(round(frac * len(lst))), min(min_cell // 2, len(lst)))
        out += lst[:n]
    return out


def test_rows(model: str) -> list[dict]:
    rows = []
    for fn in ("induce.jsonl", "addon.jsonl"):
        rows += read_jsonl(RESULTS / "test" / model / fn)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--model")
    ap.add_argument("--kind", default="both")
    ap.add_argument("--wait-file", default="")
    a = ap.parse_args()
    setup_logger("judge")
    if a.wait_file:
        while not Path(a.wait_file).exists():
            time.sleep(20)
    if a.probe:
        async def pr():
            async with aiohttp.ClientSession() as s:
                return await call(s, JUDGE_PRIMARY, JUDGE_PROMPT.format(req="How do I bake bread?", resp="I'm sorry, I can't help."))
        res = asyncio.run(pr())
        logger.info(f"probe: {res}")
        append_jsonl(LEDGER, [{"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "tag": "probe", "judge": JUDGE_PRIMARY, "n_rows": 1,
                               "cost": res.get("cost", 0.0), "cum_cost": ledger_spent() + res.get("cost", 0.0)}])
        (RESULTS / "judge_probe.json").write_text(json.dumps(res, indent=2))
        assert res["status"] == 200 and (res.get("ctok") or 0) <= 5, res
        return
    if a.smoke:
        # T2: 30 archived exp8 Gemma rows with gemini labels (stratified REFUSE / non-REFUSE), same prompt text
        arch = {r["row_key"]: r["label"] for r in read_jsonl(EXP8 / "results/judge_labels.jsonl")
                if r["kind"] == "primary" and r["judge"] == JUDGE_PRIMARY and r["label"] in LAB}
        p200 = {r["item_id"]: r for r in read_jsonl(EXP8 / "data/probe_P200.jsonl")}
        gens = [g for g in read_jsonl(EXP8 / "results/gemma_it/curve_lambda.jsonl") if g["arm"] in ("en_bt", "sl_mt")]
        cand = []
        for g in gens:
            k = f"gemma_it|{g['arm']}|{g['curve']}|{g['step']}|{g['item_id']}"
            if k in arch and g["item_id"] in p200:
                cand.append((sha1_unit(k + "smoke"), k, g))
        cand.sort()
        ref = [c for c in cand if arch[c[1]] == "REFUSE"][:15]
        non = [c for c in cand if arch[c[1]] != "REFUSE"][:15]
        # exp8 judged the first 128-token response; the prompt text states 64 tokens -> identical content sent here
        jobs = [{"row_key": "smoke|" + k, "judge": JUDGE_PRIMARY,
                 "content": JUDGE_PROMPT.format(req=p200[g["item_id"]][g["arm"]], resp=g["response"])} for _, k, g in ref + non]
        asyncio.run(run_jobs(jobs, "smoke_T2"))
        have = load_labels(JUDGE_PRIMARY)
        agree = [have.get(("smoke|" + k, JUDGE_PRIMARY)) == arch[k] for _, k, g in ref + non]
        agree_bin = [(have.get(("smoke|" + k, JUDGE_PRIMARY)) == "REFUSE") == (arch[k] == "REFUSE") for _, k, g in ref + non]
        costs = [r["cost"] for r in read_jsonl(LABELS) if r["row_key"].startswith("smoke|")]
        out = {"n": len(agree), "agree_3way": sum(agree) / len(agree), "agree_binary": sum(agree_bin) / len(agree_bin),
               "cost_per_row": sum(costs) / max(len(costs), 1), "prompt_sha": JUDGE_PROMPT_SHA}
        logger.info(f"T2 judge smoke: {out}")
        (RESULTS / "judge_smoke_T2.json").write_text(json.dumps(out, indent=2))
        return
    rows = test_rows(a.model)
    logger.info(f"{a.model}: {len(rows)} TEST rows")
    if a.kind in ("primary", "both"):
        # add-on EN-orig reference rows: gemini on 50% (plan)
        prim = [r for r in rows if not (r["arm"] == "en_orig" and sha1_unit(rk(r) + "|enorig") >= 0.5)]
        asyncio.run(run_jobs(build_jobs(prim, JUDGE_PRIMARY), f"primary_{a.model}"))
    if a.kind in ("second", "both"):
        sec = second_sample([r for r in rows if r["arm"] != "en_orig"])
        (RESULTS / f"second_sample_{a.model}.json").write_text(json.dumps([rk(r) for r in sec]))
        asyncio.run(run_jobs(build_jobs(sec, JUDGE_SECOND), f"second_{a.model}"))
    (RESULTS / f"judge_done_{a.model}_{a.kind}.json").write_text(json.dumps({"t": time.time(), "spent": ledger_spent()}))


if __name__ == "__main__":
    main()
