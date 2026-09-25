"""Shared constants, paths and small helpers for the RQ3 capability-control artifact (iter-3 exp12)."""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
DATA = WS / "data"
RESULTS = WS / "results"
ITEMS = RESULTS / "items"
LOGS = WS / "logs"
ADAPTERS = WS / "adapters"
for _d in (DATA, RESULTS, ITEMS, LOGS, ADAPTERS):
    _d.mkdir(parents=True, exist_ok=True)

SEED = 20260925
ITER1_SEED = 20260923  # iter-1 Heretic seed; rand_dirs(j) uses ITER1_SEED + j (copied verbatim)

RUN = Path(__file__).resolve().parents[4]
ITER1_EXP4 = RUN / "3_invention_loop/iter_1/gen_art/gen_art_experiment_4"
ITER1_DATASET = RUN / "3_invention_loop/iter_1/gen_art/gen_art_dataset_1"
ITER2_EXP8 = RUN / "3_invention_loop/iter_2/gen_art/gen_art_experiment_8"
ITER2_EXP5 = RUN / "3_invention_loop/iter_2/gen_art/gen_art_experiment_5"
ITER3_GENART = RUN / "round-3"

MODELS = {
    "gams3_it": {"repo": "cjvt/GaMS3-12B-Instruct", "revision": "1d0b27af5748784482600d24779409e7e1dc9adc"},
    "gemma_it": {"repo": "google/gemma-3-12b-it", "revision": "96b6f1eccf38110c56df3a15bffe176da04bfd80"},
}

UTIL_TASKS = ["arc_challenge", "boolq", "hellaswag", "openbookqa", "piqa", "winogrande"]
# lm-eval convention: acc_norm for ARC-C/HellaSwag/OBQA/PIQA; acc for BoolQ/Winogrande/Belebele
PRIMARY_METRIC = {"arc_challenge": "acc_norm", "hellaswag": "acc_norm", "openbookqa": "acc_norm", "piqa": "acc_norm",
                  "boolq": "acc", "winogrande": "acc", "belebele": "acc"}
LANGS_UTIL = ["en", "sl"]
LANGS_BELE = ["en", "sl", "hu"]
BELE_CFG = {"en": "eng_Latn", "sl": "slv_Latn", "hu": "hun_Latn"}
KL_ARMS = ["en_orig", "en_bt", "sl_mt", "hu_mt"]

HEADROOM_FLOOR = 0.10
GATE_LOSS = 0.20
N_BOOT = 2000


def sha1_int(s: str) -> int:
    return int(hashlib.sha1(s.encode()).hexdigest(), 16)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(p: Path) -> list[dict]:
    p = Path(p)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def write_jsonl(p: Path, rows: list[dict]) -> None:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def append_jsonl(p: Path, rows: list[dict]) -> None:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def setup_logger(name: str):
    from loguru import logger
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
    logger.add(str(LOGS / f"{name}.log"), rotation="30 MB", level="DEBUG")
    return logger


def headroom_H(acc_cond: float, acc_orig: float, chance: float) -> float:
    """Headroom-normalised delta: (acc_cond - chance)/(acc_orig - chance) - 1. Loss = -H."""
    den = acc_orig - chance
    if abs(den) < 1e-12:
        return float("nan")
    return (acc_cond - chance) / den - 1.0


def gate_verdict(loss_point: float, loss_hi95: float, threshold: float = GATE_LOSS) -> str:
    """CATASTROPHIC if point loss > threshold; POSSIBLY_CATASTROPHIC if only the 95% upper bound exceeds it."""
    if loss_point is None or (isinstance(loss_point, float) and math.isnan(loss_point)):
        return "PENDING"
    if loss_point > threshold:
        return "CATASTROPHIC"
    if loss_hi95 > threshold:
        return "POSSIBLY_CATASTROPHIC"
    return "OK"
