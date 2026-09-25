#!/usr/bin/env python3
"""S8 PAID PRIMARY + S9 ADJUDICATION ANCHOR (OpenRouter; ledger/ledger.jsonl; hard stop in judge_paid.HARD_STOP).

Modes (comma list, each resumable through the sha1 cache):
  smoke   20 gemini SR calls: reasoning_tokens == 0, parse rate, $/call -> results/budget_projection.json
  pb_dec  P-B restricted to the 4 decisive cells at dose* (needed to build the adjudication frame)
  adj     P-A: 100 items x 4 decisive cells at dose* (400 rows), blind, gpt-4.1 + claude-haiku-4.5, deepseek tie-break
  pb      P-B: gemini U on all harmful rows of the P1 model-cells at dose*
  pc      P-C: gemini U at zero for the 4 decisive cells
  pd      P-D: gemini SR on the NLLB English text (TTJ) for Gemma/GaMS EN>SL at dose*
  drift   25 identical prompts re-sent (cache bypass tag) -> kappa vs the first pass
Outputs: labels/gemini.jsonl (readout rows), adjudication/frame.jsonl, adjudication/labels.jsonl,
results/budget_projection.json, results/paid_summary.json.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import yaml

from loguru import logger

import judge_paid as JP
from common import (WORK, ADJ, DATA, DECISIVE, GENS, LABELS, RESULTS, ROOT, SEED, append_jsonl, dump, guard_final,
                    read_jsonl, setup_logging, sha1_int, write_jsonl)

GEM_OUT = LABELS / "gemini.jsonl"
P1 = {"gemma_it": ["EN>EN", "EN>SL", "SF_SL>SL", "SF_EN>EN", "SL>EN"], "gams3_it": ["EN>EN", "EN>SL", "SF_SL>SL",
                                                                                    "SF_EN>EN"]}


def dose_star_tag(m: str) -> str:
    return yaml.safe_load((WORK / f"dose_addendum_{m}.yaml").read_text())["dose_star_tag"]


def items() -> dict:
    d = {r["item_id"]: r for r in read_jsonl(DATA / "items_conf.jsonl")}
    d.update({r["item_id"]: r for r in read_jsonl(DATA / "twins_conf.jsonl")})
    return d


BEN_CELLS = {"gemma_it": ["EN>EN", "EN>SL", "SL>SL", "SL>EN"], "gams3_it": ["EN>EN", "EN>SL", "SL>SL"]}


def ben_rows(m: str) -> list[dict]:
    """SB (secondary, pre-registered): zero-dose benign twins in the reply-language cells."""
    return [r for r in read_jsonl(GENS / f"{m}.jsonl") if r["kind"] == "twin" and r["dose_tag"] == "zero"
            and r["cell"] in BEN_CELLS[m] and r["arm"] != "EN_orig"]


def rows_for(m: str, cells: list[str], tag: str, arm_en_bt_only: bool = True) -> list[dict]:
    return [r for r in read_jsonl(GENS / f"{m}.jsonl") if r["kind"] == "harmful" and r["cell"] in cells
            and r["dose_tag"] == tag and (not arm_en_bt_only or r["arm"] != "EN_orig")]


def sr_jobs(rows: list[dict], it: dict, text_key: str = "response", ttj: dict | None = None) -> list[dict]:
    J = []
    for r in rows:
        resp = ttj[r["key"]] if ttj is not None else r[text_key]
        J.append({"model": JP.GEMINI, "task": "sr", "req": it[r["item_id"]]["EN_orig"], "resp": resp,
                  "meta": {"key": r["key"]}})
    return J


def run_sr(rows: list[dict], tag: str, readout: str = "gemini", ttj: dict | None = None) -> None:
    it = items()
    done = {(r["key"], r["readout"]) for r in read_jsonl(GEM_OUT)}
    rows = [r for r in rows if (r["key"], readout) not in done]
    if not rows:
        logger.info(f"{tag}: nothing to do")
        return
    if ttj is not None:
        rows = [r for r in rows if r["key"] in ttj]
    res = JP.run(sr_jobs(rows, it, ttj=ttj), concurrency=16, tag=tag)
    recs = []
    for r, x in zip(rows, res):
        if x.get("err") == "budget":
            continue
        recs.append({"key": r["key"], "readout": readout, "refused": x.get("refused"), "convincing": x.get("convincing"),
                     "specific": x.get("specific"), "score": x.get("score"), "U": x.get("U"),
                     "blocked": bool(x.get("blocked")), "err": x.get("err"), "reasked": bool(x.get("reasked")),
                     "cost": x.get("cost")})
    append_jsonl(GEM_OUT, recs, fsync=True)
    ok = sum(x["score"] is not None for x in recs)
    logger.info(f"{tag}: {len(recs)} labelled, parsed {ok}, blocked {sum(x['blocked'] for x in recs)}, "
                f"cumulative ${JP.spent():.4f}")


def mode_smoke() -> None:
    m = "gemma_it"
    rows = [r for r in read_jsonl(GENS / f"{m}.jsonl") if r["kind"] == "harmful" and r["arm"] != "EN_orig"]
    rows = sorted(rows, key=lambda r: sha1_int("iter5_smoke|" + r["key"]))[:20]
    it = items()
    s0 = JP.spent()
    res = JP.run(sr_jobs(rows, it), concurrency=10, tag="smoke")
    cost = JP.spent() - s0
    n_ok = sum(x.get("score") is not None for x in res)
    rt = [x.get("reasoning_tokens") for x in res]
    per = cost / max(1, len(res))
    n_pb = 288 * 9
    proj = {"n_smoke": len(res), "parsed": n_ok, "reasoning_tokens": rt, "reasoning_zero": all((t or 0) == 0 for t in rt),
            "cost_smoke": cost, "usd_per_call": per,
            "tokens_in_mean": sum((x.get("tokens_in") or 0) for x in res) / max(1, len(res)),
            "tokens_out_mean": sum((x.get("tokens_out") or 0) for x in res) / max(1, len(res)),
            "projection": {"P-B (2592 gemini)": per * n_pb, "P-C (1152 gemini)": per * 1152,
                           "P-D (576 gemini)": per * 576,
                           "P-A (400 x gpt-4.1 + 400 x haiku-4.5 + ~15% tie-break), est. from token prices":
                               400 * (1300 * 2e-6 + 120 * 8e-6) + 400 * (1300 * 1e-6 + 120 * 5e-6) + 60 * 1300 * 0.3e-6},
            "hard_stop": JP.HARD_STOP}
    proj["total_projected"] = sum(proj["projection"].values())
    dump(RESULTS / "budget_projection.json", proj)
    logger.info(f"smoke: {json.dumps(proj)[:600]}")
    recs = [{"key": r["key"], "readout": "gemini", "refused": x.get("refused"), "convincing": x.get("convincing"),
             "specific": x.get("specific"), "score": x.get("score"), "U": x.get("U"), "blocked": bool(x.get("blocked")),
             "err": x.get("err"), "reasked": bool(x.get("reasked")), "cost": x.get("cost")} for r, x in zip(rows, res)
            if x.get("err") != "budget"]
    done = {r["key"] for r in read_jsonl(GEM_OUT) if r["readout"] == "gemini"}
    append_jsonl(GEM_OUT, [x for x in recs if x["key"] not in done])


# ------------------------------------------------------------------ adjudication
def build_frame() -> list[dict]:
    fr = ADJ / "frame.jsonl"
    if fr.exists():
        return read_jsonl(fr)
    gem = {r["key"]: r for r in read_jsonl(GEM_OUT) if r["readout"] == "gemini"}
    cells = {}
    for m, c in DECISIVE:
        tag = dose_star_tag(m)
        cells[(m, c)] = {r["item_id"]: r for r in rows_for(m, [c], tag)}
    common_items = set.intersection(*[set(v) for v in cells.values()])
    ok = [i for i in common_items if all(not gem.get(cells[k][i]["key"], {}).get("blocked", False)
                                         and cells[k][i]["key"] in gem for k in cells)]
    chosen = sorted(ok, key=lambda i: sha1_int("iter5_adj|" + i))[:100]
    ttj = {r["key"]: r["response_en"] for r in read_jsonl(LABELS / "ttj.jsonl")}
    it = items()
    frame = []
    for (m, c), d in cells.items():
        for i in chosen:
            r = d[i]
            frame.append({"adj_id": f"a{sha1_int('iter5_adjid|' + r['key']) % 10**10:010d}", "key": r["key"],
                          "item_id": i, "model": m, "cell": c, "request": it[i]["EN_orig"], "response": r["response"],
                          "translation": "" if (r["out_lang"] == "en" and r.get("lid") == "en") else ttj.get(r["key"], "")})
    random.Random(SEED).shuffle(frame)
    write_jsonl(fr, frame)
    dump(ADJ / "frame_meta.json", {"n_items": len(chosen), "n_rows": len(frame), "eligible_items": len(ok),
                                   "common_items": len(common_items), "items": chosen,
                                   "missing_translation": sum(1 for f in frame if f["translation"] == "" and
                                                              f["cell"] == "EN>SL")})
    return frame


def mode_adj() -> None:
    frame = build_frame()
    out = ADJ / "labels.jsonl"
    done = {(r["adj_id"], r["rater"]) for r in read_jsonl(out)}

    def jobs(rater: str, rows: list[dict]) -> list[dict]:
        return [{"model": JP.ADJ_MODELS[rater], "task": "adj", "req": f["request"], "resp": f["response"],
                 "translation": f["translation"], "meta": {"adj_id": f["adj_id"]}} for f in rows]
    for rater in ("A", "B"):
        todo = [f for f in frame if (f["adj_id"], rater) not in done]
        if not todo:
            continue
        res = JP.run(jobs(rater, todo), concurrency=12, tag=f"adj-{rater}")
        append_jsonl(out, [{"adj_id": f["adj_id"], "rater": rater, "model": JP.ADJ_MODELS[rater],
                            **{k: x.get(k) for k in ("class4", "refused", "convincing", "specific",
                                                     "harmful_actionable", "score", "U", "reason", "blocked", "err")}}
                           for f, x in zip(todo, res) if x.get("err") != "budget"], fsync=True)
    L = read_jsonl(out)
    by = {}
    for r in L:
        by.setdefault(r["adj_id"], {})[r["rater"]] = r
    need = [f for f in frame if f["adj_id"] in by and "A" in by[f["adj_id"]] and "B" in by[f["adj_id"]]
            and (by[f["adj_id"]]["A"].get("U") != by[f["adj_id"]]["B"].get("U")
                 or by[f["adj_id"]]["A"].get("class4") != by[f["adj_id"]]["B"].get("class4")
                 or by[f["adj_id"]]["A"].get("refused") != by[f["adj_id"]]["B"].get("refused")
                 or by[f["adj_id"]]["A"].get("U") is None or by[f["adj_id"]]["B"].get("U") is None)
            and "T" not in by[f["adj_id"]]]
    if need:
        res = JP.run(jobs("T", need), concurrency=12, tag="adj-T")
        append_jsonl(out, [{"adj_id": f["adj_id"], "rater": "T", "model": JP.ADJ_MODELS["T"],
                            **{k: x.get(k) for k in ("class4", "refused", "convincing", "specific",
                                                     "harmful_actionable", "score", "U", "reason", "blocked", "err")}}
                           for f, x in zip(need, res) if x.get("err") != "budget"], fsync=True)
    resolve()


def resolve() -> None:
    frame = read_jsonl(ADJ / "frame.jsonl")
    L = read_jsonl(ADJ / "labels.jsonl")
    by: dict = {}
    for r in L:
        by.setdefault(r["adj_id"], {})[r["rater"]] = r
    final = []
    for f in frame:
        d = by.get(f["adj_id"], {})
        a, b, t = d.get("A", {}), d.get("B", {}), d.get("T", {})

        def pick(k):
            va, vb = a.get(k), b.get(k)
            if va is not None and va == vb:
                return va, "agree"
            return t.get(k), "tiebreak"
        U, hu = pick("U")
        c4, hc = pick("class4")
        ref, hr = pick("refused")
        final.append({"adj_id": f["adj_id"], "key": f["key"], "item_id": f["item_id"], "model": f["model"],
                      "cell": f["cell"], "adj_U": U, "adj_class4": c4, "adj_refused": ref,
                      "adj_explicit_refusal": (c4 == "explicit_refusal") if c4 else None,
                      "how_U": hu, "how_class4": hc, "how_refused": hr, "A_U": a.get("U"), "B_U": b.get("U"),
                      "A_class4": a.get("class4"), "B_class4": b.get("class4"), "A_refused": a.get("refused"),
                      "B_refused": b.get("refused"), "T_U": t.get("U"), "T_class4": t.get("class4")})
    write_jsonl(ADJ / "resolved.jsonl", final)
    logger.info(f"adjudication resolved {len(final)} rows; U missing {sum(x['adj_U'] is None for x in final)}")


def mode_drift() -> None:
    first = [r for r in read_jsonl(GEM_OUT) if r["readout"] == "gemini" and r.get("score") is not None]
    first = sorted(first, key=lambda r: sha1_int("iter5_drift|" + r["key"]))[:25]
    rows = {r["key"]: r for f in GENS.glob("*.jsonl") for r in read_jsonl(f)}
    it = items()
    J = [{"model": JP.GEMINI, "task": "sr", "req": it[rows[x["key"]]["item_id"]]["EN_orig"],
          "resp": rows[x["key"]]["response"], "meta": {"key": x["key"]}} for x in first]

    async def go():
        j = JP.Judge(10)
        return await asyncio.gather(*[j.one(q["model"], q["task"], q["req"], q["resp"], "", q["meta"], "|drift")
                                      for q in J])
    res = asyncio.run(go())
    from stats_core import cohen_kappa
    a = [bool(x["U"]) for x in first]
    b = [bool(y.get("U")) for y in res]
    dump(RESULTS / "drift_check.json", {"n": len(first), "kappa_U": cohen_kappa(a, b),
                                        "agree": sum(x == y for x, y in zip(a, b)),
                                        "score_absdiff_mean": sum(abs((x["score"] or 0) - (y.get("score") or 0))
                                                                  for x, y in zip(first, res)) / max(1, len(first))})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True)
    ap.add_argument("--models", default="gemma_it,gams3_it")
    a = ap.parse_args()
    setup_logging("paid")
    guard_final("paid labels")
    models = a.models.split(",")
    for mode in a.mode.split(","):
        logger.info(f"=== {mode} (spent so far ${JP.spent():.4f}, hard stop ${JP.HARD_STOP})")
        if mode == "smoke":
            mode_smoke()
        elif mode == "pb_dec":
            for m in models:
                run_sr(rows_for(m, ["EN>EN", "EN>SL"], dose_star_tag(m)), f"pb_dec-{m}")
        elif mode == "adj":
            mode_adj()
        elif mode == "pb":
            for m in models:
                run_sr(rows_for(m, P1[m], dose_star_tag(m)), f"pb-{m}")
        elif mode == "pc":
            for m in models:
                rows = rows_for(m, ["EN>EN", "EN>SL"], "zero")
                if os.environ.get("AII_PC_TRIM") == "1":
                    keep = {i for i in sorted({r["item_id"] for r in rows}, key=lambda i: sha1_int("iter5_pc|" + i))[:200]}
                    rows = [r for r in rows if r["item_id"] in keep]
                run_sr(rows, f"pc-{m}")
        elif mode == "pd":
            ttj = {r["key"]: r["response_en"] for r in read_jsonl(LABELS / "ttj.jsonl")}
            for m in models:
                run_sr(rows_for(m, ["EN>SL"], dose_star_tag(m)), f"pd-{m}", readout="gemini_ttj", ttj=ttj)
        elif mode == "extra":  # remaining budget: gemini on other doses of the decisive cells (secondary)
            for m in models:
                for tag in ("one", "lo", "hi", "rand_hi"):
                    run_sr(rows_for(m, ["EN>EN", "EN>SL"], tag), f"extra-{m}-{tag}")
        elif mode == "ben":
            for m in models:
                run_sr(ben_rows(m), f"ben-{m}")
        elif mode == "drift":
            mode_drift()
        elif mode == "resolve":
            resolve()
    s = read_jsonl(JP.LEDGER_F)
    dump(RESULTS / "paid_summary.json", {"n_calls": len(s), "usd": sum(float(x.get("cost") or 0) for x in s),
                                         "by_model": {m: {"n": sum(x["model"] == m for x in s),
                                                          "usd": sum(float(x.get("cost") or 0) for x in s
                                                                     if x["model"] == m)}
                                                      for m in sorted({x["model"] for x in s})},
                                         "errors": sum(1 for x in s if x.get("err")),
                                         "blocked": sum(1 for x in s if x.get("blocked")), "hard_stop": JP.HARD_STOP})
    logger.info(f"total spent ${JP.spent():.4f}")


if __name__ == "__main__":
    logger.catch(reraise=True)(main)()
