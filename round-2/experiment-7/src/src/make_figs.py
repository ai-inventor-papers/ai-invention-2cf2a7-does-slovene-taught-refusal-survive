#!/usr/bin/env python3
"""Figures from results/analysis.json only (so every plotted number is a saved number)."""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from common import FIGS, RESULTS, SYSTEM_LABEL  # noqa: E402

plt.rcParams.update({"font.size": 9, "pdf.fonttype": 42, "ps.fonttype": 42})
ORDER = ["gams", "gemma", "q14", "q235", "out"]
SHORT = {"gams": "GaMS3", "gemma": "Gemma-3", "q14": "Qwen3-14B", "q235": "Qwen3-235B\n(teacher)",
         "out": "Llama-3.3\n(outgroup)", "ref_sft": "GaMS SFT\nrefusals"}


def save(fig, name):
    for ext in ("png", "pdf"):
        fig.savefig(FIGS / f"{name}.{ext}", dpi=200, bbox_inches="tight")
    plt.close(fig)


def kappa_heatmaps(A):
    blocks = [("H_en_orig", "EN original"), ("H_sl_mt", "SL (MT)"), ("H_en_bt", "EN back-translation")]
    blocks = [b for b in blocks if "pairwise" in A["T1"].get(b[0], {})]
    fig, axes = plt.subplots(1, len(blocks), figsize=(4.2 * len(blocks), 3.8))
    axes = np.atleast_1d(axes)
    for ax, (blk, title) in zip(axes, blocks):
        pw = A["T1"][blk]["pairwise"]
        M = np.eye(5)
        for i, a in enumerate(ORDER):
            for j, b in enumerate(ORDER):
                if i != j:
                    k = pw.get(f"{a}~{b}") or pw.get(f"{b}~{a}")
                    M[i, j] = k["kappa"] if k else np.nan
        im = ax.imshow(M, vmin=0, vmax=1, cmap="viridis")
        for i in range(5):
            for j in range(5):
                if i != j:
                    ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", color="w" if M[i, j] < .6 else "k",
                            fontsize=8)
        ax.set_xticks(range(5), [SHORT[s] for s in ORDER], rotation=45, ha="right", fontsize=7)
        ax.set_yticks(range(5), [SHORT[s] for s in ORDER], fontsize=7)
        ax.set_title(f"HARD-DEV {title} (n={A['T1'][blk]['n']})")
    fig.colorbar(im, ax=axes.tolist(), shrink=.7, label="Cohen's kappa (refuse vs not)")
    fig.suptitle(f"Readout: {READOUT} (5-system item subset)", fontsize=8)
    save(fig, "fig1_kappa_matrix")


def forest(A):
    rows = []
    for blk, lab in (("H_en_orig", "EN orig (primary)"), ("H_en_orig_robust_partial_as_refusal", "EN orig, PARTIAL=refuse"),
                     ("H_en_orig_genblock_as_refusal", "EN orig, provider block=refuse"),
                     ("H_en_orig_safe", "EN orig, safe items"), ("H_en_orig_unsafe", "EN orig, unsafe items"),
                     ("H_en_orig_src_xstest", "EN orig, XSTest"), ("H_en_orig_src_orbench_hard1k", "EN orig, OR-Bench hard"),
                     ("H_en_orig_src_orbench_toxic", "EN orig, OR-Bench toxic"),
                     ("H_sl_mt", "SL MT"), ("H_sl_mt_excl_fragile_bt60", "SL MT, robust MT items"),
                     ("H_en_bt", "EN back-translation"), ("R_en_orig_ceiling_set", "RefusEU EN (ceiling)"),
                     ("R_sl_mt_ceiling_set", "RefusEU SL MT (ceiling)")):
        T = A["T1"].get(blk, {})
        if "dk" in T:
            rows.append((lab, T["n_core"], T["fpcal_dk"], T["dk"], T.get("t1b_dk_q235_minus_out")))
    if not rows:
        return
    fig, ax = plt.subplots(figsize=(7.5, 0.42 * len(rows) + 1.2))
    y = np.arange(len(rows))[::-1]
    for off, idx, col, name in ((0.22, 2, "#999999", "FP-cal: k(Q14,Q235)-k(Q14,Gemma)"),
                                (0.0, 3, "#1f77b4", "T1: k(GaMS,Q235)-k(GaMS,Gemma)"),
                                (-0.22, 4, "#d62728", "T1b: k(GaMS,Q235)-k(GaMS,Llama)")):
        nan = {"est": np.nan, "ci_lo": np.nan, "ci_hi": np.nan}
        rr = [r[idx] or nan for r in rows]
        est = [x["est"] for x in rr]
        lo = [x["est"] - x["ci_lo"] for x in rr]
        hi = [x["ci_hi"] - x["est"] for x in rr]
        ax.errorbar(est, y + off, xerr=[lo, hi], fmt="o", ms=4, color=col, label=name, capsize=2)
    ax.axvline(0, color="k", lw=.8)
    ax.axvline(0.10, color="k", lw=.8, ls=":")
    ax.set_yticks(y, [f"{r[0]} (n={r[1]})" for r in rows])
    ax.set_xlabel("difference in Cohen's kappa (95% paired item bootstrap CI)")
    ax.set_title(f"Readout: {READOUT}; n = items with GaMS/Gemma/Q14/Q235 labelled (T1b: outgroup subset)", fontsize=7)
    ax.legend(fontsize=7, loc="best")
    save(fig, "fig2_dk_forest")


def openings(A):
    tops = A["T3"].get("top_openings", {})
    langs = [l for l in ("en", "sl") if any(k.endswith("|" + l) for k in tops)]
    if not langs:
        return
    fig, axes = plt.subplots(1, len(langs), figsize=(6.5 * len(langs), 5))
    axes = np.atleast_1d(axes)
    for ax, l in zip(axes, langs):
        systems = [s for s in ORDER + ["ref_sft"] if f"{s}|{l}" in tops]
        allo = []
        for s in systems:
            allo += [o for o, _ in tops[f"{s}|{l}"][:3]]
        allo = list(dict.fromkeys(allo))[:18]
        n = A["T3"]["n"]
        W = 0.8 / len(systems)
        for j, s in enumerate(systems):
            d = dict(tops[f"{s}|{l}"])
            tot = n.get(f"{s}|{l}", 1)
            ax.barh(np.arange(len(allo)) + j * W, [d.get(o, 0) / tot for o in allo], W, label=SHORT[s].replace("\n", " "))
        ax.set_yticks(np.arange(len(allo)) + 0.4, allo, fontsize=7)
        ax.invert_yaxis()
        ax.set_xlabel("share of the system's REFUSE responses (top-3 openings per system)")
        ax.set_title(f"Refusal opening trigrams ({l.upper()})")
        ax.legend(fontsize=6)
    save(fig, "fig3_opening_trigrams")


def flips(A):
    """T4 depth. The substitute judge is NOT valid on prefill rows (pooled kappa vs gemini 0.15), so this figure plots
    the primary gemini readout's descriptive flip rates (all gemini-labelled R200 prefill rows; n ~ 23-34 per bar)."""
    pth = RESULTS / "analysis_gemini_partial.json"
    if not pth.exists():
        return
    U = json.loads(pth.read_text()).get("T4_unconditional_descriptive", {})
    arms = [a for a in ("en_orig", "sl_mt") if any(k.startswith(f"gams|{a}") for k in U)]
    if not arms:
        return
    fig, axes = plt.subplots(1, len(arms), figsize=(4.5 * len(arms), 3.4))
    axes = np.atleast_1d(axes)
    sy = ("gams", "gemma", "q14")
    for ax, arm in zip(axes, arms):
        x = np.arange(3)
        for off, cond, col in ((-0.18, "pre_comply5", "#d62728"), (0.18, "pre_neutral", "#7f7f7f")):
            W = [U.get(f"{s}|{arm}|{cond}", {"p": np.nan, "lo": np.nan, "hi": np.nan, "n": 0}) for s in sy]
            p = [w["p"] for w in W]
            ax.bar(x + off, p, 0.36, yerr=[[w["p"] - w["lo"] for w in W], [w["hi"] - w["p"] for w in W]], color=col,
                   capsize=2, label="5-token compliant prefix" if cond == "pre_comply5" else "neutral prefix")
            for xi, w in zip(x, W):
                ax.text(xi + off, 0.02, f"n={w['n']}", ha="center", fontsize=6, rotation=90)
        ax.set_xticks(x, ["GaMS3", "Gemma-3", "Qwen3-14B"])
        ax.set_ylim(0, 1)
        ax.set_ylabel("share NOT refused (gemini judge)")
        ax.set_title(f"RefusEU R200 prefill, {arm}")
        ax.legend(fontsize=7)
    fig.suptitle("T4 descriptive, primary judge on the labelled subset (substitute judge invalid on prefill rows)",
                 fontsize=8)
    save(fig, "fig4_prefill_flip")


def identity(A):
    names = A["T5"]["names"]
    cats = ["GaMS", "Gemma", "Qwen", "ChatGPT", "Claude", "Llama", "other", "none"]
    keys = [f"{s}|{l}" for l in ("en", "sl") for s in ORDER if f"{s}|{l}" in names]
    if not keys:
        return
    fig, ax = plt.subplots(figsize=(8, 3.4))
    bottom = np.zeros(len(keys))
    for c in cats:
        v = np.array([names[k].get(c, {}).get("p", 0.0) for k in keys])
        ax.bar(range(len(keys)), v, bottom=bottom, label=c)
        bottom += v
    ax.set_xticks(range(len(keys)), [SHORT[k.split("|")[0]].replace("\n", " ") + "\n" + k.split("|")[1].upper()
                                     for k in keys], fontsize=6)
    ax.set_ylabel("share of ID answers (all 117 ID items)")
    ax.legend(fontsize=6, ncol=4)
    ax.set_title(f"Self-name used in identity/control answers ({READOUT})")
    save(fig, "fig5_identity_names")


READOUT = "judge"


def main() -> None:
    global READOUT
    A = json.loads((RESULTS / "analysis.json").read_text())
    READOUT = {"local": "substitute judge Mistral-Small-24B (validated vs gemini)", "gemini": "gemini-2.5-flash",
               "regex": "lexical regex"}.get(A.get("readout_key"), "judge")
    for f in (kappa_heatmaps, forest, openings, flips, identity):
        try:
            f(A)
        except (KeyError, ValueError, TypeError) as e:
            print(f"figure {f.__name__} skipped: {e!r}")
    print(sorted(p.name for p in FIGS.glob("*.png")))


if __name__ == "__main__":
    main()
