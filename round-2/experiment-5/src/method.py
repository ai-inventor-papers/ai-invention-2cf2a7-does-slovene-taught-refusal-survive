#!/usr/bin/env python3
"""Entry point of the confirmation experiment (CONFIRM-SPEC v2): GaMS3-12B-Instruct (method) vs Gemma-3-12B-IT
(baseline/control) Slovene/English refusal on the RESERVED FINAL items of the iter-1 dataset artifact.

Pipeline (each stage is a module in src/, all resumable and idempotent):
  1 build_items.py   item manifests + fold asserts                         (CPU, $0)
  2 freeze.py        protocol.json sha256 + git commit BEFORE FINAL gen    (CPU)
  3 gen.py           per model: smoke, ladder, batch check, DEV, FINAL      (GPU, NF4, greedy, 160 tok)
  4 judge.py dev     gemini-2.5-flash (+gpt-4.1 30% / identity all)        (OpenRouter)
    addendum.py      DEV-only margins, ceiling, MDE -> commit (unlocks FINAL)
    judge_local.py   deviation D1: Qwen3-14B local third judge family (DEV, then FINAL after the addendum)
  5 judge.py final   gemini on all FINAL, gpt-4.1 on 15% + identity all    (OpenRouter, <= $9 cap)
    scorers.py       lexicon, language ID, degenerate flags, regex names   ($0)
  6-7 analysis.py    C1, C2 RefusEU DiD/D + sensitivities, HARD SDT, verdicts
    judge_lang_check.py  V5 SL->EN re-judge check (NLLB)
  8 audit.py         independent recomputation, placebos, integrity
  9 make_outputs.py  method_out.json + RESULTS.md ; figures.py
Usage: uv run method.py [--from STAGE] [--skip-gen]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
PY = str(ROOT / ".venv/bin/python") if (ROOT / ".venv/bin/python").exists() else sys.executable

STAGES = [
    ("items", ["build_items.py"]),
    ("freeze", ["freeze.py", "protocol"]),
    ("gen_gemma", ["gen.py", "--model", "gemma_it"]),
    ("gen_gams", ["gen.py", "--model", "gams3_it"]),
    ("judge_local_dev", ["judge_local.py", "--split", "dev"]),
    ("judge_dev", ["judge.py", "--split", "dev"]),
    ("scorers_dev", ["scorers.py", "--split", "dev"]),
    ("addendum", ["addendum.py"]),
    ("judge_final", ["judge.py", "--split", "final"]),
    ("judge_local_final", ["judge_local.py", "--split", "final"]),
    ("scorers_final", ["scorers.py", "--split", "final"]),
    ("analysis", ["analysis.py", "--split", "final"]),
    ("analysis_dev", ["analysis.py", "--split", "dev"]),
    ("dev_judge_compare", ["dev_judge_compare.py"]),
    ("judge_calibrated_dev", ["judge_calibrated.py", "--target", "dev"]),
    ("judge_calibrated_final", ["judge_calibrated.py", "--target", "final"]),
    ("judge_lang_check", ["judge_lang_check.py"]),
    ("spend", ["judge.py", "--split", "final", "--export_only"]),
    ("audit", ["audit.py"]),
    ("outputs", ["make_outputs.py"]),
    ("figures", ["figures.py"]),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", default="items", choices=[s for s, _ in STAGES])
    ap.add_argument("--skip-gen", action="store_true")
    args = ap.parse_args()
    names = [s for s, _ in STAGES]
    for name, cmd in STAGES[names.index(args.start):]:
        if args.skip_gen and name.startswith("gen_"):
            continue
        print(f"== {name}: {' '.join(cmd)}", flush=True)
        r = subprocess.run([PY, *cmd], cwd=SRC)
        if r.returncode != 0:
            if name == "judge_lang_check":
                print("V5 check failed (cut-able); continuing")
                continue
            sys.exit(f"stage {name} failed with exit code {r.returncode}")


if __name__ == "__main__":
    main()
