#!/usr/bin/env bash
# CPU-only: recompute every number from results/items, audit it, rebuild tables/figures/method_out variants.
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
$PY src/analyze.py
$PY src/audit.py
$PY src/assemble_p0.py
$PY src/build_outputs.py
$PY src/make_figs.py
SK=../../../tools/aii-json
$SK/../.ability_client_venv/bin/python $SK/scripts/aii_json_validate_schema.py --format exp_gen_sol_out --file "$PWD/method_out.json"
$PY - <<'PYEOF'
import json
from pathlib import Path
mo = json.loads(Path("method_out.json").read_text())
Path("full_method_out.json").write_text(json.dumps(mo, ensure_ascii=False))
mini = {"metadata": mo["metadata"], "datasets": [{"dataset": d["dataset"], "examples": d["examples"][:3]} for d in mo["datasets"]]}
Path("mini_method_out.json").write_text(json.dumps(mini, ensure_ascii=False, indent=1))
def trunc(x):
    if isinstance(x, str):
        return x[:200]
    if isinstance(x, list):
        return [trunc(v) for v in x[:10]]
    if isinstance(x, dict):
        return {k: trunc(v) for k, v in x.items()}
    return x
prev = {"metadata": trunc(mo["metadata"]), "datasets": [{"dataset": d["dataset"], "examples": [trunc(e) for e in d["examples"][:3]]} for d in mo["datasets"]]}
Path("preview_method_out.json").write_text(json.dumps(prev, ensure_ascii=False, indent=1))
print("variants written")
PYEOF
for f in full_method_out.json mini_method_out.json preview_method_out.json; do
  $SK/../.ability_client_venv/bin/python $SK/scripts/aii_json_validate_schema.py --format exp_gen_sol_out --file "$PWD/$f" | tail -1
done
ls -lh method_out.json full_method_out.json mini_method_out.json preview_method_out.json results/*.json | awk '{print $5, $9}'
