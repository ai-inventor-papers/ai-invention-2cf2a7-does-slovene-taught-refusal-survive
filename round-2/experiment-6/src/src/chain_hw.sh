#!/usr/bin/env bash
# after chain_resume.sh ends: GaMS hardware-consistency regeneration on the current GPU (L4).
cd "$(dirname "$0")/.."
CP=$(cat logs/chain_resume.pid)
while kill -0 "$CP" 2>/dev/null; do sleep 20; done
echo "$(date -u +%T) resume chain ended; running hwcheck"
.venv/bin/python src/run_model.py --model gams3_it --stages hwcheck > logs/gams_hwcheck.out 2>&1
echo "$(date -u +%T) hwcheck exit $?"
