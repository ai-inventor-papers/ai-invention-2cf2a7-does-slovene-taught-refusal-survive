#!/usr/bin/env python3
"""Entry point for the iter-3 C-LAG confirmation artifact.

Runs the pipeline stages in order; every stage is resumable and skips work already on disk, so re-running after an
interruption continues where it stopped. GPU stages are run one model at a time (one 23 GB L4).

  preflight -> items -> calibrate -> freeze -> [GPU: gemma_it, gams3_it, public] -> [GPU: judges]
            -> table -> adjudication sample -> analysis -> audit -> report -> figures -> method_out.json

Usage:
  uv run method.py                      # CPU stages + analysis chain (assumes GPU stages already ran)
  uv run method.py --stages all         # everything, including the GPU blocks (hours)
  uv run method.py --stages analysis    # rebuild the table, statistics, audit, report, figures and outputs
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from loguru import logger

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
PY = str(ROOT / ".venv/bin/python")

CPU_PRE = [("preflight", ["preflight.py"]), ("items", ["build_items.py"]), ("calibrate", ["calibrate.py"])]
GPU = [("gen_gemma", ["gen.py", "--model", "gemma_it", "--phases", "final,batchcheck,bele"]),
       ("gen_gams", ["gen.py", "--model", "gams3_it", "--phases", "mini,regen,final,batchcheck,bele"]),
       ("gen_public", ["gen.py", "--model", "pew_heretic", "--phases", "public,bele"]),
       ("judge_primary", ["judge_local.py", "--judge", "qwen3_14b", "--mode", "gate,retest,final"]),
       ("judge_second", ["judge_local.py", "--judge", "mistral24b", "--mode", "gate,final"])]
ANALYSIS = [("table", ["build_table.py"]), ("adjudication", ["adjudication.py", "--make"]),
            ("analysis", ["analysis.py"]), ("audit", ["rederive.py"]), ("report", ["make_report.py"]),
            ("figures", ["figures.py"]), ("outputs", ["make_outputs.py"])]


def run(name: str, cmd: list[str]) -> int:
    t0 = time.time()
    logger.info(f"=== {name}: {' '.join(cmd)}")
    r = subprocess.run([PY] + cmd, cwd=SRC, env={**os.environ, "OMP_NUM_THREADS": "4", "OPENBLAS_NUM_THREADS": "4"})
    logger.info(f"=== {name} finished rc={r.returncode} in {time.time() - t0:.0f}s")
    return r.returncode


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="analysis", choices=["all", "pre", "gpu", "analysis"])
    ap.add_argument("--stop-on-error", action="store_true")
    a = ap.parse_args()
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
    logger.add(str(ROOT / "logs/method.log"), rotation="30 MB", level="DEBUG")
    plan: list = []
    if a.stages in ("all", "pre"):
        plan += CPU_PRE
        plan += [("freeze", ["freeze.py", "--curve_n", "200", "--hardsafe50_n", "273", "--hardsafe100_n", "50",
                             "--l3_refuseu_n", "400", "--l3_hard_n", "100", "--public", "pew_heretic",
                             "--regen_gemma", "0", "--regen_gams", "0"])]
    if a.stages in ("all", "gpu"):
        plan += GPU
    if a.stages in ("all", "analysis"):
        plan += ANALYSIS
    rc_all = 0
    for name, cmd in plan:
        rc = run(name, cmd)
        rc_all |= rc
        if rc and a.stop_on_error:
            sys.exit(rc)
    logger.info(f"pipeline done (combined rc={rc_all}); see results/RESULTS_tables.md and RESULTS.md")


if __name__ == "__main__":
    main()
