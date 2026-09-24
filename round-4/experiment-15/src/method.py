#!/usr/bin/env python3
"""Top-level entry point for the iter-4 dense-dose-ladder artifact.

The implementation lives in `src/` (one module per stage; see README.md). This driver ties the stages together and is
the file the pipeline records as `script`. Two uses:

    uv run method.py --stage all      # documents / runs the full pipeline in order (long; GPU)
    uv run method.py --stage analysis # re-run only the analysis + audit + figures + outputs from saved generations
    uv run method.py --smoke          # end-to-end on a 10-item synthetic slice (no GPU, no paid calls) -> /tmp check

The METHOD (proposed) and the BASELINE (comparison) are implemented side by side in ONE pipeline so nothing is a
confound:

  * METHOD  : an English-objective Heretic abliteration edit (`E_exp9`) applied to the Slovene-adapted
              GaMS3-12B-Instruct, scaled through a 13-step lambda ladder; the estimand is the Slovene-vs-English
              refusal-lag gap G3 (and its edit-induced component G3_edit) at matched English refusal.
  * BASELINE: (i) the unedited model (lambda = 0) on identical items and decoding; (ii) the SAME edit on the base
              family Gemma-3-12B-IT (the sibling control model that isolates Slovene adaptation); (iii) a
              norm-matched RANDOM-direction LoRA at matched edit size (the specificity control). All three run in the
              same `src/gen.py` code path as the method.

Run order (each stage is resumable; heavy stages run one model at a time):
  build_items -> judge tier -> gen (both models) -> local/paid labels -> ttj -> adjudication -> analysis
  -> rederive -> figures -> make_outputs.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
PY = str(ROOT / ".venv" / "bin" / "python")


def run(mod: str, *args: str) -> None:
    cmd = [PY, str(SRC / mod), *args]
    print(f"\n=== {' '.join(cmd)} ===", flush=True)
    subprocess.run(cmd, cwd=str(SRC), check=True)


def stage_all() -> None:
    run("preflight.py")
    run("build_items.py", "--stages", "pool,twins,mt")
    run("judge_paid.py", "tier")
    # generation + labelling is orchestrated by run_gen_all.sh (one model load at a time, J1 labels in-process)
    subprocess.run(["bash", str(ROOT / "run_gen_all.sh")], check=True)
    run("judge_local.py", "once", "--device", "cuda")
    run("ttj.py", "--judge", "local/j1")
    run("judge_local.py", "ttj", "--device", "cuda")
    for m in ("gemma_it", "gams3_it"):
        run("adjudicate.py", "draw", "--model", m, "--judge_short", "j1")
        print(f"  -> now adjudicate results/adjudication/blind_{m}.jsonl into author_labels.jsonl (blind), then continue")
    run("adjudicate.py", "unblind")
    stage_analysis()


def stage_analysis() -> None:
    run("analysis.py")
    run("rederive.py")
    run("figures.py")
    run("make_outputs.py")


def smoke() -> None:
    """Fast, offline end-to-end sanity check on synthetic labels (see the synthetic generator used in testing)."""
    run("../tests/smoke_pipeline.py") if (ROOT / "tests" / "smoke_pipeline.py").exists() else print(
        "smoke generator not present; run `uv run pytest -q tests` for the unit tests")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["all", "analysis"], default="analysis")
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    if a.smoke:
        smoke()
    elif a.stage == "all":
        stage_all()
    else:
        stage_analysis()


if __name__ == "__main__":
    main()
