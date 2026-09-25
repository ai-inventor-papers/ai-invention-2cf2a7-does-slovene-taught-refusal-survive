#!/usr/bin/env python3
"""Merge generations + judge labels into one per-row table results/rows_final.parquet (and .jsonl.gz):
one row per FINAL generation (within-study models, public checkpoints) with R/RP under the primary (Qwen3-14B)
and second-family (Mistral-24B, sampled) judges, lexicon (diagnostic), degeneracy and language ID."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from loguru import logger

from common import DATA, E5, FINAL_DIR, LABELS, RESULTS, degenerate, lex_hit, read_jsonl, setup_logging

LANGMAP = {"ENGLISH": "en", "SLOVENE": "sl", "HUNGARIAN": "hu", "CROATIAN": "hr"}


def langid(texts: list[str]) -> list[str]:
    from lingua import Language, LanguageDetectorBuilder
    det = LanguageDetectorBuilder.from_languages(Language.ENGLISH, Language.SLOVENE, Language.HUNGARIAN,
                                                 Language.CROATIAN).build()
    res = det.detect_languages_in_parallel_of([t or "" for t in texts])
    return [LANGMAP.get(r.name, "other") if r else "none" for r in res]


def load_labels(judge: str, extra: pd.DataFrame | None = None) -> pd.DataFrame:
    rows = read_jsonl(LABELS / f"labels_{judge}_final.jsonl")
    d = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["key", "label", "p_refuse", "p_partial"])
    if extra is not None and len(extra):
        d = pd.concat([d, extra], ignore_index=True)
    if d.empty:
        return pd.DataFrame(columns=["key"])
    d = d.drop_duplicates("key", keep="last")
    tag = {"qwen3_14b": "q", "mistral24b": "m"}[judge]
    d[f"label_{tag}"] = d["label"]
    d[f"pR_{tag}"] = d["p_refuse"]
    d[f"pRP_{tag}"] = d["p_refuse"] + d["p_partial"]
    return d[["key", f"label_{tag}", f"pR_{tag}", f"pRP_{tag}"]]


def exp5_originals() -> tuple[pd.DataFrame, pd.DataFrame]:
    """exp5 FINAL original-model rows (NF4, greedy, 160 tokens) reused as condition 'orig' (lambda=0) for
    RefusEU-x and HARD EN_BT/SL_MT(/EN_orig); response cut to the first 128 Gemma tokens; primary label = exp5's own
    Qwen3-14B label (same judge/prompt/NF4; 160-token window; see results/labels/retest_report_qwen3_14b.json)."""
    from judge_local import trunc128
    lab = {r["key"]: r["qwen_label"] for r in read_jsonl(E5 / "outputs/final/labels_local_qwen3.jsonl")}
    rows, labs = [], []
    for m in ("gemma_it", "gams3_it"):
        for r in read_jsonl(E5 / "outputs/final" / f"gen_{m}.jsonl"):
            if r["set"] not in ("refuseu_x", "hard") or r["arm"] not in ("EN_BT", "SL_MT", "EN_orig"):
                continue
            iid = r["pair_id"] if r["set"] == "refuseu_x" else r["item_id"]
            gid = f"{r['set']}|{r['arm']}|{iid}"
            key = f"{gid}|{m}|orig|0|exp5"
            resp = trunc128(r["response"])
            rows.append({"key": key, "gid": gid, "set": r["set"], "split": "FINAL", "item_id": iid, "pair_id": iid,
                         "arm": r["arm"], "prompt_lang": r["prompt_lang"], "model": m, "condition": "orig",
                         "lambda": 0.0, "edit_source": "none", "prompt_text": r["prompt_text"], "response": resp,
                         "n_new_tokens": min(128, r["n_new_tokens"]), "hit_eos": r["hit_eos"] and r["n_new_tokens"] <= 128,
                         "degenerate": degenerate(resp), "lex": lex_hit(resp, r["prompt_lang"]),
                         "model_sha": r.get("model_sha"), "orig_source": "exp5"})
            if r["key"] in lab:
                labs.append({"key": key, "label": lab[r["key"]], "p_refuse": np.nan, "p_partial": np.nan})
    return pd.DataFrame(rows), pd.DataFrame(labs)


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("build_table")
    gens = []
    for p in sorted(FINAL_DIR.glob("gens_*.jsonl")):
        gens += read_jsonl(p)
    g = pd.DataFrame(gens).drop_duplicates("key", keep="first")
    g["orig_source"] = "this_run"
    e5rows, e5labs = exp5_originals()
    have_orig = set(zip(g[g.condition == "orig"].model, g[g.condition == "orig"].gid))
    e5rows = e5rows[[(m, x) not in have_orig for m, x in zip(e5rows.model, e5rows.gid)]]
    isharm = pd.DataFrame(read_jsonl(DATA / "items.jsonl"))[["gid", "is_harmful"]].drop_duplicates("gid")
    e5rows = e5rows.merge(isharm, on="gid", how="inner")
    logger.info(f"exp5 originals ingested: {len(e5rows)} rows")
    g = pd.concat([g, e5rows], ignore_index=True)
    logger.info(f"{len(g)} FINAL generation rows")
    items = pd.DataFrame(read_jsonl(DATA / "items.jsonl"))
    meta_cols = ["gid", "label", "group", "pure", "bt_chrf", "l3_chrf", "l3_fragile", "source", "category",
                 "mt_fragile", "kind", "facet"]
    g = g.merge(items[[c for c in meta_cols if c in items.columns]].rename(columns={"label": "hazard"}), on="gid",
                how="left")
    for j in ("qwen3_14b", "mistral24b"):
        g = g.merge(load_labels(j, e5labs if j == "qwen3_14b" else None), on="key", how="left")
    for tag in ("q", "m"):
        col = f"label_{tag}"
        if col not in g:
            g[col] = np.nan
        g[f"R_{tag}"] = np.where(g[col].isna(), np.nan, (g[col] == "REFUSE").astype(float))
        g[f"RP_{tag}"] = np.where(g[col].isna(), np.nan, g[col].isin(["REFUSE", "PARTIAL"]).astype(float))
    adj_p = RESULTS / "adjudication" / "adjudication_labels.jsonl"
    if adj_p.exists():
        key = {r["row_id"]: r["key"] for r in read_jsonl(RESULTS / "adjudication" / "adjudication_key.jsonl")}
        adj = pd.DataFrame([{"key": key[r["row_id"]], "label_a": r["label"]} for r in read_jsonl(adj_p)
                            if r["row_id"] in key])
        g = g.merge(adj, on="key", how="left")
    else:
        g["label_a"] = np.nan
    g["lang"] = g["arm"].map({"EN_BT": "en", "EN_orig": "en", "SL_MT": "sl", "L3_MT": "hu", "EN": "en", "SL": "sl"})
    g["langid"] = langid(g["response"].tolist())
    g["lang_ok"] = (g["langid"] == g["lang"]) | (g["n_new_tokens"] < 3)
    g["model_kind"] = np.where(g["model"].isin(["gemma_it", "gams3_it"]), "within", "public")
    g["lambda"] = g["lambda"].astype(float)
    g.to_parquet(RESULTS / "rows_final.parquet", index=False)
    logger.info(f"rows_final: {len(g)} rows; judged q {g['label_q'].notna().sum()} m {g['label_m'].notna().sum()}; "
                f"cells {g.groupby(['model', 'condition']).size().to_dict()}")


if __name__ == "__main__":
    main()
