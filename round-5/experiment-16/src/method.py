#!/usr/bin/env python3
"""Entry point for the iter-5 C-OUT confirmation (exp16). Runs the stage scripts in src/ in the order actually used;
every stage is resumable (row keys, paid cache, committed addenda), so re-running a finished stage is a no-op.

  uv run method.py --stages items,freeze,gpu,paid,analysis,rederive,figures,outputs,tests

Stages:
  items     S1 body construction, dedup re-check, sentence-split NLLB arms (src/items.py)
  freeze    S2 protocol.yaml + sha256 + git commit (src/freeze.py; refuses to overwrite a frozen protocol)
  gpu       S3-S7 unattended GPU chain (run_chain.sh: Gemma -> TTJ -> GaMS3 -> TTJ -> C-EXT -> TTJ -> local scoring)
  paid      S8/S9 paid labelling in the pre-registered order (src/paid.py; hard stop in src/judge_paid.py)
  analysis  S10 estimators, placebos, SDT, SB, D1-D8 (src/analysis.py)
  rederive  S11 independent pandas re-derivation (src/rederive.py)
  figures / outputs / tests
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = str(ROOT / ".venv" / "bin" / "python") if (ROOT / ".venv" / "bin" / "python").exists() else sys.executable
PAID_ORDER = "smoke,pb_dec,adj,pb,ben,pc,pd,drift"  # amendment A1 order; each mode is cached / resumable


def run(cmd: list[str], cwd: Path, env: dict | None = None) -> None:
    print(f"$ {' '.join(cmd)}", flush=True)
    r = subprocess.run(cmd, cwd=cwd, env={**os.environ, **(env or {})})
    if r.returncode != 0:
        raise SystemExit(f"stage failed ({r.returncode}): {' '.join(cmd)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default="analysis,rederive,figures,outputs")
    ap.add_argument("--paid_modes", default=PAID_ORDER)
    a = ap.parse_args()
    src = ROOT / "src"
    for st in a.stages.split(","):
        if st == "items":
            run([PY, "items.py"], src)
        elif st == "freeze":
            run([PY, "freeze.py"], src)
        elif st == "gpu":
            run(["bash", str(ROOT / "run_chain.sh")], ROOT, {"AII_TOKEN_BUDGET": os.environ.get("AII_TOKEN_BUDGET", "15000")})
        elif st == "paid":
            run([PY, "paid.py", "--mode", a.paid_modes], src, {"AII_PC_TRIM": "1"})
        elif st == "analysis":
            run([PY, "analysis.py"], src)
        elif st == "rederive":
            run([PY, "rederive.py"], src)
        elif st == "figures":
            run([PY, "figures.py"], src)
        elif st == "outputs":
            run([PY, "make_outputs.py"], src)
        elif st == "tests":
            run([PY, "-m", "pytest", "-q", "tests/"], ROOT)
        else:
            raise SystemExit(f"unknown stage {st}")


if __name__ == "__main__":
    main()
