#!/usr/bin/env bash
# Waits until the OpenRouter endpoint answers a 1-token probe (it returned empty 404s from 00:25 UTC), then runs the
# judge worker in watch mode (resumable ledgers; failed rows carry no label and are retried).
cd "$(dirname "$0")/.."
until [ "$(curl -s -m 30 -o /dev/null -w '%{http_code}' -X POST "$OPENROUTER_BASE_URL/chat/completions" \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" -H 'Content-Type: application/json' \
  -d '{"model":"google/gemini-2.5-flash","messages":[{"role":"user","content":"Reply OK"}],"max_tokens":3,"reasoning":{"max_tokens":0}}')" = "200" ]; do
  echo "$(date -u +%T) API not answering; retry in 60s"; sleep 60
done
echo "$(date -u +%T) API OK; starting judge --watch"
exec .venv/bin/python src/judge.py --watch
