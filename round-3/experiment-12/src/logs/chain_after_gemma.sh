#!/usr/bin/env bash
cd /ai-inventor/aii_data/runs/run_FVi3e3O9CH5I/3_invention_loop/iter_3/gen_art/gen_art_experiment_12
while kill -0 $(cat logs/gpu_gemma.pid) 2>/dev/null; do sleep 5; done
sleep 5
HARD=$(cat logs/final_gpu_deadline)
LAM="--lambda-conds orig,E_iter1,E_iter1_l2.0,E_iter1_l1.5,E_iter1_l0.5 --util-bs 8"
run() { # name, args...
  local name=$1; shift
  if [ $(date +%s) -gt $(( HARD - 420 )) ]; then echo "skip $name (no time) $(date)"; return; fi
  echo "start $name $(date)"
  .venv/bin/python src/gpu_block.py "$@" $LAM --deadline-epoch $HARD > logs/gpu_$name.out 2>&1 &
  echo $! > logs/gpu_$name.pid; wait $!; echo "end $name rc=$? $(date)"
}
run gams_A --model gams3_it --stages util,kl_extra,hkl --util-conds E_art2 --kl-extra-conds E_art2
run gemma_B --model gemma_it --stages hkl,bpb,scorer2
run gams_C --model gams3_it --stages util --util-conds rand_nm_j2
echo "chain done $(date)"
