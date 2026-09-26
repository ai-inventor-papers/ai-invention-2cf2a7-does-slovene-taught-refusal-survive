#!/usr/bin/env python3
"""Entry point of the dir5 artifact (Heretic core: C3 / C5 / ALT-4 screen, SCREEN-SPEC v1).

Pipeline (each stage is resumable and writes only inside this workspace):
  S0  python3 src/prep_data.py            RefusEU pairs + splits, KL sets (+ src/prep_openrouter.py: SL MT, T/R/U grades)
      python3 src/write_protocol.py       freeze protocol.json + protocol.sha256 BEFORE GPU scoring
  GPU ./run_all.sh                         src/run_model.py for gemma_it then gams3_it (Phase O, H, P)
  J   python3 src/judge.py                gemini-2.5-flash refusal judge (150 stratified per cell)
  A   this script: src/analyze.py -> src/make_figs.py -> method_out.json (exp_gen_sol_out schema)

The METHOD is the English-objective Heretic abliteration (pinned 3521f864) applied to GaMS3-12B-Instruct; the
BASELINE/CONTROL is the identical procedure on Gemma-3-12B-IT (same config, seed, precision, items), plus the
unedited models, norm-matched and EN-KL-matched random-direction edits, and a lambda-scaled dose curve.

Usage: .venv/bin/python method.py [--run-gpu] [--judge]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent
sys.path.insert(0, str(WS / "src"))
from common import RESULTS, SPLITS, read_jsonl, setup_logger  # noqa: E402

logger = setup_logger("method")
PY = str(WS / ".venv" / "bin" / "python")


def run(cmd: list[str]):
    logger.info("run: " + " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=WS / "src")


def build_method_out() -> dict:
    A = json.loads((RESULTS / "analysis.json").read_text())
    s400 = {p["pair_id"]: p for p in read_jsonl(SPLITS / "score400.jsonl")}
    judge = {}
    for r in read_jsonl(RESULTS / "judge.jsonl"):
        judge[(r["model"], r["cell"], r["lang"], r["pair_id"], r["trial"])] = r["judge"]
    datasets = []
    for m in A["models_available"]:
        orig = {(r["pair_id"], r["lang"]): r for r in read_jsonl(RESULTS / m / "orig_score400.jsonl")}
        sel = {(r["pair_id"], r["lang"]): r for r in read_jsonl(RESULTS / m / "selected_score400.jsonl") if "s" in r}
        pre = {(r["pair_id"], r["lang"]): r for r in read_jsonl(RESULTS / m / "prefill.jsonl") if r["k"] == 5}
        ex = []
        for (pid, lang), o in orig.items():
            s = sel.get((pid, lang), {})
            e = {"input": s400[pid][lang], "output": o.get("text", ""),
                 "predict_heretic_selected_edit": s.get("text", ""),
                 "predict_prefill5_continuation": (pre[(pid, lang)]["prefill"] + pre[(pid, lang)]["text"]) if (pid, lang) in pre else "",
                 "metadata_model": m, "metadata_pair_id": pid, "metadata_lang": lang,
                 "metadata_category": o["category"], "metadata_dose_group": o["dose_group"],
                 "metadata_R_orig": o.get("R"), "metadata_s_orig": o["s"], "metadata_s1_orig": o["s1"],
                 "metadata_R_selected": s.get("R"), "metadata_s_selected": s.get("s"),
                 "metadata_prefill5_flip": pre[(pid, lang)]["flip"] if (pid, lang) in pre else None,
                 "metadata_judge_orig": judge.get((m, "orig", lang, pid, -1)),
                 "metadata_judge_selected": judge.get((m, "selected", lang, pid, -1))}
            if lang == "sl":
                e["metadata_sl_consistent_orig"] = o.get("sl_consistent")
                e["metadata_sl_consistent_selected"] = s.get("sl_consistent")
            ex.append(e)
        datasets.append({"dataset": f"RefusEU_SCORE400_{m}", "examples": ex})
        tr = json.loads((RESULTS / m / "trials.json").read_text()) if (RESULTS / m / "trials.json").exists() else []
        tex = []
        for t in tr:
            ua = t["user_attrs"]
            tex.append({"input": json.dumps({"direction_index": ua.get("direction_index"), "parameters": ua.get("parameters")}),
                        "output": json.dumps({"keyword_refusals": t["values"][0], "kl": t["values"][1]}),
                        "predict_bilingual_probe": json.dumps(ua.get("bilingual", {})),
                        "metadata_model": m, "metadata_trial_index": ua.get("index"), "metadata_number": t["number"]})
        if tex:
            datasets.append({"dataset": f"Heretic_trials_{m}", "examples": tex})
    meta = {"method_name": "English-objective Heretic abliteration: bilingual reach (GaMS3 vs Gemma-3 control)",
            "artifact": "gen_art_experiment_4 (dir5), run_FVi3e3O9CH5I iter_1, SCREEN-SPEC v1",
            "precision": "NF4 reduced precision (bitsandbytes 4-bit, double quant, bf16 compute) for both models",
            "protocol_sha256": (WS / "protocol.sha256").read_text().split()[0],
            "protocol_amendments": json.loads((RESULTS / "protocol_amendments.json").read_text()) if (RESULTS / "protocol_amendments.json").exists() else None,
            "analysis": A,
            "checks": {m: json.loads((RESULTS / m / "checks.json").read_text()) for m in A["models_available"] if (RESULTS / m / "checks.json").exists()},
            "selection_picks": {m: json.loads((RESULTS / m / "selection_pick.json").read_text()) for m in A["models_available"] if (RESULTS / m / "selection_pick.json").exists()},
            "random_edits": {m: json.loads((RESULTS / m / "random_edits.json").read_text()) for m in A["models_available"] if (RESULTS / m / "random_edits.json").exists()},
            "lambda_curves": {m: json.loads((RESULTS / m / "lambda_curve.json").read_text()) for m in A["models_available"] if (RESULTS / m / "lambda_curve.json").exists()},
            "openrouter_spend_usd": sum(float(r.get("cost", 0) or 0) for r in read_jsonl(RESULTS / "judge_ledger.jsonl")),
            "per_item_files": sorted(str(p) for p in RESULTS.rglob("*.jsonl") if "smoke" not in str(p))}
    return {"metadata": meta, "datasets": datasets}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-gpu", action="store_true", help="run ./run_all.sh first (hours)")
    ap.add_argument("--judge", action="store_true", help="run the OpenRouter judge first")
    a = ap.parse_args()
    if a.run_gpu:
        subprocess.run([str(WS / "run_all.sh")], check=True)
    if a.judge:
        run([sys.executable, "judge.py"])
    run([PY, "analyze.py"])
    run([PY, "make_figs.py"])
    out = build_method_out()
    (WS / "method_out.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=float))
    logger.info(f"method_out.json: {sum(len(d['examples']) for d in out['datasets'])} examples in {len(out['datasets'])} datasets")


if __name__ == "__main__":
    main()
