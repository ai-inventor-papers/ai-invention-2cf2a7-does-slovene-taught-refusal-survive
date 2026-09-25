#!/bin/bash
# Restore everything the manifest removes, plus the model weights (not stored in this repository).
# HF_HOME must point at the cache you want to fill. Gemma and Llama-Guard-3 are gated: accept their licences and export
# HF_TOKEN first.
set -eu
uv sync
hf download google/gemma-3-12b-it          --revision 96b6f1eccf38110c56df3a15bffe176da04bfd80
hf download cjvt/GaMS3-12B-Instruct        --revision 1d0b27af5748784482600d24779409e7e1dc9adc
hf download meta-llama/Llama-Guard-3-8B    --revision 7327bd9f6efbbe6101dc6cc4736302b3cbb6e425 --exclude "original/*"
hf download ToxicityPrompts/PolyGuard-Qwen --revision 644bfe73ff498c9a14818b72a11187eaf23f0ff1
hf download Qwen/Qwen3Guard-Gen-8B         --revision 4505cb1a6f1864f21f8b27f7daf1b9a1aab6edbb
hf download qylu4156/strongreject-15k-v1   --revision 4bd893d32390d2cace4f067dc2e3ef5294fd78a2
hf download google/gemma-2b                --revision 9cf48e52b224239de00d483ec8eb84fb8d0f3a3a --exclude "*.gguf"
echo "restored; the LoRA edits are read from the sibling iter_3 exp9 workspace (see README)"
