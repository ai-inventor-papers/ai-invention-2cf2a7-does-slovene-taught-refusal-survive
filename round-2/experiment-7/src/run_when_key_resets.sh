#!/usr/bin/env bash
# Wait for the shared OpenRouter daily limit to reset, wait for the GPU chain, then run finalize.sh.
cd "$(dirname "$0")"
.venv/bin/python src/wait_key.py 03:30 >> logs/wait_key.out 2>&1 || { echo "key never reset" >> logs/wait_key.out; exit 1; }
until [ -f logs/chain_done.flag ]; do sleep 30; done
./finalize.sh
