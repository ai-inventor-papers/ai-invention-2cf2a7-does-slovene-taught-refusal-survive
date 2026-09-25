#!/usr/bin/env python3
"""method_out.json (exp_gen_sol_out): one example per generated FINAL row, grouped into one dataset per model
(input = the user turn, output = the model response). Baseline = cond 'orig' (lambda 0, the unedited model); method =
the saved English-only Heretic edit (cond 'edit', lambda 1.0, and lambda_gate when A1 added it); controls = 'rand1'
(norm-matched random direction) and the 256-token sensitivity rows. predict_* = the benchmark-protocol verdicts on that
row (strings); metadata_* = item / condition / readout fields, plus the blind author-model adjudication if sampled."""
from __future__ import annotations

import json

from loguru import logger

from common import ADJ, GENS, RESULTS, ROOT, load_adj_key, read_gens, read_jsonl, setup_logging


def s(x) -> str:
    return "NA" if x is None else str(x)


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("make_outputs")
    rows = read_jsonl(RESULTS / "rows_final.jsonl")
    text = {}
    for m in ("gemma_it", "gams3_it"):
        for g in read_gens(GENS / f"{m}.jsonl"):
            text[g["key"]] = (g["prompt"], g["response"])
    adj = {}
    K = load_adj_key()
    if K and (ADJ / "labels.jsonl").exists():
        key = K["aid_to_key"]
        for r in read_jsonl(ADJ / "labels.jsonl"):
            adj[key[r["aid"]]] = r
    by: dict[str, list] = {}
    for r in rows:
        p, resp = text[r["key"]]
        a = adj.get(r["key"])
        ex = {"input": p, "output": resp,
              "predict_asr_benchmark_protocol": "unsafe" if r["asr"] == 1 else ("safe" if r["asr"] == 0 else "NA"),
              "predict_llamaguard3": s(r["lg_unsafe"]), "predict_polyguard_harmful": s(r["pg_unsafe"]),
              "predict_qwen3guard": s(r["q3g_label"]), "predict_polyguard_refusal": s(r["pg_refusal"]),
              "predict_strongreject_ft": s(r["sr_score"]),
              "metadata_key": r["key"], "metadata_item_id": r["item_id"], "metadata_pair_id": r["pair_id"],
              "metadata_lang": r["lang"], "metadata_model": r["model"], "metadata_cond": r["cond"],
              "metadata_ctag": r["ctag"], "metadata_lambda": r["lambda"], "metadata_max_new_tokens": r["max_new"],
              "metadata_role": ("baseline" if r["ctag"] == "orig" else "method" if r["ctag"] in ("edit1", "gate")
                                else "control"),
              "metadata_hazard": r["hazard"], "metadata_group": r["group"], "metadata_labse_cos": r["labse_cos"],
              "metadata_pair_pure": r["pair_pure"], "metadata_lingua_lang": r["lingua_lang"],
              "metadata_degenerate": r["degenerate"], "metadata_empty": r["empty"],
              "metadata_finish_reason": r["finish_reason"], "metadata_n_new_tokens": r["n_new_tokens"],
              "metadata_lg_p_unsafe": r["lg_p_unsafe"], "metadata_lg_cats": r["lg_cats"],
              "metadata_q3g_refusal": r["q3g_refusal"], "metadata_asr_source": r["asr_source"],
              "metadata_asr_loose": r["asr_loose"], "metadata_certified_refusal": r["certified_refusal"],
              "metadata_adjudicated": a is not None}
        if a:
            ex.update({"metadata_adj_harmful": a["harmful"], "metadata_adj_cls4": a["cls4"], "metadata_adj_p1": a["p1"],
                       "metadata_adj_who": "author-model (LLM, NOT human)"})
        by.setdefault(r["model"], []).append(ex)
    A = json.loads((RESULTS / "analysis.json").read_text())
    out = {"metadata": {"method_name": "Saved English-only Heretic edit (exp9 LoRA r=3) vs original, RefusEU FINAL natural prompts",
                        "baseline": "original model (lambda 0)", "readout": "RefusEU guard-ensemble ASR (LG3 + PolyGuard, "
                        "Qwen3Guard-Gen-8B adjudicates disagreements; R0 substitute for gpt-4o-mini)",
                        "statements": A["statements"], "protocol_sha256": (ROOT / "protocol.sha256").read_text().split()[0]},
           "datasets": [{"dataset": f"refuseu_eval_FINAL__{m}", "examples": v} for m, v in by.items()]}
    (ROOT / "method_out.json").write_text(json.dumps(out, ensure_ascii=False))
    logger.info(f"method_out.json: {sum(len(v) for v in by.values())} examples")


if __name__ == "__main__":
    main()
