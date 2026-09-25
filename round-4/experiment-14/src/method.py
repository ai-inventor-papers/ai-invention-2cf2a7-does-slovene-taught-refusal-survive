#!/usr/bin/env python3
"""Orchestrator for the iter-4 input x output language crossing artifact.

Method   : exp9's selected Heretic LoRA (English objective) applied as lambda-scaled bf16 hooks to NF4 Gemma-3-12B-IT
           and GaMS3-12B-Instruct, at lambda 0 and two DEV-chosen steps bracketing EN->EN refusal 50%, on a fully
           crossed 3x3 grid of input language x forced output language {EN, SL, HU}.
Baselines: unedited model (lambda 0); norm-matched random-direction edit at lambda_hi; the sibling model GaMS3 (G3);
           a public English-abliterated Gemma-3-12B-IT checkpoint (C-EXT); EN_orig vs EN_BT (MT noise).

Every stage is resumable (append-only JSONL keyed by row; paid calls cached in results/labels/cache.jsonl).
Usage:
  uv run method.py --stages prep        # preflight, pool, twins, items (GPU: NLLB), calibration, freeze
  uv run method.py --stages gemma       # MINI, DEV scan (amendment A1), KL, grid           [GPU]
  uv run method.py --stages gams        # same for GaMS3 (amendment A2)                     [GPU]
  uv run method.py --stages ext         # C-EXT public checkpoint                           [GPU]
  uv run method.py --stages judge       # J1 primary labels (local, amendment A4)             [GPU]
  uv run method.py --stages paid        # paid flash + gpt-4.1-mini labels if the key allows  [API]
  uv run method.py --stages ttj         # NLLB response translation + TTJ labels            [GPU + API]
  uv run method.py --stages asr         # StrongREJECT rubric on non-refused harmful rows    [API]
  uv run method.py --stages analysis    # table -> analysis -> audit -> figures -> method_out.json
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from loguru import logger

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
PY = sys.executable
ENV = {**os.environ, "HF_HUB_OFFLINE": os.environ.get("HF_HUB_OFFLINE", "1"), "AII_DEV_JUDGE": "j1"}

STAGES = {
    "prep": [["preflight.py"], ["build_pool.py"], ["twins.py"], ["build_items.py", "--mode", "items,aux"],
             ["calib.py"], ["freeze.py"]],
    # AII_DEV_JUDGE=j1 (amendment A4) is set in ENV below: the DEV lambda choice is judged by J1
    "gemma": [["gen.py", "--model", "gemma_it", "--phases", "mini,dev,kl,grid"]],
    "gams": [["gen.py", "--model", "gams3_it", "--phases", "mini,dev,kl,grid"]],
    "ext": [["gen.py", "--model", "pew_heretic", "--phases", "ext"]],
    "judge": [["judge_j1.py", "--mode", "calib,label", "--models", "gemma_it,gams3_it,pew_heretic"]],
    "paid": [["judge_worker.py", "--models", "gemma_it,gams3_it,pew_heretic", "--readouts", "primary,second"]],
    "ttj": [["build_items.py", "--mode", "ttj", "--models", "gemma_it,gams3_it,pew_heretic", "--only_edited"],
            ["judge_j1.py", "--mode", "label", "--models", "gemma_it,gams3_it,pew_heretic"]],
    "asr": [["asr.py"]],
    "analysis": [["build_table.py"], ["analysis.py"], ["rederive.py"], ["figures.py"], ["make_report.py"],
                 ["make_outputs.py"]],
}


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="analysis")
    a = ap.parse_args()
    order = list(STAGES) if a.stages == "all" else a.stages.split(",")
    for st in order:
        for cmd in STAGES[st]:
            logger.info(f"[{st}] {' '.join(cmd)}")
            r = subprocess.run([PY, *cmd], cwd=SRC, env=ENV)
            if r.returncode != 0:
                raise RuntimeError(f"stage {st} failed: {' '.join(cmd)} (exit {r.returncode})")


if __name__ == "__main__":
    main()
