#!/bin/bash
# usage: s.sh NAME MODE QUERY [max]   (MODE = general|scholarly)
SKILL_DIR=../../../../tools/aii-web-tools; PY="$SKILL_DIR/../.ability_client_venv/bin/python"
OUT=$(cd "$(dirname "$0")" && pwd)/search_logs
echo "# $(date -u +%FT%TZ) $2 :: $3" >> $OUT/$1.txt
$PY $SKILL_DIR/scripts/aii_fast_web_search.py --query "$3" --mode $2 --max-results ${4:-10} >> $OUT/$1.txt 2>&1
echo >> $OUT/$1.txt
