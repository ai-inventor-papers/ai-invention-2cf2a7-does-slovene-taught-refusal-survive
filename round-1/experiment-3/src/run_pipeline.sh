#!/usr/bin/env bash
# Full ALT-3 pipeline (resumable: every stage skips completed outputs). Order keeps SCORE unseen until the hash.
set -euo pipefail
cd "$(dirname "$0")/src"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
PY=../.venv/bin/python
B="--budget 10000 --max-bs 40"
[ -f ../data/harmless.jsonl ] || $PY prep_data.py
[ -f ../data/score400_mt_sl.jsonl ] || $PY translate.py
[ -f ../results/selftest_gams.json ] || $PY selftest.py --model gams
# CONSTRUCT as executed: (1) pre-registered zero-projection ablation -> MC a_late (catastrophic; interrupted before b/a24),
# (2) CONSTRUCT-only ablation-operator pilot, (3) all constructions again with mean-projection skip-BOS ablation
[ -f ../results/mc_gams.json ] || timeout 1500 $PY gpu_run.py --model gams --stage construct --variant zero $B || true
[ -f ../results/ablation_pilot_gams.json ] || $PY ablation_pilot.py --model gams
$PY gpu_run.py --model gams --stage construct --variant mean_skipbos $B
[ -f ../results/selftest_gemma.json ] || $PY selftest.py --model gemma
$PY gpu_run.py --model gemma --stage construct --variant mean_skipbos $B   # runs only the construction GaMS's MC selects
[ -f ../protocol.sha256 ] || $PY freeze.py                  # hash BEFORE any SCORE item
$PY gpu_run.py --model gemma --stage score --slmt $B
$PY gpu_run.py --model gams --stage score --slmt $B
# (local judge fallback not needed: gemini recovered)
cd .. && ./finalize.sh; exit 0
cd .. && .venv/bin/python method.py && .venv/bin/python src/audit.py
