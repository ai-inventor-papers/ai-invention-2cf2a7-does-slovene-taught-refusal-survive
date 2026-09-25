#!/usr/bin/env bash
# GPU queue: (Gemma main already running as $1) -> GaMS main -> 4v8-bit precision checks for both models.
cd "$(dirname "$0")"
if [ -n "$1" ]; then while kill -0 "$1" 2>/dev/null; do sleep 10; done; fi
.venv/bin/python gpu_pass.py --model gams3_it --phase main --skip_construct_s > logs/main_gams.out 2>&1
.venv/bin/python gpu_pass.py --model gemma_it --phase prec8 --prec_n 20 > logs/prec8_gemma.out 2>&1
.venv/bin/python gpu_pass.py --model gams3_it --phase prec8 --prec_n 20 > logs/prec8_gams.out 2>&1
echo CHAIN_DONE > logs/chain_done.flag
