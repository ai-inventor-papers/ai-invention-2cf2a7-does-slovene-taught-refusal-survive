#!/usr/bin/env bash
# after the GaMS chain ends: supplementary causal grid (CAUSAL_GRID2) for GaMS, then Gemma.
cd "$(dirname "$0")/.."
CP=$(cat logs/chain_gams.pid)
while kill -0 "$CP" 2>/dev/null; do sleep 20; done
echo "$(date -u +%T) GaMS chain ended; running causal2"
.venv/bin/python src/run_model.py --model gams3_it --stages causal2 > logs/gams_causal2.out 2>&1
.venv/bin/python src/run_model.py --model gemma_it --stages causal2 > logs/gemma_causal2.out 2>&1
echo "$(date -u +%T) causal2 done"
