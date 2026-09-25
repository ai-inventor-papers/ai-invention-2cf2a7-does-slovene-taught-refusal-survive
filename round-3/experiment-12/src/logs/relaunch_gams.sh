#!/usr/bin/env bash
cd ..
until [ -f results/items/util_gams3_it_orig.jsonl ]; do sleep 2; done
sleep 3
kill $(cat logs/gpu_gams.pid); sleep 8
DL=$(( $(date +%s) + 98*60 )); echo $DL > logs/gams_deadline
cp logs/gpu_gams.out logs/gpu_gams_attempt3.out
nohup .venv/bin/python src/gpu_block.py --model gams3_it --stages util,kl,gen,belebele,bpb,scorer2,chat --n-gen 100 --n-gen-lambda 50 --util-bs 16 --deadline-epoch $DL > logs/gpu_gams.out 2>&1 &
echo $! > logs/gpu_gams.pid
echo "relaunched $(date)"
