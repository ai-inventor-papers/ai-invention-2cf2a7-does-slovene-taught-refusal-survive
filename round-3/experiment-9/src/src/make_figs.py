#!/usr/bin/env python3
"""Figures, regenerated from results/analysis.json (which is computed from items_final.jsonl) -> figures/*.png|pdf."""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy.special import expit, logit  # noqa: E402

from common import RESULTS, WS  # noqa: E402

FIG = WS / ("figures" if "AII_RESULTS" not in __import__("os").environ else "scratch/dryrun_figs")
FIG.mkdir(exist_ok=True)
COL = {"gemma_it": "#1f77b4", "gams3_it": "#d62728"}
NAME = {"gemma_it": "Gemma-3-12B-IT", "gams3_it": "GaMS3-12B-Instruct"}
plt.rcParams.update({"font.size": 9, "pdf.fonttype": 42, "ps.fonttype": 42})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / f"{name}.png", dpi=180)
    fig.savefig(FIG / f"{name}.pdf")
    plt.close(fig)


def main():
    A = json.loads((RESULTS / "analysis.json").read_text())
    # fig1 transfer curves: B' (trials), lambda, random points (J1 R1)
    fig, axes = plt.subplots(1, 2, figsize=(9, 4), sharey=True)
    for ax, (curve, title) in zip(axes, (("Bprime|j1|R1", "40 paired Heretic trials (B')"),
                                         ("lambda|j1|R1", "lambda-scaled selected edit"))):
        g = A["G3"][curve]
        for m in ("gemma_it", "gams3_it"):
            pm = g["per_model"][m]
            pE, pS = np.array(pm["pE"]), np.array(pm["pS"])
            ax.scatter(pE, pS, s=18, color=COL[m], alpha=0.75, label=f"{NAME[m]} (a={pm['a']:.2f})")
            xs = np.linspace(0.02, 0.98, 100)
            ax.plot(xs, expit(pm["a"] + pm["b"] * logit(xs)), color=COL[m], lw=1.5)
            if curve.startswith("lambda"):
                o = np.argsort(pE)
                ax.plot(pE[o], pS[o], color=COL[m], lw=0.6, ls=":")
        for m in ("gemma_it", "gams3_it"):
            for d in A["random_specificity"][m]["edits"]:
                if d["step"].startswith("rand") and curve.startswith("Bprime"):
                    ax.scatter([d["en_bt"]], [d["sl_mt"]], marker="x", color=COL[m], s=30)
        ax.plot([0, 1], [0, 1], color="grey", lw=0.6, ls="--")
        ax.axvline(0.5, color="grey", lw=0.5)
        ax.set_xlabel("EN-BT refusal rate (J1, R1)")
        ax.set_title(f"{title}\nG3 = {g['G3']:.2f} [{g['ci95'][0]:.2f}, {g['ci95'][1]:.2f}]")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
    axes[0].set_ylabel("SL-MT refusal rate (J1, R1)")
    axes[0].legend(fontsize=7, loc="lower right")
    save(fig, "fig1_transfer_curves")

    # fig2 G3 forest
    keys = [k for k in A["G3"] if "|" in k]
    fig, ax = plt.subplots(figsize=(7, 0.32 * len(keys) + 1))
    for i, k in enumerate(keys):
        g = A["G3"][k]
        ax.errorbar(g["G3"], i, xerr=[[g["G3"] - g["ci95"][0]], [g["ci95"][1] - g["G3"]]], fmt="o", color="k", ms=4, capsize=2)
    ax.axvline(0, color="grey", lw=0.8)
    for x in (-0.675, 0.675):
        ax.axvline(x, color="red", lw=0.6, ls="--")
    ax.set_yticks(range(len(keys)))
    ax.set_yticklabels(keys, fontsize=7)
    ax.set_xlabel("G3 = a_GaMS - a_Gemma (SL log-odds at EN-BT 50%); 95% bootstrap CI; dashed = +/- m")
    save(fig, "fig2_g3_forest")

    # fig3 SDT per step
    sd = A["SDT"]["j1|R1"]["per_model"]
    fig, axes = plt.subplots(2, 2, figsize=(9, 6), sharex=True)
    for j, m in enumerate(("gemma_it", "gams3_it")):
        ps = sd[m]["per_step"]
        x = np.array([p["pE_harm"] for p in ps])
        for arm, st in (("en_bt", "o"), ("sl_mt", "s")):
            axes[0, j].scatter(x, [p[f"c_ref_{arm}"] for p in ps], marker=st, s=14, label=arm.upper().replace("_", "-"))
            axes[1, j].scatter(x, [p[f"dprime_{arm}"] for p in ps], marker=st, s=14, label=arm.upper().replace("_", "-"))
        for ax in axes[:, j]:
            ax.axvspan(0.3, 0.7, color="grey", alpha=0.1)
        dc = sd[m].get("delta_c")
        dd = sd[m].get("delta_dprime")
        axes[0, j].set_title(f"{NAME[m]}: dc={dc if dc is None else round(dc, 2)}, dd'={dd if dd is None else round(dd, 2)}")
        axes[1, j].set_xlabel("EN-BT harmful refusal rate (J1)")
    axes[0, 0].set_ylabel("c_ref = (z(H)+z(F))/2")
    axes[1, 0].set_ylabel("d' = z(H) - z(F)")
    axes[0, 0].legend(fontsize=7)
    save(fig, "fig3_sdt_per_step")

    # fig4 C5a
    c5 = A.get("C5a", {})
    if c5:
        fig, ax = plt.subplots(figsize=(4.5, 3.2))
        for i, m in enumerate(c5):
            r = c5[m]
            ax.errorbar(i, r["excess_ratio"], yerr=[[r["excess_ratio"] - r["ci95"][0]], [r["ci95"][1] - r["excess_ratio"]]],
                        fmt="o", color=COL[m], capsize=3)
        ax.axhline(1, color="grey", lw=0.8)
        ax.set_xticks(range(len(c5)))
        ax.set_xticklabels([NAME[m] for m in c5], fontsize=8)
        ax.set_ylabel("C5a excess ratio (SL/EN KL, edit vs random)")
        save(fig, "fig4_c5a")

    # fig5 judge agreement
    cells = A["judge"].get("j1_vs_j2_cells", {})
    if cells:
        fig, ax = plt.subplots(figsize=(7, 3.2))
        ks = list(cells)
        ax.bar(range(len(ks)), [cells[k]["kappaR"] for k in ks], color="#555")
        ax.axhline(0.6, color="red", ls="--", lw=0.8)
        ax.set_xticks(range(len(ks)))
        ax.set_xticklabels(ks, rotation=45, ha="right", fontsize=7)
        ax.set_ylabel("Cohen kappa (REFUSE), J1 vs J2")
        save(fig, "fig5_judge_kappa")
    print("figures written")


if __name__ == "__main__":
    main()
