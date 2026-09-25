#!/usr/bin/env bash
# Full local generation pass: GaMS -> Gemma -> Qwen3-14B, one NF4 model on the GPU at a time (resumable).
set -u
cd "$(dirname "$0")/src"
PY=../.venv/bin/python
$PY gpu_gen.py --model gams  --phase full --bs 64 --skip-bvs   >> ../logs/gpu_gams_full.out 2>&1; echo "gams exit $?" >> ../logs/chain.out
$PY gpu_gen.py --model gemma --phase full --bs 64 --bvs-n 16   >> ../logs/gpu_gemma_full.out 2>&1; echo "gemma exit $?" >> ../logs/chain.out
$PY gpu_gen.py --model q14   --phase full --bs 64 --bvs-n 16   >> ../logs/gpu_q14_full.out 2>&1; echo "q14 exit $?" >> ../logs/chain.out
touch ../logs/chain_done.flag
