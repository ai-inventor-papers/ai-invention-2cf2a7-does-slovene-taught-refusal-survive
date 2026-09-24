#!/bin/bash
# waits for the Gemma BODY process (PID given), then runs the full GaMS pipeline with the J1 label source.
cd "$(dirname "$0")/src"
while kill -0 $1 2>/dev/null; do sleep 10; done
AII_RAND_TWINS=0 ../.venv/bin/python gen.py --model gams3_it --judge local/j1 \
  --body_deadline $(date -d "22:10" +%s) > ../logs/gen_gams.out 2>&1
echo "ALL GEN DONE $(date)" > ../logs/gen_all_done.txt
