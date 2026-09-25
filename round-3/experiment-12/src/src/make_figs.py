#!/usr/bin/env python3
"""Figures from results/analysis.json only (numbers cannot disagree with the tables)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from common import RESULTS, UTIL_TASKS  # noqa: E402

plt.rcParams.update({"font.size": 9, "pdf.fonttype": 42, "ps.fonttype": 42, "axes.spines.top": False,
                     "axes.spines.right": False, "savefig.bbox": "tight", "savefig.dpi": 200})
FIG = RESULTS / "figs"
FIG.mkdir(parents=True, exist_ok=True)
A = json.loads((RESULTS / "analysis.json").read_text())
MODELS = [("gams3_it", "GaMS3-12B-Instruct"), ("gemma_it", "Gemma-3-12B-IT")]
C_EN, C_SL, C_HU = "#1f77b4", "#d62728", "#2ca02c"
SHORT = {"arc_challenge": "ARC-C", "boolq": "BoolQ", "hellaswag": "HellaSwag", "openbookqa": "OBQA", "piqa": "PIQA",
         "winogrande": "Winogr."}


def save(fig, name):
    fig.savefig(FIG / f"{name}.pdf")
    fig.savefig(FIG / f"{name}.png")
    plt.close(fig)


def fig_forest():
    cells = A["utility"]["cells"]
    conds = [c for c in ("E_iter1", "rand_nm_j1", "E_art2") if any(c in cells.get(m, {}) for m, _ in MODELS)]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.6), sharey=True)
    for ax, (m, lab) in zip(axes, MODELS):
        if m not in cells:
            ax.set_title(f"{lab} (not run)")
            continue
        y = 0
        yt, yl = [], []
        for t in UTIL_TASKS:
            for c in conds:  # identical rows in both panels (a missing condition leaves an empty row)
                for l, col, off in (("en", C_EN, -0.15), ("sl", C_SL, 0.15)):
                    d = cells[m].get(c, {}).get(l, {}).get(t)
                    if not d:
                        continue
                    mk = "o" if c == "E_iter1" else ("s" if c == "rand_nm_j1" else "^")
                    fc = col if d["eligible"] else "white"
                    ax.errorbar(d["H"], y + off, xerr=[[d["H"] - d["H_ci95"][0]], [d["H_ci95"][1] - d["H"]]], fmt=mk, color=col,
                                mfc=fc, ms=4, lw=0.8, capsize=0)
                yt.append(y)
                yl.append(f"{SHORT[t]} · {'edit' if c == 'E_iter1' else ('random' if c == 'rand_nm_j1' else c)}")
                y += 1
            y += 0.5
        ax.axvline(0, color="k", lw=0.6)
        ax.axvline(-0.2, color="grey", ls="--", lw=0.8)
        ax.set_yticks(yt)
        ax.set_yticklabels(yl, fontsize=7)
        if ax is axes[0]:
            ax.invert_yaxis()  # shared y: invert once
        ax.set_xlabel("headroom-normalised change H (95% CI)")
        ax.set_title(lab)
    h = [axes[0].plot([], [], "o", color=C_EN, label="EN")[0], axes[0].plot([], [], "o", color=C_SL, label="SL")[0],
         axes[0].plot([], [], "o", mfc="white", color="k", label="ineligible (headroom<0.10)")[0],
         axes[0].plot([], [], "s", color="grey", label="random edit rand_nm_j1 (square)")[0],
         axes[0].plot([], [], "^", color="grey", label="E_art2 (triangle)")[0]]
    fig.legend(handles=h, fontsize=7, loc="lower center", ncol=5, frameon=False, bbox_to_anchor=(0.5, -0.07))
    save(fig, "fig1_forest_H")


def fig_lambda():
    curve = A.get("lambda_gate_curve") or {}
    if not curve:
        return
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.8), sharey=True)
    for ax, (m, lab) in zip(axes, MODELS):
        pts = curve.get(m, {}).get("points", [])
        if not pts:
            ax.set_title(f"{lab} (not run)")
            continue
        lam = [0.0] + [p["lambda"] for p in pts]
        for key, cik, col, name in (("macro_H_en", "ci95_en", C_EN, "EN"), ("macro_H_sl", "ci95_sl", C_SL, "SL")):
            v = [0.0] + [p[key] for p in pts]
            lo = [0.0] + [p[cik][0] if p[cik] else np.nan for p in pts]
            hi = [0.0] + [p[cik][1] if p[cik] else np.nan for p in pts]
            ax.plot(lam, v, "-o", color=col, ms=4, label=name)
            ax.fill_between(lam, lo, hi, color=col, alpha=0.15)
        ax.axhline(-0.2, color="grey", ls="--", lw=0.8)
        ax.text(0.02, -0.19, "catastrophe gate (-0.20)", fontsize=7, color="grey")
        ax.axhline(0, color="k", lw=0.5)
        ax.set_xlabel("LoRA scale λ (λ=0: original)")
        ax.set_title(lab)
    axes[0].set_ylabel("macro H (100 items x 4 tasks)")
    axes[0].legend(frameon=False, fontsize=8)
    save(fig, "fig2_lambda_gate_curve")


def fig_kl():
    kl = A.get("kl") or {}
    if not kl:
        return
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0), sharey=True)
    for ax, (m, lab) in zip(axes, MODELS):
        if m not in kl or not all(a in kl[m]["arms"] for a in ("en_bt", "sl_mt", "hu_mt")):
            ax.set_title(f"{lab} (KL incomplete)")
            continue
        means = kl[m]["means"]
        conds = [c for c in ["E_iter1_l0.5", "E_iter1", "E_iter1_l1.5", "E_iter1_l2.0", "E_art2", "rand_c6_j1",
                             "rand_nm_j1", "rand_nm_j2", "rand_nm_j3", "rand_nm_j4", "rand_nm_j5"] if c in means]
        x = np.arange(len(conds))
        for k, (arm, col) in enumerate((("en_bt", C_EN), ("sl_mt", C_SL), ("hu_mt", C_HU))):
            v = [max(means[c][arm]["first"]["mean"], 1e-7) for c in conds]
            ax.bar(x + (k - 1) * 0.27, v, 0.27, color=col, label={"en_bt": "EN-BT", "sl_mt": "SL-MT", "hu_mt": "HU-MT"}[arm])
        ax.set_yscale("log")
        sf = kl[m]["self_floor"]["max_first"]
        ax.set_title(f"{lab}\n(self-KL floor, orig re-run: max = {sf:.1g})", fontsize=9)
        ax.set_xticks(x)
        ax.set_xticklabels([c.replace("E_iter1_l", "λ").replace("E_iter1", "edit").replace("rand_nm_j", "rnd").replace("rand_c6_j1", "rnd×6")
                            for c in conds], rotation=60, fontsize=7)
    axes[0].set_ylabel("mean first-token KL(orig‖cond)")
    axes[0].legend(frameon=False, fontsize=7, loc="upper right")
    save(fig, "fig3_kl_by_condition")


def fig_bele():
    b = A.get("belebele")
    if not b:
        return
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 2.6), sharey=True)
    for ax, (m, lab) in zip(axes, MODELS):
        cells = b["cells"].get(m)
        if not cells:
            ax.set_title(f"{lab} (not run)")
            continue
        conds = ["orig"] + [c for c in ("E_iter1", "rand_nm_j1", "E_art2") if c in cells]
        x = np.arange(len(conds))
        for k, (l, col) in enumerate((("en", C_EN), ("sl", C_SL), ("hu", C_HU))):
            first = next(iter(cells.values()))
            v = [first[l]["belebele"]["acc_orig"] if c == "orig" else cells[c][l]["belebele"]["acc"] for c in conds]
            ax.bar(x + (k - 1) * 0.27, v, 0.27, color=col, label=l.upper())
        ax.axhline(0.25, color="grey", ls=":", lw=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels(["original", "edit", "random", "E_art2"][:len(conds)])
        ax.set_title(lab)
        ax.set_ylim(0, 1)
    axes[0].set_ylabel("Belebele accuracy (n=200)")
    axes[0].legend(frameon=False, fontsize=7, ncol=3)
    save(fig, "fig4_belebele")


if __name__ == "__main__":
    for f in (fig_forest, fig_lambda, fig_kl, fig_bele):
        try:
            f()
            print("ok", f.__name__)
        except (KeyError, ValueError, TypeError, IndexError) as e:
            print("FAILED", f.__name__, repr(e))
