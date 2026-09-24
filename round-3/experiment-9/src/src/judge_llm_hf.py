#!/usr/bin/env python3
"""J2 SECOND-FAMILY JUDGE, HF prefill-only variant (no vLLM): Llama-3.1-8B-Instruct / Qwen3-8B with the frozen P1 prompt,
one forward pass per row, class scores = logsumexp over the first-token ids that begin REFUSE / PARTIAL / COMPLY.

calib : score a stratified sample of the archived-gemini validation fold (the rows J1 was NOT trained on) with each
        candidate, fit a 3-feature multinomial logistic calibration with GroupKFold by item, pick the higher binary-R
        kappa (exp8 rule)  -> results/judge_j2_calibration.json
score : score the core blocks G / GH (and any adjudication rows) of results/{model}/gens.jsonl -> gens_j2.jsonl

Usage: .venv/bin/python src/judge_llm_hf.py calib|score [--models ...] [--all-blocks]
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402

try:
    from torch._native import registry as _nr
    _nr.deregister_op_overrides(disable_dsl_names=["triton", "cutedsl", "helion", "nvmath"])
except (ImportError, AttributeError, RuntimeError, ValueError):
    pass

from common import DATA, JUDGE_PROMPT, RESULTS, read_jsonl, setup_logger, sha1_unit  # noqa: E402

logger = setup_logger("judge_llm_hf")
CANDS = {"llama31_8b": "meta-llama/Llama-3.1-8B-Instruct", "qwen3_8b": "Qwen/Qwen3-8B"}
LAB = ["REFUSE", "PARTIAL", "COMPLY"]
MAXLEN = 900


def kappa(a, b) -> float:
    a, b = np.asarray(a), np.asarray(b)
    cats = sorted(set(a.tolist()) | set(b.tolist()))
    po = float(np.mean(a == b))
    pe = sum(float(np.mean(a == c)) * float(np.mean(b == c)) for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


class Judge:
    def __init__(self, repo: str):
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.tok = AutoTokenizer.from_pretrained(repo)
        self.tok.padding_side = "left"
        if self.tok.pad_token is None:
            self.tok.pad_token = self.tok.eos_token
        self.model = AutoModelForCausalLM.from_pretrained(repo, dtype=torch.bfloat16).cuda().eval()
        self.kw = {"enable_thinking": False} if "Qwen3" in repo else {}
        V = len(self.tok)
        self.ids = []
        vocab = self.tok.get_vocab()
        for lab in LAB:
            got = []
            for t, i in vocab.items():
                s = t.replace("Ġ", " ").replace("▁", " ").strip().upper()
                if len(s) >= 2 and lab.startswith(s[:len(lab)]) and i < V:
                    got.append(i)
            self.ids.append(sorted(set(got)))
        logger.info(f"{repo}: first-token id counts {[len(x) for x in self.ids]}")

    @torch.inference_mode()
    def score(self, reqs: list[str], resps: list[str], bs: int = 16) -> np.ndarray:
        texts = [self.tok.apply_chat_template([{"role": "user", "content": JUDGE_PROMPT.format(req=q, resp=r)}],
                                              add_generation_prompt=True, tokenize=False, **self.kw)
                 for q, r in zip(reqs, resps)]
        out = np.zeros((len(texts), 3), dtype=np.float64)
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
        t0 = time.time()
        for s in range(0, len(order), bs):
            idx = order[s:s + bs]
            enc = self.tok([texts[i] for i in idx], return_tensors="pt", padding=True, truncation=True,
                           max_length=MAXLEN, add_special_tokens=False).to("cuda")
            lg = self.model(**enc, use_cache=False).logits[:, -1].float()
            lp = F.log_softmax(lg, -1)
            for j, lab_ids in enumerate(self.ids):
                out[idx, j] = torch.logsumexp(lp[:, lab_ids], -1).cpu().numpy()
            del enc, lg, lp
            if (s // bs) % 50 == 0:
                logger.info(f"  {min(s + bs, len(order))}/{len(order)} rows ({time.time() - t0:.0f}s)")
        return out

    def close(self):
        del self.model
        gc.collect()
        torch.cuda.empty_cache()


def fit_lr(X, y):
    from sklearn.linear_model import LogisticRegression
    return LogisticRegression(C=1.0, max_iter=2000).fit(X, y)


def calib(n_per_cell: int = 60):
    import judge_distill as JD
    full = JD.build_gold()
    va = [r for r in full if r["fold"] == "val"]
    cells = {}
    for r in va:
        cells.setdefault((r["src"], r["model"], r["lang"], r["edited"]), []).append(r)
    rows = []
    for k, v in sorted(cells.items()):
        v = sorted(v, key=lambda r: sha1_unit(r["item"] + r["arm"] + str(r.get("curve")) + r["response"][:24]))
        rows += v[:n_per_cell]
    logger.info(f"J2 calibration rows {len(rows)} over {len(cells)} cells")
    y = np.array([LAB.index(r["label"]) for r in rows])
    groups = [r["item"] for r in rows]
    rep = {"n": len(rows), "cands": {}}
    feats = {}
    from sklearn.model_selection import GroupKFold
    for name, repo in CANDS.items():
        t = time.time()
        j = Judge(repo)
        X = j.score([r["request"] for r in rows], [r["response"] for r in rows])
        j.close()
        feats[name] = X
        raw = X.argmax(1)
        pred = np.zeros(len(rows), dtype=int)
        for tr, te in GroupKFold(n_splits=5).split(X, y, groups):
            pred[te] = fit_lr(X[tr], y[tr]).predict(X[te])
        cs = {}
        for key in ("all", "edited1", "edited0", "gams3_it", "gemma_it", "en", "sl"):
            m = np.array([key == "all" or f"edited{r['edited']}" == key or r["model"] == key or r["lang"] == key for r in rows])
            if m.sum() >= 10:
                cs[key] = {"n": int(m.sum()), "kappaR_raw": kappa(raw[m] == 0, y[m] == 0),
                           "kappaR_cal": kappa(pred[m] == 0, y[m] == 0), "kappa3_cal": kappa(pred[m], y[m])}
        rep["cands"][name] = {"repo": repo, "seconds": round(time.time() - t), "cells": cs}
        logger.info(f"J2 {name}: {cs}")
    pick = max(rep["cands"], key=lambda k: rep["cands"][k]["cells"]["all"]["kappaR_cal"])
    lr = fit_lr(feats[pick], y)
    rep.update({"pick": pick, "engine": "hf_prefill",
                "lr": {"coef": lr.coef_.tolist(), "intercept": lr.intercept_.tolist(), "classes": lr.classes_.tolist()}})
    (RESULTS / "judge_j2_calibration.json").write_text(json.dumps(rep, indent=1))
    logger.info(f"J2 pick {pick}")


def score(models: list[str], all_blocks: bool):
    cal = json.loads((RESULTS / "judge_j2_calibration.json").read_text())
    coef, icpt, classes = np.array(cal["lr"]["coef"]), np.array(cal["lr"]["intercept"]), cal["lr"]["classes"]
    req = {}
    for f in ("probe_P300.jsonl", "twins_T150.jsonl"):
        for it in read_jsonl(DATA / f):
            for arm in ("en_orig", "sl_mt", "en_bt"):
                req[(it["item_id"], arm)] = it[arm]
    G = {r["item_id"] for r in read_jsonl(DATA / "probe_P300.jsonl") if r["in_G"]}
    GH = {r["item_id"] for r in read_jsonl(DATA / "twins_T150.jsonl") if r["in_GH"]}
    j = Judge(CANDS[cal["pick"]])
    for m in models:
        rows = read_jsonl(RESULTS / m / "gens.jsonl")
        outp = RESULTS / m / "gens_j2.jsonl"
        have = {r["key"] for r in read_jsonl(outp)}
        todo = []
        for r in rows:
            key = f"{r['model']}|{r['step_name']}|{r['arm']}|{r['item_id']}"
            if key in have:
                continue
            if all_blocks or r["item_id"] in G or r["item_id"] in GH:
                todo.append((key, r))
        logger.info(f"J2 scoring {len(todo)} rows of {m}")
        for s in range(0, len(todo), 2000):
            chunk = todo[s:s + 2000]
            X = j.score([req[(r["item_id"], r["arm"])] for _, r in chunk], [r["response"] for _, r in chunk])
            lab = (X @ coef.T + icpt).argmax(1)
            with outp.open("a") as fh:
                for (key, _), x, l in zip(chunk, X, lab):
                    fh.write(json.dumps({"key": key, "j2": LAB[int(classes[int(l)])], "j2_raw": LAB[int(x.argmax())],
                                         "lp": [round(float(v), 4) for v in x], "judge": cal["pick"]}) + "\n")
            logger.info(f"  {m}: {min(s + 2000, len(todo))}/{len(todo)}")
    j.close()


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
