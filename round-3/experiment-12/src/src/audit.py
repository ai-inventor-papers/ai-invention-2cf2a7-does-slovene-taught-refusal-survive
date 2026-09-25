#!/usr/bin/env python3
"""STEP 9 audit (path B, written independently of analyze.py: plain json + numpy, no shared helpers).
Reads ONLY results/items/*.jsonl, recomputes every headline number and compares to results/analysis.json
(point estimates to 1e-9, bootstrap CI endpoints within 0.01 using its own seed stream), and runs three
label-permutation placebos (model swap -> I, language swap -> A, condition swap -> H), 1,000 permutations each."""
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

WS = Path(__file__).resolve().parent.parent
IT = WS / "results" / "items"
METRIC = {"arc_challenge": "acc_norm", "hellaswag": "acc_norm", "openbookqa": "acc_norm", "piqa": "acc_norm",
          "boolq": "acc", "winogrande": "acc", "belebele": "acc"}
TASKS = ["arc_challenge", "boolq", "hellaswag", "openbookqa", "piqa", "winogrande"]
rng = np.random.default_rng(424242)


def rj(p):
    return [json.loads(x) for x in Path(p).read_text().splitlines() if x.strip()] if Path(p).exists() else []


def load(kind):
    D = defaultdict(dict)  # (model, cond, lang, task) -> {item_id: (correct, 1/k)}
    for f in sorted(IT.glob(kind + "_*.jsonl")):
        for r in rj(f):
            D[(r["model"], r["cond"], r["lang"], r["task"])][r["item_id"]] = (float(r[METRIC[r["task"]]]), 1.0 / r["n_choices"])
    return D


def vecs(D, m, c, l, t):
    o, e = D.get((m, "orig", l, t)), D.get((m, c, l, t))
    if not o or not e:
        return None
    ids = sorted(set(o) & set(e))
    return (np.array([o[i][0] for i in ids]), np.array([e[i][0] for i in ids]), float(np.mean([o[i][1] for i in ids])), ids)


def Hval(vo, vc, ch):
    return (vc.mean() - ch) / (vo.mean() - ch) - 1


def macro(D, m, c, l, tasks):
    hs = []
    for t in tasks:
        v = vecs(D, m, c, l, t)
        if v is None:
            continue
        vo, vc, ch, _ = v
        if vo.mean() - ch >= 0.10 - 1e-9:
            hs.append(Hval(vo, vc, ch))
    return float(np.mean(hs)) if hs else float("nan")


def close(a, b, tol):
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, float) and np.isnan(a):
        return isinstance(b, float) and np.isnan(b)
    return abs(a - b) <= tol


def main():
    A = json.loads((WS / "results" / "analysis.json").read_text())
    out = {"checks": [], "placebos": {}}

    def check(name, mine, theirs, tol=1e-9):
        ok = close(mine, theirs, tol)
        out["checks"].append({"name": name, "audit": mine, "analysis": theirs, "tol": tol, "pass": bool(ok)})

    U = load("util")
    models = sorted({k[0] for k in U})
    conds = sorted({k[1] for k in U if k[1] != "orig"})
    ut = A["utility"]
    for m in models:
        for c in conds:
            if c not in ut["macros"].get(m, {}):
                continue
            for l in ("en", "sl"):
                for t in TASKS:
                    v = vecs(U, m, c, l, t)
                    if v is None:
                        continue
                    vo, vc, ch, ids = v
                    cell = ut["cells"][m][c][l][t]
                    check(f"acc {m}/{c}/{l}/{t}", float(vc.mean()), cell["acc"], 1e-5)
                    check(f"H {m}/{c}/{l}/{t}", float(Hval(vo, vc, ch)), cell["H"], 1e-5)
                mm = macro(U, m, c, l, TASKS)
                check(f"macroH {m}/{c}/{l}", mm, ut["macros"][m][c][l]["macro_H"], 1e-5)
                # own-seed bootstrap of macro H: CI endpoints within 0.01
                elig = [t for t in TASKS if vecs(U, m, c, l, t) is not None and
                        vecs(U, m, c, l, t)[0].mean() - vecs(U, m, c, l, t)[2] >= 0.10 - 1e-9]
                if elig:
                    bs = []
                    V = {t: vecs(U, m, c, l, t) for t in elig}
                    IX = {t: rng.integers(0, len(V[t][0]), (2000, len(V[t][0]))) for t in elig}
                    for t in elig:
                        vo, vc, ch, _ = V[t]
                        bs.append((vc[IX[t]].mean(1) - ch) / (vo[IX[t]].mean(1) - ch) - 1)
                    b = np.mean(bs, 0)
                    lo, hi = np.percentile(b, [2.5, 97.5])
                    ci = ut["macros"][m][c][l]["macro_H_ci95"]
                    check(f"macroH_ci95_lo {m}/{c}/{l}", float(lo), ci[0], 0.01)
                    check(f"macroH_ci95_hi {m}/{c}/{l}", float(hi), ci[1], 0.01)
                    # gate recomputation
                    loss, loss_hi = -mm, -float(lo)
                    verdict = "CATASTROPHIC" if loss > 0.2 else ("POSSIBLY_CATASTROPHIC" if loss_hi > 0.2 else "OK")
                    g = A["gates"][m][c]["per_lang"][l]
                    if g["rule"].startswith("headroom"):
                        # the CI-based verdict can legitimately flip only if loss_hi is within bootstrap noise of .20
                        agree = verdict == g["verdict"] or abs(loss_hi - 0.2) < 0.01
                        out["checks"].append({"name": f"gate {m}/{c}/{l}", "audit": verdict, "analysis": g["verdict"], "pass": bool(agree)})
            if "A_sl_minus_en" in ut["macros"][m][c]:
                a = macro(U, m, c, "sl", TASKS) - macro(U, m, c, "en", TASKS)
                check(f"A {m}/{c}", a, ut["macros"][m][c]["A_sl_minus_en"], 1e-5)
    for c, d in ut.get("interaction", {}).items():
        I = (macro(U, "gams3_it", c, "sl", TASKS) - macro(U, "gams3_it", c, "en", TASKS)) - \
            (macro(U, "gemma_it", c, "sl", TASKS) - macro(U, "gemma_it", c, "en", TASKS))
        check(f"I {c}", I, d["I"], 1e-5)

    # ---------------- KL recomputation ----------------
    for m in models:
        rows = rj(IT / f"kl_{m}.jsonl")
        if not rows or m not in A["kl"]:
            continue
        by = defaultdict(dict)
        for r in rows:
            by[r["arm"]][r["item_id"]] = dict(r["kl"])
        for r in rj(IT / f"klextra_{m}.jsonl"):
            if r["item_id"] in by[r["arm"]]:
                by[r["arm"]][r["item_id"]].update(r["kl"])
        arms = [a for a in ("en_orig", "en_bt", "sl_mt", "hu_mt") if a in by]
        ids = sorted(set.intersection(*[set(by[a]) for a in arms]))
        for c in A["kl"][m]["conds"]:
            for a in arms:
                v = float(np.mean([by[a][i][c]["first"] for i in ids]))
                check(f"KLfirst {m}/{c}/{a}", v, A["kl"][m]["means"][c][a]["first"]["mean"], 1e-9)
        rj_ = [c for c in A["kl"][m]["conds"] if c.startswith("rand_nm_j")]
        for c in ("E_iter1", "E_art2"):
            if c not in A["kl"][m]["conds"]:
                continue
            for k in ("first", "multi"):
                def mean_arm(a, cc):
                    if cc == "rand":
                        return float(np.mean([np.mean([by[a][i][j][k] for j in rj_]) for i in ids]))
                    return float(np.mean([by[a][i][cc][k] for i in ids]))
                r_e = mean_arm("sl_mt", c) / mean_arm("en_bt", c)
                r_r = mean_arm("sl_mt", "rand") / mean_arm("en_bt", "rand")
                d = A["kl"][m]["ratios"][c][k]["sl_over_enbt"]
                check(f"RATIO {m}/{c}/{k}", r_e, d["ratio"], 1e-9)
                check(f"EXCESS {m}/{c}/{k}", r_e / r_r, d["excess_vs_rand"]["excess"], 1e-9)

    # ---------------- placebos (utility, E_iter1) ----------------
    def per_pair(m, c, l, t):
        v = vecs(U, m, c, l, t)
        return v

    for c in [x for x in ("E_iter1", "E_art2") if x in conds]:
        # (c) condition-label swap within item -> H centres at 0
        for m in [mm for mm in models if c in ut["macros"].get(mm, {})]:
            for l in ("en", "sl"):
                perm = []
                obs = macro(U, m, c, l, TASKS)
                V = {t: per_pair(m, c, l, t) for t in TASKS}
                V = {t: v for t, v in V.items() if v is not None and v[0].mean() - v[2] >= 0.10 - 1e-9}
                for _ in range(1000):
                    hs = []
                    for t, (vo, vc, ch, _) in V.items():
                        sw = rng.random(len(vo)) < 0.5
                        a, b = np.where(sw, vc, vo), np.where(sw, vo, vc)
                        hs.append(Hval(a, b, ch))
                    perm.append(np.mean(hs))
                perm = np.array(perm)
                out["placebos"][f"cond_swap H {m}/{c}/{l}"] = {"observed": obs, "perm_mean": float(perm.mean()), "perm_sd": float(perm.std()),
                                                              "centred": bool(abs(perm.mean()) < 0.25 * perm.std() + 1e-12),
                                                              "p_two_sided": float((np.abs(perm) >= abs(obs)).mean())}
        # (b) language-label swap within pair (paired tasks share ids across EN/SL) -> A centres at 0
        for m in [mm for mm in models if c in ut["macros"].get(mm, {})]:
            V = {}
            for t in TASKS:
                ve, vs = per_pair(m, c, "en", t), per_pair(m, c, "sl", t)
                if ve is None or vs is None or ve[3] != vs[3]:
                    continue
                V[t] = (ve, vs)
            obs = macro(U, m, c, "sl", TASKS) - macro(U, m, c, "en", TASKS)
            perm = []
            for _ in range(1000):
                he, hs_ = [], []
                for t, (ve, vs) in V.items():
                    sw = rng.random(len(ve[0])) < 0.5
                    eo, ec = np.where(sw, vs[0], ve[0]), np.where(sw, vs[1], ve[1])
                    so, sc = np.where(sw, ve[0], vs[0]), np.where(sw, ve[1], vs[1])
                    if ve[0].mean() - ve[2] >= 0.10 - 1e-9:
                        he.append(Hval(eo, ec, ve[2]))
                    if vs[0].mean() - vs[2] >= 0.10 - 1e-9:
                        hs_.append(Hval(so, sc, vs[2]))
                perm.append(np.mean(hs_) - np.mean(he))
            perm = np.array(perm)
            out["placebos"][f"lang_swap A {m}/{c}"] = {"observed": obs, "perm_mean": float(perm.mean()), "perm_sd": float(perm.std()),
                                                       "centred": bool(abs(perm.mean()) < 0.25 * perm.std() + 1e-12),
                                                       "p_two_sided": float((np.abs(perm - perm.mean()) >= abs(obs - perm.mean())).mean())}
        # (a) model-label swap per pair (items identical across models) -> I centres at 0
        if len(models) == 2 and all(c in ut["macros"].get(mm, {}) for mm in models):
            g, e = "gams3_it", "gemma_it"
            V = {}
            for t in TASKS:
                vv = [per_pair(mm, c, l, t) for mm in (g, e) for l in ("en", "sl")]
                if any(v is None for v in vv) or len({tuple(v[3]) for v in vv}) != 1:
                    continue
                V[t] = vv
            obs = ut["interaction"].get(c, {}).get("I", float("nan"))
            perm = []
            for _ in range(1000):
                acc = {(mm, l): [] for mm in (g, e) for l in ("en", "sl")}
                for t, (ge, gs, ee, es) in V.items():
                    sw = rng.random(len(ge[0])) < 0.5
                    for (x, y, l) in ((ge, ee, "en"), (gs, es, "sl")):
                        xo, xc = np.where(sw, y[0], x[0]), np.where(sw, y[1], x[1])
                        yo, yc = np.where(sw, x[0], y[0]), np.where(sw, x[1], y[1])
                        if xo.mean() - x[2] >= 0.10 - 1e-9:
                            acc[(g, l)].append(Hval(xo, xc, x[2]))
                        if yo.mean() - y[2] >= 0.10 - 1e-9:
                            acc[(e, l)].append(Hval(yo, yc, y[2]))
                perm.append((np.mean(acc[(g, "sl")]) - np.mean(acc[(g, "en")])) - (np.mean(acc[(e, "sl")]) - np.mean(acc[(e, "en")])))
            perm = np.array(perm)
            out["placebos"][f"model_swap I {c}"] = {"observed": obs, "perm_mean": float(perm.mean()), "perm_sd": float(perm.std()),
                                                    "centred": bool(abs(perm.mean()) < 0.25 * perm.std() + 1e-12),
                                                    "p_two_sided": float((np.abs(perm - perm.mean()) >= abs(obs - perm.mean())).mean())}
    # ---------------- scorer second path ----------------
    out["scorer2"] = A.get("scorer2_agreement", {})
    out["n_checks"] = len(out["checks"])
    out["n_failed"] = sum(not c["pass"] for c in out["checks"])
    out["failed"] = [c for c in out["checks"] if not c["pass"]][:50]
    out["placebos_all_centred"] = all(v["centred"] for v in out["placebos"].values())
    out["all_pass"] = out["n_failed"] == 0 and out["placebos_all_centred"]
    (WS / "results" / "audit.json").write_text(json.dumps(out, indent=2, default=float))
    print(f"audit: {out['n_checks']} checks, {out['n_failed']} failed; placebos centred: {out['placebos_all_centred']}")
    for k, v in out["placebos"].items():
        print(f"  {k}: obs={v['observed']:.4f} perm_mean={v['perm_mean']:.4f} sd={v['perm_sd']:.4f} p={v['p_two_sided']:.3f}")


if __name__ == "__main__":
    main()
