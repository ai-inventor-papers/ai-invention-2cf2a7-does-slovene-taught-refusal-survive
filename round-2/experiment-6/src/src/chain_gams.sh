#!/usr/bin/env bash
# waits for the Gemma GPU process (PID in logs/gemma_stage2.pid) to exit, then runs GaMS stage 1 and stage 2.
cd "$(dirname "$0")/.."
GP=$(cat logs/gemma_stage2.pid)
while kill -0 "$GP" 2>/dev/null; do sleep 20; done
echo "$(date -u +%T) gemma process ended; starting GaMS"
.venv/bin/python src/run_model.py --model gams3_it --stages smoke,dev,dirs > logs/gams_stage1.out 2>&1 && \
.venv/bin/python src/run_model.py --model gams3_it --stages freeze,final,causal,collateral > logs/gams_stage2.out 2>&1
echo "$(date -u +%T) GaMS chain exit $?"
