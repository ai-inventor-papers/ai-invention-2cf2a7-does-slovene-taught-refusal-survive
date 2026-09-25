#!/usr/bin/env python3
"""Figures drawn ONLY from results/analysis.json (vector PDF + PNG, Type-42 fonts, colour-blind-safe palette)."""
from __future__ import annotations

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from common import FIG, RESULTS  # noqa: E402

plt.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42, "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False})
C = {"gemma_it": "#0072B2", "gams3_it": "#D55E00", "pew_heretic": "#009E73"}
NAME = {"gemma_it": "Gemma-3-12B-IT", "gams3_it": "GaMS3-12B-Instruct", "pew_heretic": "p-e-w heretic (C-EXT)"}


def save(fig, name: str) -> None:
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(FIG / f"{name}.{ext}", dpi=200)
    plt.close(fig)


def fig1(A: dict) -> None:
    """safe rate (1 - U, local StrongREJECT on English text: the only readout present in every cell/dose) by reply
    language x dose, per model."""
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8), sharey=True)
    for ax, m in zip(axes, ("gemma_it", "gams3_it")):
        tags = [t for t in ("zero", "lo", "hi", "one") if f"{m}|EN>EN|{t}|std" in A["units"]]
        for cell, ls in (("EN>EN", "-"), ("EN>SL", "--"), ("EN>HU", ":")):
            ys = [(A["units"].get(f"{m}|{cell}|{t}|std", {}).get("local_U") or {}).get("S_or_R") for t in tags]
            xs = [i for i, y in enumerate(ys) if y is not None]
            ax.plot(xs, [ys[i] for i in xs], ls, marker="o", color=C[m], label=f"reply {cell.split('>')[1]}")
        lam = A["dose"].get(m, {})
        ax.set_xticks(range(len(tags)))
        ax.set_xticklabels([{"zero": "0", "lo": f"lo={lam.get('lambda_lo')}", "hi": f"hi={lam.get('lambda_hi')}",
                             "one": "1.0"}[t] for t in tags])
        ax.set_title(NAME[m])
        ax.set_xlabel("edit dose lambda")
        ax.set_ylim(0, 1.02)
        ax.legend(frameon=False, fontsize=7)
    axes[0].set_ylabel("safe rate S = 1 - U (local SR, EN text)")
    save(fig, "fig1_safe_rate_by_reply_language")


def fig2(A: dict) -> None:
    names = [("OUT|gemma_it|dose*", "OUT Gemma"), ("OUT|gams3_it|dose*", "OUT GaMS3"), ("dOUT|dose*", "dOUT"),
             ("IN|gemma_it|dose*", "IN Gemma"), ("OUT_SF|gemma_it|dose*", "OUT_SF Gemma"),
             ("SL_HU|gemma_it|dose*", "SL-HU Gemma"), ("OUT_edit|gemma_it", "OUT_edit Gemma"),
             ("OUT|gemma_it|zero", "OUT Gemma (lambda 0)")]
    ros = [("primary", "primary", "#000000"), ("raw_gemini", "raw gemini-U", "#0072B2"),
           ("local_U", "local SR (TTJ)", "#009E73"), ("gem_refused", "gemini refused", "#E69F00"),
           ("adj_U", "adjudicated U", "#CC79A7"), ("j1", "J1 refusal", "#999999")]
    m = A["verdicts"]["m"]
    fig, ax = plt.subplots(figsize=(7.8, 4.6))
    y = 0
    ticks = []
    for key, lab in names:
        e = A["estimands"].get(key) or {}
        present = [(r, l, c) for r, l, c in ros if r in e]
        if not present:
            continue
        for k, (r, l, c) in enumerate(present):
            v = e[r]
            yy = y - k * 0.12
            ax.errorbar(v["est"], yy, xerr=[[v["est"] - v["ci95"][0]], [v["ci95"][1] - v["est"]]], fmt="o", ms=3,
                        color=c, capsize=2, label=l if y == 0 or l not in ax.get_legend_handles_labels()[1] else None)
        ticks.append((y - 0.06 * (len(present) - 1), lab))
        y -= 1
    ax.axvspan(-m, m, color="#dddddd", alpha=0.5, lw=0)
    ax.axvline(0, color="k", lw=0.6)
    ax.set_yticks([t[0] for t in ticks])
    ax.set_yticklabels([t[1] for t in ticks])
    ax.set_xlabel("contrast (logit of safe/refusal rate), 95% bootstrap CI; grey band = +/- m")
    h, l = ax.get_legend_handles_labels()
    ax.legend(h, l, frameon=False, fontsize=7, loc="upper left", bbox_to_anchor=(1.01, 1.0))
    save(fig, "fig2_forest_estimands")


def fig3(A: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.9))
    langs = ["EN", "SL", "HU"]
    for ax, m in zip(axes, ("gemma_it", "gams3_it")):
        t = A["dose"].get(m, {}).get("dose_star_tag", "hi")
        M = np.full((3, 3), np.nan)
        for i, a in enumerate(langs):
            for j, b in enumerate(langs):
                u = A["units"].get(f"{m}|{a}>{b}|{t}|std")
                if u and u.get("local_U"):
                    M[i, j] = u["local_U"]["S_or_R"]
        im = ax.imshow(M, vmin=0, vmax=1, cmap="viridis")
        for i in range(3):
            for j in range(3):
                if np.isfinite(M[i, j]):
                    ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center",
                            color="w" if M[i, j] < 0.6 else "k", fontsize=8)
        ax.set_xticks(range(3))
        ax.set_xticklabels(langs)
        ax.set_yticks(range(3))
        ax.set_yticklabels(langs)
        ax.set_xlabel("reply language")
        ax.set_ylabel("prompt language")
        ax.set_title(f"{NAME[m]} @ dose* ({t})", fontsize=8)
    fig.colorbar(im, ax=axes, shrink=0.8, label="safe rate (local SR)")
    fig.savefig(FIG / "fig3_grid_heatmap.pdf")
    fig.savefig(FIG / "fig3_grid_heatmap.png", dpi=200)
    plt.close(fig)


def fig4(A: dict) -> None:
    sd = {k: v for k, v in A.get("sdt", {}).items() if "DiD" not in k}
    if not sd:
        return
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.8))
    keys = sorted(sd)
    for ax, f, lab in ((axes[0], "c", "criterion c (higher = more refusal)"), (axes[1], "dprime", "d'")):
        ax.barh(range(len(keys)), [sd[k][f] for k in keys], color=[C.get(k.split("|")[0], "#777") for k in keys])
        ax.set_yticks(range(len(keys)))
        ax.set_yticklabels([k.replace("gemma_it", "Gemma").replace("gams3_it", "GaMS3") for k in keys], fontsize=6)
        ax.set_xlabel(lab + " (J1, flagged)")
    save(fig, "fig4_sdt")


def fig5(A: dict) -> None:
    sb = A.get("secondary_benign_SB", {}).get("rates", {})
    if not sb:
        return
    fig, ax = plt.subplots(figsize=(6.4, 2.8))
    ros = [("gem_refused", "gemini refused (SB primary)", "#E69F00"), ("ttj_j1", "TTJ-J1", "#009E73"),
           ("j1", "J1 original", "#999999")]
    keys = ["gemma_it|EN>EN", "gemma_it|EN>SL", "gemma_it|SL>SL", "gemma_it|SL>EN", "gams3_it|EN>EN",
            "gams3_it|EN>SL", "gams3_it|SL>SL"]
    for k, (ro, lab, col) in enumerate(ros):
        vals = [(sb.get(ro) or {}).get(key) for key in keys]
        xs = [i + (k - 1) * 0.26 for i in range(len(keys))]
        ax.bar([x for x, v in zip(xs, vals) if v], [v["FR"] for v in vals if v], width=0.25, color=col, label=lab)
        for x, v in zip(xs, vals):
            if v:
                ax.plot([x, x], v["wilson95"], color="k", lw=0.7)
    ax.set_xticks(range(len(keys)))
    ax.set_xticklabels([k.replace("gemma_it|", "Gemma\n").replace("gams3_it|", "GaMS3\n") for k in keys], fontsize=7)
    ax.set_ylabel("false refusal of benign twins, lambda 0")
    ax.legend(frameon=False, fontsize=7)
    save(fig, "fig5_benign_false_refusal")


def main() -> None:
    A = json.loads((RESULTS / "analysis.json").read_text())
    for f in (fig1, fig2, fig3, fig4, fig5):
        try:
            f(A)
        except (KeyError, ValueError, TypeError) as e:
            print(f"{f.__name__} failed: {e}")


if __name__ == "__main__":
    main()
