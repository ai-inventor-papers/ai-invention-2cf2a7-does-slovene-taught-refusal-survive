#!/usr/bin/env bash
# Resume after the 22:38 UTC session kill: GaMS FINAL (skips done keys) -> causal -> collateral -> causal2, then Gemma causal2.
cd "$(dirname "$0")/.."
echo "$(date -u +%T) resume chain start"
.venv/bin/python src/run_model.py --model gams3_it --stages final,causal,collateral,causal2 > logs/gams_stage2_resume.out 2>&1
echo "$(date -u +%T) GaMS exit $?"
.venv/bin/python src/run_model.py --model gemma_it --stages causal2 > logs/gemma_causal2.out 2>&1
echo "$(date -u +%T) Gemma causal2 exit $?"
