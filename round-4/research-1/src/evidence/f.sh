#!/bin/bash
# usage: f.sh NAME URL [maxchars]
SKILL_DIR=/ai-inventor/.claude/skills/aii-web-tools; PY="$SKILL_DIR/../.ability_client_venv/bin/python"
OUT=$(cd "$(dirname "$0")" && pwd)/grep_fetch_logs
echo "# $(date -u +%FT%TZ) $2" > $OUT/$1.txt
$PY $SKILL_DIR/scripts/aii_fast_web_fetch.py fetch --url "$2" --max-chars ${3:-6000} >> $OUT/$1.txt 2>&1
