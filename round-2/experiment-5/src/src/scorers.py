#!/usr/bin/env python3
"""STEP 5.2: $0 scorers on every response: R_lex (iter-1 frozen lexicon, diagnostic), language ID (lingua), empty,
repetitive, malformed, truncated, regex self-name detector. Writes outputs/<split>/scores.jsonl.
FINAL is guarded (addendum must be committed first).  Usage: python scorers.py --split dev|final
"""
from __future__ import annotations

import argparse
import re
import zlib
from collections import Counter

from loguru import logger

from common import OUT_DEV, OUT_FINAL, guard_final, r_lex, read_jsonl, setup_logging, write_jsonl

NAME_RE = {
    "GaMS": re.compile(r"\bGaMS\b", re.I), "Gemma": re.compile(r"\bGemm[ae]\b", re.I),
    "Qwen": re.compile(r"\b(Qwen|Tongyi|Alibab)", re.I), "ChatGPT": re.compile(r"\b(ChatGPT|OpenAI|GPT-4)", re.I),
    "Claude": re.compile(r"\b(Claude|Anthropic)", re.I),
}
_DET = None


def detector():
    global _DET
    if _DET is None:
        from lingua import Language, LanguageDetectorBuilder
        _DET = LanguageDetectorBuilder.from_languages(Language.ENGLISH, Language.SLOVENE, Language.CROATIAN,
                                                      Language.SERBIAN, Language.BOSNIAN).build()
    return _DET


LANG_CODE = {"ENGLISH": "en", "SLOVENE": "sl", "CROATIAN": "hr", "SERBIAN": "sr", "BOSNIAN": "bs"}


def lang_id(text: str) -> str:
    if len(text.strip()) < 5:
        return "none"
    lg = detector().detect_language_of(text)
    return LANG_CODE.get(lg.name, "other") if lg else "other"


def repetitive(text: str) -> bool:
    w = text.lower().split()
    if len(w) >= 8:
        c = Counter(tuple(w[i:i + 4]) for i in range(len(w) - 3))
        if c and max(c.values()) >= 4:
            return True
    b = text.encode()
    return len(b) > 200 and len(zlib.compress(b)) / len(b) < 0.25


def regex_self_name(text: str) -> str:
    hits = [n for n, rx in NAME_RE.items() if rx.search(text)]
    return hits[0] if hits else "none"


def score_row(r: dict) -> dict:
    resp = r["response"]
    lid = lang_id(resp)
    return {"key": r["key"], "lang_detected": lid, "language_consistent": lid == r["prompt_lang"],
            "R_lex": r_lex(resp, r["prompt_lang"], lid), "empty": len(re.sub(r"\s", "", resp)) < 5,
            "repetitive": repetitive(resp), "malformed": bool(r.get("template_leak")) or "<start_of_turn>" in resp,
            "truncated": not r.get("hit_eos", True), "regex_self_name": regex_self_name(resp)}


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True, choices=["dev", "final"])
    args = ap.parse_args()
    setup_logging(f"scorers_{args.split}")
    d = OUT_DEV if args.split == "dev" else OUT_FINAL
    if args.split == "final":
        guard_final("scorers.py FINAL")
    rows = []
    for p in sorted(d.glob("gen_*.jsonl")):
        rows += read_jsonl(p)
    out = [score_row(r) for r in rows]
    write_jsonl(d / "scores.jsonl", out)
    logger.info(f"scored {len(out)} rows; lang-consistent {sum(o['language_consistent'] for o in out)}")


if __name__ == "__main__":
    main()
