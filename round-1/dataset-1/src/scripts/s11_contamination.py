#!/usr/bin/env python3
"""Step 11 ($0, CPU; plan step 7e): contamination flags vs the public GaMS SFT prompts (cjvt/GaMS-Nemotron-Chat, dedup).
Per item: exact match, and share of the item's word n-grams (n = min(8, #words)) found in the same-language Nemotron
prompts; flag if exact or share > 0.5. Items: RefusEU eval EN/SL, HARD EN (vs EN) and SL MT (vs SL), RefusEU-X SL."""
import json
import sys
from pathlib import Path

import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import OUT, WORK, setup_logging  # noqa: E402
from s8b_identity_finalize import NgramIndex, words  # noqa: E402

setup_logging("s11_contamination")


@logger.catch(reraise=True)
def main() -> None:
    nem = pd.read_parquet(WORK / "nemotron_prompts.parquet")
    ev = pd.read_parquet(WORK / "eval_items.parquet")
    h = pd.read_parquet(WORK / "hard_mt.parquet")
    rx = pd.read_parquet(WORK / "refuseu_x_mt.parquet")
    items = {"en": pd.concat([ev[ev.lang == "en"][["item_id", "prompt"]].assign(set="eval"),
                              h[["item_id", "prompt"]].assign(set="hard_en", item_id=lambda d: d.item_id + "_en")]),
             "sl": pd.concat([ev[ev.lang == "sl"][["item_id", "prompt"]].assign(set="eval"),
                              h[["item_id", "prompt_sl"]].rename(columns={"prompt_sl": "prompt"}).assign(set="hard_sl", item_id=lambda d: d.item_id + "_sl"),
                              rx[["item_id", "prompt_sl"]].rename(columns={"prompt_sl": "prompt"}).assign(set="refuseu_x")])}
    res = []
    for lang, it in items.items():
        ns = {max(1, min(8, len(words(t)))) for t in it.prompt}
        idx = NgramIndex(nem[nem.language == lang].user.tolist(), ns)
        it = it.assign(nem_exact=it.prompt.map(idx.is_exact), nem_ngram_share=it.prompt.map(idx.share).round(4))
        it["contaminated"] = it.nem_exact | (it.nem_ngram_share > 0.5)
        res.append(it.drop(columns=["prompt"]).assign(lang=lang))
        logger.info(f"{lang}: {it.groupby('set').contaminated.sum().to_dict()}")
    r = pd.concat(res, ignore_index=True)
    r.to_parquet(WORK / "contamination.parquet")
    rep = {f"{s}|{l}": {"n": len(g), "exact": int(g.nem_exact.sum()), "gt50pct_ngram": int((g.nem_ngram_share > 0.5).sum()),
                        "max_share": float(g.nem_ngram_share.max())} for (s, l), g in r.groupby(["set", "lang"])}
    (OUT / "contamination_report.json").write_text(json.dumps(rep, indent=1))
    logger.info(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
