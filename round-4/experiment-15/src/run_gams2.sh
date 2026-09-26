#!/bin/bash
# waits for the Gemma body process (PID 17829) to exit, then runs the full GaMS pipeline with a generous deadline
# so the GaMS random-direction control (never scored in earlier iterations) is not truncated.
cd "$(dirname "$0")/src"
while kill -0 17829 2>/dev/null; do sleep 10; done
sleep 5
AII_RAND_TWINS=0 ../.venv/bin/python gen.py --model gams3_it --judge local/j1 \
  --body_deadline $(date -d "23:25" +%s) > ../logs/gen_gams.out 2>&1
echo "ALL GEN DONE $(date)" > ../logs/gen_all_done.txt
