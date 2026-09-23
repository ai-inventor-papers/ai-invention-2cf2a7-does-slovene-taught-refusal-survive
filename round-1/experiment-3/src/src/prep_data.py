#!/usr/bin/env python3
"""P0 CPU prep: RefusEU EN/SL pairing, CONSTRUCT/SCORE split, SCORE-400, CONSTRUCT-200, MC-HARM-40, CONSTRUCT-DIR,
alpaca harmless set (EN side; SL side is filled by translate.py), identity item files. Deterministic."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pandas as pd
from loguru import logger

from common import DATA, HIGH_EN, LOW_EN, assert_not_eval, setup_logging, sha1, write_jsonl
from identity_items import CONT, ID_CHECK, ID_DIR, PERSONAL_CTRL

STAGE0B = Path("/ai-inventor/aii_data/runs/run_FVi3e3O9CH5I/iter_3/gen_hypo/claude_agent/stage0b/stage0b_summary.json")


def user_prompt(chosen) -> str:
    return [t["content"] for t in chosen if t["role"] == "user"][0]


def dose_group(cat: str) -> str:
    return "low" if cat in LOW_EN else ("high" if cat in HIGH_EN else "mid")


def build_pairs() -> tuple[list[dict], dict]:
    pairs, log = [], {}
    for split in ["train", "test"]:
        fe = f"lang_en/{split}-00000-of-00001.parquet"
        fs = f"lang_sl/{split}-00000-of-00001.parquet"
        assert_not_eval(fe), assert_not_eval(fs)
        e = pd.read_parquet(DATA / "refuseu" / fe)
        s = pd.read_parquet(DATA / "refuseu" / fs)
        assert len(e) == len(s)
        same_rowid = float((e.row_id.values == s.row_id.values).mean())
        same_cat = float((e.category.values == s.category.values).mean())
        log[split] = {"n_rows": len(e), "row_id_unique": int(e.row_id.nunique()), "rowindex_rowid_agree": same_rowid,
                      "rowindex_category_agree": same_cat}
        # row_id is NOT unique within a split (several generated variants share a row_id), so the pairing key is
        # the row index, which aligns row_id AND category at 100% (asserted). pair_id = split:rowindex.
        assert same_rowid == 1.0 and same_cat == 1.0, "row-index pairing invalid"
        for i in range(len(e)):
            pid = f"{split}:{i}"
            pairs.append({"pair_id": pid, "row_index": i, "row_id": int(e.row_id.iloc[i]), "split": split,
                          "category": e.category.iloc[i], "dose_group": dose_group(e.category.iloc[i]),
                          "prompt_en": user_prompt(e.chosen.iloc[i]), "prompt_sl": user_prompt(s.chosen.iloc[i]),
                          "id_en": e.id.iloc[i], "id_sl": s.id.iloc[i], "sha": sha1(pid),
                          "h": int(sha1(pid), 16) % 4})
    log["pairing_method"] = "row index within split (row_id and category identical at 100%; row_id not unique)"
    log["n_pairs"] = len(pairs)
    log["note"] = ("RefusEU lang_en/lang_sl rows sharing an index are category-matched, topic-related GENERATED "
                   "VARIANTS, not translations of each other (verified by inspection). 'Item-matched' in this "
                   "artifact therefore means row/category-matched, not translation-matched.")
    return pairs, log


def score400(score: list[dict]) -> tuple[list[dict], dict]:
    by = defaultdict(list)
    for p in score:
        by[p["category"]].append(p)
    for c in by:
        by[c].sort(key=lambda p: p["sha"])
    chosen = []
    for c in sorted(LOW_EN):
        chosen += by[c][:45]
    others = sorted([c for c in by if c not in LOW_EN], key=lambda c: int(c[1:]))
    ptr = {c: 0 for c in others}
    while len(chosen) < 400:
        progressed = False
        for c in others:
            if len(chosen) >= 400:
                break
            if ptr[c] < len(by[c]):
                chosen.append(by[c][ptr[c]]); ptr[c] += 1; progressed = True
        if not progressed:
            raise RuntimeError("ran out of SCORE pairs")
    counts = defaultdict(int)
    for p in chosen:
        counts[p["category"]] += 1
    chosen.sort(key=lambda p: p["sha"])
    # random-direction fifth assignment by sha1 order (k=0..4)
    for i, p in enumerate(chosen):
        p["fifth"] = i * 5 // len(chosen)
    return chosen, dict(sorted(counts.items(), key=lambda kv: int(kv[0][1:])))


def construct200(construct: list[dict]) -> list[dict]:
    by = defaultdict(list)
    for p in construct:
        by[p["category"]].append(p)
    n = len(construct)
    quota = {c: 200 * len(v) / n for c, v in by.items()}
    alloc = {c: int(q) for c, q in quota.items()}
    rem = 200 - sum(alloc.values())
    for c in sorted(quota, key=lambda c: -(quota[c] - int(quota[c])))[:rem]:
        alloc[c] += 1
    out = []
    for c, v in by.items():
        out += sorted(v, key=lambda p: p["sha"])[:alloc[c]]
    return sorted(out, key=lambda p: p["sha"])


def alpaca_harmless() -> list[dict]:
    from huggingface_hub import snapshot_download
    d = Path(snapshot_download("tatsu-lab/alpaca", repo_type="dataset"))
    df = pd.concat([pd.read_parquet(f) for f in sorted(d.rglob("*.parquet"))])
    df = df[(df.input.str.strip() == "")]
    df = df[df.instruction.str.split().str.len().between(5, 40)]
    df = df.drop_duplicates("instruction")
    rows = sorted(df.instruction.tolist(), key=sha1)[:200]
    return [{"hid": f"alpaca:{sha1(t)[:12]}", "prompt_en": t, "prompt_sl": None,
             "set": "HARMLESS-CONSTRUCT" if i < 100 else "HARMLESS-EVAL"} for i, t in enumerate(rows)]


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("prep_data")
    pairs, plog = build_pairs()
    construct = [p for p in pairs if p["h"] == 0]
    score = [p for p in pairs if p["h"] != 0]
    s400, counts = score400(score)
    c200 = construct200(construct)
    c200_ids = {p["pair_id"] for p in c200}
    mc40 = c200[:40]
    cdir = sorted([p for p in construct if p["pair_id"] not in c200_ids], key=lambda p: p["sha"])[:300]
    assert len(s400) == 400 and not ({p["pair_id"] for p in s400} & {p["pair_id"] for p in construct})
    assert not (c200_ids & {p["pair_id"] for p in cdir})
    write_jsonl(DATA / "pairs_all.jsonl", pairs)
    write_jsonl(DATA / "score400.jsonl", s400)
    write_jsonl(DATA / "score_all.jsonl", score)
    write_jsonl(DATA / "construct200.jsonl", c200)
    write_jsonl(DATA / "mc_harm40.jsonl", mc40)
    write_jsonl(DATA / "construct_dir.jsonl", cdir)
    harmless = alpaca_harmless()
    hp = DATA / "harmless.jsonl"
    if hp.exists():  # keep SL translations already filled in
        old = {r["hid"]: r for r in map(json.loads, hp.read_text().splitlines())}
        for r in harmless:
            r["prompt_sl"] = old.get(r["hid"], {}).get("prompt_sl")
    write_jsonl(hp, harmless)
    ident = {"ID_DIR": ID_DIR, "ID_CHECK": ID_CHECK, "PERSONAL_CTRL": PERSONAL_CTRL, "CONT": CONT}
    (DATA / "identity_items.json").write_text(json.dumps(ident, ensure_ascii=False, indent=1))
    s0 = json.loads(STAGE0B.read_text())
    manifest = {
        "pairing": plog, "n_construct": len(construct), "n_score": len(score), "score400_category_counts": counts,
        "score400_dose_groups": {g: sum(p["dose_group"] == g for p in s400) for g in ["low", "mid", "high"]},
        "n_construct200": len(c200), "n_mc_harm40": len(mc40), "n_construct_dir": len(cdir),
        "n_harmless": len(harmless), "overlap_unknown": True,
        "overlap_note": ("refuseu_overlap.json holds counts only (<=10 EN / <=7 SL items overlap the reserved eval split); "
                         "the per-item drop list cannot be rebuilt without reading the reserved split, so items are "
                         "kept and sha1 hashes of every used prompt are exported to results/prompt_hashes.json"),
        "stage0b_per_category_dose": s0["per_category_dose"],
        "low_en": sorted(LOW_EN), "high_en": sorted(HIGH_EN),
    }
    (DATA / "splits_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    logger.info(json.dumps({k: v for k, v in manifest.items() if k != "stage0b_per_category_dose"}, indent=1)[:3000])


if __name__ == "__main__":
    main()
