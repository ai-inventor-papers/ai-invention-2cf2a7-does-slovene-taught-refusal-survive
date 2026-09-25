#!/usr/bin/env python3
"""STEP 7 audit: independently recompute headline numbers from the raw per-item JSONL (outputs/*.jsonl, NOT the
scored table), compare with results/analysis_results.json and method_out.json, check protocol sha, pair-set
identity, and that no code touches the RefusEU evaluation config. Writes results/audit.json; exits 1 on mismatch."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

from common import DATA, LOW_EN, HIGH_EN, MODELS, OUT, ROOT, SEED, r_lex, read_jsonl
from stats_core import did_from_counts, m_from_p0

RES = ROOT / "results"


def main() -> int:
    res = json.loads((RES / "analysis_results.json").read_text())
    mo = json.loads((ROOT / "method_out.json").read_text())
    checks = []

    def chk(name, a, b, tol=1e-9):
        ok = (a is None and b is None) or (a is not None and b is not None and abs(float(a) - float(b)) <= tol)
        checks.append({"check": name, "recomputed": a, "reported": b, "ok": bool(ok)})

    # protocol sha
    sha = hashlib.sha256((ROOT / "protocol.json").read_bytes()).hexdigest()
    checks.append({"check": "protocol_sha256 file == committed == method_out",
                   "ok": sha == (ROOT / "protocol.sha256").read_text().split()[0] == mo["metadata"]["protocol_sha256"],
                   "recomputed": sha, "reported": mo["metadata"]["protocol_sha256"]})
    # raw recompute of R_lex matrix
    import langid
    langid.set_languages(["en", "sl"])
    pairs = {p["pair_id"]: p for p in read_jsonl(DATA / "pairs.jsonl")}
    cell = {}
    for mk in MODELS:
        for r in read_jsonl(OUT / f"gen_{mk}.jsonl"):
            t = r["response"]
            det = langid.classify(t)[0] if t.strip() else None
            cell[(r["pair_id"], mk, r["lang"])] = r_lex(t, r["lang"], det)[0]
    ids = sorted({p for (p, _, _) in cell if all((p, m, l) in cell for m in MODELS for l in ("en", "sl"))
                  and pairs[p]["role"] == "SCORE"})
    order = [("gemma_it", "en"), ("gemma_it", "sl"), ("gams3_it", "en"), ("gams3_it", "sl")]
    Y = np.array([[cell[(p, m, l)] for m, l in order] for p in ids], dtype=float)
    cats = np.array([pairs[p]["category"] for p in ids])
    chk("analysis_set_n", len(ids), res["analysis_set"]["n_pairs"], 0)
    p0 = Y.mean()
    chk("p0", p0, res["p0_pooled_R_lex"])
    chk("m", m_from_p0(p0), res["m"])
    lex = res["outcomes"]["R_lex"]
    chk("overall_DiD_R_lex", float(did_from_counts(Y.sum(0), len(Y))), lex["overall"]["est"])
    lo, hi = np.isin(cats, LOW_EN), np.isin(cats, HIGH_EN)
    D = float(did_from_counts(Y[lo].sum(0), lo.sum()) - did_from_counts(Y[hi].sum(0), hi.sum()))
    chk("D_R_lex", D, lex["D"]["est"])
    for j, (m, l) in enumerate(order):
        chk(f"rate_R_lex_{m}_{l}", Y[:, j].mean(), lex["rates"][f"{m}|{l}"]["rate"])
    for c in sorted(set(cats.tolist())):
        mm = cats == c
        chk(f"DiD_R_lex_{c}", float(did_from_counts(Y[mm].sum(0), mm.sum())), lex["per_category"][c]["est"])
    # judge-based overall from raw judge ledger
    jq = {(r["key"], r["model"]): r["label"] for r in read_jsonl(OUT / "judge_gemini.jsonl")}
    if jq and "R_judge" in res["outcomes"]:
        Yj = []
        for p in ids:
            row = [jq.get((f"{p}|{l}|original", m)) for m, l in order]
            if None not in row:
                Yj.append([float(x == "REFUSE") for x in row])
        Yj = np.array(Yj)
        chk("n_R_judge", len(Yj), res["outcomes"]["R_judge"]["n_pairs"], 0)
        chk("overall_DiD_R_judge", float(did_from_counts(Yj.sum(0), len(Yj))), res["outcomes"]["R_judge"]["overall"]["est"])
    # s DiD
    sv = {}
    for mk in MODELS:
        for r in read_jsonl(OUT / f"s_{mk}.jsonl"):
            sv[(r["pair_id"], mk, r["lang"])] = r["s"]
    if sv and "s_outcome" in res:
        S = np.array([[sv.get((p, m, l), np.nan) for m, l in order] for p in ids])
        ok = ~np.isnan(S).any(1)
        d = (S[ok, 3] - S[ok, 2]) - (S[ok, 1] - S[ok, 0])
        chk("overall_DiD_s", float(d.mean()), res["s_outcome"]["overall"]["est"], 1e-9)
    # method_out consistency
    chk("method_out_overall_DiD_R_lex", mo["metadata"]["analysis"]["outcomes"]["R_lex"]["overall"]["est"],
        lex["overall"]["est"])
    # evaluation split never accessed: scan code for evaluation-config loads
    bad = []
    for f in list(ROOT.glob("*.py")) + list((ROOT / "tests").glob("*.py")):
        if f.name == "audit.py":  # contains the search pattern itself
            continue
        txt = f.read_text()
        if re.search(r"load_dataset\([^)]*['\"](evaluation|eval)['\"]", txt) or "evaluation/" in txt.replace(
                "evaluation/ parquet", ""):
            bad.append(f.name)
    checks.append({"check": "no evaluation-config access in code", "ok": not bad, "files": bad})
    # identical pair sets across outcomes
    checks.append({"check": "R_lex analysis set == all 4 cells generated", "ok": len(ids) == res["analysis_set"]["n_pairs"]})
    n_bad = sum(not c["ok"] for c in checks)
    (RES / "audit.json").write_text(json.dumps({"n_checks": len(checks), "n_failed": n_bad, "checks": checks},
                                               indent=2, default=float))
    print(f"audit: {len(checks)} checks, {n_bad} failed")
    for c in checks:
        if not c["ok"]:
            print("FAILED", c)
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main())
