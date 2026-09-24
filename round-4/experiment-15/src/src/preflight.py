#!/usr/bin/env python3
"""S0 PREFLIGHT: existence + sha256 of every read-only input, hardware, torch/transformers/bnb versions.

A missing input logs its named fallback rather than failing silently. Writes results/preflight.json.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from common import EDITS, EXP9, MODELS, RESULTS, setup_logging, sha256_file

logger = setup_logging("preflight")


@__import__("loguru").logger.catch(reraise=True)
def main() -> None:
    out: dict = {"edits": {}, "inputs": {}, "hardware": {}, "versions": {}}
    for edit, per in EDITS.items():
        for m, d in per.items():
            f = Path(d) / "adapter_model.safetensors"
            out["edits"][f"{edit}|{m}"] = {"path": str(d), "exists": f.exists(),
                                           "sha256": sha256_file(f)[:16] if f.exists() else None}
    for name, p in {"exp9_judge_parts": EXP9 / "judge_model/mdeberta_gemini_distill/model_parts/manifest.json",
                    "exp9_probe_P300": EXP9 / "data/probe_P300.jsonl",
                    "exp9_gate_harmless40": EXP9 / "data/gate_harmless40.jsonl"}.items():
        out["inputs"][name] = {"path": str(p), "exists": Path(p).exists()}
    try:
        import torch
        out["hardware"] = {"cuda": torch.cuda.is_available(),
                           "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                           "vram_gb": round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1)
                           if torch.cuda.is_available() else 0,
                           "has_c_compiler": bool(shutil.which("cc") or shutil.which("gcc"))}
        import bitsandbytes
        import transformers
        out["versions"] = {"torch": torch.__version__, "transformers": transformers.__version__,
                           "bitsandbytes": bitsandbytes.__version__}
    except ImportError as e:
        out["versions"]["error"] = str(e)
    df = shutil.disk_usage(os.environ.get("HF_HUB_CACHE", "/"))
    out["hardware"]["hf_cache_free_gb"] = round(df.free / 1e9, 1)
    out["models"] = {m: MODELS[m] for m in MODELS}
    (RESULTS / "preflight.json").write_text(json.dumps(out, indent=1))
    missing = [k for k, v in {**out["edits"], **out["inputs"]}.items() if not v["exists"]]
    logger.info(f"preflight written; missing inputs: {missing or 'none'}; hardware {out['hardware']}")


if __name__ == "__main__":
    main()
