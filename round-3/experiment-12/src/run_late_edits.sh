#!/usr/bin/env bash
# Late pass (STEP 5): re-enter each model block; the build stage reloads the saved (sha-verified) condition states,
# discovers artifact 2's selected adapter (E_art2) and builds its own norm-matched random controls, then scores ONLY
# what is missing (every stage/condition whose results/items file exists is skipped; KL rows are appended per item).
# NOTE: KL rows already on disk were computed without E_art2 -> run with KL_FRESH=1 to recompute KL for E_art2.
set -euo pipefail
cd "$(dirname "$0")"
for M in ${MODELS:-gams3_it gemma_it}; do
  .venv/bin/python src/gpu_block.py --model "$M" --stages util,belebele,gen --n-util 200 --n-gen 100 --gen-conds orig
done
.venv/bin/python src/analyze.py && .venv/bin/python src/audit.py && .venv/bin/python src/assemble_p0.py && .venv/bin/python src/build_outputs.py
