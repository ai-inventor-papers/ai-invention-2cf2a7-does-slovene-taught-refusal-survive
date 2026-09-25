#!/usr/bin/env bash
# Waits for the OpenRouter daily key limit to reset, runs the T0 synthetic judge-prompt test (both families),
# writes GO_FINAL only if every expected label is returned, then runs the judge worker in watch mode.
cd "$(dirname "$0")/.."
PY=.venv/bin/python
until $PY src/judge.py --t0 && grep -q '"cost"' results/judge/t0.json && [ "$($PY -c "import json;d=json.load(open('results/judge/t0.json'));print(len(d['items'])==12 and all(len(v)==4 and all(x is not None for x in v.values()) for v in d['items'].values()))")" = "True" ]; do
  echo "$(date -u +%T) T0 not complete (key limit?) - sleeping 120s"; sleep 120
done
if $PY -c "import json,sys;sys.exit(0 if json.load(open('results/judge/t0.json'))['all_expected'] else 1)"; then
  touch results/judge/GO_FINAL; echo "T0 passed -> GO_FINAL"
else
  echo "T0 FAILED: FINAL judging blocked until the prompt is reviewed (DEV judging continues)"
fi
$PY src/judge.py --watch
