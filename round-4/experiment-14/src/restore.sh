#!/usr/bin/env bash
# Restore files removed after the round (see .aii/manifest.yaml and README "Restoring removed files").
set -euo pipefail
uv sync                                   # .venv/ (pinned by pyproject.toml + uv.lock)
hf download google/gemma-3-12b-it          --revision 96b6f1eccf38110c56df3a15bffe176da04bfd80
hf download cjvt/GaMS3-12B-Instruct        --revision 1d0b27af5748784482600d24779409e7e1dc9adc
hf download p-e-w/gemma-3-12b-it-heretic   --revision e037e6e112ea85777fc3858469cdc31fdfceaa13
hf download facebook/nllb-200-distilled-1.3B
