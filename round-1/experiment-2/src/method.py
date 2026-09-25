#!/usr/bin/env python3
"""Pipeline driver + method_out.json builder for the ALT-2 / C4 screen (GaMS3 vs Gemma-3, NF4).

The GPU/CPU steps live in src/ and are run in this order (each resumable, each writes results/...):
  src/data_build.py -> src/mt_nllb.py -> src/make_protocol.py -> src/smoke_test.py ->
  src/base_geometry.py --model pt|gb -> src/base_stats.py --model pt|gb ->
  src/instruct_run.py --model gemma|gams -> src/judge.py -> src/analyze.py -> src/figures.py -> method.py

`python method.py --run-all` executes the whole chain; `python method.py` (default) only assembles method_out.json
from saved results. method_out.json follows the exp_gen_sol_out schema: one dataset per readout, examples keyed by
item x language with the baseline model (Gemma-3-12B-IT, the shared-ancestor sibling) and the method model
(GaMS3-12B-Instruct) as predict_* fields, plus per-example metadata (R, s, s_c, base-geometry projections)."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def rj(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def run_all() -> None:
    steps = [["src/data_build.py"], ["src/mt_nllb.py"], ["src/make_protocol.py"], ["src/smoke_test.py"],
             ["src/base_geometry.py", "--model", "pt"], ["src/base_stats.py", "--model", "pt"],
             ["src/base_geometry.py", "--model", "gb"], ["src/base_stats.py", "--model", "gb"],
             ["src/instruct_run.py", "--model", "gemma"], ["src/instruct_run.py", "--model", "gams"],
             ["src/judge.py"], ["src/analyze.py"], ["src/figures.py"]]
    for s in steps:
        print(">>", " ".join(s), flush=True)
        subprocess.run([PY, *s], cwd=ROOT, check=True)


def build() -> None:
    A = json.loads((ROOT / "results/analysis/analysis.json").read_text())
    pairs = {p["pair_id"]: p for p in rj(ROOT / "data/refuseu_pairs.jsonl")}
    alp = {a["hid"]: a for a in rj(ROOT / "data/alpaca_harmless.jsonl")}
    S = {m: {(r["item"], r["lang"]): r for r in rj(ROOT / f"results/inst_{m}/s_score.jsonl")} for m in ["gemma", "gams"]}
    R4 = {m: {(r["pair_id"], r["lang"]): r for r in rj(ROOT / f"results/inst_{m}/r_score400.jsonl")} for m in ["gemma", "gams"]}
    hmean = A["S2"]["s_harmless_mean"]
    proj = defaultdict(dict)
    for m in ["pt", "gb"]:
        for r in rj(ROOT / f"results/base_{m}/item_proj.jsonl"):
            if r["layer_name"] == "Lpt" and r["dir"] == "pooled" and r["kind"] == "harm":
                proj[(r["item"], r["lang"])][f"harm_z_{m}"] = round(r["harm_z"], 4)
    judge = {r["key"]: r for r in rj(ROOT / "results/shared/judge_labels.jsonl")}

    # dataset 1: SCORE-400 behaviour (generation + lexicon + judge + s)
    ex1 = []
    for (pid, lang), g in sorted(R4["gemma"].items()):
        if (pid, lang) not in R4["gams"]:
            continue
        a, b = g, R4["gams"][(pid, lang)]
        e = {"input": pairs[pid][lang],
             "output": f"REFUSE (RefusEU harmful prompt, gold Llama-Guard category {pairs[pid]['category']})",
             "predict_baseline_gemma3_12b_it": a["text"], "predict_method_gams3_12b_instruct": b["text"],
             "metadata_pair_id": pid, "metadata_lang": lang, "metadata_category": pairs[pid]["category"],
             "metadata_R_lex_gemma": a["R_lex"], "metadata_R_lex_gams": b["R_lex"],
             "metadata_degenerate_gemma": a["degenerate"], "metadata_degenerate_gams": b["degenerate"],
             "metadata_s_gemma": round(S["gemma"][(pid, lang)]["s"], 4), "metadata_s_gams": round(S["gams"][(pid, lang)]["s"], 4),
             "metadata_judge_gemma": judge.get(f"orig|gemma|{lang}|{pid}", {}).get("label"),
             "metadata_judge_gams": judge.get(f"orig|gams|{lang}|{pid}", {}).get("label"),
             **{f"metadata_{k}": v for k, v in proj.get((pid, lang), {}).items()}}
        ex1.append(e)
    # dataset 2: all SCORE harmful pairs, continuous readout s / s_c + base geometry (the ALT-2 regression data)
    ex2 = []
    for (item, lang), g in sorted(S["gemma"].items()):
        if g["kind"] != "harm" or (item, lang) not in S["gams"]:
            continue
        b = S["gams"][(item, lang)]
        ex2.append({"input": pairs[item][lang], "output": "refusal-leaning prefix preference expected (s > 0)",
                    "predict_baseline_gemma3_12b_it": f"s={g['s']:.4f}", "predict_method_gams3_12b_instruct": f"s={b['s']:.4f}",
                    "metadata_pair_id": item, "metadata_lang": lang, "metadata_category": g["category"],
                    "metadata_in_score400": g["in_score400"], "metadata_s_gemma": round(g["s"], 4), "metadata_s_gams": round(b["s"], 4),
                    "metadata_s_c_gemma": round(g["s"] - hmean["gemma"][lang], 4), "metadata_s_c_gams": round(b["s"] - hmean["gams"][lang], 4),
                    **{f"metadata_{k}": v for k, v in proj.get((item, lang), {}).items()}})
    # dataset 3: C4 induction (per hid x lang x direction; R curve over the alpha grid, text at the largest alpha)
    ex3 = []
    ind = {m: rj(ROOT / f"results/inst_{m}/induction.jsonl") for m in ["gemma", "gams"]}
    by = defaultdict(lambda: defaultdict(dict))
    for m in ind:
        for r in ind[m]:
            by[(r["hid"], r["lang"], r["direction"])][m][r["alpha_k"]] = r
    for (hid, lang, d), mm in sorted(by.items()):
        if "gemma" not in mm or "gams" not in mm:
            continue
        kmax = {m: max(mm[m]) for m in mm}
        ex3.append({"input": alp[hid][lang], "output": "COMPLY at alpha=0 (harmless alpaca prompt); refusal induced as alpha grows for a refusal direction",
                    "predict_baseline_gemma3_12b_it": mm["gemma"][kmax["gemma"]]["text"],
                    "predict_method_gams3_12b_instruct": mm["gams"][kmax["gams"]]["text"],
                    "metadata_hid": hid, "metadata_lang": lang, "metadata_direction": d,
                    "metadata_alpha_k": sorted(mm["gemma"]),
                    "metadata_R_by_alpha_gemma": [mm["gemma"][k]["R_lex"] for k in sorted(mm["gemma"])],
                    "metadata_R_by_alpha_gams": [mm["gams"][k]["R_lex"] for k in sorted(mm["gams"])],
                    "metadata_s_by_alpha_gemma": [round(mm["gemma"][k]["s"], 3) for k in sorted(mm["gemma"])],
                    "metadata_s_by_alpha_gams": [round(mm["gams"][k]["s"], 3) for k in sorted(mm["gams"])],
                    "metadata_deg_by_alpha_gemma": [mm["gemma"][k]["degenerate"] for k in sorted(mm["gemma"])],
                    "metadata_deg_by_alpha_gams": [mm["gams"][k]["degenerate"] for k in sorted(mm["gams"])]})
    headline = {k: A.get(k) for k in ["S5", "m"]}
    s1 = A["S1"]
    headline["S1_Lpt"] = {k: v for k, v in s1["Lpt"].items()}
    headline["S1_Lown"] = {k: v for k, v in s1["Lown"].items()}
    headline["S1_layers"] = {"L_pt": s1["L_pt"], "L_gb": s1["L_gb"], "cos_pt_gb_at_Lpt": s1["cos_pt_gb_at_Lpt"],
                             "style_check": s1["style_check"]}
    headline["S2"] = {k: A["S2"][k] for k in ["cells", "DiD", "D", "label", "ceiling_rule_triggered"]}
    headline["S3"] = {k: ({kk: vv for kk, vv in v.items()} if isinstance(v, dict) else v) for k, v in A["S3"].items() if k != "_arrays"}
    s4 = A["S4"]
    headline["S4"] = {k: s4.get(k) for k in ["verdict", "positive_control_pass", "pt_reaches_all_cells", "Delta", "controls",
                                             "baseline_alpha0", "n_bar", "flip_spearman_en_sl", "n_boot"]}
    headline["S4"]["a50_table"] = {k: {"a50": v.get("a50"), "a50_over_Nbar": (v["a50"] / s4["n_bar"][k.split("|")[0]]) if v.get("a50") else None,
                                       "status": v.get("status"), "rel_ec50": v.get("rel_ec50"), "alpha_s0": v.get("alpha_s0"),
                                       "deg_at_a50": v.get("deg_at_a50"), "incoherence_confounded": v.get("incoherence_confounded"),
                                       "frac_never_flipped": v.get("frac_never_flipped")} for k, v in s4["cells"].items()}
    headline["S4"]["a50_ci"] = s4.get("a50_ci")
    headline["S4"]["readout"] = "lexicon (pre-registered); see S4_judge for the co-primary judge readout (D16)"
    sj = A.get("S4_judge", {})
    if "cells" in sj:
        headline["S4_judge"] = {k: sj.get(k) for k in ["verdict", "positive_control_pass", "pt_reaches_all_cells", "Delta",
                                                       "baseline_alpha0", "n_bar", "n_boot"]}
        headline["S4_judge"]["a50_table"] = {k: {"a50": v.get("a50"), "a50_interp": v.get("a50_interp"), "status": v.get("status"),
                                                 "peak_R": v.get("peak_R")} for k, v in sj["cells"].items()}
        headline["S4_judge"]["note"] = "controls (lang-ID, random) judged too; pt NR in all 4 cells under the judge readout"
    headline["S2_judge"] = A.get("S2_judge")
    headline["exploratory"] = {"S1_meanpool": A.get("S1_meanpool_exploratory"), "S1_punct_matched": A.get("S1_punct_matched_exploratory"),
                               "label": "post-freeze exploratory robustness checks; not part of the decision rule"}
    kap = ROOT / "results/shared/kappa.json"
    headline["kappa"] = json.loads(kap.read_text()) if kap.exists() else "NOT COMPUTED"
    meta = {
        "method_name": "ALT-2 base-geometry screen + C4 ancestor-direction induction (SCREEN-SPEC v1, slot 3)",
        "description": "Does the base checkpoint set the EN/SL refusal profile of GaMS3-12B-Instruct vs Gemma-3-12B-IT? "
                       "Baseline = Gemma-3-12B-IT (shared-ancestor sibling, own directions, random / language-ID controls); "
                       "method arm = GaMS3 (base + instruct).",
        "checkpoints": json.loads((ROOT / "config/resolved_revisions.json").read_text()),
        "precision": "bitsandbytes NF4 4-bit, double quant, bf16 compute (REDUCED PRECISION)",
        "hardware": "1x RTX 4090 24 GB",
        "protocol_sha256": (ROOT / "config/protocol.sha256").read_text().split()[0],
        "protocol_addendum": json.loads((ROOT / "config/protocol_addendum.json").read_text()) if (ROOT / "config/protocol_addendum.json").exists() else None,
        "deviations": json.loads((ROOT / "config/protocol.json").read_text())["deviations"],
        "induction_tier": {m: json.loads((ROOT / f"results/inst_{m}/induction_tier.json").read_text())
                           for m in ["gemma", "gams"] if (ROOT / f"results/inst_{m}/induction_tier.json").exists()},
        "mt_comparison_gemini_vs_nllb": json.loads((ROOT / "results/analysis/mt_comparison.json").read_text())
        if (ROOT / "results/analysis/mt_comparison.json").exists() else None,
        "openrouter_spend_usd": round(sum(r.get("cost", 0) or 0 for r in rj(ROOT / "results/shared/openrouter_ledger.jsonl")), 4),
        "headline": headline,
        "audit": json.loads((ROOT / "results/analysis/audit.json").read_text()) if (ROOT / "results/analysis/audit.json").exists() else None,
    }
    out = {"metadata": meta, "datasets": [
        {"dataset": "RefusEU_SCORE400_generation_EN_SL", "examples": ex1},
        {"dataset": "RefusEU_SCORE_all_pairs_refusal_score_s", "examples": ex2},
        {"dataset": "alpaca_harmless_C4_induction", "examples": ex3}]}
    (ROOT / "method_out.json").write_text(json.dumps(out, ensure_ascii=False, default=lambda o: None))
    print(f"method_out.json: {len(ex1)} / {len(ex2)} / {len(ex3)} examples; "
          f"sha256 {hashlib.sha256((ROOT / 'method_out.json').read_bytes()).hexdigest()[:12]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-all", action="store_true")
    a = ap.parse_args()
    if a.run_all:
        run_all()
    build()
