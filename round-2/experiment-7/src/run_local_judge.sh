#!/usr/bin/env bash
# Substitute readout (budget blocker, see src/local_judge.py): refusal judge on all full-pass rows, then self-name judge,
# then the ID/pilot validation, then the xent fill-in for API texts that arrived after the first xent pass.
set -u
cd "$(dirname "$0")/src"
PY=../.venv/bin/python
$PY local_judge.py --task refusal --phase full --bs 16 >> ../logs/local_judge.out 2>&1
$PY local_judge.py --task idname --phase full --bs 16 >> ../logs/local_judge.out 2>&1
$PY local_judge.py --task idname --phase pilot --bs 16 >> ../logs/local_judge.out 2>&1
$PY local_judge.py --task refusal --variant prefill_v2 --bs 16 >> ../logs/local_judge.out 2>&1   # post-hoc, rejected
for m in gams gemma q14; do $PY xent.py --model $m >> ../logs/xent.out 2>&1; done
touch ../logs/local_judge_done.flag
