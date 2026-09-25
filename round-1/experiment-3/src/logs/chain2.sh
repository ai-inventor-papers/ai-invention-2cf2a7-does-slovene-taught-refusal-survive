#!/usr/bin/env bash
cd ../src
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
../.venv/bin/python gpu_run.py --model gams --stage construct --variant mean_skipbos --budget 10000 --max-bs 40 > ../logs/gpu_gams_construct2.out 2>&1 || { echo GAMS_FAIL; exit 1; }
[ -f ../results/selftest_gemma.json ] || ../.venv/bin/python selftest.py --model gemma > ../logs/selftest_gemma.out 2>&1
../.venv/bin/python gpu_run.py --model gemma --stage construct --variant mean_skipbos --budget 10000 --max-bs 40 > ../logs/gpu_gemma_construct.out 2>&1 || { echo GEMMA_FAIL; exit 1; }
echo CHAIN_DONE
