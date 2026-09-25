#!/usr/bin/env python3
"""Figures from results/analysis_final.json (+ items_final.jsonl). PDF + PNG into figures/.
 fig1_forest: all pre-registered contrasts with 95% CI and +/-margin bands
 fig2_tradeoff: OR-Bench-style trade-off plane (F = refusal on safe, H = refusal on unsafe) per model x arm, arrows EN->SL
 fig3_dose: per-category DiD_ref vs log2(EN dose + 1)
 fig4_identity: identity self-name x maker distribution per model x language
 fig5_rates: refusal rates per model x set x arm with Wilson 95% CIs
"""
from __future__ import annotations

import json
from collections import Counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from common import FIG, PROTO, RESULTS, read_jsonl  # noqa: E402

plt.rcParams.update({"font.size": 9, "pdf.fonttype": 42, "ps.fonttype": 42, "axes.spines.top": False,
                     "axes.spines.right": False})
C_GEM, C_GAMS = "#4C72B0", "#C44E52"


def save(fig, name):
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(FIG / f"{name}.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def forest(A, add):
    s = A["C2_refuseu_sensitivities"]
    h = A["C2_hard_sdt"]["primary_SLMT_vs_ENBT"]
    rows = [("C1  DiD_id (own name, identity items)", A["C1"]["identity"]["DiD_id"], add["m_id"]),
            ("C1  DiD_id (control items)", A["C1"]["control"].get("DiD_id"), add["m_id"]),
            ("C2  DiD_ref (RefusEU natural, all)", A["C2_refuseu"]["DiD_overall"], add["m"]),
            ("C2  D = DiD(low-EN) - DiD(high-EN)", A["C2_refuseu"]["D"], add["m"]),
            ("C2s DiD_ref^MT (SL_MT vs EN_BT)", s["item_matched_MT_ENBT"]["DiD_overall"], add["m"]),
            ("C2s D^MT", s["item_matched_MT_ENBT"]["D"], add["m"]),
            ("HARD DiD_d' (SL_MT vs EN_BT)", h["DiD_dprime"], add["m_dprime"]),
            ("HARD DiD_c", h["DiD_c"], add["m_c"]),
            ("HARD D_d' (low - high)", h["D_dprime"], add["m_dprime"])]
    rows = [r for r in rows if r[1]]
    fig, ax = plt.subplots(figsize=(7.2, 0.42 * len(rows) + 0.8))
    for i, (lab, st, m) in enumerate(rows[::-1]):
        ax.fill_between([-m, m], i - 0.35, i + 0.35, color="0.88", zorder=0)
        ax.plot(st["ci95"], [i, i], color="k", lw=1.2)
        ax.plot(st["ci90"], [i, i], color="k", lw=3)
        ax.plot([st["est"]], [i], "o", color=C_GAMS, ms=5, zorder=3)
    ax.axvline(0, color="0.4", lw=0.8, ls="--")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows[::-1]])
    ax.set_xlabel("contrast (log-odds for DiD/D; z units for d', c); >0 = GaMS Slovene surplus\n"
                  "grey band = pre-registered +/- margin; thick = 90% CI, thin = 95% CI")
    save(fig, "fig1_forest")


def tradeoff(A):
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.6), sharey=True)
    for ax, (name, key) in zip(axes, (("SL_MT vs EN_BT (primary)", "primary_SLMT_vs_ENBT"),
                                      ("SL_MT vs EN_orig", "SLMT_vs_ENorig"))):
        v = A["C2_hard_sdt"][key]
        H, F = v["cells"]["H"], v["cells"]["F"]
        for (j0, j1), col, lab in (((0, 1), C_GEM, "Gemma-3-12B-IT"), ((2, 3), C_GAMS, "GaMS3-12B-Instruct")):
            ax.annotate("", xy=(F[j1], H[j1]), xytext=(F[j0], H[j0]),
                        arrowprops=dict(arrowstyle="->", color=col, lw=1.5))
            ax.plot(F[j0], H[j0], "o", color=col, mfc="white", label=f"{lab} EN")
            ax.plot(F[j1], H[j1], "o", color=col, label=f"{lab} SL")
        ax.set_title(name, fontsize=9)
        ax.set_xlabel("F = refusal rate on SAFE prompts (over-refusal)")
    axes[0].set_ylabel("H = refusal rate on UNSAFE prompts")
    axes[0].legend(fontsize=7, loc="lower right")
    save(fig, "fig2_tradeoff")


def dose(A):
    pc = A["C2_refuseu_sensitivities"]["per_category_dose"]
    fig, ax = plt.subplots(figsize=(5, 3.6))
    cols = {"low": "#DD8452", "high": "#4C72B0", "int": "#55A868", None: "0.5"}
    for c, v in pc["per_category"].items():
        ax.errorbar(v["log2_en_dose_p1"], v["DiD_ref"], yerr=1.96 * v["var"] ** 0.5, fmt="o",
                    color=cols.get(v["group"]), ms=4, lw=0.8, capsize=2)
        ax.annotate(c, (v["log2_en_dose_p1"], v["DiD_ref"]), fontsize=7, xytext=(3, 3), textcoords="offset points")
    ax.axhline(0, color="0.4", ls="--", lw=0.8)
    ax.set_xlabel("log2(estimated EN safety-refusal SFT rows + 1)")
    ax.set_ylabel("per-category DiD_ref (log-odds)")
    ax.set_title(f"WLS slope {pc['wls_slope']:.3f} (95% CI {pc['slope_ci95'][0]:.2f}, {pc['slope_ci95'][1]:.2f}); "
                 "orange=low-EN, blue=high-EN", fontsize=8)
    save(fig, "fig3_dose")


def identity(rows, substitute=False):
    cats = ["GaMS", "Gemma", "Qwen", "ChatGPT", "Claude", "other", "none", "UNPARSED"]
    colors = ["#C44E52", "#4C72B0", "#DD8452", "#55A868", "#8172B3", "#937860", "0.8", "0.5"]
    groups = [(mk, lg) for mk in ("gemma_it", "gams3_it") for lg in ("EN", "SL")]
    fig, ax = plt.subplots(figsize=(6, 3.2))
    for i, (mk, lg) in enumerate(groups):
        fld = "regex_self_name" if substitute else "id_name"
        c = Counter(r[fld] or "UNPARSED" for r in rows if r["set"] == "identity" and r["kind"] == "identity"
                    and r["model"] == mk and r["arm"] == lg)
        n = sum(c.values()) or 1
        b = 0
        for cat, col in zip(cats, colors):
            v = c.get(cat, 0) / n
            ax.bar(i, v, bottom=b, color=col, label=cat if i == 0 else None)
            b += v
    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels([f"{'Gemma' if mk == 'gemma_it' else 'GaMS'}\n{lg}" for mk, lg in groups])
    ax.set_ylabel("share of identity answers")
    ax.set_title("Self-name mentioned (regex detector; D5), identity FINAL items" if substitute else
                 "Self-name used (judge), identity FINAL items", fontsize=9)
    ax.legend(fontsize=7, bbox_to_anchor=(1.01, 1), loc="upper left")
    save(fig, "fig4_identity")


def rates(A):
    d = A["descriptives"]
    keys = [k for k in d if not k.split("|")[1] == "identity" and "|hard|" not in k]
    keys += [k for k in d if "|hard|" in k]
    fig, ax = plt.subplots(figsize=(9, 0.18 * len(keys) + 1))
    for i, k in enumerate(keys[::-1]):
        v = d[k]
        col = C_GAMS if k.startswith("gams") else C_GEM
        ax.plot(v["refusal_wilson95"], [i, i], color=col, lw=1)
        ax.plot(v["refusal_rate"], i, "o", color=col, ms=3)
    ax.set_yticks(range(len(keys)))
    ax.set_yticklabels(keys[::-1], fontsize=6)
    ax.set_xlabel("primary-judge refusal rate (REFUSE) with Wilson 95% CI"
                  + (" [substitute judge: local Qwen3-14B]" if A.get("substitute_mode") else ""))
    save(fig, "fig5_rates")


def judge_calib():
    p = RESULTS / "dev_judge_compare.json"
    if not p.exists():
        return
    d = json.loads(p.read_text())["per_cell"]
    fig, ax = plt.subplots(figsize=(4.6, 4.2))
    for c, v in d.items():
        mk, arm = c.split("|")[0], c.split("|")[-1]
        sl = arm.startswith("SL")
        ax.scatter(v["rate_gemini"], v["rate_qwen3"], s=28, marker="o" if sl else "s",
                   facecolors=(C_GAMS if mk == "gams3_it" else C_GEM) if sl else "none",
                   edgecolors=C_GAMS if mk == "gams3_it" else C_GEM)
        if abs(v["qwen_minus_gemini"]) > 0.15:
            ax.annotate(c.replace("_it", "").replace("|hard", ""), (v["rate_gemini"], v["rate_qwen3"]), fontsize=5.5,
                        xytext=(3, -8), textcoords="offset points")
    ax.plot([0, 1], [0, 1], color="0.6", lw=0.8, ls="--")
    ax.set_xlabel("refusal rate, gemini-2.5-flash judge (DEV)")
    ax.set_ylabel("refusal rate, local Qwen3-14B judge (DEV)")
    ax.set_title("Judge calibration on DEV cells (filled = SL arm, open = EN arm;\nblue = Gemma, red = GaMS)", fontsize=8)
    save(fig, "fig6_judge_calibration_dev")


def main():
    A = json.loads((RESULTS / "analysis_final.json").read_text())
    add = json.loads((PROTO / "addendum_dev.json").read_text())
    rows = read_jsonl(RESULTS / "items_final.jsonl")
    forest(A, add)
    tradeoff(A)
    dose(A)
    identity(rows, bool(A.get("substitute_mode")))
    rates(A)
    judge_calib()
    print("figures written")


if __name__ == "__main__":
    main()
