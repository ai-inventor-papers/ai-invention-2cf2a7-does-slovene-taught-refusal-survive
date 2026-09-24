#!/usr/bin/env python3
"""Entry point: does a Slovene caution direction cause Gemma-3's Slovene refusal lag? (iter-3 dir3)

Runs the full pipeline in order (each stage is resumable; completed outputs are never regenerated):
  data      src/prep_data.py                      inputs check, Dolly sets, NLLB SL-MT/EN-BT, splits, overlap, manifest
  pass1 M   src/gpu_block.py --phases smoke,acts,geom,devgen       (per model: load, T1 smoke, activations, directions,
                                                                     geometry, every DEV generation)
  devjudge  src/judge_local.py --judge qwen [--calib] --what dev   (local judge; calibration vs archived gemini)
  decide    src/dev_decide.py --model M              L*, alpha-grid multiplier, lambda*
  pass2 M   src/gpu_block.py --phases dev,freeze,induce,addon,rq4  (band rule -> protocol freeze + git commit -> TEST)
  judge     src/judge_local.py --judge qwen --what test; --judge mistral --what second (+ calib)
  adjud     src/adjudicate.py --sample   (then the blind labels are written to results/adjudication_blind.jsonl)
  rq4       src/rq4.py --model M
  analysis  src/analysis.py; src/audit.py; src/make_figs.py; src/make_outputs.py

Baselines / controls implemented side by side in the same code path: the unedited model (O), the edit alone (E0),
the own-EN refusal direction (positive control for induction), the language-identity direction (rival), and
centred-variance-matched random orthogonal directions (induction + add-on); the M-a add-on (full SL direction).

Usage: .venv/bin/python method.py --stage all | data | gemma | gams | judge | analysis
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent
PY = str(WS / ".venv/bin/python")


def run(args: list[str]) -> None:
    print(">>", " ".join(args), flush=True)
    subprocess.run([PY, *args], cwd=WS, check=True)


def model_block(m: str, calib: bool) -> None:
    run(["src/gpu_block.py", "--model", m, "--phases", "smoke,acts,geom,devgen"])
    run(["src/judge_local.py", "--judge", "qwen", "--model", m, "--what", "dev", *(["--calib"] if calib else [])])
    run(["src/dev_decide.py", "--model", m])
    run(["src/gpu_block.py", "--model", m, "--phases", "dev,freeze,induce,addon,rq4"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all", choices=["all", "data", "gemma", "gams", "judge", "analysis"])
    a = ap.parse_args()
    if a.stage in ("all", "data"):
        run(["src/prep_data.py"])
    if a.stage in ("all", "gemma"):
        model_block("gemma_it", calib=True)
    if a.stage in ("all", "gams"):
        model_block("gams3_it", calib=False)
    if a.stage in ("all", "judge"):
        for m in ("gemma_it", "gams3_it"):
            run(["src/judge_local.py", "--judge", "qwen", "--model", m, "--what", "test"])
        run(["src/judge_local.py", "--judge", "mistral", "--calib", "--what", "second"])
        run(["src/adjudicate.py", "--sample"])
    if a.stage in ("all", "analysis"):
        for m in ("gemma_it", "gams3_it"):
            run(["src/rq4.py", "--model", m])
        run(["src/analysis.py"])
        run(["src/audit.py"])
        run(["src/make_figs.py"])
        run(["src/make_outputs.py"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
