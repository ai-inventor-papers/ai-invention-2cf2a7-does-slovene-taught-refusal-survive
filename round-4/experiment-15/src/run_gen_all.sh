#!/bin/bash
# A4 driver: Gemma BODY (resume; J1 labels in-process) -> GaMS full pipeline (J1 labels in-process).
cd "$(dirname "$0")/src"
AII_RAND_TWINS=0 ../.venv/bin/python gen.py --model gemma_it --phases body,kl --judge local/j1 \
  --body_deadline $(date -d "20:35" +%s) > ../logs/gen_gemma_body.out 2>&1
AII_RAND_TWINS=0 ../.venv/bin/python gen.py --model gams3_it --judge local/j1 \
  --body_deadline $(date -d "22:10" +%s) > ../logs/gen_gams.out 2>&1
echo "ALL GEN DONE $(date)" > ../logs/gen_all_done.txt
