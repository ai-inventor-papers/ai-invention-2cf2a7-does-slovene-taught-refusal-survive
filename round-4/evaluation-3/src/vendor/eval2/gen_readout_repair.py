#!/usr/bin/env python3
"""Generate READOUT_REPAIR.md: every iter-1/2 number the paper might quote -> validated replacement + status."""
from __future__ import annotations

import json
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
A = json.loads((WS / "results/eval_results.json").read_text())
P = A["step1_selection"]["primary"]
lag = A["step3_lag"]


def g(curve, rn, stat="G3_50"):
    r = lag.get(curve, {}).get(rn, {})
    if not isinstance(r, dict) or "status" in r:
        return None
    v = r.get(stat)
    return v if isinstance(v, dict) else None


def fmt(v):
    if not v:
        return "n/a"
    ci = v.get("CI95")
    return f"{v['est']:+.2f} [{ci[0]:+.2f}, {ci[1]:+.2f}]" if ci else f"{v['est']:+.2f}"


def status(old, new, m=0.6752):
    if not new:
        return "UNCITABLE (no validated coverage)"
    ci = new.get("CI95")
    if ci is None:
        return "UNCERTAIN"
    if old < 0 and ci[1] < 0:
        return "SURVIVES (sign holds, CI excludes 0)"
    if old < 0 and ci[0] <= 0 <= ci[1]:
        return "SHRINKS/INCONCLUSIVE (CI now includes 0)"
    if old < 0 and ci[0] > 0:
        return "REVERSES"
    return "CHANGED"


# choose the headline statistic per curve (G3_50 if on support else IG)
def headline(curve, rn):
    r = lag.get(curve, {}).get(rn, {})
    if isinstance(r, dict) and r.get("on_support") is False and g(curve, rn, "IG"):
        return g(curve, rn, "IG"), "IG (integrated gap; B support rule failed, G3@50% extrapolated)"
    return g(curve, rn, "G3_50"), "G3 at EN 50%"

Bp, Bp_stat = headline("B", "primary_R")
Ap, Ap_stat = headline("A1", "primary_R")
Brg = g("B", "primary_R_RG")
sel = A["step1_selection"]["table"]
clag = A["C_LAG_screen"]

rows = [
    ("exp8 G3 curve B (lexicon)", "-2.36 [-3.18, -1.62]", "lexicon (kappa~0.34 vs gemini on Gemma-EN)",
     f"{fmt(Bp)} [{P}, {Bp_stat}]; RG-corrected {fmt(Brg)}", status(-2.36, Bp),
     "iter_2/.../gen_art_experiment_8/results/analysis.json G3.B"),
    ("exp8 G3 curve A1 (lexicon)", "-0.19 [-1.03, 0.78]", "lexicon",
     f"{fmt(Ap)} [{P}, {Ap_stat}]", status(-0.19, Ap),
     "exp8 analysis.json G3.A1"),
    ("exp8 'Llama judge' cross-model readout", "substitute local judge (Llama-3.1-8B, kappa 0.52 vs gemini)",
     "Llama-8B on both models", f"replaced by {P} (calib kappa vs gemini {sel.get(P,{}).get('kappa_R')}); "
     f"Llama-8B B G3 = {fmt(g('B','llama8b_R'))}", "SUPERSEDED",
     "exp8 analysis.json primary_readout"),
    ("exp8 gemini Gemma-only SL-minus-EN pp at EN50 (B)", "+35.5 pp", "gemini (Gemma rows only; GaMS never judged)",
     f"per-model lag now computed for BOTH models; see results eval_results.json step3_lag", "CONTEXTUALISED",
     "exp8 analysis.json gemma_judge_only.B.SL_minus_EN_pp_at_EN50"),
    ("exp8 gemini Gemma-only pp at EN50 (A1)", "+40.2 pp", "gemini (Gemma only)", "see step3_lag per-model", "CONTEXTUALISED",
     "exp8 analysis.json gemma_judge_only.A1"),
    ("iter-1 screen lexicon G3", "-1.86", "iter-1 lexicon", f"{fmt(Bp)} ({P})", status(-1.86, Bp),
     "hypothesis text / iter-1"),
    ("exp5 HARD DiD_c (criterion shift)", "+0.52 [0.38, 0.68]", "Qwen3-14B (exp5 FINAL)",
     f"reproduced in STEP 6 S1 under Qwen3-14B: {fmt((A['step6_meta']['S1_exp5_FINAL'].get('R|q14') or {}).get('DiD_c'))}",
     "REPLICATED (confirmatory, reported separately)", "exp5 analysis_final.json C2_hard_sdt.DiD_c"),
    ("exp7 Gemma safe-SL over-refusal", "+0.24", "Mistral-24B (exp7)",
     f"STEP 6 S2 DiD_c (gemini) {fmt((A['step6_meta']['S2_exp7_DEV'].get('R|gem') or {}).get('DiD_c'))}",
     "RELATED (criterion-shift meta S2)", "exp7 analysis.json"),
]

md = ["# READOUT_REPAIR — every iter-1/2 number mapped to its validated replacement",
      "",
      "**SCREEN REPAIR (MODE L).** exp8 saved 24,000 responses; this artifact re-judges them with local open-weight judges "
      f"(primary **{P}**) and a blind author-model adjudication (NOT human), because the shared OpenRouter budget is exhausted. "
      "Sign convention: G3 = (GaMS − Gemma) Slovene refusal log-odds at matched English refusal; **negative = de-censoring "
      "strips GaMS's Slovene refusal faster than Gemma's** (the original claim).",
      "",
      f"**C-LAG screen holds under validated judges: {clag['holds']}.** Rule: {clag['rule']}",
      "Conditions: " + ", ".join(f"{k}={v}" for k, v in clag["conditions"].items()),
      "",
      "| iter-1/2 quantity | old value | old readout | validated replacement | status | source |",
      "|---|---|---|---|---|---|"]
for r in rows:
    md.append("| " + " | ".join(str(x) for x in r) + " |")
md += ["",
       "## Reading",
       f"- The exp8 lexicon B value (−2.36) and A1 value (−0.19) are **reproduced exactly** by the imported estimator "
       "(unit test `exp8_lexicon_B_reproduced`), so any change below is the readout, not the code.",
       f"- Primary judge selection: {A['step1_selection']['why']}",
       "- On the 240 blind-adjudicated EDITED rows, **all** instruments (gemini, local judges, lexicon) agree only weakly "
       "with careful adjudication, and the errors are model- and language-dependent — see `judge_error_matrices.json` and "
       "`results/eval_results.json step2_characterise`. This is why the corrected estimate carries wide uncertainty and why "
       "the lexicon headline cannot be taken at face value.",
       "- The bias tipping point (`step5_tipping`) states how much extra false-REFUSE in Gemma-SL (or false-COMPLY in "
       "GaMS-SL) would be needed to move the lag to −m or to 0, compared with the measured differential bias.",
       "- Full numbers: `results/eval_results.json`; figures in `figures/`; independent re-derivation in `work/rederive.json`."]
(WS / "READOUT_REPAIR.md").write_text("\n".join(md))
print("wrote READOUT_REPAIR.md; C-LAG holds:", clag["holds"])
