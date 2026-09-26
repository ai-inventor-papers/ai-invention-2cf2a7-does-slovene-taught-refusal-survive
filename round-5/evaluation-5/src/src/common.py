"""Shared paths, constants and small numeric helpers for the audit (all sources are READ-ONLY)."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import math
import sys
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from loguru import logger

WS = Path(__file__).resolve().parents[1]
RES = WS / "results"
FIG = WS / "figures"
LOGS = WS / "logs"
for _d in (RES, FIG, LOGS):
    _d.mkdir(exist_ok=True)

# ONE constant locates every upstream artifact: AII_RUN_ROOT, else the invention-loop root three levels above this
# workspace (<root>/iter_5/gen_art/gen_art_evaluation_5), i.e. the layout the artifacts are published in.
RUN = Path(os.environ.get("AII_RUN_ROOT", str(WS.parents[2]))).resolve()
EXP15 = RUN / "round-4/experiment-15/src"
EXP14 = RUN / "round-4/experiment-14/src"
EXP13 = RUN / "iter_4/gen_art/gen_art_experiment_13"
EVAL3 = RUN / "round-4/evaluation-3/src"
RESEARCH1 = RUN / "round-4/research-1/src"
EXP9 = RUN / "round-3/experiment-9/src"
EXP10 = RUN / "round-3/experiment-10/src"
EXP11 = RUN / "round-3/experiment-11/src"
EXP12 = RUN / "round-3/experiment-12/src"
EVAL2 = RUN / "round-3/evaluation-2/src"
EXP8 = RUN / "round-2/experiment-8/src"
EXP5 = RUN / "round-2/experiment-5/src"
EVAL1 = RUN / "round-2/evaluation-1/src"
EXP4 = RUN / "round-1/experiment-4/src"
EXP1 = RUN / "round-1/experiment-1/src"
PAPER = RUN / "round-4/report-text/paper_draft.md"
REVIEW = RUN / "round-4/review/.terminal_claude_agent_struct_out.json"
ITER5 = RUN / "round-5"

SEED = 20260927
B = 2000
M = 0.675
MODELS = ("gemma_it", "gams3_it")


def setup_logging(name: str) -> None:
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|" + name + "|{message}")
    logger.add(LOGS / f"{name}.log", rotation="30 MB", level="DEBUG")


def rel(p: Path | str) -> str:
    """Run-relative path for provenance (no absolute server paths in published files)."""
    p = Path(p)
    for base, pre in ((WS, ""), (RUN, "RUN/")):
        try:
            return pre + str(p.relative_to(base))
        except ValueError:
            continue
    return str(p)


def read_json(p: Path) -> Any:
    return json.loads(Path(p).read_text())


def read_jsonl(p: Path) -> list[dict]:
    p = Path(p)
    op = gzip.open if p.suffix == ".gz" else open
    with op(p, "rt") as f:
        return [json.loads(line) for line in f if line.strip()]


def clean(o: Any) -> Any:
    """JSON-safe: numpy -> python, NaN/inf -> None."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return f if math.isfinite(f) else None
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    return o


def write_json(p: Path, obj: Any) -> None:
    Path(p).write_text(json.dumps(clean(obj), indent=1))
    logger.info(f"wrote {rel(p)}")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------ rates / logits
def hautus_logit(k, n):
    """Hautus (1995) log-linear rule on the logit scale: ln((k+.5)/(n-k+.5)) (= Haldane-Anscombe = logit of Jeffreys mean)."""
    k = np.asarray(k, float)
    n = np.asarray(n, float)
    return np.log((k + 0.5) / (n - k + 0.5))


def logit(p):
    p = np.asarray(p, float)
    return np.log(p / (1 - p))


def pct_ci(a: Iterable[float], lo: float = 2.5, hi: float = 97.5) -> list[float | None]:
    a = np.asarray(list(a), float)
    a = a[np.isfinite(a)]
    if len(a) < 20:
        return [None, None]
    return [float(np.percentile(a, lo)), float(np.percentile(a, hi))]


def bca_ci(point: float, boots: np.ndarray, jack: np.ndarray, alpha: float = 0.05) -> list[float | None]:
    from scipy import stats
    b = np.asarray(boots, float)
    b = b[np.isfinite(b)]
    j = np.asarray(jack, float)
    j = j[np.isfinite(j)]
    if len(b) < 50 or len(j) < 5:
        return [None, None]
    prop = np.mean(b < point)
    prop = min(max(prop, 1.0 / len(b)), 1 - 1.0 / len(b))
    z0 = stats.norm.ppf(prop)
    jm = j.mean()
    num = np.sum((jm - j) ** 3)
    den = 6.0 * (np.sum((jm - j) ** 2) ** 1.5)
    a = num / den if den > 0 else 0.0
    out = []
    for q in (alpha / 2, 1 - alpha / 2):
        z = stats.norm.ppf(q)
        adj = stats.norm.cdf(z0 + (z0 + z) / (1 - a * (z0 + z)))
        out.append(float(np.percentile(b, 100 * adj)))
    return out


def wilson(k: float, n: float, z: float = 1.96) -> list[float | None]:
    if n <= 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [c - h, c + h]


def flatten(o: Any, prefix: str = "") -> Iterable[tuple[str, float]]:
    """Yield (json_path, number) for every numeric leaf."""
    if isinstance(o, dict):
        for k, v in o.items():
            yield from flatten(v, f"{prefix}/{k}" if prefix else str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from flatten(v, f"{prefix}/[{i}]")
    elif isinstance(o, bool):
        return
    elif isinstance(o, (int, float)) and math.isfinite(float(o)):
        yield prefix, float(o)


def get_path(o: Any, path: str) -> Any:
    """Resolve a '/'-separated path. Keys may themselves contain '/', so each level greedily takes the LONGEST run of
    path segments that is an existing key ('[i]' segments index lists)."""
    seg = path.split("/")
    cur, i = o, 0
    while i < len(seg):
        if isinstance(cur, list):
            cur = cur[int(seg[i].strip("[]"))]
            i += 1
            continue
        for j in range(len(seg), i, -1):
            k = "/".join(seg[i:j])
            if k in cur:
                cur, i = cur[k], j
                break
        else:
            raise KeyError(seg[i])
    return cur
