#!/usr/bin/env python3
"""Step 4b (OpenRouter, step C): plan MT for the HARD set. Forward google/gemini-2.5-flash (temperature 0, 20 items/call,
'preserve ambiguity, homonyms and figurative wording; do not soften or refuse'), back-translation openai/gpt-4.1-mini,
chrF2; < 40 -> one unbatched forward retry; refused/empty -> NLLB fallback (flagged). The earlier local NLLB/Marian round
trip is kept as secondary columns nllb_*."""
import asyncio
import sys
from pathlib import Path

import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.api_mt import api_round_trip  # noqa: E402
from lib.common import LABELS, WORK, setup_logging  # noqa: E402

setup_logging("s4b_hard_api_mt")


@logger.catch(reraise=True)
def main() -> None:
    h = pd.read_parquet(WORK / "hard_mt.parquet")
    if "nllb_prompt_sl" not in h.columns:
        h = h.rename(columns={c: f"nllb_{c}" for c in ["prompt_sl", "prompt_bt", "bt_chrf", "mt_retry", "bt_chrf_first", "mt_empty", "mt_by", "keep"] if c in h.columns})
        h.to_parquet(WORK / "hard_mt_nllb_backup.parquet")
    rec = asyncio.run(api_round_trip(h.item_id.tolist(), h.prompt.tolist(), "C_hard_mt", LABELS / "hard_mt",
                                     "Translate faithfully, keeping the user's register."))
    r = pd.DataFrame([rec[k] for k in h.item_id])
    for c in r.columns:
        h[c] = r[c].values
    fb = h.mt_refused | h.mt_empty
    h.loc[fb, "prompt_sl"] = h.loc[fb, "nllb_prompt_sl"]
    h.loc[fb, "prompt_bt"] = h.loc[fb, "nllb_prompt_bt"]
    h.loc[fb, "bt_chrf"] = h.loc[fb, "nllb_bt_chrf"]
    h.loc[fb, "mt_by"] = h.loc[fb, "nllb_mt_by"] + " [fallback: API MT refused/empty]"
    h["keep"] = (h.bt_chrf >= 40) & (h.prompt_sl.str.strip() != "")
    h.to_parquet(WORK / "hard_mt.parquet")
    logger.info(f"API MT: median chrF {h.bt_chrf.median():.1f} (NLLB {h.nllb_bt_chrf.median():.1f}); <40 {(h.bt_chrf < 40).sum()}; "
                f"refused {int(h.mt_refused.sum())}; fallback {int(fb.sum())}; keep {int(h.keep.sum())}")
    logger.info(h.groupby("source").bt_chrf.describe().to_string())


if __name__ == "__main__":
    main()
