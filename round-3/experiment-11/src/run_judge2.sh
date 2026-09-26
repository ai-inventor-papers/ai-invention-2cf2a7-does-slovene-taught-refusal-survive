#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/src"
PY=../.venv/bin/python
$PY judge_local.py --judge qwen3_14b --mode gate,retest,final --bs 20 > ../logs/judge_q.out 2>&1
$PY gen.py --model pew_heretic --phases public --bs 48 > ../logs/gpu_pew.out 2>&1
$PY judge_local.py --judge qwen3_14b --mode final --bs 20 > ../logs/judge_q3.out 2>&1
$PY judge_local.py --judge mistral24b --mode gate,final --bs 10 > ../logs/judge_m.out 2>&1
echo QUEUE_DONE > ../logs/queue3_done.flag
