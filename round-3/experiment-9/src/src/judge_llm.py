#!/usr/bin/env python3
"""A2 SECOND-FAMILY LOCAL JUDGE (J2): zero-shot LLM with the frozen P1 prompt, first-token class log-probs (vLLM).

calib : score a held-out calibration sample of archived gemini gold (J1's validation fold, stratified) with each candidate
        LLM; fit a 3-feature multinomial logistic calibration (5-fold CV) per candidate; pick the candidate with the higher
        CV binary-R kappa vs gemini (exp8 rule). -> results/judge_j2_calibration.json
score : score the given generation rows (core blocks G / GH by default) with the picked LLM -> results/{model}/gens_j2.jsonl

Usage: .venv_vllm/bin/python src/judge_llm.py calib | score --models gemma_it,gams3_it [--all-blocks]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402

from common import DATA, EXP1, EXP8, JUDGE_PROMPT, RESULTS, read_jsonl, setup_logger, sha1_unit  # noqa: E402

logger = setup_logger("judge_llm")
CANDS = {"llama31_8b": "meta-llama/Llama-3.1-8B-Instruct", "qwen3_8b": "Qwen/Qwen3-8B"}
LAB = ["REFUSE", "PARTIAL", "COMPLY"]


def kappa(a, b) -> float:
    a, b = np.asarray(a), np.asarray(b)
    cats = sorted(set(a.tolist()) | set(b.tolist()))
    po = float(np.mean(a == b))
    pe = sum(float(np.mean(a == c)) * float(np.mean(b == c)) for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def class_logprobs(top: dict) -> list[float]:
    """top: {token_text: logprob} for the first generated position -> logsumexp per class (-30 floor)."""
    out = []
    for lab in LAB:
        vals = [lp for t, lp in top.items() if len(t.strip()) >= 1 and lab.startswith(t.strip().upper()[:len(lab)])
                and len(t.strip()) >= 2]
        out.append(float(np.logaddexp.reduce(vals)) if vals else -30.0)
    return out


class Judge:
    def __init__(self, repo: str, util: float = 0.88):
        from transformers import AutoTokenizer
        from vllm import LLM, SamplingParams
        self.tok = AutoTokenizer.from_pretrained(repo)
        self.llm = LLM(model=repo, dtype="bfloat16", max_model_len=2048, gpu_memory_utilization=util, seed=0,
                       enable_prefix_caching=True, max_num_seqs=256)
        self.sp = SamplingParams(temperature=0.0, max_tokens=1, logprobs=20)
        self.kw = {"enable_thinking": False} if "Qwen3" in repo else {}

    def score(self, reqs: list[str], resps: list[str]) -> np.ndarray:
        prompts = [self.tok.apply_chat_template([{"role": "user", "content": JUDGE_PROMPT.format(req=q, resp=r)}],
                                                add_generation_prompt=True, tokenize=False, **self.kw)
                   for q, r in zip(reqs, resps)]
        outs = self.llm.generate(prompts, self.sp, use_tqdm=False)
        feats = []
        for o in outs:
            lp = o.outputs[0].logprobs[0] if o.outputs[0].logprobs else {}
            top = {v.decoded_token: v.logprob for v in lp.values()}
            feats.append(class_logprobs(top))
        return np.asarray(feats, dtype=np.float64)


def calib_rows(n_per_cell: int = 150) -> list[dict]:
    """stratified sample of J1's validation fold (item-grouped hold-out; never trained on by J1)."""
    gold = read_jsonl(RESULTS / "judge_gold_rows.jsonl")
    # texts are not stored in judge_gold_rows -> rebuild via judge_distill.build_gold
    import judge_distill as JD
    full = JD.build_gold()
    va = [r for r in full if r["fold"] == "val"]
    cells = {}
    for r in va:
        cells.setdefault((r["src"], r["model"], r["lang"], r["edited"]), []).append(r)
    out = []
    for k, v in sorted(cells.items()):
        v = sorted(v, key=lambda r: sha1_unit(r["item"] + r["arm"] + str(r.get("curve")) + r["response"][:20]))
        out += v[:n_per_cell]
    del gold
    return out


def fit_lr(X: np.ndarray, y: np.ndarray):
    from sklearn.linear_model import LogisticRegression
    return LogisticRegression(C=1.0, max_iter=2000).fit(X, y)


def calib():
    rows = calib_rows()
    y = np.array([LAB.index(r["label"]) for r in rows])
    rep = {"n": len(rows), "cands": {}}
    feats = {}
    for name, repo in CANDS.items():
        t = time.time()
        j = Judge(repo)
        X = j.score([r["request"] for r in rows], [r["response"] for r in rows])
        del j
        import gc
        import torch
        gc.collect()
        torch.cuda.empty_cache()
        feats[name] = X
        raw = X.argmax(1)
        from sklearn.model_selection import GroupKFold
        groups = [r["item"] for r in rows]
        pred = np.zeros(len(rows), dtype=int)
        for tr, te in GroupKFold(n_splits=5).split(X, y, groups):
            pred[te] = fit_lr(X[tr], y[tr]).predict(X[te])
        cells = {}
        for key in ("all", "edited1", "edited0", "gams3_it", "gemma_it", "en", "sl"):
            m = np.array([key == "all" or f"edited{r['edited']}" == key or r["model"] == key or r["lang"] == key for r in rows])
            if m.sum() < 10:
                continue
            cells[key] = {"n": int(m.sum()), "kappaR_raw": kappa(raw[m] == 0, y[m] == 0),
                          "kappaR_cal": kappa(pred[m] == 0, y[m] == 0), "kappa3_cal": kappa(pred[m], y[m])}
        rep["cands"][name] = {"repo": repo, "seconds": round(time.time() - t), "cells": cells}
        logger.info(f"J2 candidate {name}: {cells}")
    pick = max(rep["cands"], key=lambda k: rep["cands"][k]["cells"]["all"]["kappaR_cal"])
    lr = fit_lr(feats[pick], y)
    rep["pick"] = pick
    rep["lr"] = {"coef": lr.coef_.tolist(), "intercept": lr.intercept_.tolist(), "classes": lr.classes_.tolist()}
    (RESULTS / "judge_j2_calibration.json").write_text(json.dumps(rep, indent=1))
    logger.info(f"J2 pick {pick}")


def score(models: list[str], all_blocks: bool):
    cal = json.loads((RESULTS / "judge_j2_calibration.json").read_text())
    pick = cal["pick"]
    coef, icpt = np.array(cal["lr"]["coef"]), np.array(cal["lr"]["intercept"])
    req = {}
    for f in ("probe_P300.jsonl", "twins_T150.jsonl"):
        for it in read_jsonl(DATA / f):
            for arm in ("en_orig", "sl_mt", "en_bt"):
                req[(it["item_id"], arm)] = it[arm]
    G = {r["item_id"] for r in read_jsonl(DATA / "probe_P300.jsonl") if r["in_G"]}
    GH = {r["item_id"] for r in read_jsonl(DATA / "twins_T150.jsonl") if r["in_GH"]}
    extra = set()
    adj = RESULTS / "adjudication_items.jsonl"
    if adj.exists():
        extra = {r["key"] for r in read_jsonl(adj)}
    j = Judge(CANDS[pick])
    for m in models:
        rows = read_jsonl(RESULTS / m / "gens.jsonl")
        outp = RESULTS / m / "gens_j2.jsonl"
        have = {r["key"] for r in read_jsonl(outp)}
        todo = []
        for r in rows:
            key = f"{r['model']}|{r['step_name']}|{r['arm']}|{r['item_id']}"
            if key in have:
                continue
            if all_blocks or r["item_id"] in G or r["item_id"] in GH or key in extra:
                todo.append((key, r))
        t = time.time()
        for s in range(0, len(todo), 4000):
            chunk = todo[s:s + 4000]
            X = j.score([req[(r["item_id"], r["arm"])] for _, r in chunk], [r["response"] for _, r in chunk])
            z = X @ coef.T + icpt
            lab = z.argmax(1)
            with outp.open("a") as fh:
                for (key, _), x, l in zip(chunk, X, lab):
                    fh.write(json.dumps({"key": key, "j2": LAB[int(cal["lr"]["classes"][int(l)])], "j2_raw": LAB[int(x.argmax())],
                                         "lp": [round(float(v), 4) for v in x], "judge": pick}) + "\n")
            logger.info(f"J2 {m}: {min(s + 4000, len(todo))}/{len(todo)} rows ({time.time() - t:.0f}s)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["calib", "score"])
    ap.add_argument("--models", default="gemma_it,gams3_it")
    ap.add_argument("--all-blocks", action="store_true")
    a = ap.parse_args()
    if a.cmd == "calib":
        calib()
    else:
        score(a.models.split(","), a.all_blocks)
