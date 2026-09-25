#!/usr/bin/env python3
"""Section 2 (DATA): DEPTH-600 / D300 / D200 (FINAL), DEV items, natural-SL DEV items, harmless sets, split manifest.

Reads the dataset artifact (art_EG6OpEkGvysx) full_data_out.json blocks refuseu_x_mt + refuseu_eval, and the iter-1
alpaca_harmless.jsonl. Writes data/*.jsonl + data/split_manifest.json. CPU only.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict

from common import (DATA, DATASET_DIR, HARMLESS_SRC, HIGH_EN, INTERMEDIATE, LOW_EN, SEED, group_of, read_jsonl,
                    setup_logger, sha1_int, write_jsonl)

logger = setup_logger("prep_data")


def alloc_proportional(counts: dict[str, int], total: int, floor: int) -> dict[str, int]:
    """largest-remainder proportional allocation with a per-category floor (capped at availability)."""
    N = sum(counts.values())
    base = {c: min(n, max(min(floor, n), math.floor(total * n / N))) for c, n in counts.items()}
    rem = {c: total * n / N - math.floor(total * n / N) for c, n in counts.items()}
    diff = total - sum(base.values())
    order = sorted(counts, key=lambda c: (-rem[c], c))
    i = 0
    while diff != 0 and i < 10000:
        c = order[i % len(order)]
        if diff > 0 and base[c] < counts[c]:
            base[c] += 1; diff -= 1
        elif diff < 0 and base[c] > min(floor, counts[c]):
            base[c] -= 1; diff += 1
        i += 1
    assert sum(base.values()) == total, (base, total)
    return base


def shrink(alloc: dict[str, int], total: int) -> dict[str, int]:
    """re-stratified sub-allocation: each category gets ~total/sum(alloc) of its allotment (largest remainder)."""
    S = sum(alloc.values())
    exact = {c: alloc[c] * total / S for c in alloc}
    out = {c: math.floor(v) for c, v in exact.items()}
    for c in sorted(alloc, key=lambda c: (-(exact[c] - out[c]), c))[: total - sum(out.values())]:
        out[c] += 1
    assert sum(out.values()) == total
    return out


def main() -> None:
    src = DATASET_DIR / "full_data_out.json"
    logger.info(f"loading {src}")
    d = json.loads(src.read_text())
    blocks = {b["dataset"]: b["examples"] for b in d["datasets"]}
    X = [r for r in blocks["refuseu_x_mt"] if r.get("metadata_keep") is True]
    logger.info(f"refuseu_x_mt keep==True: {len(X)} / {len(blocks['refuseu_x_mt'])}")
    frozen = json.loads((DATASET_DIR / "outputs" / "frozen_groups.json").read_text())["groups"]
    assert frozen["low_EN"] == LOW_EN and frozen["high_EN"] == HIGH_EN and frozen["intermediate"] == INTERMEDIATE

    items = []
    for r in X:
        cat = r["output"]
        items.append({
            "item_id": r["metadata_source_pair_id"], "x_item_id": r["metadata_item_id"], "cat": cat,
            "group": group_of(cat), "pure": bool(r.get("metadata_source_item_pure_en")),
            "fold": r["metadata_fold"], "bt_chrf": r.get("metadata_bt_chrf"),
            "en_orig": r["metadata_source_prompt_en"], "sl_mt": r["input"], "en_bt": r["metadata_back_translation"],
        })
    ids = [it["item_id"] for it in items]
    assert len(ids) == len(set(ids)), "source_pair_id must be unique in refuseu_x_mt"
    # triplet integrity: EN-orig must equal the refuseu_eval EN text of the same source pair
    en_eval = {r["metadata_pair_id"]: r for r in blocks["refuseu_eval"] if r["metadata_lang"] == "en"}
    mism = sum(1 for it in items if en_eval[it["item_id"]]["input"] != it["en_orig"])
    assert mism == 0, f"{mism} EN-orig texts differ from refuseu_eval EN"
    lab_mism = sum(1 for it in items if en_eval[it["item_id"]]["output"] != it["cat"])
    logger.info(f"triplets share source_pair_id; EN-orig text identical to refuseu_eval EN for all; label mismatches={lab_mism}")

    final = [it for it in items if it["fold"] == "refuseu_x_FINAL"]
    dev = [it for it in items if it["fold"] == "refuseu_x_DEV"]
    by_cat = defaultdict(list)
    for it in final:
        by_cat[it["cat"]].append(it)
    for c in by_cat:
        by_cat[c].sort(key=lambda it: sha1_int(it["item_id"] + str(SEED)))
    alloc = {c: min(60, len(by_cat[c])) for c in LOW_EN}
    others = {c: len(by_cat[c]) for c in sorted(by_cat) if c not in LOW_EN}
    alloc.update(alloc_proportional(others, 600 - sum(alloc.values()), floor=20))
    d600 = [it for c in sorted(alloc) for it in by_cat[c][: alloc[c]]]
    a300 = shrink(alloc, 300)
    d300 = [it for c in sorted(a300) for it in by_cat[c][: a300[c]]]
    a200 = shrink(a300, 200)
    d200 = [it for c in sorted(a200) for it in by_cat[c][: a200[c]]]
    s600, s300, s200 = ({it["item_id"] for it in x} for x in (d600, d300, d200))
    assert len(s600) == 600 and s300 <= s600 and s200 <= s300 and len(s300) == 300 and len(s200) == 200
    assert not (s600 & {it["item_id"] for it in dev}), "DEPTH-600 must be disjoint from DEV"
    for it in d600:
        it["in_d300"] = it["item_id"] in s300
        it["in_d200"] = it["item_id"] in s200
    logger.info(f"DEPTH-600 per-category: {dict(sorted(alloc.items(), key=lambda x: int(x[0][1:])))}")
    logger.info(f"D300: {a300}; D200: {a200}; groups D600: {Counter(it['group'] for it in d600)}")

    # natural SL DEV prompts (refuseu_eval DEV, SL side) — used for direction construction only
    nat = [{"item_id": r["metadata_item_id"], "cat": r["output"], "group": group_of(r["output"]),
            "pure": bool(r.get("metadata_item_pure")), "fold": r["metadata_fold"], "sl_nat": r["input"]}
           for r in blocks["refuseu_eval"] if r["metadata_fold"] == "refuseu_eval_DEV" and r["metadata_lang"] == "sl"]
    logger.info(f"DEV x_mt items {len(dev)}; natural SL DEV {len(nat)}")

    hl = [r for r in read_jsonl(HARMLESS_SRC) if r.get("valid") is True]
    hl.sort(key=lambda r: sha1_int(r["hid"] + str(SEED)))
    h_con = [dict(r, use="H_con") for r in hl[:200]]
    h_col = [dict(r, use="H_col") for r in hl[200:250]]
    assert len(h_con) == 200 and len(h_col) == 50 and not ({r["hid"] for r in h_con} & {r["hid"] for r in h_col})

    write_jsonl(DATA / "depth600.jsonl", d600)
    write_jsonl(DATA / "dev_items.jsonl", dev)
    write_jsonl(DATA / "dev_nat_sl.jsonl", nat)
    write_jsonl(DATA / "harmless.jsonl", h_con + h_col)

    def h(lst):
        return hashlib.sha256("\n".join(sorted(lst)).encode()).hexdigest()

    # length stats per arm (characters; token lengths are logged by run_model with the shared tokenizer)
    lens = {arm: {"mean_chars": sum(len(it[arm]) for it in d600) / 600} for arm in ("en_orig", "sl_mt", "en_bt")}
    bt_tail = sum(1 for it in d600 if it["en_bt"].rstrip().endswith(("The New York Times", "Times")))
    manifest = {
        "source": str(src), "source_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
        "harmless_source": str(HARMLESS_SRC), "seed": SEED,
        "depth600_ids_sha256": h(s600), "d300_ids_sha256": h(s300), "d200_ids_sha256": h(s200),
        "dev_ids_sha256": h([it["item_id"] for it in dev]), "dev_nat_ids_sha256": h([r["item_id"] for r in nat]),
        "h_con_sha256": h([r["hid"] for r in h_con]), "h_col_sha256": h([r["hid"] for r in h_col]),
        "alloc_d600": alloc, "alloc_d300": a300, "alloc_d200": a200,
        "n": {"d600": 600, "d300": 300, "d200": 200, "dev": len(dev), "dev_nat_sl": len(nat), "h_con": 200, "h_col": 50},
        "groups_d600": dict(Counter(it["group"] for it in d600)), "pure_d600": sum(it["pure"] for it in d600),
        "arm_char_lengths": lens, "bt_trailing_hallucination_newyorktimes": bt_tail,
        "disjoint_d600_dev": True, "all_keep_true": True,
        "note": "SL = NLLB-200-distilled-1.3B MT (not human-verified); EN-BT = Helsinki-NLP/opus-mt-tc-big-zls-en BT.",
    }
    (DATA / "split_manifest.json").write_text(json.dumps(manifest, indent=2))
    logger.info(f"wrote data/; BT trailing 'New York Times' hallucinations in D600: {bt_tail}")


if __name__ == "__main__":
    main()
