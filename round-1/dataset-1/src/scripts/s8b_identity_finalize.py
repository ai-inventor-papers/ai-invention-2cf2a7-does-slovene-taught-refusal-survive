#!/usr/bin/env python3
"""Step 8b ($0, GPU+CPU): identity set finalisation. (1) dedup candidates vs GaMS-Nemotron-Chat EN prompts (exact or
>50% n-gram overlap, n = min(8, #words); short items are therefore checked for verbatim containment), and within-set
char-5-gram Jaccard > 0.8; (2) select 120 identity items balanced 20/facet (real OASST2 first, then generated in sha1
order) + 120 controls matched 1:1 on word count (+-30%); (3) gemini-2.5-flash EN->SL (informal ti-form), gpt-4.1-mini back-translation, chrF; < 40 -> one
retry -> drop and refill from the reserve pool; (4) SL items re-checked vs Nemotron SL prompts (esp. the 694
identity=True rows); (5) split 40 DEV / 80 FINAL per type by sha1(item_id)."""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.common import OUT, WORK, setup_logging, sha1_hex, sha1_int, sha256_text  # noqa: E402

setup_logging("s8b_identity_finalize")
FACETS = ["name", "creator_company", "model_family", "who_made_you", "origin_language", "comparison"]


def words(t: str) -> list[str]:
    return re.findall(r"\w+", t.lower())


class NgramIndex:
    """hash sets of word n-grams (n=1..8) of a prompt collection, plus per-prompt sets for a small reference subset."""

    def __init__(self, texts: list[str], ns: set[int]):
        self.sets = {n: set() for n in ns}
        self.exact = {" ".join(words(t)) for t in texts}
        for t in texts:
            w = words(t)
            for n in ns:
                for i in range(len(w) - n + 1):
                    self.sets[n].add(hash(" ".join(w[i:i + n])))

    def share(self, t: str) -> float:
        w = words(t)
        if not w:
            return 0.0
        n = min(8, len(w))
        g = [hash(" ".join(w[i:i + n])) for i in range(len(w) - n + 1)]
        return float(np.mean([x in self.sets[n] for x in g])) if g else 0.0

    def is_exact(self, t: str) -> bool:
        return " ".join(words(t)) in self.exact


def max_overlap_vs(t: str, refs: list[list[str]]) -> float:
    w = words(t)
    n = min(8, len(w))
    if n == 0:
        return 0.0
    g = {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}
    best = 0.0
    for rw in refs:
        rg = {" ".join(rw[i:i + n]) for i in range(len(rw) - n + 1)}
        if rg:
            best = max(best, len(g & rg) / len(g))
    return round(best, 4)


def char5(t: str) -> set:
    t = re.sub(r"\s+", " ", t.lower())
    return {t[i:i + 5] for i in range(max(len(t) - 4, 1))}


@logger.catch(reraise=True)
def main() -> None:
    import asyncio
    from lib.api_mt import api_round_trip
    from lib.common import LABELS
    c = pd.read_parquet(WORK / "identity_candidates.parquet")
    nem = pd.read_parquet(WORK / "nemotron_prompts.parquet")
    ns = set(range(1, 9))
    idx_en = NgramIndex(nem[nem.language == "en"].user.tolist(), ns)
    c["nem_en_overlap"] = c.text.map(idx_en.share)
    c["nem_en_exact"] = c.text.map(idx_en.is_exact)
    n0 = len(c)
    c = c[~c.nem_en_exact & (c.nem_en_overlap <= 0.5)].copy()
    logger.info(f"EN Nemotron dedup: {n0} -> {len(c)}")
    # within-set near-dup (keep real first, then sha1 order)
    c["item_id"] = "identity_" + c.kind + "_" + c.text.map(lambda t: sha1_hex(t)[:12])
    c["prio"] = (c.source != "oasst_real").astype(int)
    c = c.assign(h=c.item_id.map(sha1_int)).sort_values(["prio", "h"]).reset_index(drop=True)
    keep, grams = [], []
    for t in c.text:
        g = char5(t)
        dup = any(len(g & o) / max(len(g | o), 1) > 0.8 for o in grams)
        keep.append(not dup)
        if not dup:
            grams.append(g)
    c = c[keep].reset_index(drop=True)
    c["n_words"] = c.text.map(lambda t: len(t.split()))
    logger.info(f"after near-dup: {c.groupby(['kind', 'facet']).size().to_dict()}")
    # real identity seeds are mapped to facets; generic 'who are you' / 'are you chatgpt' seeds go to name / comparison pools
    c.loc[(c.kind == "identity") & (c.facet == "who_are_you"), "facet"] = "name"
    c.loc[(c.kind == "identity") & (c.facet == "comparison_real"), "facet"] = "comparison_real"
    # MT all candidates once (cheap) -> round-trip chrF, drop < 40 after one retry
    recs = asyncio.run(api_round_trip(c.item_id.tolist(), c.text.tolist(), "D_identity_mt", LABELS / "identity_mt",
                                      "Use natural Slovene in the informal ti-form (tikanje), as a real user would type it to a chatbot."))
    c = pd.concat([c, pd.DataFrame([recs[k] for k in c.item_id])], axis=1)
    c["mt_keep"] = (c.bt_chrf >= 40) & ~c.mt_empty
    idx_sl = NgramIndex(nem[nem.language == "sl"].user.tolist(), ns)
    c["nem_sl_overlap"] = c.prompt_sl.map(idx_sl.share)
    c["nem_sl_exact"] = c.prompt_sl.map(idx_sl.is_exact)
    id_refs_sl = [words(t) for t in nem[(nem.language == "sl") & nem.identity].user]
    c["max_nemotron_identity_8gram_overlap_sl"] = c.prompt_sl.map(lambda t: max_overlap_vs(t, id_refs_sl))
    ok = c.mt_keep & ~c.nem_sl_exact & (c.nem_sl_overlap <= 0.5)
    logger.info(f"MT keep {c.mt_keep.sum()}/{len(c)}; SL-dedup ok {ok.sum()}")
    pool = c[ok].copy()
    # ---- select 120 identity balanced 20/facet ----
    sel = []
    for f in FACETS:
        g = pool[(pool.kind == "identity") & (pool.facet == f)].sort_values(["prio", "h"])
        if f == "comparison":  # keep GaMS-first / Gemma-first balanced
            a = g[g.comparison_order == "GaMS-first"].head(10); b = g[g.comparison_order == "Gemma-first"].head(10)
            g = pd.concat([a, b])
        sel.append(g.head(20).assign(facet_final=f))
    ident = pd.concat(sel)
    short = 120 - len(ident)
    if short > 0:  # refill from any remaining identity candidates (logged)
        rest = pool[(pool.kind == "identity") & ~pool.item_id.isin(ident.item_id) & (pool.facet != "comparison")]
        ident = pd.concat([ident, rest.sort_values(["prio", "h"]).head(short).assign(facet_final=lambda d: d.facet)])
        logger.warning(f"identity refill {short}")
    # ---- controls matched 1:1 on word count (+-30%) ----
    ctrl_pool = pool[pool.kind == "control"].sort_values(["prio", "h"]).copy()
    used, match = set(), []
    for _, r in ident.iterrows():
        cand = ctrl_pool[~ctrl_pool.item_id.isin(used)]
        within = cand[(cand.n_words >= 0.7 * r.n_words) & (cand.n_words <= 1.3 * r.n_words)]
        pick = (within if len(within) else cand).assign(d=lambda d: (d.n_words - r.n_words).abs()).sort_values(["d", "prio", "h"]).iloc[0]
        used.add(pick.item_id)
        match.append((r.item_id, pick.item_id, bool(len(within))))
    ctrl = ctrl_pool.set_index("item_id").loc[[m[1] for m in match]].reset_index()
    ctrl["matched_pair_id"] = [m[0] for m in match]
    ctrl["length_matched_30pct"] = [m[2] for m in match]
    ident["matched_pair_id"] = [m[1] for m in match]
    ident["length_matched_30pct"] = [m[2] for m in match]
    ctrl["facet_final"] = "control_personal"
    fin = pd.concat([ident, ctrl], ignore_index=True)
    fin["fold"] = "identity_confirm_FINAL"
    for k, g in fin.groupby("kind"):
        order = sorted(g.item_id, key=sha1_int)
        fin.loc[fin.item_id.isin(order[:40]), "fold"] = "identity_confirm_DEV"
    fin = fin.drop(columns=["h", "d"], errors="ignore")
    fin.to_parquet(WORK / "identity_final.parquet")
    c.drop(columns=["h"]).to_parquet(WORK / "identity_candidates_scored.parquet")
    ids = {"note": "RESERVED identity-confirmation items; must NOT be used in iter-1 screens. Sibling screens must verify disjointness.",
           "identity_DEV": sorted(fin[(fin.kind == "identity") & (fin.fold == "identity_confirm_DEV")].item_id),
           "identity_FINAL": sorted(fin[(fin.kind == "identity") & (fin.fold == "identity_confirm_FINAL")].item_id),
           "control_DEV": sorted(fin[(fin.kind == "control") & (fin.fold == "identity_confirm_DEV")].item_id),
           "control_FINAL": sorted(fin[(fin.kind == "control") & (fin.fold == "identity_confirm_FINAL")].item_id),
           "texts_en_sha256": sha256_text("\n".join(sorted(fin.text)))}
    ids["sha256_all_ids"] = sha256_text("\n".join(sorted(fin.item_id)))
    (OUT / "identity_items_ids.json").write_text(json.dumps(ids, indent=1))
    rep = {"n_candidates_generated": int(n0), "final_counts": fin.groupby(["kind", "fold"]).size().astype(int).to_dict(),
           "facet_counts": fin[fin.kind == "identity"].facet_final.value_counts().to_dict(),
           "source_counts": fin.groupby(["kind", "source"]).size().astype(int).to_dict(),
           "length_matched_share": float(fin.length_matched_30pct.mean()),
           "bt_chrf_median": float(fin.bt_chrf.median()), "bt_chrf_min": float(fin.bt_chrf.min()),
           "max_nem_en_overlap": float(fin.nem_en_overlap.max()), "max_nem_sl_overlap": float(fin.nem_sl_overlap.max())}
    rep = {k: ({"|".join(map(str, kk)) if isinstance(kk, tuple) else kk: v for kk, v in val.items()} if isinstance(val, dict) else val) for k, val in rep.items()}
    (OUT / "identity_report.json").write_text(json.dumps(rep, indent=1))
    logger.info(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
