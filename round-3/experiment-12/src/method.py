#!/usr/bin/env python3
"""RQ3 capability control — single entry point.

Method under test: the English-objective Heretic abliteration edit (iter-1 selected LoRA, lambda 1, plus lambda-scaled
0.5/1.5/2.0) applied to GaMS3-12B-Instruct and Gemma-3-12B-IT (NF4).
Baselines/controls: (i) the ORIGINAL model (identity LoRA) on identical items, (ii) a norm-matched RANDOM-direction
edit built through Heretic's own abliterate() with the SAME parameters (only the directions random; 5 seeds for KL,
seed 1 for utility), (iii) the c=6 random edit (largest random perturbation, KL/BPB only).

Steps (each is its own resumable script under src/; this file only orchestrates them in order):
  1  src/prep_data.py      item sets (paired EN/SL utility, Belebele EN/SL/HU, Dolly harmless, FLORES passages, overlap audit)
  1c src/prep_mt.py        NLLB-200 MT of the harmless set (SL-MT, EN-BT, HU-MT) + chrF gate
  2  src/write_protocol.py protocol freeze (sha256 + git commit) BEFORE any edited-condition forward pass
  3-4 src/gpu_block.py     per model: edits + manipulation check, lm-eval utility, KL, generations, Belebele, BPB, scorer-2, chat
  6  src/analyze.py        headroom-normalised H, macros, A, I, random-adjusted, McNemar/Holm, gates, KL ratios, BPB, fluency
  9  src/audit.py          independent recomputation (path B) + label-permutation placebos
  8  src/assemble_p0.py    P0 table (RQ1 reused, RQ2 from artifact 4 if present, RQ3 here)
  10 src/build_outputs.py  method_out.json, gates.json, RESULTS.md ; src/make_figs.py figures

Usage:  .venv/bin/python method.py [--steps prep,mt,protocol,gams,gemma,analyze] [--minutes-per-model 100]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from loguru import logger

WS = Path(__file__).resolve().parent
PY = str(WS / ".venv" / "bin" / "python")
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add(str(WS / "logs" / "method.log"), rotation="30 MB", level="DEBUG")

GPU_STAGES = "util,kl,gen,belebele,bpb,scorer2,chat"


def run(args: list[str]) -> None:
    logger.info("RUN " + " ".join(args))
    t = time.time()
    r = subprocess.run([PY] + args, cwd=WS)
    logger.info(f"exit {r.returncode} after {time.time() - t:.0f}s")
    if r.returncode != 0:
        raise RuntimeError(f"step failed: {args}")


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", default="prep,mt,protocol,gams,gemma,analyze")
    ap.add_argument("--minutes-per-model", type=float, default=100.0)
    ap.add_argument("--n-gen", type=int, default=100)
    a = ap.parse_args()
    steps = a.steps.split(",")
    if "prep" in steps:
        run(["src/prep_data.py"])
    if "mt" in steps:
        run(["src/prep_mt.py"])
    if "protocol" in steps:
        run(["src/write_protocol.py"])
    for m, key in (("gams3_it", "gams"), ("gemma_it", "gemma")):  # GaMS first (artifact 2's Gemma selection gets more time)
        if key in steps:
            dl = int(time.time() + a.minutes_per_model * 60)
            run(["src/gpu_block.py", "--model", m, "--stages", "pilot," + GPU_STAGES, "--n-gen", str(a.n_gen),
                 "--n-gen-lambda", "50", "--util-bs", "8",
                 "--lambda-conds", "orig,E_iter1,E_iter1_l2.0,E_iter1_l1.5,E_iter1_l0.5", "--deadline-epoch", str(dl)])
    if "analyze" in steps:
        for s in ("src/analyze.py", "src/audit.py", "src/assemble_p0.py", "src/build_outputs.py", "src/make_figs.py"):
            run([s])


if __name__ == "__main__":
    main()
