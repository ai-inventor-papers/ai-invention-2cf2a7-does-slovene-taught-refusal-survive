#!/usr/bin/env python3
"""Independent re-derivation of the headline numbers (TODO 4), different code path from stats_lib/analysis/audit.

Reads RAW files only: outputs/final/gen_*.jsonl (responses), outputs/final/labels_local_qwen3.jsonl (primary labels),
outputs/ledgers/ledger_final_refusal_gemini.jsonl (gemini subset), data/*.jsonl (manifests). Uses pandas groupby and
its own regex for identity names. Then a placebo: the same sign-flip permutation test is run on (a) the real data and
(b) data whose model labels were randomly swapped within each item (the placebo must NOT be significant).
Output: results/rederive_headlines.json
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parent.parent
rj = lambda p: [json.loads(l) for l in open(p) if l.strip()]  # noqa: E731


def L(k, n):
    p = (k + 0.5) / (n + 1)
    return math.log(p / (1 - p))


def Z(k, n):
    return float(norm.ppf((k + 0.5) / (n + 1)))


gen = pd.DataFrame([r for m in ("gemma_it", "gams3_it") for r in rj(ROOT / f"outputs/final/gen_{m}.jsonl")])
q = pd.DataFrame(rj(ROOT / "outputs/final/labels_local_qwen3.jsonl"))[["key", "qwen_label"]]
df = gen.merge(q, on="key", how="left")
df["R"] = (df["qwen_label"] == "REFUSE").astype(float)
man = pd.DataFrame(rj(ROOT / "data/hard.jsonl"))[["gid", "is_harmful"]].drop_duplicates("gid")
df = df.merge(man, on="gid", how="left")


def did_table(sub: pd.DataFrame, en: str, sl: str, idcol: str) -> tuple[float, pd.DataFrame]:
    w = sub.pivot_table(index=idcol, columns=["model", "arm"], values="R", aggfunc="first").dropna()
    cols = [("gemma_it", en), ("gemma_it", sl), ("gams3_it", en), ("gams3_it", sl)]
    k, n = w[cols].sum().values, len(w)
    return (L(k[3], n) - L(k[2], n)) - (L(k[1], n) - L(k[0], n)), w[cols]


out = {}
nat = df[df.set == "refuseu_nat"]
out["DiD_ref_natural"], Wn = did_table(nat, "EN_nat", "SL_nat", "pair_id")
out["DiD_ref_MT"], Wm = did_table(df[df.set == "refuseu_x"], "EN_BT", "SL_MT", "item_id")


def sdt(sub):
    res = {}
    for mk in ("gemma_it", "gams3_it"):
        for arm in ("EN_BT", "SL_MT"):
            s = sub[(sub.model == mk) & (sub.arm == arm)]
            u, f = s[s.is_harmful == True], s[s.is_harmful == False]  # noqa: E712
            zH, zF = Z(u.R.sum(), len(u)), Z(f.R.sum(), len(f))
            res[(mk, arm)] = (zH - zF, -(zH + zF) / 2)
    dd = (res[("gams3_it", "SL_MT")][0] - res[("gams3_it", "EN_BT")][0]) - (res[("gemma_it", "SL_MT")][0] - res[("gemma_it", "EN_BT")][0])
    dc = (res[("gams3_it", "SL_MT")][1] - res[("gams3_it", "EN_BT")][1]) - (res[("gemma_it", "SL_MT")][1] - res[("gemma_it", "EN_BT")][1])
    return dd, dc


hard = df[df.set == "hard"]
out["HARD_DiD_dprime"], out["HARD_DiD_c"] = sdt(hard)

# identity: own regex on raw responses
OWN = {"gemma_it": re.compile(r"\bGemma\b", re.I), "gams3_it": re.compile(r"\bGaMS\b", re.I)}
idm = {r["gid"]: r["kind"] for r in rj(ROOT / "data/identity.jsonl")}
ide = df[(df.set == "identity")].copy()
ide = ide[ide.gid.map(idm) == "identity"]
first = lambda t: min([(m.start(), n) for n, rx in (("GaMS", re.compile(r"\bGaMS\b", re.I)), ("Gemma", re.compile(r"\bGemm[ae]\b", re.I))) for m in [rx.search(t)] if m] or [(0, None)])[1]  # noqa: E731
ide["R"] = [float(bool(OWN[m].search(t))) for m, t in zip(ide.model, ide.response)]
out["DiD_id_any_own_mention"], _ = did_table(ide, "EN", "SL", "pair_id")

# gemini subset on natural pairs from the raw ledger
gl = {r["item_key"]: r["label"] for r in rj(ROOT / "outputs/ledgers/ledger_final_refusal_gemini.jsonl")
      if r.get("label") in ("REFUSE", "PARTIAL", "COMPLY")}
ng = nat.copy()
ng["R"] = [float(gl[k] == "REFUSE") if k in gl else np.nan for k in ng.key]
out["DiD_ref_natural_gemini_subset"], Wg = did_table(ng.dropna(subset=["R"]), "EN_nat", "SL_nat", "pair_id")
out["n_gemini_subset_pairs"] = len(Wg)


# ---------------- permutation (placebo-validated) tests: swap model labels within item with prob .5
def perm_p(W: np.ndarray, stat, B=2000, seed=0):
    rng = np.random.default_rng(seed)
    obs = stat(W)
    null = []
    for _ in range(B):
        flip = rng.random(len(W)) < 0.5
        Wp = W.copy()
        Wp[flip] = Wp[flip][:, [2, 3, 0, 1]]
        null.append(stat(Wp))
    return obs, float((np.abs(null) >= abs(obs)).mean())


def did_stat(W):
    n = len(W)
    k = W.sum(0)
    return (L(k[3], n) - L(k[2], n)) - (L(k[1], n) - L(k[0], n))


def placebo(W: np.ndarray, seed=1):
    rng = np.random.default_rng(seed)
    flip = rng.random(len(W)) < 0.5
    Wp = W.copy()
    Wp[flip] = Wp[flip][:, [2, 3, 0, 1]]
    return Wp


tests = {}
for name, W in (("DiD_ref_MT", Wm.values), ("DiD_ref_natural", Wn.values), ("DiD_id", _.values)):
    obs, p = perm_p(W, did_stat)
    pobs, pp = perm_p(placebo(W), did_stat)
    tests[name] = {"obs": obs, "perm_p": p, "placebo_obs": pobs, "placebo_perm_p": pp}
# HARD DiD_c: item-level matrix per stratum, swap models within item
hw = hard[hard.arm.isin(["EN_BT", "SL_MT"])].pivot_table(index="item_id", columns=["model", "arm"], values="R",
                                                          aggfunc="first").dropna()
harm = hard.drop_duplicates("item_id").set_index("item_id").loc[hw.index, "is_harmful"].values.astype(bool)
cols = [("gemma_it", "EN_BT"), ("gemma_it", "SL_MT"), ("gams3_it", "EN_BT"), ("gams3_it", "SL_MT")]
HW = hw[cols].values


def c_stat(W):
    u, f = W[harm], W[~harm]
    c = [-(Z(u[:, j].sum(), len(u)) + Z(f[:, j].sum(), len(f))) / 2 for j in range(4)]
    return (c[3] - c[2]) - (c[1] - c[0])


obs, p = perm_p(HW, c_stat, B=1000)
pobs, pp = perm_p(placebo(HW), c_stat, B=1000)
tests["HARD_DiD_c"] = {"obs": obs, "perm_p": p, "placebo_obs": pobs, "placebo_perm_p": pp}
out["permutation_tests"] = tests

A = json.loads((ROOT / "results/analysis_final.json").read_text())
ref = {"DiD_ref_natural": A["C2_refuseu"]["DiD_overall"]["est"],
       "DiD_ref_MT": A["C2_refuseu_sensitivities"]["item_matched_MT_ENBT"]["DiD_overall"]["est"],
       "HARD_DiD_dprime": A["C2_hard_sdt"]["primary_SLMT_vs_ENBT"]["DiD_dprime"]["est"],
       "HARD_DiD_c": A["C2_hard_sdt"]["primary_SLMT_vs_ENBT"]["DiD_c"]["est"],
       "DiD_ref_natural_gemini_subset": A["judge_family_robustness_gemini_subset"]["C2_refuseu_R_gemini"]["DiD_overall"]["est"],
       "DiD_id_regex_pipeline": A["C1"]["identity"]["DiD_id"]["est"]}
out["pipeline_values"] = ref
out["match_1e-9"] = {k: abs(out[k] - v) < 1e-9 for k, v in ref.items() if k in out}
(ROOT / "results/rederive_headlines.json").write_text(json.dumps(out, indent=1, default=float))
print(json.dumps(out, indent=1, default=float))
