#!/usr/bin/env python3
"""Agreement of the local substitute judge with the primary gemini judge, per system x set x arm x condition cell.
Usage: python judge_agreement.py [--phase pilot|full] [--local FILE]"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict

import numpy as np
from sklearn.metrics import cohen_kappa_score

from common import LABELS, read_jsonl
from stats import kappa


def agreement(phase: str, local_name: str = "refusal_local.jsonl") -> dict:
    base = LABELS / "pilot" if phase == "pilot" else LABELS
    g = {r["key"]: r["label"] for r in read_jsonl(base / "refusal_gemini.jsonl")}
    loc = {r["key"]: r for r in read_jsonl(base / local_name)}
    cells = defaultdict(list)
    for k, r in loc.items():
        if g.get(k) in ("REFUSE", "PARTIAL", "COMPLY"):
            cells[(r["system"], r["set"], r["lang_arm"], r["condition"])].append((g[k], r["label"]))
            cells[("ALL", r["set"], "ALL", "ALL")].append((g[k], r["label"]))
    out = {}
    for c, pr in sorted(cells.items()):
        a = [x for x, _ in pr]
        b = [y for _, y in pr]
        ab, bb = np.array([x == "REFUSE" for x in a], float), np.array([y == "REFUSE" for y in b], float)
        ar, br = np.array([x != "COMPLY" for x in a], float), np.array([y != "COMPLY" for y in b], float)
        out["|".join(c)] = {"n": len(pr), "kappa_binary": kappa(ab, bb), "agree_binary": float((ab == bb).mean()),
                            "kappa_binary_partial_as_refusal": kappa(ar, br),
                            "kappa_3way": float(cohen_kappa_score(a, b)) if len(set(a) | set(b)) > 1 else None,
                            "refusal_gemini": float(ab.mean()), "refusal_local": float(bb.mean())}
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="pilot")
    ap.add_argument("--local", default="refusal_local.jsonl")
    a = ap.parse_args()
    for k, v in agreement(a.phase, a.local).items():
        print(k, json.dumps({kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items()}))
