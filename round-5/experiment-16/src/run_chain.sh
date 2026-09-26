#!/usr/bin/env bash
# Unattended GPU chain actually used (one NVIDIA L4): Gemma -> TTJ -> GaMS -> TTJ -> C-EXT (pew) -> TTJ + round-trip
# -> local scoring (J1, TTJ-J1, local StrongREJECT). Per-model generation deadlines (minutes) come from the env vars
# below; the queue is resumable, and results/queue_<model>.json records what the deadline cut.
set -u
cd "$(dirname "$0")/src"
PY=../.venv/bin/python
export HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false
GEMMA_MIN=${GEMMA_MIN:-85}; GAMS_MIN=${GAMS_MIN:-68}; EXT_MIN=${EXT_MIN:-16}
dl() { echo $(( $(date +%s) + $1 * 60 )) > ../results/deadline_$2.txt; }
step() { echo "=== $(date -u +%H:%M:%S) $*"; "$@"; echo "=== exit $? $(date -u +%H:%M:%S)"; }
dl $GEMMA_MIN gemma_it;  step $PY gen.py --model gemma_it --phases smoke,dev,conf
step $PY translate.py --mode ttj
dl $GAMS_MIN gams3_it;   step $PY gen.py --model gams3_it --phases smoke,dev,conf
step $PY translate.py --mode ttj
dl $EXT_MIN pew_heretic; step $PY gen.py --model pew_heretic --phases dev,conf
step $PY translate.py --mode ttj,roundtrip
step $PY score_local.py --mode j1,sr
touch ../results/chain.done
