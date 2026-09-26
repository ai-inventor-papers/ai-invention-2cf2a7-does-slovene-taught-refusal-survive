#!/usr/bin/env python3
"""S8 blind adjudication by the executing agent (AUTHOR MODEL, NOT HUMAN).

draw  --model M : per model 120 rows = SL-edited 60, EN-edited 40, orig 20 (SL 10 / EN 10); rows stratified by dose
                  bin (60% from the lag window, EN-R in [0.3, 0.7]); in the SL-edited cell >= 25 judge-REFUSE and
                  >= 25 judge-COMPLY rows (so Se and Sp are both estimable). Labels, model, lambda and judge output
                  are stripped; rows shuffled; blind file results/adjudication/blind_<M>.jsonl (uid, request, response).
                  The key (uid -> row_id) is written to results/adjudication/_key_<M>.json and NOT read before labelling.
unblind         : joins author_labels.jsonl (uid, label, harmful_content) with the keys ->
                  author_labels_unblinded.jsonl (row_id, label, harmful_content, ...), logs timestamps.
Scope reduction (F7, logged): 240 rows (120/model) instead of 300; batches drawn per model (after each model's ladder
was labelled) rather than interleaved across models, so the adjudicator knew which model a batch came from; lambda,
language-arm metadata and all judge labels stayed hidden.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone

from common import GENS, LABELS, RESULTS, SEED, read_jsonl, setup_logging, sha1, write_jsonl

logger = setup_logging("adjudicate")
ADJ = RESULTS / "adjudication"
ADJ.mkdir(exist_ok=True, parents=True)


def draw(model: str, judge_short: str) -> None:
    rows = [r for r in read_jsonl(GENS / f"{model}.jsonl") if r["set"] == "BODY" and r["edit"] == "E_exp9"
            and r["block"] in ("ladder", "fillin") and r["arm"] in ("EN_BT", "SL_MT")]
    lab = {r["row_id"]: r["label"] for r in read_jsonl(LABELS / f"primary_{judge_short}.jsonl")}
    if judge_short == "j1":
        # J1 labels for SL rows are produced after generation (GPU busy); label a seeded candidate pool on CPU now
        rng0 = random.Random(SEED + 5)
        pool = [r for r in rows if r["row_id"] not in lab]
        rng0.shuffle(pool)
        cand = ([r for r in pool if r["arm"] == "SL_MT" and r["lambda"] > 0][:450] +
                [r for r in pool if r["arm"] == "EN_BT" and r["lambda"] > 0][:150] +
                [r for r in pool if r["lambda"] == 0][:60])
        if cand:
            import torch
            from judge_local import OUT, label, load_j1
            torch.set_num_threads(16)
            m_, t_, sha_ = load_j1("cpu")
            label(m_, t_, sha_, cand, OUT)
            lab = {r["row_id"]: r["label"] for r in read_jsonl(LABELS / f"primary_{judge_short}.jsonl")}
    rows = [r for r in rows if r["row_id"] in lab]
    agg = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["arm"] == "EN_BT":
            agg[r["lambda"]][0] += lab[r["row_id"]] == "REFUSE"
            agg[r["lambda"]][1] += 1
    en = {l: k / n for l, (k, n) in agg.items() if n}
    win = {l for l, p in en.items() if l > 0 and 0.3 <= p <= 0.7}
    rng = random.Random(SEED + (1 if model == "gams3_it" else 0))
    rng.shuffle(rows)
    picked, used = [], set()

    def take(pool, n, cond=lambda r: True):
        out = []
        for r in pool:
            if len(out) >= n:
                break
            if r["row_id"] in used or not cond(r):
                continue
            out.append(r)
            used.add(r["row_id"])
        return out
    sl_ed = [r for r in rows if r["arm"] == "SL_MT" and r["lambda"] > 0]
    en_ed = [r for r in rows if r["arm"] == "EN_BT" and r["lambda"] > 0]
    # SL-edited: 25 judge-REFUSE + 25 judge-COMPLY (>= 60% from window) + 10 any
    for want in ("REFUSE", "COMPLY"):
        picked += take(sl_ed, 15, lambda r, w=want: lab[r["row_id"]] == w and r["lambda"] in win)
        picked += take(sl_ed, 25 - sum(1 for p in picked if p["arm"] == "SL_MT" and lab[p["row_id"]] == want),
                       lambda r, w=want: lab[r["row_id"]] == w)
    picked += take(sl_ed, 6, lambda r: r["lambda"] in win)
    picked += take(sl_ed, 60 - sum(1 for p in picked if p["arm"] == "SL_MT"))
    picked += take(en_ed, 24, lambda r: r["lambda"] in win)
    picked += take(en_ed, 16)
    picked += take(rows, 10, lambda r: r["lambda"] == 0 and r["arm"] == "SL_MT")
    picked += take(rows, 10, lambda r: r["lambda"] == 0 and r["arm"] == "EN_BT")
    rng.shuffle(picked)
    key, blind = {}, []
    for r in picked:
        uid = "u" + sha1(r["row_id"] + "adj" + str(SEED))[:10]
        key[uid] = r["row_id"]
        blind.append({"uid": uid, "request": r["request"], "response": r["response"]})
    write_jsonl(ADJ / f"blind_{model}.jsonl", blind)
    (ADJ / f"_key_{model}.json").write_text(json.dumps({"drawn_utc": datetime.now(timezone.utc).isoformat(),
                                                        "key": key}))
    logger.info(f"drew {len(blind)} rows for {model}: "
                f"{Counter((r['arm'], r['lambda'] > 0, lab[r['row_id']]) for r in picked)}; window {sorted(win)}")


def unblind() -> None:
    labs = read_jsonl(ADJ / "author_labels.jsonl")
    key = {}
    for m in ("gemma_it", "gams3_it"):
        p = ADJ / f"_key_{m}.json"
        if p.exists():
            key.update(json.loads(p.read_text())["key"])
    out = []
    for l in labs:
        if l["uid"] in key:
            out.append({"row_id": key[l["uid"]], "uid": l["uid"], "label": l["label"],
                        "harmful_content": l.get("harmful_content"), "by": "author_model_blind (NOT human)",
                        "batch": l.get("batch"), "ts": l.get("ts")})
    write_jsonl(ADJ / "author_labels_unblinded.jsonl", out)
    (ADJ / "unblind_log.json").write_text(json.dumps({"unblinded_utc": datetime.now(timezone.utc).isoformat(),
                                                      "n": len(out), "labels": dict(Counter(o["label"] for o in out))}))
    logger.info(f"unblinded {len(out)} labels: {Counter(o['label'] for o in out)}")


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["draw", "unblind"])
    ap.add_argument("--model")
    ap.add_argument("--judge_short", default="gemini-2.5-flash")
    a = ap.parse_args()
    if a.mode == "draw":
        draw(a.model, a.judge_short)
    else:
        unblind()


if __name__ == "__main__":
    main()
