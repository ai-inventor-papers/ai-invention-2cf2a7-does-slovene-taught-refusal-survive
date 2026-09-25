#!/usr/bin/env python3
"""0.2 benign top-up: gpt-4.1-mini twins (frozen TWIN_PROMPT) of C-half harmful items that lack a JBB benign twin,
each checked HARMLESS by gemini-2.5-flash-lite AND gpt-4.1-mini (one-line harmfulness question) and read by the
executor (results/twins_review.json). Rejected twins are redrawn from the next harmful item. -> data/pool_benign.jsonl"""
from __future__ import annotations

import json

from loguru import logger

from common import DATA, RESULTS, SEED, dump, read_jsonl, setup_logging, sha1_int, write_jsonl
import judge_paid


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("twins")
    harm = read_jsonl(DATA / "pool_harmful.jsonl")
    ben = read_jsonl(DATA / "pool_benign_pre.jsonl")
    need = 100 - len(ben)
    have_twin = {b.get("twin_of") for b in ben}
    order = sorted([h for h in harm if h["item_id"] not in have_twin], key=lambda h: sha1_int(h["item_id"] + str(SEED)))
    reject = set(json.loads((RESULTS / "twins_reject.json").read_text())) if (RESULTS / "twins_reject.json").exists() else set()
    out, review, k = [], [], 0
    while len(out) < need and k < len(order):
        batch = order[k:k + (need - len(out)) + 6]
        k += len(batch)
        tw = judge_paid.run([{"tier": "gpt41mini", "task": "twin", "req": h["text"], "meta": {"id": h["item_id"]}}
                             for h in batch], tag="twin")
        texts = [(h, (t.get("text") or "").strip().strip('"')) for h, t in zip(batch, tw)]
        texts = [(h, t) for h, t in texts if t and h["item_id"] not in reject]
        chk = {}
        for tier in ("flash_lite", "gpt41mini"):
            r = judge_paid.run([{"tier": tier, "task": "harm", "req": t, "meta": {"id": h["item_id"]}}
                                for h, t in texts], tag=f"harmchk-{tier}")
            for (h, _), x in zip(texts, r):
                chk.setdefault(h["item_id"], {})[tier] = x.get("label")
        for h, t in texts:
            ok = all(v == "HARMLESS" for v in chk[h["item_id"]].values())
            review.append({"harmful_id": h["item_id"], "harmful": h["text"], "twin": t, "checks": chk[h["item_id"]],
                           "accepted": ok})
            if ok and len(out) < need:
                out.append({"src": "gpt41mini-twin", "text": t, "category": h.get("category"), "twin_of": h["item_id"],
                            "benign_origin": "llm_twin", "n_words": len(t.split())})
    for b in ben:
        b["benign_origin"] = "JBB-benign"
    allb = ben + out
    for i, b in enumerate(allb):
        b["item_id"] = f"b{i:03d}"
        b["kind"] = "benign"
    write_jsonl(DATA / "pool_benign.jsonl", allb)
    dump(RESULTS / "twins_review.json", review)
    logger.info(f"benign: {len(ben)} JBB + {len(out)} twins; rejected {sum(not r['accepted'] for r in review)}")


if __name__ == "__main__":
    main()
