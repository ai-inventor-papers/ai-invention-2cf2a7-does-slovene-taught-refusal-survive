#!/usr/bin/env bash
# Sequential GPU chain (single L4): each step resumable; stops at the first failure.
# DEV decisions are made with the gemini surrogate (flag files written after src/dev_decide.py --judge surrogate/gemini).
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
step() { echo "=== $(date -u +%H:%M:%S) $*" >> logs/chain.log; "$@" >> logs/chain.log 2>&1; }
done_or() { if [ -f "$1" ]; then echo "=== skip ($1 exists): ${*:2}" >> logs/chain.log; else step "${@:2}"; fi; }
waitf() { while [ ! -f "$1" ]; do sleep 5; done; }
[ -n "${WAIT_PID:-}" ] && while kill -0 "$WAIT_PID" 2>/dev/null; do sleep 5; done
done_or results/dev/gams3_it/devgen_done.json $PY src/gpu_block.py --model gams3_it --phases smoke,acts,geom,devgen
waitf results/dev/gemma_it/decisions_final.flag
done_or results/gemma_it/gpu_done.json $PY src/gpu_block.py --model gemma_it --phases dev,freeze,induce,addon,rq4
waitf results/dev/gams3_it/decisions_final.flag
done_or results/gams3_it/gpu_done.json $PY src/gpu_block.py --model gams3_it --phases dev,freeze,induce,addon,rq4
step $PY src/judge_local.py --judge qwen --what second
echo "=== $(date -u +%H:%M:%S) CHAIN DONE" >> logs/chain.log
