#!/bin/bash
# Waits for the Gemma BODY process, extends Gemma BODY to 400 items (A3), then runs the full GaMS pipeline.
cd "$(dirname "$0")/src"
GP=$(cat ../logs/gen_gemma.pid)
while kill -0 $GP 2>/dev/null; do sleep 10; done
AII_EXTEND_N=400 ../.venv/bin/python gen.py --model gemma_it --phases extend --judge google/gemini-2.5-flash \
  --body_deadline $(date -d "20:45" +%s) > ../logs/gen_gemma_extend.out 2>&1
AII_RAND_TWINS=0 ../.venv/bin/python gen.py --model gams3_it --judge google/gemini-2.5-flash \
  --body_deadline $(date -d "22:15" +%s) > ../logs/gen_gams.out 2>&1
echo "ALL GEN DONE $(date)" > ../logs/gen_all_done.txt
