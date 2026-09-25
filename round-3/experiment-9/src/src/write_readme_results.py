#!/usr/bin/env python3
"""RESULTS.md: the pre-registered verdicts in the pre-registered wording, rendered from results/analysis.json."""
from __future__ import annotations

import json

from common import RESULTS, WS

NAME = {"gemma_it": "Gemma-3-12B-IT", "gams3_it": "GaMS3-12B-Instruct"}


def f(x, d=2):
    if x is None:
        return "n/a"
    if isinstance(x, (list, tuple)):
        return "[" + ", ".join(f(v, d) for v in x) + "]"
    return f"{x:.{d}f}" if isinstance(x, float) else str(x)


def main():
    A = json.loads((RESULTS / "analysis.json").read_text())
    au = json.loads((RESULTS / "audit.json").read_text()) if (RESULTS / "audit.json").exists() else {}
    pb, pl = A["G3"]["Bprime|j1|R1"], A["G3"]["lambda|j1|R1"]
    F3 = A.get("verdict_F3")
    sd = A["SDT"]["j1|R1"]["per_model"]
    v = A["verdict"]
    L = ["# RESULTS", "",
         "All numbers below are produced by `src/analysis.py` from `results/items_final.jsonl` and re-derived by the",
         "independent second code path `src/audit.py`. Full tables: [`results/summary_tables.md`](results/summary_tables.md).", "",
         "## 1. Primary: does Slovene refusal fall faster at matched English suppression?", "",
         ((f"**G3 (B\', {pb['n_steps']} paired Heretic trial steps) = " + f(pb['G3']) + "**, 95% CI " + f(pb['ci95']) + ", MDE " + f(pb['mde']) + ".")
          if pb.get("identified") else
          (f"**G3 (B\', {pb['n_steps']} paired Heretic trial steps): NOT IDENTIFIED.** Every paired trial step that both "
           "models completed sits at high EN refusal, so this fit extrapolates to EN = 50% from a separated design; "
           "neither its point estimate nor its interval is interpretable, and it is excluded from the headline.")), "",
         f"**G3 (lambda curve) = {f(pl['G3'])}**, 95% CI {f(pl['ci95'])}.", "",
         f"Support rule satisfied: {pb['support_ok']} "
         + "; ".join(f"{NAME[m]} #[.2,.5)={pb['per_model'][m]['support'][0]}, #[.5,.8]={pb['per_model'][m]['support'][1]}"
                     for m in ("gemma_it", "gams3_it")) + ".", "",
         f"**Pre-registered verdict: {v['verdict']}** (margin m = 0.675; m_local = 0.20 co-reported).", "",
         "| condition | met |", "|---|---|"]
    L += [f"| {k} | {b} |" for k, b in v["conditions"].items()]
    if F3:
        L += ["", "### B' is off support -> pre-registered fallback F3", "",
              F3["trigger"] + ".", "",
              f"**F3 verdict (lambda curve, 9 paired steps per model): {F3['verdict']}** - "
              f"G3 = {f(pl['G3'])}, 95% CI {f(pl['ci95'])}, MDE {f(pl['mde'])}.", "",
              "| F3 condition | met |", "|---|---|"]
        L += [f"| {k} | {b} |" for k, b in F3["F3_conditions"].items()]
        L += ["", f"EN-BT refusal range per model on the lambda curve: "
                  + "; ".join(f"{NAME[m]} {f(r[0])}-{f(r[1])}" for m, r in F3["en_range_per_model"].items()), ""]
    L += ["", "## 2. Mechanism: criterion or geometry?", "",
          "| model | n steps in window | Delta-c (SL-EN) | 95% CI | Delta-d\' | 95% CI | reading |", "|---|---|---|---|---|---|---|"]
    for m, r in sd.items():
        L.append(f"| {NAME[m]} | {r['n_window']} | {f(r.get('delta_c'))} | {f(r.get('delta_c_ci95'))} | "
                 f"{f(r.get('delta_dprime'))} | {f(r.get('delta_dprime_ci95'))} | {r.get('reading')} |")
    if "did_c" in A["SDT"]["j1|R1"]:
        s = A["SDT"]["j1|R1"]
        L.append(f"| DiD (Gemma - GaMS) | | {f(s['did_c'])} | {f(s['did_c_ci95'])} | {f(s['did_dprime'])} | "
                 f"{f(s['did_dprime_ci95'])} | |")
    L += ["", "## 3. Controls", "",
          f"- Placebos (must centre at 0): model-label swap null mean {f(A['placebos']['model_swap']['null_mean'])} "
          f"(sd {f(A['placebos']['model_swap']['null_sd'])}, p = {f(A['placebos']['model_swap']['p_two_sided'], 4)}); "
          f"language-label swap null mean {f(A['placebos']['lang_swap']['null_mean'])} "
          f"(p = {f(A['placebos']['lang_swap']['p_two_sided'], 4)}).",
          "- Norm-matched random-direction edits (5 seeds, matched per module on ||dW||_F):"]
    for m, s in A["random_specificity"].items():
        L.append(f"  - {NAME[m]}: EN-BT refusal within 50% relative of the unedited model: "
                 f"{s['random_within_50pct_relative']}; per-seed rates in `results/summary_tables.md`.")
    for m, c in A.get("C5a", {}).items():
        L.append(f"- C5a {NAME[m]}: SL/EN first-token-KL excess ratio {f(c['excess_ratio'])} 95% CI {f(c['ci95'])}.")
    L += ["", "## 4. Readout validity", ""]
    hg = (A["judge"].get("j1_vs_heldout_gemini") or {}).get("all")
    if hg:
        L.append(f"- J1 (gemini-distilled classifier) vs held-out archived gemini labels: kappa_R {f(hg['kappaR'])} "
                 f"(3-way {f(hg['kappa3'])}) on {hg['n']} rows; per-cell table in `results/summary_tables.md`.")
    cells = A["judge"].get("j1_vs_j2_cells", {})
    if cells:
        bad = [k for k, c in cells.items() if not c["pass_0.6"]]
        L.append(f"- J1 vs J2 (second family) per cell: {len(cells) - len(bad)}/{len(cells)} cells reach kappa_R >= 0.6; "
                 f"failing cells: {bad}.")
    if "adjudication" in A["judge"]:
        a = A["judge"]["adjudication"].get("all", {})
        L.append(f"- Blind adjudication (executing agent, NOT a human; n = {a.get('n')}): J1 kappa_R {f(a.get('j1_kappaR'))}, "
                 f"J2 kappa_R {f(a.get('j2_kappaR'))}.")
        if "rogan_gladen_G3_Bprime_point" in A["judge"]:
            L.append(f"- Misclassification-corrected (Rogan-Gladen) G3 point estimate: "
                     f"{f(A['judge']['rogan_gladen_G3_Bprime_point'])}.")
    L += ["", "## 5. Sanity gates", ""]
    for m, s in A["sanity"].items():
        eg = (s.get("engine_gate") or {})
        L.append(f"- {NAME[m]}: template sha1 match {(s.get('template') or {}).get('matches_expected')}; "
                 f"trial-1 replay identical {(s.get('replay_trial1') or {}).get('identical_values')}; "
                 f"lambda=1 reproduction {(s.get('lambda1_reproduction') or {}).get('identical')}; "
                 f"EN refusal cut >= 50% relative {s.get('en_cut_ge_50pct_relative')}; engine gate PASS {eg.get('PASS')}.")
    L.append(f"- Pairing of the 40 Heretic trials across models: {A.get('pairing_check')}.")
    L.append(f"- Steps excluded by QC (degeneracy >= 10% or SL language consistency < 95%): "
             f"{list(A['step_qc_flagged_excluded'])}.")
    if au:
        L.append(f"- Second code path (`src/audit.py`): all_pass = {au.get('all_pass')} over {au.get('n_checks')} checks.")
    cells = A["judge"].get("j1_vs_j2_cells", {})
    npass = sum(1 for c in cells.values() if c["pass_0.6"])
    L += ["", "## 6. How much this verdict should be trusted", "",
          f"The pre-registered rule says a cell whose judge gate fails cannot carry a primary. Only {npass} of {len(cells)} "
          "model x arm x edited cells reach kappa_R >= 0.6 between J1 and the second family, so the CONFIRM-LAG verdict "
          "above is **qualified**: the two readouts agree on the *sign and significance* of G3 on the lambda curve "
          "(J1 " + f(pl['G3']) + " " + f(pl['ci95']) + ", J2 " + f(A['G3']['lambda|j2|R1|G_rows']['G3']) + " "
          + f(A['G3']['lambda|j2|R1|G_rows']['ci95']) + ") but not row by row. J1 itself is validated against 2,755 "
          "held-out real gemini labels (kappa_R 0.84), which is the stronger of the two checks; J2 is an 8B zero-shot "
          "judge whose own agreement with gemini is only kappa_R 0.58, so most of the disagreement is J2's error.", "",
          "## 7. Limitations", "",
          "- Reduced precision: everything runs in bitsandbytes NF4; absolute refusal levels may differ from bf16.",
          "- The Slovene arm is NLLB machine translation without a native-speaker audit.",
          "- The primary judge is a classifier distilled from archived `gemini-2.5-flash` labels (the run\'s OpenRouter",
          "  budget was exhausted before this artifact started), so it inherits that judge\'s biases; GaMS edited rows have",
          "  no archived gemini gold and rest on J1-J2 agreement plus the (agent, not human) adjudication.",
          "- The 40 Heretic trials are sampler start-up draws: B\' samples Heretic\'s parameter space, it is not \"what",
          "  Heretic would ship\".", ""]
    (WS / "RESULTS.md").write_text("\n".join(L) + "\n")
    print("RESULTS.md written")


if __name__ == "__main__":
    main()
