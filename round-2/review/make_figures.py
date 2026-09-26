"""Render the reconciled paper's data figures straight from the saved artifact results.

Every plotted number is read from an artifact's own results file; nothing is typed in by hand
except axis text. Run: python make_figures.py  -> figures/<id>.pdf + .png
"""
import collections
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools/aii-data-fig-gen/scripts"))
import matplotlib.pyplot as plt  # noqa: E402
from chart_geometry import assert_text_is_legible  # noqa: E402
from chart_style import (  # noqa: E402
    PALETTE, apply_house_style, assert_legends_clear_of_data, clear_legends_of_data,
    fit_legends, fit_tick_labels, fit_titles, literal, place_legend,
)

RUN = Path(__file__).resolve().parents[2]
EXP1 = RUN / "round-1/experiment-1/src/results/analysis_results.json"
GROUPS = RUN / "round-1/dataset-1/src"
EXP5 = RUN / "round-2/experiment-5/src/results"
EXP8 = RUN / "round-2/experiment-8/src/results"
EVAL1 = RUN / "round-2/evaluation-1/src/eval_out.json"
OUT = Path(__file__).parent / "figures"
OUT.mkdir(exist_ok=True)
BLUE, ORANGE, GREY = PALETTE[0], PALETTE[1], "#888888"

# Audited dose groups (dataset artifact frozen_groups.json; Table 1 of the paper).
LOW = ["S2", "S5", "S7", "S13"]
INT = ["S6", "S12"]


def finish(fig, name):
    fit_legends(fig)
    clear_legends_of_data(fig)
    fit_tick_labels(fig)
    fit_titles(fig)
    clear_legends_of_data(fig)
    assert_text_is_legible(fig)
    assert_legends_clear_of_data(fig)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"{name}.{ext}", dpi=200)
    plt.close(fig)
    print("wrote", name)


def ci_err(est, lo, hi):
    return np.array([[est - lo], [hi - est]])


def fig_forest_did():
    r = json.load(open(EXP1))["outcomes"]["R_judge"]
    cats = [f"S{i}" for i in range(1, 15)]
    order = LOW + INT + [c for c in cats if c not in LOW + INT]
    fig, ax = plt.subplots(figsize=(7, 5.2), layout="constrained")
    rows = order + ["Overall"]
    for y, c in enumerate(rows):
        e = r["overall"] if c == "Overall" else r["per_category"][c]
        lo, hi = e["ci95"]
        col = BLUE if c in LOW else (GREY if c in INT else ORANGE)
        if c == "Overall":
            col = "black"
        ax.errorbar(e["est"], y, xerr=ci_err(e["est"], lo, hi), fmt="D" if c == "Overall" else "o",
                    color=col, ecolor=col, capsize=3, markersize=6 if c == "Overall" else 5)
    ax.axvline(0, color="#999999", linestyle="--", linewidth=1)
    ax.set_yticks(range(len(rows)), labels=[literal(f"{c} (n={r['per_category'][c]['n']})") if c != "Overall"
                                            else literal(f"Overall (n={r['n_pairs']})") for c in rows])
    ax.invert_yaxis()
    ax.set_xlabel(literal("DiD in refusal log-odds, GaMS3 minus Gemma-IT (SL minus EN)"))
    ax.set_title(literal("Per-category refusal DiD, iteration-1 SCORE set (gemini judge)"))
    for lab, col in (("low-EN dose (audited)", BLUE), ("intermediate", GREY), ("high-EN dose (audited)", ORANGE)):
        ax.plot([], [], "o", color=col, label=literal(lab))
    fig.legend(loc="outside lower center", ncols=3, frameon=False)
    ax.grid(axis="y", visible=False)
    finish(fig, "fig_forest_did")


def fig_judge_dependence():
    a = json.load(open(EXP5 / "analysis_final.json"))
    d = json.load(open(EXP5 / "analysis_dev.json"))
    cal = json.load(open(EXP5 / "judge_calibrated_final.json"))
    ev = [x for x in json.load(open(EVAL1))["datasets"]]  # noqa: F841  (provenance only)
    sens = a["C2_refuseu_sensitivities"]
    jf = a["judge_family_robustness_gemini_subset"]

    def find(o, key):
        if isinstance(o, dict):
            if key in o and isinstance(o[key], dict) and "est" in o[key]:
                return o[key]
            for v in o.values():
                f = find(v, key)
                if f:
                    return f
        return None

    rows = [
        ("Iter-1 SCORE, gemini (2,137 pairs)", sens["pooled_with_iter1"]["iter1_DiD_overall"]),
        ("FINAL, Qwen3-14B (1,300)", a["C2_refuseu"]["DiD_overall"]),
        ("FINAL subset, gemini (607)", jf["C2_refuseu_R_gemini"]["DiD_overall"]),
        ("FINAL subset, Qwen3-14B (same 607)", jf["C2_refuseu_R_qwen3_same_pairs"]["DiD_overall"]),
        ("FINAL, Qwen3 calibrated to gemini", find(cal, "DiD_ref_natural")),
        ("FINAL, Qwen3, partial counted as refusal", sens["Rp_coding"]["DiD_overall"]),
        ("FINAL, frozen lexicon (diagnostic)", sens["lexicon_R_lex_diagnostic"]["DiD_overall"]),
        ("DEV, gemini (100)", find(d["C2_refuseu"], "DiD_overall")),
        ("FINAL item-matched MT, Qwen3 (1,296)", sens["item_matched_MT_ENBT"]["DiD_overall"]),
    ]
    fig, ax = plt.subplots(figsize=(7, 4.4), layout="constrained")
    for y, (lab, e) in enumerate(rows):
        lo, hi = e["ci95"]
        col = PALETTE[2] if "MT" in lab else (GREY if "lexicon" in lab or "partial" in lab else BLUE)
        ax.errorbar(e["est"], y, xerr=ci_err(e["est"], lo, hi), fmt="o", color=col, ecolor=col, capsize=3)
        print(f"  {lab}: {e['est']:.2f} [{lo:.2f}, {hi:.2f}]")
    ax.axvline(0, color="#999999", linestyle="--", linewidth=1)
    ax.set_yticks(range(len(rows)), labels=[literal(r[0]) for r in rows])
    ax.invert_yaxis()
    ax.set_xlabel(literal("Refusal DiD (log-odds)"))
    ax.set_title(literal("RefusEU refusal DiD depends on the readout"))
    ax.grid(axis="y", visible=False)
    finish(fig, "fig_judge_dependence")


def fig_hard_sdt():
    p = json.load(open(EXP5 / "analysis_final.json"))["C2_hard_sdt"]["primary_SLMT_vs_ENBT"]["cells"]
    cells = ["Gemma EN", "Gemma SL", "GaMS3 EN", "GaMS3 SL"]
    fig, axes = plt.subplots(1, 3, figsize=(7, 2.9), layout="constrained")
    for ax, key, title in zip(axes, ("dprime", "c", "F"),
                              ("(a) d′ (sensitivity)", "(b) criterion c", "(c) false-alarm rate (safe items)")):
        v = p[key]
        cols = [BLUE, BLUE, ORANGE, ORANGE]
        bars = ax.bar(range(4), v, color=cols)
        for b in (bars[1], bars[3]):
            b.set_hatch("///")
            b.set_edgecolor("white")
        ax.set_xticks(range(4), labels=[literal(c) for c in cells])
        ax.set_title(literal(title))
        ax.axhline(0, color="#555555", linewidth=0.8)
        print(f"  {key}: {[round(x, 3) for x in v]}")
    finish(fig, "fig_hard_sdt")


def hl(k, n):
    p = (k + 0.5) / (n + 1)
    return np.log(p / (1 - p))


def fit_glm(x, k, n):
    X = np.column_stack([np.ones_like(x), x])
    b = np.zeros(2)
    y = k / n
    for _ in range(80):
        e = X @ b
        pr = 1 / (1 + np.exp(-e))
        w = n * pr * (1 - pr) + 1e-9
        z = e + (y - pr) / np.maximum(pr * (1 - pr), 1e-9)
        b = np.linalg.solve(X.T @ (X * w[:, None]) + 1e-6 * np.eye(2), X.T @ (w * z))
    return b


def curve_points(rows, model, curve, readout):
    d = collections.defaultdict(dict)
    for r in rows:
        if r["model"] == model and r["curve"] == curve and r.get(readout) is not None:
            d[(r["step"], r["item_id"])][r["arm"]] = r[readout]
    st = collections.defaultdict(lambda: [0, 0, 0])
    for (s, _), v in d.items():
        if "en_bt" in v and "sl_mt" in v:
            t = st[s]
            t[0] += v["en_bt"]
            t[1] += v["sl_mt"]
            t[2] += 1
    S = sorted(st)
    kE, kS, n = (np.array([st[s][i] for s in S], float) for i in range(3))
    return kE, kS, n


def fig_transfer_retest():
    rows = [json.loads(line) for line in open(EXP8 / "items_final.jsonl")]
    rows = [r for r in rows if r["arm"] in ("en_bt", "sl_mt") and r["curve"] in ("trial", "lambda")]
    fig, axes = plt.subplots(1, 2, figsize=(7, 3.6), layout="constrained")
    grid = np.linspace(-4, 4, 200)
    pgrid = 1 / (1 + np.exp(-grid))
    for ax, curve, title in zip(axes, ("trial", "lambda"),
                                ("(a) 29 paired fresh Heretic trials (curve B)", "(b) iter-1 LoRA scaled by λ (curve A1)")):
        a_vals = {}
        for model, col, mk, name in (("gemma_it", BLUE, "o", "Gemma-IT"), ("gams3_it", ORANGE, "^", "GaMS3")):
            kE, kS, n = curve_points(rows, model, curve, "R_lex")
            a, b = fit_glm(hl(kE, n), kS, n)
            a_vals[model] = a
            ax.scatter((kE + 0.5) / (n + 1), (kS + 0.5) / (n + 1), color=col, marker=mk, s=22, alpha=0.8,
                       label=literal(f"{name}, lexicon") if curve == "trial" else None)
            ax.plot(pgrid, 1 / (1 + np.exp(-(a + b * grid))), color=col, linewidth=1.5)
        kE, kS, n = curve_points(rows, "gemma_it", curve, "R_gemini")
        ag, bg = fit_glm(hl(kE, n), kS, n)
        ax.scatter((kE + 0.5) / (n + 1), (kS + 0.5) / (n + 1), facecolors="white", edgecolors=BLUE, marker="s",
                   s=18, linewidths=1.0, label=literal("Gemma-IT, gemini (dotted)") if curve == "trial" else None)
        ax.plot(pgrid, 1 / (1 + np.exp(-(ag + bg * grid))), color=BLUE, linewidth=1.2, linestyle=":")
        ax.plot([0, 1], [0, 1], color="#bbbbbb", linestyle="--", linewidth=0.8)
        ax.axvline(0.5, color="#cccccc", linewidth=0.8)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1.02)
        ax.set_xlabel(literal("English (EN-BT) refusal rate"))
        ax.set_ylabel(literal("Slovene (SL-MT) refusal rate"))
        ax.set_title(literal(title))
        g3 = a_vals["gams3_it"] - a_vals["gemma_it"]
        print(f"  {curve}: a_gemma={a_vals['gemma_it']:.2f} a_gams={a_vals['gams3_it']:.2f} G3_lex={g3:.2f} "
              f"a_gemma_gemini={ag:.2f}")
    fig.legend(loc="outside lower center", ncols=3, frameon=False)
    finish(fig, "fig_transfer_retest")


if __name__ == "__main__":
    apply_house_style()
    fig_forest_did()
    fig_judge_dependence()
    fig_hard_sdt()
    fig_transfer_retest()
