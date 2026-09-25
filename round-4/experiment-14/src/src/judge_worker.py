#!/usr/bin/env python3
"""1.5 judge worker: tails results/gens/*.jsonl and labels rows as they land.
  primary  (frozen tier from results/judge_tier_choice.json) P1 on every grid / C-EXT row
  second   gpt-4.1-mini P1 on the frozen stratified frame: u = sha1(row_key + seed) / 2^160 < 0.25 (0.35 at lambda_lo /
           lambda_hi), drawn deterministically BEFORE labels exist; within-study models only
  ttj      primary P1 on the NLLB English translation of SL/HU-output responses, request = EN_orig
  asr      StrongREJECT rubric on harmful rows NOT labelled REFUSE by the primary (request = EN_orig)
The request shown to P1 is the input-language arm text WITHOUT the output-language suffix (protocol, k).
Output: results/labels/labels.jsonl (one row per key x readout), resumable through the judge cache."""
from __future__ import annotations

import argparse
import json
import time

from loguru import logger

from common import ARM_OF, DATA, GENS, LABELS, RESULTS, SEED, append_jsonl, read_jsonl, setup_logging, sha1
import judge_paid

OUT = LABELS / "labels.jsonl"


def in_second_frame(key: str, lam_tag: str) -> bool:
    u = int(sha1(key + str(SEED)), 16) / 2 ** 160
    return u < (0.35 if lam_tag in ("lo", "hi") else 0.25)


def lam_tag(model: str, lam: float) -> str:
    p = RESULTS / f"lambda_steps_{model}.json"
    if lam == 0:
        return "zero"
    if p.exists():
        s = json.loads(p.read_text())
        if abs(lam - s["lambda_lo"]) < 1e-9:
            return "lo"
        if abs(lam - s["lambda_hi"]) < 1e-9:
            return "hi"
    return "other"


def one_pass(models: list[str], readouts: list[str], concurrency: int) -> int:
    items = {r["item_id"]: r for r in read_jsonl(DATA / "items.jsonl")}
    done = {(r["key"], r["readout"]) for r in read_jsonl(OUT)}
    prim = json.loads((RESULTS / "judge_tier_choice.json").read_text())["primary"]
    ttj = {r["key"]: r["translation"] for r in read_jsonl(LABELS / "ttj_translations.jsonl")}
    prim_lab = {r["key"]: r["label"] for r in read_jsonl(OUT) if r["readout"] == "primary"}
    jobs = []
    for m in models:
        for r in read_jsonl(GENS / f"{m}.jsonl"):
            it = items[r["item_id"]]
            req = it["EN_orig"] if r["cond"] == "mtnoise" else it[ARM_OF[r["in_lang"]]]
            resp = judge_paid.tok_trunc(r["response"])
            base = {"key": r["key"], "model": m}
            if "primary" in readouts and (r["key"], "primary") not in done:
                jobs.append({"tier": prim, "task": "p1", "req": req, "resp": resp,
                             "meta": {**base, "readout": "primary"}})
            if ("second" in readouts and r["cond"] in ("edit", "rand", "mtnoise") and (r["key"], "second") not in done
                    and in_second_frame(r["key"], lam_tag(m, r["lambda"]))):
                jobs.append({"tier": "gpt41mini", "task": "p1", "req": req, "resp": resp,
                             "meta": {**base, "readout": "second"}})
            if "ttj" in readouts and r["key"] in ttj and (r["key"], "ttj") not in done:
                jobs.append({"tier": prim, "task": "p1", "req": it["EN_orig"], "resp": judge_paid.tok_trunc(ttj[r["key"]]),
                             "meta": {**base, "readout": "ttj"}})
            if ("asr" in readouts and r["kind"] == "harmful" and prim_lab.get(r["key"]) in ("PARTIAL", "COMPLY")
                    and (r["key"], "asr") not in done and r["cond"] in ("edit", "ext")):
                jobs.append({"tier": prim, "task": "sr", "req": it["EN_orig"], "resp": resp,
                             "meta": {**base, "readout": "asr"}})
    if not jobs:
        return 0
    logger.info(f"judge pass: {len(jobs)} jobs ({', '.join(f'{k}={sum(j['meta']['readout'] == k for j in jobs)}' for k in readouts)})")
    for s in range(0, len(jobs), 1000):
        ch = jobs[s:s + 1000]
        res = judge_paid.run(ch, concurrency=concurrency, tag="worker")
        rows = []
        for j, x in zip(ch, res):
            if x.get("err"):
                continue
            row = {**j["meta"], "tier": j["tier"], "label": x.get("label"), "cost": x.get("cost")}
            if j["task"] == "sr":
                row.update({k: x.get(k) for k in ("refused", "convincing", "specific", "score")})
            rows.append(row)
        append_jsonl(OUT, rows)
        if judge_paid.spent() >= judge_paid.HARD_STOP:
            logger.error("hard stop reached")
            break
    return len(jobs)


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="gemma_it")
    ap.add_argument("--readouts", default="primary,second")
    ap.add_argument("--follow", action="store_true")
    ap.add_argument("--concurrency", type=int, default=24)
    args = ap.parse_args()
    setup_logging("judge_worker")
    models, readouts = args.models.split(","), args.readouts.split(",")
    while True:
        n = one_pass(models, readouts, args.concurrency)
        if not args.follow:
            break
        if (RESULTS / "judge_worker.stop").exists() and n == 0:
            break
        time.sleep(45 if n == 0 else 5)
    logger.info(f"worker done; cumulative ${judge_paid.spent():.4f}")


if __name__ == "__main__":
    main()
