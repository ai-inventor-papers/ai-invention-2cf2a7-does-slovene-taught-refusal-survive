"""Download model snapshots (safetensors + configs only) into the shared HF cache, sequentially."""
import sys, time
from huggingface_hub import snapshot_download
SPECS = {
    "gams": ("cjvt/GaMS3-12B-Instruct", "1d0b27af57"),
    "gemma": ("google/gemma-3-12b-it", None),
    "q14": ("Qwen/Qwen3-14B", None),
    "nllb": ("facebook/nllb-200-distilled-1.3B", None),
}
PAT = ["*.json", "*.safetensors", "*.model", "*.txt", "tokenizer*", "*.jinja"]
for k in sys.argv[1:]:
    repo, rev = SPECS[k]
    t = time.time()
    for attempt in range(3):
        try:
            p = snapshot_download(repo, revision=rev, allow_patterns=PAT, max_workers=8)
            print(f"DONE {k} {repo} {p} {time.time()-t:.0f}s", flush=True); break
        except Exception as e:
            print(f"ERR {k} attempt {attempt}: {e!r}", flush=True); time.sleep(10)
