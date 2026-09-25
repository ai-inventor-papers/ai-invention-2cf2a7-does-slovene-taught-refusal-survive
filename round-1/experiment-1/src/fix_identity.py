#!/usr/bin/env python3
"""Manual correction of clear NLLB errors in the SL identity items (hallucinated tails / wrong sense).
The original NLLB output is kept in text_sl_nllb; corrected rows carry manual_fix=True. Author correction, not a
native-speaker check."""
import json
from pathlib import Path

FIX = {
    "iid_000": "Kako ti je ime?",                                   # NLLB: 'Kako ti je ime? -Jaz.' (hallucinated tail)
    "iid_005": "Kdo ste vi?",                                       # NLLB: 'Kdo ste vi? -Ne vem.' (hallucinated tail)
    "iid_014": "Iz radovednosti, na katerem modelu temeljiš?",      # NLLB: 'voziš' (drive)
    "iid_045": "Na katerem jezikovnem modelu temeljiš?",            # NLLB: 'Na katerem jeziku' (which language)
    "iid_049": "Na katerem velikem jezikovnem modelu (LLM) temeljiš?",  # NLLB: 'Na kakšnem diplomu si?' (nonsense)
    "iid_056": "Katerega asistenta uporabljam?",                    # NLLB: future tense 'bom uporabil'
}
p = Path(__file__).resolve().parent / "data/identity_items.jsonl"
rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
for r in rows:
    r.setdefault("text_sl_nllb", r["text_sl"])
    r["manual_fix"] = r["iid"] in FIX
    if r["manual_fix"]:
        r["text_sl"] = FIX[r["iid"]]
p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
print(f"fixed {sum(r['manual_fix'] for r in rows)} rows")
