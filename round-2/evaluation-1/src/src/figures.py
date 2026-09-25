#!/usr/bin/env python3
"""Figures from work/eval_full.json + work/verdict_table.json (numbers are read, never re-typed)."""
from __future__ import annotations

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from common import FIG, WORK  # noqa: E402

plt.rcParams.update({"font.size": 9, "pdf.fonttype": 42, "ps.fonttype": 42, "axes.spines.top": False, "axes.spines.right": False})
C = {"P1_real_or_pooled": "#1f5fa8", "P1_sur": "#d98c1f", "native": "#3a9a5b", "lex": "#9a9a9a", "JP2": "#b0413e"}
P = "P1_real_or_pooled"


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / f"{name}.pdf")
    fig.savefig(FIG / f"{name}.png", dpi=200)
    plt.close(fig)


def forest(E):
    MA = E["M5_meta_analysis"]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    names = list(MA[P]["estimates"].keys())
    ys = np.arange(len(names))[::-1] + 2.0
    offs = {P: 0.18, "P1_sur": 0.0, "native": -0.18}
    for r, off in offs.items():
        ma = MA.get(r)
        if not isinstance(ma, dict):
            continue
        for y, n in zip(ys, names):
            e = ma["estimates"].get(n)
            if e:
                ax.errorbar(e["est"], y + off, xerr=[[e["est"] - e["ci95"][0]], [e["ci95"][1] - e["est"]]], fmt="o", ms=4,
                            color=C[r], capsize=2, label=r if n == names[0] else None)
    pk = [k for k in MA[P]["pooled"] if k.startswith("natural_k")][0]
    pn = MA[P]["pooled"][pk]
    g = pn["GLS_fixed_bootcov"]
    ax.errorbar(g["mu"], 1.0, xerr=[[g["mu"] - pn["GLS_bootstrap_ci95"][0]], [pn["GLS_bootstrap_ci95"][1] - g["mu"]]], fmt="D", color="k", ms=6, capsize=3)
    re_ = pn["RE_REML_HKSJmod_independence"]
    ax.errorbar(re_["mu"], 0.4, xerr=[[re_["mu"] - re_["ci95_hksj_mod"][0]], [re_["ci95_hksj_mod"][1] - re_["mu"]]], fmt="s", color="#555", ms=5, capsize=3)
    ax.plot(re_["prediction_interval95"], [0.4, 0.4], color="#555", lw=0.8, ls=":")
    ax.set_yticks(list(ys) + [1.0, 0.4])
    ax.set_yticklabels([n.replace("_", " ") for n in names] + ["pooled natural: GLS (boot cov)", "RE REML+HKSJ (indep.) + 95% PI"])
    ax.axvline(0, color="k", lw=0.6)
    for m in (-0.402, 0.402):
        ax.axvline(m, color="#bbb", lw=0.6, ls="--")
    ax.set_xlabel("GaMS-minus-Gemma Slovene DiD, Hautus log-odds  [GaMS(SL-EN) - Gemma(SL-EN)]")
    ax.set_title(f"Which GaMS Slovene deficit? I^2={re_['I2']:.2f}, tau={re_['tau']:.2f}; E5 (exp3 slmt) not judgeable", fontsize=9)
    ax.legend(loc="lower left", fontsize=7, frameon=False)
    save(fig, "fig1_forest_meta")


def agreement_heatmap(E):
    oof = E["M2_surrogates"]["pooled_surrogate_oof_vs_own_prompt"]
    gate = E["cell_gate"]
    keys = [k for k in gate if not k.startswith("exp1|gemma_it|construct")]
    keys = sorted(keys, key=lambda k: (k.split("|")[0], k.split("|")[2], k.split("|")[1], k.split("|")[3]))
    cols = ["real P1 share", "surrogate OOF kappa", "surrogate OOF PABAK", "gate"]
    M = np.full((len(keys), len(cols)), np.nan)
    for i, k in enumerate(keys):
        M[i, 0] = gate[k]["real_P1_share"]
        o = oof.get(k)
        if o:
            M[i, 1] = o["kappa"] if o["kappa"] is not None else np.nan
            M[i, 2] = o["PABAK"]
        M[i, 3] = {"VALID": 1.0, "FAILS": 0.0, "UNVALIDATED": 0.5}[gate[k]["status"]]
    fig, ax = plt.subplots(figsize=(5.4, 0.16 * len(keys) + 1.2))
    im = ax.imshow(M, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_yticks(range(len(keys)))
    ax.set_yticklabels([k.replace("gams3_it", "GaMS").replace("gemma_it", "Gemma") for k in keys], fontsize=5.5)
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=20, fontsize=7)
    for i in range(len(keys)):
        for j in range(len(cols)):
            if np.isfinite(M[i, j]):
                t = {1.0: "VALID", 0.0: "FAIL", 0.5: "UNVAL"}[M[i, j]] if j == 3 else f"{M[i, j]:.2f}"
                ax.text(j, i, t, ha="center", va="center", fontsize=4.8)
    ax.set_title("Readout validity per cell (gate: kappa>=.6 or PABAK>=.8 & prev>.7; A2: kappa>=.4 if >=10 minority)", fontsize=6.5)
    fig.colorbar(im, ax=ax, fraction=0.03)
    save(fig, "fig2_agreement_heatmap")


def depth(E):
    M = E["M4_rederived"]
    series = {"lexicon (iter-1)": (M["exp4_lexicon_depth_curve"], C["lex"], "--"),
              "harmonised P1_real_or_pooled (provisional)": (M[P]["exp4"]["depth_curve_with_ci"], C[P], "-"),
              "JP2 real judge (Gemma) / pooled-JP2 (GaMS)": (M["exp4_sensitivity_JP2_native_gemma_plus_pooledJP2_gams"]["depth_curve_with_ci"], C["JP2"], "-.")}
    fig, axes = plt.subplots(1, 4, figsize=(9.5, 2.8), sharey=True)
    for ax, (m, l) in zip(axes, [("gemma_it", "en"), ("gemma_it", "sl"), ("gams3_it", "en"), ("gams3_it", "sl")]):
        for lab, (d, col, ls) in series.items():
            c = d[f"{m}|{l}"]
            ks = [5, 10, 20]
            f = [c[str(k)]["flip_rate"] for k in ks]
            lo = [c[str(k)]["wilson95"][0] for k in ks]
            hi = [c[str(k)]["wilson95"][1] for k in ks]
            ax.plot(ks, f, ls, color=col, marker="o", ms=3, label=lab)
            ax.fill_between(ks, lo, hi, color=col, alpha=0.12)
        ax.set_title(f"{'GaMS' if 'gams' in m else 'Gemma'} {l.upper()}", fontsize=8)
        ax.set_xticks([5, 10, 20])
        ax.set_xlabel("prefill length k (tokens)")
    axes[0].set_ylabel("flip rate | refused at k=0")
    axes[0].legend(fontsize=5.5, frameon=False, loc="upper left")
    fig.suptitle("Prefill depth curves by readout (GaMS cells: no real judge label exists; only Gemma-JP2 is a real judge)", fontsize=8)
    save(fig, "fig3_prefill_depth_by_readout")


def c3(E):
    M = E["M4_rederived"]
    fig, axes = plt.subplots(1, 2, figsize=(7, 3), sharex=True, sharey=True)
    for ax, (r, name) in zip(axes, [("lex", "lexicon (iter-1)"), (P, "harmonised (provisional)")]):
        pts = M[r]["exp4"]["C3"]["lambda_points"]
        for m, col in (("gemma_it", "#444"), ("gams3_it", "#c0392b")):
            p = pts[m]
            ax.plot(p["x_EN_logodds"], p["y_SL_logodds"], "o-", color=col, ms=3, label=f"{'GaMS' if 'gams' in m else 'Gemma'} a={p['a']:+.2f}, b={p['b']:.2f}")
        g = M[r]["exp4"]["C3"]["G3_lambda_curve"]
        ax.plot([-3, 4], [-3, 4], color="#ccc", lw=0.6)
        ax.set_title(f"{name}: lambda-curve G3={g['est']:+.2f} [{g['ci95'][0]:+.2f},{g['ci95'][1]:+.2f}]", fontsize=7.5)
        ax.set_xlabel("EN refusal (Hautus log-odds)")
        ax.legend(fontsize=6.5, frameon=False)
    axes[0].set_ylabel("SL refusal (Hautus log-odds)")
    save(fig, "fig4_c3_lambda_curves")


def readout_sensitivity(E):
    M = E["M4_rederived"]
    rows = []
    def ex(r, path):
        d = M[r]
        for k in path:
            if not isinstance(d, dict) or k not in d:
                return None
            d = d[k]
        return (d.get("est", d.get("point")), d["ci95"])
    stats = [("ALT-4 Sig_EN", ["exp4", "ALT4", "Sig", "en"]), ("ALT-4 Sig_SL", ["exp4", "ALT4", "Sig", "sl"]),
             ("C3 G3 (17 trials)", ["exp4", "C3", "G3_matched_first17"]), ("E6 exp4 DiD", ["exp4", "DiD_ref_orig_score400"]),
             ("E4 exp3 DiD_C0", ["exp3", "DiD_ref_C0"]), ("ALT-3 TD*", ["exp3", "TDstar"]), ("E3 exp2 DiD", ["exp2_DiD_SCORE400"]),
             ("E1 exp1 DiD", ["exp1", "iter1_hypothesis_groups", "overall"])]
    readouts = [("lex", C["lex"]), ("native", C["native"]), ("P1_sur", C["P1_sur"]), (P, C[P])]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    for i, (lab, path) in enumerate(stats):
        for j, (r, col) in enumerate(readouts):
            v = ex(r, path)
            if v and v[0] is not None:
                y = len(stats) - i + (j - 1.5) * 0.17
                ax.errorbar(v[0], y, xerr=[[v[0] - v[1][0]], [v[1][1] - v[0]]], fmt="o", ms=3, color=col, capsize=1.5,
                            label=r if i == 0 or (lab == "E6 exp4 DiD" and r == "native") else None)
        jp = M["exp4_sensitivity_JP2_native_gemma_plus_pooledJP2_gams"]
        if path[0] == "exp4":
            d = jp
            for k in path[1:]:
                d = d[k]
            y = len(stats) - i + 2.5 * 0.17
            ax.errorbar(d["est"], y, xerr=[[d["est"] - d["ci95"][0]], [d["ci95"][1] - d["est"]]], fmt="^", ms=3, color=C["JP2"], capsize=1.5,
                        label="JP2 (Gemma real) + pooled-JP2 (GaMS)" if i == 0 else None)
    ax.set_yticks([len(stats) - i for i in range(len(stats))])
    ax.set_yticklabels([s[0] for s in stats])
    ax.axvline(0, color="k", lw=0.6)
    ax.set_xlim(-6, 6)
    ax.set_xlabel("statistic (log-odds), 95% bootstrap CI")
    ax.set_title("Readout sensitivity: the same saved responses, different refusal readouts", fontsize=8.5)
    h, l = ax.get_legend_handles_labels()
    seen = {}
    for hh, ll in zip(h, l):
        seen.setdefault(ll, hh)
    ax.legend(seen.values(), seen.keys(), fontsize=6.5, frameon=False, loc="lower right")
    save(fig, "fig5_readout_sensitivity")


def verdict_fig(VT):
    cols = ["claim", "iter-1 verdict", "harmonised verdict", "changed", "readout-robust", "cells valid"]
    cell = [[v["claim"][:48], v["original_verdict"][:46], v["judged_verdict"][:42], v["changed"], str(v["readout_robust"])[:7],
             str(v["input_cells_valid"])] for v in VT]
    fig, ax = plt.subplots(figsize=(11, 0.34 * len(cell) + 0.8))
    ax.axis("off")
    t = ax.table(cellText=cell, colLabels=cols, loc="center", cellLoc="left", colWidths=[0.27, 0.26, 0.24, 0.06, 0.09, 0.08])
    t.auto_set_font_size(False)
    t.set_fontsize(6.5)
    for (i, j), c in t.get_celld().items():
        if i > 0 and j == 3 and cell[i - 1][3] == "Y":
            c.set_facecolor("#fde2c8")
        if i > 0 and j == 5 and cell[i - 1][5] == "False":
            c.set_facecolor("#f6c8c8")
    ax.set_title("Verdict table (M7): iter-1 vs harmonised readout", fontsize=9)
    save(fig, "fig6_verdict_table")


def main():
    E = json.loads((WORK / "eval_full.json").read_text())
    VT = json.loads((WORK / "verdict_table.json").read_text())
    forest(E)
    agreement_heatmap(E)
    depth(E)
    c3(E)
    readout_sensitivity(E)
    verdict_fig(VT)
    print(sorted(p.name for p in FIG.glob("*.png")))


if __name__ == "__main__":
    main()
