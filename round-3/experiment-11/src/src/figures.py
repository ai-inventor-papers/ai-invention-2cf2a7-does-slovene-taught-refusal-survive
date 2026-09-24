#!/usr/bin/env python3
"""Figures from results/analysis.json (+ rows table for per-item distributions): (1) FINAL lambda curves SL vs EN_BT
per model with the fitted GLM; (2) SDT c / d' along the curve; (3) public-checkpoint SL/L3 - EN_BT bars; (4)
competence scatter (descriptive). Colour-blind-safe palette; PDF + PNG."""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from common import FIG, RESULTS  # noqa: E402

C = {"gemma_it": "#0072B2", "gams3_it": "#D55E00", "EN": "#4D4D4D", "SL": "#009E73", "L3": "#CC79A7"}
NAME = {"gemma_it": "Gemma-3-12B-IT", "gams3_it": "GaMS3-12B-Instruct", "pew_heretic": "p-e-w heretic",
        "huihui": "huihui abliterated", "mlabonne_v2": "mlabonne abliterated-v2"}
plt.rcParams.update({"font.size": 10, "pdf.fonttype": 42, "ps.fonttype": 42})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / f"{name}.pdf")
    fig.savefig(FIG / f"{name}.png", dpi=200)
    plt.close(fig)


def fig_curve(A):
    g = A["G3"].get("q_R")
    if not g:
        return
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8))
    ax = axes[0]
    xs = np.linspace(0.03, 0.97, 100)
    for m in ("gemma_it", "gams3_it"):
        pm = g["per_model"][m]
        ax.scatter(pm["p_en"], pm["p_L"], color=C[m], label=f"{NAME[m]} (steps)", s=28, zorder=3)
        a, b = pm["a"], pm["b"]
        ax.plot(xs, 1 / (1 + np.exp(-(a + b * np.log(xs / (1 - xs))))), color=C[m], lw=1.5)
    ax.plot([0, 1], [0, 1], ls=":", color="grey", lw=1)
    ax.axvline(0.5, color="grey", lw=0.6)
    ax.set_xlabel("EN-BT refusal rate (Qwen3-14B judge)")
    ax.set_ylabel("SL-MT refusal rate")
    ax.set_title(f"FINAL lambda curve; G3 = {g['G3']:.2f} [{g['ci95'][0]:.2f}, {g['ci95'][1]:.2f}]")
    ax.legend(fontsize=8, loc="upper left")
    ax = axes[1]
    for m in ("gemma_it", "gams3_it"):
        pm = g["per_model"][m]
        st = g["steps"]
        ax.plot(st, pm["p_en"], "-o", color=C[m], ms=4, label=f"{NAME[m]} EN-BT")
        ax.plot(st, pm["p_L"], "--s", color=C[m], ms=4, label=f"{NAME[m]} SL-MT")
    ax.set_xlabel("lambda (LoRA scaling of the English Heretic edit)")
    ax.set_ylabel("refusal rate")
    ax.legend(fontsize=7)
    save(fig, "fig1_lambda_curve")


def fig_sdt(A):
    s = A["sdt_curve"]["q_R"]
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4))
    from analysis import sdt_curve  # noqa: F401  (documentation of source)
    raw = json.loads((RESULTS / "analysis.json").read_text())
    for m in ("gemma_it", "gams3_it"):
        pts = [r for r in raw.get("sdt_curve_steps", {}).get(m, [])] if "sdt_curve_steps" in raw else []
        if not pts:
            continue
        lam = [r["lambda"] for r in pts if "delta_c" in r]
        axes[0].plot(lam, [r["delta_c"] for r in pts if "delta_c" in r], "-o", color=C[m], label=NAME[m])
        axes[1].plot(lam, [r["delta_d"] for r in pts if "delta_d" in r], "-o", color=C[m], label=NAME[m])
    axes[0].axhline(0, color="grey", lw=0.6)
    axes[1].axhline(0, color="grey", lw=0.6)
    axes[0].set_title("Delta-c = c(EN-BT) - c(SL-MT)  (+ = SL more refusal-prone)")
    axes[1].set_title("Delta-d' = d'(EN-BT) - d'(SL-MT)")
    for ax in axes:
        ax.set_xlabel("lambda")
        ax.legend(fontsize=8)
    save(fig, "fig2_sdt_curve")


def fig_public(A):
    p = A["public"]["q_R"]
    ms = [m for m in p if isinstance(p[m], dict) and "SL_minus_EN_pp" in p[m]]
    if not ms:
        return
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    x = np.arange(len(ms))
    for off, tag, col in ((-0.18, "SL", C["SL"]), (0.18, "L3", C["L3"])):
        v = [p[m].get(f"{tag}_minus_EN_pp", np.nan) for m in ms]
        lo = [p[m].get(f"{tag}_minus_EN_ci95", [np.nan, np.nan])[0] for m in ms]
        hi = [p[m].get(f"{tag}_minus_EN_ci95", [np.nan, np.nan])[1] for m in ms]
        ax.bar(x + off, v, 0.36, color=col, label=f"{tag} - EN-BT")
        ax.errorbar(x + off, v, yerr=[np.array(v) - np.array(lo), np.array(hi) - np.array(v)], fmt="none",
                    ecolor="black", lw=1)
    ax.axhline(0, color="grey", lw=0.6)
    ax.axhline(5, color="grey", ls=":", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([NAME.get(m, m) + (" (orig ref.)" if m == "gemma_it" else "") for m in ms], fontsize=8,
                       rotation=10)
    ax.set_ylabel("refusal difference (pp), PUB items")
    ax.legend(fontsize=8)
    save(fig, "fig3_public_checkpoints")


def fig_competence(A):
    cells = A.get("competence", {}).get("scatter_cells", [])
    if not cells:
        return
    fig, ax = plt.subplots(figsize=(4.6, 3.6))
    for c in cells:
        ax.scatter(c["belebele_acc"], c["lag_lam1"], color=C[c["model"]], marker="o" if c["lang"] == "sl" else "^",
                   s=60)
        ax.annotate(f"{NAME[c['model']].split('-')[0]} {c['lang']}", (c["belebele_acc"], c["lag_lam1"]), fontsize=7,
                    xytext=(4, 4), textcoords="offset points")
    ax.axhline(0, color="grey", lw=0.6)
    ax.set_xlabel("Belebele accuracy (orig model)")
    ax.set_ylabel("language lag at lambda=1 (log-odds L - EN-BT)")
    ax.set_title("DESCRIPTIVE (n = 4 cells)", fontsize=9)
    save(fig, "fig4_competence_scatter")


def main():
    A = json.loads((RESULTS / "analysis.json").read_text())
    for f in (fig_curve, fig_sdt, fig_public, fig_competence):
        try:
            f(A)
        except (KeyError, ValueError, TypeError) as e:
            print(f"{f.__name__} skipped: {e}")


if __name__ == "__main__":
    main()
