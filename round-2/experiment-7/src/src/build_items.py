#!/usr/bin/env python3
"""STEP 0: build data/items.jsonl (H = HARD-DEV, R = SCORE-400, R200 depth subset, ID = identity) and data/ref_sft.jsonl.

All sets are NON-RESERVED: asserts that no refuseu_eval / identity_confirm / hard_FINAL item enters data/items.jsonl.
REF_sft = GaMS3's actual SFT refusal texts (DATASET gams_dose_rows with consensus_response_type == safety_refusal;
the DATASET already stores metadata_response = first assistant turn of cjvt/GaMS-Nemotron-Chat, so no HF join is needed).
"""
from __future__ import annotations

import json
from collections import Counter

from common import (DATA, DATASET_DIR, EXP1_DIR, RESERVED_IID_COLLISIONS, read_jsonl, sha256_file, sha_rank,
                    setup_logging, write_jsonl)

logger = setup_logging("build_items")


def norm(s: str) -> str:
    return " ".join((s or "").lower().split())


@logger.catch(reraise=True)
def main() -> None:
    full = json.loads((DATASET_DIR / "full_data_out.json").read_text())
    blocks = {ds["dataset"]: ds["examples"] for ds in full["datasets"]}
    sm = json.loads((DATASET_DIR / "outputs/split_manifest.json").read_text())
    dev_ids = set(sm["hard"]["DEV"]["ids"])
    final_ids = set(sm["hard"]["FINAL"]["ids"]) if isinstance(sm["hard"]["FINAL"], dict) else set(sm["hard"]["FINAL"])
    logger.info(f"hard DEV listed {len(dev_ids)}, FINAL {len(final_ids)}")

    # ---------------- H = HARD-DEV
    hard = [e for k, v in blocks.items() if k.startswith("hard_") for e in v]
    by = {}
    for e in hard:
        if e["metadata_item_id"] in dev_ids and e["metadata_keep"]:
            by.setdefault(e["metadata_item_id"], {})[e["metadata_lang"]] = e
    items = []
    for iid in sorted(by):
        d = by[iid]
        if "en" not in d or "sl" not in d:
            continue
        en, sl = d["en"], d["sl"]
        items.append({"set": "H", "item_id": iid, "source": en["metadata_source"],
                      "is_harmful": bool(en["metadata_is_harmful"]), "hazard": en["output"],
                      "source_category": en["metadata_source_category"], "mt_fragile": bool(sl["metadata_mt_fragile"]),
                      "bt_chrf_gemini": sl["metadata_bt_chrf"], "arms": {"en_orig": en["input"], "sl_mt": sl["input"]},
                      "gpt_back_translation": sl.get("metadata_back_translation")})
    assert not ({it["item_id"] for it in items} & final_ids), "hard FINAL item leaked into H"
    logger.info(f"H: {len(items)} items; strata {Counter((i['source'], i['is_harmful']) for i in items)}")

    # ---------------- R = SCORE-400 (iter-1 exp1 MT-parallel arm; NLLB fwd, existing back_en)
    reserved_texts = {norm(e["input"]) for e in blocks["refuseu_eval"]} | {norm(e["input"]) for e in blocks["identity_confirm"]}
    reserved_texts |= {norm(e["input"]) for e in blocks.get("refuseu_x_mt", [])}
    r_rows = read_jsonl(EXP1_DIR / "data/mt_parallel.jsonl")
    r_items = []
    for r in r_rows:
        r_items.append({"set": "R", "item_id": f"R:{r['pair_id']}", "pair_id": r["pair_id"], "category": r["category"],
                        "is_harmful": True, "source": "refuseu_score", "hazard": r["category"],
                        "mt_flag": r.get("mt_flag"), "chrf_back": r.get("chrf_back"),
                        "arms": {"en_orig": r["prompt_en"], "sl_mt": r["prompt_sl_mt"], "en_bt": r["back_en"]}})
    ranked = sorted(r_items, key=lambda x: sha_rank(x["pair_id"]))
    r200 = {x["item_id"] for x in ranked[:200]}
    for x in r_items:
        x["r200"] = x["item_id"] in r200
    leak = [x["item_id"] for x in r_items if norm(x["arms"]["en_orig"]) in reserved_texts]
    assert not leak, f"R items overlap reserved texts: {leak[:5]}"
    logger.info(f"R: {len(r_items)} items, R200 {len(r200)}")

    # ---------------- ID = identity (iter-1) minus the 3 reserved collisions
    id_rows = [r for r in read_jsonl(EXP1_DIR / "data/identity_items.jsonl") if r["iid"] not in RESERVED_IID_COLLISIONS]
    id_items = [{"set": "ID", "item_id": f"ID:{r['iid']}", "type": r["type"], "intent": r.get("intent"),
                 "arms": {"en": r["text_en"], "sl": r["text_sl"]}} for r in id_rows]
    leak = [x["item_id"] for x in id_items for t in x["arms"].values() if norm(t) in reserved_texts]
    assert not leak, f"ID items overlap reserved identity_confirm texts: {leak}"
    logger.info(f"ID: {len(id_items)} items ({Counter(x['type'] for x in id_items)})")

    all_items = items + r_items + id_items
    write_jsonl(DATA / "items.jsonl", all_items)

    # ---------------- REF_sft
    dose = blocks["gams_dose_rows"]
    ref = []
    for e in dose:
        if e["metadata_consensus_response_type"] == "safety_refusal" and e.get("metadata_response"):
            ref.append({"conversation_id": e["metadata_conversation_id"], "lang": e["metadata_language"],
                        "multiplicity": e.get("metadata_multiplicity"), "hazard": e.get("metadata_hazard_eval_taxonomy"),
                        "prompt": e["input"], "response": e["metadata_response"]})
    # de-duplicate exact-copy refusals (802 of 1,439 duplicate conversation ids are exact copies)
    seen, ref_u = set(), []
    for r in ref:
        k = (r["lang"], r["response"])
        if k not in seen:
            seen.add(k)
            ref_u.append(r)
    write_jsonl(DATA / "ref_sft.jsonl", ref_u)
    logger.info(f"REF_sft: {len(ref)} safety_refusal rows -> {len(ref_u)} unique; {Counter(r['lang'] for r in ref_u)}")

    manifest = {"items_sha256": sha256_file(DATA / "items.jsonl"), "ref_sft_sha256": sha256_file(DATA / "ref_sft.jsonl"),
                "n": {"H": len(items), "R": len(r_items), "R200": len(r200), "ID": len(id_items), "REF_sft": len(ref_u)},
                "H_strata": {f"{a}|{b}": c for (a, b), c in Counter((i['source'], i['is_harmful']) for i in items).items()},
                "sources": {"H": str(DATASET_DIR / "full_data_out.json") + " (hard_* blocks, split_manifest hard.DEV, keep)",
                            "R": str(EXP1_DIR / "data/mt_parallel.jsonl"),
                            "ID": str(EXP1_DIR / "data/identity_items.jsonl") + f" minus {sorted(RESERVED_IID_COLLISIONS)}",
                            "REF_sft": "DATASET gams_dose_rows metadata_response (cjvt/GaMS-Nemotron-Chat first assistant turn)"},
                "reserved_checks": "asserted: no hard_FINAL id in H; no refuseu_eval/refuseu_x/identity_confirm text in R or ID",
                "R200_rule": "200 pair_ids with lowest int(sha1(pair_id+'20260924'))"}
    (DATA / "items_manifest.json").write_text(json.dumps(manifest, indent=1))
    logger.info(json.dumps(manifest["n"]))


if __name__ == "__main__":
    main()
