#!/usr/bin/env bash
# F1 fallback / post-GPU finalisation: judge everything still unjudged (resumable ledgers), fix m from DEV,
# then analysis -> audit -> figures -> RESULTS.md -> method_out.json (+ full/mini/preview).
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
$PY src/judge.py --once          # resumes from results/judge/*_ledger.jsonl; stops cleanly at the key/budget limit
$PY src/set_m.py                 # no-op if results/m_frozen.json already exists
$PY src/analysis.py
$PY src/audit.py
$PY src/make_figs.py
$PY src/write_results_md.py
$PY method.py build-output
