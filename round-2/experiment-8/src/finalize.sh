#!/bin/bash
# Idempotent post-GPU pipeline. Safe to re-run at any time:
#   1. judge any generations that have no label yet (resumable ledger; stops cleanly at the key limit / $9.5 cap)
#   2. contamination audit -> items table -> analysis -> audit -> figures -> method_out.json (+ mini / preview)
#   3. schema validation and a final dry run that must print 0 pending judge calls
# Statistics fall back to the frozen lexicon (labelled "JUDGE PENDING") only if < 95% of rows carry a primary label.
set -e
cd "$(dirname "$0")"
PY=$(pwd)/.venv/bin/python
(cd src && $PY judge.py --dry-run)
(cd src && $PY judge.py) || echo "judge stopped early (key limit?) - re-run ./finalize.sh later"
(cd src && $PY contamination_check.py)
$PY method.py
SK=/ai-inventor/.claude/skills/aii-json
$SK/../.ability_client_venv/bin/python $SK/scripts/aii_json_validate_schema.py --format exp_gen_sol_out --file "$(pwd)/method_out.json" || true
$SK/../.ability_client_venv/bin/python $SK/scripts/aii_json_format_mini_preview.py --input "$(pwd)/method_out.json" || true
ls -lh method_out.json mini_method_out.json preview_method_out.json 2>/dev/null || true
(cd src && $PY judge.py --dry-run)
