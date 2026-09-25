#!/usr/bin/env bash
# amendment 9: judge hardware-consistency check, then resume the targeted queue (stages 2-5) + causal/collateral grids
set -euo pipefail
cd "$(dirname "$0")"
PY=../.venv/bin/python
$PY local_judge.py --hwcheck --score --model Qwen/Qwen3-8B --batch 16 --ledger local8b_hwcheck.jsonl
$PY local_judge.py --plan primary --score --model Qwen/Qwen3-8B --batch 16 --ledger local8b.jsonl
