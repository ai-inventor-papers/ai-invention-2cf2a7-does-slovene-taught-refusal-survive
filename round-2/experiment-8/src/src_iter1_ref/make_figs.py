#!/usr/bin/env python3
"""Figures from saved results only (results/figs/): transfer curves, Pareto fronts, prefill depth, KL-ratio forest."""
from __future__ import annotations

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

import os  # noqa: E402
from pathlib import Path  # noqa: E402

from common import RESULTS, read_jsonl  # noqa: E402

RESULTS = Path(os.environ.get("AII_RESULTS", str(RESULTS)))  # override only for tests

FIG = RESULTS / "figs"
FIG.mkdir(parents=True, exist_ok=True)
MODELS = {"gemma_it": ("Gemma-3-12B-IT", "#1f77b4"), "gams3_it": ("GaMS3-12B-Instruct", "#d62728")}
A = json.loads((RESULTS / "analysis.json").read_text())


def hl(k, n):
    p = (k + 0.5) / (n + 1.0)
    return np.log(p / (1 - p))


PRIMARY = A.get("primary_readout", "lexicon")
JM = {(r["model"], r["cell"], r["lang"], r["pair_id"], r["trial"]): r["judge"]
      for r in read_jsonl(RESULTS / "judge.jsonl") if r.get("judge")}
SENS = A.get("sensitivity_readouts", {})


def trial_rates(m):
    rows = [r for r in read_jsonl(RESULTS / m / "trial_probe.jsonl") if r["tag"] == "trial" and "R" in r]
    if PRIMARY == "judge":
        rows = [dict(r, R=int(JM[(m, "trialpool", r["lang"], r["pair_id"], r["trial"])] == "refuse"))
                for r in rows if (m, "trialpool", r["lang"], r["pair_id"], r["trial"]) in JM]
    by = {}
    for r in rows:
        by.setdefault(r["trial"], {"en": [], "sl": []})[r["lang"]].append(r["R"])
    t = sorted(by)
    x = np.array([hl(sum(by[i]["en"]), len(by[i]["en"])) for i in t])
    y = np.array([hl(sum(by[i]["sl"]), len(by[i]["sl"])) for i in t])
    return t, x, y


# 1. transfer curves
fig, ax = plt.subplots(figsize=(6, 5))
for m, (lab, c) in MODELS.items():
    if not (RESULTS / m / "trial_probe.jsonl").exists():
        continue
    t, x, y = trial_rates(m)
    ax.scatter(x, y, s=14, color=c, alpha=0.55, label=f"{lab}: Heretic trials (n={len(t)})")
    c3 = A.get("C3", {}).get("all_trials", {}).get("all_pairs", {})
    if c3:
        a, b = c3["a"][m], c3["b_slope"][m]["est"]
        xs = np.linspace(x.min() - 0.3, x.max() + 0.3, 50)
        ax.plot(xs, a + b * xs, color=c, lw=1.5)
    lam = A.get("C3", {}).get("lambda_curve", {}).get("points", {}).get(m)
    if lam:
        ax.plot(lam["x_EN_logodds"], lam["y_SL_logodds"], "--o", color=c, ms=4, lw=1, alpha=0.9, label=f"{lab}: λ-scaled pick")
ax.axvline(0, color="grey", lw=0.8, ls=":")
ax.plot([-4, 4], [-4, 4], color="k", lw=0.6, ls=":", alpha=0.5)
ax.set_xlabel(f"EN refusal, Hautus log-odds (TRIAL-PROBE, {PRIMARY} readout)")
ax.set_ylabel("SL refusal, Hautus log-odds")
ax.set_title("C3: Slovene refusal vs English refusal across edits")
ax.legend(fontsize=7)
fig.tight_layout()
fig.savefig(FIG / "c3_transfer_curves.png", dpi=150)
fig.savefig(FIG / "c3_transfer_curves.pdf")
plt.close(fig)

# 2. Pareto fronts
fig, ax = plt.subplots(figsize=(6, 4.5))
for m, (lab, c) in MODELS.items():
    p = RESULTS / m / "trials.json"
    if not p.exists():
        continue
    tr = json.loads(p.read_text())
    v = np.array([t["values"] for t in tr])
    ax.scatter(v[:, 1], v[:, 0] * 100, s=12, color=c, alpha=0.5, label=lab)
    o = np.argsort(v[:, 1])
    best, fx, fy = 2.0, [], []
    for i in o:
        if v[i, 0] < best:
            best = v[i, 0]
            fx.append(v[i, 1])
            fy.append(v[i, 0] * 100)
    ax.step(fx, fy, where="post", color=c, lw=1.5)
ax.set_xscale("log")
ax.set_xlabel("first-token KL on harmless_alpaca test[:100] (Heretic objective)")
ax.set_ylabel("Heretic keyword refusals / 100 (EN objective)")
ax.set_title("Heretic trials and Pareto fronts (NF4, reduced-trial)")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(FIG / "pareto_fronts.png", dpi=150)
fig.savefig(FIG / "pareto_fronts.pdf")
plt.close(fig)

# 3. prefill depth
depth = A.get("ALT4", {}).get("prefill_depth_curve", {})
if depth:
    fig, ax = plt.subplots(figsize=(5.5, 4))
    for m, (lab, c) in MODELS.items():
        for lang, ls in (("en", "-"), ("sl", "--")):
            d = depth.get(m, {}).get(lang, {})
            ks = sorted(int(k) for k in d if d[k] is not None)
            if ks:
                ax.plot([0] + ks, [0] + [d[str(k)] if str(k) in d else d[k] for k in ks], ls, marker="o", color=c,
                        label=f"{lab} {lang.upper()}")
    ax.set_xlabel("compliant-prefix tokens prefilled (k)")
    ax.set_ylabel("flip rate (refusal -> non-refusal)")
    ax.set_title("ALT-4: prefill flip depth curve (original models)")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(FIG / "prefill_depth.png", dpi=150)
    fig.savefig(FIG / "prefill_depth.pdf")
    plt.close(fig)

# 4. KL-ratio forest
c5 = A.get("C5a", {})
rows = []
for m, (lab, c) in MODELS.items():
    for v in ("norm_matched", "en_kl_matched"):
        e = c5.get(m, {}).get(v)
        if e:
            rows.append((f"{lab}\n{v}", e["excess"]["est"], e["excess"]["ci95"], c))
if rows:
    fig, ax = plt.subplots(figsize=(6, 1 + 0.6 * len(rows)))
    for i, (lab, est, ci, c) in enumerate(rows):
        ax.errorbar(est, i, xerr=[[est - ci[0]], [ci[1] - est]], fmt="o", color=c, capsize=3)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows], fontsize=7)
    ax.axvline(1, color="k", ls=":")
    ax.set_xscale("log")
    ax.set_xlabel("excess SL/EN KL ratio (Heretic pick / random edit), 95% CI")
    ax.set_title("C5a: Slovene off-target leakage vs random-direction edits")
    fig.tight_layout()
    fig.savefig(FIG / "c5a_kl_ratio_forest.png", dpi=150)
    fig.savefig(FIG / "c5a_kl_ratio_forest.pdf")
    plt.close(fig)
# 5. readout comparison on the trial curve (lexicon vs judge v2 vs judge v1)
rows = []
for m, (lab, c) in MODELS.items():
    if not (RESULTS / m / "trial_probe.jsonl").exists():
        continue
    tr = [r for r in read_jsonl(RESULTS / m / "trial_probe.jsonl") if r["tag"] == "trial" and "R" in r]
    for lang in ("en", "sl"):
        x = [r for r in tr if r["lang"] == lang]
        if not x:
            continue
        lexr = np.mean([r["R"] for r in x])
        jr = {}
        for v, fn in (("judge_v2", "judge.jsonl"), ("judge_v1", "judge_v1.jsonl")):
            jm = {(r["cell"], r["lang"], r["pair_id"], r["trial"]): r["judge"]
                  for r in read_jsonl(RESULTS / fn) if r.get("judge") and r["model"] == m}
            hit = [int(jm[("trialpool", r["lang"], r["pair_id"], r["trial"])] == "refuse") for r in x
                   if ("trialpool", r["lang"], r["pair_id"], r["trial"]) in jm]
            jr[v] = np.mean(hit) if hit else np.nan
        rows.append((f"{lab}\n{lang.upper()}", lexr, jr["judge_v2"], jr["judge_v1"], c))
if rows:
    fig, ax = plt.subplots(figsize=(6, 4))
    xs = np.arange(len(rows))
    ax.bar(xs - 0.25, [r[1] for r in rows], 0.25, label="lexicon (pre-registered)", color="#4c72b0")
    ax.bar(xs, [r[2] for r in rows], 0.25, label="LLM judge v2 (truncation-aware)", color="#dd8452")
    ax.bar(xs + 0.25, [r[3] for r in rows], 0.25, label="LLM judge v1 (plan prompt)", color="#937860")
    ax.set_xticks(xs)
    ax.set_xticklabels([r[0] for r in rows], fontsize=7)
    ax.set_ylabel("mean refusal rate over Heretic trials")
    ax.set_title("Readouts disagree on abliterated 40-token continuations")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(FIG / "readout_comparison.png", dpi=150)
    fig.savefig(FIG / "readout_comparison.pdf")
    plt.close(fig)

print("figs:", sorted(p.name for p in FIG.glob("*.png")))
