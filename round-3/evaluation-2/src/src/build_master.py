#!/usr/bin/env python3
"""STEP 0: input check, master table (request text, resp64/resp128 under the models' own Gemma-3 tokenizer, all archived
labels), and the FROZEN sampling frames (second-family 25% sample, blind adjudication sample, calibration set).
Everything is decided by sha1(row_key + seed) BEFORE any new label exists.

Writes: work/inputs_check.json, work/master.parquet, work/counts.json, work/frames.json,
        adjudication/blind_items.jsonl (uid, request, response, lang ONLY), adjudication/_key.json (uid -> row_key; the
        agent does not open it before committing its labels).
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

from common import (ADJ, DS1, E5, E6, E7, E8, EV1, SEED, WORK, jdump, read_jsonl, row_key, setup_logger, sha1_unit,
                    sha256_file, TOKENIZER_REPO)

logger = setup_logger("build_master")


def inputs_check() -> dict:
    need = {
        "E8/items_final (FATAL)": E8 / "results/items_final.jsonl",
        "E8/judge_labels": E8 / "results/judge_labels.jsonl",
        "E8/judge_ledger": E8 / "results/judge_ledger.jsonl",
        "E8/judge_local/llama31_8b": E8 / "results/judge_local/llama31_8b.jsonl",
        "E8/judge_local/qwen3_8b": E8 / "results/judge_local/qwen3_8b.jsonl",
        "E8/judge_local/selection": E8 / "results/judge_local/selection.json",
        "E8/probe_P200": E8 / "data/probe_P200.jsonl",
        "E8/harmless100": E8 / "data/harmless100.jsonl",
        "E8/src/common.py": E8 / "src/common.py",
        "E8/src/analysis.py": E8 / "src/analysis.py",
        "E8/analysis.json": E8 / "results/analysis.json",
        "E8/protocol.json": E8 / "protocol.json",
        "E8/protocol_amendments.json": E8 / "results/protocol_amendments.json",
        "E5/items_final.parquet": E5 / "results/items_final.parquet",
        "E5/analysis_final.json": E5 / "results/analysis_final.json",
        "E7/gens/gemma": E7 / "gens/gemma.jsonl",
        "E7/gens/gams": E7 / "gens/gams.jsonl",
        "E7/labels/refusal_gemini": E7 / "labels/refusal_gemini.jsonl",
        "E7/labels/refusal_local": E7 / "labels/refusal_local.jsonl",
        "E7/analysis.json": E7 / "results/analysis.json",
        "EV1/harmonised_P1": EV1 / "labels/harmonised_P1.jsonl.gz",
        "EV1/author_gold_prefill5": EV1 / "labels/author_gold_prefill5.json",
        "DS1/split_manifest": DS1 / "split_manifest.json",
    }
    out = {k: {"path": str(v), "exists": v.exists(), "bytes": v.stat().st_size if v.exists() else None} for k, v in need.items()}
    # exp6 adjudication source of the '19/19 gemini errors toward REFUSE' figure
    hits = []
    if E6.exists():
        for p in E6.rglob("*"):
            if p.is_file() and p.suffix in (".json", ".jsonl", ".md") and "adjud" in p.name.lower():
                hits.append(str(p))
    out["exp6_adjudication_files"] = hits
    out["E8_items_final_sha256"] = sha256_file(E8 / "results/items_final.jsonl")
    if not out["E8/items_final (FATAL)"]["exists"]:
        raise SystemExit("FATAL: E8 items_final.jsonl missing")
    return out


def load_requests() -> dict:
    req = {}
    for f in ("probe_P200.jsonl", "harmless100.jsonl"):
        for it in read_jsonl(E8 / "data" / f):
            for arm in ("en_orig", "sl_mt", "en_bt"):
                if arm in it:
                    req[(it["item_id"], arm)] = it[arm]
    return req


def main():
    chk = inputs_check()
    jdump(chk, WORK / "inputs_check.json")
    logger.info(f"inputs: {sum(v['exists'] for k, v in chk.items() if isinstance(v, dict) and 'exists' in v)} present; "
                f"exp6 adjudication files: {len(chk['exp6_adjudication_files'])}")
    d = pd.read_json(E8 / "results/items_final.jsonl", lines=True)
    d["row_key"] = [row_key(r) for r in d[["model", "arm", "curve", "step", "item_id"]].to_dict("records")]
    assert d.row_key.is_unique
    req = load_requests()
    d["request"] = [req[(i, a)] for i, a in zip(d.item_id, d.arm)]
    # ---- tokenizer: GaMS3 and Gemma-3 share the Gemma-3 tokenizer; verify on 20 strings when both are available ----
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(TOKENIZER_REPO[0], revision=TOKENIZER_REPO[1])
    tok_check = {"tokenizer": f"{TOKENIZER_REPO[0]}@{TOKENIZER_REPO[1][:8]}"}
    try:
        tg = AutoTokenizer.from_pretrained("google/gemma-3-12b-it", revision="96b6f1eccf38110c56df3a15bffe176da04bfd80")
        sample = d.response.sample(20, random_state=SEED).tolist()
        same = [tok(s, add_special_tokens=False).input_ids == tg(s, add_special_tokens=False).input_ids for s in sample]
        tok_check.update({"gemma_vs_gams_identical_on_20": int(sum(same)), "n": 20})
    except (OSError, ValueError) as e:
        tok_check["gemma_tokenizer_unavailable"] = str(e)[:200]
    logger.info(f"tokenizer check {tok_check}")
    ids = tok(d.response.fillna("").tolist(), add_special_tokens=False)["input_ids"]
    d["n_tok_resp"] = [len(x) for x in ids]
    d["resp64"] = [tok.decode(x[:64], skip_special_tokens=True) for x in ids]
    d["resp128"] = [tok.decode(x[:128], skip_special_tokens=True) for x in ids]
    d["trunc_differs"] = (d.n_tok_resp > 64).astype(int)
    # ---- archived labels ----
    llama = {r["row_key"]: r["label"] for r in read_jsonl(E8 / "results/judge_local/llama31_8b.jsonl")}
    qw8 = {r["row_key"]: r["label"] for r in read_jsonl(E8 / "results/judge_local/qwen3_8b.jsonl")}
    calib = {r["row_key"] for r in read_jsonl(E8 / "results/judge_local/llama31_8b.jsonl") if r.get("set") == "calib"}
    d["label3_llama8b"] = d.row_key.map(llama)
    d["label3_qwen8b"] = d.row_key.map(qw8)
    d["in_calib"] = d.row_key.isin(calib).astype(int)
    jl = read_jsonl(E8 / "results/judge_labels.jsonl")
    t64 = {r["row_key"].replace("|trunc64", ""): r["label"] for r in jl if r["kind"] == "trunc64"}
    sec = {r["row_key"]: r["label"] for r in jl if r["kind"] == "second"}
    d["label3_gemini_t64"] = d.row_key.map(t64)
    d["label3_gpt41_arch"] = d.row_key.map(sec)
    d["label3_gemini"] = d["label3_gemini"].where(d["label3_gemini"].isin(["REFUSE", "PARTIAL", "COMPLY"]))
    # ---- step-level lexicon EN-BT rate (dose bin available for both models before any judging) ----
    en = d[d.arm == "en_bt"].groupby(["model", "curve", "step"]).R_lex.mean().rename("step_lex_en").reset_index()
    d = d.merge(en, on=["model", "curve", "step"], how="left")
    d["dose_bin"] = pd.cut(d.step_lex_en, [-0.01, 0.3, 0.7, 1.01], labels=["lo", "mid", "hi"]).astype(str)
    d = d.drop(columns=["response"]).assign(response=d.response.values) if False else d
    d.to_parquet(WORK / "master.parquet", index=False)
    logger.info(f"master: {d.shape}")
    # ---- counts ----
    cnt = d.groupby(["model", "curve", "arm"]).agg(n=("row_key", "size"), n_steps=("step", "nunique"),
                                                   gemini=("label3_gemini", lambda s: int(s.notna().sum())),
                                                   llama8b=("label3_llama8b", lambda s: int(s.notna().sum())),
                                                   gemini_t64=("label3_gemini_t64", lambda s: int(s.notna().sum())),
                                                   trunc_differs=("trunc_differs", "sum"),
                                                   max_new=("max_new", "max")).reset_index()
    gaps = d[(d.model == "gemma_it") & d.curve.isin(["trial", "lambda", "orig", "harmless_lambda"]) &
             d.label3_gemini.isna()].groupby(["curve", "arm", "step"]).size()
    jdump({"table": cnt.to_dict("records"), "gemma_gemini_gaps": {"|".join(map(str, k)): int(v) for k, v in gaps.items()},
           "B_rows_per_model": d[d.curve == "trial"].groupby("model").size().to_dict(), "tokenizer_check": tok_check},
          WORK / "counts.json")
    # ---- frames ----
    frames = {}
    # (1) 25% stratified second-family sample of trial + lambda rows (model x arm x curve x lexicon EN-dose bin)
    # drawn at the item x step level (both arms kept) so every sampled EN-BT row has its SL-MT pair for the G3 curve
    pool = d[d.curve.isin(["trial", "lambda"]) & d.arm.isin(["en_bt", "sl_mt"])].copy()
    pool["pair_key"] = pool.model + "|" + pool.curve + "|" + pool.step.astype(str) + "|" + pool.item_id
    chosen = set()
    for _, g in pool.groupby(["model", "curve", "dose_bin"]):
        keys = sorted(set(g.pair_key), key=lambda k: sha1_unit(f"{k}|{SEED}|sample25"))
        chosen |= set(keys[: int(np.ceil(0.25 * len(keys)))])
    samp = sorted(pool.row_key[pool.pair_key.isin(chosen)])
    frames["sample25"] = samp
    # (2) calibration set (exp8's 1,000 Gemma rows)
    frames["calib"] = sorted(calib)
    # (3) blind adjudication: 60 per model x language, edited rows (B trials + A1 lambda), lexicon EN-dose in [0.2, 0.8]
    ed = d[d.curve.isin(["trial", "lambda"]) & d.arm.isin(["en_bt", "sl_mt"]) & d.step_lex_en.between(0.2, 0.8) &
           (d.degenerate == 0)].copy()

    def rb(x):
        return None if x not in ("REFUSE", "PARTIAL", "COMPLY") else int(x == "REFUSE")
    labs = ed[["label3_gemini", "label3_llama8b"]].map(rb)
    labs["lex"] = ed.R_lex
    disagree = labs.apply(lambda r: len({v for v in r.values if v is not None and not pd.isna(v)}) > 1, axis=1)
    ed["disagree"] = disagree.astype(int)
    adj, incl = [], {}
    N_PER, N_RAND = 60, 30
    for (m, arm), g in ed.groupby(["model", "arm"]):
        keys = sorted(g.row_key, key=lambda k: sha1_unit(f"{k}|{SEED}|adj_rand"))
        rnd = keys[:N_RAND]
        dis_pool = sorted(set(g.row_key[g.disagree == 1]) - set(rnd), key=lambda k: sha1_unit(f"{k}|{SEED}|adj_dis"))
        n_dis = N_PER - N_RAND
        dis = dis_pool[:n_dis]
        p_r = N_RAND / len(g)
        n_D = int((g.disagree == 1).sum())
        p_d = min(1.0, n_dis / max(1, len(dis_pool)))
        dset = set(g.row_key[g.disagree == 1])
        for k in rnd + dis:
            pi = p_r + (p_d - p_r * p_d if k in dset else 0.0)
            incl[k] = {"pi": pi, "w": 1.0 / pi, "draw": "random" if k in rnd else "disagreement", "cell": f"{m}|{arm}",
                       "N_cell": int(len(g)), "N_disagree": n_D}
        adj += rnd + dis
    frames["adjudication"] = adj
    frames["adjudication_inclusion"] = incl
    jdump(frames, WORK / "frames.json")
    # blind file: uid, request, response (native length, as the primary judge sees it), lang -- nothing else, shuffled
    sub = d.set_index("row_key").loc[adj]
    uids = {k: f"u{int(sha1_unit(k + '|uid') * 1e9):09d}" for k in adj}
    blind = [{"uid": uids[k], "request": sub.at[k, "request"], "response": sub.at[k, "response"],
              "lang": "sl" if sub.at[k, "arm"] == "sl_mt" else "en"} for k in adj]
    blind.sort(key=lambda r: r["uid"])
    (ADJ / "blind_items.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in blind))
    jdump({uids[k]: k for k in adj}, ADJ / "_key.json")
    # exp7 HARD-DEV rows (Gemma + GaMS, en_orig / en_bt / sl_mt, k0) for a readout-consistent L1 pass in STEP 6 (S2)
    items7 = {r["item_id"]: r for r in read_jsonl(E7 / "data/items.jsonl") if r["set"] == "H"}
    bt7 = {r["item_id"]: r["en_bt"] for r in read_jsonl(E7 / "data/h_en_bt.jsonl")}
    e7 = []
    for sysname, model in (("gemma", "gemma_it"), ("gams", "gams3_it")):
        for r in read_jsonl(E7 / "gens" / f"{sysname}.jsonl"):
            if r["set"] != "H" or r["condition"] != "k0":
                continue
            it = items7[r["item_id"]]
            reqtxt = bt7.get(r["item_id"]) if r["lang_arm"] == "en_bt" else it["arms"].get(r["lang_arm"])
            if reqtxt is None:
                continue
            e7.append({"row_key": f"e7|{r['key']}", "e7_key": r["key"], "model": model, "arm": r["lang_arm"],
                       "item_id": r["item_id"], "is_harmful": bool(it["is_harmful"]), "request": reqtxt,
                       "response": r["response"], "mt_fragile": bool(it.get("mt_fragile"))})
    pd.DataFrame(e7).to_parquet(WORK / "e7_hard.parquet", index=False)
    logger.info(f"exp7 HARD-DEV rows for L1: {len(e7)}")
    logger.info(f"frames: sample25={len(samp)} calib={len(calib)} adjudication={len(adj)}; "
                f"draws {Counter(v['draw'] for v in incl.values())}")


if __name__ == "__main__":
    main()
