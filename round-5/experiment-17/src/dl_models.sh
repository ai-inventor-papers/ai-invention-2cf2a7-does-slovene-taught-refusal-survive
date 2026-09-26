#!/bin/bash
# Download the four pinned snapshots into the shared HF cache (HF_HOME is preset by the platform).
hf download google/gemma-3-12b-it --revision 96b6f1eccf38110c56df3a15bffe176da04bfd80 > logs/dl_gemma.log 2>&1 &
hf download cjvt/GaMS3-12B-Instruct --revision 1d0b27af5748784482600d24779409e7e1dc9adc > logs/dl_gams.log 2>&1 &
hf download meta-llama/Llama-Guard-3-8B --revision 7327bd9f6efbbe6101dc6cc4736302b3cbb6e425 --exclude "original/*" > logs/dl_lg.log 2>&1 &
hf download ToxicityPrompts/PolyGuard-Qwen --revision 644bfe73ff498c9a14818b72a11187eaf23f0ff1 > logs/dl_pg.log 2>&1 &
wait
echo ALLDONE > logs/dl_done.txt
