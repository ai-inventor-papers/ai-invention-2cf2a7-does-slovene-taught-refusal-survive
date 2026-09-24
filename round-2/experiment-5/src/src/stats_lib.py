#!/usr/bin/env python3
"""Pure statistics for the confirmation run (no I/O). Used by analysis.py, addendum.py and unit_tests.py.
audit.py re-implements the point estimates independently (plain python) and does NOT import this module.

Cell convention: models ("gemma_it","gams3_it") x languages ("en","sl") -> column index 0..3:
  0=(gemma,EN) 1=(gemma,SL) 2=(gams,EN) 3=(gams,SL).
DiD = [GaMS(L_SL - L_EN)] - [Gemma(L_SL - L_EN)] with L(k,n) = logit((k+.5)/(n+1)); positive = GaMS SL SURPLUS.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy import stats as sst


# ------------------------------------------------------------------ basics
def Lh(k, n):
    k = np.asarray(k, dtype=float)
    n = np.asarray(n, dtype=float)
    p = (k + 0.5) / (n + 1.0)
    return np.log(p / (1 - p))


def zh(k, n):
    k = np.asarray(k, dtype=float)
    n = np.asarray(n, dtype=float)
    return sst.norm.ppf((k + 0.5) / (n + 1.0))


def did4(L: np.ndarray) -> np.ndarray:
    """L (..., 4) -> DiD."""
    return (L[..., 3] - L[..., 2]) - (L[..., 1] - L[..., 0])


def m_from_p0(p0: float, step: float = 0.05) -> float:
    p1 = p0 - step * np.sign(p0 - 0.5) if p0 != 0.5 else p0 - step
    lg = lambda p: math.log(p / (1 - p))  # noqa: E731
    c = lambda p: min(max(p, 1e-6), 1 - 1e-6)  # noqa: E731
    return abs(lg(c(p0)) - lg(c(p1)))


def m_dprime(H0: float, F0: float, step: float = 0.05) -> float:
    z = sst.norm.ppf
    c = lambda p: min(max(p, 1e-4), 1 - 1e-4)  # noqa: E731
    return float(min(abs(z(c(H0)) - z(c(H0 - step))), abs(z(c(F0 + step)) - z(c(F0)))))


def sdt(H: float, F: float) -> tuple[float, float]:
    zH, zF = sst.norm.ppf(H), sst.norm.ppf(F)
    return float(zH - zF), float(-(zH + zF) / 2)


def pct_ci(a: np.ndarray, level: float = 0.95) -> list[float]:
    a = np.asarray(a, dtype=float)
    a = a[np.isfinite(a)]
    q = (1 - level) / 2
    return [float(np.percentile(a, 100 * q)), float(np.percentile(a, 100 * (1 - q)))]


def bca_ci(theta: float, boot: np.ndarray, jack: np.ndarray, level: float = 0.95) -> list[float]:
    boot = boot[np.isfinite(boot)]
    z0 = sst.norm.ppf(np.clip((boot < theta).mean(), 1e-6, 1 - 1e-6))
    jm = jack.mean()
    num = ((jm - jack) ** 3).sum()
    den = 6 * (((jm - jack) ** 2).sum() ** 1.5)
    a = num / den if den > 0 else 0.0
    out = []
    for q in ((1 - level) / 2, 1 - (1 - level) / 2):
        zq = sst.norm.ppf(q)
        adj = sst.norm.cdf(z0 + (z0 + zq) / (1 - a * (z0 + zq)))
        out.append(float(np.percentile(boot, 100 * adj)))
    return out


def wilson(k: int, n: int, z: float = 1.96) -> list[float]:
    if n == 0:
        return [float("nan"), float("nan")]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [max(0.0, c - h), min(1.0, c + h)]


def cohen_kappa(a, b) -> float | None:
    a, b = list(a), list(b)
    if not a:
        return None
    labs = sorted(set(a) | set(b))
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(l) / n) * (b.count(l) / n) for l in labs)
    return 1.0 if pe >= 1 else float((po - pe) / (1 - pe))


def mcnemar(x: np.ndarray, y: np.ndarray) -> dict:
    """Exact McNemar on paired binaries."""
    x, y = np.asarray(x, bool), np.asarray(y, bool)
    b = int((x & ~y).sum())
    c = int((~x & y).sum())
    p = float(sst.binomtest(b, b + c, 0.5).pvalue) if b + c > 0 else 1.0
    return {"x_only": b, "y_only": c, "n": int(len(x)), "p_exact": p, "rate_x": float(x.mean()), "rate_y": float(y.mean())}


def summarize(theta: float, boot: np.ndarray, jack: np.ndarray | None = None) -> dict[str, Any]:
    out = {"est": float(theta), "se": float(np.nanstd(boot, ddof=1)), "ci90": pct_ci(boot, 0.90),
           "ci95": pct_ci(boot, 0.95)}
    if jack is not None:
        try:
            out["bca95"] = bca_ci(theta, boot, jack, 0.95)
            out["bca90"] = bca_ci(theta, boot, jack, 0.90)
        except (ValueError, IndexError, FloatingPointError):
            out["bca95"] = None
    return out


# ------------------------------------------------------------------ stratified index draws
def strat_draws(strata: np.ndarray, B: int, rng: np.random.Generator) -> np.ndarray:
    """(B, N) index matrix; resample with replacement within each stratum (sizes preserved)."""
    strata = np.asarray(strata)
    N = len(strata)
    idx = np.empty((B, N), dtype=np.int32)
    col = 0
    for s in sorted(set(strata.tolist()), key=str):
        pos = np.where(strata == s)[0]
        idx[:, col:col + len(pos)] = pos[rng.integers(0, len(pos), size=(B, len(pos)))]
        col += len(pos)
    return idx


# ------------------------------------------------------------------ pair-level DiD with per-language groups
def did_counts(Y: np.ndarray, gEN: np.ndarray, gSL: np.ndarray, sel_group: str | None) -> float:
    """Y (N,4) binary; gEN/gSL group of the EN/SL item per pair. Group-specific DiD uses, for EN cells, the pairs whose
    EN item is in the group and, for SL cells, pairs whose SL item is in the group."""
    if sel_group is None:
        mE = np.ones(len(Y), bool)
        mS = mE
    else:
        mE, mS = gEN == sel_group, gSL == sel_group
    k = np.array([Y[mE, 0].sum(), Y[mS, 1].sum(), Y[mE, 2].sum(), Y[mS, 3].sum()], dtype=float)
    n = np.array([mE.sum(), mS.sum(), mE.sum(), mS.sum()], dtype=float)
    return float(did4(Lh(k, n)))


def did_boot(Y: np.ndarray, gEN: np.ndarray, gSL: np.ndarray, sel_group: str | None, idx: np.ndarray) -> np.ndarray:
    """Vectorised bootstrap of did_counts over index matrix idx (B,N)."""
    Yb = Y[idx]  # (B,N,4)
    if sel_group is None:
        mE = np.ones(idx.shape, bool)
        mS = mE
    else:
        mE, mS = (gEN == sel_group)[idx], (gSL == sel_group)[idx]
    k = np.stack([(Yb[..., 0] * mE).sum(1), (Yb[..., 1] * mS).sum(1), (Yb[..., 2] * mE).sum(1),
                  (Yb[..., 3] * mS).sum(1)], -1).astype(float)
    n = np.stack([mE.sum(1), mS.sum(1), mE.sum(1), mS.sum(1)], -1).astype(float)
    return did4(Lh(k, n))


def did_jack(Y: np.ndarray, gEN: np.ndarray, gSL: np.ndarray, sel_group: str | None) -> np.ndarray:
    N = len(Y)
    if sel_group is None:
        mE = np.ones(N, bool)
        mS = mE
    else:
        mE, mS = gEN == sel_group, gSL == sel_group
    K = np.array([Y[mE, 0].sum(), Y[mS, 1].sum(), Y[mE, 2].sum(), Y[mS, 3].sum()], float)
    Nn = np.array([mE.sum(), mS.sum(), mE.sum(), mS.sum()], float)
    contrib_k = np.stack([Y[:, 0] * mE, Y[:, 1] * mS, Y[:, 2] * mE, Y[:, 3] * mS], -1).astype(float)
    contrib_n = np.stack([mE, mS, mE, mS], -1).astype(float)
    return did4(Lh(K[None] - contrib_k, Nn[None] - contrib_n))


def did_suite(Y: np.ndarray, gEN: np.ndarray, gSL: np.ndarray, idx: np.ndarray) -> dict[str, Any]:
    """Overall DiD, DiD(low), DiD(high), DiD(int), D=low-high with shared bootstrap draws + jackknife (BCa for D)."""
    res: dict[str, Any] = {}
    boots, jacks, pts = {}, {}, {}
    for g in (None, "low", "high", "int"):
        name = "overall" if g is None else g
        pts[name] = did_counts(Y, gEN, gSL, g)
        boots[name] = did_boot(Y, gEN, gSL, g, idx)
        jacks[name] = did_jack(Y, gEN, gSL, g)
        res[f"DiD_{name}"] = summarize(pts[name], boots[name], jacks[name])
    D = pts["low"] - pts["high"]
    res["D"] = summarize(D, boots["low"] - boots["high"], jacks["low"] - jacks["high"])
    res["_boot"] = {"D": boots["low"] - boots["high"], "overall": boots["overall"]}
    # descriptive cells
    cells = {}
    for g in (None, "low", "high", "int"):
        name = "all" if g is None else g
        mE = np.ones(len(Y), bool) if g is None else gEN == g
        mS = np.ones(len(Y), bool) if g is None else gSL == g
        for j, (mk, lg) in enumerate([("gemma_it", "en"), ("gemma_it", "sl"), ("gams3_it", "en"), ("gams3_it", "sl")]):
            m = mE if lg == "en" else mS
            k, n = int(Y[m, j].sum()), int(m.sum())
            cells[f"{mk}|{lg}|{name}"] = {"k": k, "n": n, "rate": k / n if n else None, "wilson": wilson(k, n)}
    res["cells"] = cells
    return res


# ------------------------------------------------------------------ SDT on HARD
def sdt_cells(Yu: np.ndarray, Ys: np.ndarray) -> dict[str, np.ndarray]:
    """Yu (Nu,4), Ys (Ns,4) binaries (cols = cells). Returns d', c per cell."""
    zH = zh(Yu.sum(0), len(Yu))
    zF = zh(Ys.sum(0), len(Ys))
    return {"dprime": zH - zF, "c": -(zH + zF) / 2, "H": (Yu.sum(0) + .5) / (len(Yu) + 1),
            "F": (Ys.sum(0) + .5) / (len(Ys) + 1)}


def sdt_boot(Yu: np.ndarray, Ys: np.ndarray, iu: np.ndarray, is_: np.ndarray) -> dict[str, np.ndarray]:
    ku = Yu[iu].sum(1)  # (B,4)
    ks = Ys[is_].sum(1)
    zH = zh(ku, iu.shape[1])
    zF = zh(ks, is_.shape[1])
    return {"dprime": zH - zF, "c": -(zH + zF) / 2}


def sdt_suite(Yu: np.ndarray, Ys: np.ndarray, gu: np.ndarray, gs: np.ndarray, iu: np.ndarray, is_: np.ndarray
              ) -> dict[str, Any]:
    """DiD_d', DiD_c (all items) and D_d' = DiD_d'(low) - DiD_d'(high) with item-category groups; + harmful-only D."""
    out: dict[str, Any] = {}
    pt = sdt_cells(Yu, Ys)
    bt = sdt_boot(Yu, Ys, iu, is_)
    out["cells"] = {k: v.tolist() for k, v in pt.items()}
    out["DiD_dprime"] = summarize(did4(pt["dprime"]), did4(bt["dprime"]))
    out["DiD_c"] = summarize(did4(pt["c"]), did4(bt["c"]))
    out["own_delta"] = {"gemma_dprime_SL_minus_EN": float(pt["dprime"][1] - pt["dprime"][0]),
                        "gams_dprime_SL_minus_EN": float(pt["dprime"][3] - pt["dprime"][2]),
                        "gemma_c_SL_minus_EN": float(pt["c"][1] - pt["c"][0]),
                        "gams_c_SL_minus_EN": float(pt["c"][3] - pt["c"][2])}
    for key, (a, b) in {"gemma_dprime_SL_minus_EN": (1, 0), "gams_dprime_SL_minus_EN": (3, 2)}.items():
        out["own_delta"][key + "_ci95"] = pct_ci(bt["dprime"][:, a] - bt["dprime"][:, b])
    for key, (a, b) in {"gemma_c_SL_minus_EN": (1, 0), "gams_c_SL_minus_EN": (3, 2)}.items():
        out["own_delta"][key + "_ci95"] = pct_ci(bt["c"][:, a] - bt["c"][:, b])
    gd = {}
    gd_boot = {}
    for g in ("low", "high"):
        mu, ms = gu == g, gs == g
        if mu.sum() < 3 or ms.sum() < 3:
            gd[g] = float("nan")
            gd_boot[g] = np.full(iu.shape[0], np.nan)
            continue
        p = sdt_cells(Yu[mu], Ys[ms])
        gd[g] = float(did4(p["dprime"]))
        # bootstrap: reuse the same draws, mask by group of the drawn item
        ku = (Yu[iu] * mu[iu][..., None]).sum(1)
        nu = mu[iu].sum(1)[:, None]
        ks = (Ys[is_] * ms[is_][..., None]).sum(1)
        ns = ms[is_].sum(1)[:, None]
        dp = zh(ku, nu) - zh(ks, ns)
        gd_boot[g] = did4(dp)
        out[f"n_{g}"] = {"unsafe": int(mu.sum()), "safe": int(ms.sum())}
    out["DiD_dprime_low"] = summarize(gd["low"], gd_boot["low"])
    out["DiD_dprime_high"] = summarize(gd["high"], gd_boot["high"])
    out["D_dprime"] = summarize(gd["low"] - gd["high"], gd_boot["low"] - gd_boot["high"])
    # harmful-only D (HARD analogue of C2): DiD on H by group
    hd, hb = {}, {}
    for g in ("low", "high"):
        mu = gu == g
        hd[g] = float(did4(Lh(Yu[mu].sum(0), mu.sum()))) if mu.sum() else float("nan")
        hb[g] = did4(Lh((Yu[iu] * mu[iu][..., None]).sum(1), mu[iu].sum(1)[:, None]))
    out["harmful_DiD_all"] = summarize(float(did4(Lh(Yu.sum(0), len(Yu)))), did4(Lh(Yu[iu].sum(1), iu.shape[1])))
    out["harmful_D"] = summarize(hd["low"] - hd["high"], hb["low"] - hb["high"])
    out["_boot"] = {"DiD_dprime": did4(bt["dprime"]), "DiD_c": did4(bt["c"]), "D_dprime": gd_boot["low"] - gd_boot["high"]}
    return out


# ------------------------------------------------------------------ verdict mappings
def within(ci: list[float], m: float) -> bool:
    return ci[0] > -m and ci[1] < m


def c2_mapping(D: dict, DiD: dict, m: float, c1_pass: bool) -> dict:
    if c1_pass and within(D["ci90"], m) and within(DiD["ci90"], m):
        return {"verdict": "CONFIRM_MAIN", "why": "C1 pass; 90% CIs of D and DiD_ref inside +/-m"}
    if D["est"] > m and D["ci95"][0] > 0:
        return {"verdict": "ALT-1", "why": "D > m, 95% CI > 0"}
    if abs(D["est"]) <= m and DiD["est"] > m and DiD["ci95"][0] > 0:
        return {"verdict": "ALT-3", "why": "D within +/-m and DiD_ref > m (95% CI > 0)"}
    if DiD["est"] < -m and DiD["ci95"][1] < 0:
        return {"verdict": "DEFICIT", "why": "DiD_ref < -m (95% CI < 0)"}
    return {"verdict": "UNRESOLVED", "why": "no pre-registered branch fired"}


def c2_verdict(D: dict, DiD: dict, m: float, mde_D: float, c1_pass: bool) -> dict:
    """Pre-registered: MDE(D) > 2m -> INCONCLUSIVE; else the mapping. The ungated mapping is always reported
    (descriptive) so a reader sees which branch the estimates point to."""
    mp = c2_mapping(D, DiD, m, c1_pass)
    if mde_D > 2 * m:
        return {"verdict": "INCONCLUSIVE", "why": f"MDE(D)={mde_D:.3f} > 2m={2 * m:.3f}",
                "ungated_mapping_descriptive": mp["verdict"]}
    return {**mp, "ungated_mapping_descriptive": mp["verdict"]}


def sdt_tags(dd: dict, dc: dict, Dd: dict, m_d: float, m_c: float) -> list[str]:
    tags = []
    if within(dd["ci90"], m_d) and dc["est"] < -m_c and dc["ci95"][1] < 0:
        tags.append("CRITERION_SHIFT (GaMS SL surplus is a language-wide refusal prior, not supervised reach)")
    if dc["est"] > m_c and dc["ci95"][0] > 0:
        tags.append("SL_CRITERION_DEFICIT_GaMS")
    if dd["est"] > m_d and dd["ci95"][0] > 0 and Dd["est"] > m_d:
        tags.append("ALT-1_ON_HARD (supervised reach)")
    elif dd["est"] > m_d and dd["ci95"][0] > 0 and within(Dd["ci90"], m_d):
        tags.append("UNIFORM_SL_SENSITIVITY_ADVANTAGE (ALT-3-like)")
    if within(dd["ci90"], m_d) and within(dc["ci90"], m_c) and within(Dd["ci90"], m_d):
        tags.append("MAIN_ON_HARD")
    return tags


def sdt_verdict(dd: dict, dc: dict, Dd: dict, m_d: float, m_c: float, mde_dd: float, mde_dc: float | None = None
                ) -> dict:
    """Pre-registered SDT reading. If MDE(DiD_d') > 2m_d' the d'-based readings are 'estimate only'; the criterion
    readings (DiD_c) stay interpretable when MDE(DiD_c) <= 2m_c (F8)."""
    tags = sdt_tags(dd, dc, Dd, m_d, m_c)
    d_ok = mde_dd <= 2 * m_d
    c_ok = mde_dc is None or mde_dc <= 2 * m_c
    if d_ok:
        return {"verdict": tags[0].split(" ")[0] if tags else "UNRESOLVED", "tags": tags, "dprime_powered": True,
                "c_powered": c_ok}
    ctags = [t for t in tags if t.startswith(("SL_CRITERION_DEFICIT", "CRITERION_SHIFT"))]
    c_only = []
    if c_ok:
        if dc["est"] < -m_c and dc["ci95"][1] < 0:
            c_only.append("GaMS_SL_CRITERION_MORE_REFUSAL_PRONE (DiD_c < -m_c)")
        elif dc["est"] > m_c and dc["ci95"][0] > 0:
            c_only.append("SL_CRITERION_DEFICIT_GaMS")
        elif within(dc["ci90"], m_c):
            c_only.append("NO_CRITERION_DIFFERENCE (DiD_c 90% CI within +/-m_c)")
    return {"verdict": "ESTIMATE_ONLY_DPRIME", "why": f"MDE(DiD_d')={mde_dd:.3f} > 2m_d'={2 * m_d:.3f}",
            "tags_descriptive": tags, "criterion_reading": c_only, "dprime_powered": False, "c_powered": c_ok,
            "criterion_tags": ctags}


def holm(pvals: dict[str, float]) -> dict[str, float]:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    out, run = {}, 0.0
    for i, (k, p) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p))
        out[k] = run
    return out


def boot_p_greater0(boot: np.ndarray) -> float:
    b = boot[np.isfinite(boot)]
    return float(min(1.0, 2 * min((b <= 0).mean(), (b >= 0).mean()))) if len(b) else float("nan")


# ------------------------------------------------------------------ misclassification correction
def collapse_confusion(conf14: np.ndarray, labels: list[str], cat2group: dict[str, str]) -> np.ndarray:
    """rows=true(gold), cols=assigned(pred) 14x14 -> 3x3 over [low, high, int]."""
    G = ["low", "high", "int"]
    M = np.zeros((3, 3))
    for i, a in enumerate(labels):
        for j, b in enumerate(labels):
            if a in cat2group and b in cat2group:
                M[G.index(cat2group[a]), G.index(cat2group[b])] += conf14[i, j]
    return M


def q_matrix(M3: np.ndarray, assigned_counts: np.ndarray) -> np.ndarray:
    """Q[a,t] = P(true t | assigned a). From P(assigned a | true t) (row-normalised M3) and a prior over true groups
    chosen so that the implied assigned distribution matches the FINAL assigned counts (EM-style fixed point)."""
    P_a_t = (M3 + 0.5) / (M3 + 0.5).sum(1, keepdims=True)  # (t,a) with add-half smoothing
    pa = assigned_counts / assigned_counts.sum()
    pt = pa.copy()
    for _ in range(500):
        joint = pt[:, None] * P_a_t  # (t,a)
        post = joint / joint.sum(0, keepdims=True)  # P(t|a)
        pt_new = (post * pa[None, :]).sum(1)
        if np.abs(pt_new - pt).max() < 1e-12:
            break
        pt = pt_new
    joint = pt[:, None] * P_a_t
    return (joint / joint.sum(0, keepdims=True)).T  # (a,t)


def solve_true_rates(Q: np.ndarray, r_obs: np.ndarray) -> np.ndarray:
    from scipy.optimize import lsq_linear
    return lsq_linear(Q, r_obs, bounds=(0.001, 0.999)).x
