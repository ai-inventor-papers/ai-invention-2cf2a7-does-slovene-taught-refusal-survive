#!/usr/bin/env python3
"""STEP 8 figures (results/figs/*.pdf|png) drawn from results/analysis.json + items_final.jsonl."""
from __future__ import annotations

import json
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from common import MODEL_ORDER, RESULTS, read_jsonl  # noqa: E402

FIG = RESULTS / "figs"
FIG.mkdir(parents=True, exist_ok=True)
COL = {"gemma_it": "#2a6fdb", "gams3_it": "#d9480f"}
NAME = {"gemma_it": "Gemma-3-12B-IT", "gams3_it": "GaMS3-12B-Instruct"}
plt.rcParams.update({"font.size": 9, "pdf.fonttype": 42, "ps.fonttype": 42})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / f"{name}.pdf")
    fig.savefig(FIG / f"{name}.png", dpi=180)
    plt.close(fig)


def main():
    A = json.loads((RESULTS / "analysis.json").read_text())
    rows = read_jsonl(RESULTS / "items_final.jsonl")
    ro = A["primary_readout"]
    # (1) transfer curves
    panels = [("B", "trial", "B: fresh Heretic trials (P100, 64 tok)"), ("A1", "lambda", "A1: lambda x iter-1 adapter"),
              ("A2", "ablate", "A2: graded own-EN-direction ablation")]
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.6))
    for ax, (key, curve, title) in zip(axes, panels):
        g = A["G3"].get(key, {})
        for m in MODEL_ORDER:
            pm = g.get("primary", {}).get("per_model", {}).get(m) if isinstance(g, dict) else None
            if not pm:
                continue
            x, y = np.array(pm["pEN"]), np.array(pm["pSL"])
            ax.scatter(x, y, s=14, color=COL[m], alpha=0.75, label=NAME[m])
            xx = np.linspace(0.02, 0.98, 100)
            ax.plot(xx, 1 / (1 + np.exp(-(pm["a"] + pm["b"] * np.log(xx / (1 - xx))))), color=COL[m], lw=1.3)
        ax.plot([0, 1], [0, 1], ls=":", color="grey", lw=0.8)
        ax.axvline(0.5, color="k", lw=0.6, ls="--")
        gp = g.get("primary") if isinstance(g, dict) else None
        if gp:
            title += f"\nG3 = {gp['G3']:.2f} [{gp['CI95'][0]:.2f}, {gp['CI95'][1]:.2f}]"
        ax.set_title(title, fontsize=8.5)
        ax.set_xlabel("EN-BT refusal rate")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
    axes[0].set_ylabel("SL-MT refusal rate")
    axes[0].legend(fontsize=7, loc="upper left")
    save(fig, "fig1_transfer_curves")
    # (2) forest
    items = []
    for key in ("B", "B_plus_F5", "A1", "A2"):
        g = A["G3"].get(key, {})
        if not isinstance(g, dict):
            continue
        for rk, lab in (("primary", ""), ("partial_as_refusal", " PARTIAL=ref"), ("lexicon", " lexicon")):
            if rk in g and isinstance(g[rk], dict) and "G3" in g[rk]:
                items.append((f"{key}{lab}", g[rk]["G3"], g[rk]["CI95"]))
    items += [("iter-1 trials (lexicon)", -1.86, [-2.87, -1.13]), ("iter-1 lambda curve", -0.99, [np.nan, np.nan])]
    fig, ax = plt.subplots(figsize=(6, 0.35 * len(items) + 1.2))
    m = A["m_C3"]
    ax.axvspan(-m, m, color="#e8f5e9")
    ax.axvline(0, color="k", lw=0.6)
    for i, (lab, g3, ci) in enumerate(items[::-1]):
        ax.errorbar(g3, i, xerr=None if np.isnan(ci[0]) else [[g3 - ci[0]], [ci[1] - g3]], fmt="o",
                    color="#555" if "iter-1" in lab else "#1b4f9c", capsize=3)
    ax.set_yticks(range(len(items)))
    ax.set_yticklabels([x[0] for x in items[::-1]], fontsize=8)
    ax.set_xlabel("G3 = SL log-odds(GaMS) - SL log-odds(Gemma) at EN refusal 50%  (band = +/- m = 0.675)")
    save(fig, "fig2_g3_forest")
    # (3) survival shallow vs deep along lambda
    d = A.get("depth", {}).get("A1")
    if d:
        k0 = {(r["model"], r["arm"], r["item_id"]): r.get(ro) for r in rows if r["curve"] == "orig"}
        kp = {(r["model"], r["arm"], r["item_id"]): r.get(ro) for r in rows if r["curve"] == "prefill"}
        lam = defaultdict(dict)
        for r in rows:
            if r["curve"] == "lambda" and r.get(ro) is not None:
                lam[(r["model"], r["arm"], r["item_id"])][r["step"]] = r[ro]
        steps = sorted({s for v in lam.values() for s in v})
        fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), sharey=True)
        for ax, m in zip(axes, MODEL_ORDER):
            for arm, ls in (("en_bt", "-"), ("sl_mt", "--")):
                for sh, c in ((1, "#c92a2a"), (0, "#2b8a3e")):
                    keys = [k for k in k0 if k[0] == m and k[1] == arm and k0[k] == 1 and k in kp
                            and kp[k] is not None and int(kp[k] == 0) == sh]
                    if not keys:
                        continue
                    surv = []
                    for s in steps:
                        alive = [k for k in keys if all(lam[k].get(t, 0) == 1 for t in steps if t <= s)]
                        surv.append(len(alive) / len(keys))
                    ax.plot([0] + steps, [1] + surv, ls=ls, color=c,
                            label=f"{'SL' if arm == 'sl_mt' else 'EN'} {'shallow' if sh else 'deep'} (n={len(keys)})")
            ax.set_title(NAME[m])
            ax.set_xlabel("lambda")
            ax.legend(fontsize=6.5)
        axes[0].set_ylabel("fraction still refusing at all steps <= lambda")
        save(fig, "fig3_depth_survival")
        # (4) flip rates
        fig, ax = plt.subplots(figsize=(5, 3.2))
        labs, vals, errs = [], [], []
        for m in MODEL_ORDER:
            for arm in ("en_bt", "sl_mt"):
                c = d["cells"].get(f"{m}|{arm}")
                if c:
                    labs.append(f"{NAME[m].split('-')[0]}\n{'EN-BT' if arm == 'en_bt' else 'SL-MT'}")
                    vals.append(c["flip_rate"])
                    errs.append([c["flip_rate"] - c["flip_CI95"][0], c["flip_CI95"][1] - c["flip_rate"]])
        ax.bar(range(len(vals)), vals, yerr=np.array(errs).T, color=["#2a6fdb", "#74a9f0", "#d9480f", "#f5a06b"][:len(vals)],
               capsize=3)
        ax.set_xticks(range(len(vals)))
        ax.set_xticklabels(labs, fontsize=8)
        ax.set_ylabel("flip rate after compliant prefill\n(among items refused at k=0)")
        save(fig, "fig4_prefill_flip")
    # (5) C5a
    c = A.get("C5a", {})
    ok = [m for m in MODEL_ORDER if isinstance(c.get(m), dict) and "excess_ratio" in c[m]]
    if ok:
        fig, ax = plt.subplots(figsize=(4.5, 2.6))
        for i, m in enumerate(ok):
            v = c[m]
            ax.errorbar(v["excess_ratio"], i, xerr=[[v["excess_ratio"] - v["CI95"][0]], [v["CI95"][1] - v["excess_ratio"]]],
                        fmt="o", color=COL[m], capsize=3)
            ax.plot(v["iter1_energy_matched_reference"], i, "x", color="grey")
        ax.axvline(1, color="k", lw=0.7)
        ax.set_yticks(range(len(ok)))
        ax.set_yticklabels([NAME[m] for m in ok])
        ax.set_xlabel("excess SL/EN KL ratio vs centred-variance random edit\n(x = iter-1 energy-matched)")
        save(fig, "fig5_c5a")
    print("figures written to", FIG)


if __name__ == "__main__":
    main()
