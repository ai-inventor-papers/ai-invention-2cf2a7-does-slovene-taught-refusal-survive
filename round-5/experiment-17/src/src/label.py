#!/usr/bin/env python3
"""Paid readouts over generated rows (resumable; content-addressed cache; ledger; hard stop in judge_paid).

  --what devp1   P1 (gemini-2.5-flash) on DEV rows of results/gens/dev_<m>.jsonl -> labels/p1_dev.jsonl
  --what p1      P1 on FINAL rows at the A2 tier (results/amendments/A2.json) -> labels/p1.jsonl; the second-family
                 frame (sha1(key|seed) share) also gets openai/gpt-4.1-mini -> labels/p1b.jsonl
  --what adj     gpt-4o-mini adjudication of guard disagreements (LG != PG or NA) -> labels/adj.jsonl
  --what sr      StrongREJECT on SR-eligible rows (+ the 150-row imputation audit) -> labels/sr.jsonl
Only rows whose key is not yet in the target label file are sent."""
from __future__ import annotations

import argparse
import glob
import json

from loguru import logger

from common import GENS, LABELS, RESULTS, SEED, append_jsonl, read_jsonl, setup_logging, sha1, sha1_int
import judge_paid

AMEND = RESULTS / "amendments"


def gens(pattern: str) -> list[dict]:
    rows = []
    for f in sorted(glob.glob(str(GENS / pattern))):
        rows += read_jsonl(f)
    return rows


def in_frame(key: str, share: float) -> bool:
    return (sha1_int(f"{key}|{SEED}") % 10_000) < share * 10_000


def run_jobs(jobs: list[dict], out: str, readout: str, conc: int = 24) -> int:
    n = 0
    for s in range(0, len(jobs), 400):
        ch = jobs[s:s + 400]
        res = judge_paid.run(ch, concurrency=conc, tag=readout)
        recs = []
        for j, x in zip(ch, res):
            if x.get("err"):
                continue
            recs.append({**j["meta"], "readout": readout, "tier": j["tier"],
                         **{k: x.get(k) for k in ("label", "refused", "convincing", "specific", "score")},
                         "raw": x.get("raw"), "cost": x.get("cost")})
        append_jsonl(LABELS / out, recs)
        n += len(recs)
        if judge_paid.spent() >= judge_paid.HARD_STOP:
            break
    return n


def guard_table() -> dict[str, dict]:
    lg = {r["key"]: r for r in read_jsonl(LABELS / "guard_llamaguard3.jsonl")}
    pg = {r["key"]: r for r in read_jsonl(LABELS / "guard_polyguard.jsonl")}
    out = {}
    for k in set(lg) & set(pg):
        out[k] = {"lg": lg[k].get("lg_unsafe"), "pg": pg[k].get("pg_unsafe"), "pg_ref": pg[k].get("pg_refusal")}
    return out


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--what", required=True, choices=["devp1", "p1", "adj", "sr"])
    ap.add_argument("--models", default="gemma_it,gams3_it")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    setup_logging(f"label_{a.what}")
    models = a.models.split(",")
    if a.what == "devp1":
        done = {r["key"] for r in read_jsonl(LABELS / "p1_dev.jsonl")}
        rows = [r for m in models for r in gens(f"dev_{m}.jsonl") if r["key"] not in done]
        jobs = [{"tier": "flash", "task": "p1", "req": r["prompt"], "resp": judge_paid.tok_trunc(r["response"], 64),
                 "meta": {"key": r["key"], "model": r["model"]}} for r in rows]
        jobs = jobs[:a.limit] if a.limit else jobs
        logger.info(f"devp1 jobs {len(jobs)}")
        run_jobs(jobs, "p1_dev.jsonl", "p1_dev")
    elif a.what == "p1":
        a2 = json.loads((AMEND / "A2.json").read_text())
        tier, share, gate_p1 = a2["p1_tier"], a2["second_family_share"], a2.get("p1_on_gate_rows", True)
        p1_share = a2.get("p1_prompt_share", 1.0)
        done = {r["key"] for r in read_jsonl(LABELS / "p1.jsonl")}
        doneb = {r["key"] for r in read_jsonl(LABELS / "p1b.jsonl")}
        rows = [r for m in models for r in gens(f"{m}.jsonl")]
        gate_lams = {}
        for m in models:
            f = AMEND / f"lambda_gate_{m}.json"
            if f.exists():
                gate_lams[m] = json.loads(f.read_text()).get("lambda_gate")
        sel = []
        for r in rows:
            if r["max_new"] != 128 or r["cond"] == "rand1":
                continue  # P1 is not run on control / sensitivity rows
            if r["cond"] == "edit" and r["lambda"] not in (1.0,) and not gate_p1:
                continue
            if p1_share < 1.0 and not in_frame("p1|" + r["pair_id"], p1_share):
                continue
            sel.append(r)
        jobs = [{"tier": tier, "task": "p1", "req": r["prompt"], "resp": judge_paid.tok_trunc(r["response"], 64),
                 "meta": {"key": r["key"], "model": r["model"]}} for r in sel if r["key"] not in done]
        jobsb = [{"tier": "gpt41mini", "task": "p1", "req": r["prompt"],
                  "resp": judge_paid.tok_trunc(r["response"], 64), "meta": {"key": r["key"], "model": r["model"]}}
                 for r in sel if r["key"] not in doneb and in_frame(r["key"], share)]
        if a.limit:
            jobs, jobsb = jobs[:a.limit], jobsb[:a.limit]
        logger.info(f"p1 jobs {len(jobs)} (tier {tier}); second-family jobs {len(jobsb)} (share {share})")
        run_jobs(jobs, "p1.jsonl", "p1")
        run_jobs(jobsb, "p1b.jsonl", "p1b")
    elif a.what == "adj":
        gt = guard_table()
        done = {r["key"] for r in read_jsonl(LABELS / "adj.jsonl")}
        rows = [r for m in models for r in gens(f"{m}.jsonl") + gens(f"dev_{m}.jsonl")]
        jobs = []
        for r in rows:
            g = gt.get(r["key"])
            if g is None or r["key"] in done:
                continue
            if g["lg"] is None or g["pg"] is None or g["lg"] != g["pg"]:
                jobs.append({"tier": "gpt4omini", "task": "adj", "req": r["prompt"], "resp": r["response"],
                             "meta": {"key": r["key"], "model": r["model"]}})
        jobs = jobs[:a.limit] if a.limit else jobs
        logger.info(f"adj jobs {len(jobs)}")
        run_jobs(jobs, "adj.jsonl", "adj", conc=32)
    elif a.what == "sr":
        a2 = json.loads((AMEND / "A2.json").read_text())
        sr_share = a2.get("sr_share", 1.0)
        gt = guard_table()
        done = {r["key"] for r in read_jsonl(LABELS / "sr.jsonl")}
        rows = [r for m in models for r in gens(f"{m}.jsonl")]
        elig, imputed = [], []
        for r in rows:
            g = gt.get(r["key"])
            if g is None:
                continue
            if g["lg"] == 0 and g["pg"] == 0 and g["pg_ref"] == 1:
                imputed.append(r)
            elif sr_share >= 1.0 or in_frame("sr|" + r["key"], sr_share):
                elig.append(r)
        # imputation audit: 150 hash-random imputed rows, stratified model x lang x cond(lambda)
        strata: dict[tuple, list] = {}
        for r in imputed:
            if r["max_new"] != 128:
                continue
            strata.setdefault((r["model"], r["lang"], r["cond"], r["lambda"]), []).append(r)
        audit = []
        ns = max(1, len(strata))
        per = max(1, 150 // ns)
        for k in sorted(strata, key=str):
            audit += sorted(strata[k], key=lambda r: sha1("audit|" + r["key"]))[:per]
        audit_keys = {r["key"] for r in audit}
        todo = [r for r in elig + audit if r["key"] not in done]
        jobs = [{"tier": "flash", "task": "sr", "req": r["prompt"], "resp": r["response"],
                 "meta": {"key": r["key"], "model": r["model"], "sr_audit": int(r["key"] in audit_keys)}}
                for r in todo]
        jobs = jobs[:a.limit] if a.limit else jobs
        logger.info(f"sr: eligible {len(elig)} imputed {len(imputed)} audit {len(audit)}; jobs {len(jobs)}")
        run_jobs(jobs, "sr.jsonl", "sr", conc=32)
        # provider-block fallback (plan g): unparsable / blocked rows -> gpt-4.1-mini, judge_fallback = 1
        have = {r["key"]: r for r in read_jsonl(LABELS / "sr.jsonl")}
        miss = [j for j in jobs if j["meta"]["key"] not in have or have[j["meta"]["key"]].get("score") is None]
        miss_keys = {j["meta"]["key"] for j in miss}
        fb = [{**j, "tier": "gpt41mini", "meta": {**j["meta"], "judge_fallback": 1}} for j in miss]
        if fb:
            logger.warning(f"sr fallback to gpt-4.1-mini for {len(fb)} rows")
            run_jobs(fb, "sr.jsonl", "sr", conc=16)
        logger.info(f"sr done; fallback {len(miss_keys)}")
    logger.info(f"cumulative spend ${judge_paid.spent():.4f}")


if __name__ == "__main__":
    main()
