"""Pure vector helpers shared by gpu_block.py and the unit tests."""
from __future__ import annotations

import torch


def unit(v: torch.Tensor) -> torch.Tensor:
    return v / v.norm().clamp(min=1e-12)


def orth(v: torch.Tensor, basis: list[torch.Tensor]) -> torch.Tensor:
    """Gram-Schmidt v against an orthonormalised version of basis (two passes)."""
    Q = []
    for b in basis:
        b = b.clone()
        for q in Q:
            b = b - (b @ q) * q
        if b.norm() > 1e-8:
            Q.append(unit(b))
    for _ in range(2):
        for q in Q:
            v = v - (v @ q) * q
    return v
