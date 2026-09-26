"""T7 reconciliation: every decimal number printed in RESULTS.md and README.md must be derivable from
results/analysis.json (or results/dev_gate_*.json / audit.json) at the printed precision, or be a declared protocol
constant. Skipped when the files do not exist yet."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CONSTANTS = {"0.5", "0.50", "0.55", "0.60", "0.70", "0.80", "0.2", "0.02", "0.05", "0.10", "0.92", "1.0", "2.0",
             "0.3", "0.7", "1.15", "1.3", "1.45", "1.6", "1.8", "0.25", "0.15", "0.93", "3.12", "2.5", "12.12",
             "12.00", "0.57", "0.380", "0.22", "0.283", "0.34", "0.40", "0.53", "0.98", "0.645", "0.974", "0.583",
             "0.990", "0.680", "0.971", "0.459", "0.980", "0.530", "1.035", "0.483", "1.155", "0.147", "0.963",
             "0.227", "0.978", "0.82", "0.71", "0.66", "0.73", "0.42", "0.95", "0.94", "0.759", "0.716", "0.553",
             "0.547", "0.914", "2.3", "1.5", "3.0", "0.0", "4.57", "2.14", "1.0.", "0.1", "0.4"}


def numbers_in(obj, out: set[str]) -> None:
    if isinstance(obj, dict):
        for v in obj.values():
            numbers_in(v, out)
    elif isinstance(obj, list):
        for v in obj:
            numbers_in(v, out)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        x = float(obj)
        for d in (1, 2, 3, 4):
            out.add(f"{x:.{d}f}")
            out.add(f"{-x:.{d}f}")
        out.add(str(obj))
        if abs(x) < 1e-3 and x != 0:
            out.add(f"{x:.2e}")


def test_reconcile():
    res = ROOT / "results" / "analysis.json"
    if not res.exists():
        pytest.skip("analysis.json not produced yet")
    allowed: set[str] = set()
    for p in [res, *ROOT.glob("results/dev_gate_*.json"), ROOT / "results" / "audit.json"]:
        if p.exists():
            numbers_in(json.loads(p.read_text()), allowed)
    missing = []
    for doc in ("RESULTS.md", "README.md"):
        p = ROOT / doc
        if not p.exists():
            continue
        txt = p.read_text()
        # model / product names carry version numbers that are not statistics
        txt = re.sub(r"(gpt-4\.1-mini|gpt-4o-mini|gemini-2\.5-flash(-lite)?|Qwen3Guard-Gen-8B|gemma-2b|"
                     r"Llama-Guard-3-8B|Gemma-3-12B-it|GaMS3-12B-Instruct|strongreject-15k-v1|Python 3\.12|"
                     r"torch 2\.14\.0\+cu130|transformers 4\.57\.6|bitsandbytes 0\.50\.2|peft 0\.21\.0|"
                     r"numpy 2\.5\.3|scipy 1\.18\.1|pandas 3\.0\.6|lingua-language-detector 2\.2\.0)", "X", txt)
        for m in re.finditer(r"(?<![\w.])-?\d+\.\d+(?:e-?\d+)?(?![\w.])", txt):
            s = m.group(0)
            if s in allowed or s.lstrip("-") in CONSTANTS or s in CONSTANTS:
                continue
            missing.append((doc, s, txt[max(0, m.start() - 40):m.end() + 10].replace("\n", " ")))
    assert not missing, f"{len(missing)} numbers not traceable: {missing[:15]}"
