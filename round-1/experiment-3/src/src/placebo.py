#!/usr/bin/env python3
"""Placebo / shuffle checks for the headline statistics (TODO-4 audit): the same pair-bootstrap machinery must NOT
produce 'significant' results on inputs where the true effect is zero by construction.
  P1 model-label shuffle: for each pair, swap GaMS<->Gemma rows with prob 1/2 (all conditions, both langs together);
     TD*, DiD_ref expected ~0 -> report the fraction of 200 shuffles whose 95% CI excludes 0 (should be ~<=5%).
  P2 condition placebo: replace C1 by C0 for both models (ablation with no effect) -> G, TD must be exactly 0.
  P3 language-label shuffle within pair (swap EN<->SL rows per pair, same swap for every model/condition) -> gap-based
     statistics centred on 0.
Uses the lexicon readout and s. Writes results/placebo.json."""
from __future__ import annotations

import json

import numpy as np

import analyze as A
from common import RES, SEED, setup_logging


def main() -> None:
    setup_logging("placebo")
    pids, cells = A.load_cells()
    out = {}
    rng = np.random.default_rng(SEED + 7)
    A.NB = 300
    for rd, cont in [("lex", False), ("s", True)]:
        M = A.readout_matrix(cells, rd)
        M = {k: v for k, v in M.items() if k[2] in ("en", "sl")}
        # P2
        Mp = dict(M)
        for m in A.MODS:
            for g in ["en", "sl"]:
                Mp[(m, "C1", g)] = M[(m, "C0", g)].copy()
        st = A.full_stats(Mp, cont=cont)
        out[f"P2_{rd}"] = {"G": {k: v["point"] for k, v in st["G"].items() if k.endswith(("C2", "C3"))},
                           "note": "C1:=C0 -> G(M,ctrl) = -shrink(M,ctrl); TD* reflects controls only"}
        # P1
        excl_td, excl_did, tds, pos_td, pos_g = 0, 0, [], 0, 0
        n_sh = 60
        for _ in range(n_sh):
            sw = rng.random(400) < 0.5
            Ms = {}
            for (m, c, g), v in M.items():
                o = "gemma" if m == "gams" else "gams"
                Ms[(m, c, g)] = np.where(sw, M[(o, c, g)], v)
            st = A.full_stats(Ms, cont=cont, idx_all=rng.integers(0, 400, size=(A.NB, 400)))
            tds.append(st["TDstar"]["point"])
            excl_td += st["TDstar"]["ci95"][0] > 0 or st["TDstar"]["ci95"][1] < 0
            pos_td += st["TDstar"]["ci95"][0] > 0
            pos_g += all(st["TD"][c]["ci95"][0] > 0 for c in ["C2", "C3"])
            excl_did += st["DiD_ref_C0"]["ci95"][0] > 0 or st["DiD_ref_C0"]["ci95"][1] < 0
        out[f"P1_{rd}"] = {"n_shuffles": n_sh, "frac_TDstar_CI_excludes_0": excl_td / n_sh,
                           "frac_DiDref_CI_excludes_0": excl_did / n_sh,
                           "frac_TDstar_CI_lower_gt_0 (false-survival side)": pos_td / n_sh,
                           "frac_both_TD_C2_C3_lower_gt_0": pos_g / n_sh, "mean_TDstar": float(np.mean(tds)),
                           "sd_TDstar": float(np.std(tds))}
        # P3
        sw = rng.random(400) < 0.5
        Ml = {}
        for (m, c, g), v in M.items():
            o = "sl" if g == "en" else "en"
            Ml[(m, c, g)] = np.where(sw, M[(m, c, o)], v)
        st = A.full_stats(Ml, cont=cont)
        out[f"P3_{rd}"] = {"DiD_ref_C0": st["DiD_ref_C0"], "gap_C0": {k: v for k, v in st["gap"].items() if k.endswith("C0")}}
        print(rd, json.dumps(out[f"P1_{rd}"]))
    (RES / "placebo.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
