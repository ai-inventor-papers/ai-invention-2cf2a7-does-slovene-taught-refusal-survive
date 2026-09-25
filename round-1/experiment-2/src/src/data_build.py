#!/usr/bin/env python3
"""P1 data build (CPU): RefusEU EN/SL screen pairs (train+test only; evaluation split NEVER read),
sha1 CONSTRUCT/SCORE split, SCORE-400, alpaca harmless sample (pre-MT), item manifest, dose table copy."""
from __future__ import annotations

import hashlib
import json
import random
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
from huggingface_hub import hf_hub_download
from loguru import logger

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SEED = 20260923
LOW_EN = ["S5", "S7", "S8", "S13"]
STAGE0B = Path("/ai-inventor/aii_data/runs/run_FVi3e3O9CH5I/iter_3/gen_hypo/claude_agent/stage0b")
REFUSEU_REV = "5523ce30b9b6af59e95ade9c610b8b974412a6bb"

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add(ROOT / "logs/data_build.log", rotation="30 MB", level="DEBUG")


def sha1(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def first_user(conv) -> str:
    return [t["content"] for t in conv if t["role"] == "user"][0]


def load_refuseu() -> pd.DataFrame:
    rows = []
    for split in ["train", "test"]:
        d = {}
        for lang in ["en", "sl"]:
            # ONLY lang_*/{train,test}; the evaluation/ config is the RESERVED confirmation set.
            p = hf_hub_download("NASK-PIB/RefusEU", f"lang_{lang}/{split}-00000-of-00001.parquet", repo_type="dataset",
                                revision=REFUSEU_REV)
            d[lang] = pd.read_parquet(p)
            for c in ["id", "row_id", "category", "chosen"]:
                assert c in d[lang].columns, (lang, split, c)
        e, s = d["en"].reset_index(drop=True), d["sl"].reset_index(drop=True)
        assert len(e) == len(s)
        e_num = e.id.str.split("_").str[0]
        s_num = s.id.str.split("_").str[0]
        # The shared-id column carries a language suffix ('0_en-gb' vs '0_sl'); pair on the numeric stem.
        stem_ok = (e_num.values == s_num.values)
        cat_ok = (e.category.values == s.category.values)
        rid_ok = (e.row_id.values == s.row_id.values)
        logger.info(f"{split}: n={len(e)} id-stem match={stem_ok.mean():.4f} category match={cat_ok.mean():.4f} "
                    f"row_id match={rid_ok.mean():.4f} id-stem unique={e_num.is_unique}")
        # id stems repeat across categories (per-category generation), so the unique pair key is (id stem, category).
        key = e_num + ":" + e.category
        assert key.is_unique, "(id stem, category) not unique"
        for i in range(len(e)):
            if not (stem_ok[i] and cat_ok[i]):
                logger.warning(f"drop unpaired {split} row {i}")
                continue
            en, sl = first_user(e.chosen[i]), first_user(s.chosen[i])
            rows.append({"pair_id": f"{split}:{e.category[i]}:{e_num[i]}", "id_en": e.id[i], "id_sl": s.id[i], "row_id": int(e.row_id[i]),
                         "split": split, "category": e.category[i], "en": en, "sl": sl})
    df = pd.DataFrame(rows)
    ratio = df.sl.str.len() / df.en.str.len()
    ok = ratio.between(0.4, 2.5)
    logger.info(f"length ratio SL/EN within [0.4,2.5]: {ok.mean():.4f} (outliers {int((~ok).sum())})")
    for _, r in df[~ok].iterrows():
        logger.debug(f"ratio outlier {r.pair_id} {len(r.en)} {len(r.sl)}")
    return df


def assign_roles(df: pd.DataFrame) -> pd.DataFrame:
    df["sha1"] = df.pair_id.map(sha1)
    df["h"] = df.sha1.map(lambda x: int(x, 16) % 4)
    df["role"] = df.h.map(lambda h: "CONSTRUCT" if h == 0 else "SCORE")
    # SCORE-400: stratified by category, lowest sha1 within category.
    score = df[df.role == "SCORE"].sort_values("sha1")
    by_cat = {c: g.pair_id.tolist() for c, g in score.groupby("category")}
    chosen: list[str] = []
    for c in LOW_EN:
        chosen += by_cat.get(c, [])[:45]
    n_low = len(chosen)
    others = sorted([c for c in by_cat if c not in LOW_EN], key=lambda c: int(c[1:]))
    remaining = 400 - n_low
    quota = {c: 0 for c in others}
    # even split, then redistribute surplus of short categories round-robin to the largest ones
    base = remaining // len(others)
    for c in others:
        quota[c] = min(base, len(by_cat[c]))
    left = remaining - sum(quota.values())
    order = sorted(others, key=lambda c: -len(by_cat[c]))
    while left > 0:
        progressed = False
        for c in order:
            if left == 0:
                break
            if quota[c] < len(by_cat[c]):
                quota[c] += 1
                left -= 1
                progressed = True
        assert progressed, "not enough SCORE items"
    for c in others:
        chosen += by_cat[c][:quota[c]]
    assert len(chosen) == 400, len(chosen)
    s400 = set(chosen)
    df["in_score400"] = df.pair_id.isin(s400)
    logger.info(f"SCORE-400 low-EN n={n_low}; quotas {quota}")
    return df


def build_alpaca() -> list[dict]:
    p = hf_hub_download("tatsu-lab/alpaca", "data/train-00000-of-00001-a09b74b3ef9c3b56.parquet", repo_type="dataset")
    a = pd.read_parquet(p)
    a = a[a.input.str.strip() == ""]
    excl = set()
    for sp in ["train", "test"]:
        try:
            hp = hf_hub_download("mlabonne/harmless_alpaca", f"data/{sp}-00000-of-00001.parquet", repo_type="dataset")
            h = pd.read_parquet(hp)
            # D7: mlabonne/harmless_alpaca is itself a re-packaging of ~all no-input alpaca instructions, so a full
            # exclusion leaves 0 items. Exclude exactly the slices Heretic 3521f864 consumes (train[:400] for
            # directions, test[:100] for KL) -- the leakage the spec's exclusion was meant to prevent.
            h = h.iloc[:400] if sp == "train" else h.iloc[:100]
            excl |= set(h["text"].astype(str).map(norm))
        except Exception as e:  # noqa: BLE001 - file name variants; logged
            logger.warning(f"harmless_alpaca {sp}: {e!r}")
    logger.info(f"mlabonne/harmless_alpaca exclusion set: {len(excl)}")
    lex = json.loads((ROOT / "config/lexicon.json").read_text())
    markers = lex["en"]
    keep = []
    for ins in a.instruction.tolist():
        n = norm(ins)
        if n in excl:
            continue
        if any(m in n.replace("’", "'") for m in markers):
            continue
        if not (3 <= len(ins.split()) <= 60):
            continue
        keep.append(ins)
    keep = sorted(set(keep))  # deterministic order before seeded sampling
    logger.info(f"alpaca candidates after filters: {len(keep)}")
    rnd = random.Random(SEED)
    sample = rnd.sample(keep, 440)
    out = [{"hid": "a" + sha1(ins)[:10], "en": ins, "sha1": sha1(ins)} for ins in sample]
    return sorted(out, key=lambda r: r["sha1"])


def main() -> None:
    DATA.mkdir(exist_ok=True)
    df = assign_roles(load_refuseu())
    cnt = df.groupby(["category", "role"]).size().unstack(fill_value=0)
    logger.info(f"per-category counts per role:\n{cnt}")
    logger.info(f"roles: {Counter(df.role)}; SCORE-400 {int(df.in_score400.sum())}")
    with (DATA / "refuseu_pairs.jsonl").open("w") as f:
        for r in df.to_dict("records"):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    man = []
    for r in df.to_dict("records"):
        for lang in ["en", "sl"]:
            man.append({"pair_id": r["pair_id"], "id": r[f"id_{lang}"], "row_id": r["row_id"], "lang": lang,
                        "split": r["split"], "role": r["role"], "in_score400": bool(r["in_score400"]),
                        "sha1_norm_prompt": sha1(norm(r[lang]))})
    (DATA / "screen_item_manifest.json").write_text(json.dumps({
        "note": "RefusEU items read by this screen (lang_* train+test only). The confirmation step must drop any "
                "RefusEU evaluation item whose normalised-prompt sha1 or >50% 8-gram overlap matches one of these "
                "(D1: the overlap list could not be rebuilt without reading the reserved evaluation parquet).",
        "normalisation": "lowercase, collapse whitespace, strip", "items": man}, ensure_ascii=False))
    shutil.copy(STAGE0B / "stage0b_summary.json", DATA / "dose_table_stage0b.json")
    alp = build_alpaca()
    with (DATA / "alpaca_sample_pre_mt.jsonl").open("w") as f:
        for r in alp:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    logger.info(f"wrote {len(df)} pairs, {len(alp)} alpaca items")


if __name__ == "__main__":
    main()
