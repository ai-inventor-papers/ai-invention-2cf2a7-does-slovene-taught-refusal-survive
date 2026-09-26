#!/usr/bin/env bash
cd ../src
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
P=$(cat ../logs/chain2.pid); while kill -0 $P 2>/dev/null; do sleep 10; done
grep -q CHAIN_DONE ../logs/chain2.out || { echo "chain2 failed"; exit 1; }
[ -f ../protocol.sha256 ] || ../.venv/bin/python freeze.py > ../logs/freeze.out 2>&1 || { echo FREEZE_FAIL; exit 1; }
../.venv/bin/python gpu_run.py --model gemma --stage score --slmt --budget 10000 --max-bs 40 > ../logs/gpu_gemma_score.out 2>&1 || { echo GEMMA_SCORE_FAIL; exit 1; }
echo GEMMA_SCORE_DONE
(../.venv/bin/python judge.py > ../logs/judge_1.out 2>&1 &)
../.venv/bin/python gpu_run.py --model gams --stage score --slmt --budget 10000 --max-bs 40 > ../logs/gpu_gams_score.out 2>&1 || { echo GAMS_SCORE_FAIL; exit 1; }
echo GAMS_SCORE_DONE
