#!/usr/bin/env python3
"""STEP 0 - input manifest: existence, size and sha256 of every read-only source listed in inputs.yaml."""
from __future__ import annotations

import yaml
from loguru import logger

from common import RES, RUN, WS, sha256_file, setup_logging, write_json


def main() -> dict:
    setup_logging("check_inputs")
    spec = yaml.safe_load((WS / "inputs.yaml").read_text())
    out, missing = {}, []
    for art, d in spec["artifacts"].items():
        root = RUN / d["root"]
        for f in d["files"]:
            p = root / f
            key = f"{art}:{f}"
            if p.exists() and p.is_file():
                out[key] = {"path": f"RUN/{d['root']}/{f}", "exists": True, "bytes": p.stat().st_size,
                            "sha256": sha256_file(p) if p.stat().st_size < 200e6 else "skipped (>200MB)"}
            else:
                out[key] = {"path": f"RUN/{d['root']}/{f}", "exists": False}
                missing.append(key)
    res = {"n_files": len(out), "n_missing": len(missing), "missing": missing, "files": out,
           "rule": "a missing file makes only its dependent cells UNTRACEABLE; it does not stop the run"}
    write_json(RES / "inputs_manifest.json", res)
    logger.info(f"inputs: {len(out)} files, {len(missing)} missing {missing}")
    return res


if __name__ == "__main__":
    main()
