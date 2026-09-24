#!/usr/bin/env python3
"""Download the two pinned 12B checkpoints (safetensors + tokenizer/config only) into the shared HF cache."""
import sys, time
from huggingface_hub import snapshot_download
MODELS = [("cjvt/GaMS3-12B-Instruct", "1d0b27af5748784482600d24779409e7e1dc9adc"),
          ("google/gemma-3-12b-it", "96b6f1eccf38110c56df3a15bffe176da04bfd80")]
which = sys.argv[1:] or [m for m, _ in MODELS]
for repo, rev in MODELS:
    if repo not in which: continue
    t = time.time()
    p = snapshot_download(repo, revision=rev, allow_patterns=["*.json", "*.safetensors", "*.model", "tokenizer*", "*.jinja"], max_workers=16)
    print(f"{repo}@{rev} -> {p} in {time.time()-t:.0f}s", flush=True)
