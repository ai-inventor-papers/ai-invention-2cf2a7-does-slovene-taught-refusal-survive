#!/usr/bin/env bash
cd ..
while kill -0 $(cat logs/gpu_gams.pid) 2>/dev/null; do sleep 5; done
sleep 5
DL=$(( $(date +%s) + 118*60 )); echo $DL > logs/gemma_deadline
nohup .venv/bin/python src/gpu_block.py --model gemma_it --stages pilot,util,kl,gen,belebele,bpb,scorer2,chat --n-gen 100 --n-gen-lambda 50 --util-bs 8 --util-conds orig,E_iter1,rand_nm_j1,rand_nm_j2 --lambda-conds orig,E_iter1,E_iter1_l2.0,E_iter1_l1.5,E_iter1_l0.5 --deadline-epoch $DL > logs/gpu_gemma.out 2>&1 &
echo $! > logs/gpu_gemma.pid
echo "gemma launched $(date) deadline $DL"
