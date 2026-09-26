#!/usr/bin/env python3
"""Figures from results/analysis/analysis.json and the saved JSONL (no GPU)."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "figures"
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})
COL = {"pt": "#1b6ca8", "own_pooled": "#2a9d8f", "gb": "#e76f51", "langid": "#8e44ad", "own_en": "#6c9a3b",
       "own_sl": "#b5838d", "rand": "#9e9e9e"}


def save(fig, name):
    FIG.mkdir(exist_ok=True)
    fig.savefig(FIG / f"{name}.png", dpi=200, bbox_inches="tight")
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    A = json.loads((ROOT / "results/analysis/analysis.json").read_text())
    s1 = A.get("S1", {})
    if "per_layer" in s1:
        fig, ax = plt.subplots(1, 2, figsize=(9, 3.2))
        for m, ls in [("pt", "-"), ("gb", "--")]:
            pl = s1["per_layer"][m]
            L = [r["layer"] for r in pl]
            for la, c in [("en", "#1b6ca8"), ("sl", "#e76f51")]:
                ax[0].plot(L, [r[f"dprime_{la}_pooled"] for r in pl], ls, color=c, label=f"{'gemma-3-pt' if m == 'pt' else 'GaMS3-base'} {la.upper()}")
            pr = s1["probes"][m]
            ax[1].plot([p["layer"] for p in pr], [p["auroc_sl"] for p in pr], ls, color="#e76f51", label=f"{m} SL (CV)")
            ax[1].plot([p["layer"] for p in pr], [p["auroc_en_to_sl"] for p in pr], ls, color="#555", label=f"{m} EN→SL")
        for a_ in ax:
            a_.axvline(s1["L_pt"], color="k", lw=0.6, ls=":")
        ax[0].set(xlabel="layer (hidden_states index)", ylabel="SCORE d′ (pooled dir.)", title="Base-model harm separability")
        ax[1].set(xlabel="layer", ylabel="probe AUROC", title="Probe AUROC (ceiling >0.99 uninformative)")
        ax[0].legend(frameon=False, fontsize=7); ax[1].legend(frameon=False, fontsize=7)
        save(fig, "fig1_base_layer_curves")
    s4 = A.get("S4", {})
    for tag, S4x in [("lexicon", s4), ("judge", A.get("S4_judge", {}))]:
        if "cells" not in S4x:
            continue
        fig, axs = plt.subplots(2, 2, figsize=(9, 7), sharey=True)
        fig.subplots_adjust(hspace=0.45)
        for i, m in enumerate(["gemma", "gams"]):
            grid = {int(k): v / S4x["n_bar"][m] for k, v in S4x["alpha_grid"][m].items()}
            for j, la in enumerate(["en", "sl"]):
                ax = axs[i, j]
                b0 = S4x["baseline_alpha0"].get(f"{m}_{la}", {}).get("R")
                for k, c in S4x["cells"].items():
                    mm, d, l2 = k.split("|")
                    if mm != m or l2 != la or "R" not in c:
                        continue
                    col = COL["rand"] if d.startswith("rand") else COL.get(d, "k")
                    x = [grid[kk] for kk in c["ks"]]
                    ax.plot(x, c["R"], "-o" if not d.startswith("rand") else "-", ms=2.5, lw=1.6 if d == "pt" else 0.9,
                            color=col, alpha=0.5 if d.startswith("rand") else 1,
                            label=None if d.startswith("rand") and d != "rand0" else ("random (x5)" if d == "rand0" else d))
                if b0 is not None:
                    ax.axhline(b0, color="k", lw=0.5, ls=":")
                ax.axhline(0.5, color="k", lw=0.4)
                ax.set_xscale("log")
                ax.set_title(f"{'Gemma-3-12B-IT' if m == 'gemma' else 'GaMS3-12B-Instruct'}: {la.upper()} harmless", fontsize=9)
                ax.set(xlabel="α / N̄", ylabel=f"refusal rate ({tag})")
        axs[0, 0].legend(frameon=False, fontsize=7)
        fig.suptitle(f"C4 induction at L22 ({tag} readout; non-degenerate refusals)", fontsize=10)
        save(fig, f"fig2_induction_dose_response_{tag}")
    if "cells" in s4:
        # ECDF of per-prompt flip thresholds
        fig, axs = plt.subplots(1, 2, figsize=(9, 3.2), sharey=True)
        for i, m in enumerate(["gemma", "gams"]):
            for d in ["pt", "own_pooled"]:
                for la, ls in [("en", "-"), ("sl", "--")]:
                    thr = s4["flip_thresholds"].get(f"{m}|{d}|{la}", {})
                    if not thr:
                        continue
                    v = np.array([t / s4["n_bar"][m] if t is not None else np.inf for t in thr.values()])
                    xs = np.sort(v[np.isfinite(v)])
                    if len(xs):
                        axs[i].step(xs, np.arange(1, len(xs) + 1) / len(v), ls, color=COL[d], where="post", label=f"{d} {la.upper()}")
            axs[i].set_xscale("log"); axs[i].set(title={"gemma": "Gemma-3-12B-IT", "gams": "GaMS3-12B-Instruct"}[m],
                                                 xlabel="per-prompt flip threshold α*/N̄", ylabel="fraction flipped")
            axs[i].legend(frameon=False, fontsize=7)
        save(fig, "fig3_flip_threshold_ecdf")
    s3 = A.get("S3", {})
    if "_arrays" in s3:
        y, g = np.array(s3["_arrays"]["y"]), np.array(s3["_arrays"]["g"])
        fig, ax = plt.subplots(figsize=(4.5, 3.5))
        ax.scatter(g, y, s=3, alpha=0.3, color="#1b6ca8")
        b = np.polyfit(g, y, 1)
        xx = np.linspace(g.min(), g.max(), 10)
        ax.plot(xx, np.polyval(b, xx), color="k", lw=1)
        ax.set(xlabel="base-geometry contrast g (harm-z DiD)", ylabel="instruct DiD on s (y)",
               title=f"r = {s3['corr_y_g']:.3f}; geometry share = {s3['s']['geometry_share']:.2f}")
        save(fig, "fig4_regression_y_vs_g")
    # forest
    rows = []
    if "Lpt" in s1:
        rows.append(("Δd′_SL (GaMS-base − pt) @L_pt", s1["Lpt"]["Delta_dprime_SL"], s1["Lpt"]["Delta_dprime_SL_ci"]))
        rows.append(("DiD d′ (SL−EN) @L_pt", s1["Lpt"]["DiD_dprime"], s1["Lpt"]["DiD_dprime_ci"]))
    for d, v in s4.get("Delta", {}).items():
        if v.get("Delta_C4") is not None:
            rows.append((f"Δ_C4 {d}", v["Delta_C4"], v.get("ci_all_finite_only") or [None, None]))
    if rows:
        fig, ax = plt.subplots(figsize=(6, 0.45 * len(rows) + 1))
        for i, (lab, est, c) in enumerate(rows):
            ax.plot([est], [i], "o", color="k")
            if c and c[0] is not None:
                ax.plot(c, [i, i], "-", color="k")
        ax.axvline(0, color="grey", lw=0.6)
        ax.axvspan(-np.log(1.5), np.log(1.5), color="#2a9d8f", alpha=0.08)
        ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[0] for r in rows])
        ax.set_title("Headline contrasts (95% bootstrap CI; shaded = ±ln1.5)")
        save(fig, "fig5_forest")
    print("figures written")


if __name__ == "__main__":
    main()
