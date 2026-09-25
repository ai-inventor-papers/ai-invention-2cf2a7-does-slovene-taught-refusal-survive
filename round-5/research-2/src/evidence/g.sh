#!/bin/bash
# usage: g.sh NAME URL PATTERN [maxmatches] [ctx]
SKILL_DIR=../../../../tools/aii-web-tools; PY="$SKILL_DIR/../.ability_client_venv/bin/python"
OUT=$(cd "$(dirname "$0")" && pwd)/grep_fetch_logs
echo "# $(date -u +%FT%TZ) $2 :: $3" > $OUT/$1.txt
$PY $SKILL_DIR/scripts/aii_fast_web_fetch.py grep --url "$2" --pattern "$3" -i --max-matches ${4:-15} --context-chars ${5:-220} >> $OUT/$1.txt 2>&1
