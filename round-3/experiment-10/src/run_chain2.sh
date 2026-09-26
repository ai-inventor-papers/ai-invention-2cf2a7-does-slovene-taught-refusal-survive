#!/usr/bin/env bash
# Remaining GPU chain after the Gemma TEST block (the executor restructured the chain here so that the GaMS surrogate
# labels and the blind-adjudication sample exist before the Qwen second-family pass).
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
step() { echo "=== $(date -u +%H:%M:%S) $*" >> logs/chain.log; "$@" >> logs/chain.log 2>&1; }
done_or() { if [ -f "$1" ]; then echo "=== skip ($1 exists): ${*:2}" >> logs/chain.log; else step "${@:2}"; fi; }
while [ ! -f results/gemma_it/gpu_done.json ]; do sleep 10; done
step $PY src/judge_surrogate.py --apply gemma_it test
done_or results/adjudication_key_gemma_it.jsonl $PY src/adjudicate.py --sample --model gemma_it
done_or results/gams3_it/gpu_done.json $PY src/gpu_block.py --model gams3_it --phases dev,freeze,induce,addon,rq4
step $PY src/judge_surrogate.py --apply gams3_it test
done_or results/adjudication_key_gams3_it.jsonl $PY src/adjudicate.py --sample --model gams3_it
step $PY src/judge_local.py --judge qwen --what second
echo "=== $(date -u +%H:%M:%S) CHAIN2 DONE" >> logs/chain.log
