#!/usr/bin/env bash
# Paid labelling chain actually used (amendment A1 order); each step is cached / resumable, hard stop $4.00:
#  Gemma P1 done -> P-B + SB (Gemma); GaMS3 P1 done -> P-B (GaMS3); after the post-GaMS3 TTJ -> adjudication (P-A),
#  SB (GaMS3), P-C (trimmed to 200 items), P-D, drift re-check  (order per amendments A1/A4).
set -u
cd "$(dirname "$0")"
PY=../.venv/bin/python
has() { grep -q "\"dose_tag\": \"rand_hi\"" "gens/$1.jsonl" 2>/dev/null || grep -q '"run"' "results/queue_$1.json" 2>/dev/null; }
step() { echo "=== $(date -u +%H:%M:%S) paid $*"; (cd src && $PY paid.py "$@"); echo "=== exit $? $(date -u +%H:%M:%S)"; }
until has gemma_it; do sleep 30; done
step --mode pb,ben --models gemma_it   # (already done before the A4 re-order; cached no-op on re-run)
until has gams3_it; do sleep 30; done
step --mode pb --models gams3_it
until grep -q "model pew_heretic" logs/chain3.out; do sleep 30; done
step --mode adj --models gemma_it,gams3_it
step --mode ben --models gams3_it
AII_PC_TRIM=1 step --mode pc --models gemma_it,gams3_it
step --mode pd,drift --models gemma_it,gams3_it
touch results/paid.done
