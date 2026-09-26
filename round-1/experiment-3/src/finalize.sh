#!/usr/bin/env bash
# CPU-only post-processing: judge (resumable) -> analysis -> method_out -> audit -> placebo -> figures -> json variants
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
(cd src && ../$PY judge.py && ../$PY judge_local.py && ../$PY analyze.py)
$PY method.py
(cd src && ../$PY audit.py && ../$PY placebo.py && ../$PY figures.py)
SK=../../../tools/aii-json
$SK/../.ability_client_venv/bin/python $SK/scripts/aii_json_validate_schema.py --format exp_gen_sol_out --file "$(pwd)/method_out.json"
