#!/usr/bin/env python3
"""Phase 0.3: freeze protocol.yaml (sha256 -> protocol.sha256) and git-commit code + protocol BEFORE any FINAL
generation and BEFORE any paid FINAL label. Also: amend.py-style helper `record_amendment` used by later steps."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone

import yaml

from common import JUDGE_PROMPT_SHA, ADJ_PROMPT_SHA, ROOT, RESULTS, SR_RUBRIC_SHA, sha256_file


def git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()


def record_amendment(aid: str, body: dict) -> None:
    rec = {"id": aid, "utc": datetime.now(timezone.utc).isoformat(), "protocol_sha256": sha256_file(ROOT / "protocol.yaml"),
           **body}
    with (RESULTS / "protocol_amendments.jsonl").open("a") as f:
        f.write(json.dumps(rec) + "\n")
    if (ROOT / ".git").exists():
        git("add", "results/protocol_amendments.jsonl", "results/amendments")
        git("commit", "-q", "-m", f"amendment {aid}", "--no-verify")


def main() -> None:
    p = ROOT / "protocol.yaml"
    yaml.safe_load(p.read_text())  # must parse
    h = sha256_file(p)
    (ROOT / "protocol.sha256").write_text(f"{h}  protocol.yaml\n")
    (RESULTS / "freeze.json").write_text(json.dumps({
        "protocol_sha256": h, "frozen_utc": datetime.now(timezone.utc).isoformat(), "epoch": time.time(),
        "p1_prompt_sha256": JUDGE_PROMPT_SHA, "sr_rubric_sha256": SR_RUBRIC_SHA, "adj_prompt_sha256": ADJ_PROMPT_SHA},
        indent=1))
    if not (ROOT / ".git").exists():
        git("init", "-q")
        git("config", "user.email", "noreply@anthropic.com")
        git("config", "user.name", "exp17-executor")
    (ROOT / ".gitignore").write_text(".venv/\nlogs/\n__pycache__/\nresults/gens/\nresults/labels/\n.aii*\n*.ptylog\n")
    git("add", "protocol.yaml", "protocol.sha256", "src", "data/provenance.json", "data/contamination_check.json",
        "results/freeze.json", "pyproject.toml", "uv.lock", ".gitignore")
    print(git("commit", "-q", "-m", f"freeze protocol {h[:12]} before FINAL generation / paid labels", "--no-verify"))
    print(git("log", "--oneline", "-n", "1"))
    print("frozen", h)


if __name__ == "__main__":
    sys.exit(main())
