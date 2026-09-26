#!/usr/bin/env python3
"""Pre-registered LLM judge: google/gemini-2.5-flash via OpenRouter (temperature 0, reasoning disabled, JSON output),
through the resumable cost ledger results/judge_ledger.jsonl (soft cap $6, hard cap $9.5).
Selection: ALL responses of SCORE cells C0-C3 in EN and SL (both models) -> judge-R robustness readout and per-cell
kappa; 150-response random samples (seed 20260923; minority lexicon class topped up to 20) of C4/C5 cells and of the
SL-MT cells; all manipulation-check ID-CHECK responses (identity judge); 50/cell of harmless side-effect cells.
Writes results/judge_labels.jsonl. Safe to re-run as more item files appear (only new responses are called)."""
from __future__ import annotations

import json

from loguru import logger

from common import RES, setup_logging
from judge_local import build_jobs, messages, prompt_lookup
from llm import MODEL, call_many, key_for, parse_json, spent


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("judge")
    jobs = build_jobs(full_langs=("en", "sl"))
    look = prompt_lookup()
    calls, seen = [], set()
    for j in jobs:
        j["key"] = key_for(MODEL, j["task"], j.get("prompt_sha1", j.get("prompt", "")), j["response"])
        if j["key"] not in seen:
            seen.add(j["key"]); calls.append((j["key"], messages(j, look)))
    est = len(calls) * 1.6e-4
    logger.info(f"{len(jobs)} judge jobs ({len(calls)} unique); upper-bound estimate ${est:.2f} if none cached; spent ${spent():.3f}")
    res = call_many(calls, "judge", max_tokens=60, conc=16)
    # second pass for failed / truncated / unparsable outputs: new ledger key, larger max_tokens
    bad = [(k, m) for k, m in calls if not (res.get(k) and parse_json(res[k]["out"]))]
    if bad:
        logger.info(f"retrying {len(bad)} failed/unparsed judge calls with max_tokens=300")
        res2 = call_many([(key_for(k, "retry2"), m) for k, m in bad], "judge_retry", max_tokens=300, conc=8)
        for k, _ in bad:
            r2 = res2.get(key_for(k, "retry2"))
            if r2 and parse_json(r2["out"]):
                res[k] = r2
        # gemini-specific errors (safety block / empty choices): pre-registered F8 second family for these few items
        for fb in ["openai/gpt-4.1-mini", "mistralai/mistral-small-3.2-24b-instruct"]:
            bad = [(k, m) for k, m in bad if not (res.get(k) and parse_json(res[k]["out"]))]
            if not bad:
                break
            logger.info(f"{len(bad)} still unlabelled -> fallback judge {fb}")
            tag = "fallback_gpt41mini" if "gpt" in fb else "fallback_mistral"
            res3 = call_many([(key_for(k, tag), m) for k, m in bad], "judge_fallback", max_tokens=120, conc=8, model=fb)
            for k, _ in bad:
                r3 = res3.get(key_for(k, tag))
                if r3 and parse_json(r3["out"]):
                    res[k] = dict(r3, fallback_model=fb)
    out, n_unparsed = [], 0
    for j in jobs:
        r = res.get(j["key"])
        d = parse_json(r["out"]) if r else None
        jj = {k: v for k, v in j.items() if k != "response"}
        jj["judge_model"] = (r or {}).get("fallback_model", MODEL)
        if j["task"] == "refusal":
            lab = str((d or {}).get("label", "")).lower()
            jj.update({"judge_label": lab if lab in ("refuse", "comply", "partial", "degenerate") else None,
                       "judge_language": (d or {}).get("language"), "judge_degenerate": (d or {}).get("degenerate")})
            n_unparsed += jj["judge_label"] is None
        else:
            jj.update({"judge_self_name": (d or {}).get("self_name"), "judge_mentions_slovenia": (d or {}).get("mentions_slovenia")})
        out.append(jj)
    (RES / "judge_labels.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out))
    logger.info(f"wrote {len(out)} labels; refusal unlabelled={n_unparsed}; total spent ${spent():.3f}")


if __name__ == "__main__":
    main()
