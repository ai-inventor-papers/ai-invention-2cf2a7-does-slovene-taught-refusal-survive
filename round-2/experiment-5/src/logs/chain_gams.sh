#!/usr/bin/env bash
cd /ai-inventor/aii_data/runs/run_FVi3e3O9CH5I/3_invention_loop/iter_2/gen_art/gen_art_experiment_5/src
while kill -0 $(cat ../logs/gen_gemma.pid) 2>/dev/null; do sleep 15; done
echo "gemma exited at $(date -u)" >> ../logs/chain.log
../.venv/bin/python gen.py --model gams3_it --bs 64 > ../logs/gen_gams3_it.stdout 2>&1
echo "gams exited $? at $(date -u)" >> ../logs/chain.log
