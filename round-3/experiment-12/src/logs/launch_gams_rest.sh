#!/usr/bin/env bash
cd /ai-inventor/aii_data/runs/run_FVi3e3O9CH5I/3_invention_loop/iter_3/gen_art/gen_art_experiment_12
until grep -q "gemma launched" logs/launch_gemma.log 2>/dev/null; do sleep 5; done
while kill -0 $(cat logs/gpu_gemma.pid) 2>/dev/null; do sleep 5; done
sleep 5
HARD=$(cat logs/final_gpu_deadline)
NOW=$(date +%s)
if [ $NOW -gt $(( HARD - 600 )) ]; then echo "no time for GaMS remainder $(date)"; exit 0; fi
nohup .venv/bin/python src/gpu_block.py --model gams3_it --stages bpb,scorer2,util,gen,belebele,chat --n-gen 100 --n-gen-lambda 50 --util-bs 8 --util-conds rand_nm_j2 --lambda-conds orig,E_iter1,E_iter1_l2.0,E_iter1_l1.5,E_iter1_l0.5 --deadline-epoch $HARD > logs/gpu_gams_rest.out 2>&1 &
echo $! > logs/gpu_gams_rest.pid
echo "gams remainder launched $(date)"
