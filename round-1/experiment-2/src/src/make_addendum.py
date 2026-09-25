#!/usr/bin/env python3
"""D2: freeze m from the pooled lexicon R of the 100 CONSTRUCT pairs x EN/SL x both instruct models, BEFORE analyze.py
opens any SCORE file. Writes config/protocol_addendum.json + sha256, and records the post-freeze deviations declared
during execution (D13-D16) with their timestamps."""
from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    R = []
    for m in ["gemma", "gams"]:
        R += [json.loads(l)["R_lex"] for l in (ROOT / f"results/inst_{m}/r_construct100.jsonl").read_text().splitlines()]
    p0 = (sum(R) + 0.5) / (len(R) + 1)
    lg = lambda p: math.log(p / (1 - p))
    m = lg(p0 + 0.05) - lg(p0) if p0 <= 0.5 else lg(p0) - lg(p0 - 0.05)
    add = {"frozen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "p0_construct_pooled_hautus": p0, "n": len(R),
           "m_logodds_5pp": m,
           "post_freeze_deviations": {
               "D13": "KV-reuse s equivalence threshold: exact in fp32 (1e-4, smoke_test.json); bf16/NF4 path noise up to ~0.25 "
                      "nats on the 12B, so cache mode is kept unless |diff| > 0.5 (declared before any s was analysed).",
               "D14": "Induction grid extended by 3 lower log-steps (alpha/N_bar = 0.0197, 0.0130, 0.0086; k = -2,-3,-4) for every "
                      "direction, declared before any induction output: N_bar(L22) ~ 5e4 while the own refusal diff-of-means "
                      "norm is ~3.1e3 (0.06 N_bar). Residual norms are uniformly large (median ~ mean), not outlier-driven.",
               "D15": "4PL fitted on the rising limb only (alphas up to the peak of R); alpha50 = NR unless the empirical "
                      "non-degenerate peak R >= 0.5; model-free interpolated crossing co-reported. Reason: inverted-U curves "
                      "(off-manifold collapse at large alpha) that a monotone 4PL cannot represent. Declared after the Gemma "
                      "curves were seen and before the GaMS induction was analysed.",
               "D16": "gemini-2.5-flash judge (OpenRouter key restored mid-run) labels ALL SCORE-400 responses and ALL pt / own "
                      "pooled / lang-ID / random induction responses (not just 150-item kappa subsets): R_judge is reported "
                      "as a co-primary readout because the EN lexicon fails validation (kappa < 0.7).",
               "EXPLORATORY": "Base-model last-token format confound (harmful prompts end in '?'/'\"', harmless in '.'): "
                              "punctuation-matched d' (src/base_punct_check.py) and mean-pooled residuals (--pool mean) are "
                              "exploratory robustness checks, not part of the pre-registered rule."}}
    p = ROOT / "config/protocol_addendum.json"
    p.write_text(json.dumps(add, indent=1))
    (ROOT / "config/protocol_addendum.sha256").write_text(hashlib.sha256(p.read_bytes()).hexdigest() + "  config/protocol_addendum.json\n")
    print(json.dumps({k: v for k, v in add.items() if k != "post_freeze_deviations"}))


if __name__ == "__main__":
    main()
