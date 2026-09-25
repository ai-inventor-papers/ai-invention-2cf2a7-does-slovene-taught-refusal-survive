#!/usr/bin/env bash
# One command after the GPU pass: API generation -> judging -> optional T4-api prefill -> xent -> analysis -> audit ->
# figures -> method_out -> report. Every paid step is resumable (ledger keys) and globally capped at $9 (AII_COST_CAP);
# each step runs in 2-3 passes so keys lost to transient proxy outages / upstream 429s are filled. Safe to re-run.
# (The API pilot + post-freeze pilot checks ran once at 00:02 UTC: gens/pilot/, labels/pilot/, results/pilot_checks_api.json.)
set -u
cd "$(dirname "$0")/src"
PY=../.venv/bin/python
L=../logs/finalize.out
echo "=== finalize start $(date -u +%FT%TZ)" >> $L
$PY api_gen.py --probe >> $L 2>&1
# Phase A: teacher + outgroup generation, and (disjointly) judging of the three local systems, concurrently
( for p in 1 2; do $PY api_gen.py --system q235 --conc 16 >> ../logs/api_q235.out 2>&1; done ) &
P1=$!
( for p in 1 2 3; do $PY api_gen.py --system out --conc 10 >> ../logs/api_out.out 2>&1; done ) &
P2=$!
( for p in 1 2; do $PY judge.py --judge refusal --conc 24 --systems gams,gemma,q14 >> $L 2>&1; done ) &
P3=$!
wait $P1 $P2 $P3
echo "=== phase A done $(date -u +%FT%TZ)" >> $L
# exploratory white-box wording likelihood on the GPU (resumable per text key) while judging proceeds
( for m in gams gemma q14; do $PY xent.py --model $m >> ../logs/xent.out 2>&1; done ) &
PX=$!
# Phase B: judge the API rows, then the optional T4-api prefill on the common refused set, then judge those rows
for p in 1 2; do $PY judge.py --judge refusal --conc 32 >> $L 2>&1; done
for s in q235 out; do for p in 1 2; do $PY api_gen.py --system $s --prefill --conc 8 >> $L 2>&1; done; done
for p in 1 2; do $PY judge.py --judge refusal --conc 32 >> $L 2>&1; done
for p in 1 2; do $PY judge.py --judge idname --conc 24 >> $L 2>&1; done
for p in 1 2; do $PY judge.py --judge second --conc 16 >> $L 2>&1; done
echo "=== phase B done $(date -u +%FT%TZ)" >> $L
wait $PX
$PY analyze.py >> $L 2>&1
$PY analyze.py --readout gemini >> $L 2>&1   # pre-registered readout (complete once the paid judge has run)
$PY analyze.py --readout regex >> $L 2>&1
$PY prefill_v2_validation.py >> $L 2>&1
$PY audit.py >> $L 2>&1
$PY make_figs.py >> $L 2>&1
$PY make_method_out.py >> $L 2>&1
$PY make_report.py >> $L 2>&1
echo "=== finalize end $(date -u +%FT%TZ)" >> $L
touch ../logs/finalize_done.flag
