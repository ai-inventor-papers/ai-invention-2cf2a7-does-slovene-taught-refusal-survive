#!/usr/bin/env python3
"""Figures from results/analysis.json only (no hand-typed numbers):
F1 3x3 heatmaps of L* (edit-induced lag at matched EN->EN 50%) per model; F2 forest plot of OUT/IN/INT (SL) per model x
readout; F3 per-cell dose curves (R vs dose); F4 SDT d'/c per cell at lambda_hi; F5 judge Se/Sp per judge cell;
F6 C-EXT refusal per cell. PDF + PNG."""
from __future__ import annotations

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from common import FIG, RESULTS  # noqa: E402

plt.rcParams.update({"pdf.fonttype": 42, "ps.fonttype": 42, "font.size": 9})
L = ["en", "sl", "hu"]
NAMES = {"gemma_it": "Gemma-3-12B-IT", "gams3_it": "GaMS3-12B-Instruct"}
COL = {"gemma_it": "#1f77b4", "gams3_it": "#d62728"}


def eb(v, lo, hi):
    """non-negative, finite error-bar half widths"""
    a = 0.0 if lo is None or not np.isfinite(lo) else max(0.0, v - lo)
    b = 0.0 if hi is None or not np.isfinite(hi) else max(0.0, hi - v)
    return [[a], [b]]


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / f"{name}.pdf")
    fig.savefig(FIG / f"{name}.png", dpi=200)
    plt.close(fig)


def main() -> None:
    A = json.loads((RESULTS / "analysis.json").read_text())
    S = A["readouts"]["raw_R"]
    # F1
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.6))
    for ax, m in zip(axes, ("gemma_it", "gams3_it")):
        M = np.full((3, 3), np.nan)
        txt = [["" for _ in L] for _ in L]
        for a, i in enumerate(L):
            for b, o in enumerate(L):
                s = S.get(f"Lstar|{m}|{i}{o}")
                if s and s["est"] is not None:
                    M[a, b] = s["est"]
                    ci = s["ci95"]
                    txt[a][b] = f"{s['est']:.2f}\n[{ci[0]:.2f},{ci[1]:.2f}]" if ci[0] is not None else f"{s['est']:.2f}"
        v = np.nanmax(np.abs(M)) if np.isfinite(M).any() else 1
        im = ax.imshow(M, cmap="RdBu_r", vmin=-v, vmax=v)
        for a in range(3):
            for b in range(3):
                ax.text(b, a, txt[a][b], ha="center", va="center", fontsize=7)
        ax.set_xticks(range(3), [x.upper() for x in L])
        ax.set_yticks(range(3), [x.upper() for x in L])
        ax.set_xlabel("output language (suffix)")
        ax.set_ylabel("input language")
        ax.set_title(f"{NAMES[m]}: L* (logit)")
        fig.colorbar(im, ax=ax, fraction=0.046)
    save(fig, "F1_lstar_heatmaps")
    # F2 forest
    fig, ax = plt.subplots(figsize=(7, 4.2))
    rows = []
    for m in ("gemma_it", "gams3_it"):
        for tag in ("raw_R", "rg_R", "ppi_R", "ttj_R", "second_R", "raw_RP"):
            for st in ("OUT_SL", "IN_SL", "INT_SL"):
                s = A["readouts"].get(tag, {}).get(f"{st}|{m}")
                if s and s["ci95"][0] is not None:
                    rows.append((f"{NAMES[m][:6]} {st} {tag}", s["est"], s["ci95"], m))
    for k, (lab, e, ci, m) in enumerate(rows):
        ax.errorbar(e, k, xerr=eb(e, ci[0], ci[1]), fmt="o", color=COL[m], ms=3, capsize=2)
    ax.axvline(0, color="k", lw=0.6)
    ax.set_yticks(range(len(rows)), [r[0] for r in rows], fontsize=5.5)
    ax.invert_yaxis()
    ax.set_xlabel("logit (95% item-bootstrap CI)")
    ax.set_title("Output- vs input-side share of the edit-induced Slovene lag")
    save(fig, "F2_out_in_forest")
    # F3 dose curves
    ct = A["cell_table"]
    fig, axes = plt.subplots(3, 3, figsize=(8, 7), sharex=True, sharey=True)
    for a, i in enumerate(L):
        for b, o in enumerate(L):
            ax = axes[a, b]
            for m in ("gemma_it", "gams3_it"):
                st = A["lambda_steps"].get(m)
                if not st:
                    continue
                xs, ys, lo, hi = [], [], [], []
                for d, lam in (("zero", 0.0), ("lo", st["lambda_lo"]), ("hi", st["lambda_hi"])):
                    c = ct.get(f"{m}|{d}|{i}{o}|harmful")
                    if c:
                        xs.append(lam)
                        ys.append(c["R"])
                        e_ = eb(c["R"], *c["R_ci"])
                        lo.append(e_[0][0])
                        hi.append(e_[1][0])
                ax.errorbar(xs, ys, yerr=[lo, hi], marker="o", color=COL[m], ms=3, capsize=2, label=NAMES[m])
            ax.set_title(f"{i.upper()}->{o.upper()}", fontsize=8)
            ax.axhline(0.5, color="grey", lw=0.5, ls=":")
    axes[2, 1].set_xlabel("lambda (model-specific steps)")
    axes[1, 0].set_ylabel("refusal rate (primary judge)")
    axes[0, 0].legend(fontsize=6)
    save(fig, "F3_dose_curves")
    # F4 SDT
    sd = A["sdt"]["cells"]
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.2))
    for ax, key in zip(axes, ("d'", "c")):
        for k, m in enumerate(("gemma_it", "gams3_it")):
            for d, mk in (("zero", "o"), ("hi", "s")):
                xs, ys = [], []
                for j, (i, o) in enumerate([(i, o) for i in L for o in L]):
                    c = sd.get(f"{m}|{d}|{i}{o}")
                    if c:
                        xs.append(j + 0.15 * k)
                        ys.append(c[key])
                ax.plot(xs, ys, mk, color=COL[m], ms=4, label=f"{NAMES[m][:6]} {d}", alpha=0.85)
        ax.set_xticks(range(9), [f"{i}{o}".upper() for i in L for o in L], fontsize=6)
        ax.set_title(f"SDT {key} per cell")
    axes[0].legend(fontsize=6)
    save(fig, "F4_sdt")
    # F5 judge validity
    jv = A["judge_validity"].get("L_primary|R", {})
    cells = [c for c in jv if not c.startswith("_")]
    fig, ax = plt.subplots(figsize=(7, 3.2))
    for k, c in enumerate(cells):
        s = jv[c]
        ax.errorbar(k - 0.1, s["Se"], yerr=eb(s["Se"], *s["Se_ci"]), fmt="o", color="C2",
                    ms=3, capsize=2, label="Se" if k == 0 else None)
        ax.errorbar(k + 0.1, s["Sp"], yerr=eb(s["Sp"], *s["Sp_ci"]), fmt="s", color="C4",
                    ms=3, capsize=2, label="Sp" if k == 0 else None)
    ax.axhline(0.8, color="grey", ls=":", lw=0.6)
    ax.set_xticks(range(len(cells)), cells, rotation=60, fontsize=5.5, ha="right")
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=6)
    ax.set_title("Primary judge vs blind author-model adjudication (NOT human)")
    save(fig, "F5_judge_validity")
    # F6 C-EXT
    ce = A.get("c_ext", {})
    if ce:
        fig, ax = plt.subplots(figsize=(6, 3))
        for k, (m, e) in enumerate(ce.items()):
            vals = [e.get(f"{i}{o}", {}).get("R", np.nan) for i in L for o in L]
            ax.bar(np.arange(9) + 0.3 * k, vals, width=0.3, label=m)
        g0 = [A["cell_table"].get(f"gemma_it|zero|{i}{o}|harmful", {}).get("R", np.nan) for i in L for o in L]
        ax.plot(np.arange(9), g0, "k_", ms=12, label="Gemma lambda 0")
        ax.set_xticks(range(9), [f"{i}{o}".upper() for i in L for o in L], fontsize=7)
        ax.set_ylabel("refusal rate")
        ax.legend(fontsize=6)
        ax.set_title("Public English-abliterated Gemma checkpoint(s): residual refusal per cell")
        save(fig, "F6_cext")
    print("figures written")


if __name__ == "__main__":
    main()
