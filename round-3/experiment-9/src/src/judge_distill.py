#!/usr/bin/env python3
"""A2 LOCAL PRIMARY JUDGE (J1): gemini-distilled 3-way refusal classifier.

Training gold = ARCHIVED real google/gemini-2.5-flash labels under the frozen P1 prompt:
  (a) exp8 results/items_final.jsonl: Gemma-3-12B-IT responses (orig, lambda-scaled Heretic, graded ablation, random
      control, 29 Heretic trials; EN-orig / EN-BT / SL-MT; 64 and 128 tokens) with label3_gemini;
  (b) iter-1 exp1 outputs gen_{model}.jsonl / gen_mt_{model}.jsonl + judge_gemini.jsonl: Gemma AND GaMS unedited
      responses to RefusEU EN / native-SL / SL-MT prompts (64 tokens).
EXCLUDED: every row whose item (pair_id or normalised EN text) is in this artifact's P300 / DEV12 / twin sources.
Split: item-grouped (sha1(item) -> 15% validation). Model: microsoft/mdeberta-v3-base, input = (response, request)
truncated to 320 tokens (request truncated first). Reports held-out kappa per source x model x language x edited.

Usage: .venv/bin/python src/judge_distill.py train | predict --files results/gemma_it/gens.jsonl,...
"""
from __future__ import annotations

import argparse
import json
import math
import time
from collections import defaultdict

import numpy as np
import torch

from common import DATA, EXP1, EXP8, RESULTS, WS, norm_text, read_jsonl, setup_logger, sha1_hex, sha1_unit, write_jsonl
from judge_model_io import ensure_model_file, split_model_file

logger = setup_logger("judge_distill")
LAB = ["REFUSE", "PARTIAL", "COMPLY"]
BASE = "microsoft/mdeberta-v3-base"
MDIR = WS / "judge_model" / "mdeberta_gemini_distill"
MAXLEN = 256
MAX_TRAIN = 12000  # stratified cap (GPU is shared with the Heretic phase)


def kappa(a: list, b: list) -> float:
    a, b = np.asarray(a), np.asarray(b)
    if len(a) == 0:
        return float("nan")
    cats = sorted(set(a) | set(b))
    po = float(np.mean(a == b))
    pe = sum(float(np.mean(a == c)) * float(np.mean(b == c)) for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def excluded_items() -> tuple[set, set]:
    ids, txt = set(), set()
    for f in ("probe_P300.jsonl", "dev12.jsonl"):
        for r in read_jsonl(DATA / f):
            ids.add(r["item_id"])
            txt.add(sha1_hex(norm_text(r["en_orig"])))
    return ids, txt


def build_gold() -> list[dict]:
    ex_ids, ex_txt = excluded_items()
    rows = []
    # (a) exp8
    req = {}
    for f in ("probe_P200.jsonl", "dev20.jsonl", "harmless100.jsonl"):
        for it in read_jsonl(EXP8 / "data" / f):
            for arm in ("en_orig", "sl_mt", "en_bt"):
                if arm in it:
                    req[(it["item_id"], arm)] = it[arm]
    n_ex = 0
    for r in read_jsonl(EXP8 / "results" / "items_final.jsonl"):
        lab = r.get("label3_gemini")
        if lab not in LAB or (r["item_id"], r["arm"]) not in req:
            continue
        q = req[(r["item_id"], r["arm"])]
        if sha1_hex(norm_text(req.get((r["item_id"], "en_orig"), q))) in ex_txt:
            n_ex += 1
            continue
        edited = int(r["curve"] not in ("orig", "prefill") and not (r["curve"] in ("lambda", "ablate") and r["step"] == 0))
        rows.append({"src": "exp8", "model": r["model"], "lang": "sl" if r["arm"] == "sl_mt" else "en", "arm": r["arm"],
                     "edited": edited, "item": r["item_id"], "request": q, "response": r["response"], "label": lab,
                     "n_tokens": r.get("n_tokens"), "curve": r["curve"]})
    # (b) iter-1 exp1
    pairs = {p["pair_id"]: p for p in read_jsonl(EXP1 / "data" / "pairs.jsonl")}
    mtp = {p["pair_id"]: p for p in read_jsonl(EXP1 / "data" / "mt_parallel.jsonl")}
    labs = {}
    for r in read_jsonl(EXP1 / "outputs" / "judge_gemini.jsonl"):
        if r.get("label") in LAB and not r.get("fallback"):
            labs[(r["model"], r["key"])] = r["label"]
    for m in ("gemma_it", "gams3_it"):
        for f in (f"gen_{m}.jsonl", f"gen_mt_{m}.jsonl"):
            for g in read_jsonl(EXP1 / "outputs" / f):
                lab = labs.get((m, g["key"]))
                if lab is None:
                    continue
                pid = g["pair_id"]
                p = pairs.get(pid)
                if p is None:
                    continue
                if pid in ex_ids or sha1_hex(norm_text(p["prompt_en"].strip().strip('"'))) in ex_txt:
                    n_ex += 1
                    continue
                if "mt" in f:
                    q = (mtp.get(pid) or {}).get("prompt_sl_mt")
                    lang, arm = "sl", "sl_mt"
                else:
                    lang = g["lang"]
                    q = p["prompt_en"] if lang == "en" else p["prompt_sl"]
                    arm = "en_orig" if lang == "en" else "sl_native"
                if not q:
                    continue
                rows.append({"src": "exp1", "model": m, "lang": lang, "arm": arm, "edited": 0, "item": pid, "request": q,
                             "response": g["response"], "label": lab, "n_tokens": g.get("n_tokens"), "curve": "orig"})
    for r in rows:
        r["fold"] = "val" if sha1_unit(str(r["item"]) + "|judge_split") < 0.15 else "train"
    logger.info(f"gold rows {len(rows)} (excluded {n_ex} rows on probe items); by src/model/lang/edited: "
                f"{dict(sorted(defaultdict(int, {k: sum(1 for r in rows if (r['src'], r['model'], r['lang'], r['edited']) == k) for k in {(r['src'], r['model'], r['lang'], r['edited']) for r in rows}}).items()))}")
    return rows


def encode(tok, resp: list[str], req: list[str]):
    return tok(resp, req, truncation="only_second", max_length=MAXLEN, padding=True, return_tensors="pt")


@torch.inference_mode()
def predict_probs(model, tok, resp: list[str], req: list[str], bs: int = 32) -> np.ndarray:
    dev = next(model.parameters()).device
    bs = bs if dev.type == "cuda" else 16
    order = sorted(range(len(resp)), key=lambda i: len(resp[i]) + len(req[i]))
    out = np.zeros((len(resp), 3), dtype=np.float32)
    for s in range(0, len(order), bs):
        idx = order[s:s + bs]
        enc = encode(tok, [resp[i] for i in idx], [req[i] for i in idx]).to(dev)
        lg = model(**enc).logits.float()
        out[idx] = torch.softmax(lg, -1).cpu().numpy()
    return out


def train():
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup
    torch.manual_seed(20260925)
    gold = build_gold()
    write_jsonl(RESULTS / "judge_gold_rows.jsonl", [{k: v for k, v in r.items() if k not in ("request", "response")} for r in gold])
    tr = [r for r in gold if r["fold"] == "train"]
    if len(tr) > MAX_TRAIN:
        cells = defaultdict(list)
        for r in tr:
            cells[(r["src"], r["model"], r["lang"], r["edited"])].append(r)
        per = max(1, MAX_TRAIN // len(cells))
        tr = []
        for k, v in sorted(cells.items()):
            v = sorted(v, key=lambda r: sha1_unit(r["item"] + r["arm"] + str(r.get("curve")) + r["response"][:24]))
            tr += v[:per]
        logger.info(f"train fold subsampled to {len(tr)} rows ({per} per cell over {len(cells)} cells)")
    va = [r for r in gold if r["fold"] == "val"]
    tok = AutoTokenizer.from_pretrained(BASE)
    torch.cuda.set_per_process_memory_fraction(0.30)  # shares the GPU with the Heretic phase: this process OOMs first
    model = AutoModelForSequenceClassification.from_pretrained(BASE, num_labels=3, dtype=torch.float32).cuda()
    for p_ in model.base_model.embeddings.parameters():  # frozen 250k-vocab embeddings (memory); encoder + head trained
        p_.requires_grad_(False)
    epochs, bs, lr = 2, 8, 3e-5
    opt = torch.optim.AdamW([p_ for p_ in model.parameters() if p_.requires_grad], lr=lr, weight_decay=0.01)
    n_steps = epochs * math.ceil(len(tr) / bs)
    sch = get_linear_schedule_with_warmup(opt, int(0.06 * n_steps), n_steps)
    y = torch.tensor([LAB.index(r["label"]) for r in tr])
    t0 = time.time()
    rng = np.random.default_rng(20260925)
    step = 0
    for ep in range(epochs):
        model.train()
        chunks = np.array_split(sorted(rng.permutation(len(tr)).tolist(),
                                       key=lambda i: len(tr[i]["response"]) + len(tr[i]["request"])),
                                math.ceil(len(tr) / bs))
        rng.shuffle(chunks)
        for idx in chunks:
            enc = encode(tok, [tr[i]["response"] for i in idx], [tr[i]["request"] for i in idx]).to("cuda")
            out = model(**enc, labels=y[idx].cuda())
            out.loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sch.step()
            opt.zero_grad()
            step += 1
            if step % 300 == 0:
                logger.info(f"ep {ep} step {step}/{n_steps} loss {out.loss.item():.4f} ({time.time() - t0:.0f}s)")
        model.eval()
        pr = predict_probs(model, tok, [r["response"] for r in va], [r["request"] for r in va])
        pl = [LAB[i] for i in pr.argmax(1)]
        k3 = kappa(pl, [r["label"] for r in va])
        kR = kappa([int(p == "REFUSE") for p in pl], [int(r["label"] == "REFUSE") for r in va])
        logger.info(f"epoch {ep}: val kappa3 {k3:.3f} kappaR {kR:.3f}")
    MDIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(MDIR))
    tok.save_pretrained(str(MDIR))
    split_model_file(MDIR)  # 1.06 GB fp32 checkpoint -> 95 MB parts (publishing limit); see src/judge_model_io.py
    # held-out validation report
    pr = predict_probs(model, tok, [r["response"] for r in va], [r["request"] for r in va])
    rep = {"n_train": len(tr), "n_val": len(va), "base": BASE, "epochs": epochs, "bs": bs, "lr": lr, "maxlen": MAXLEN,
           "train_seconds": round(time.time() - t0), "cells": {}}
    cells = defaultdict(list)
    for r, p in zip(va, pr):
        lab = LAB[int(p.argmax())]
        for key in ("all", f"{r['model']}|{r['lang']}", f"{r['model']}|{r['lang']}|edited{r['edited']}",
                    f"{r['src']}|{r['model']}|edited{r['edited']}", f"edited{r['edited']}"):
            cells[key].append((lab, r["label"]))
    for k, v in sorted(cells.items()):
        a, b = [x[0] for x in v], [x[1] for x in v]
        rep["cells"][k] = {"n": len(v), "kappa3": kappa(a, b),
                           "kappaR": kappa([int(x == "REFUSE") for x in a], [int(x == "REFUSE") for x in b]),
                           "kappaRP": kappa([int(x != "COMPLY") for x in a], [int(x != "COMPLY") for x in b]),
                           "rate_R_gold": float(np.mean([x == "REFUSE" for x in b])),
                           "rate_R_pred": float(np.mean([x == "REFUSE" for x in a])),
                           "sens_R": float(np.mean([x == "REFUSE" for x, g in zip(a, b) if g == "REFUSE"])) if "REFUSE" in b else None,
                           "spec_R": float(np.mean([x != "REFUSE" for x, g in zip(a, b) if g != "REFUSE"])) if any(g != "REFUSE" for g in b) else None}
    (RESULTS / "judge_j1_validation.json").write_text(json.dumps(rep, indent=1))
    logger.info(json.dumps({k: {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items()}
                            for k, v in rep["cells"].items()})[:3000])


def predict(files: list[str], device: str = "cuda"):
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    ensure_model_file(MDIR)  # reassemble model.safetensors from model_parts/ if needed
    tok = AutoTokenizer.from_pretrained(str(MDIR))
    model = AutoModelForSequenceClassification.from_pretrained(str(MDIR)).to(device).eval()
    if device == "cpu":
        torch.set_num_threads(40)
    req = {}
    for f in ("probe_P300.jsonl", "twins_T150.jsonl", "dev12.jsonl", "gate_harmless40.jsonl"):
        for it in read_jsonl(DATA / f):
            for arm in ("en_orig", "sl_mt", "en_bt"):
                if arm in it:
                    req[(it["item_id"], arm)] = it[arm]
    for f in files:
        rows = read_jsonl(WS / f)
        outp = (WS / f).with_name((WS / f).stem + "_j1.jsonl")
        have = {}
        for r in read_jsonl(outp):
            have[r["key"]] = r
        todo = [r for r in rows if row_key(r) not in have]
        if not todo:
            continue
        t = time.time()
        pr = predict_probs(model, tok, [r["response"] for r in todo], [req[(r["item_id"], r["arm"])] for r in todo])
        new = [{"key": row_key(r), "j1": LAB[int(p.argmax())], "p": [round(float(x), 5) for x in p]} for r, p in zip(todo, pr)]
        with outp.open("a") as fh:
            for n in new:
                fh.write(json.dumps(n) + "\n")
        logger.info(f"J1 predicted {len(new)} rows of {f} in {time.time() - t:.0f}s")


def row_key(r: dict) -> str:
    return f"{r['model']}|{r['step_name']}|{r['arm']}|{r['item_id']}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["train", "predict", "gold"])
    ap.add_argument("--files", default="")
    ap.add_argument("--device", default="cuda")
    a = ap.parse_args()
    if a.cmd == "train":
        train()
    elif a.cmd == "gold":
        build_gold()
    else:
        predict([f for f in a.files.split(",") if f], a.device)
