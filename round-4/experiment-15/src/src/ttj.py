#!/usr/bin/env python3
"""S7c translate-then-judge (R-JUDGE): NLLB-200-distilled-1.3B SL->EN of every selected SL response.

Selection (per model): E_exp9 rows at lambda 0, at the 4 ladder/fill-in steps whose BODY EN-BT refusal (primary judge,
R coding) is nearest 0.30/0.43/0.57/0.70 (flash budget rule), and at max lambda (random arm excluded under the flash budget rule). The judged request is the item's EN-BT
text, so the readout is language-neutral. Also writes results/asr_selection.json (harmful BODY rows, both languages, at
the same steps) for the R-INCAP rubric. Resumable (skips row_ids already in results/ttj.jsonl).
"""
from __future__ import annotations

import argparse
import gc
import json
import time
from collections import defaultdict

from common import DATA, GENS, LABELS, RESULTS, append_jsonl, read_jsonl, setup_logging

logger = setup_logging("ttj")


def select(judge_short: str) -> tuple[list[dict], list[str], dict]:
    rows = []
    for f in sorted(GENS.glob("*.jsonl")):
        rows += read_jsonl(f)
    lab = {r["row_id"]: r["label"] for r in read_jsonl(LABELS / f"primary_{judge_short}.jsonl")}
    agg = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["set"] == "BODY" and r["arm"] == "EN_BT" and r["edit"] == "E_exp9" and r["row_id"] in lab:
            a = agg[(r["model"], round(r["lambda"], 4))]
            a[0] += lab[r["row_id"]] == "REFUSE"
            a[1] += 1
    en = {k: v[0] / v[1] for k, v in agg.items() if v[1]}
    # flash budget rule (plan S7): the 4 ladder steps nearest EN 0.30/0.43/0.57/0.70, plus lambda 0 and max lambda
    steps = defaultdict(set)
    for m in {k[0] for k in en}:
        pos = {lam: p for (mm, lam), p in en.items() if mm == m and lam > 0}
        steps[m].add(0.0)
        for t in (0.30, 0.43, 0.57, 0.70):
            if pos:
                steps[m].add(min(pos, key=lambda l: abs(pos[l] - t)))
    for m in {k[0] for k in en}:
        steps[m].add(max(l for (mm, l) in en if mm == m))
    sel_sl, asr_ids = [], []
    for r in rows:
        if r["set"] != "BODY" or r["block"] not in ("ladder", "fillin", "random"):
            continue
        lam = round(r["lambda"], 4)
        in_step = r["edit"] == "E_exp9" and lam in steps[r["model"]]  # random arm excluded (flash budget rule)
        if not in_step:
            continue
        if r["arm"] == "SL_MT":
            sel_sl.append(r)
        if r["edit"] == "E_exp9" and r["arm"] in ("EN_BT", "SL_MT"):
            asr_ids.append(r["row_id"])
    return sel_sl, asr_ids, {m: sorted(v) for m, v in steps.items()}


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", default=None)
    a = ap.parse_args()
    judge = a.judge or json.loads((RESULTS / "judge_tier_table.json").read_text())["judge_primary"]
    sel, asr_ids, steps = select(judge.split("/")[-1])
    (RESULTS / "asr_selection.json").write_text(json.dumps({"steps": steps, "row_ids": asr_ids}))
    items = {it["item_id"]: it for it in read_jsonl(DATA / "items.jsonl")}
    done = {r["row_id"] for r in read_jsonl(RESULTS / "ttj.jsonl")}
    todo = [r for r in sel if r["row_id"] not in done]
    logger.info(f"TTJ: steps {steps}; {len(sel)} SL rows selected, {len(todo)} to translate; ASR ids {len(asr_ids)}")
    if not todo:
        return
    import torch

    from build_items import load_nllb, mt
    model, tok = load_nllb()
    t0 = time.time()
    for i in range(0, len(todo), 1000):
        chunk = todo[i:i + 1000]
        tr = mt(model, tok, [r["response"] or " " for r in chunk], "slv_Latn", "eng_Latn", bs=64)
        append_jsonl(RESULTS / "ttj.jsonl", [{"row_id": r["row_id"], "model": r["model"], "edit": r["edit"],
                                              "lambda": r["lambda"], "item_id": r["item_id"],
                                              "req_en": items[r["item_id"]]["en_bt"], "resp_en": t}
                                             for r, t in zip(chunk, tr)])
        logger.info(f"TTJ {i + len(chunk)}/{len(todo)} in {time.time() - t0:.0f}s")
    del model
    gc.collect()
    torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
