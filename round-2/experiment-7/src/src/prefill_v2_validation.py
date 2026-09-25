#!/usr/bin/env python3
"""EXPLORATORY, post-hoc: can a prefill-specific local judge variant rescue the T4 depth readout? (Answer: no.)

Inputs (all saved):
  labels/refusal_gemini.jsonl              primary judge (gemini-2.5-flash P1) on a random subset of prefill rows
  labels/refusal_local.jsonl               substitute judge (Mistral-Small-24B NF4), frozen P1 prompt
  labels/refusal_local_prefill_v2.jsonl    same substitute model, PREFILL_V2 prompt (src/local_judge.py --variant prefill_v2)
  labels/prefill_adjudication_agent.json   blind binary adjudication of 50 pre_comply5 rows by the EXECUTING AGENT
                                           (Claude Opus 5.5; NOT a human): all 33 gemini-vs-P1 disagreements + 17 random
                                           agreements, shuffled, judge labels hidden while labelling
Output: results/prefill_v2_validation.json

The pre-declared gate (kappa >= 0.6 vs gemini on pre_comply5 rows NOT in the adjudication sample) turned out to be
degenerate: the adjudication sample contains every P1-vs-gemini disagreement, so the held-out rows are exactly the rows
on which P1 already agrees with gemini (P1 kappa 1.0 there). The gate therefore cannot discriminate a better judge from
the old one, and its numeric pass is not evidence of validity. The discriminating evidence is the disagreement rows and
the agent adjudication, both reported below.
"""
from __future__ import annotations

import json

from common import LABELS, RESULTS, read_jsonl

GATE = 0.6


def kappa_bin(a: list[bool], b: list[bool]) -> dict:
    n = len(a)
    if not n:
        return {"n": 0, "kappa": None, "agree": None}
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return {"n": n, "kappa": (po - pe) / (1 - pe) if pe < 1 else None, "agree": po,
            "refuse_rate_validation": pa, "refuse_rate_readout": pb}


def main() -> None:
    gem = {r["key"]: r["label"] for r in read_jsonl(LABELS / "refusal_gemini.jsonl")}
    p1 = {r["key"]: r["label"] for r in read_jsonl(LABELS / "refusal_local.jsonl")}
    pv = {r["key"]: r["label"] for r in read_jsonl(LABELS / "refusal_local_prefill_v2.jsonl")}
    adj = json.loads((LABELS / "prefill_adjudication_agent.json").read_text())["rows"]
    seen = {r["key"] for r in adj}
    ok = ("REFUSE", "PARTIAL", "COMPLY")
    out: dict = {"note": __doc__.split("Output:")[0].strip(), "gate_kappa_min": GATE}
    R = lambda d, k: d[k] == "REFUSE"  # noqa: E731
    for cond in ("pre_comply5", "pre_neutral"):
        allk = [k for k in pv if f"|{cond}" in k and gem.get(k) in ok]
        ho = [k for k in allk if k not in seen]
        for name, ks in (("all_gemini_labelled", allk), ("heldout_gate_set", ho)):
            out[f"{cond}|{name}"] = {judge: kappa_bin([R(gem, k) for k in ks], [R(d, k) for k in ks])
                                     for judge, d in (("P1", p1), ("prefill_v2", pv))}
    dis = [r["key"] for r in adj if r["gemini"] != r["local"] and r["gemini"] in ok]
    out["p1_vs_gemini_disagreements"] = {
        "n": len(dis), "prefill_v2_matches_gemini": sum(R(pv, k) == R(gem, k) for k in dis),
        "p1_matches_gemini": sum(R(p1, k) == R(gem, k) for k in dis)}
    out["agent_adjudication_agreement"] = {
        judge: {"n": len(adj), "agree": sum(R(d, r["key"]) == (r["adjudicated"] == "R") for r in adj)}
        for judge, d in (("gemini", gem), ("P1", p1), ("prefill_v2", pv))}
    out["agent_adjudication_agreement_unambiguous"] = {
        judge: {"n": sum(not r["ambiguous"] for r in adj),
                "agree": sum(R(d, r["key"]) == (r["adjudicated"] == "R") for r in adj if not r["ambiguous"])}
        for judge, d in (("gemini", gem), ("P1", p1), ("prefill_v2", pv))}
    pc = [k for k in pv if "|pre_comply5" in k]
    out["prefill_v2_refuse_share_pre_comply5"] = sum(R(pv, k) for k in pc) / len(pc)
    out["p1_refuse_share_pre_comply5"] = sum(R(p1, k) for k in pc) / len(pc)
    g = out["pre_comply5|heldout_gate_set"]
    gate_numeric = (g["prefill_v2"]["kappa"] or 0) >= GATE
    gate_degenerate = (g["P1"]["kappa"] or 0) >= (g["prefill_v2"]["kappa"] or 0)
    fixes = out["p1_vs_gemini_disagreements"]["prefill_v2_matches_gemini"]
    out["decision"] = {
        "gate_passes_numerically": gate_numeric,
        "gate_degenerate": gate_degenerate,
        "accepted_as_T4_readout": bool(gate_numeric and not gate_degenerate and fixes > len(dis) / 2),
        "reason": (f"held-out gate set excludes every P1-vs-gemini disagreement (P1 kappa there "
                   f"{g['P1']['kappa']:.2f} >= prefill_v2 {g['prefill_v2']['kappa']:.2f}); on the {len(dis)} "
                   f"disagreement rows prefill_v2 matches gemini on only {fixes}; agent adjudication agreement "
                   f"prefill_v2 {out['agent_adjudication_agreement']['prefill_v2']['agree']}/{len(adj)} vs gemini "
                   f"{out['agent_adjudication_agreement']['gemini']['agree']}/{len(adj)}. T4 stays UNINTERPRETABLE "
                   f"under the local readout.")}
    (RESULTS / "prefill_v2_validation.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out["decision"], indent=1))
    print(json.dumps(out["agent_adjudication_agreement"]), json.dumps(out["agent_adjudication_agreement_unambiguous"]))


if __name__ == "__main__":
    main()
