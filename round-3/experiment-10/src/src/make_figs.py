#!/usr/bin/env python3
"""Figures from saved results only (results/analysis.json, results/<M>/geometry_*.json, results/rq4.json).
figures/: fig1_geometry_per_layer, fig2_induction_curves, fig3_switch_ecdf, fig4_addon_bars, fig5_rq4_per_layer (PNG + PDF)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import FIGS, MODELS, MODEL_ORDER, RESULTS  # noqa: E402

plt.rcParams.update({"font.size": 9, "pdf.fonttype": 42, "axes.spines.top": False, "axes.spines.right": False})
COL = {"gemma_it": "#1f6fb2", "gams3_it": "#d0661b"}
DCOL = {"u_SLperp": "#c0392b", "rEN": "#2c3e50", "u_lang": "#27ae60", "rand1": "#999999", "rand2": "#b3b3b3", "rand3": "#cccccc"}
J1 = "surrogate/gemini"


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIGS / f"{name}.png", dpi=200)
    fig.savefig(FIGS / f"{name}.pdf")
    plt.close(fig)


def main():
    A = json.loads((RESULTS / "analysis.json").read_text())
    models = [m for m in MODEL_ORDER if (RESULTS / m / "geometry_post.json").exists()]
    # ---- fig1 geometry per layer
    fig, ax = plt.subplots(1, 4, figsize=(13, 3))
    for M in models:
        g = json.loads((RESULTS / M / "geometry_post.json").read_text())
        L = [x["layer"] for x in g]
        c = COL[M]
        ax[0].plot(L, [x["f"] for x in g], color=c, label=MODELS[M]["label"])
        ax[0].fill_between(L, [x["f_ci95"][0] for x in g], [x["f_ci95"][1] for x in g], color=c, alpha=.2)
        ax[1].plot(L, [x["cos_EN_SL"] for x in g], color=c)
        ax[1].plot(L, [x["ceiling_cos_EN_SL"] for x in g], color=c, ls=":", lw=1)
        ax[1].plot(L, [x["cos_ENo_ENbt"] for x in g], color=c, ls="--", lw=1)
        ax[2].plot(L, [x["rho"] for x in g], color=c)
        ax[2].fill_between(L, [x["rho_ci95"][0] for x in g], [x["rho_ci95"][1] for x in g], color=c, alpha=.2)
        ax[3].plot(L, [x["dp_SL_along_rEN"] for x in g], color=c)
        ax[3].plot(L, [x["dp_SL_along_rSL"] for x in g], color=c, ls="--")
        Ls = A["dev_decisions"][M]["layer"]["L_star"]
        for a in ax:
            a.axvline(Ls, color=c, lw=.8, alpha=.5)
    ax[0].set_title("f = share of SL dir. energy in EN dir.")
    ax[1].set_title("cos(r_EN, r_SL) (: split-half ceiling, -- EN-orig vs EN-BT)")
    ax[2].set_title("rho = SL harm proj. on r_EN / EN")
    ax[3].set_title("d' of SL harm vs harmless (— r_EN, -- r_SL)")
    for a in ax:
        a.set_xlabel("layer")
    ax[0].legend(frameon=False)
    save(fig, "fig1_geometry_per_layer")
    # ---- fig2 induction curves
    ind = {k: v for k, v in A["induction"].items() if k.startswith(f"{J1}|R|") and k.endswith("|exclude")}
    if ind:
        fig, ax = plt.subplots(len(models), 2, figsize=(10, 3.2 * len(models)), squeeze=False)
        for i, M in enumerate(models):
            r = ind.get(f"{J1}|R|{M}|exclude")
            if not r:
                continue
            x = r["levels"]
            for j, lang in enumerate(("en", "sl")):
                for d in DCOL:
                    c = r["curves"].get(f"{d}|{lang}")
                    if not c:
                        continue
                    ax[i, j].plot(x, [np.nan if v is None else v for v in c["rate"]], marker="o", ms=3, color=DCOL[d],
                                  label=f"{d} (a50={'>' if c['censored'] else ''}{c['alpha50']:.2f})")
                ax[i, j].set_title(f"{MODELS[M]['label']} - harmless {'EN-BT' if lang == 'en' else 'SL-MT'} prompts")
                ax[i, j].set_xlabel("K (alpha / |d|)")
                ax[i, j].set_ylabel("refusal rate (local judge)")
                ax[i, j].set_ylim(-.02, 1.02)
                ax[i, j].legend(frameon=False, fontsize=7)
        save(fig, "fig2_induction_curves")
        fig, ax = plt.subplots(1, len(models), figsize=(5 * len(models), 3), squeeze=False)
        for i, M in enumerate(models):
            r = ind.get(f"{J1}|R|{M}|exclude")
            if not r:
                continue
            for d in ("u_SLperp", "rEN", "u_lang", "rand1"):
                for lang, ls in (("en", "--"), ("sl", "-")):
                    c = r["curves"].get(f"{d}|{lang}")
                    if not c or not c["switch_points"]:
                        continue
                    sp = [np.inf if s is None else s for s in c["switch_points"]]
                    xs = np.sort(sp)
                    ax[0, i].step(np.r_[0, xs[np.isfinite(xs)]], np.r_[0, np.arange(1, np.isfinite(xs).sum() + 1) / len(xs)],
                                  where="post", color=DCOL[d], ls=ls, label=f"{d} {lang}")
            ax[0, i].set_title(f"{MODELS[M]['label']}: per-prompt switch points (ECDF)")
            ax[0, i].set_xlabel("K")
            ax[0, i].legend(frameon=False, fontsize=6)
        save(fig, "fig3_switch_ecdf")
    # ---- fig4 add-on
    add = {k: v for k, v in A["addon"].items() if k.startswith(f"{J1}|R|")}
    if add:
        fig, ax = plt.subplots(1, 2, figsize=(12, 3.4))
        w = 0.38
        for i, M in enumerate(models):
            r = add.get(f"{J1}|R|{M}")
            if not r:
                continue
            conds = [c for c in r["conditions"] if c != "O"]
            conds = ["E0"] + [c for c in conds if c != "E0"]
            xs = np.arange(len(conds)) + (i - .5) * w
            for k, (key, cik) in enumerate((("Lag", "Lag_ci"), ("BenignExcess", "BenignExcess_ci"))):
                v = [r["conds"][c][key] for c in conds]
                lo = [r["conds"][c][key] - r["conds"][c][cik][0] for c in conds]
                hi = [r["conds"][c][cik][1] - r["conds"][c][key] for c in conds]
                ax[k].bar(xs, v, w, yerr=[lo, hi], color=COL[M], alpha=.85, label=MODELS[M]["label"], capsize=2)
                ax[k].set_xticks(np.arange(len(conds)))
                ax[k].set_xticklabels(conds, rotation=35, ha="right")
                ax[k].axhline(0, color="k", lw=.6)
        ax[0].set_title("Lag = logit R_SL - logit R_EN (TEST160 harmful)")
        ax[1].set_title("BenignExcess = logit FA_SL - logit FA_EN (hard benign)")
        ax[0].legend(frameon=False)
        save(fig, "fig4_addon_bars")
    # ---- fig5 RQ4
    if (RESULTS / "rq4.json").exists():
        rq = json.loads((RESULTS / "rq4.json").read_text())
        fig, ax = plt.subplots(1, 3, figsize=(13, 3))
        for M in models:
            if M not in rq:
                continue
            for st, ls in (("O", "-"), ("E1", "--"), ("Estar", ":")):
                rows = [r for r in rq[M]["rows"] if r["state"] == st and r["pos"] == "post"]
                L = [r["layer"] for r in rows]
                ax[0].plot(L, [r["sl_mt"]["auroc"] for r in rows], color=COL[M], ls=ls, label=f"{M} {st}")
                ax[1].plot(L, [r["sl_mt"]["dprime_fixed_probe"] for r in rows], color=COL[M], ls=ls)
                ax[2].plot(L, [r["transfer"]["en_bt->sl_mt"] for r in rows], color=COL[M], ls=ls)
        ax[0].set_title("SL-MT probe AUROC (5-fold CV)")
        ax[1].set_title("SL d' along ORIGINAL r_SL (fixed probe)")
        ax[2].set_title("transfer AUROC EN-BT -> SL-MT")
        ax[0].legend(frameon=False, fontsize=6)
        for a in ax:
            a.set_xlabel("layer")
        save(fig, "fig5_rq4_per_layer")
    print("figures written")


if __name__ == "__main__":
    main()
