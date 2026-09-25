#!/usr/bin/env python3
"""STEP 1d + STEP 2: cost projection and paid labelling passes.

usage: python label_passes.py project | primary [P] | second | ttj | asr   [--limit N for scale-up]
All passes share labels/ledger.jsonl (cache, resume, HARD STOP at $8 over the whole ledger).
"""
from __future__ import annotations

import asyncio
import functools
import json
import re
import sys

import numpy as np
import pandas as pd
from loguru import logger

from common import (JUDGE_PROMPT, JUDGE_PROMPT_SHA, PROMPTS, RESULTS, SECOND, SEED, WORK, setup_logger, sha1, sha1_unit,
                    write_json)
from judge_api import ledger_load, run_jobs

SR_PROMPT = (PROMPTS / "strongreject.txt").read_text() if (PROMPTS / "strongreject.txt").exists() else ""
SR_SHA = sha1(SR_PROMPT)
PRICE = {"google/gemini-2.5-flash": (0.30, 2.50), "google/gemini-2.5-flash-lite": (0.10, 0.40), SECOND: (0.40, 1.60)}


@functools.lru_cache(maxsize=1)
def chosen_primary() -> str:
    return json.loads((RESULTS / "tier_bakeoff.json").read_text())["chosen"]


@functools.lru_cache(maxsize=1)
def reuse_archived() -> bool:
    return bool(json.loads((RESULTS / "tier_bakeoff.json").read_text())["archived_exp8_gemini_reuse"])


def frame() -> pd.DataFrame:
    return pd.read_parquet(WORK / "frame.parquet")


def p1_job(judge, key, req, resp, pass_):
    content = JUDGE_PROMPT.format(req=req, resp=resp)
    return {"cache": sha1(f"{judge}|{JUDGE_PROMPT_SHA}|{content}"), "key": key, "judge": judge, "pass": pass_,
            "content": content, "max_tokens": 5, "prompt_sha": JUDGE_PROMPT_SHA}


def primary_rows(df: pd.DataFrame) -> pd.DataFrame:
    """rows that need a fresh primary label (archived exp8 Gemma gemini labels reused when the drift check allows)."""
    need = df[df.lang != "hu"]  # cut ladder step 3 (AM1): Hungarian L3 rows dropped
    b_gams = (need.source == "exp8") & (need.model == "gams3_it") & (need.curve == "trial")
    keep_b = np.array([sha1_unit(f"{i}|{s}|Bcut") < 0.30 for i, s in zip(need.item_id, need.step)])
    need = need[~b_gams | keep_b]  # cut ladder step 1 (AM1): exp8 B GaMS -> 30% item sample within trial (both arms kept)
    if reuse_archived():
        need = df[~((df.source == "exp8") & df.arch_gemini_3.isin(["REFUSE", "PARTIAL", "COMPLY"]))]
    return need


def second_sample(df: pd.DataFrame) -> pd.DataFrame:
    """stratified inclusion within source x model x lang x condition x dose_bin; pi stored."""
    d = df[(df.priority <= 2) & (df.lang != "hu")].copy()
    d["cell"] = d.source + "|" + d.model + "|" + d.lang + "|" + d.condition + "|" + d.dose_bin
    decisive = d.source.isin(["exp9", "exp11"]) & (d.lang == "sl") & (d.condition == "edited")
    N = d.groupby("cell").key.transform("size")
    base = np.where(decisive, 0.25, 0.15)
    base = np.where(d.dose_bin == "lagwin", np.minimum(1.0, 3 * base), base)
    pi = np.where(d.condition == "orig", np.minimum(1.0, 60.0 / N), np.minimum(1.0, np.maximum(base, 60.0 / N)))
    d["pi_second"] = pi
    d["u"] = [sha1_unit(k + "|second") for k in d.key]
    return d[d.u < d.pi_second]


def ttj_rows(df: pd.DataFrame) -> pd.DataFrame:
    m = (((df.source == "exp9") & df.curve.isin(["orig", "lambda"]) & (df.kind == "harmful"))
         | ((df.source == "exp11") & (df.priority == 1)) | (df.source == "exp10"))
    d = df[m & df.arm.isin(["en_bt", "sl_mt"]) & df.source.isin(["exp9", "exp11"])]
    # cut ladder step 6 (AM1): TTJ restricted to exp9 and exp11 bracket steps + lambda 0
    keep = np.zeros(len(d), bool)
    for src in ("exp9", "exp11"):
        for mdl in ("gemma_it", "gams3_it"):
            st = bracket_steps(df, src, mdl)
            keep |= ((d.source == src) & (d.model == mdl) & d.step.isin(st)).values
    d = d[keep]
    lam_items = set(df[(df.source == "exp9") & (df.curve == "lambda")].item_id)
    return d[(d.source != "exp9") | d.item_id.isin(lam_items)]


def bracket_steps(df: pd.DataFrame, source: str, model: str) -> list[float]:
    """steps bracketing EN-BT refusal 50% under the PRIMARY labels (2 below-nearest / 2 above-nearest) + step 0."""
    lab = primary_label_map()
    sub = df[(df.source == source) & (df.model == model) & (df.arm == "en_bt") & (df.kind == "harmful")
             & ((df.curve == "lambda") | (df.curve == "orig"))]
    r = sub.assign(R=[1.0 if lab.get(k) == "REFUSE" else (np.nan if lab.get(k) is None else 0.0) for k in sub.key])
    rate = r.groupby("step").R.mean()
    hi = sorted([s for s, v in rate.items() if v >= 0.5 and s > 0])
    lo = sorted([s for s, v in rate.items() if v < 0.5 and s > 0])
    br = hi[-2:] + lo[:2]
    return sorted(set(br + [0.0]))


_PL = None


def primary_label_map() -> dict:
    global _PL
    if _PL is None:
        df = frame()
        judge = chosen_primary()
        reuse = reuse_archived()
        done, _ = ledger_load()
        _PL = {}
        for r in df.itertuples():
            if reuse and r.source == "exp8" and r.arch_gemini_3 in ("REFUSE", "PARTIAL", "COMPLY"):
                _PL[r.key] = r.arch_gemini_3
                continue
            j = p1_job(judge, r.key, r.request, r.response, "primary")
            if j["cache"] in done:
                _PL[r.key] = done[j["cache"]]["label"]
    return _PL


def asr_rows(df: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for src in ("exp9", "exp11"):
        for m in ("gemma_it", "gams3_it"):
            st = bracket_steps(df, src, m)
            sub = df[(df.source == src) & (df.model == m) & (df.kind == "harmful") & df.arm.isin(["en_bt", "sl_mt"])
                     & df.curve.isin(["orig", "lambda"]) & df.step.isin(st)]
            if src == "exp9":  # orig rows restricted to the 100 lambda-curve items
                lam_items = set(df[(df.source == "exp9") & (df.curve == "lambda")].item_id)
                sub = sub[sub.item_id.isin(lam_items)]
            parts.append(sub)
    return pd.concat(parts)


def sr_job(judge, key, req, resp):
    content = SR_PROMPT.replace("{forbidden_prompt}", req).replace("{response}", resp)
    return {"cache": sha1(f"{judge}|{SR_SHA}|{content}"), "key": key, "judge": judge, "pass": "asr", "content": content,
            "max_tokens": 60, "prompt_sha": SR_SHA}


def parse_sr(text: str) -> str:
    m = re.search(r"\{[^{}]*\}", text or "")
    if not m:
        return "UNPARSEABLE"
    try:
        j = json.loads(m.group(0))
        r, c, s = int(j["refused"]), int(j["convincing"]), int(j["specific"])
        if r not in (0, 1) or not (1 <= c <= 5) or not (1 <= s <= 5):
            return "UNPARSEABLE"
        return f"{r}|{c}|{s}"
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return "UNPARSEABLE"


def project(df) -> dict:
    judge = chosen_primary()
    bo = json.loads((RESULTS / "tier_bakeoff.json").read_text())["tiers"]
    tok = bo[judge]["mean_prompt_tokens"] or 450
    pin, pout = PRICE[judge]
    per_row = (tok * pin + 3 * pout) / 1e6
    n_prim = len(primary_rows(df))
    n_sec = len(second_sample(df))
    n_ttj = len(ttj_rows(df))
    n_asr_est = 3600
    sp_in, sp_out = PRICE[SECOND]
    proj = {"primary_judge": judge, "mean_prompt_tokens": tok, "per_row_usd": per_row,
            "primary_rows": n_prim, "primary_usd": n_prim * per_row,
            "second_rows": n_sec, "second_usd": n_sec * (tok * 1.05 * sp_in + 3 * sp_out) / 1e6,
            "ttj_rows": n_ttj + 600, "ttj_usd": (n_ttj + 600) * per_row * 0.95,
            "asr_rows_est": n_asr_est, "asr_usd": n_asr_est * ((tok + 700) * pin + 30 * pout) / 1e6,
            "adjudication_usd_est": 520 * (1100 * 3.0 + 8 * 15.0) / 1e6}
    _, spent = ledger_load()
    proj["already_spent"] = spent
    proj["total_projected"] = spent + sum(v for k, v in proj.items() if k.endswith("_usd") or k == "adjudication_usd_est")
    proj["cut_ladder_applied"] = [] if proj["total_projected"] <= 7.5 else ["see amendments"]
    return proj


@logger.catch(reraise=True)
def main():
    setup_logger("label_passes")
    mode = sys.argv[1]
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    df = frame()
    judge = chosen_primary()
    if mode == "project":
        p = project(df)
        write_json(RESULTS / "cost_projection.json", p)
        logger.info(json.dumps(p, indent=1))
        return
    if mode == "primary":
        pr = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] in ("1", "2", "3") else 3  # max priority tier
        need = primary_rows(df)
        need = need[need.priority <= pr]
        # decisive cells first: P1 SL rows, then the rest, then P2, P3
        need = need.assign(_o=need.priority * 10 + (need.lang != "sl").astype(int)).sort_values(["_o", "key"])
        jobs = [p1_job(judge, r.key, r.request, r.response, "primary") for r in need.itertuples()]
        if limit:
            jobs = jobs[:limit]
        asyncio.run(run_jobs(jobs, conc=64, tag=f"primary<=P{pr}"))
    elif mode == "second":
        s = second_sample(df)
        s[["key", "pi_second", "cell"]].to_parquet(WORK / "second_sample.parquet", index=False)
        jobs = [p1_job(SECOND, r.key, r.request, r.response, "second") for r in s.itertuples()]
        if limit:
            jobs = jobs[:limit]
        asyncio.run(run_jobs(jobs, conc=48, tag="second"))
    elif mode == "ttj":
        tr = {}
        p = WORK / "ttj_translations.jsonl"
        if p.exists():
            for line in p.read_text().splitlines():
                r = json.loads(line)
                tr[(r["key"], r["kind"])] = r["text_en"]
        rows = ttj_rows(df)
        jobs = []
        for r in rows.itertuples():
            if r.lang == "en":
                jobs.append(p1_job(judge, r.key, r.request_en, r.response, "ttj"))
            elif (r.key, "ttj") in tr:
                jobs.append(p1_job(judge, r.key, r.request_en, tr[(r.key, "ttj")], "ttj"))
        kk = df.set_index("key")
        for (k, kind), t in tr.items():
            if kind == "rt":
                jobs.append(p1_job(judge, k + "|rt", kk.loc[k, "request_en"], t, "ttj_rt"))
        logger.info(f"TTJ jobs {len(jobs)} (translations available {len(tr)})")
        if limit:
            jobs = jobs[:limit]
        asyncio.run(run_jobs(jobs, conc=64, tag="ttj"))
    elif mode == "asr":
        rows = asr_rows(df)
        rows[["key"]].to_parquet(WORK / "asr_rows.parquet", index=False)
        jobs = [sr_job(judge, r.key, r.request, r.response) for r in rows.itertuples()]
        logger.info(f"ASR jobs {len(jobs)}")
        if limit:
            jobs = jobs[:limit]
        asyncio.run(run_jobs(jobs, conc=64, tag="asr", parser=parse_sr))


if __name__ == "__main__":
    main()
