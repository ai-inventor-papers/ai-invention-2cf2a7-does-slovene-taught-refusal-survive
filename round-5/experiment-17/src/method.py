#!/usr/bin/env python3
"""Top-level entry point for exp17: the frozen-core RQ2 experiment on RefusEU's own reserved natural prompts.

METHOD  = one English-only de-censoring edit (the saved iteration-3 Heretic LoRA, r = 3 on o_proj + down_proj, applied
          as a scaled forward hook at lambda 1.0, plus lambda_gate when the DEV manipulation check demands it).
BASELINE= the same model, same prompts, same decoding, with the hook disabled (lambda 0, asserted bit-identical to the
          unedited weights). Both conditions are generated in one pipeline, on identical prompts, so every edit
          contrast is paired and no implementation-level confound separates them.
CONTROLS= a norm-matched random direction (rand_1) at the same dose, and a 256-token regeneration subset.
READOUT = the RefusEU attack-success protocol run locally (Llama-Guard-3-8B + PolyGuard-Qwen, third guard adjudicating
          their disagreements), a StrongREJECT harmful-content score, two refusal flags, language consistency and
          degeneracy, with per-cell sensitivity/specificity from a blind author-model adjudication and Rogan-Gladen
          corrected rates.

This driver runs the stages in the order they were actually executed and is resumable: every stage skips work whose
row keys already exist. Stages (comma list, default all):

  preflight  inputs / hashes / model pins / OpenRouter check / disk
  items      build the FINAL + DEV item files, provenance, contamination audit
  tests      pytest (statistics, parsers, cache keys) - runs BEFORE any model load
  freeze     sha256-freeze and commit protocol.yaml (no FINAL row may be generated before this)
  gen        model session A for each model (hook checks, MINI, DEV dose grid, FINAL conditions, controls)
  guards     the three local guards, one in GPU memory at a time
  gate       the DEV dose gate per model (amendment A1) and the lambda_gate FINAL rows
  sr         the StrongREJECT fine-tuned evaluator on every row
  table      merge generations + readouts -> results/rows_final.jsonl
  frame      draw the blind adjudication frame (per model)
  analysis   statistics -> results/analysis.json (+ rq2_table.csv, judge_validity.json, cells_compliance.json)
  audit      the independent re-derivation of every headline
  outputs    figures, RESULTS.md, method_out.json

Usage:
  uv run method.py                      # everything, in order
  uv run method.py --stages analysis,audit,outputs
  uv run method.py --stages gen --model gams3_it
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
PY = str(ROOT / ".venv/bin/python")
MODELS = ("gemma_it", "gams3_it")
ALL = ["preflight", "items", "tests", "freeze", "gen", "guards", "gate", "sr", "table", "frame", "analysis", "audit",
       "outputs"]


def run(cmd: list[str], cwd: Path = SRC) -> int:
    print(f"\n=== {' '.join(cmd)}", flush=True)
    t0 = time.time()
    rc = subprocess.call(cmd, cwd=str(cwd))
    print(f"=== exit {rc} in {time.time() - t0:.0f}s", flush=True)
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stages", default=",".join(ALL))
    ap.add_argument("--model", default=None, help="restrict the gen/gate/frame stages to one model")
    ap.add_argument("--gate_pairs", type=int, default=650, help="FINAL pairs for the lambda_gate condition (plan cut 3)")
    a = ap.parse_args()
    stages = [s for s in a.stages.split(",") if s]
    models = (a.model,) if a.model else MODELS
    bad = [s for s in stages if s not in ALL]
    if bad:
        print(f"unknown stages: {bad}; known: {ALL}")
        return 2
    fail = 0
    for st in stages:
        if st == "preflight":
            fail |= run([PY, "preflight.py"])
        elif st == "items":
            fail |= run([PY, "build_items.py"])
        elif st == "tests":
            fail |= run([PY, "-m", "pytest", "-q", "-c", "pytest.ini"], cwd=ROOT)
        elif st == "freeze":
            fail |= run([PY, "freeze.py"])
        elif st == "gen":
            for m in models:
                fail |= run([PY, "gen.py", "--model", m])
                for g in ("polyguard", "llamaguard3", "qwen3guard"):
                    fail |= run([PY, "guards.py", "--guard", g])
        elif st == "guards":
            for g in ("polyguard", "llamaguard3", "qwen3guard"):
                fail |= run([PY, "guards.py", "--guard", g])
        elif st == "gate":
            for m in models:
                fail |= run([PY, "dev_gate.py", "--model", m, "--n_pairs", str(a.gate_pairs)])
                fail |= run([PY, "gen.py", "--model", m, "--stages", "gate"])
            for g in ("polyguard", "llamaguard3", "qwen3guard"):
                fail |= run([PY, "guards.py", "--guard", g])
        elif st == "sr":
            fail |= run([PY, "sr_ft.py"])
        elif st == "table":
            fail |= run([PY, "build_table.py"])
        elif st == "frame":
            for m in models:
                run([PY, "adjudicate_frame.py", "--model", m])  # exits non-zero once the frame is frozen
        elif st == "analysis":
            fail |= run([PY, "analysis.py"])
        elif st == "audit":
            fail |= run([PY, "rederive.py"])
        elif st == "outputs":
            for s2 in ("figures.py", "make_report.py", "make_outputs.py"):
                fail |= run([PY, s2])
            fail |= run([PY, "-m", "pytest", "-q", "-c", "pytest.ini"], cwd=ROOT)
    print(f"\nmethod.py finished; aggregate failure flag {fail}")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
