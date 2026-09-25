#!/usr/bin/env python3
"""STEP 1a: enumerate every saved generation that enters a statistic into work/frame.parquet (no new generation).

Columns: source, key, item_id, model, lang, arm, condition (orig/edited/random), curve, step, kind, request, request_en,
response, priority, dose_bin, archived labels (arch_*). Also writes work/inputs_check.json.
"""
from __future__ import annotations

import json
from collections import defaultdict

import numpy as np
import pandas as pd
from loguru import logger

from common import DS1, E8, E9, E10, E11, E12, EV2, WORK, read_jsonl, setup_logger, write_json

ARM_NORM = {"en_bt": "en_bt", "sl_mt": "sl_mt", "en_orig": "en_orig", "EN_BT": "en_bt", "SL_MT": "sl_mt",
            "EN_orig": "en_orig", "L3_MT": "hu_mt"}
LANG = {"en_bt": "en", "en_orig": "en", "sl_mt": "sl", "hu_mt": "hu"}


def lab_R(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return np.nan
    return float(x == "REFUSE")


def inputs_check() -> dict:
    need = {
        "exp9_items": E9 / "results/items_final.jsonl", "exp9_probe": E9 / "data/probe_P300.jsonl",
        "exp9_twins": E9 / "data/twins_T150.jsonl", "exp9_rubric": E9 / "results/adjudication_rubric.md",
        "exp9_adj_items": E9 / "results/adjudication_items.jsonl", "exp9_adj_key": E9 / "results/adjudication_key.json",
        "exp11_rows": E11 / "results/rows_final.parquet", "exp11_adj_labels": E11 / "results/adjudication/adjudication_labels.jsonl",
        "exp11_adj_key": E11 / "results/adjudication/adjudication_key.jsonl", "exp11_protocol": E11 / "protocol.yaml",
        "exp8_items": E8 / "results/items_final.jsonl", "exp8_judge_labels": E8 / "results/judge_labels.jsonl",
        "exp8_common": E8 / "src/common.py", "exp10_test_gemma": E10 / "results/test/gemma_it/addon.jsonl",
        "exp10_test_gams": E10 / "results/test/gams3_it/addon.jsonl", "eval2_master": EV2 / "work/master.parquet",
        "eval2_relabelled": EV2 / "work/items_relabelled.jsonl.gz", "eval2_adj_labels": EV2 / "work/adj_labels_ordered.txt",
        "eval2_results": EV2 / "results/eval_results.json", "eval2_error_matrices": EV2 / "judge_error_matrices.json",
        "exp12_gates": E12 / "results/gates.json", "ds1_full_data": DS1 / "full_data_out.json",
    }
    out = {k: {"path": str(p.relative_to(p.parents[4])) if len(p.parents) > 4 else str(p), "exists": p.exists()}
           for k, p in need.items()}
    for k, v in out.items():
        if not v["exists"]:
            logger.warning(f"MISSING input {k}: {v['path']} -> fallback logged")
            v["fallback"] = {"eval2_error_matrices": "rebuild from eval2 results/eval_results.json step2_adjudication",
                             "exp12_gates": "catastrophe gate not cited", "ds1_full_data": "C1 check done on dataset dir listing"
                             }.get(k, "input not used")
    return out


def check_c1() -> dict:
    """C1: the 590-row refuseu_gold_calib block holds prompt hazard-category gold, not response refusal labels."""
    res = {"claim": "refuseu_gold_calib block is hazard-category gold for PROMPTS, not refusal labels for responses"}
    cands = list(DS1.glob("full_data_out*.json")) + list(DS1.glob("full_data_out/*.json"))
    for p in cands[:3]:
        try:
            d = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError) as e:
            res[str(p.name)] = f"unreadable: {e}"
            continue
        for ds in d.get("datasets", []):
            name = ds.get("dataset", "")
            if "gold" in name or "calib" in name:
                ex = ds["examples"][0]
                res["block"] = name
                res["n"] = len(ds["examples"])
                res["fields"] = sorted(ex.keys())
                res["example_output"] = str(ex.get("output"))[:120]
                res["has_response_field"] = any("response" in k for k in ex)
    res["verified"] = bool(res.get("block")) and not res.get("has_response_field", True)
    logger.info(f"C1 check: {res}")
    return res


def exp9_rows() -> list[dict]:
    req = {}
    for it in read_jsonl(E9 / "data/probe_P300.jsonl"):
        for a in ("en_orig", "sl_mt", "en_bt"):
            req[(it["item_id"], a)] = it[a]
        req[(it["item_id"], "EN")] = it["en_orig"]
    for it in read_jsonl(E9 / "data/twins_T150.jsonl"):
        for a in ("en_orig", "sl_mt", "en_bt"):
            if a in it:
                req[(it["item_id"], a)] = it[a]
        req[(it["item_id"], "EN")] = it["en_orig"]
    rows = []
    for r in read_jsonl(E9 / "results/items_final.jsonl"):
        cond = {"orig": "orig", "lambda": "edited", "trial": "edited", "rand": "random"}[r["curve"]]
        if r["curve"] in ("orig", "lambda"):
            pr = 1
        else:
            pr = 3
        rows.append(dict(source="exp9", key=f"exp9|{r['key']}", item_id=r["item_id"], model=r["model"], arm=r["arm"],
                         lang=LANG[r["arm"]], condition=cond, curve=r["curve"], step=float(r["step"]), kind=r["kind"],
                         request=req[(r["item_id"], r["arm"])], request_en=req[(r["item_id"], "EN")],
                         response=r["response"], priority=pr, degenerate=int(r.get("degenerate") or 0),
                         arch_j1=lab_R(r.get("j1")), arch_j2=lab_R(r.get("j2")), arch_j1_3=r.get("j1"),
                         arch_j2_3=r.get("j2"), arch_lex=float(r["lex"]) if r.get("lex") is not None else np.nan))
    return rows


def exp11_rows() -> list[dict]:
    d = pd.read_parquet(E11 / "results/rows_final.parquet")
    d = d[(d.set == "refuseu_x") & d.arm.isin(["EN_BT", "SL_MT", "L3_MT"])].rename(columns={"lambda": "lam"})
    curve_items = set(d[d.condition == "lam"].item_id)
    en_src = pd.read_parquet(E11 / "results/rows_final.parquet", columns=["item_id", "arm", "prompt_text", "set"])
    en_src = en_src[(en_src.arm == "EN_orig")].drop_duplicates("item_id").set_index("item_id").prompt_text.to_dict()
    items = {}
    for it in read_jsonl(E11 / "data/items.jsonl"):
        items[it.get("item_id")] = it
    rows = []
    for r in d.itertuples():
        arm = ARM_NORM[r.arm]
        curve_item = r.item_id in curve_items
        if arm == "hu_mt":
            pr = 3
        elif curve_item:
            pr = 1
        else:
            continue  # non-curve refuseu_x items enter no curve statistic here
        cond = {"orig": "orig", "lam": "edited", "edit": "edited"}[r.condition]
        step = 0.0 if r.condition == "orig" else float(r.lam)
        it = items.get(r.item_id, {})
        ren = en_src.get(r.item_id) or it.get("en_orig") or it.get("EN_orig") or it.get("text_en") or r.prompt_text
        rows.append(dict(source="exp11", key=f"exp11|{r.key}", item_id=r.item_id, model=r.model, arm=arm,
                         lang=LANG[arm], condition=cond, curve="lambda" if r.condition != "orig" else "orig", step=step,
                         kind="harmful", request=r.prompt_text, request_en=ren, response=r.response, priority=pr,
                         degenerate=int(bool(r.degenerate)), arch_q14=r.R_q, arch_q14_3=r.label_q,
                         arch_lex=float(r.lex)))
    return rows


def exp8_rows() -> list[dict]:
    d = pd.read_parquet(EV2 / "work/master.parquet")
    q14 = {x["row_key"]: x["label"] for x in read_jsonl(EV2 / "labels/qwen3_14b.jsonl") if "row_key" in x} \
        if (EV2 / "labels/qwen3_14b.jsonl").exists() else {}
    m24 = {x["row_key"]: x["label"] for x in read_jsonl(EV2 / "labels/mistral24b.jsonl") if "row_key" in x} \
        if (EV2 / "labels/mistral24b.jsonl").exists() else {}
    en_req = d[d.arm == "en_orig"].drop_duplicates("item_id").set_index("item_id").request.to_dict()
    p200 = {it["item_id"]: it["en_orig"] for it in read_jsonl(E8 / "data/probe_P200.jsonl")}
    rows = []
    for r in d.itertuples():
        if r.curve not in ("orig", "lambda", "trial"):
            continue
        cond = "orig" if r.curve == "orig" else "edited"
        if r.curve == "trial":
            pr = 2
        else:
            pr = 2
        rows.append(dict(source="exp8", key=f"exp8|{r.row_key}", item_id=r.item_id, model=r.model, arm=r.arm,
                         lang=LANG[r.arm], condition=cond, curve=r.curve, step=float(r.step), kind="harmful",
                         request=r.request, request_en=p200.get(r.item_id) or en_req.get(r.item_id, r.request),
                         response=r.response, priority=pr, degenerate=int(r.degenerate), in_P100=float(r.in_P100),
                         arch_gemini=lab_R(r.label3_gemini), arch_gemini_3=r.label3_gemini,
                         arch_llama8b=lab_R(r.label3_llama8b), arch_q14=lab_R(q14.get(r.row_key)),
                         arch_m24=lab_R(m24.get(r.row_key)), arch_lex=float(r.R_lex), eval2_dose_bin=r.dose_bin,
                         exp8_row_key=r.row_key))
    return rows


def exp10_rows() -> list[dict]:
    p200 = {}
    for it in read_jsonl(E8 / "data/probe_P200.jsonl"):
        for a in ("en_orig", "sl_mt", "en_bt"):
            p200[(it["item_id"], a)] = it[a]
    rows = []
    for m in ("gemma_it", "gams3_it"):
        for r in read_jsonl(E10 / f"results/test/{m}/addon.jsonl"):
            if r["set"] != "test160" or r["cond"] not in ("O", "E0") or r["arm"] not in ("en_bt", "sl_mt"):
                continue
            if (r["item_id"], r["arm"]) not in p200:
                continue
            cond = "orig" if r["cond"] == "O" else "edited"
            rows.append(dict(source="exp10", key=f"exp10|{m}|{r['cond']}|{r['arm']}|{r['item_id']}", item_id=r["item_id"],
                             model=m, arm=r["arm"], lang=LANG[r["arm"]], condition=cond, curve=r["cond"],
                             step=float(r.get("lam") or 0.0), kind="harmful", request=p200[(r["item_id"], r["arm"])],
                             request_en=p200[(r["item_id"], "en_orig")], response=r["response"], priority=2,
                             degenerate=int(r.get("degenerate") or 0), arch_lex=float(r.get("lex") or 0)))
    return rows


def add_dose_bins(df: pd.DataFrame) -> pd.DataFrame:
    """dose bin from the artifact's ARCHIVED EN-BT refusal at that step: lagwin [0.3,0.7], high >0.7, low <0.3, orig."""
    arch = np.where(df.source == "exp9", df.get("arch_j1"),
                    np.where(df.source == "exp11", df.get("arch_q14"),
                             np.where(df.source == "exp8", df.get("arch_gemini").fillna(df.get("arch_llama8b")),
                                      df.get("arch_lex"))))
    df["_arch"] = arch
    en = df[df.arm == "en_bt"].groupby(["source", "model", "curve", "step"])["_arch"].mean().to_dict()
    bins = []
    for s, m, c, st, cond in zip(df.source, df.model, df.curve, df.step, df.condition):
        if cond == "orig":
            bins.append("orig")
            continue
        if s == "exp10":
            bins.append("lagwin")  # lambda* is the EN~50% operating point by construction
            continue
        p = en.get((s, m, c, st), np.nan)
        bins.append("lagwin" if 0.3 <= p <= 0.7 else ("high" if p > 0.7 else ("low" if p < 0.3 else "unk")))
    df["dose_bin"] = bins
    df["arch_en_rate_step"] = [en.get(k, np.nan) for k in zip(df.source, df.model, df.curve, df.step)]
    return df.drop(columns=["_arch"])


@logger.catch(reraise=True)
def main():
    setup_logger("build_frame")
    ic = inputs_check()
    ic["C1_gold_calib_check"] = check_c1()
    write_json(WORK / "inputs_check.json", ic)
    rows = exp9_rows()
    logger.info(f"exp9 rows {len(rows)}")
    r11 = exp11_rows()
    logger.info(f"exp11 rows {len(r11)}")
    r8 = exp8_rows()
    logger.info(f"exp8 rows {len(r8)}")
    r10 = exp10_rows()
    logger.info(f"exp10 rows {len(r10)}")
    df = pd.DataFrame(rows + r11 + r8 + r10)
    assert df.key.is_unique, df.key[df.key.duplicated()].head()
    df = add_dose_bins(df)
    df["resp_trunc"] = df.response.fillna("").str.slice(0, 2000)
    df.to_parquet(WORK / "frame.parquet", index=False)
    summ = df.groupby(["source", "model", "curve", "condition", "lang", "priority"]).size().reset_index(name="n")
    logger.info("\n" + summ.to_string())
    write_json(WORK / "frame_summary.json", {"n_rows": len(df), "by_cell": summ.to_dict("records"),
                                             "dose_bins": {f"{a}|{b}": int(v) for (a, b), v in df.groupby(["source", "dose_bin"]).size().items()}})


if __name__ == "__main__":
    main()
