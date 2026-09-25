#!/bin/bash
# GPU chain actually used after the Gemma session A (`src/gen.py --model gemma_it`: checks, MINI, DEV grid, FINAL orig +
# edit@1.0, rand_1 control, 256-token sensitivity) finished. One large model on the GPU at a time:
#   guards on Gemma rows (PolyGuard, Llama-Guard-3, Qwen3Guard) -> Gemma DEV gate (amendment A1) -> Gemma gate session
#   -> GaMS session A -> guards on all new rows -> GaMS DEV gate -> GaMS gate session -> guards on new rows
#   -> StrongREJECT-ft on every row -> build_table.
# Every stage is resumable by row key; re-running this script skips finished work.
# Usage: bash run_chain.sh [PID_TO_WAIT_FOR] [GATE_PAIRS]
set -u
cd "$(dirname "$0")/src"
PY=../.venv/bin/python
WAIT_PID=${1:-}
GATE_PAIRS=${2:-650}
log() { echo "$(date -u +%H:%M:%S) $*" | tee -a ../logs/chain.log; }
guards() {  # $1 = tag. The two RefusEU guards score every row; the adjudicator substitute (Qwen3Guard) scores only
            # the rows where they disagree - the scope RefusEU gives its own GPT-4o-mini adjudicator (amendment A4).
  for g in polyguard llamaguard3; do
    log "guards $1: $g (all rows)"
    $PY guards.py --guard $g > ../logs/guard_${1}_$g.out 2>&1 || log "guard $1 $g exit $?"
  done
  log "guards $1: qwen3guard (LG/PG disagreements only)"
  $PY guards.py --guard qwen3guard --only disagreements > ../logs/guard_${1}_qwen3guard.out 2>&1 || log "guard $1 q3g exit $?"
}
gate() {  # $1 = model
  log "dev gate $1 (gate condition on $GATE_PAIRS pairs if needed)"
  $PY dev_gate.py --model $1 --n_pairs $GATE_PAIRS > ../logs/dev_gate_$1.out 2>&1 || log "dev_gate $1 exit $?"
  need=$($PY -c "import json;g=json.load(open('../results/amendments/lambda_gate_$1.json'));print(int(bool(g.get('lambda_gate')) and g['lambda_gate']!=1.0))" 2>/dev/null || echo 0)
  if [ "$need" = "1" ]; then
    log "gate session $1"
    $PY gen.py --model $1 --stages gate > ../logs/gen_gate_$1.out 2>&1 || log "gen gate $1 exit $?"
  else
    log "no gate session for $1 (PASS at 1.0 or A1 missing)"
  fi
}
if [ -n "$WAIT_PID" ]; then
  log "waiting for pid $WAIT_PID"
  while kill -0 "$WAIT_PID" 2>/dev/null; do sleep 15; done
fi
guards p0
gate gemma_it
log "GaMS session A (short DEV grid: wall-cut amendment A0_gams3_it; extended only if the gate fails)"
AII_DEV_GRID=0,1.0 $PY gen.py --model gams3_it > ../logs/gen_gams3_it.out 2>&1 || log "gen gams3_it exit $?"
guards p1
gate gams3_it
guards p2
log "StrongREJECT-ft on all rows"
$PY sr_ft.py > ../logs/sr_ft.out 2>&1 || log "sr_ft exit $?"
$PY build_table.py > ../logs/build_table.out 2>&1 || log "build_table exit $?"
log "chain done"
