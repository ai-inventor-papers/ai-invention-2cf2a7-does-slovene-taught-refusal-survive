#!/usr/bin/env python3
"""Step 4 ($0, GPU): machine-translate (i) the HARD set EN->SL, (ii) all 1,400 RefusEU eval EN prompts (RefusEU-X
companion; MT by a NON-study model), (iii) 50 gold EN RefusEU test prompts (MT-pair reference for the correspondence
grade). Round-trip chrF with cross-family back-translation; chrF >= 40 keep rule."""
import sys
from pathlib import Path

import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.common import WORK, setup_logging, sha1_int  # noqa: E402
from lib.mt import round_trip  # noqa: E402

setup_logging("s4_mt")


@logger.catch(reraise=True)
def main() -> None:
    hard = pd.read_parquet(WORK / "hard_items.parquet")
    ev = pd.read_parquet(WORK / "eval_items.parquet")
    calib = pd.read_parquet(WORK / "calib_items.parquet")
    ref = calib[(calib.lang == "en") & (calib.gold_split == "test")].copy()
    ref = ref.assign(h=ref.item_id.map(sha1_int)).sort_values("h").head(50)
    en_ev = ev[ev.lang == "en"]
    texts = hard.prompt.tolist() + en_ev.prompt.tolist() + ref.prompt.tolist()
    n = int(sys.argv[1]) if len(sys.argv) > 1 else len(texts)
    recs = round_trip(texts[:n])
    df = pd.DataFrame(recs)
    df["prompt_en"] = texts[:n]
    a, b = len(hard), len(hard) + len(en_ev)
    if n < len(texts):
        logger.info(df.head(10).to_string()); return
    h = pd.concat([hard.reset_index(drop=True), df.iloc[:a].reset_index(drop=True).drop(columns=["prompt_en"])], axis=1)
    h["keep"] = (h.bt_chrf >= 40) & ~h.mt_empty
    h.to_parquet(WORK / "hard_mt.parquet")
    x = df.iloc[a:b].reset_index(drop=True)
    x["source_pair_id"] = en_ev.pair_id.values
    x["item_id"] = "refuseu_x_" + en_ev.row_id.astype(str).values + "_sl"
    x["fold"] = en_ev.fold.str.replace("refuseu_eval", "refuseu_x").values
    x["keep"] = (x.bt_chrf >= 40) & ~x.mt_empty
    x.to_parquet(WORK / "refuseu_x_mt.parquet")
    g = df.iloc[b:].reset_index(drop=True)
    g["item_id"] = ref.item_id.values
    g["gold"] = ref.gold.values
    g.to_parquet(WORK / "gold_mt_ref.parquet")
    for name, d in [("hard", h), ("refuseu_x", x), ("gold_ref", g)]:
        logger.info(f"{name}: n={len(d)} chrF median {d.bt_chrf.median():.1f} <40: {(d.bt_chrf < 40).sum()} empty {d.mt_empty.sum()}")


if __name__ == "__main__":
    main()
