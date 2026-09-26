"""Prefetch checkpoints (pinned revisions) into the SHARED HF cache (never deleted: siblings share it)."""
import json, sys, time
from pathlib import Path
from huggingface_hub import snapshot_download
revs = json.loads(Path(__file__).resolve().parents[1].joinpath("config/resolved_revisions.json").read_text())
for repo in sys.argv[1:]:
    t = time.time()
    p = snapshot_download(repo, revision=revs[repo], allow_patterns=["*.json", "*.safetensors", "tokenizer*", "*.model", "*.jinja"], max_workers=8)
    print(f"DONE {repo} {p} {time.time()-t:.0f}s", flush=True)
