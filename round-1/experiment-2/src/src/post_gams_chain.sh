#!/bin/bash
# GPU chain after the GaMS instruct run: exploratory mean-pooled base residuals, then the 8-bit quant check.
cd "$(dirname "$0")/.."
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2
.venv/bin/python src/base_geometry.py --model pt --pool mean --tag _meanpool > logs/run_base_pt_meanpool.out 2>&1
(.venv/bin/python src/base_stats.py --model pt --tag _meanpool --workers 14 > logs/run_stats_pt_meanpool.out 2>&1 &)
.venv/bin/python src/base_geometry.py --model gb --pool mean --tag _meanpool > logs/run_base_gb_meanpool.out 2>&1
.venv/bin/python src/quant_check.py --model gams > logs/quant_gams.out 2>&1
.venv/bin/python src/base_stats.py --model gb --tag _meanpool --workers 14 > logs/run_stats_gb_meanpool.out 2>&1
echo CHAIN_DONE >> logs/post_gams_chain.done
