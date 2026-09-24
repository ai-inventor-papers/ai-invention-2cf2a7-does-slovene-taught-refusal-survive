#!/usr/bin/env python3
"""3.4 m rule: VALUE fixed after BOTH models' DEV runs are judged and BEFORE any FINAL statistic is computed.
p_dev = pooled judged flip rate at P5 over DEV items refused at k0 in both sl_mt and en_bt (per model), both models,
arms sl_mt + en_bt, Hautus. m = logit(p+.05)-logit(p) if p<=.5 else logit(p)-logit(p-.05). Writes results/m_frozen.json
and commits it to the protocol git dir."""
from __future__ import annotations

import datetime as dt
import hashlib
import json

from common import RESULTS, WS, hautus, logit, read_jsonl, setup_logger
from labels import load_labels

logger = setup_logger("set_m")


def main() -> None:
    out = RESULTS / "m_frozen.json"
    if out.exists():
        logger.info(f"m already frozen: {out.read_text()}")
        return
    lab, _, _ = load_labels()
    k = n = 0
    per = {}
    for m in ("gemma_it", "gams3_it"):
        rows = read_jsonl(RESULTS / m / "dev_gen.jsonl")
        assert rows, f"DEV rows missing for {m}"
        R = {}
        for r in rows:
            L = lab.get(r["key"])
            if L:
                R[(r["item_id"], r["arm"], r["cond"])] = L["label"] == "REFUSE"
        items = {r["item_id"] for r in rows if r["arm"] == "sl_mt"}
        J = [i for i in items if R.get((i, "sl_mt", "k0")) and R.get((i, "en_bt", "k0"))]
        km = nm = 0
        for i in J:
            for arm in ("sl_mt", "en_bt"):
                v = R.get((i, arm, "P5"))
                if v is not None:
                    km += int(not v); nm += 1
        per[m] = {"J_dev": len(J), "n_items": len(items), "flips": km, "n": nm}
        k += km; n += nm
    p = hautus(k, n)
    m_val = logit(p + 0.05) - logit(p) if p <= 0.5 else logit(p) - logit(p - 0.05)
    rec = {"p_dev": p, "k": k, "n": n, "m": m_val, "per_model": per,
           "frozen_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
           "note": "value fixed after both DEV runs, before any FINAL statistic (analysis.py refuses to run without it)"}
    out.write_text(json.dumps(rec, indent=1))
    try:
        from freeze import _commit
        c = _commit([str(out.relative_to(WS))], f"Freeze m value = {m_val:.4f} (p_dev={p:.4f})")
        rec["commit"] = c
        out.write_text(json.dumps(rec, indent=1))
    except (RuntimeError, OSError) as e:
        logger.warning(f"git commit of m failed: {e}")
    logger.info(f"m frozen: {rec}")


if __name__ == "__main__":
    main()
