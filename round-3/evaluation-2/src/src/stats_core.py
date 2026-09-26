"""Core statistics for the readout repair. The GLM (fit_glm), Hautus logit, isotonic-at-0 and kappa are IMPORTED from
exp8 src/analysis.py so the new numbers are computed by the same estimator; the curve/bootstrap machinery is re-vectorised
here (the exp8 Curve class hard-codes one readout column) and is validated by reproducing exp8's lexicon G3 values.
"""
from __future__ import annotations

import importlib.util
import math
import os
import sys

import numpy as np

from common import E8, M_C3, MODELS, SEED

# ---------------------------------------------------------------- import exp8 analysis.py without clobbering our common
_mine = sys.modules.pop("common")
os.environ.setdefault("AII_RESULTS", str(E8 / "results"))
sys.path.insert(0, str(E8 / "src"))
_spec = importlib.util.spec_from_file_location("e8_analysis", E8 / "src" / "analysis.py")
e8 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(e8)
sys.modules["e8_common"] = sys.modules.pop("common")
sys.path.remove(str(E8 / "src"))
sys.modules["common"] = _mine

fit_glm = e8.fit_glm
hautus_logit = e8.hautus_logit
isotonic_at0 = e8.isotonic_at0
kappa_e8 = e8.kappa
wilson = e8.wilson
NBOOT = 2000


def norm_ppf(p):
    from scipy.stats import norm
    return float(norm.ppf(min(max(p, 1e-6), 1 - 1e-6)))


def norm_cdf(z):
    from scipy.stats import norm
    return float(norm.cdf(z))


# ---------------------------------------------------------------- curve data
class CurveData:
    """E[m], S[m]: [n_steps, n_items] binary (NaN = missing) for EN-BT and SL-MT under one readout."""

    def __init__(self, df, col: str, curve_rows_mask, items: list[str], steps: dict):
        self.items = items
        self.steps = steps
        idx = {i: j for j, i in enumerate(items)}
        self.E, self.S = {}, {}
        sub = df[curve_rows_mask]
        for m in MODELS:
            sidx = {s: j for j, s in enumerate(steps[m])}
            for arm, store in (("en_bt", self.E), ("sl_mt", self.S)):
                A = np.full((len(steps[m]), len(items)), np.nan)
                g = sub[(sub.model == m) & (sub.arm == arm)]
                for s, it, v in zip(g.step.values, g.item_id.values, g[col].values):
                    if s in sidx and it in idx and v is not None and not (isinstance(v, float) and math.isnan(v)):
                        A[sidx[s], idx[it]] = float(v)
                store[m] = A

    def counts(self, m, w=None, sel=None):
        E, S = self.E[m], self.S[m]
        ok = ~np.isnan(E) & ~np.isnan(S)
        w = np.ones(E.shape[1]) if w is None else w
        kE = (np.where(ok, E, 0) * w[None, :]).sum(1)
        kS = (np.where(ok, S, 0) * w[None, :]).sum(1)
        n = (ok * w[None, :]).sum(1)
        if sel is not None:
            return kE[sel], kS[sel], n[sel]
        return kE, kS, n

    def coverage(self):
        return {m: float(np.mean(~np.isnan(self.E[m]) & ~np.isnan(self.S[m]))) for m in MODELS}


def rg(p, se, sp):
    """Rogan-Gladen corrected prevalence, clipped to [0.001, 0.999]."""
    den = se + sp - 1.0
    if den <= 0.05:
        return np.clip(p, 0.001, 0.999)
    return np.clip((p + sp - 1.0) / den, 0.001, 0.999)


def fit_model(kE, kS, n, corr=None):
    """GLM of SL on logit-Hautus EN; corr = (SeE, SpE, SeS, SpS) applies Rogan-Gladen to the step rates first."""
    keep = n > 0
    kE, kS, n = kE[keep], kS[keep], n[keep]
    if corr is not None:
        seE, spE, seS, spS = corr
        kE = rg(kE / n, seE, spE) * n
        kS = rg(kS / n, seS, spS) * n
    x = hautus_logit(kE, n)
    a, b = fit_glm(x, kS, n)
    return a, b, x, kS, n


def support(x):
    pE = 1 / (1 + np.exp(-x))
    return {"n_lo": int(np.sum((pE >= 0.2) & (pE < 0.5))), "n_hi": int(np.sum((pE >= 0.5) & (pE <= 0.8))),
            "EN_range": [float(pE.min()), float(pE.max())]}


def g3_analysis(cd: CurveData, paired: bool, *, rule_min: int, corr_draws=None, corr_point=None, n_boot: int = NBOOT,
                seed: int = SEED, iso_ci: bool = False, bca: bool = True) -> dict:
    """Full G3 read: G3 at EN 50% (x*=0), at x*_joint, integrated gap IG over the EN overlap, isotonic, per-model lag.
    corr_point: dict m -> (SeE, SpE, SeS, SpS) for the point estimate; corr_draws: callable(rng) -> same, per replicate."""
    pt = {m: fit_model(*cd.counts(m), corr=None if corr_point is None else corr_point[m]) for m in MODELS}
    if any(len(pt[m][2]) < 2 for m in MODELS):
        return {"status": "insufficient steps with data", "n_steps": {m: int(len(pt[m][2])) for m in MODELS}}
    sup = {m: support(pt[m][2]) for m in MODELS}
    for m in MODELS:
        sup[m]["ok"] = sup[m]["n_lo"] >= rule_min and sup[m]["n_hi"] >= rule_min
    on_support = all(s["ok"] for s in sup.values())
    lo = max(s["EN_range"][0] for s in sup.values())
    hi = min(s["EN_range"][1] for s in sup.values())
    overlap = [lo, hi] if hi > lo else None
    if overlap:
        pooled = np.concatenate([1 / (1 + np.exp(-pt[m][2])) for m in MODELS])
        inside = pooled[(pooled >= lo) & (pooled <= hi)]
        xj_p = float(np.median(inside)) if len(inside) else (lo + hi) / 2
        xj_p = min(max(xj_p, 0.01), 0.99)
        xj = math.log(xj_p / (1 - xj_p))
        grid = np.linspace(math.log(max(lo, 0.005) / (1 - max(lo, 0.005))), math.log(min(hi, 0.995) / (1 - min(hi, 0.995))), 21)
    else:
        xj_p, xj, grid = float("nan"), float("nan"), None

    def stats_from(ab):
        (aG, bG), (aM, bM) = ab["gemma_it"], ab["gams3_it"]
        out = {"G3_50": (aM - aG), "G3_joint": (aM + bM * xj) - (aG + bG * xj) if overlap else float("nan"),
               "IG": float(np.mean((aM + bM * grid) - (aG + bG * grid))) if grid is not None else float("nan")}
        for m, (a, b) in ab.items():
            out[f"lag_logodds_{m}"] = a  # SL log-odds at EN 50% minus logit(0.5)=0
            out[f"lag_pp_{m}"] = 100 * (1.0 / (1.0 + math.exp(-max(min(a, 30.0), -30.0))) - 0.5)
        return out

    point = stats_from({m: pt[m][:2] for m in MODELS})
    iso = {}
    for tag, x0 in (("50", 0.0), ("joint", xj)):
        if tag == "joint" and not overlap:
            continue
        v = {}
        for m in MODELS:
            _, _, x, kS, n = pt[m]
            v[m] = isotonic_at0(x - x0, hautus_logit(kS, n))
        iso[f"G3_iso_{tag}"] = v["gams3_it"] - v["gemma_it"]
    rng = np.random.default_rng(seed)
    nI = len(cd.items)
    nS = {m: len(cd.steps[m]) for m in MODELS}
    B = {k: [] for k in point}
    B_iso = []
    for _ in range(n_boot):
        w = np.bincount(rng.integers(0, nI, nI), minlength=nI).astype(float)
        if paired:
            s = rng.integers(0, nS["gemma_it"], nS["gemma_it"])
            sel = {m: s for m in MODELS}
        else:
            sel = {m: rng.integers(0, nS[m], nS[m]) for m in MODELS}
        corr = corr_draws(rng) if corr_draws is not None else corr_point
        ab, isv = {}, {}
        for m in MODELS:
            a, b, x, kS, n = fit_model(*cd.counts(m, w, sel[m]), corr=None if corr is None else corr[m])
            ab[m] = (a, b)
            if iso_ci:
                isv[m] = isotonic_at0(x, hautus_logit(kS, n))
        st = stats_from(ab)
        for k, v in st.items():
            B[k].append(v)
        if iso_ci:
            B_iso.append(isv["gams3_it"] - isv["gemma_it"])
    res = {"on_support": on_support, "support": sup, "rule_min_per_side": rule_min, "overlap_EN": overlap,
           "x_joint_pEN": xj_p, "per_model": {m: {"a": pt[m][0], "b": pt[m][1], "n_steps": int(len(pt[m][2])),
                                                  "pEN": (1 / (1 + np.exp(-pt[m][2]))).round(4).tolist(),
                                                  "pSL": (pt[m][3] / pt[m][4]).round(4).tolist()} for m in MODELS},
           "n_items": nI, "n_boot": n_boot, "coverage": cd.coverage(), **iso}
    for k, v in point.items():
        arr = np.array(B[k], dtype=float)
        arr = arr[np.isfinite(arr)]
        if len(arr) < 10:
            res[k] = {"est": v}
            continue
        se = float(np.std(arr, ddof=1))
        res[k] = {"est": float(v), "SE": se, "MDE": 2.8 * se, "CI95": np.percentile(arr, [2.5, 97.5]).tolist(),
                  "CI90": np.percentile(arr, [5, 95]).tolist(), "boot_mean": float(arr.mean()), "_boot": arr}
        if k.startswith("G3") or k == "IG":
            res[k]["verdict_m"] = verdict(res[k], M_C3)
            res[k]["verdict_m_local"] = verdict(res[k], 0.20067069546215124)
    if iso_ci and B_iso:
        res["G3_iso_50_CI95"] = np.nanpercentile(B_iso, [2.5, 97.5]).tolist()
    if bca:
        try:
            _bca(cd, res, point, corr_point)
        except (ValueError, FloatingPointError, np.linalg.LinAlgError) as e:
            res["BCa_error"] = str(e)
    for k in list(res):
        if isinstance(res[k], dict):
            res[k].pop("_boot", None)
    res["headline"] = "G3_50" if on_support else "G3_joint+IG (support rule failed; G3_50 EXTRAPOLATED)"
    return res


def _bca(cd, res, point, corr_point):
    nI = len(cd.items)
    step_i = max(1, nI // 50)
    jack = {k: [] for k in ("G3_50", "G3_joint", "IG")}
    xj_p = res["x_joint_pEN"]
    xj = math.log(xj_p / (1 - xj_p)) if res["overlap_EN"] else float("nan")
    if res["overlap_EN"]:
        lo, hi = res["overlap_EN"]
        grid = np.linspace(math.log(max(lo, 0.005) / (1 - max(lo, 0.005))), math.log(min(hi, 0.995) / (1 - min(hi, 0.995))), 21)
    for i in range(0, nI, step_i):
        w = np.ones(nI)
        w[i:i + step_i] = 0
        ab = {m: fit_model(*cd.counts(m, w), corr=None if corr_point is None else corr_point[m])[:2] for m in MODELS}
        (aG, bG), (aM, bM) = ab["gemma_it"], ab["gams3_it"]
        jack["G3_50"].append(aM - aG)
        if res["overlap_EN"]:
            jack["G3_joint"].append((aM + bM * xj) - (aG + bG * xj))
            jack["IG"].append(float(np.mean((aM + bM * grid) - (aG + bG * grid))))
    for k, jk in jack.items():
        if not jk or not isinstance(res.get(k), dict) or "SE" not in res[k]:
            continue
        jk = np.array(jk)
        arr = res[k]["_boot"]
        z0 = norm_ppf(float(np.mean(arr < point[k])))
        acc = np.sum((jk.mean() - jk) ** 3) / (6 * np.sum((jk.mean() - jk) ** 2) ** 1.5 + 1e-12)
        qs = []
        for alpha in (0.025, 0.975):
            za = norm_ppf(alpha)
            q = norm_cdf(z0 + (z0 + za) / (1 - acc * (z0 + za)))
            qs.append(float(np.percentile(arr, 100 * q)))
        res[k]["CI95_BCa"] = qs
        res[k]["BCa_acceleration"] = float(acc)


def verdict(st: dict, m: float) -> str:
    if "CI95" not in st:
        return "NA"
    c90, c95, mde = st["CI90"], st["CI95"], st["MDE"]
    if c95[1] < -m:
        return "LAG"
    if -m < c90[0] and c90[1] < m and mde <= 2 * m:
        return "LOCKSTEP"
    return "INCONCLUSIVE"


def permutation_B(cd: CurveData, n_perm: int = 2000, seed: int = SEED + 1) -> dict:
    rng = np.random.default_rng(seed)
    cnt = {m: cd.counts(m) for m in MODELS}
    T = len(cd.steps["gemma_it"])

    def g3c(c):
        return fit_model(*c["gams3_it"])[0] - fit_model(*c["gemma_it"])[0]

    obs = g3c(cnt)
    null = []
    for _ in range(n_perm):
        sw = rng.random(T) < 0.5
        c = {}
        for m, o in (("gemma_it", "gams3_it"), ("gams3_it", "gemma_it")):
            c[m] = tuple(np.where(sw, cnt[o][j], cnt[m][j]) for j in range(3))
        null.append(g3c(c))
    null = np.array(null)
    return {"G3_obs": float(obs), "null_mean": float(null.mean()), "null_sd": float(null.std()),
            "p_two_sided": float((np.sum(np.abs(null) >= abs(obs)) + 1) / (len(null) + 1))}


def placebo_lang_swap(cd: CurveData, n: int = 1000, seed: int = SEED + 2) -> dict:
    """swap EN/SL labels within item x step (independently per model); G3 should centre at 0."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        ab = {}
        for m in MODELS:
            E, S = cd.E[m], cd.S[m]
            sw = rng.random(E.shape) < 0.5
            E2, S2 = np.where(sw, S, E), np.where(sw, E, S)
            ok = ~np.isnan(E2) & ~np.isnan(S2)
            kE, kS, nn = np.where(ok, E2, 0).sum(1), np.where(ok, S2, 0).sum(1), ok.sum(1).astype(float)
            ab[m] = fit_model(kE, kS, nn)[0]
        out.append(ab["gams3_it"] - ab["gemma_it"])
    out = np.array(out)
    out = out[np.isfinite(out)]
    return {"mean": float(out.mean()), "sd": float(out.std()), "n": int(len(out))}


# ---------------------------------------------------------------- agreement
def cohen_kappa(a, b):
    a, b = np.asarray(a), np.asarray(b)
    if len(a) == 0:
        return float("nan")
    po = float(np.mean(a == b))
    cats = np.union1d(a, b)
    pe = sum(float(np.mean(a == c)) * float(np.mean(b == c)) for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def agreement(a, b, n_boot: int = 500, seed: int = SEED) -> dict:
    a, b = np.asarray(a), np.asarray(b)
    n = len(a)
    if n == 0:
        return {"n": 0}
    k = cohen_kappa(a, b)
    po = float(np.mean(a == b))
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(n_boot):
        i = rng.integers(0, n, n)
        bs.append(cohen_kappa(a[i], b[i]))
    bs = np.array(bs, dtype=float)
    bs = bs[np.isfinite(bs)]
    return {"n": int(n), "kappa": k, "kappa_CI95": np.percentile(bs, [2.5, 97.5]).tolist() if len(bs) > 20 else None,
            "PABAK": 2 * po - 1, "agree": po, "rate_a": float(np.mean(a == 1)) if a.dtype != object else None,
            "rate_b": float(np.mean(b == 1)) if b.dtype != object else None}


def se_sp_weighted(judge, ref, w):
    """IPW sensitivity / specificity of judge (binary) against ref (binary)."""
    judge, ref, w = np.asarray(judge, float), np.asarray(ref, float), np.asarray(w, float)
    pos, neg = ref == 1, ref == 0
    se = float(np.sum(w[pos] * (judge[pos] == 1)) / max(np.sum(w[pos]), 1e-9)) if pos.any() else float("nan")
    sp = float(np.sum(w[neg] * (judge[neg] == 0)) / max(np.sum(w[neg]), 1e-9)) if neg.any() else float("nan")
    return se, sp, int(pos.sum()), int(neg.sum())
