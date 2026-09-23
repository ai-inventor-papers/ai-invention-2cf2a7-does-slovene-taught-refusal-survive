"""Shared OpenRouter cost ledger: one JSONL line per call (cost from usage.cost), filelock-guarded cumulative sum,
hard cap $9.50 overall with per-step sub-caps; BudgetExhausted is raised BEFORE a call that could exceed a cap."""
import json
import time
from pathlib import Path

from filelock import FileLock

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "ledger/ledger.jsonl"
LOCK = FileLock(str(ROOT / "ledger/ledger.lock"))
CAP = 9.50
SUB_CAPS = {"A": 2.6, "D": 0.5, "B": 4.3, "C": 2.3}  # B raised 3.6->4.3 mid-run (gemini dose batches cost ~2x estimate); overall $9.50 cap is binding


class BudgetExhausted(RuntimeError):
    pass


class Ledger:
    def __init__(self) -> None:
        LEDGER.parent.mkdir(exist_ok=True)
        LEDGER.touch()
        self.total, self.by_step = 0.0, {}
        for l in LEDGER.open():
            if l.strip():
                r = json.loads(l)
                self.total += r.get("cost_usd", 0.0)
                self.by_step[r["step"]] = self.by_step.get(r["step"], 0.0) + r.get("cost_usd", 0.0)

    def check(self, step: str, est: float) -> None:
        if self.total + est > CAP:
            raise BudgetExhausted(f"total {self.total:.3f} + {est:.4f} > {CAP}")
        sub = SUB_CAPS.get(step[0])
        spent = sum(v for k, v in self.by_step.items() if k[0] == step[0])  # sub-cap is per priority letter (A/B/C/D)
        if sub is not None and spent + est > sub:
            raise BudgetExhausted(f"step group {step[0]} {spent:.3f} + {est:.4f} > {sub}")

    def add(self, step: str, model: str, key: str, usage: dict) -> float:
        c = float(usage.get("cost", 0.0) or 0.0)
        rec = {"ts": time.time(), "step": step, "model": model, "item_key": key,
               "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"), "cost_usd": c}
        with LOCK:
            with LEDGER.open("a") as f:
                f.write(json.dumps(rec) + "\n")
        self.total += c
        self.by_step[step] = self.by_step.get(step, 0.0) + c
        return c
