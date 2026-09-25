#!/usr/bin/env python3
"""Figures from results/analysis.json only (no recomputation): figures/*.png."""
from __future__ import annotations

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from common import RES

FIG = RES.parent / "figures"
FIG.mkdir(exist_ok=True)
A = json.loads((RES / "analysis.json").read_text())
COL = {"gams": "#1f77b4", "gemma": "#d62728"}


def fig_rates():
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.6), sharey=True)
    conds = ["C0", "C1", "C2", "C3", "C4", "C5"]
    lab = ["orig", "persona\nlate", "persona\nearly", "iso\nrand", "var\nrand", "langid\nlate"]
    rates = A["primary"]["rates"]
    for ax, g in zip(axes, ["en", "sl"]):
        for k, m in enumerate(["gams", "gemma"]):
            v = [rates.get(f"{m}|{c}|{g}", np.nan) for c in conds]
            ax.bar(np.arange(6) + (k - 0.5) * 0.38, v, 0.38, color=COL[m], label=m)
        ax.set_xticks(range(6)); ax.set_xticklabels(lab, fontsize=8); ax.set_title(f"refusal rate, {g.upper()} (primary readout)")
        ax.set_ylim(0, 1)
    axes[0].legend(); fig.tight_layout(); fig.savefig(FIG / "refusal_rates.png", dpi=150); plt.close(fig)


def fig_forest():
    rows = []
    for rd, key in [("binary", "primary"), ("s", "s_coprimary")]:
        st = A[key]
        for c in ["C2", "C3", "C4", "C5"]:
            for m in ["gams", "gemma"]:
                g = st["G"].get(f"{m}|{c}")
                if g:
                    rows.append((f"{rd} G({m},{c})", g))
            if c in st["TD"]:
                rows.append((f"{rd} TD({c})", st["TD"][c]))
        if "TDstar" in st:
            rows.append((f"{rd} TD*", st["TDstar"]))
        if "DiD_ref_C0" in st:
            rows.append((f"{rd} DiD_ref(C0)", st["DiD_ref_C0"]))
    fig, ax = plt.subplots(figsize=(7, 0.28 * len(rows) + 1))
    for i, (n, v) in enumerate(rows):
        ax.errorbar(v["point"], i, xerr=[[v["point"] - v["ci95"][0]], [v["ci95"][1] - v["point"]]], fmt="o", color="k", ms=3)
    ax.axvline(0, color="grey", lw=0.8)
    ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[0] for r in rows], fontsize=7); ax.invert_yaxis()
    ax.set_xlabel("log-odds (binary) / s units; 95% pair-bootstrap CI")
    fig.tight_layout(); fig.savefig(FIG / "forest_G_TD.png", dpi=150); plt.close(fig)


def fig_sweep():
    sw = A.get("sweep_s", {})
    bands = ["b0_7", "b8_15", "b16_23", "b24_31", "b32_39", "b40_47"]
    fig, ax = plt.subplots(figsize=(6, 3.4))
    for m in ["gams", "gemma"]:
        pts = [sw.get(f"{m}|{b}", {}).get("net") for b in bands]
        if not all(pts):
            continue
        y = [p["point"] for p in pts]
        lo = [p["point"] - p["ci95"][0] for p in pts]; hi = [p["ci95"][1] - p["point"] for p in pts]
        ax.errorbar(range(6), y, yerr=[lo, hi], marker="o", color=COL[m], label=m, capsize=2)
    ax.axhline(0, color="grey", lw=0.8)
    ax.set_xticks(range(6)); ax.set_xticklabels(bands); ax.set_ylabel("shrink of SL-EN s gap:\npersona minus iso-random")
    ax.legend(); fig.tight_layout(); fig.savefig(FIG / "band_sweep_s.png", dpi=150); plt.close(fig)


def fig_identity():
    mc = A.get("manipulation_checks", {})
    keys = [k for k in mc if "judge_identity" in mc[k]]
    if not keys:
        return
    fig, axes = plt.subplots(1, len(keys), figsize=(3.2 * len(keys), 3.4), sharey=True, squeeze=False)
    conds = ["original", "persona_late", "persona_early", "iso1_late", "var1_late"]
    for ax, k in zip(axes[0], keys):
        ji = mc[k]["judge_identity"]
        for j, g in enumerate(["en", "sl"]):
            own = [ji.get(f"{c}|{g}", {}).get("own_name_rate", np.nan) for c in conds]
            qw = [ji.get(f"{c}|{g}", {}).get("qwen_rate", np.nan) for c in conds]
            x = np.arange(5) + (j - 0.5) * 0.38
            ax.bar(x, own, 0.38, color=["#4c72b0", "#55a868"][j], label=f"own name {g}")
            ax.bar(x, qw, 0.38, bottom=np.nan_to_num(own), color=["#c44e52", "#dd8452"][j], label=f"'Qwen' {g}")
        ax.set_xticks(range(5)); ax.set_xticklabels(["orig", "pers\nlate", "pers\nearly", "iso", "var"], fontsize=8)
        ax.set_title(k.replace("@mean_skipbos", "\n(mean-proj)"), fontsize=8); ax.set_ylim(0, 1)
    axes[0][0].legend(fontsize=6); axes[0][0].set_ylabel("share of ID-CHECK replies (gemini judge)")
    fig.tight_layout(); fig.savefig(FIG / "identity_mc.png", dpi=150); plt.close(fig)


if __name__ == "__main__":
    for f in (fig_rates, fig_forest, fig_sweep, fig_identity):
        try:
            f()
        except (KeyError, ValueError, TypeError) as e:
            print(f"figure {f.__name__} skipped: {e!r}")
    print(sorted(p.name for p in FIG.glob("*.png")))
