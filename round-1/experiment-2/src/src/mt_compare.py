#!/usr/bin/env python3
"""Post-hoc MT quality check (OpenRouter key restored): gemini-2.5-flash EN->SL (the plan's MT) vs the frozen
NLLB-200 1.3B translations actually used in every model run. The frozen items are NOT replaced (protocol + all GPU
runs used them); this quantifies how different the harmless SL prompts would have been.
Writes data/alpaca_harmless_gemini_mt.jsonl and results/analysis/mt_comparison.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from sacrebleu.metrics import CHRF

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ledger import done_keys  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    chrf = CHRF()
    items = [json.loads(l) for l in (ROOT / "data/alpaca_harmless.jsonl").read_text().splitlines()]
    led = done_keys("mt_alpaca")
    rows = []
    for r in items:
        f, b = led.get(f"fwd:{r['hid']}"), led.get(f"bwd:{r['hid']}")
        if not f or not b:
            continue
        g_sl, g_bt = f["content"].strip(), b["content"].strip()
        rows.append({"hid": r["hid"], "role": r["role"], "induction": r["induction"], "en": r["en"],
                     "sl_nllb": r["sl"], "sl_gemini": g_sl, "backtrans_gemini": g_bt,
                     "chrF_bt_nllb": r["chrF"], "chrF_bt_gemini": round(chrf.sentence_score(g_bt, [r["en"]]).score, 2),
                     "chrF_nllb_vs_gemini_sl": round(chrf.sentence_score(r["sl"], [g_sl]).score, 2)})
    with (ROOT / "data/alpaca_harmless_gemini_mt.jsonl").open("w") as fo:
        for r in rows:
            fo.write(json.dumps(r, ensure_ascii=False) + "\n")
    out = {"note": __doc__.splitlines()[0], "n": len(rows)}
    for name, sel in [("all_used", lambda r: r["role"] in ("CONSTRUCT", "SCORE")), ("induction", lambda r: r["induction"])]:
        s = [r for r in rows if sel(r)]
        a = lambda k: np.array([r[k] for r in s])
        out[name] = {"n": len(s),
                     "median_chrF_backtrans_nllb": float(np.median(a("chrF_bt_nllb"))),
                     "median_chrF_backtrans_gemini": float(np.median(a("chrF_bt_gemini"))),
                     "median_chrF_nllb_vs_gemini_sl": float(np.median(a("chrF_nllb_vs_gemini_sl"))),
                     "frac_nllb_vs_gemini_chrF_lt_40": float(np.mean(a("chrF_nllb_vs_gemini_sl") < 40)),
                     "frac_backtrans_nllb_lt_50": float(np.mean(a("chrF_bt_nllb") < 50)),
                     "frac_backtrans_gemini_lt_50": float(np.mean(a("chrF_bt_gemini") < 50))}
    (ROOT / "results/analysis/mt_comparison.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    worst = sorted([r for r in rows if r["induction"]], key=lambda r: r["chrF_nllb_vs_gemini_sl"])[:4]
    for r in worst:
        print(r["chrF_nllb_vs_gemini_sl"], "|", r["en"][:70], "|", r["sl_nllb"][:70], "|", r["sl_gemini"][:70])


if __name__ == "__main__":
    main()
