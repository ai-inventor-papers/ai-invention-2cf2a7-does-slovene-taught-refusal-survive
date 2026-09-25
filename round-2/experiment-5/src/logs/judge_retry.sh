#!/usr/bin/env bash
# Resume the FINAL API judge whenever the relay answers; stop when all sweeps are complete or at 02:45 UTC (deviation D5).
cd ../src
while [ "$(date -u +%H%M)" \< "0245" ] || [ "$(date -u +%H)" \> "12" ]; do
  code=$(curl -s -m 30 -o /dev/null -w "%{http_code}" "$OPENROUTER_BASE_URL/chat/completions" -H "Authorization: Bearer $OPENROUTER_API_KEY" -H "Content-Type: application/json" -d '{"model":"google/gemini-2.5-flash","messages":[{"role":"user","content":"OK"}],"max_tokens":3,"reasoning":{"max_tokens":0}}')
  echo "$(date -u +%T) probe $code" >> ../logs/judge_retry.log
  if [ "$code" = "200" ]; then
    ../.venv/bin/python judge.py --split final --conc 24 >> ../logs/judge_final.stdout 2>&1
    n_g=$(wc -l < ../outputs/ledgers/ledger_final_refusal_gemini.jsonl)
    n_i=$(cat ../outputs/ledgers/ledger_final_identity_gpt41.jsonl 2>/dev/null | wc -l)
    n_s=$(cat ../outputs/ledgers/ledger_final_refusal_gpt41.jsonl 2>/dev/null | wc -l)
    echo "$(date -u +%T) after run: gemini=$n_g gpt41=$n_s id_gpt41=$n_i" >> ../logs/judge_retry.log
    if [ "$n_g" -ge 19660 ] && [ "$n_s" -ge 3003 ] && [ "$n_i" -ge 640 ]; then echo "$(date -u +%T) COMPLETE" >> ../logs/judge_retry.log; exit 0; fi
  fi
  sleep 120
done
echo "$(date -u +%T) cut-off reached" >> ../logs/judge_retry.log
