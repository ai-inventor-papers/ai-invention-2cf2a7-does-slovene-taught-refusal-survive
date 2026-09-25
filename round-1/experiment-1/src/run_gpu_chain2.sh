#!/usr/bin/env bash
# Second GPU queue (after run_gpu_chain.sh): CONSTRUCT generation + s for both models (non-circular m_s calibration).
cd "$(dirname "$0")"
until [ -f logs/chain_done.flag ]; do sleep 15; done
.venv/bin/python gpu_pass.py --model gemma_it --phase main --construct_gen > logs/construct_gemma.out 2>&1
.venv/bin/python gpu_pass.py --model gams3_it --phase main --construct_gen > logs/construct_gams.out 2>&1
echo CHAIN2_DONE > logs/chain2_done.flag
