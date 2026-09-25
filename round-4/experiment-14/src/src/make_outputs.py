#!/usr/bin/env python3
"""method_out.json in exp_gen_sol_out format: one example per generation row (input = user turn, output = response)
with metadata (item, kind, model, in/out language, lambda, cond, detected language, labels, ASR, translation).
Grouped into datasets by model. Also writes full/mini/preview variants."""
from __future__ import annotations

import json

from loguru import logger

from common import RESULTS, ROOT, read_jsonl, setup_logging


def pred_of(r: dict) -> str:
    return r.get("L_primary") or "UNLABELLED"


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("make_outputs")
    rows = read_jsonl(RESULTS / "rows_final.jsonl")
    A = json.loads((RESULTS / "analysis.json").read_text())
    by = {}
    for r in rows:
        ex = {"input": r["text"], "output": r["response"],
              "predict_primary_judge": pred_of(r),
              "predict_second_judge": r.get("L_second") or "NOT_IN_FRAME",
              "predict_ttj": r.get("L_ttj") or "NA",
              "metadata_item_id": r["item_id"], "metadata_kind": r["kind"], "metadata_source": r.get("source"),
              "metadata_model": r["model"], "metadata_in_lang": r["in_lang"], "metadata_out_lang": r["out_lang"],
              "metadata_lambda": r["lambda"], "metadata_dose": r["dose"], "metadata_cond": r["cond"],
              "metadata_lang_detected": r["lang_detected"], "metadata_lang_conf": r["lang_conf"],
              "metadata_degenerate": bool(r["degenerate"]), "metadata_n_new_tokens": r["n_new_tokens"],
              "metadata_adjudicated": r.get("L_adj"),
              "metadata_asr_score": (r.get("asr") or {}).get("score"),
              "metadata_translated_response": r.get("translated_response")}
        by.setdefault(r["model"], []).append(ex)
    out = {"metadata": {
        "title": "Does Slovene refusal follow the prompt or the reply? Input x output language crossing under "
                 "partial-dose English abliteration (Gemma-3-12B-IT vs GaMS3-12B-Instruct)",
        "method": "exp9 Heretic LoRA as lambda-scaled bf16 hooks on NF4 models; 3x3 input x output language grid; "
                  "lambda 0 / lambda_lo / lambda_hi bracketing EN->EN refusal 50%",
        "baselines": ["unedited model (lambda 0)", "norm-matched random-direction edit at lambda_hi",
                      "sibling model GaMS3 (G3 per cell)", "public English-abliterated Gemma checkpoint(s) (C-EXT)",
                      "EN_orig vs EN_BT (MT noise)"],
        "decisions": {k: v.get("mechanism_SL") for k, v in A.get("decisions", {}).items()},
        "robust_call_SL": A.get("robust_call_SL"),
        "analysis_file": "results/analysis.json"},
        "datasets": [{"dataset": f"inout_grid_{m}", "examples": ex} for m, ex in sorted(by.items())]}
    p = ROOT / "method_out.json"
    p.write_text(json.dumps(out, ensure_ascii=False))
    (ROOT / "full_method_out.json").write_text(json.dumps(out, ensure_ascii=False))
    mini = {"metadata": out["metadata"], "datasets": [{"dataset": d["dataset"], "examples": d["examples"][:3]}
                                                       for d in out["datasets"]]}
    (ROOT / "mini_method_out.json").write_text(json.dumps(mini, ensure_ascii=False, indent=1))

    def trunc(o):
        if isinstance(o, str):
            return o[:200]
        if isinstance(o, list):
            return [trunc(x) for x in o]
        if isinstance(o, dict):
            return {k: trunc(v) for k, v in o.items()}
        return o
    (ROOT / "preview_method_out.json").write_text(json.dumps(trunc(mini), ensure_ascii=False, indent=1))
    logger.info(f"method_out.json: {sum(len(d['examples']) for d in out['datasets'])} examples, "
                f"{p.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
