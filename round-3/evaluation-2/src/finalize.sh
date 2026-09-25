#!/bin/bash
set -e
cd "$(dirname "$0")"
export EVAL_NBOOT=1000
.venv/bin/python eval.py 2>&1 | tail -20
.venv/bin/python src/gen_readout_repair.py
.venv/bin/python src/rederive.py 2>&1 | tail -6
SKILL_DIR="../../../tools/aii-json"
$SKILL_DIR/../.ability_client_venv/bin/python $SKILL_DIR/scripts/aii_json_validate_schema.py --format exp_eval_sol_out --file "$PWD/eval_out.json" 2>&1 | tail -4
$SKILL_DIR/../.ability_client_venv/bin/python $SKILL_DIR/scripts/aii_json_format_mini_preview.py --input "$PWD/eval_out.json" 2>&1 | tail -3
ls -lh eval_out.json results/eval_results.json judge_error_matrices.json work/items_relabelled.jsonl.gz figures/ 2>&1 | tail -12
echo FINALIZE_DONE
