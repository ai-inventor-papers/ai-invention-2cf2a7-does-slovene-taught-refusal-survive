#!/usr/bin/env python3
"""Write the artifact struct-out JSON."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

summary = (
    "Mechanism experiment (iter-4, dir3) locating where a residual refusal 'language lag' lives after an "
    "English-objective abliteration edit. It reuses exp9's selected Heretic LoRA (rank 3, o_proj+down_proj) applied as "
    "lambda-scaled bf16 forward hooks (lambda=0 bit-identical to base, max|dlogit|=0 asserted) on NF4 "
    "Gemma-3-12B-IT@96b6f1ec and GaMS3-12B-Instruct@1d0b27af. Design: a fully crossed input-language x "
    "forced-output-language grid over English/Slovene/Hungarian (9 cells; a one-line output-language instruction in the "
    "input language, held constant across all cells), each model scored at lambda 0 and two DEV-chosen doses that "
    "bracket English-to-English refusal at 50 percent. Items: 200 external harmful prompts from standard safety "
    "benchmarks (HarmBench/StrongREJECT/JBB, loaded from the authors' canonical CSVs because the HF mirrors are gated), "
    "deduplicated (exact + 8-gram) against RefusEU, the edit's own optimisation sets and every earlier probe, hash-split "
    "to a held-out half, plus 100 benign twins (JBB benign items + LLM-written twins, each machine- and executor-vetted "
    "for harmlessness). Baselines in the same pipeline: the unedited model, a norm-matched random-direction edit (with "
    "first-token KL collateral), the sibling GaMS3 model (per-cell cross-model contrast), one public English-abliterated "
    "checkpoint (descriptive), and a machine-translation-noise control. Estimand: at matched English-to-English refusal "
    "50 percent, the edit-induced lag is decomposed into an output-side share and an input-side share, with a 2000-draw "
    "fully-paired item bootstrap, 5000-draw within-item permutation placebos, signal-detection d'/c per cell, a secondary "
    "GEE, Rogan-Gladen and PPI++ judge-error corrections, and a fully independent pandas re-derivation of every headline "
    "(80/80 checks below 1e-6; placebos centre at zero). "
    "HEADLINE for Gemma-3-12B-IT: the residual Slovene refusal tracks the REPLY language the model is forced to write, "
    "not the language of the prompt. The output-side share is clearly positive (about +1.14 logit, 95% CI [0.60, 1.56]) "
    "while the input-side share is near zero or negative (about -0.60, CI [-1.02, -0.18]); the within-item input/output "
    "label-swap placebo centres at zero (p about 0). This is corroborated judge-independently by a blind author-model "
    "adjudication (labelled NOT human) that reads the actual generated text: refusal is markedly higher when the reply "
    "is non-English (~0.50) than when it is English (~0.33), and a non-English prompt answered in English refuses no "
    "more than English-to-English, which rules out the rival explanation that the automated judge merely mis-scores "
    "Slovene text. The lag is Slovene-specific (Slovene reply > Hungarian reply). "
    "Honest caveats: the pre-registered paid judges were blocked mid-run by a shared-key daily limit, so the primary "
    "readout is a local classifier distilled from archived judge labels (held-out kappa 0.84) that over-calls refusal "
    "(specificity ~0.60); the Rogan-Gladen correction is therefore numerically degenerate and is flagged, PPI++ keeps "
    "the sign but widens intervals, so the finding does NOT reach the pre-registered multi-readout 'robust' bar and is "
    "reported as strong exploratory evidence supported by the raw readout plus the judge-independent gold adjudication. "
    "GaMS3 is the secondary sibling arm (ESTIMATE; its dose bracket is flagged narrow). All decision rules, doses and "
    "amendments (A0-A6) were frozen and git-committed before the corresponding generation. Downstream: method_out.json "
    "holds one row per generation (input=user turn, output=response, metadata incl. model, input/output language, dose, "
    "detected language, judge label, adjudication, ASR, translation); results/analysis.json holds every statistic with "
    "CI/MDE/verdict; RESULTS.md and results/RESULTS_tables.md are generated from that JSON with no hand-typed numbers."
)

obj = {
    "title": "Does Slovene refusal follow the prompt or the reply?",
    "layman_summary": (
        "Tests whether a partly-unlocked Slovene/English AI model's leftover safety refusals depend on the language it "
        "is forced to answer in or the language of the question, and finds they track the answer language."
    ),
    "summary": summary,
    "out_expected_files": {
        "script": "method.py",
        "full_output": "method_out.json",
        "mini_output": "mini_method_out.json",
        "preview_output": "preview_method_out.json",
        "reproducibility": "reproducibility.md",
    },
    "upload_ignore_regexes": [
        "(^|/)\\.venv/",
        "(^|/)judge_model/",
        "(^|/)__pycache__/",
        "(^|/)\\.pytest_cache/",
        "(^|/)results/labels/cache\\.jsonl$",
    ],
}
assert 80 <= len(obj["layman_summary"]) <= 250, len(obj["layman_summary"])
assert 500 <= len(obj["summary"]) <= 5000, len(obj["summary"])
assert 12 <= len(obj["title"]) <= 90
(ROOT / ".terminal_claude_agent_struct_out.json").write_text(json.dumps(obj, indent=2))
print("wrote struct-out; title", len(obj["title"]), "layman", len(obj["layman_summary"]), "summary", len(obj["summary"]))
