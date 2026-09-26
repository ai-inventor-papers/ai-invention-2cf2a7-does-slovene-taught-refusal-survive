#!/usr/bin/env bash
# Resumable completion of the confirmation run (F5): generation (if incomplete) -> DEV judge -> DEV addendum (commit,
# unlocks FINAL) -> FINAL judge -> $0 scorers -> analysis -> judge-language check -> audit -> outputs -> figures.
# Every step is idempotent: generations and judge ledgers skip keys already present; the addendum is written once.
# Usage: bash finalize.sh            (run from the workspace root)
#        SKIP_GEN=1 bash finalize.sh (do not touch the GPU)
set -euo pipefail
cd "$(dirname "$0")/src"
PY=../.venv/bin/python
[ -x "$PY" ] || { (cd .. && uv sync); }

if [ "${SKIP_GEN:-0}" != "1" ]; then
  for M in gemma_it gams3_it; do
    $PY gen.py --model "$M" --phases smoke,ladder,batchcheck,dev,final
  done
fi

echo "== OpenRouter probe (one call per family)"
$PY openrouter.py | tee ../logs/openrouter_probe_finalize.json
if grep -q '"ok": false' ../logs/openrouter_probe_finalize.json && [ ! -f ../protocol/primary_judge.json ]; then
  echo "OpenRouter unavailable and no substitute-judge decision recorded; all \$0 work is done. Re-run later." >&2
  exit 3
fi
# If protocol/primary_judge.json exists (deviation D5/D6), the API judge steps below resume what they can
# (ledgers skip done keys; failures are not recorded) and the local Qwen3-14B labels are the primaries.

echo "== DEV local third-family judge (Qwen3-14B, \$0)"
$PY judge_local.py --split dev
echo "== DEV judging"
$PY judge.py --split dev || true
echo "== DEV scorers (\$0)"
$PY scorers.py --split dev
echo "== DEV addendum (margins, ceiling, MDE) -> commit"
$PY addendum.py
echo "== FINAL judging (guarded by the addendum hash)"
$PY judge.py --split final || true
$PY judge_local.py --split final
$PY scorers.py --split final
echo "== analysis"
$PY analysis.py --split final
echo "== DEV analysis (gemini-judged replication), judge calibration (exploratory)"
$PY analysis.py --split dev
$PY dev_judge_compare.py
$PY judge_calibrated.py --target dev
$PY judge_calibrated.py --target final
echo "== judge-language check (V5; NLLB SL->EN on 200 responses)"
$PY judge.py --split final --export_only
$PY judge_lang_check.py || echo "V5 judge-language check failed (cut-able); continuing"
$PY judge.py --split final --export_only   # refresh results/spend.json incl. the V5 ledger
echo "== audit"
$PY audit.py
echo "== outputs + figures"
$PY make_outputs.py
$PY figures.py
echo "done"
