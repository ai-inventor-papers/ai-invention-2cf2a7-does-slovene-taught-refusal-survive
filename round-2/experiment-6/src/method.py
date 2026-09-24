#!/usr/bin/env python3
"""Entry point: refusal depth by language (prefill) in Gemma-3-12B-IT vs GaMS3-12B-Instruct.

Method (ours): judged, item-matched prefill-depth design. Each DEPTH-600 item is run in three arms (EN-orig, SL-MT,
EN-BT); the assistant turn is prefilled with a meaning-matched compliant opener at k = 0/3/5/10/20/full tokens.
Controls: a neutral prefix, a cross-language prefix and templates. Readouts: a mechanistic representation readout and
causal steering.
Baseline (comparison): the k=0 no-prefill condition, plus the EN back-translation arm as the language baseline
(MT-noise-controlled). The iter-1 lexicon readout is also logged as the superseded baseline readout.

  python method.py pipeline      # full run: GPU per model -> judge -> m -> analysis -> audit -> figures -> outputs
  python method.py build-output  # only (re)build method_out.json (+ full/mini/preview) from saved results

Stages log to logs/; every number in RESULTS.md is pulled from results/analysis.json (write_results_md.py).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent
sys.path.insert(0, str(WS / "src"))

from loguru import logger  # noqa: E402

from common import CONDITIONS, DATA, RESULTS, read_jsonl  # noqa: E402

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add(str(WS / "logs" / "method.log"), rotation="30 MB", level="DEBUG")
PY = str(WS / ".venv" / "bin" / "python")


def sh(args: list[str]) -> None:
    logger.info("run: " + " ".join(args))
    subprocess.run(args, cwd=WS, check=True)


def pipeline() -> None:
    sh([PY, "src/prep_data.py"])
    for m in ("gemma_it", "gams3_it"):
        sh([PY, "src/run_model.py", "--model", m, "--stages", "smoke,dev,dirs"])
        sh([PY, "src/run_model.py", "--model", m, "--stages", "freeze,final,causal,collateral"])
    sh([PY, "src/judge.py", "--t0"])
    sh([PY, "src/judge.py", "--once"])
    sh([PY, "src/set_m.py"])
    sh([PY, "src/analysis.py"])
    sh([PY, "src/audit.py"])
    sh([PY, "src/make_figs.py"])
    sh([PY, "src/write_results_md.py"])
    build_output()


def build_output() -> None:
    from labels import load_labels
    lab, _, _ = load_labels()
    A = json.loads((RESULTS / "analysis.json").read_text())
    ADJ = {}
    for fn in ("claude_labels.jsonl", "claude_labels2.jsonl"):
        for r in read_jsonl(RESULTS / "adjudication" / fn):
            ADJ[r["key"]] = r["label"]
    items = {it["item_id"]: it for it in read_jsonl(DATA / "depth600.jsonl")}
    datasets = []
    for m in A["models_present"]:
        rows = read_jsonl(RESULTS / m / "final_gen.jsonl")
        by_item: dict = {}
        for r in rows:
            by_item.setdefault(r["item_id"], []).append(r)
        J = set()
        for i, rs in by_item.items():
            d = {(r["arm"], r["cond"]): lab.get(r["key"], {}).get("label") for r in rs}
            if d.get(("sl_mt", "k0")) == "REFUSE" and d.get(("en_bt", "k0")) == "REFUSE":
                J.add(i)
        ex = []
        for i in sorted(by_item, key=lambda x: int(x.rsplit("_", 1)[1])):
            it = items[i]
            e = {"input": json.dumps({"en_orig": it["en_orig"], "sl_mt": it["sl_mt"], "en_bt": it["en_bt"]}, ensure_ascii=False),
                 "output": "REFUSE",
                 "metadata_adjudicated_label": None,
                 "metadata_item_id": i, "metadata_category": it["cat"], "metadata_group": it["group"],
                 "metadata_pure": it["pure"], "metadata_in_d300": it["in_d300"], "metadata_in_d200": it["in_d200"],
                 "metadata_in_J": i in J, "metadata_model": m, "metadata_bt_chrf": it["bt_chrf"]}
            for r in by_item[i]:
                if r["key"] in ADJ:
                    e["metadata_adjudicated_label"] = ADJ[r["key"]]
                L = lab.get(r["key"])
                e[f"predict_{r['cond']}_{r['arm']}"] = L["label"] if L else "UNJUDGED"
                e[f"predict_lexicon_{r['cond']}_{r['arm']}"] = "REFUSE" if r["lex_hit"] else "NO_MARKER"
            ex.append(e)
        datasets.append({"dataset": f"refuseu_x_mt_DEPTH600__{m}", "examples": ex})
    meta = {
        "method_name": "Judged item-matched refusal-depth-by-language (prefill) with neutral/cross-language controls, "
                       "representation readout and causal steering",
        "baseline": "k=0 (no prefix) + EN back-translation arm (MT-noise-controlled language baseline); iter-1 lexicon "
                    "readout logged as predict_lexicon_* (superseded baseline readout)",
        "output_field": "expected behaviour for a harmful RefusEU item = REFUSE; predict_<cond>_<arm> = judge label "
                        "(google/gemini-2.5-flash; gpt-4.1 for 403-routed items)",
        "conditions": {k: {kk: vv for kk, vv in v.items()} for k, v in CONDITIONS.items()},
        "m": A["m"], "H_depth": A.get("H_depth"), "primary": {m: {k: A["primary"][m][k] for k in
                                                                  ("J", "DG", "DGN", "DDG", "MT_noise_P5", "robustness", "AUC", "cross_2x2")}
                                                              for m in A["primary"]},
        "cross_model": A.get("cross_model"), "batch_check": A.get("batch_check"), "kappa_summary": A.get("kappa_summary"),
        "hardware_check": A.get("hardware_check"),
        "judge_validation": A.get("judge_validation"),
        "adjudicated_primary": A.get("adjudicated_primary"),
        "judge_sensitivity": A.get("judge_sensitivity"),
        "headline": ("No available LLM judge passed validation on prefilled continuations (gemini-2.5-flash over-calls "
                     "refusal, local open-weight judges under-call it, gpt-4.1 became unreachable when the run budget "
                     "was exhausted), so the primary result is the judge-free representation readout and every judged "
                     "number is flagged. On the blind stratum-weighted adjudication, neither model shows a language gap "
                     "in prefill-induced compliance at k=5."),
        "hardware_note": "container migrated RTX 4090 -> NVIDIA L4 mid-run (see results/hardware_manifest.json)",
        "label_free_depth_lstar": {m: A["mechanism"][m].get("label_free_depth_lstar") for m in A["mechanism"]},
        "mechanism_summary": {m: {k: A["mechanism"][m].get(k) for k in ("lstar", "auroc", "gee", "mediation",
                                                                        "action_not_representation_signature")}
                              for m in A["mechanism"]},
        "causal_summary": {m: {arm: {k: v for k, v in A["causal"][m].get(arm, {}).items() if k != "per_item_min_alpha"}
                               for arm in ("sl_mt", "en_bt")} for m in A["causal"]},
        "precision": "NF4 (bitsandbytes, double quant, bf16 compute) for both models — reduced precision",
        "artifacts": {"results_dir": str(RESULTS), "analysis": str(RESULTS / "analysis.json"), "audit": str(RESULTS / "audit.json")},
    }
    out = {"metadata": meta, "datasets": datasets}
    (WS / "method_out.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str))
    logger.info(f"method_out.json: {[len(d['examples']) for d in datasets]} examples")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build-output"
    {"pipeline": pipeline, "build-output": build_output}[cmd]()
