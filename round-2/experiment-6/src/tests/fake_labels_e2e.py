#!/usr/bin/env python3
"""End-to-end TEST of the analysis stack on real generation rows with FAKE (random) judge labels, in a scratch results
dir (AII_RESULTS). Never touches results/. GaMS rows are simulated by copying Gemma rows if GaMS has not run yet.
Usage: AII_RESULTS=<scratch> python tests/fake_labels_e2e.py  (then run analysis/audit/figs with the same env)."""
import json
import os
import random
import shutil
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
SRC = WS / "results"
DST = Path(os.environ["AII_RESULTS"])
assert DST.resolve() != SRC.resolve()
if DST.exists():
    shutil.rmtree(DST)
DST.mkdir(parents=True)
rng = random.Random(0)
gem, gpt = [], []


def fake(key, cond, arm):
    p_ref = 0.97 if cond == "k0" else (0.80 if arm == "sl_mt" else 0.93)
    u = rng.random()
    lab = "REFUSE" if u < p_ref else ("PARTIAL" if u < p_ref + 0.03 else "COMPLY")
    return lab


for m in ("gemma_it", "gams3_it"):
    src_m = SRC / m if (SRC / m / "final_gen.jsonl").exists() else SRC / "gemma_it"
    (DST / m).mkdir()
    for fn in ("final_gen.jsonl", "dev_gen.jsonl", "batch_check.jsonl", "causal.jsonl", "collateral.jsonl", "hw_check.jsonl"):
        p = src_m / fn
        if not p.exists():
            continue
        out = []
        for line in p.read_text().splitlines():
            r = json.loads(line)
            if src_m.name != m:
                r["key"] = r["key"].replace("gemma_it", m); r["model"] = m
                if "base_key" in r:
                    r["base_key"] = r["base_key"].replace("gemma_it", m)
            out.append(r)
            if fn == "batch_check.jsonl":
                for suf in ("|b", "|s"):
                    gem.append({"key": r["key"] + suf, "ok": True, "label": "REFUSE", "late_refusal": False, "off_language": False, "cost": 0})
                continue
            if fn == "causal.jsonl":
                lab = "REFUSE" if rng.random() < min(0.95, 0.2 + 0.12 * r["alpha"]) else "COMPLY"
            elif fn == "collateral.jsonl":
                lab = "REFUSE" if rng.random() < min(0.9, 0.02 + 0.05 * r["alpha"]) else "COMPLY"
            else:
                lab = fake(r["key"], r["cond"], r["arm"])
            gem.append({"key": r["key"], "ok": True, "label": lab, "late_refusal": rng.random() < 0.3, "off_language": False, "cost": 0})
            if rng.random() < 0.12:
                lab2 = lab if rng.random() < 0.9 else rng.choice(["REFUSE", "PARTIAL", "COMPLY"])
                gpt.append({"key": r["key"], "ok": True, "label": lab2, "late_refusal": False, "off_language": False, "cost": 0})
        (DST / m / fn).write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in out) + "\n")
    for fn in ("directions.npz", "dir_acts.npz", "prefix_table.json"):
        if (src_m / fn).exists():
            shutil.copy(src_m / fn, DST / m / fn)
if (SRC / "hardware_manifest.json").exists():
    shutil.copy(SRC / "hardware_manifest.json", DST / "hardware_manifest.json")
(DST / "judge").mkdir()
(DST / "judge" / "gemini_ledger.jsonl").write_text("\n".join(json.dumps(x) for x in gem) + "\n")
(DST / "judge" / "gpt41_ledger.jsonl").write_text("\n".join(json.dumps(x) for x in gpt) + "\n")
(DST / "m_frozen.json").write_text(json.dumps({"p_dev": 0.1, "k": 10, "n": 100, "m": 0.47, "per_model": {}, "note": "FAKE TEST"}))
print(f"fake labels: {len(gem)} gemini, {len(gpt)} gpt -> {DST}")
