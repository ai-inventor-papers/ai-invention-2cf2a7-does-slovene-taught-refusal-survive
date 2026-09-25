#!/usr/bin/env python3
"""Figures (PDF + PNG) drawn only from results/analysis.json, so a figure cannot disagree with the numbers."""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from common import FIG, RESULTS, setup_logging  # noqa: E402

logger = setup_logging("figures")
plt.rcParams.update({"font.size": 9, "pdf.fonttype": 42, "ps.fonttype": 42, "axes.spines.top": False,
                     "axes.spines.right": False})
COL = {"gemma_it": "#1f77b4", "gams3_it": "#d62728"}
NAME = {"gemma_it": "Gemma-3-12B-IT", "gams3_it": "GaMS3-12B-Instruct"}


def lg(p):
    p = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def ex(x):
    return 1 / (1 + np.exp(-np.asarray(x, float)))


def save(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(FIG / f"{name}.{ext}", dpi=200, bbox_inches="tight")
    plt.close(fig)


def wil(k, n, z=1.96):
    p = k / max(n, 1)
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, p - (c - h)), max(0.0, (c + h) - p)


def fig1(A):
    fig, ax = plt.subplots(figsize=(4.6, 4.0))
    for m in ("gemma_it", "gams3_it"):
        st = A["steps_R"][m]
        for s in st:
            e = wil(s["k_sl"], s["n_sl"])
            mk = "s" if s["lambda"] == 0 else "o"
            ax.errorbar(s["p_en"], s["p_sl"], yerr=[[e[0]], [e[1]]], fmt=mk, color=COL[m], ms=4, lw=0.8,
                        mfc="white" if s["lambda"] == 0 else COL[m])
        pm = A["headline"]["R"]["per_model"][m]
        xs = np.linspace(0.02, 0.98, 100)
        ax.plot(xs, ex(pm["a"]["point"] + pm["b"]["point"] * lg(xs)), color=COL[m], lw=1.4,
                label=f"{NAME[m]}: a={pm['a']['point']:.2f}, b={pm['b']['point']:.2f}")
    ax.plot([0, 1], [0, 1], ":", color="grey", lw=0.8)
    ax.axvline(0.5, color="grey", lw=0.6, ls="--")
    ax.set_xlabel("EN-BT refusal rate at step (primary judge, R)")
    ax.set_ylabel("SL-MT refusal rate at step")
    g = A["headline"]["R"]["RAW"]["G3"]
    ax.set_title(f"G3 = {g['point']:.2f} [{g['ci95'][0]:.2f}, {g['ci95'][1]:.2f}] (open square = lambda 0)", fontsize=8)
    ax.legend(fontsize=7, frameon=False, loc="upper left")
    save(fig, "fig1_sl_vs_en_per_step")


def fig2(A):
    fig, ax = plt.subplots(figsize=(4.8, 3.8))
    for m in ("gemma_it", "gams3_it"):
        st = A["steps_R"][m]
        x = [s["x_logit_en_hautus"] for s in st]
        y = [s["margin_M"] for s in st]
        ax.plot(x, y, "o-", color=COL[m], ms=4, lw=0.8, label=f"{NAME[m]} Heretic E_exp9 (per step)")
        pm = A["headline"]["R"]["per_model"][m]
        xs = np.linspace(min(x), max(x), 50)
        ax.plot(xs, pm["a"]["point"] + (pm["b"]["point"] - 1) * xs, "--", color=COL[m], lw=0.8)
    ra = A.get("random_arm", {})
    if ra.get("available"):
        for k, v in ra["by_rank"].items():
            for m in ("gemma_it", "gams3_it"):
                pm = v["per_model"][m]
                st0 = [s for s in A["steps_R"][m] if s["lambda"] == 0][0]
                M0 = st0["margin_M"]
                p_en = st0["p_en"] + pm["dEN_rand"]
                ax.plot(lg(p_en), M0 + pm["dM_rand"], "x", color=COL[m], ms=7, mew=1.5)
        ax.plot([], [], "kx", label="norm-matched random edit at lambda_R")
    ax.axhline(0, color="grey", lw=0.6)
    ax.axvline(0, color="grey", lw=0.6, ls="--")
    ax.set_xlabel("logit EN-BT refusal at step")
    ax.set_ylabel("margin M = logit p_SL - logit p_EN")
    ax.legend(fontsize=7, frameon=False)
    save(fig, "fig2_margin_rbase")


def fig3(A):
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.0))
    per = A["sdt"]["R"]["per_step"]
    for ax, key, lab in ((axs[0], "d_prime", "d' = z(H) - z(F)"), (axs[1], "c_ref", "c_ref = (z(H)+z(F))/2")):
        for m in ("gemma_it", "gams3_it"):
            for lang, ls in (("en", "-"), ("sl", "--")):
                r = sorted([p for p in per if p["model"] == m and p["lang"] == lang], key=lambda p: p["lambda"])
                ax.plot([p["en_R"] for p in r], [p[key] for p in r], "o" + ls, color=COL[m], ms=3, lw=0.8,
                        label=f"{NAME[m]} {lang.upper()}")
        ax.set_xlabel("EN-BT refusal at step")
        ax.set_ylabel(lab)
        ax.invert_xaxis()
    axs[0].legend(fontsize=6, frameon=False)
    save(fig, "fig3_sdt_per_step")


def fig4(A):
    rows = []
    for cod in ("R", "RP"):
        h = A["headline"][cod]
        rows.append((f"RAW {cod}", h["RAW"]["G3"]["point"], h["RAW"]["G3"]["ci95"]))
        for k in ("RG", "PPI"):
            if k in h:
                rows.append((f"{k} {cod}", h[k]["G3"]["point"], h[k]["G3"]["ci95"]))
        sf = h.get("second_family_IPW", {})
        if sf.get("available"):
            rows.append((f"gpt-4.1-mini IPW {cod}", sf["G3"], sf.get("G3_ci95") or [np.nan, np.nan]))
        t = A["ttj"].get(cod, {})
        if t.get("available"):
            rows.append((f"TTJ {cod}", t["G3"], t["G3_ci95"]))
        rows.append((f"G3_edit RAW {cod}", h["RAW"]["G3_edit"]["point"], h["RAW"]["G3_edit"]["ci95"]))
        rows.append((f"G3_orig RAW {cod}", h["RAW"]["G3_orig"]["point"], h["RAW"]["G3_orig"]["ci95"]))
        rows.append((f"IG RAW {cod}", h["RAW"]["IG"]["point"], h["RAW"]["IG"]["ci95"]))
    ctx = A["iter3_context"]
    rows += [("iter-3 exp9 G3", ctx["G3_exp9"], [np.nan, np.nan]), ("iter-3 exp11 G3", ctx["G3_exp11"], [np.nan, np.nan]),
             ("iter-3 eval2 IG", ctx["IG_eval2"], [np.nan, np.nan])]
    fig, ax = plt.subplots(figsize=(5.2, 0.28 * len(rows) + 0.8))
    for i, (lab, p, c) in enumerate(rows[::-1]):
        col = "grey" if lab.startswith("iter-3") else ("#555" if "G3_" in lab or "IG" in lab else "k")
        ax.errorbar(p, i, xerr=[[max(0, p - c[0])], [max(0, c[1] - p)]] if np.isfinite(c[0]) else None, fmt="o", color=col,
                    ms=4)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows[::-1]], fontsize=7)
    ax.axvline(0, color="grey", lw=0.6)
    ax.axvline(-A["m"], color="red", lw=0.6, ls="--")
    ax.set_xlim(-3.5, 3.5)  # clip: the Rogan-Gladen CI is uninformatively wide near its identifiability threshold
    ax.annotate("RG CI runs off-axis\n(near RG identifiability limit)", xy=(3.4, len(rows) - 2.5), fontsize=6,
                ha="right", va="center", color="#888")
    ax.set_xlabel("log-odds (GaMS - Gemma); dashed red = -m; axis clipped to [-3.5, 3.5]")
    save(fig, "fig4_g3_forest")


def fig5(A):
    cells = A["judge_validity"]["cells"]
    ks = [k for k in cells if cells[k].get("primary_R")]
    fig, ax = plt.subplots(figsize=(5.6, 3.0))
    for i, k in enumerate(ks):
        c = cells[k]["primary_R"]
        ax.errorbar(i - 0.12, c["Se"], yerr=[[max(0, c["Se"] - c["Se_ci"][0])], [max(0, c["Se_ci"][1] - c["Se"])]], fmt="o",
                    color="#1f77b4", ms=4, label="Se" if i == 0 else None)
        ax.errorbar(i + 0.12, c["Sp"], yerr=[[max(0, c["Sp"] - c["Sp_ci"][0])], [max(0, c["Sp_ci"][1] - c["Sp"])]], fmt="s",
                    color="#d62728", ms=4, label="Sp" if i == 0 else None)
    ax.axhline(0.8, color="grey", ls="--", lw=0.6)
    ax.set_xticks(range(len(ks)))
    ax.set_xticklabels([k.replace("|", "\n") for k in ks], fontsize=6)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("primary judge vs author-model adjudication (R)")
    ax.legend(fontsize=7, frameon=False)
    save(fig, "fig5_judge_se_sp")


@logger.catch(reraise=True)
def main() -> None:
    A = json.loads((RESULTS / "analysis.json").read_text())
    for f in (fig1, fig2, fig3, fig4, fig5):
        try:
            f(A)
            logger.info(f"{f.__name__} ok")
        except (KeyError, ValueError, IndexError, TypeError) as e:
            logger.error(f"{f.__name__} failed: {e}")


if __name__ == "__main__":
    main()
