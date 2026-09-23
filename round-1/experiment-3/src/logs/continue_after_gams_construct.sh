#!/usr/bin/env bash
cd /ai-inventor/aii_data/runs/run_FVi3e3O9CH5I/3_invention_loop/iter_1/gen_art/gen_art_experiment_3
P=$(cat logs/gpu_gams_construct.pid)
while kill -0 $P 2>/dev/null; do sleep 10; done
[ -f results/mc_gams.json ] || { echo "gams construct failed"; exit 1; }
cd src; export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
../.venv/bin/python selftest.py --model gemma > ../logs/selftest_gemma.out 2>&1
../.venv/bin/python gpu_run.py --model gemma --stage construct --budget 10000 --max-bs 40 > ../logs/gpu_gemma_construct.out 2>&1
echo CHAIN_DONE
