#!/usr/bin/env python3
"""S10: method_out.json in the exp_gen_sol_out schema. One example per FINAL prompt (set x arm x item); output = the
expected behaviour (REFUSE for harmful RefusEU-x / HARD-unsafe items, COMPLY for benign HARD items, ANSWER for
identity); predict_<model>_<condition> = the primary judge label (Qwen3-14B, REFUSE/PARTIAL/COMPLY) of that model's
response ('NA' when not generated). All statistics go into top-level metadata (analysis.json headline subset)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from common import RESULTS, ROOT


def ident(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", s)


def main() -> None:
    d = pd.read_parquet(RESULTS / "rows_final.parquet")
    A = json.loads((RESULTS / "analysis.json").read_text())
    d["cond_tag"] = d.apply(lambda r: r["condition"] if r["condition"] in ("orig", "public")
                            else f"{r['condition']}{r['lambda']:g}", axis=1).map(ident)
    d["pcol"] = "predict_" + d.model + "_" + d.cond_tag
    lab = d.label_q.fillna("UNJUDGED").astype(str)
    d["pred"] = lab
    datasets = []
    for set_, g in d.groupby("set"):
        piv = g.pivot_table(index=["gid"], columns="pcol", values="pred", aggfunc="first")
        meta = g.drop_duplicates("gid").set_index("gid")
        ex = []
        for gid, row in piv.iterrows():
            m = meta.loc[gid]
            harmful = bool(m["is_harmful"]) if m["is_harmful"] is not None else None
            out = "ANSWER" if set_ == "identity" else ("REFUSE" if harmful else "COMPLY")
            e = {"input": str(m["prompt_text"]), "output": out,
                 "metadata_gid": gid, "metadata_item_id": str(m["item_id"]), "metadata_arm": str(m["arm"]),
                 "metadata_prompt_lang": str(m["prompt_lang"]), "metadata_is_harmful": harmful}
            for k in ("hazard", "group", "source", "category", "l3_chrf", "bt_chrf"):
                if k in m and pd.notna(m[k]):
                    e[f"metadata_{k}"] = m[k] if not hasattr(m[k], "item") else m[k].item()
            for c, v in row.items():
                if isinstance(v, str):
                    e[c] = v
            ex.append(e)
        datasets.append({"dataset": f"{set_}_FINAL", "examples": ex})
    head = {k: A.get(k) for k in ("verdict_C_LAG", "verdict_C_MOD", "protocol_sha256", "n_rows")}
    head["G3"] = {k: {kk: v.get(kk) for kk in ("G3", "ci95", "ci90", "mde", "se")} for k, v in A.get("G3", {}).items()
                  if isinstance(v, dict)}
    head["two_point_q_R"] = A.get("two_point", {}).get("q_R")
    head["public_q_R"] = A.get("public", {}).get("q_R")
    head["mcnemar_q_R"] = A.get("mcnemar", {}).get("q_R")
    head["gates"] = A.get("gates")
    meta = {"method_name": "C-LAG confirmation: English Heretic edit (iter-1 LoRA, lambda-scaled) scored on "
                           "untouched FINAL items in EN_BT / SL_MT / L3_MT (Hungarian)",
            "baseline": "unedited models (condition orig) on identical items and decoding; sibling model contrast "
                        "GaMS3 vs Gemma-3-IT; public English-abliterated checkpoints",
            "judge": "Qwen3-14B local (primary; OpenRouter relay budget exhausted); Mistral-Small-24B second family",
            "predict_field_convention": "predict_<model>_<condition><lambda> = primary judge label",
            "headline": head, "full_analysis": "results/analysis.json", "protocol": "protocol.yaml"}
    out = {"metadata": meta, "datasets": datasets}
    import os
    (Path(os.environ.get("AII_OUT_DIR", str(ROOT))) / "method_out.json").write_text(json.dumps(out, ensure_ascii=False, default=str))
    print(f"method_out.json: {sum(len(x['examples']) for x in datasets)} examples in {len(datasets)} datasets")


if __name__ == "__main__":
    main()
