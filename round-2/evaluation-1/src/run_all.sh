#!/usr/bin/env bash
# Full pipeline. $0 steps always run; the paid census (src/judge_p1.py) runs only if the OpenRouter key has budget
# (it probes GET /api/v1/key first and exits 3 when exhausted). Everything is resumable from labels/ledger.jsonl.
set -euo pipefail
cd "$(dirname "$0")"
[ -d .venv ] || { uv venv .venv --python=3.12 && uv pip install --python .venv/bin/python -r requirements.txt; }
PY=.venv/bin/python
(cd src && ../$PY build_registry.py)          # registry + exact-identity P1 propagation
(cd src && ../$PY surrogate.py)               # P1-only surrogate (trained on real exp1 P1 labels)
(cd src && ../$PY surrogate_pooled.py)        # pooled multi-prompt surrogate anchored to P1
(cd src && ../$PY judge_p1.py --tier ALL) || echo "paid tiers not run (exit $?) - statistics use the \$0 readouts"
$PY eval.py                                   # all statistics -> work/eval_full.json
$PY src/report.py                             # eval_out.json, RECONCILIATION.md, verdict table
$PY src/figures.py                            # figures/
(cd src && ../$PY spotcheck.py)               # score every readout against the blind adjudication
(cd src && ../$PY audit.py)                   # 46 independent checks; non-zero exit on any failure
(cd src && ../$PY placebo_check.py)           # headline tests rerun on shuffled input must FAIL
