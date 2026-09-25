#!/bin/bash
# Download the two 12B checkpoints (pinned revisions) + NLLB into the shared HF cache.
set -e
hf download google/gemma-3-12b-it --revision 96b6f1eccf38110c56df3a15bffe176da04bfd80 --exclude "*.gguf" > logs/dl_gemma.log 2>&1 &
P1=$!
hf download facebook/nllb-200-distilled-1.3B --exclude "*.bin" > logs/dl_nllb.log 2>&1 || hf download facebook/nllb-200-distilled-1.3B >> logs/dl_nllb.log 2>&1
wait $P1
hf download cjvt/GaMS3-12B-Instruct --revision 1d0b27af5748784482600d24779409e7e1dc9adc > logs/dl_gams.log 2>&1
echo DONE
