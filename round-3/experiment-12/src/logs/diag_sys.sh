#!/usr/bin/env bash
cd /ai-inventor/aii_data/runs/run_FVi3e3O9CH5I/3_invention_loop/iter_3/gen_art/gen_art_experiment_12
while kill -0 $(cat logs/chain.pid) 2>/dev/null; do sleep 5; done
DL=$(date -d "today 11:16" +%s)
if [ $(date +%s) -gt $(( DL - 300 )) ]; then echo "skip diag (no time) $(date)"; exit 0; fi
echo "start diag $(date)"
.venv/bin/python src/gpu_block.py --model gemma_it --stages hkl_sys --deadline-epoch $DL > logs/gpu_gemma_diag.out 2>&1
echo "end diag rc=$? $(date)"
