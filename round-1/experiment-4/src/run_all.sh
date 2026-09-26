#!/bin/bash
# Full GPU chain: Gemma-3-12B-IT then GaMS3-12B-Instruct (sequential; each process frees its model on exit).
# Final settings (results/protocol_amendments.json, amendments 2-3): 20 trials, 50+50 probe items x 40 new tokens,
# s1 per trial, lambda grid {0.5,1.2}, no in-run rank-k, Mech-C deferred. GaMS Phase H hard deadline 19:08 UTC.
cd "$(dirname "$0")"
.venv/bin/python -u src/run_model.py --model gemma_it --n-trials 20 --rank-variant none --lambda-grid 0.5,1.2 --no-mech-c --skip-replay > logs/gemma_it.out 2>&1
echo "gemma exit $?" >> logs/chain.log
.venv/bin/python -u src/run_model.py --model gams3_it --n-trials 20 --rank-variant none --lambda-grid 0.5,1.2 --no-mech-c --deadline-epoch 1790190480 > logs/gams3_it.out 2>&1
echo "gams exit $?" >> logs/chain.log
