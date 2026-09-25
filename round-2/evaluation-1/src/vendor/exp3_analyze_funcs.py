"""VENDORED VERBATIM from iter-1 exp3 (art_3GJzU9GuyW5r) src/analyze.py: hl, boot_idx, level, signature, summarize,
full_stats, verdict (the pre-registered ALT-3 persona-gate statistics). Constants copied from exp3 common/analyze."""
from __future__ import annotations

import numpy as np

SEED = 20260923
NB = 2000
CONDS = ["C0", "C1", "C2", "C3", "C4", "C5"]
MODS = ["gams", "gemma"]


def hl(k: np.ndarray, n: int) -> np.ndarray:
    p = (k + 0.5) / (n + 1.0)
    return np.log(p / (1 - p))


def boot_idx(n: int) -> np.ndarray:
    rng = np.random.default_rng(SEED)
    return rng.integers(0, n, size=(NB, n))


def level(M: dict, key, idx: np.ndarray | None, cont: bool) -> np.ndarray | float:
    x = M[key]
    if idx is None:
        return float(x.mean()) if cont else float(hl(x.sum(), len(x)))
    xs = x[idx]
    return xs.mean(1) if cont else hl(xs.sum(1), x.shape[0])


def signature(M: dict, idx, cont: bool, sl: str = "sl") -> dict:
    """Returns dict of stats (scalars if idx None else arrays over bootstrap)."""
    L = lambda m, c, g: level(M, (m, c, g), idx, cont)
    gap = {(m, c): L(m, c, sl) - L(m, c, "en") for m in MODS for c in CONDS if (m, c, sl) in M and (m, c, "en") in M}
    shrink = {(m, c): gap[(m, "C0")] - gap[(m, c)] for (m, c) in gap}
    out = {"gap": gap, "shrink": shrink}
    G = {}
    for m in MODS:
        for ctrl in ["C2", "C3", "C4", "C5"]:
            if (m, "C1") in shrink and (m, ctrl) in shrink:
                G[(m, ctrl)] = shrink[(m, "C1")] - shrink[(m, ctrl)]
    TD = {ctrl: G[("gams", ctrl)] - G[("gemma", ctrl)] for ctrl in ["C2", "C3", "C4", "C5"] if ("gams", ctrl) in G and ("gemma", ctrl) in G}
    out.update({"G": G, "TD": TD})
    if "C2" in TD and "C3" in TD:
        out["TDstar"] = np.minimum(TD["C2"], TD["C3"])
    if ("gams", "C0") in gap and ("gemma", "C0") in gap:
        out["DiD_ref"] = gap[("gams", "C0")] - gap[("gemma", "C0")]
    return out


def summarize(point, boot) -> dict:
    b = np.asarray(boot)
    return {"point": float(point), "ci95": [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))],
            "se_boot": float(b.std(ddof=1))}


def full_stats(M: dict, cont: bool, sl: str = "sl", idx_all=None) -> dict:
    n = 400
    idx = boot_idx(n) if idx_all is None else idx_all
    P = signature(M, None, cont, sl)
    B = signature(M, idx, cont, sl)
    res = {"gap": {f"{m}|{c}": summarize(P["gap"][(m, c)], B["gap"][(m, c)]) for (m, c) in P["gap"]},
           "shrink": {f"{m}|{c}": summarize(P["shrink"][(m, c)], B["shrink"][(m, c)]) for (m, c) in P["shrink"]},
           "G": {f"{m}|{c}": summarize(P["G"][k], B["G"][k]) for k in P["G"] for (m, c) in [k]},
           "TD": {c: summarize(P["TD"][c], B["TD"][c]) for c in P["TD"]}}
    if "TDstar" in P:
        res["TDstar"] = summarize(P["TDstar"], B["TDstar"])
    if "DiD_ref" in P:
        res["DiD_ref_C0"] = summarize(P["DiD_ref"], B["DiD_ref"])
    res["levels"] = {f"{m}|{c}|{g}": level(M, (m, c, g), None, cont) for (m, c, g) in M if g in ("en", sl)}
    if not cont:
        res["rates"] = {f"{m}|{c}|{g}": float(M[(m, c, g)].mean()) for (m, c, g) in M}
    return res


def verdict(st: dict, m_thr: float, mc_pass: bool, catastrophic_c1: bool) -> dict:
    if "TDstar" not in st:
        return {"label": "UNTESTABLE", "reason": "missing conditions"}
    td = st["TDstar"]
    g2, g3 = st["G"].get("gams|C2"), st["G"].get("gams|C3")
    se = td["se_boot"]
    z = (td["point"] - m_thr) / se if se > 0 else float("nan")
    z_abs = (abs(td["point"]) - m_thr) / se if se > 0 else float("nan")
    conds = {"mc_pass_gams": mc_pass, "G_gams_C2_gt_m": g2["point"] > m_thr, "G_gams_C2_ci_lo_gt0": g2["ci95"][0] > 0,
             "G_gams_C3_gt_m": g3["point"] > m_thr, "G_gams_C3_ci_lo_gt0": g3["ci95"][0] > 0,
             "TDstar_gt0": td["point"] > 0, "TDstar_ci_lo_gt0": td["ci95"][0] > 0, "C1_not_catastrophic": not catastrophic_c1,
             "z_c_gt0": bool(z > 0)}
    survives = all(conds.values())
    mde = 2.8 * se
    if not mc_pass:
        label = "UNTESTABLE"
    elif survives:
        label = "SURVIVES"
    elif mde > 2 * m_thr:
        label = "INCONCLUSIVE"
    else:
        label = "FAILS"
    direction = ("persona ablation shrinks GaMS's SL surplus more than controls/Gemma" if td["point"] > 0 else
                 "NEGATIVE: persona ablation widens GaMS's SL surplus relative to controls/Gemma (persona suppresses SL refusal)")
    return {"label": label, "survives": survives, "TDstar": td, "threshold_m": m_thr, "z_c": z, "z_c_abs_version": z_abs,
            "MDE": mde, "MDE_gt_2m": mde > 2 * m_thr, "conditions": conds, "direction_note": direction}
