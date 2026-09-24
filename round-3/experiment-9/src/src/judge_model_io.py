#!/usr/bin/env python3
"""The J1 checkpoint (1.06 GB fp32 safetensors) exceeds the 100 MB per-file publishing limit, so it is stored SPLIT into
`model_parts/model.safetensors.part_XXX` (95 MB each) and reassembled on demand.

`ensure_model_file()` is called by src/judge_distill.py before every load; `split_model_file()` re-splits after training.
Byte-identical round trip is checked with sha256 (`model_parts/manifest.json`).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

CHUNK = 95 * 1024 * 1024


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def split_model_file(mdir: Path) -> dict:
    src = Path(mdir) / "model.safetensors"
    parts_dir = Path(mdir) / "model_parts"
    parts_dir.mkdir(exist_ok=True)
    for old in parts_dir.glob("model.safetensors.part_*"):
        old.unlink()
    names, n = [], 0
    with src.open("rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            n += 1
            name = f"model.safetensors.part_{n:03d}"
            (parts_dir / name).write_bytes(b)
            names.append(name)
    man = {"file": "model.safetensors", "parts": names, "chunk_bytes": CHUNK,
           "sha256": _sha256(src), "size_bytes": src.stat().st_size}
    (parts_dir / "manifest.json").write_text(json.dumps(man, indent=1))
    src.unlink()
    return man


def ensure_model_file(mdir: Path) -> Path:
    """Reassemble model.safetensors from model_parts/ if it is not already present."""
    mdir = Path(mdir)
    dst = mdir / "model.safetensors"
    if dst.exists():
        return dst
    man = json.loads((mdir / "model_parts" / "manifest.json").read_text())
    with dst.open("wb") as out:
        for name in man["parts"]:
            out.write((mdir / "model_parts" / name).read_bytes())
    got = _sha256(dst)
    if got != man["sha256"]:
        dst.unlink()
        raise RuntimeError(f"reassembled checkpoint sha256 {got} != {man['sha256']}")
    return dst


if __name__ == "__main__":
    import sys
    d = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent / "judge_model" / "mdeberta_gemini_distill"
    print(json.dumps(split_model_file(d) if sys.argv[1] == "split" else {"path": str(ensure_model_file(d))}, indent=1)[:400])
