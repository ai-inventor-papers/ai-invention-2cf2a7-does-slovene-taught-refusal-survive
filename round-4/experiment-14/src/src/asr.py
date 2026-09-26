#!/usr/bin/env python3
"""R-INCAP arm: StrongREJECT rubric (verbatim repo template; request = EN_orig source) on harmful rows NOT labelled
REFUSE by the primary judge, in the 4 EN/SL cells at lambda_lo and lambda_hi (departure D4: scored by
gemini-2.5-flash-lite for cost). REFUSE rows score 0 in the analysis. Appends readout='asr' rows to labels.jsonl."""
from __future__ import annotations

from loguru import logger

from common import DATA, GENS, LABELS, append_jsonl, read_jsonl, setup_logging
from build_table import dose_tag
import judge_paid

TIER = "flash_lite"


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("asr")
    items = {r["item_id"]: r for r in read_jsonl(DATA / "items.jsonl")}
    out = LABELS / "labels.jsonl"
    L = read_jsonl(out)
    prim = {r["key"]: r["label"] for r in L if r["readout"] == "primary"}
    done = {r["key"] for r in L if r["readout"] == "asr"}
    jobs = []
    for m in ("gemma_it", "gams3_it"):
        for r in read_jsonl(GENS / f"{m}.jsonl"):
            if (r["kind"] == "harmful" and r["cond"] == "edit" and r["in_lang"] != "hu" and r["out_lang"] != "hu"
                    and dose_tag(m, r["lambda"], r["cond"]) in ("lo", "hi") and prim.get(r["key"]) in ("PARTIAL", "COMPLY")
                    and r["key"] not in done):
                jobs.append({"tier": TIER, "task": "sr", "req": items[r["item_id"]]["EN_orig"],
                             "resp": judge_paid.tok_trunc(r["response"]), "meta": {"key": r["key"], "model": m}})
    logger.info(f"ASR jobs {len(jobs)}")
    for s in range(0, len(jobs), 500):
        ch = jobs[s:s + 500]
        res = judge_paid.run(ch, concurrency=24, tag="asr")
        append_jsonl(out, [{**j["meta"], "readout": "asr", "tier": TIER,
                            **{k: x.get(k) for k in ("refused", "convincing", "specific", "score")}, "cost": x.get("cost")}
                           for j, x in zip(ch, res) if not x.get("err")])
    logger.info(f"done; cumulative ${judge_paid.spent():.4f}")


if __name__ == "__main__":
    main()
