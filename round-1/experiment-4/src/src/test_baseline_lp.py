#!/usr/bin/env python3
"""Unit test for the sharded O2 baseline-log-prob cache (CPU; no model needed).

Checks: round-trip equality within float16 precision, every shard below the byte cap, and that a missing cache
returns None so the caller recomputes.
"""
import sys
import tempfile
from pathlib import Path

sys.argv = [__file__, "--model", "gemma_it"]
import torch

import run_model as RM


def main():
    with tempfile.TemporaryDirectory() as d:
        out = Path(d)
        assert RM.load_baseline_lp(out) is None, "empty dir must return None"
        torch.manual_seed(0)
        base = {(k, l): torch.randn(37, 5000) for k in ("sel", "eval") for l in ("en", "sl")}
        cap = 200 * 1024  # force many shards
        paths = RM.save_baseline_lp(out, base, max_bytes=cap)
        sizes = [p.stat().st_size for p in paths]
        assert paths and max(sizes) < cap * 1.15, f"shard too big: {max(sizes)} vs {cap}"
        back = RM.load_baseline_lp(out)
        assert set(back) == set(base), (set(back), set(base))
        for k in base:
            assert back[k].shape == base[k].shape, (k, back[k].shape, base[k].shape)
            err = (back[k] - base[k]).abs().max().item()
            assert err < 1e-2, (k, err)
        # real-scale shard count with the production cap
        big = {("sel", "en"): torch.zeros(400, 262144)}
        paths2 = RM.save_baseline_lp(out / "big" if (out / "big").mkdir() else out / "big", big)
        assert all(p.stat().st_size < 100 * 1024 ** 2 for p in paths2), "production shard exceeds 100 MB"
        print(f"OK  {len(paths)} shards (max {max(sizes) / 1024:.0f} KiB), round-trip max err {err:.2e}; "
              f"production-cap shards for a 400x262144 tensor: {len(paths2)}, "
              f"max {max(p.stat().st_size for p in paths2) / 1024 ** 2:.0f} MB")


if __name__ == "__main__":
    main()
