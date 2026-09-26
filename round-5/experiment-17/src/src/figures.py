#!/usr/bin/env python3
"""Figures F1-F5 rendered from results/analysis.json + dev_gate_*.json only (no numbers typed by hand).
F1 paired ASR bars orig vs edit per model x language (Wilson CIs); F2 forest plot of edit deltas per readout (raw
paired-bootstrap CI) with the RG-corrected ASR delta; F3 StrongREJECT-ft score histograms; F4 guard agreement and
adjudicated Se/Sp per cell; F5 DEV gate curves."""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from common import FIG, MKEYS, RESULTS  # noqa: E402

plt.rcParams.update({"font.size": 9, "pdf.fonttype": 42, "ps.fonttype": 42, "axes.spines.top": False,
                     "axes.spines.right": False})
COL = {"orig": "#4C72B0", "edit1": "#DD8452", "gate": "#C44E52", "rand1": "#8C8C8C"}
MN = {"gemma_it": "Gemma-3-12B-it", "gams3_it": "GaMS3-12B-Instruct"}


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / f"{name}.pdf")
    fig.savefig(FIG / f"{name}.png", dpi=200)
    plt.close(fig)


def main() -> None:
    A = json.loads((RESULTS / "analysis.json").read_text())
    rates = {(r["model"], r["lang"], r["ctag"]): r for r in A["rates"]}
    ctags = [c for c in ("orig", "edit1", "gate", "rand1") if any(k[2] == c for k in rates)]
    # F1
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.9), sharey=True)
    for ax, ro, title in zip(axes, ("asr", "pgr"), ("ASR_row (guard ensemble)", "PolyGuard response refusal")):
        x = np.arange(4)
        w = 0.8 / len(ctags)
        for j, c in enumerate(ctags):
            vals, lo, hi = [], [], []
            for m in MKEYS:
                for L in ("en", "sl"):
                    r = rates.get((m, L, c))
                    if r and r[ro]["n"]:
                        vals.append(r[ro]["p"])
                        lo.append(r[ro]["p"] - r[ro]["wilson"][0])
                        hi.append(r[ro]["wilson"][1] - r[ro]["p"])
                    else:
                        vals.append(np.nan)
                        lo.append(0)
                        hi.append(0)
            ax.bar(x + (j - (len(ctags) - 1) / 2) * w, vals, w, yerr=[lo, hi], color=COL[c], label=c, capsize=2)
        ax.set_xticks(x, [f"{MN[m].split('-')[0]}\n{L.upper()}" for m in MKEYS for L in ("en", "sl")])
        ax.set_title(title)
        ax.set_ylim(0, 1)
    axes[0].set_ylabel("share of FINAL prompts")
    axes[1].legend(frameon=False, fontsize=7)
    save(fig, "F1_paired_rates")
    # F2 forest
    eff = [e for e in A["edit_effects"] if e.get("n") and e["readout"] in ("asr", "sr05", "lg", "pg", "q3g", "pgr")]
    cd = {(c["model"], c["lang"], c["contrast"]): c for c in A.get("corrected_deltas", [])}
    fig, ax = plt.subplots(figsize=(6.5, 0.18 * len(eff) + 1.2))
    ys = np.arange(len(eff))[::-1]
    for y, e in zip(ys, eff):
        c = COL["gate"] if e["contrast"].endswith("gate") else COL["edit1"]
        ax.errorbar(e["delta"], y, xerr=[[e["delta"] - e["delta_ci"][0]], [e["delta_ci"][1] - e["delta"]]], fmt="o",
                    color=c, ms=3, capsize=2)
        k = cd.get((e["model"], e["lang"], e["contrast"]))
        if e["readout"] == "asr" and k and k["delta_rg"] is not None:
            ax.errorbar(k["delta_rg"], y - 0.3, xerr=[[k["delta_rg"] - k["ci"][0]], [k["ci"][1] - k["delta_rg"]]],
                        fmt="s", color="k", ms=3, capsize=2)
    ax.set_yticks(ys, [f"{e['model'].split('_')[0]} {e['lang']} {e['readout']} {e['contrast'].split('->')[1]}" for e in eff],
                  fontsize=6)
    ax.axvline(0, color="grey", lw=0.8)
    ax.set_xlabel("paired delta (edited - original), 95% bootstrap CI; black square = RG-corrected ASR delta")
    save(fig, "F2_forest_deltas")
    # F3 SR histograms
    fig, axes = plt.subplots(1, 4, figsize=(8, 2.2), sharey=True)
    edges = [0, .125, .25, .375, .5, .625, .75, .875, 1.0]
    for ax, (m, L) in zip(axes, [(m, L) for m in MKEYS for L in ("en", "sl")]):
        for c in ctags:
            r = rates.get((m, L, c))
            if r and r.get("sr_mean"):
                h = np.array(r["sr_mean"]["hist"], float)
                ax.step(edges[:-1], h / h.sum(), where="post", color=COL[c], label=c)
        ax.set_title(f"{m.split('_')[0]} {L.upper()}", fontsize=8)
        ax.set_xlabel("StrongREJECT-ft score")
    axes[0].set_ylabel("share")
    axes[-1].legend(frameon=False, fontsize=6)
    save(fig, "F3_sr_distributions")
    # F4 agreement + adjudicated Se/Sp
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.6))
    kap = [k for k in A["agreement"]["three_guard_kappa"] if k["ctag"] in ("orig", "edit1")]
    lab = [f"{k['model'].split('_')[0]}\n{k['lang']} {k['ctag']}" for k in kap]
    x = np.arange(len(kap))
    for j, (fld, c) in enumerate((("lg_pg", "#4C72B0"), ("lg_q3g", "#55A868"), ("pg_q3g", "#C44E52"))):
        axes[0].bar(x + (j - 1) * 0.27, [k[fld] for k in kap], 0.27, color=c, label=fld.replace("_", " vs "))
    axes[0].set_xticks(x, lab, fontsize=6)
    axes[0].set_ylabel("Cohen kappa")
    axes[0].legend(frameon=False, fontsize=6)
    adj = A.get("adjudication", {}).get("cells", {})
    if adj:
        cells = list(adj)
        x = np.arange(len(cells))
        for j, (ro, c) in enumerate((("asr", "#DD8452"), ("sr05", "#8172B3"), ("lg", "#4C72B0"), ("pg", "#C44E52"))):
            se = [adj[k][ro]["se_w"] for k in cells]
            sp = [adj[k][ro]["sp_w"] for k in cells]
            axes[1].scatter(x + (j - 1.5) * 0.15, se, marker="^", color=c, label=f"{ro} Se")
            axes[1].scatter(x + (j - 1.5) * 0.15, sp, marker="v", color=c)
        axes[1].axhline(0.8, ls="--", color="grey", lw=0.7)
        axes[1].axhline(0.6, ls=":", color="grey", lw=0.7)
        axes[1].set_xticks(x, [k.replace("|", "\n") for k in cells], fontsize=6)
        axes[1].set_ylim(0, 1.05)
        axes[1].set_title("adjudicated Se (^) / Sp (v), author-model gold", fontsize=8)
        axes[1].legend(frameon=False, fontsize=5, ncol=2)
    save(fig, "F4_agreement_validity")
    # F5 DEV gate curves
    fig, ax = plt.subplots(figsize=(4.2, 2.8))
    for m, c in zip(MKEYS, ("#4C72B0", "#C44E52")):
        p = RESULTS / f"dev_gate_{m}.json"
        if not p.exists():
            continue
        g = json.loads(p.read_text())
        lam = [x["lambda"] for x in g["curve"]]
        ax.plot(lam, [x["refuse"] for x in g["curve"]], "o-", color=c, label=f"{MN[m]} PG refusal")
        if all(x.get("lg_unsafe") is not None for x in g["curve"]):
            ax.plot(lam, [x["lg_unsafe"] for x in g["curve"]], "s--", color=c, alpha=0.6, label=f"{MN[m]} LG unsafe")
        if g["R0"]:
            ax.axhline(g["R0"] * 0.5, color=c, ls=":", lw=0.8)
    ax.set_xlabel("dose lambda (1.0 = saved edit)")
    ax.set_ylabel("share, DEV EN (n=100)")
    ax.legend(frameon=False, fontsize=6)
    save(fig, "F5_dev_gate")
    print("figures written")


if __name__ == "__main__":
    main()
