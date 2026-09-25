#!/usr/bin/env python3
"""ALT-3 persona-gate screen: method (persona-direction ablation, late band) vs baselines/controls (original model,
early-band ablation, isotropic + variance-matched random ablation, language-identity ablation), GaMS3-12B-Instruct vs
Gemma-3-12B-IT sibling control. The heavy lifting lives in src/ (see run_pipeline.sh); this script assembles
method_out.json (exp_gen_sol_out schema) from results/analysis.json and the per-item JSONL.

Per-example rows: one per SCORE-400 pair x model x language; input = the prompt, output = expected behaviour for a
RefusEU harmful prompt, predict_* = the model's greedy 64-token response under each condition, metadata_* = R/s per
condition, category, dose group."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from loguru import logger

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from common import DATA, ITEMS, RES, read_jsonl, setup_logging  # noqa: E402

COND_NAMES = {"C0": "original", "C1": "persona_ablation_late", "C2": "persona_ablation_early",
              "C3": "iso_random_ablation_late", "C4": "varmatch_random_ablation_late", "C5": "langid_ablation_late"}


def build_datasets() -> list[dict]:
    s4 = read_jsonl(DATA / "score400.jsonl")
    mt = {r["pair_id"]: r["prompt_slmt"] for r in read_jsonl(DATA / "score400_mt_sl.jsonl")}
    judge = {}
    jp = RES / "judge_labels.jsonl"
    if jp.exists():
        for r in read_jsonl(jp):
            if r["task"] == "refusal" and not r.get("harmless"):
                judge[(r["model"], r["condition"], r["lang"], r["pair_id"])] = r["judge_label"]
    ds = []
    for model, mname in [("gams", "GaMS3-12B-Instruct"), ("gemma", "Gemma-3-12B-IT")]:
        cells = {}
        for c in COND_NAMES:
            f = ITEMS / f"{model}__{c}.jsonl"
            if f.exists():
                for r in read_jsonl(f):
                    cells[(c, r["lang"], r["pair_id"])] = r
        for lang, lname in [("en", "EN"), ("sl", "SL (RefusEU native)"), ("slmt", "SL-MT (NLLB translation of EN)")]:
            ex = []
            for p in s4:
                if ("C0", lang, p["pair_id"]) not in cells:
                    continue
                prompt = mt[p["pair_id"]] if lang == "slmt" else p[f"prompt_{lang}"]
                e = {"input": prompt,
                     "output": f"refuse (RefusEU harmful prompt, Llama-Guard category {p['category']})",
                     "metadata_pair_id": p["pair_id"], "metadata_category": p["category"],
                     "metadata_dose_group": p["dose_group"], "metadata_fifth": p["fifth"], "metadata_model": model,
                     "metadata_lang": lang}
                for c, cn in COND_NAMES.items():
                    r = cells.get((c, lang, p["pair_id"]))
                    if r is None:
                        continue
                    e[f"predict_{cn}"] = r["response"]
                    e[f"metadata_R_lexv1_{c}"] = r["R_lexv1"]
                    e[f"metadata_s_{c}"] = round(r["s"], 4)
                    e[f"metadata_resp_lang_{c}"] = r["resp_lang"]
                    jl = judge.get((model, c, lang, p["pair_id"]))
                    if jl is not None:
                        e[f"metadata_judge_{c}"] = jl
                ex.append(e)
            if ex:
                ds.append({"dataset": f"RefusEU SCORE-400 | {mname} | {lname}", "examples": ex})
    return ds


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("method")
    an = json.loads((RES / "analysis.json").read_text())
    prot = json.loads((ROOT / "protocol.json").read_text())
    v = an["verdict_primary"]
    vb = {"candidate": "ALT-3", "signature": "TD* = min(TD(C2 early), TD(C3 iso-random))",
          "readout": an["primary_readout_per_model"], "value": v.get("TDstar", {}).get("point"),
          "ci95": v.get("TDstar", {}).get("ci95"), "threshold_m": v.get("threshold_m"), "z_c": v.get("z_c"),
          "z_c_abs_version": v.get("z_c_abs_version"), "MDE": v.get("MDE"), "survives": v.get("survives"),
          "label": v.get("label"), "conditions": v.get("conditions"), "direction_note": v.get("direction_note"),
          "s_coprimary": an.get("verdict_s"), "ceiling_rule_triggered": an.get("ceiling_rule_triggered"),
          "manipulation_check": {k: {"PASS": mc.get("PASS"), "criteria": mc.get("criteria"),
                                     "judge_criteria": mc.get("judge_criteria")} for k, mc in an["manipulation_checks"].items()},
          "chosen_construction": prot["frozen"]["chosen_construction"],
          "reduced_scope_labels": ["NF4 4-bit (both models)", "SCORE-400 not full SCORE", "local open-weight judge "
                                   "(Qwen2.5-7B-Instruct) instead of gemini-2.5-flash (OpenRouter daily limit)",
                                   "RefusEU SL prompts are generated variants (not translations) + NLLB-MT SL robustness cell",
                                   "no human audit", "overlap_unknown (eval-split near-duplicates not dropped)",
                                   "late-third window per spec", "NVIDIA L4 GPU"]}
    out = {"metadata": {"method_name": "ALT-3 persona-gate screen (own-name persona direction ablation)",
                        "description": ("Does a Slovene-taught own-name persona direction gate Slovene refusal in "
                                        "GaMS3-12B-Instruct relative to its base family Gemma-3-12B-IT? Triple difference "
                                        "of the (SL-EN) refusal log-odds shrink under late persona ablation vs early/random "
                                        "ablation, GaMS minus Gemma."),
                        "protocol_sha256": (ROOT / "protocol.sha256").read_text().split()[0],
                        "verdict": vb, "m": an["m"], "m_s": an["m_s"],
                        "headline": {"DiD_ref_C0_primary": an["primary"].get("DiD_ref_C0"),
                                     "DiD_ref_C0_s": an["s_coprimary"].get("DiD_ref_C0"),
                                     "TD_by_control_primary": an["primary"].get("TD"), "G_primary": an["primary"].get("G"),
                                     "shrink_primary": an["primary"].get("shrink"), "rates_primary": an["primary"].get("rates"),
                                     "TD_by_control_s": an["s_coprimary"].get("TD"), "G_s": an["s_coprimary"].get("G")},
                        "robustness_verdicts": {k: {"label": r["verdict"].get("label"), "TDstar": r["verdict"].get("TDstar")}
                                                for k, r in an["robustness"].items()},
                        "analysis_file": "results/analysis.json",
                        "kept_artifacts": {"directions": "results/directions/{gams,gemma}.npz",
                                           "items": "results/items/*.jsonl", "analysis": "results/analysis.json",
                                           "workspace": str(ROOT)}},
           "datasets": build_datasets()}
    (ROOT / "method_out.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    logger.info(f"method_out.json written: {sum(len(d['examples']) for d in out['datasets'])} examples; verdict {vb['label']}")


if __name__ == "__main__":
    main()
