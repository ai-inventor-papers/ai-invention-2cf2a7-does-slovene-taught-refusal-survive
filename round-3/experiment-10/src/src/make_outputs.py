#!/usr/bin/env python3
"""S11: method_out.json in the exp_gen_sol_out schema. One example per TEST row (input = prompt, output = response,
predict_* = judge labels, metadata_* = model / block / arm / condition / step / lambda ...), datasets = model x block.
The aggregated analysis (headline numbers + verdicts) goes into top-level metadata."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import MODEL_ORDER, RESULTS, WS, read_jsonl, row_key  # noqa: E402

J1, J2 = "surrogate/gemini", "local/qwen3-14b"


def main():
    import judge as J
    req = J.req_map()
    lab = {}
    for r in read_jsonl(RESULTS / "judge_labels.jsonl"):
        lab.setdefault(r["judge"], {})[r["row_key"]] = r["label"]
    A = json.loads((RESULTS / "analysis.json").read_text())
    datasets = []
    for M in MODEL_ORDER:
        for blk in ("induce", "addon"):
            rows = read_jsonl(RESULTS / "test" / M / f"{blk}.jsonl")
            if not rows:
                continue
            ex = []
            for r in rows:
                k = row_key(r)
                e = {"input": req[(r["item_id"], r["arm"])], "output": r["response"],
                     "predict_surrogate_gemini": lab.get(J1, {}).get(k, "UNJUDGED"),
                     "predict_qwen3_14b_sample": lab.get(J2, {}).get(k, "NOT_IN_SAMPLE"),
                     "predict_lexicon": "REFUSE" if r["lex"] else "NOT_REFUSE",
                     "predict_s1_proxy": ("REFUSE" if r["s1"] > 0 else "NOT_REFUSE") if r.get("s1") is not None else "NA",
                     "metadata_model": M, "metadata_block": blk, "metadata_item_id": r["item_id"], "metadata_arm": r["arm"],
                     "metadata_lang": r["lang"], "metadata_condition": r["cond"], "metadata_step": r["step"],
                     "metadata_degenerate": r["degenerate"], "metadata_lang_ok": r["lang_ok"], "metadata_s1": r.get("s1")}
                if blk == "induce":
                    e.update({"metadata_alpha": r.get("alpha"), "metadata_layer": r.get("layer"), "metadata_kl_first": r.get("kl_first"),
                              "metadata_manip_proj": r.get("manip_proj")})
                else:
                    e.update({"metadata_set": r.get("set"), "metadata_lambda": r.get("lam"), "metadata_direction": r.get("dir")})
                ex.append(e)
            datasets.append({"dataset": f"{M}_{blk}", "examples": ex})
    head = {"method_name": "Slovene caution direction: geometry + induction + add-on neutralisation + RQ4 (iter-3 dir3)",
            "judges": {"primary": J1, "second": J2 + " (stratified 20% sample)", "note": "OpenRouter run budget exhausted -> plan F1: local Qwen3-14B failed the gemini gate on edited rows; primary = TF-IDF emulator of archived gemini labels (grouped-CV gated), checked by blind agent adjudication (author model, not human)"},
            "final_verdict": A.get("final_verdict"), "verdict_table": A.get("verdict_table"),
            "dev_decisions": A.get("dev_decisions"), "geometry_contrast": A.get("geometry", {}).get("contrast_gemma_minus_gams"),
            "G3_op": A.get("G3_op"), "induction_contrast": A.get("induction_contrast"),
            "analysis_file": "results/analysis.json", "audit_file": "results/audit.json"}
    out = {"metadata": head, "datasets": datasets}
    (WS / "method_out.json").write_text(json.dumps(out, ensure_ascii=False, default=str))
    print(f"method_out.json: {sum(len(d['examples']) for d in datasets)} examples in {len(datasets)} datasets")


if __name__ == "__main__":
    main()
