#!/usr/bin/env python3
"""EXPLORATORY (post-freeze; found during execution): last-token format confound in the base-model harm contrast.
Harmful RefusEU prompts end in '"' (EN, quote-wrapped) or '?' (SL 95%), harmless alpaca mostly in '.'. This
re-computes the S1 statistics on a PUNCTUATION-MATCHED subset: harmful and harmless prompts that both end in '?'
(quotes stripped at the end: '?"' counts as '?'), directions refit on CONSTRUCT '?'-items, d' on SCORE '?'-items,
per layer, for pt and gb; plus a pure format direction ('?'-ending vs '.'-ending harmless) and its cosine with the
harm direction. Bootstrap CIs (items resampled). Writes results/analysis/punct_check.json."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SEED = 20260923


def endc(t: str) -> str:
    t = t.strip().rstrip('"”“\'').strip()
    return t[-1] if t else ""


def dp(a, b):
    return float((a.mean() - b.mean()) / np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2))


def main() -> None:
    pairs = {p["pair_id"]: p for p in map(json.loads, (ROOT / "data/refuseu_pairs.jsonl").read_text().splitlines())}
    alp = {a["hid"]: a for a in map(json.loads, (ROOT / "data/alpaca_harmless.jsonl").read_text().splitlines())}
    L_pt = json.loads((ROOT / "results/base_pt/layer_choice.json").read_text())["L_pt"]
    L_gb = json.loads((ROOT / "results/base_gb/layer_stats.json").read_text())["L_own"]
    out = {"note": __doc__.splitlines()[0], "L_pt": L_pt, "L_gb": L_gb}
    rng = np.random.default_rng(SEED)
    D = {}
    for m in ["pt", "gb"]:
        idx = pd.read_json(ROOT / f"results/base_{m}/resid_index.jsonl", lines=True)
        idx["text"] = [pairs[i][l] if k == "harm" else alp[i][l] for i, l, k in zip(idx.item, idx.lang, idx.kind)]
        idx["end"] = idx.text.map(endc)
        _cache = ROOT / f"scratch/resid_{m}.npy"
        if not _cache.exists():
            raise FileNotFoundError(f"{_cache} is a regenerable cache (not kept, >100 MB): run src/base_geometry.py first")
        X = np.load(_cache, mmap_mode="r")
        layers = sorted(set(range(2, 49, 2)) | {L_pt, L_gb})
        XS = {l: np.array(X[:, l, :], dtype=np.float32) for l in layers}
        res = {"counts": {}, "per_layer": []}
        for la in ["en", "sl"]:
            for k in ["harm", "harmless"]:
                for ro in ["CONSTRUCT", "SCORE"]:
                    s = idx[(idx.lang == la) & (idx.kind == k) & (idx.role == ro)]
                    res["counts"][f"{la}_{k}_{ro}"] = s.end.value_counts().head(4).to_dict()
        for l in layers:
            rec = {"layer": l}
            dirs = {}
            for la in ["en", "sl"]:
                m_ = lambda k, ro, e: ((idx.lang == la) & (idx.kind == k) & (idx.role == ro) & (idx.end == e)).values
                dirs[la] = XS[l][m_("harm", "CONSTRUCT", "?")].mean(0) - XS[l][m_("harmless", "CONSTRUCT", "?")].mean(0)
                fmt = XS[l][m_("harmless", "CONSTRUCT", "?")].mean(0) - XS[l][m_("harmless", "CONSTRUCT", ".")].mean(0)
                dirs[f"fmt_{la}"] = fmt
            r = (dirs["en"] + dirs["sl"]) / 2
            r = r / np.linalg.norm(r)
            for la in ["en", "sl"]:
                m_ = lambda k, e: ((idx.lang == la) & (idx.kind == k) & (idx.role == "SCORE") & (idx.end == e)).values
                h, b = XS[l][m_("harm", "?")] @ r, XS[l][m_("harmless", "?")] @ r
                rec[f"dprime_{la}_matched"] = dp(h, b)
                rec[f"n_{la}"] = [int(len(h)), int(len(b))]
                # original (unmatched) pooled direction evaluated on the matched subset
                f = dirs[f"fmt_{la}"] / np.linalg.norm(dirs[f"fmt_{la}"])
                rec[f"cos_harm_vs_format_{la}"] = float(r @ f)
            res["per_layer"].append(rec)
            D[(m, l)] = (r, idx, XS[l])
        out[m] = res
    # bootstrap Delta d'SL (gb - pt), matched, at L_pt and at each model's own L; resample SCORE harm pairs and harmless items
    def boot(l_pt_m, l_gb_m, la):
        (rp, idxp, Xp), (rg, idxg, Xg) = D[("pt", l_pt_m)], D[("gb", l_gb_m)]
        sel = lambda idx_, k: np.where(((idx_.lang == la) & (idx_.kind == k) & (idx_.role == "SCORE") & (idx_.end == "?")).values)[0]
        hp, bp = Xp[sel(idxp, "harm")] @ rp, Xp[sel(idxp, "harmless")] @ rp
        hg, bg = Xg[sel(idxg, "harm")] @ rg, Xg[sel(idxg, "harmless")] @ rg
        assert len(hp) == len(hg) and len(bp) == len(bg)
        est = dp(hg, bg) - dp(hp, bp)
        bs = []
        for _ in range(2000):
            i = rng.integers(0, len(hp), len(hp)); j = rng.integers(0, len(bp), len(bp))
            bs.append(dp(hg[i], bg[j]) - dp(hp[i], bp[j]))
        return {"est": est, "ci": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))], "n_harm": int(len(hp)), "n_harmless": int(len(bp))}
    out["Delta_dprime_matched"] = {f"{la}_at_Lpt": boot(L_pt, L_pt, la) for la in ["en", "sl"]}
    out["Delta_dprime_matched"].update({f"{la}_at_ownL": boot(L_pt, L_gb, la) for la in ["en", "sl"]})
    (ROOT / "results/analysis").mkdir(parents=True, exist_ok=True)
    (ROOT / "results/analysis/punct_check.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out["Delta_dprime_matched"], indent=1))
    for m in ["pt", "gb"]:
        print(m, [(r["layer"], round(r["dprime_en_matched"], 2), round(r["dprime_sl_matched"], 2), round(r["cos_harm_vs_format_en"], 2))
                  for r in out[m]["per_layer"] if r["layer"] in (L_pt, L_gb) or r["layer"] % 6 == 0])


if __name__ == "__main__":
    main()
