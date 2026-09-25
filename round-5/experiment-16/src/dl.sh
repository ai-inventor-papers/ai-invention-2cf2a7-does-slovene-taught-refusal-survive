#!/usr/bin/env bash
# Downloads every pinned checkpoint into the run's shared HF cache ($HF_HUB_CACHE); order = order of use.
set -u
dl() { echo "=== $1@$2 $(date -u +%H:%M:%S)"; df -h "$HF_HUB_CACHE" | tail -1; hf download "$1" --revision "$2" ${3:-} >/dev/null 2>&1 && echo "OK $1 $(date -u +%H:%M:%S)" || echo "FAIL $1 $(date -u +%H:%M:%S)"; }
dl facebook/nllb-200-distilled-1.3B main
dl google/gemma-3-12b-it 96b6f1eccf38110c56df3a15bffe176da04bfd80
dl qylu4156/strongreject-15k-v1 main
dl google/gemma-2b main
dl cjvt/GaMS3-12B-Instruct 1d0b27af5748784482600d24779409e7e1dc9adc
dl p-e-w/gemma-3-12b-it-heretic e037e6e112ea85777fc3858469cdc31fdfceaa13
