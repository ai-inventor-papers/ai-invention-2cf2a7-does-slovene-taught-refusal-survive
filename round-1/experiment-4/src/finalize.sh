#!/bin/bash
# Post-GPU pipeline: (judge if the shared key is up) -> analysis -> figures -> method_out.json -> audit -> RESULTS.md
set -e
cd "$(dirname "$0")"
PY=.venv/bin/python
MODELS=${1:-gemma_it,gams3_it}
CODE=$(curl -s -o /dev/null -w "%{http_code}" https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"google/gemini-2.5-flash","messages":[{"role":"user","content":"hi"}],"max_tokens":3,"reasoning":{"max_tokens":0}}')
if [ "$CODE" = "200" ]; then
  (cd src && python3 judge.py --models "$MODELS" --all)                      # v2 prompt (primary judge sensitivity)
  (cd src && python3 judge.py --models "$MODELS" --all --prompt-version v1)  # v1 prompt (plan's wording)
else
  echo "OpenRouter returned HTTP $CODE (shared key over its daily limit) -> skipping judging; judge readouts stay partial."
fi
$PY method.py
(cd src && ../$PY audit.py | tail -45)
(cd src && ../$PY write_results_md.py)
$PY method.py
ls -lh method_out.json RESULTS.md results/audit.json
