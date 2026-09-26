#!/usr/bin/env bash
# Idempotent post-generation pipeline: J1 -> J2 -> adjudication sample -> analysis -> audit -> figures -> method_out.json
set -u
cd "$(dirname "$0")"
PY=.venv/bin/python
$PY -u src/judge_distill.py predict --files results/gemma_it/gens.jsonl,results/gams3_it/gens.jsonl 2>&1 | tail -3
$PY -u src/judge_llm_hf.py calib 2>&1 | tail -3
$PY -u src/judge_llm_hf.py score --models gemma_it,gams3_it 2>&1 | tail -3
(cd src && ../$PY adjudicate.py 30 2>&1 | tail -1)
$PY method.py 2>&1 | tail -5
(cd src && ../$PY write_results.py && ../$PY write_readme_results.py)
