#!/usr/bin/env python3
"""Phase 0.2: build data/items_final.jsonl (1,300 pairs x EN/SL) and data/items_dev.jsonl (100 pairs x EN/SL) from the
reserved refuseu_eval block of art_EG6OpEkGvysx (full_data_out.json; never the 200-char preview). Asserts fold
membership against the dataset's split_manifest.json, DEV/FINAL disjointness, counts and max prompt length > 200.
Writes data/provenance.json, data/contamination_check.json and the frozen hash orders (random-control subset,
256-token sensitivity subset, 650-pair reduction order)."""
from __future__ import annotations

import glob
import hashlib
import json

from loguru import logger

from common import DATA, DS_DIR, RUN, dump, setup_logging, sha1, sha256_file, write_jsonl

KEEP = ["metadata_item_balanced_label", "metadata_item_group", "metadata_labse_cos", "metadata_corr_grade",
        "metadata_pair_pure", "metadata_item_pure", "output"]


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("build_items")
    src = DS_DIR / "full_data_out.json"
    man_p = DS_DIR / "outputs/split_manifest.json"
    data = json.loads(src.read_text())
    blk = [d for d in data["datasets"] if d["dataset"] == "refuseu_eval"]
    assert len(blk) == 1, "refuseu_eval block missing"
    ex = blk[0]["examples"]
    del data
    man = json.loads(man_p.read_text())["refuseu_eval"]
    dev_ids, fin_ids = set(man["DEV"]["ids"]), set(man["FINAL"]["ids"])
    assert not dev_ids & fin_ids, "DEV/FINAL overlap in manifest"
    logger.info(f"refuseu_eval rows {len(ex)}; manifest DEV {len(dev_ids)} FINAL {len(fin_ids)}")

    def row(e: dict) -> dict:
        return {"item_id": e["metadata_item_id"], "pair_id": e["metadata_pair_id"], "lang": e["metadata_lang"],
                "fold": e["metadata_fold"], "prompt": e["input"], "hazard": e["metadata_item_balanced_label"],
                "hazard_blind_label": e["output"], "group": e["metadata_item_group"],
                "labse_cos": e["metadata_labse_cos"], "corr_grade": e["metadata_corr_grade"],
                "pair_pure": e["metadata_pair_pure"], "item_pure": e["metadata_item_pure"]}

    fin = [row(e) for e in ex if e["metadata_fold"] == "refuseu_eval_FINAL"]
    dev = [row(e) for e in ex if e["metadata_fold"] == "refuseu_eval_DEV"]
    # manifest ids may be pair ids or item ids: accept either
    def in_fold(r: dict, ids: set) -> bool:
        return r["pair_id"] in ids or r["item_id"] in ids
    assert all(in_fold(r, fin_ids) for r in fin), "a FINAL row is not in the manifest FINAL fold"
    assert all(in_fold(r, dev_ids) for r in dev), "a DEV row is not in the manifest DEV fold"
    assert not {r["pair_id"] for r in fin} & {r["pair_id"] for r in dev}
    for rows, n in ((fin, 1300), (dev, 100)):
        for L in ("en", "sl"):
            k = sum(r["lang"] == L for r in rows)
            assert k == n, (L, k, n)
        assert len({r["pair_id"] for r in rows}) == n
    mx = max(len(r["prompt"]) for r in fin)
    assert mx > 200, "prompts look truncated (preview file?)"
    logger.info(f"FINAL {len(fin)} rows, DEV {len(dev)} rows; max prompt chars {mx}")

    # frozen hash orders over FINAL pair ids
    pairs = sorted({r["pair_id"] for r in fin}, key=lambda p: sha1("20260925|" + p))
    order = {p: i for i, p in enumerate(pairs)}
    rand_ctrl = pairs[:200]
    sens256 = sorted(pairs, key=lambda p: sha1("256|20260925|" + p))[:100]
    for r in fin:
        r["hash_rank"] = order[r["pair_id"]]
        r["rand_ctrl"] = r["pair_id"] in set(rand_ctrl)
        r["sens256"] = r["pair_id"] in set(sens256)
    fin.sort(key=lambda r: (r["hash_rank"], r["lang"]))
    write_jsonl(DATA / "items_final.jsonl", fin)
    write_jsonl(DATA / "items_dev.jsonl", sorted(dev, key=lambda r: (sha1("20260925|" + r["pair_id"]), r["lang"])))

    # contamination: any refuseu_eval item id inside generation/row files of iter 2-4 artifacts?
    ids = {r["item_id"] for r in fin} | {r["pair_id"] for r in fin}
    pat_files = []
    for it in (2, 3, 4):
        for pat in ("gens", "rows"):
            pat_files += glob.glob(str(RUN / f"iter_{it}/gen_art/*/**/*{pat}*"), recursive=True)
    pat_files = sorted({f for f in pat_files if f.endswith((".jsonl", ".json", ".csv"))})
    hits: dict[str, int] = {}
    import re
    rx = re.compile(r"refuseu_eval_\d+")
    for f in pat_files:
        try:
            with open(f, errors="ignore") as fh:
                found = set(rx.findall(fh.read()))
        except (OSError, IsADirectoryError):
            continue
        k = len(found & ids)
        if k:
            hits[f.split("3_invention_loop/")[-1]] = k
    dump(DATA / "contamination_check.json", {"files_scanned": len(pat_files), "files_with_hits": hits,
                                             "n_hit_files": len(hits),
                                             "rule": "grep 'refuseu_eval_<n>' ids of FINAL items inside any gens/rows "
                                                     "file of iter_2..4 gen_art workspaces"})
    logger.info(f"contamination: {len(pat_files)} files scanned, {len(hits)} with FINAL ids: {hits}")

    dump(DATA / "provenance.json", {
        "source_dataset": "art_EG6OpEkGvysx iter_1/gen_art/gen_art_dataset_1/full_data_out.json (block refuseu_eval)",
        "source_sha256": sha256_file(src), "split_manifest_sha256": sha256_file(man_p),
        "hf_dataset": f"NASK-PIB/RefusEU@{man['refuseu_commit']}", "fold_rule": man["rule"],
        "counts": {"FINAL_rows": len(fin), "DEV_rows": len(dev), "FINAL_pairs": 1300, "DEV_pairs": 100},
        "max_prompt_chars": mx, "rand_ctrl_rule": "first 200 FINAL pair_ids by sha1('20260925|'+pair_id)",
        "sens256_rule": "first 100 FINAL pair_ids by sha1('256|20260925|'+pair_id) (EN+SL)",
        "reduction_order": "hash_rank = rank of sha1('20260925|'+pair_id)",
        "items_final_sha256": sha256_file(DATA / "items_final.jsonl"),
        "items_dev_sha256": sha256_file(DATA / "items_dev.jsonl"),
        "contamination_hit_files": len(hits)})
    logger.info("provenance written")


if __name__ == "__main__":
    main()
