"""Label resolution from the judge ledgers (shared by set_m.py and analysis.py; audit.py re-implements it).

PRIMARY readout (protocol_amendment_5.json): the LOCAL open-weight judge, results/judge/local_ledger.jsonl.
The API judges are kept as comparison readouts, because the run's OpenRouter budget was exhausted mid-study and
because gemini-2.5-flash failed its validation (binary-R kappa 0.17 vs gpt-4.1 on DEV, 0.19 vs the blind adjudication;
it calls prefilled compliance 'REFUSE'). NOTE: the local judge did NOT pass the amendment-5 acceptance gates either
(results/judge/validation.json), so every judged number in this artifact is a FLAGGED readout and the judge-free
representation readout is the primary result. See RESULTS.md.
"""
from __future__ import annotations

from common import RESULTS, read_jsonl

JD = RESULTS / "judge"


LOCAL_JUDGE = "Qwen/Qwen3-8B"  # judge of record (amendment 7): results/judge/local8b.jsonl, bf16, prefill-only label scoring
LOCAL_LEDGER = JD / "local8b.jsonl"
SECOND_LOCAL = ("Qwen/Qwen3-14B", JD / "local_ledger.jsonl")  # second local reader (NF4), kept for per-cell reliability


def _read(path, src, only_model: str | None = None):
    out = {}
    for r in read_jsonl(path):
        if only_model and r.get("judge_model") != only_model:
            continue
        if r.get("ok"):
            out[r["key"]] = {"label": r["label"], "late_refusal": r.get("late_refusal"),
                             "off_language": r.get("off_language"), "src": src}
    return out


def load_labels(primary: str = "local") -> tuple[dict, dict, dict]:
    """returns (final_label, second_reader, third_reader).
    final = local Qwen3-8B judge (no cross-judge fallback).
    second = gemini-2.5-flash (prompt v2), third = openai/gpt-4.1 (DEV rows + the adjudication sample)."""
    loc = _read(LOCAL_LEDGER, "local", only_model=LOCAL_JUDGE)
    gem = _read(JD / "gemini_ledger.jsonl", "gemini")
    gpt = _read(JD / "gpt41_ledger.jsonl", "gpt41")
    gpt.update(_read(JD / "select" / "openai__gpt-4.1.jsonl", "gpt41"))
    order = {"local": (loc, gem, gpt), "gemini": (gem, loc, gpt), "gpt41": (gpt, loc, gem)}[primary]
    # NO cross-judge fallback: mixing readouts inside a cell would mix two different measurement instruments, and the
    # instruments demonstrably disagree (validation.json). A row without a primary label is simply unlabelled.
    final = dict(order[0])
    n_fb = 0
    final["_meta"] = {"primary": primary, "n_local": len(loc), "n_gemini": len(gem), "n_gpt41": len(gpt),
                      "n_fallback": n_fb, "n_total": len(final) - 1,
                      "note": "primary = local Qwen3-8B bf16 judge (amendment 7), prompt v2, prefill-only label scoring; FLAGGED (failed amendment-5 gates)"}
    return final, order[1], order[2]
