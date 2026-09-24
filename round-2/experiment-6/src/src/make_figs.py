#!/usr/bin/env python3
"""Figures from results/analysis.json only (numbers cannot disagree with the analysis)."""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from common import FIGS, RESULTS  # noqa: E402

plt.rcParams.update({"font.size": 9, "pdf.fonttype": 42, "axes.spines.top": False, "axes.spines.right": False})
A = json.loads((RESULTS / "analysis.json").read_text())
MN = {"gemma_it": "Gemma-3-12B-IT", "gams3_it": "GaMS3-12B-Instruct"}
COL = {"sl_mt": "#c0392b", "en_bt": "#2471a3", "en_orig": "#7f8c8d"}
ARMN = {"sl_mt": "SL-MT", "en_bt": "EN-BT", "en_orig": "EN-orig"}
models = A["models_present"]


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIGS / f"{name}.png", dpi=180)
    fig.savefig(FIGS / f"{name}.pdf")
    plt.close(fig)


# 1 depth curves (tokens and chars)
fig, axes = plt.subplots(2, len(models), figsize=(4.2 * len(models), 6), squeeze=False)
for c, m in enumerate(models):
    cur = A["primary"][m]["curves_D300"]
    for r, xkey in enumerate(("k_tokens", "k_chars")):
        ax = axes[r, c]
        for arm, pts in cur.items():
            pts = [p for p in pts if p["cond"] != "Pfull"]
            x = [p[xkey] for p in pts]; y = [p["rate"] for p in pts]
            lo = [max(0.0, p["rate"] - p["wilson"][0]) for p in pts]; hi = [max(0.0, p["wilson"][1] - p["rate"]) for p in pts]
            ax.errorbar(x, y, yerr=[lo, hi], marker="o", ms=4, capsize=2, color=COL[arm], label=ARMN[arm])
            full = [p for p in cur[arm] if p["cond"] == "Pfull"]
            if full:
                ax.scatter([full[0][xkey]], [full[0]["rate"]], marker="*", s=80, color=COL[arm], zorder=5)
        ax.set_xlabel("prefix length (tokens)" if xkey == "k_tokens" else "prefix length (characters)")
        ax.set_ylabel("judged flip rate | J")
        ax.set_title(f"{MN[m]}  (★ = meaning-matched full opener)", fontsize=8)
        ax.legend(fontsize=7)
save(fig, "fig1_depth_curves")

# 2 compliant vs neutral
fig, axes = plt.subplots(1, len(models), figsize=(4.2 * len(models), 3.2), squeeze=False)
for c, m in enumerate(models):
    ax = axes[0, c]
    P = A["primary"][m]
    vals = [("P5 SL", P["DG"]["a"]["rate"], "sl_mt"), ("P5 EN-BT", P["DG"]["b"]["rate"], "en_bt"),
            ("N5 SL", P["DGN"]["a"]["rate"], "sl_mt"), ("N5 EN-BT", P["DGN"]["b"]["rate"], "en_bt")]
    ax.bar(range(4), [v[1] or 0 for v in vals], color=[COL[v[2]] for v in vals], alpha=[1, 1, .5, .5][0])
    for i, v in enumerate(vals):
        ax.text(i, (v[1] or 0) + 0.005, f"{(v[1] or 0):.3f}", ha="center", fontsize=7)
    ax.set_xticks(range(4)); ax.set_xticklabels([v[0] for v in vals], fontsize=7)
    ax.set_ylabel("flip rate | J")
    fmt = lambda v: "n/a" if v is None else f"{v:.2f}"
    ax.set_title(f"{MN[m]}: DG={fmt(P['DG']['est'])}, DGN={fmt(P['DGN']['est'])}, DDG={fmt(P['DDG']['est'])}", fontsize=8)
save(fig, "fig2_compliant_vs_neutral")

# 3 cross-language 2x2
fig, axes = plt.subplots(1, len(models), figsize=(4.2 * len(models), 3.2), squeeze=False)
for c, m in enumerate(models):
    ax = axes[0, c]
    c2 = A["primary"][m].get("cross_2x2")
    if not c2:
        ax.set_title(f"{MN[m]}: 2x2 not available"); continue
    cells = c2["cells"]
    lab = ["prompt SL\nprefix SL", "prompt SL\nprefix EN", "prompt EN-BT\nprefix EN", "prompt EN-BT\nprefix SL"]
    ks = ["promptSL_prefixSL", "promptSL_prefixEN", "promptEN_prefixEN", "promptEN_prefixSL"]
    rates = [cells[k]["flips"] / cells[k]["n"] if cells[k]["n"] else 0 for k in ks]
    ax.bar(range(4), rates, color=["#c0392b", "#e59866", "#2471a3", "#85c1e9"])
    ax.set_xticks(range(4)); ax.set_xticklabels(lab, fontsize=6.5)
    ax.set_ylabel("flip rate | J (D300, k=5)")
    ax.set_title(f"{MN[m]}: prompt eff {c2['prompt_effect']['est']:.2f}, prefix eff {c2['prefix_effect']['est']:.2f}", fontsize=8)
save(fig, "fig3_cross_language_2x2")

# 4 retention decay per layer
fig, axes = plt.subplots(2, len(models), figsize=(4.2 * len(models), 6), squeeze=False)
for c, m in enumerate(models):
    dec = A["mechanism"][m]["decay"]; L = A["mechanism"][m]["layers"]
    for r, which in enumerate(("ret_ref_last", "ret_harm_last")):
        ax = axes[r, c]
        for key, ls in (("k0", "-"), ("P5", "--"), ("P20", ":")):
            for arm in ("sl_mt", "en_bt"):
                d = dec.get(f"{arm}|{key}")
                if d:
                    ax.plot(L, d[which], ls, color=COL[arm], label=f"{ARMN[arm]} {key}")
        ax.axvline(A["mechanism"][m]["lstar"], color="k", lw=0.5)
        ax.set_xlabel("layer"); ax.set_ylabel(which.replace("_", " ") + " (1 = refused-harmful anchor)")
        ax.set_title(MN[m], fontsize=8); ax.legend(fontsize=6)
save(fig, "fig4_retention_by_layer")

# 5 AUROC ref vs harm
fig, ax = plt.subplots(figsize=(5, 3))
xs, labs, i = [], [], 0
for m in models:
    for arm in ("sl_mt", "en_bt"):
        a = A["mechanism"][m]["auroc"].get(arm, {})
        if "auroc_ref" in a:
            ax.bar(i - 0.18, a["auroc_ref"], 0.35, color="#8e44ad", label="refusal proj" if i == 0 else None)
            ax.bar(i + 0.18, a["auroc_harm"], 0.35, color="#16a085", label="harm proj" if i == 0 else None)
        labs.append(f"{MN[m].split('-')[0]}\n{ARMN[arm]}"); xs.append(i); i += 1
ax.axhline(0.5, color="k", lw=0.5); ax.set_xticks(xs); ax.set_xticklabels(labs, fontsize=7)
ax.set_ylabel("AUROC (last-token projection -> flip at k=5)"); ax.legend(fontsize=7)
save(fig, "fig5_auroc_ref_vs_harm")

# 6 restoration dose-response
fig, axes = plt.subplots(1, len(models), figsize=(4.2 * len(models), 3.2), squeeze=False)
for c, m in enumerate(models):
    ax = axes[0, c]
    cz = A["causal"].get(m, {})
    for arm in ("sl_mt", "en_bt"):
        t = cz.get(arm, {}).get("table", {})
        own = sorted((float(k.split("|")[1]), v) for k, v in t.items() if k.startswith("own|") and v["restoration"] is not None)
        if own:
            ax.plot([a for a, _ in own], [v["restoration"] for _, v in own], "o-", color=COL[arm],
                    label=f"{ARMN[arm]} own (n={cz[arm]['n_flipped_at_a0']})")
        for k, v in t.items():
            d, a = k.split("|")
            if d != "own" and v["restoration"] is not None:
                ax.scatter([float(a)], [v["restoration"]], marker={"harm": "s", "rand1": "x", "rand2": "x", "rand1n": "^"}[d],
                           color=COL[arm], alpha=0.6)
    ax.set_xlabel("a (SD units of the direction)"); ax.set_ylabel("restored refusal among a=0 flips")
    ax.set_title(f"{MN[m]} (x random, ▲ norm-matched random, ■ harm dir)", fontsize=7); ax.legend(fontsize=7)
save(fig, "fig6_restoration")

# 7 collateral
fig, axes = plt.subplots(1, len(models), figsize=(4.2 * len(models), 3.2), squeeze=False)
for c, m in enumerate(models):
    ax = axes[0, c]
    co = A["collateral"].get(m, {})
    for lg, colr in (("en", "#2471a3"), ("sl", "#c0392b")):
        own = sorted((float(k.split("|")[2]), v) for k, v in co.items() if k.startswith(f"{lg}|own|") and v.get("harmless_refusal") is not None)
        if own:
            ax.plot([a for a, _ in own], [v["harmless_refusal"] for _, v in own], "o-", color=colr, label=f"harmless {lg.upper()} refusal")
            ax2 = ax.twinx() if lg == "en" else ax2
            ax2.plot([a for a, _ in own], [v["first_token_kl"] for _, v in own], "--", color=colr, alpha=0.5)
    ax.set_xlabel("a"); ax.set_ylabel("judged refusal on harmless (solid)")
    if own:
        ax2.set_ylabel("first-token KL (dashed)")
    ax.set_title(MN[m], fontsize=8); ax.legend(fontsize=7)
save(fig, "fig7_collateral")
# 8 label-free depth at L*
fig, axes = plt.subplots(1, len(models), figsize=(4.2 * len(models), 3.2), squeeze=False)
order = ["k0", "P3", "P5", "P10", "P20", "Pfull", "N5", "Nfull", "X5"]
for c, m in enumerate(models):
    ax = axes[0, c]
    lf = A["mechanism"][m].get("label_free_depth_lstar", {})
    conds = [k for k in order if k in lf]
    x = np.arange(len(conds))
    ax.plot(x, [lf[k]["ret_ref_last_SL"] for k in conds], "o-", color=COL["sl_mt"], label="refusal proj, SL-MT")
    ax.plot(x, [lf[k]["ret_ref_last_EN_BT"] for k in conds], "o-", color=COL["en_bt"], label="refusal proj, EN-BT")
    ax.plot(x, [lf[k]["ret_harm_last_SL"] for k in conds], "s--", color=COL["sl_mt"], alpha=0.5, label="harm proj, SL-MT")
    ax.plot(x, [lf[k]["ret_harm_last_EN_BT"] for k in conds], "s--", color=COL["en_bt"], alpha=0.5, label="harm proj, EN-BT")
    ax.set_xticks(x); ax.set_xticklabels(conds, fontsize=7)
    ax.set_ylabel(f"retention at L*={A['mechanism'][m]['lstar']} (last input token)")
    ax.set_title(MN[m] + " (all D300 items, label-free)", fontsize=8); ax.legend(fontsize=6)
save(fig, "fig8_label_free_depth")
# 9 judge validation: agreement of each instrument with the two references (this decides what counts as a result)
V = A.get("judge_validation", {})
if V.get("judges"):
    names = [n for n in ("gpt41", "gemini", "local") if n in V["judges"]]
    lbl = {"gpt41": "gpt-4.1\n(reference)", "gemini": "gemini-2.5-flash\n(pre-registered)", "local": "local Qwen3-14B\n(fallback)"}
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.2))
    ax = axes[0]
    x = np.arange(len(names))
    for off, (key, c, lab_) in enumerate(((("vs_gpt41_dev_sl"), "#c0392b", "vs gpt-4.1, DEV SL"),
                                          (("vs_gpt41_dev_en"), "#2471a3", "vs gpt-4.1, DEV EN"),
                                          (("vs_adjudication_all"), "#616a6b", "vs blind adjudication"))):
        v = [(V["judges"][n].get(key) or {}).get("kappa_R") for n in names]
        ax.bar(x + (off - 1) * 0.27, [0 if z is None else z for z in v], 0.26, color=c, label=lab_)
    ax.axhline(0.6, ls="--", c="k", lw=1)
    ax.text(len(names) - 0.5, 0.62, "acceptance gate", fontsize=6, ha="right")
    ax.set_xticks(x); ax.set_xticklabels([lbl[n] for n in names], fontsize=7)
    ax.set_ylabel("Cohen κ (binary REFUSE)"); ax.legend(fontsize=6); ax.set_title("No judge clears the gate", fontsize=8)
    ax = axes[1]
    for i, n in enumerate(names):
        v = V["judges"][n].get("vs_adjudication_all") or {}
        if not v:
            continue
        ax.bar(i - 0.17, v["refuse_rate_judge"], 0.32, color="#2471a3", label="judge" if i == 0 else None)
        ax.bar(i + 0.17, v["refuse_rate_adjudicator"], 0.32, color="#f39c12", label="blind adjudicator" if i == 0 else None)
    ax.set_xticks(x); ax.set_xticklabels([lbl[n] for n in names], fontsize=7)
    ax.set_ylabel("refusal rate on the adjudication sample")
    ax.set_title("gemini over-calls refusal on prefilled text", fontsize=8); ax.legend(fontsize=6)
    save(fig, "fig9_judge_validation")

# 10 judge sensitivity: the primary contrast under each instrument
JS = A.get("judge_sensitivity", {})
if JS:
    fig, ax = plt.subplots(figsize=(5.6, 3.2))
    ks = [k for k in JS if "DG" in JS[k]]
    for i, k in enumerate(ks):
        v = JS[k]["DG"]
        if v["est"] is None:
            continue
        lo, hi = v["ci95"]
        ax.errorbar(i, v["est"], yerr=[[v["est"] - lo], [hi - v["est"]]], fmt="o", color="#2471a3", capsize=3)
    ax.axhline(0, c="k", lw=1)
    ax.axhline(A["m"]["m"], ls="--", c="#c0392b", lw=1)
    ax.text(len(ks) - 0.5, A["m"]["m"] * 1.03, "m", fontsize=7, ha="right", color="#c0392b")
    ax.set_xticks(range(len(ks)))
    ax.set_xticklabels([k.replace("|", "\n") for k in ks], fontsize=6)
    ax.set_ylabel("DG = logit flip(SL-MT) − logit flip(EN-BT), k=5")
    ax.set_title("The measured language gap depends on the instrument", fontsize=8)
    save(fig, "fig10_judge_sensitivity")

AD = A.get("adjudicated_primary", {}).get("by_model", {})
if AD:
    ms = [m for m in AD if "risk_difference" in AD[m]]
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.2))
    ax = axes[0]
    w = 0.35
    for i, m in enumerate(ms):
        v = AD[m]
        ax.bar(i - w / 2, v["flip_SL_MT"]["p"], w, color=COL["sl_mt"], label="SL-MT" if i == 0 else None)
        ax.bar(i + w / 2, v["flip_EN_BT"]["p"], w, color=COL["en_bt"], label="EN-BT" if i == 0 else None)
    ax.set_xticks(range(len(ms))); ax.set_xticklabels([MN[m] for m in ms], fontsize=7)
    ax.set_ylabel("flip rate at k=5 (adjudicated, stratum-weighted)")
    ax.legend(fontsize=7); ax.set_title("Prefill compliance by language", fontsize=8)
    ax = axes[1]
    for i, m in enumerate(ms):
        v = AD[m]["risk_difference"]
        lo, hi = v["ci95"]
        ax.errorbar(i, v["est"], yerr=[[v["est"] - lo], [hi - v["est"]]], fmt="o", color="#2c3e50", capsize=4)
    ax.axhline(0, c="k", lw=1)
    ax.set_xticks(range(len(ms))); ax.set_xticklabels([MN[m] for m in ms], fontsize=7)
    ax.set_xlim(-0.6, len(ms) - 0.4)
    ax.set_ylabel("risk difference  p(SL-MT) − p(EN-BT)")
    ax.set_title("No language gap survives a reliable reading", fontsize=8)
    save(fig, "fig11_adjudicated_primary")

print("figures written")
