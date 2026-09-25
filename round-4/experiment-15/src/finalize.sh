#!/bin/bash
# F3 resume script: runs the PRE-REGISTERED paid readout on the saved generations once OpenRouter budget is available.
# Not executed in this artifact (the run key hit its $12 limit at 19:05 UTC; see results/protocol_amendments.json A4).
# Every paid call is cached in results/ledger.jsonl (keyed by sha1(request||response)), so nothing is paid twice.
# Projected cost at 2026-09 prices: flash primary ~$1.8, gpt-4.1-mini 25% ~$0.7, TTJ ~$0.2, ASR ~$0.8 (total ~$3.5).
set -euo pipefail
cd "$(dirname "$0")/src"
export AII_CAP="${AII_CAP:-4.75}"
sed -i "s/^HARD_CAP = .*/HARD_CAP = ${AII_CAP}  # restored by finalize.sh/" orclient.py
touch ../results/judge_stop
../.venv/bin/python judge_paid.py loop --judge google/gemini-2.5-flash          # primary on ALL rows
../.venv/bin/python judge_paid.py second --judge google/gemini-2.5-flash        # gpt-4.1-mini stratified 25%
../.venv/bin/python ttj.py --judge google/gemini-2.5-flash                      # NLLB translations (GPU)
../.venv/bin/python judge_paid.py ttj --judge google/gemini-2.5-flash
../.venv/bin/python judge_paid.py asr --judge google/gemini-2.5-flash           # StrongREJECT-style rubric
echo '{"primary_readout": "google/gemini-2.5-flash"}' > ../results/readout.json
../.venv/bin/python analysis.py && ../.venv/bin/python rederive.py && ../.venv/bin/python figures.py \
  && ../.venv/bin/python make_outputs.py
