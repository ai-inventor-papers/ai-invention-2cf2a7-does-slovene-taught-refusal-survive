#!/usr/bin/env bash
# Sequential GPU queue (one model on the GPU at a time). PID-based waits only; every job is resumable.
set -u
cd "$(dirname "$0")/src"
PY=../.venv/bin/python
while kill -0 "$(cat ../logs/gpu_gemma.pid)" 2>/dev/null; do sleep 20; done
AII_SKIP_LADDER=1 $PY gen.py --model gams3_it --phases mini,regen,final,batchcheck,bele --bs 64 > ../logs/gpu_gams.out 2>&1
$PY gen.py --model gemma_it --phases final --bs 64 > ../logs/gpu_gemma_topup.out 2>&1
$PY gen.py --model pew_heretic --phases public,bele --bs 64 > ../logs/gpu_pew.out 2>&1
$PY judge_local.py --judge qwen3_14b --mode gate,retest,final --bs 16 > ../logs/judge_q.out 2>&1
$PY judge_local.py --judge mistral24b --mode gate,final --bs 8 > ../logs/judge_m.out 2>&1
echo QUEUE_DONE > ../logs/queue_done.flag
