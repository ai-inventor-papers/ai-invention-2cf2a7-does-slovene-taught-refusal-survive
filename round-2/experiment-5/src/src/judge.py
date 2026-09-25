#!/usr/bin/env python3
"""STEP 4.1 / 5.1: OpenRouter judges on DEV or FINAL generations (resumable, cost-capped, KEY_DOWN-safe).

  refusal : gemini-2.5-flash on ALL refusal-set responses (refuseu_nat, refuseu_x, hard) [+ DEV batch-check rows];
            content-blocked items are rerouted to openai/gpt-4.1 as their PRIMARY label;
            openai/gpt-4.1 second family on sha1(key+'20260924') mod 100 < 15 (FINAL) / < 30 (DEV).
  identity: gemini + gpt-4.1 on ALL identity responses (NAME|MAKER).
Exports outputs/<split>/labels_refusal.jsonl and labels_identity.jsonl.
FINAL is guarded: raises unless protocol/addendum_dev.json is committed and hash-verified.

Usage: python judge.py --split dev|final [--task refusal|identity|all] [--limit N] [--conc 24] [--version v1|v2]
"""
from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter

from loguru import logger

from common import LEDGERS, OUT_DEV, OUT_FINAL, SEED, guard_final, read_jsonl, setup_logging, sha1_int, write_jsonl
from openrouter import Ledger, run_jobs, total_spent, KEY_DOWN_FLAG
import prompts as P

GEMINI, GPT41 = "google/gemini-2.5-flash", "openai/gpt-4.1"
REFUSAL_SETS = ("refuseu_nat", "refuseu_x", "hard")


def judge_prompt_version() -> dict:
    """v1 unless the addendum recorded a v2 revision (file protocol/judge_prompt_v2.json)."""
    from common import PROTO
    p2 = PROTO / "judge_prompt_v2.json"
    if p2.exists():
        return json.loads(p2.read_text())
    return {"version": "v1", "system": P.JUDGE_SYSTEM_V1, "user": P.JUDGE_USER_V1}


def second_family(key: str, split: str) -> bool:
    return sha1_int(key + str(SEED)) % 100 < (15 if split == "final" else 30)


def gen_rows(split: str) -> list[dict]:
    if split == "final":
        guard_final("judge.py FINAL generations")
        rows = []
        for p in sorted(OUT_FINAL.glob("gen_*.jsonl")):
            rows += read_jsonl(p)
        return rows
    rows = []
    for p in sorted(OUT_DEV.glob("gen_*.jsonl")):
        rows += read_jsonl(p)
    for p in sorted(OUT_DEV.glob("batchcheck_*.jsonl")):
        for r in read_jsonl(p):
            rows.append({**r, "set": "batchcheck", "arm": r["mode"], "split": "DEV"})
    return rows


def refusal_job(r: dict, model: str, jp: dict) -> dict:
    return {"key": f"{r['key']}||{model}|{jp['version']}", "model": model, "max_tokens": 8,
            "messages": [{"role": "system", "content": jp["system"]},
                         {"role": "user", "content": jp["user"].format(req=r["prompt_text"], resp=r["response"])}],
            "meta": {"item_key": r["key"], "judge_version": jp["version"]}}


def identity_job(r: dict, model: str) -> dict:
    return {"key": f"{r['key']}||{model}|id_v1", "model": model, "max_tokens": 16,
            "messages": [{"role": "system", "content": P.JUDGE_SYSTEM_V1},
                         {"role": "user", "content": P.ID_USER_V1.format(q=r["prompt_text"], resp=r["response"])}],
            "meta": {"item_key": r["key"]}}


async def run(split: str, task: str, limit: int, conc: int) -> dict:
    rows = gen_rows(split)
    jp = judge_prompt_version()
    stats = {}
    if task in ("refusal", "all"):
        rr = [r for r in rows if r["set"] in REFUSAL_SETS or r["set"] == "batchcheck"]
        if limit:
            rr = rr[:limit]
        jobs = [refusal_job(r, GEMINI, jp) for r in rr]
        est = sum(len(j["messages"][0]["content"]) + len(j["messages"][1]["content"]) for j in jobs) / 3.3
        est_cost = est * 0.30 / 1e6 + len(jobs) * 3 * 2.5 / 1e6
        sec = [r for r in rr if second_family(r["key"], split)]
        est2 = sum(len(r["prompt_text"]) + len(r["response"]) + 900 for r in sec) / 3.3 * 2.0 / 1e6
        logger.info(f"[{split}] refusal: {len(jobs)} gemini jobs (~${est_cost:.2f}), {len(sec)} gpt-4.1 (~${est2:.2f}); "
                    f"spent so far ${total_spent():.3f}")
        if est_cost + est2 + total_spent() > 9.0:
            raise RuntimeError("pre-sweep estimate exceeds the $9 cap; aborting (plan: abort if > $8 for FINAL)")
        lg = Ledger(f"{split}_refusal_gemini")
        stats["gemini"] = await run_jobs(lg, jobs, P.parse_refusal, conc)
        if lg.stop:
            return {"stopped": lg.stop_reason, **stats}
        blocked = {r["item_key"] for r in read_jsonl(lg.path) if r.get("label") == "BLOCKED"}
        fb = Ledger(f"{split}_refusal_gpt41_fallback")
        fjobs = [refusal_job(r, GPT41, jp) for r in rr if r["key"] in blocked]
        logger.info(f"{len(fjobs)} gemini content-blocked -> gpt-4.1 primary")
        stats["fallback"] = await run_jobs(fb, fjobs, P.parse_refusal, conc)
        g2 = Ledger(f"{split}_refusal_gpt41")
        stats["gpt41"] = await run_jobs(g2, [refusal_job(r, GPT41, jp) for r in sec], P.parse_refusal, conc)
        if g2.stop or fb.stop:
            return {"stopped": g2.stop_reason or fb.stop_reason, **stats}
    if task in ("identity", "all"):
        ri = [r for r in rows if r["set"] == "identity"]
        if limit:
            ri = ri[:limit]
        for fam, m in (("gemini", GEMINI), ("gpt41", GPT41)):
            lg = Ledger(f"{split}_identity_{fam}")
            stats[f"id_{fam}"] = await run_jobs(lg, [identity_job(r, m) for r in ri], P.parse_id, conc)
            if lg.stop:
                return {"stopped": lg.stop_reason, **stats}
    return stats


def export(split: str) -> dict:
    """Merge ledgers into per-response label files. Primary refusal label = gemini unless BLOCKED -> gpt-4.1."""
    jp = judge_prompt_version()["version"]

    def led(name):
        out = {}
        for r in read_jsonl(LEDGERS / f"ledger_{name}.jsonl"):
            if r.get("judge_version", jp) == jp or "identity" in name:
                out[r["item_key"]] = r
        return out
    gem, fb, g2 = led(f"{split}_refusal_gemini"), led(f"{split}_refusal_gpt41_fallback"), led(f"{split}_refusal_gpt41")
    labels = []
    from common import PROTO
    pj = PROTO / "primary_judge.json"  # deviation D2 contingency (written only if gemini is unavailable at cut-off)
    if split == "final" and pj.exists() and json.loads(pj.read_text()).get("primary") == "qwen3_local":
        ql = {r["key"]: r for r in read_jsonl((OUT_DEV if split == "dev" else OUT_FINAL) / "labels_local_qwen3.jsonl")
              if r.get("qwen_label")}
        for k, q in ql.items():
            gl = gem.get(k, {}).get("label")
            labels.append({"key": k, "judge_gemini": gl, "judge_primary": q["qwen_label"],
                           "judge_primary_model": "Qwen/Qwen3-14B(local,substitute)",
                           "judge_gpt41": g2[k]["label"] if k in g2 else None, "judge_version": jp})
        gem = {}
    for k, r in gem.items():
        prim, pm = r["label"], GEMINI
        if prim == "BLOCKED":
            if k in fb:
                prim, pm = fb[k]["label"], GPT41
            else:
                prim, pm = None, None
        labels.append({"key": k, "judge_gemini": r["label"], "judge_primary": prim, "judge_primary_model": pm,
                       "judge_gpt41": g2[k]["label"] if k in g2 else None, "judge_version": jp})
    write_jsonl((OUT_DEV if split == "dev" else OUT_FINAL) / "labels_refusal.jsonl", labels)
    ig, ip = led(f"{split}_identity_gemini"), led(f"{split}_identity_gpt41")
    idl = [{"key": k, "id_name_gemini": r.get("label"), "id_maker_gemini": r.get("label2"),
            "id_name_gpt41": ip.get(k, {}).get("label"), "id_maker_gpt41": ip.get(k, {}).get("label2")}
           for k, r in ig.items()]
    write_jsonl((OUT_DEV if split == "dev" else OUT_FINAL) / "labels_identity.jsonl", idl)
    from common import RESULTS
    per = {p.stem: round(sum(float(r.get("cost") or 0) for r in read_jsonl(p)), 6) for p in sorted(LEDGERS.glob("ledger_*.jsonl"))}
    (RESULTS / "spend.json").write_text(json.dumps({"total_usd": total_spent(), "per_ledger": per,
                                                    "n_calls": {p.stem: len(read_jsonl(p)) for p in sorted(LEDGERS.glob("ledger_*.jsonl"))}}, indent=1))
    c = Counter(x["judge_primary"] for x in labels)
    return {"n_refusal": len(labels), "primary_counts": dict(c), "n_identity": len(idl),
            "n_blocked": sum(x["judge_gemini"] == "BLOCKED" for x in labels)}


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True, choices=["dev", "final"])
    ap.add_argument("--task", default="all", choices=["refusal", "identity", "all"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--conc", type=int, default=24)
    ap.add_argument("--export_only", action="store_true")
    args = ap.parse_args()
    setup_logging(f"judge_{args.split}")
    if not args.export_only:
        if KEY_DOWN_FLAG.exists():
            KEY_DOWN_FLAG.unlink()  # re-probe implicitly: the first call re-sets it if still down
        st = asyncio.run(run(args.split, args.task, args.limit, args.conc))
        logger.info(f"run stats: {st}")
    ex = export(args.split)
    logger.info(f"export: {ex}; total spent ${total_spent():.3f}")


if __name__ == "__main__":
    main()
