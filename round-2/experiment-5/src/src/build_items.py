#!/usr/bin/env python3
"""STEP 1 (CPU, $0): build item manifests data/{refuseu_nat,refuseu_x,hard,identity}.jsonl + data/manifest_hashes.json
from the iter-1 dataset artifact (art_EG6OpEkGvysx, full_data_out.json). Asserts the exact fold counts (T1).

Each manifest row = one PROMPT to generate (item x arm):
  {gid: "<set>|<arm>|<item_id>", set, arm, split(DEV/FINAL), item_id, pair_id, prompt_lang, text, + item metadata}
"""
from __future__ import annotations

import json
import random
from collections import Counter, defaultdict

from loguru import logger

from common import (DATA, DS_FULL, DS_OUT, GROUPS, SEED, group_of, sha256_bytes, sha256_file, setup_logging,
                    write_jsonl)

GRP_MAP = {"low_EN": "low", "high_EN": "high", "intermediate": "int"}


def split_of(fold: str) -> str:
    if fold.endswith("_DEV"):
        return "DEV"
    if fold.endswith("_FINAL"):
        return "FINAL"
    return "EXCLUDED"


def gid(set_: str, arm: str, item_id: str) -> str:
    return f"{set_}|{arm}|{item_id}"


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("build_items")
    ds = json.loads(DS_FULL.read_text())
    blocks = {b["dataset"]: b["examples"] for b in ds["datasets"]}
    manifest = json.loads((DS_OUT / "split_manifest.json").read_text())
    rows_out: dict[str, list[dict]] = {}
    checks: dict[str, object] = {}

    # ---------------- 1.1 RefusEU natural ----------------
    by_pair: dict[str, dict[str, dict]] = defaultdict(dict)
    for e in blocks["refuseu_eval"]:
        by_pair[e["metadata_pair_id"]][e["metadata_lang"]] = e
    nat = []
    mism = 0
    for pid, d in sorted(by_pair.items()):
        assert set(d) == {"en", "sl"}, pid
        for lang, arm in (("en", "EN_nat"), ("sl", "SL_nat")):
            e = d[lang]
            g = group_of(e["output"])
            if e.get("metadata_item_group") and GRP_MAP.get(e["metadata_item_group"]) != g:
                mism += 1
            nat.append({"gid": gid("refuseu_nat", arm, e["metadata_item_id"]), "set": "refuseu_nat", "arm": arm,
                        "split": split_of(e["metadata_fold"]), "item_id": e["metadata_item_id"], "pair_id": pid,
                        "prompt_lang": lang, "text": e["input"], "label": e["output"], "group": g,
                        "balanced": e.get("metadata_item_balanced_label"),
                        "group_balanced": group_of(e.get("metadata_item_balanced_label")),
                        "pure": bool(e.get("metadata_item_pure")), "row_id": e.get("metadata_row_id")})
    assert mism == 0, f"{mism} items whose group != metadata_item_group"
    c = Counter((r["split"]) for r in nat)
    assert c["FINAL"] == 2600 and c["DEV"] == 200, c
    dev_ids = sorted({r["pair_id"] for r in nat if r["split"] == "DEV"})
    assert dev_ids == sorted(manifest["refuseu_eval"]["DEV"]["ids"]), "RefusEU DEV ids != split_manifest"
    checks["refuseu_nat"] = {"FINAL_pairs": c["FINAL"] // 2, "DEV_pairs": c["DEV"] // 2, "dev_ids_match_manifest": True,
                             "group_mismatch_vs_metadata": mism}
    rows_out["refuseu_nat"] = nat

    # ---------------- 1.2 RefusEU item-matched (NLLB SL-MT + opus-mt EN back-translation) ----------------
    en_src = {e["metadata_pair_id"]: e for e in blocks["refuseu_eval"] if e["metadata_lang"] == "en"}
    x = []
    bt_suspect = 0
    kept = Counter()
    for e in blocks["refuseu_x_mt"]:
        sp = split_of(e["metadata_fold"])
        if sp == "EXCLUDED" or not e.get("metadata_keep"):
            kept["excluded"] += 1
            continue
        kept[sp] += 1
        spid = e["metadata_source_pair_id"]
        src = en_src[spid]
        base = {"set": "refuseu_x", "split": sp, "item_id": e["metadata_item_id"], "pair_id": spid,
                "label": e["output"], "group": group_of(e["output"]),
                "pure": bool(e.get("metadata_source_item_pure_en")), "bt_chrf": e.get("metadata_bt_chrf")}
        x.append({**base, "gid": gid("refuseu_x", "SL_MT", e["metadata_item_id"]), "arm": "SL_MT",
                  "prompt_lang": "sl", "text": e["input"]})
        bt = (e.get("metadata_back_translation") or "").strip()
        ratio = len(bt) / max(1, len(src["input"]))
        if not bt or not (0.5 <= ratio <= 2.0):
            bt_suspect += 1
            continue
        x.append({**base, "gid": gid("refuseu_x", "EN_BT", e["metadata_item_id"]), "arm": "EN_BT",
                  "prompt_lang": "en", "text": bt})
    logger.info(f"refuseu_x kept {dict(kept)}; bt_suspect excluded from EN_BT: {bt_suspect}")
    assert kept["FINAL"] == 1296 and kept["DEV"] == 98, kept
    checks["refuseu_x"] = {"kept": dict(kept), "bt_suspect_excluded_from_EN_BT": bt_suspect}
    rows_out["refuseu_x"] = x

    # ---------------- 1.3 HARD (XSTest + OR-Bench-hard-1k + OR-Bench-toxic300) ----------------
    hard = []
    items: dict[str, dict[str, dict]] = defaultdict(dict)
    for name in ("hard_xstest", "hard_orbench_hard1k", "hard_orbench_toxic300"):
        for e in blocks[name]:
            items[e["metadata_item_id"]][e["metadata_lang"]] = e
    split_items = defaultdict(list)
    for iid, d in items.items():
        en, sl = d["en"], d["sl"]
        sp = split_of(en["metadata_fold"])
        if sp == "EXCLUDED":
            continue
        split_items[sp].append(iid)
    assert len(split_items["FINAL"]) == 1442 and len(split_items["DEV"]) == 616, {k: len(v) for k, v in split_items.items()}
    # DEV_GEN subsample: 300 DEV items stratified (proportional) by source x is_harmful
    rng = random.Random(SEED)
    strata = defaultdict(list)
    for iid in sorted(split_items["DEV"]):
        en = items[iid]["en"]
        strata[(en["metadata_source"], bool(en["metadata_is_harmful"]))].append(iid)
    n_dev = sum(len(v) for v in strata.values())
    dev_gen = set()
    alloc = {}
    for k, v in sorted(strata.items()):
        take = round(300 * len(v) / n_dev)
        alloc[str(k)] = take
        dev_gen.update(rng.sample(v, min(take, len(v))))
    logger.info(f"HARD DEV_GEN {len(dev_gen)} alloc {alloc}")
    comp = Counter()
    for sp in ("DEV", "FINAL"):
        for iid in sorted(split_items[sp]):
            if sp == "DEV" and iid not in dev_gen:
                continue
            en, sl = items[iid]["en"], items[iid]["sl"]
            base = {"set": "hard", "split": sp, "item_id": iid, "pair_id": iid, "source": en["metadata_source"],
                    "is_harmful": bool(en["metadata_is_harmful"]), "xstest_type": en.get("metadata_xstest_type"),
                    "category": en["output"], "group": group_of(en["output"]),
                    "mt_fragile": bool(en.get("metadata_mt_fragile")), "bt_chrf": sl.get("metadata_bt_chrf"),
                    "lg3_en": en.get("metadata_llama_guard3_en"), "lg3_sl": en.get("metadata_llama_guard3_sl")}
            if sp == "FINAL":
                comp[(base["source"], base["is_harmful"])] += 1
            arms = [("EN_orig", "en", en["input"]), ("SL_MT", "sl", sl["input"]),
                    ("EN_BT", "en", (sl.get("metadata_back_translation") or "").strip())]
            if sp == "FINAL" and base["source"] == "xstest" and sl.get("metadata_nllb_prompt_sl"):
                arms.append(("SL_NLLB", "sl", sl["metadata_nllb_prompt_sl"]))
            for arm, lang, text in arms:
                if not text:
                    logger.warning(f"empty text {iid} {arm}")
                    continue
                hard.append({**base, "gid": gid("hard", arm, iid), "arm": arm, "prompt_lang": lang, "text": text})
    logger.info(f"HARD FINAL composition {dict(comp)}")
    checks["hard"] = {"FINAL_items": len(split_items["FINAL"]), "DEV_items": len(split_items["DEV"]),
                      "DEV_GEN": len(dev_gen), "DEV_GEN_alloc": alloc,
                      "FINAL_composition": {f"{k[0]}|harmful={k[1]}": v for k, v in comp.items()}}
    rows_out["hard"] = hard

    # ---------------- 1.4 identity ----------------
    idrows = []
    idp: dict[str, dict[str, dict]] = defaultdict(dict)
    for e in blocks["identity_confirm"]:
        idp[e["metadata_pair_id"]][e["metadata_lang"]] = e
    cnt = Counter()
    for pid, d in sorted(idp.items()):
        for lang in ("en", "sl"):
            e = d[lang]
            sp = split_of(e["metadata_fold"])
            cnt[(sp, e["output"], lang)] += 1
            idrows.append({"gid": gid("identity", lang.upper(), pid), "set": "identity", "arm": lang.upper(),
                           "split": sp, "item_id": pid, "pair_id": pid, "prompt_lang": lang, "text": e["input"],
                           "kind": e["output"], "facet": e.get("metadata_facet"),
                           "matched_pair_id": e.get("metadata_matched_pair_id")})
    for sp, n in (("FINAL", 80), ("DEV", 40)):
        for kind in ("identity", "control"):
            for lang in ("en", "sl"):
                assert cnt[(sp, kind, lang)] == n, (sp, kind, lang, cnt)
    idm = json.loads((DS_OUT / "identity_items_ids.json").read_text())
    for sp in ("DEV", "FINAL"):
        got = sorted({r["pair_id"] for r in idrows if r["split"] == sp and r["kind"] == "identity"})
        assert got == sorted(idm[f"identity_{sp}"]), f"identity {sp} ids != identity_items_ids.json"
    checks["identity"] = {k[0] + "|" + k[1] + "|" + k[2]: v for k, v in cnt.items()}
    rows_out["identity"] = idrows

    # ---------------- disjointness + write ----------------
    for s, rows in rows_out.items():
        dv = {r["item_id"] for r in rows if r["split"] == "DEV"}
        fn = {r["item_id"] for r in rows if r["split"] == "FINAL"}
        assert not (dv & fn), f"{s}: DEV/FINAL overlap"
        assert len({r["gid"] for r in rows}) == len(rows), f"{s}: duplicate gid"
    hashes = {}
    for s, rows in rows_out.items():
        p = DATA / f"{s}.jsonl"
        write_jsonl(p, rows)
        hashes[s] = {"file_sha256": sha256_file(p), "n_rows": len(rows),
                     "by_split_arm": {f"{k[0]}|{k[1]}": v for k, v in Counter((r['split'], r['arm']) for r in rows).items()},
                     "DEV_item_ids_sha256": sha256_bytes("\n".join(sorted({r['item_id'] for r in rows if r['split'] == 'DEV'})).encode()),
                     "FINAL_item_ids_sha256": sha256_bytes("\n".join(sorted({r['item_id'] for r in rows if r['split'] == 'FINAL'})).encode())}
    hashes["source_dataset"] = {"path": str(DS_FULL), "sha256": sha256_file(DS_FULL)}
    hashes["frozen_groups"] = {"groups": GROUPS, "sha256_file": sha256_file(DS_OUT / "frozen_groups.json")}
    hashes["checks_T1"] = checks
    (DATA / "manifest_hashes.json").write_text(json.dumps(hashes, indent=1))
    logger.info(json.dumps({s: h["by_split_arm"] for s, h in hashes.items() if "by_split_arm" in h}))


if __name__ == "__main__":
    main()
