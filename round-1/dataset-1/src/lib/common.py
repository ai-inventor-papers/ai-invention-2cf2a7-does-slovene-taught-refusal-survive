"""Shared helpers: paths, logging, hashing, Wilson intervals, kappa, taxonomy."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from loguru import logger

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT.parents[3]  # ../../../..
S0 = RUN / "iter_2/gen_hypo/claude_agent/stage0"
S0B = RUN / "iter_3/gen_hypo/claude_agent/stage0b"
DS = ROOT / "temp/datasets"
WORK = ROOT / "work"
OUT = ROOT / "outputs"
LABELS = ROOT / "labels"
PROMPTS = ROOT / "prompts"
CATS = [f"S{i}" for i in range(1, 15)]
LOW_EN = ["S5", "S7", "S8", "S13"]
HIGH_EN = ["S2", "S3", "S4", "S9", "S10", "S11", "S14"]
MID_EN = ["S1", "S6", "S12"]
CAT_NAMES = {
    "S1": "Violent Crimes", "S2": "Non-Violent Crimes", "S3": "Sex-Related Crimes",
    "S4": "Child Sexual Exploitation", "S5": "Defamation", "S6": "Specialized Advice", "S7": "Privacy",
    "S8": "Intellectual Property", "S9": "Indiscriminate Weapons", "S10": "Hate",
    "S11": "Suicide & Self-Harm", "S12": "Sexual Content", "S13": "Elections", "S14": "Code Interpreter Abuse",
}


def setup_logging(name: str) -> None:
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
    (ROOT / "logs").mkdir(exist_ok=True)
    logger.add(ROOT / f"logs/{name}.log", rotation="30 MB", level="DEBUG")


def sha1_int(s: str) -> int:
    return int(hashlib.sha1(s.encode("utf-8")).hexdigest(), 16)


def sha1_hex(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def wilson(k: float, n: float, z: float = 1.959964) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, float(c - h)), min(1.0, float(c + h)))


def cohen_kappa(a: list, b: list) -> float | None:
    pairs = [(x, y) for x, y in zip(a, b) if isinstance(x, (str, bool)) and isinstance(y, (str, bool))]
    if len(pairs) < 2:
        return None
    from sklearn.metrics import cohen_kappa_score
    x, y = zip(*pairs)
    if len(set(x) | set(y)) < 2:
        return None
    return round(float(cohen_kappa_score(x, y)), 4)


def fleiss_kappa(votes: list[list]) -> float | None:
    """votes: list of items, each a list of labels (same #raters, no None)."""
    votes = [v for v in votes if all(isinstance(x, (str, bool)) for x in v)]
    if not votes:
        return None
    cats = sorted({x for v in votes for x in v})
    n = len(votes[0])
    M = np.array([[v.count(c) for c in cats] for v in votes], dtype=float)
    P_i = ((M * (M - 1)).sum(1)) / (n * (n - 1))
    p_j = M.sum(0) / (len(votes) * n)
    Pbar, Pe = P_i.mean(), (p_j ** 2).sum()
    return round(float((Pbar - Pe) / (1 - Pe)), 4) if Pe < 1 else None


def write_jsonl(p: Path, rows: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with Path(p).open("w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(p: Path) -> list[dict]:
    with Path(p).open() as f:
        return [json.loads(l) for l in f if l.strip()]
