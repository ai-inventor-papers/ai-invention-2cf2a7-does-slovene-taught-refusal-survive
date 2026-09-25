#!/usr/bin/env python3
"""Choose the substitute primary judge from the calibration outputs (amendment judge_substitution_budget_exhausted).

Reads results/judge_local/<judge>.jsonl calib rows for every candidate, scores each against the frozen gemini labels on the
1,000-row gemma_it calibration set (binary R = REFUSE Cohen kappa, plus 3-way agreement and per-language kappa), and writes
results/judge_local/selection.json: {"primary": <higher-kappa judge>, "second": <other>, "table": {...}}.
Tie within 0.01 -> qwen3_8b (listed first in the amendment)."""
from __future__ import annotations

import json

import numpy as np

from common import RESULTS, read_jsonl
from judge_local import JUDGES, gemini_labels

LAB = ["REFUSE", "PARTIAL", "COMPLY"]


def kappa(a, b):
    a, b = np.asarray(a), np.asarray(b)
    if len(a) == 0:
        return float("nan"), float("nan")
    po = float(np.mean(a == b))
    pe = sum(float(np.mean(a == c)) * float(np.mean(b == c)) for c in np.union1d(a, b))
    return ((po - pe) / (1 - pe) if pe < 1 else float("nan")), po


def main():
    gem = gemini_labels()
    lang = {}
    for r in read_jsonl(RESULTS / "items_final.jsonl"):
        lang[r["item_id"], r["arm"]] = "en" if r["arm"] in ("en_bt", "en_orig") else "sl"
    # arm from row_key: model|arm|curve|step|item
    def arm_of(rk):
        return rk.split("|")[1]

    table = {}
    for j in JUDGES:
        f = RESULTS / "judge_local" / f"{j}.jsonl"
        if not f.exists():
            continue
        rows = [r for r in read_jsonl(f) if r.get("set") == "calib" and r["row_key"] in gem]
        if not rows:
            continue
        a = [int(r["label"] == "REFUSE") for r in rows]
        b = [int(gem[r["row_key"]] == "REFUSE") for r in rows]
        k, po = kappa(a, b)
        k3, po3 = kappa([r["label"] for r in rows], [gem[r["row_key"]] for r in rows])
        top1 = float(np.mean([r.get("label_token_is_top1", False) for r in rows]))
        per_lang = {}
        for lg in ("en", "sl"):
            sub = [r for r in rows if arm_of(r["row_key"]) in (("en_bt", "en_orig") if lg == "en" else ("sl_mt",))]
            if sub:
                kk, _ = kappa([int(r["label"] == "REFUSE") for r in sub], [int(gem[r["row_key"]] == "REFUSE") for r in sub])
                per_lang[lg] = {"n": len(sub), "kappa_R": kk}
        table[j] = {"n": len(rows), "kappa_R": k, "agree_R": po, "kappa_3way": k3, "agree_3way": po3,
                    "label_is_top1_frac": top1, "per_lang": per_lang,
                    "rate_local_R": float(np.mean(a)), "rate_gemini_R": float(np.mean(b))}
    ranked = sorted(table, key=lambda j: (-table[j]["kappa_R"], j != "qwen3_8b"))
    primary = ranked[0]
    # tie within 0.01 -> qwen3_8b
    if "qwen3_8b" in table and table["qwen3_8b"]["kappa_R"] >= table[primary]["kappa_R"] - 0.01:
        primary = "qwen3_8b"
    second = [j for j in ranked if j != primary][0] if len(ranked) > 1 else None
    sel = {"primary": primary, "second": second, "rule": "argmax binary-R Cohen kappa vs gemini on 1000-row gemma_it calib; "
           "tie within 0.01 -> qwen3_8b", "table": table,
           "repos": {j: JUDGES[j]["repo"] for j in table}}
    (RESULTS / "judge_local" / "selection.json").write_text(json.dumps(sel, indent=2))
    print(json.dumps(sel, indent=2))


if __name__ == "__main__":
    main()
