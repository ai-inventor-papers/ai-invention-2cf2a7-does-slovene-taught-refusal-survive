#!/usr/bin/env bash
# Final pass: P1 top-up on new adjudicated rows, analysis, re-derivation, tests, schema validation, mini/preview.
set -euo pipefail
cd "$(dirname "$0")"
AII_HARD_STOP=3.05 .venv/bin/python src/paid_round5.py p1
.venv/bin/python eval.py
.venv/bin/python src/rederive.py
.venv/bin/python -m pytest -q
# Schema validation + mini/preview use the aii-json skill of the AI Inventor platform; set AII_JSON_SKILL_DIR to it.
if [ -n "${AII_JSON_SKILL_DIR:-}" ]; then
  PY="$AII_JSON_SKILL_DIR/../.ability_client_venv/bin/python"
  $PY "$AII_JSON_SKILL_DIR/scripts/aii_json_validate_schema.py" --format exp_eval_sol_out --file "$(pwd)/eval_out.json"
  $PY "$AII_JSON_SKILL_DIR/scripts/aii_json_format_mini_preview.py" --input "$(pwd)/eval_out.json" || true
fi
