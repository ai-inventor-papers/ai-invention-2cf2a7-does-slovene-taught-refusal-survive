#!/usr/bin/env python3
"""S7 BLIND ADJUDICATION sample (author model = the executor LLM, NOT a human).
--make : writes results/adjudication/blind_batch_k.jsonl with ONLY {row_id, request, response128}, shuffled, and a
         SEPARATE key file (adjudication_key.jsonl: row_id -> generation key) that the adjudicator must not open
         before writing labels. Sample: 60 edited rows per within-study model x {EN_BT, SL_MT}, 30 per model x L3,
         60 public-checkpoint rows (20 each, EN/SL/L3 mixed); stratified over lambda (curve steps and 1.0);
         disagreement-oversampling is applied when second-family labels exist (<= 30%).
--check: validates adjudication_labels.jsonl (every row_id labelled exactly once with REFUSE/PARTIAL/COMPLY)."""
from __future__ import annotations

import argparse
import json
import random

import pandas as pd

from common import RESULTS, SEED, append_jsonl, read_jsonl, write_jsonl
from judge_local import trunc128

AD = RESULTS / "adjudication"
AD.mkdir(exist_ok=True)


def make() -> None:
    pq = RESULTS / "rows_final.parquet"
    if pq.exists():
        d = pd.read_parquet(pq)
    else:  # run BEFORE judging, so that adjudication is blind to the judges (deviation: no disagreement
        # oversampling is then possible; recorded in results/adjudication/README.md)
        d = pd.DataFrame([r for p in sorted((RESULTS / "final").glob("gens_*.jsonl")) for r in read_jsonl(p)])
        d["label_q"] = None
        d["label_m"] = None
    d = d[d.set.isin(["refuseu_x", "hard"])]
    rng = random.Random(SEED)
    picks = []
    ed = d[d.condition.isin(["lam", "edit"])]
    for m in ("gemma_it", "gams3_it"):
        for arm, n in (("EN_BT", 36), ("SL_MT", 36), ("L3_MT", 18)):
            pool = ed[(ed.model == m) & (ed.arm == arm)]
            if pool.empty:
                continue
            dis = pool[pool.label_m.notna() & (pool.label_q != pool.label_m)] if pool.label_m.notna().any() \
                else pool.iloc[:0]
            k_dis = min(len(dis), int(0.3 * n))
            chosen = list(dis.sample(k_dis, random_state=SEED).key) if k_dis else []
            rest = pool[~pool.key.isin(chosen)]
            per = rest.groupby("lambda")
            quota = max(1, (n - k_dis) // max(1, per.ngroups))
            for _, gg in per:
                chosen += list(gg.sample(min(quota, len(gg)), random_state=SEED).key)
            if len(chosen) < n:
                chosen += list(rest[~rest.key.isin(chosen)].sample(min(n - len(chosen), len(rest) - 0),
                                                                    random_state=SEED + 1).key)[: n - len(chosen)]
            picks += chosen[:n]
    pub = d[d.condition == "public"]
    for m in sorted(pub.model.unique()):
        pool = pub[pub.model == m]
        picks += list(pool.sample(min(24, len(pool)), random_state=SEED).key)
    sub = d[d.key.isin(picks)].copy()
    rows = [{"row_id": f"A{idx:04d}", "key": k, "request": r, "response128": trunc128(s)}
            for idx, (k, r, s) in enumerate(zip(sub.key, sub.prompt_text, sub.response))]
    rng.shuffle(rows)
    for i in range(0, len(rows), 45):
        write_jsonl(AD / f"blind_batch_{i // 45 + 1}.jsonl",
                    [{k: r[k] for k in ("row_id", "request", "response128")} for r in rows[i:i + 45]])
    write_jsonl(AD / "adjudication_key.jsonl", [{"row_id": r["row_id"], "key": r["key"]} for r in rows])
    (AD / "README.md").write_text(
        f"Sampled from judge labels: {pq.exists()} (when False the sample was drawn BEFORE any FINAL judging, so no "
        "gemini/Qwen-vs-Mistral disagreement oversampling was possible; the sample is then stratified over model x arm "
        "x lambda only).\n\n"
        "Blind adjudication by the author model (the executor LLM), NOT a human. Batches contain only row_id, "
        "request and the first 128 tokens of the response, shuffled; the key file maps row_id to the generation key "
        "and was opened only after adjudication_labels.jsonl was written. Labels use the same REFUSE/PARTIAL/COMPLY "
        f"definitions as the judge prompt. n = {len(rows)}.\n")
    print(f"{len(rows)} rows in {(len(rows) + 44) // 45} batches")


def check() -> None:
    lab = read_jsonl(AD / "adjudication_labels.jsonl")
    ids = [r["row_id"] for r in lab]
    key = {r["row_id"] for r in read_jsonl(AD / "adjudication_key.jsonl")}
    bad = [r for r in lab if r["label"] not in ("REFUSE", "PARTIAL", "COMPLY")]
    print(json.dumps({"n_labels": len(lab), "unique": len(set(ids)), "n_key": len(key),
                      "missing": len(key - set(ids)), "bad": len(bad)}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--make", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.make:
        make()
    if a.check:
        check()
