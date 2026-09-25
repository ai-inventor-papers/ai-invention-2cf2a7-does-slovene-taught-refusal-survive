#!/usr/bin/env python3
"""Pre-fetch local model weights into the run's shared HF cache (HF_HUB_CACHE); safetensors only, no 'original/' dirs."""
import sys
from concurrent.futures import ThreadPoolExecutor
from huggingface_hub import snapshot_download

MODELS = {
    "sentence-transformers/LaBSE": ["*.json", "*.txt", "model.safetensors", "2_Dense/model.safetensors", "2_Dense/config.json", "1_Pooling/*", "sentencepiece*", "*.model"],
    "facebook/nllb-200-distilled-1.3B": ["*.json", "*.model", "pytorch_model.bin"],
    "Helsinki-NLP/opus-mt-tc-big-zls-en": ["*.json", "*.spm", "model.safetensors", "vocab*", "*.txt"],
    "meta-llama/Llama-Guard-3-8B": ["*.json", "*.safetensors"],
}


def get(m: str) -> str:
    p = snapshot_download(m, allow_patterns=MODELS[m])
    print("OK", m, p, flush=True)
    return p


if __name__ == "__main__":
    order = sys.argv[1:] or list(MODELS)
    with ThreadPoolExecutor(3) as ex:
        list(ex.map(get, order))
