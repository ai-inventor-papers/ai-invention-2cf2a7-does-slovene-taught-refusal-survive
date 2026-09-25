#!/usr/bin/env python3
"""Single entry point for the ALT-5 teacher-inheritance screen (iter 2, experiment 7).

Method under test vs baselines, all on byte-identical prompts, greedy decoding, empty system turn, ONE judge readout:
  system under test : GaMS3-12B-Instruct (NF4, local)           -- predict_gams
  baseline (sibling): Gemma-3-12B-IT (NF4, local; shared base)  -- predict_gemma
  teacher reference : Qwen3-235B-A22B (OpenRouter, thinking off) -- output / predict_q235
  positive control  : Qwen3-14B (NF4, local, same family)       -- predict_q14
  outgroup placebo  : Llama-3.3-70B-Instruct (OpenRouter)        -- predict_out
Primary statistic T1: dk = kappa(GaMS, Q235) - kappa(GaMS, Gemma) on HARD-DEV EN (paired item bootstrap), gated by the
family calibration FP-cal = kappa(Q14, Q235) - kappa(Q14, Gemma) > 0; see results/protocol.json (frozen, sha256).

Every stage is a resumable script in src/; this driver runs them in order and stops at the first failure.
  python method.py --stage all            # everything (GPU + API + analysis); resumable
  python method.py --stage items|bt|gpu|api|judge|local|xent|analyze|report
Stage 'local' is the $0 SUBSTITUTE readout used for the delivered headline numbers while the run's OpenRouter budget was
exhausted (Mistral-Small-24B NF4, same frozen prompts, all five systems) plus the rejected post-hoc prefill_v2 variant.
Stage 'gpu' runs GaMS -> Gemma -> Qwen3-14B one NF4 model at a time (~1.3 GPU-h on an RTX 4090).
Stages 'api' and 'judge' spend OpenRouter money (global cap AII_COST_CAP, default $9; hard budget $10).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from loguru import logger

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
PY = str(ROOT / ".venv/bin/python") if (ROOT / ".venv/bin/python").exists() else sys.executable

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
(ROOT / "logs").mkdir(exist_ok=True)
logger.add(ROOT / "logs/method.log", rotation="30 MB", level="DEBUG")

STAGES: dict[str, list[list[str]]] = {
    # STEP 0: item sets H / R / R200 / ID + REF_sft (GaMS3's own SFT refusal texts), reserved-id asserts
    "items": [["build_items.py"]],
    # STEP 1: NLLB-200 back-translation of the HARD-DEV Slovene arm (en_bt)
    "bt": [["gpu_gen.py", "--model", "nllb"]],
    # STEP 4: local NF4 generation (k0 x 3 arms + 5-token compliant / neutral prefill on R200) + batch-1 checks
    "gpu": [["gpu_gen.py", "--model", "gams", "--phase", "full", "--bs", "64", "--bvs-n", "32"],
            ["gpu_gen.py", "--model", "gemma", "--phase", "full", "--bs", "64", "--bvs-n", "16"],
            ["gpu_gen.py", "--model", "q14", "--phase", "full", "--bs", "64", "--bvs-n", "16"]],
    # STEP 3: API generation (teacher + outgroup), pinned providers, temperature 0, max_tokens 160
    "api": [["api_gen.py", "--probe"],
            ["api_gen.py", "--system", "q235", "--conc", "16"],
            ["api_gen.py", "--system", "out", "--conc", "16"]],
    # STEP 5: one readout for all systems (gemini-2.5-flash P1), identity-name judge, gpt-4.1 second family 15%
    "judge": [["judge.py", "--judge", "refusal", "--conc", "32"],
              ["judge.py", "--judge", "idname", "--conc", "24"],
              ["judge.py", "--judge", "second", "--conc", "16"]],
    # SUBSTITUTE readout (post-freeze deviation; see src/local_judge.py) + post-hoc prefill variant (rejected)
    "local": [["local_judge.py", "--task", "refusal", "--phase", "full", "--bs", "16"],
              ["local_judge.py", "--task", "idname", "--phase", "full", "--bs", "16"],
              ["local_judge.py", "--task", "idname", "--phase", "pilot", "--bs", "16"],
              ["local_judge.py", "--task", "refusal", "--variant", "prefill_v2", "--bs", "16"]],
    # exploratory (post-freeze) white-box wording likelihood of teacher vs outgroup texts under each local model
    "xent": [["xent.py", "--model", "gams"], ["xent.py", "--model", "gemma"], ["xent.py", "--model", "q14"]],
    # STEPS 6-7: statistics, independent audit, figures, method_out.json, RESULTS.md
    "analyze": [["analyze.py", "--readout", "local"], ["analyze.py", "--readout", "gemini"],
                ["analyze.py", "--readout", "regex"], ["prefill_v2_validation.py"], ["audit.py"], ["make_figs.py"],
                ["make_method_out.py"]],
    "report": [["make_report.py"]],
}
ORDER = ["items", "bt", "gpu", "api", "judge", "local", "xent", "analyze", "report"]


def run(cmd: list[str]) -> None:
    t0 = time.time()
    logger.info(f"RUN {' '.join(cmd)}")
    r = subprocess.run([PY, *cmd], cwd=SRC)
    logger.info(f"END {' '.join(cmd)} exit={r.returncode} in {time.time() - t0:.0f}s")
    if r.returncode != 0:
        raise RuntimeError(f"stage command failed: {' '.join(cmd)} (exit {r.returncode})")


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", default="all", choices=["all", *ORDER])
    a = ap.parse_args()
    for st in (ORDER if a.stage == "all" else [a.stage]):
        for cmd in STAGES[st]:
            run(cmd)
    logger.info("done")


if __name__ == "__main__":
    main()
