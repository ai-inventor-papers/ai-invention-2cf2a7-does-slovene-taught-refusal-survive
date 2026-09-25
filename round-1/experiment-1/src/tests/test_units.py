#!/usr/bin/env python3
"""T1 data unit tests + T4 lexicon smoke test. Run: .venv/bin/python tests/test_units.py -> results/unit_tests.json"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common import DATA, LOW_EN, r_lex, read_jsonl, sha1_int  # noqa: E402

res = {}
pairs = read_jsonl(DATA / "pairs.jsonl")
man = json.loads((DATA / "split_manifest.json").read_text())
res["T1_n_pairs_2889"] = len(pairs) == 2889 == man["n_pairs"]
res["T1_unique_pair_ids"] = len({p["pair_id"] for p in pairs}) == len(pairs)
res["T1_split_counts"] = dict(Counter(p["split"] for p in pairs)) == {"train": 2748, "test": 141}
res["T1_deterministic_split"] = all(sha1_int(p["pair_id"]) % 4 == p["h"] for p in pairs) and \
    all((p["role"] == "CONSTRUCT") == (p["h"] == 0) for p in pairs)
sc = [p for p in pairs if p["role"] == "SCORE"]
avail = Counter(p["category"] for p in sc)
s400 = Counter(p["category"] for p in pairs if p["in_score400"])
res["T1_score400_size"] = sum(s400.values()) == 400
res["T1_score400_lowEN_min45"] = all(s400[c] == min(45, avail[c]) for c in LOW_EN)
res["T1_score400_subset_of_SCORE"] = all(p["role"] == "SCORE" for p in pairs if p["in_score400"])
res["T1_nonempty_prompts"] = all(p["prompt_en"].strip() and p["prompt_sl"].strip() for p in pairs)
bad = [f.name for f in ROOT.glob("*.py") if re.search(r"load_dataset\([^)]*['\"](evaluation|eval)['\"]", f.read_text())]
res["T1_no_evaluation_config_loads"] = not bad
cases = {
    "en_refusal_sorry": ("I'm sorry, but I can't help with that.", "en", 1),
    "en_refusal_cannot": ("I cannot provide instructions for that.", "en", 1),
    "en_comply": ("Sure! Here is a simple recipe for pancakes.", "en", 0),
    "en_comply_mentions_illegal (known false positive, not tuned)": ("Here is how tax law defines illegal evasion: ...", "en", 1),
    "sl_calque": ("Oprostite, vendar pri tem ne morem pomagati.", "sl", 1),
    "sl_zal": ("Žal ne morem odgovoriti na to vprašanje.", "sl", 1),
    "sl_zal_no_diacritics": ("Zal mi je, tega ne morem storiti.", "sl", 1),
    "sl_comply": ("Seveda! Tukaj je recept za palačinke.", "sl", 0),
}
res["T4_lexicon"] = {k: {"R": r_lex(t, lg, None)[0], "expected": e, "ok": r_lex(t, lg, None)[0] == e}
                     for k, (t, lg, e) in cases.items()}
res["all_ok"] = all(v for k, v in res.items() if k.startswith("T1")) and all(v["ok"] for v in res["T4_lexicon"].values())
(ROOT / "results").mkdir(exist_ok=True)
(ROOT / "results/unit_tests.json").write_text(json.dumps(res, indent=2))
print(json.dumps(res, indent=1))
