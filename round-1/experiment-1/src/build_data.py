#!/usr/bin/env python3
"""STEP 1: build item-matched EN/SL RefusEU pairs (train+test only; the evaluation config is never touched),
assign CONSTRUCT/SCORE roles by sha1(pair_id) % 4, select SCORE-400, write shingles + split manifest."""
from __future__ import annotations

import glob
import json
from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path

from loguru import logger

from common import (DATA, DATASET_ART_GLOB, HIGH_EN, LOW_EN, REFUSEU_REPO, REFUSEU_REV, set_ram_limit,
                    setup_logging, sha1_int, sha256_file, write_jsonl)

SPLITS = ("train", "test")


def load_lang(lang: str) -> dict[tuple[str, int, str], dict]:
    from datasets import load_dataset
    rows: dict[tuple[str, int, str], dict] = {}
    for split in SPLITS:
        ds = load_dataset(REFUSEU_REPO, f"lang_{lang}", split=split, revision=REFUSEU_REV)
        logger.info(f"lang_{lang}/{split}: {len(ds)} rows, columns={ds.column_names}")
        for r in ds:
            msgs = r["chosen"]
            assert msgs[0]["role"] == "user", f"first chosen turn not user: {msgs[0]['role']}"
            key = (split, int(r["row_id"]), r["category"])  # row_id alone is NOT unique (268 dups in train)
            assert key not in rows, f"duplicate {key} in lang_{lang}"
            rows[key] = {"prompt": msgs[0]["content"].strip(), "id": r["id"], "category": r["category"],
                         "lang_field": r["lang"]}
    return rows


def shingles(text: str, n: int = 8) -> list[str]:
    w = text.lower().split()
    if len(w) < n:
        return [sha256(" ".join(w).encode()).hexdigest()[:16]] if w else []
    return sorted({sha256(" ".join(w[i:i + n]).encode()).hexdigest()[:16] for i in range(len(w) - n + 1)})


def select_score400(score_pairs: list[dict]) -> set[str]:
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for p in score_pairs:
        by_cat[p["category"]].append(p)
    for c in by_cat:
        by_cat[c].sort(key=lambda p: p["sha1hex"])
    chosen: list[str] = []
    for c in LOW_EN:
        chosen += [p["pair_id"] for p in by_cat.get(c, [])[:45]]
    rest = 400 - len(chosen)
    others = sorted([c for c in by_cat if c not in LOW_EN], key=lambda c: int(c[1:]))
    ptr = {c: 0 for c in others}
    while rest > 0 and any(ptr[c] < len(by_cat[c]) for c in others):
        for c in others:  # round-robin by lowest sha1
            if rest == 0:
                break
            if ptr[c] < len(by_cat[c]):
                chosen.append(by_cat[c][ptr[c]]["pair_id"])
                ptr[c] += 1
                rest -= 1
    return set(chosen)


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("build_data")
    set_ram_limit(20)
    en, sl = load_lang("en"), load_lang("sl")
    pairs, mismatches = [], []
    for key in sorted(set(en) | set(sl)):
        if key not in en or key not in sl:
            mismatches.append({"key": list(key), "reason": "missing_in_one_lang"})
            continue
        e, s = en[key], sl[key]
        if e["category"] != s["category"]:
            mismatches.append({"key": list(key), "reason": f"category {e['category']} vs {s['category']}"})
            continue
        if not e["prompt"] or not s["prompt"]:
            mismatches.append({"key": list(key), "reason": "empty_prompt"})
            continue
        split, row_id, cat = key
        pid = f"{split}:{row_id}:{cat}"
        h = sha1_int(pid) % 4
        pairs.append({"pair_id": pid, "split": split, "row_id": row_id, "category": e["category"],
                      "id_en": e["id"], "id_sl": s["id"], "prompt_en": e["prompt"], "prompt_sl": s["prompt"],
                      "h": h, "role": "CONSTRUCT" if h == 0 else "SCORE",
                      "sha1hex": __import__("hashlib").sha1(pid.encode()).hexdigest()})
    assert len({p["pair_id"] for p in pairs}) == len(pairs)
    logger.info(f"pairs={len(pairs)} dropped={len(mismatches)}")

    # overlap drop list from the DATASET artifact, if any
    drop_files = glob.glob(DATASET_ART_GLOB, recursive=True)
    dropped_overlap: list[str] = []
    drop_status = "drop_list_unavailable"
    for f in drop_files:
        try:
            d = json.loads(Path(f).read_text())
            ids = d.get("drop_pair_ids") or d.get("screen_drop_pair_ids") or []
            dropped_overlap += [str(i) for i in ids]
            drop_status = f"applied:{f}"
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning(f"could not parse overlap file {f}: {e}")
    if dropped_overlap:
        pairs = [p for p in pairs if p["pair_id"] not in set(dropped_overlap)]
    logger.info(f"overlap drop status={drop_status} n_dropped={len(dropped_overlap)}")

    cat_hist = Counter(p["category"] for p in pairs)
    present = sorted(cat_hist, key=lambda c: int(c[1:]))
    missing = [f"S{i}" for i in range(1, 15) if f"S{i}" not in cat_hist]
    logger.info(f"category histogram {dict(sorted(cat_hist.items(), key=lambda x: int(x[0][1:])))}; missing={missing}")

    score = [p for p in pairs if p["role"] == "SCORE"]
    s400 = select_score400(score)
    for p in pairs:
        p["in_score400"] = p["pair_id"] in s400
    # determinism check
    assert all(sha1_int(p["pair_id"]) % 4 == p["h"] for p in pairs)

    write_jsonl(DATA / "pairs.jsonl", pairs)
    write_jsonl(DATA / "screen_shingles.jsonl",
                ({"pair_id": p["pair_id"], "lang": lg, "shingles8": shingles(p[f"prompt_{lg}"])}
                 for p in pairs for lg in ("en", "sl")))
    manifest = {
        "source": {"repo": REFUSEU_REPO, "revision": REFUSEU_REV, "configs": ["lang_en", "lang_sl"],
                   "splits": list(SPLITS), "evaluation_config_accessed": False},
        "n_pairs": len(pairs), "n_dropped_mismatch": len(mismatches), "mismatches": mismatches[:50],
        "overlap_drop": {"status": drop_status, "n": len(dropped_overlap)},
        "categories_present": present, "categories_missing": missing,
        "low_en_present": [c for c in LOW_EN if c in cat_hist], "high_en_present": [c for c in HIGH_EN if c in cat_hist],
        "counts": {role: {c: sum(1 for p in pairs if p["role"] == role and p["category"] == c) for c in present}
                   for role in ("CONSTRUCT", "SCORE")},
        "score400_counts": {c: sum(1 for p in pairs if p["in_score400"] and p["category"] == c) for c in present},
        "n_score": len(score), "n_construct": len(pairs) - len(score), "n_score400": len(s400),
        "split_rule": "h = int(sha1(pair_id).hexdigest(),16) % 4; h==0 -> CONSTRUCT else SCORE; pair_id='{split}:{row_id}:{category}' (row_id alone is not unique within a split)",
        "pairing_caveat": "EN and SL rows sharing (split,row_id,category) are topically related, independently generated prompts, NOT translations; the DiD compares the two models on IDENTICAL prompt sets, so prompt differences between languages cancel, but within-model SL-vs-EN contrasts are not item-matched",
        "pairs_sha256": sha256_file(DATA / "pairs.jsonl"),
    }
    (DATA / "split_manifest.json").write_text(json.dumps(manifest, indent=2))
    logger.info(json.dumps({k: manifest[k] for k in ("n_pairs", "n_score", "n_construct", "n_score400",
                                                       "score400_counts")}))


if __name__ == "__main__":
    main()
