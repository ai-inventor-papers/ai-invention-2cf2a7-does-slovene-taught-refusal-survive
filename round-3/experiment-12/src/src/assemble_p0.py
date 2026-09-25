#!/usr/bin/env python3
"""STEP 8: P0 table (re-runnable by the paper step). RQ1 = original-model FINAL refusal (reused from iter-2 exp5,
cited, not re-run); RQ2 = paired orig->edit refusal delta from this round's artifact 4 if its per-item files exist,
else PENDING; RQ3 = this artifact's capability gate; RQ4 = 'see artifact 3' with a path if found."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ITER2_EXP5, ITER3_GENART, RESULTS, read_jsonl, sha256_file  # noqa: E402


def rq1() -> dict:
    p = ITER2_EXP5 / "results" / "analysis_final.json"
    if not p.exists():
        return {"status": "MISSING", "path": str(p)}
    d = json.loads(p.read_text())["descriptives"]
    rows = {}
    for k, v in d.items():
        m, blk, arm = k.split("|")[:3]
        if blk.startswith("refuseu"):
            rows[k] = {"model": m, "block": blk, "arm": arm, "n": v["n"], "refusal_rate": v["refusal_rate"],
                       "wilson95": v.get("refusal_wilson95")}
    return {"status": "REUSED (iter-2 exp5 FINAL, judge-labelled)", "source": str(p), "sha256": sha256_file(p), "rows": rows}


def find_rq2() -> dict:
    """Artifact 4 per-item post-edit FINAL rows: any iter_3 workspace (not ours) with results/**/items*.jsonl that
    carries both an original and an edited condition and a refusal label."""
    cands = []
    for f in sorted(ITER3_GENART.glob("*/results/**/items*.jsonl")):
        if "gen_art_experiment_12" in str(f):
            continue
        cands.append(f)
    for f in cands:
        rows = read_jsonl(f)[:2000]
        if not rows:
            continue
        keys = set(rows[0])
        label = next((k for k in ("refusal", "refused", "judge_refusal", "label", "R") if k in keys), None)
        cond = next((k for k in ("cond", "condition", "arm") if k in keys), None)
        if label and cond:
            return {"status": "FOUND", "path": str(f), "label_field": label, "cond_field": cond, "n_rows_peek": len(rows)}
    return {"status": "PENDING", "searched": str(ITER3_GENART / "*/results/**/items*.jsonl"), "n_candidates": len(cands)}


def rq2_lexical_provisional() -> dict:
    """Artifact 4 (iter_3 exp11) final generations carry a lexical refusal marker ('lex'). Until its judge labels exist,
    compute a PROVISIONAL paired orig->edit (lambda 1) refusal delta per model x set x arm from that marker."""
    from scipy.stats import binomtest
    files = sorted(ITER3_GENART.glob("*/results/final/gens_*.jsonl"))
    files = [f for f in files if "gen_art_experiment_12" not in str(f)]
    if not files:
        return {"status": "PENDING"}
    by: dict = {}
    for f in files:
        for r in read_jsonl(f):
            if r.get("split") != "FINAL" or "lex" not in r:
                continue
            lam = float(r.get("lambda", 0) or 0)
            cond = "orig" if r.get("condition") == "orig" or lam == 0.0 else (f"edit_l{lam}" if r.get("condition") == "edit" else None)
            if cond is None:
                continue
            key = (r["model"], r.get("set"), r.get("arm"), str(r.get("is_harmful")))
            by.setdefault(key, {}).setdefault(cond, {})[r["item_id"]] = int(str(r["lex"]) in ("1", "True", "true"))
    out = {}
    for key, cc in sorted(by.items()):
        if "orig" not in cc or "edit_l1.0" not in cc:
            continue
        ids = sorted(set(cc["orig"]) & set(cc["edit_l1.0"]))
        if len(ids) < 20:
            continue
        a = [cc["orig"][i] for i in ids]
        b = [cc["edit_l1.0"][i] for i in ids]
        n10 = sum(1 for x, y in zip(a, b) if x == 1 and y == 0)
        n01 = sum(1 for x, y in zip(a, b) if x == 0 and y == 1)
        p = binomtest(min(n10, n01), n10 + n01, 0.5).pvalue if n10 + n01 else 1.0
        ra, rb = sum(a) / len(a), sum(b) / len(b)
        out["|".join(key)] = {"n": len(ids), "lex_refusal_orig": ra, "lex_refusal_edit": rb, "delta": rb - ra,
                              "mcnemar_p": p, "relative_cut": (1 - rb / ra) if ra else None}
    return {"status": "PROVISIONAL (lexical refusal marker from artifact 4 final generations; its judge labels were not yet available)",
            "files": [str(f) for f in files], "deltas": out}


def rq2_delta(info: dict) -> dict:
    if info["status"] != "FOUND":
        lex = rq2_lexical_provisional()
        return {**info, "lexical_provisional": lex}
    from scipy.stats import binomtest
    rows = read_jsonl(Path(info["path"]))
    lab, cf = info["label_field"], info["cond_field"]
    by = {}
    for r in rows:
        key = (r.get("model"), r.get("lang") or r.get("language"), r.get("item_id") or r.get("pair_id"))
        by.setdefault(key[:2], {}).setdefault(r[cf], {})[key[2]] = float(bool(r[lab])) if not isinstance(r[lab], (int, float)) else float(r[lab])
    out = {}
    for (m, lang), conds in by.items():
        orig = next((c for c in conds if "orig" in str(c).lower()), None)
        for c in conds:
            if c == orig or orig is None:
                continue
            ids = sorted(set(conds[orig]) & set(conds[c]))
            a = [conds[orig][i] for i in ids]
            b = [conds[c][i] for i in ids]
            n10 = sum(1 for x, y in zip(a, b) if x == 1 and y == 0)
            n01 = sum(1 for x, y in zip(a, b) if x == 0 and y == 1)
            p = binomtest(min(n10, n01), n10 + n01, 0.5).pvalue if n10 + n01 else 1.0
            out[f"{m}|{lang}|{c}"] = {"n": len(ids), "refusal_orig": sum(a) / max(1, len(a)), "refusal_edit": sum(b) / max(1, len(b)),
                                      "delta": (sum(b) - sum(a)) / max(1, len(a)), "mcnemar_p": p,
                                      "en_cut_relative": (1 - sum(b) / sum(a)) if sum(a) else None}
    return {**info, "deltas": out}


def main() -> None:
    gates = json.loads((RESULTS / "gates.json").read_text()) if (RESULTS / "gates.json").exists() else {}
    art3 = sorted(str(p.parent) for p in ITER3_GENART.glob("*/README.md") if "gen_art_experiment_12" not in str(p))
    table = {"RQ1_original_refusal": rq1(), "RQ2_post_edit_refusal": rq2_delta(find_rq2()),
             "RQ3_capability_gate": {"source": str(RESULTS / "gates.json"),
                                     "verdicts": {m: {c: g.get("verdict") for c, g in gm.items()} for m, gm in gates.get("gates", gates).items()
                                                  if isinstance(gm, dict)}},
             "RQ4": {"status": "see artifact 3", "iter3_workspaces_with_README": art3},
             "EN_refusal_cut_gate": "requires artifact 2/4 post-edit refusal rows; PENDING unless RQ2 FOUND (en_cut_relative >= 0.50)"}
    (RESULTS / "p0_table.json").write_text(json.dumps(table, indent=2, default=float))
    md = ["# P0 table", "", "## RQ1 original-model FINAL refusal (reused from iter-2 exp5)", "",
          "| model | block | arm | n | refusal | Wilson 95% |", "|---|---|---|---|---|---|"]
    for k, v in table["RQ1_original_refusal"].get("rows", {}).items():
        w = v["wilson95"] or [float("nan")] * 2
        md.append(f"| {v['model']} | {v['block']} | {v['arm']} | {v['n']} | {v['refusal_rate']:.3f} | [{w[0]:.3f}, {w[1]:.3f}] |")
    md += ["", f"## RQ2 post-edit refusal: {table['RQ2_post_edit_refusal']['status']}", ""]
    lx = table["RQ2_post_edit_refusal"].get("lexical_provisional", {})
    if lx.get("deltas"):
        md += [f"PROVISIONAL, lexical marker only: {lx['status']}", "", "| model / set / arm / is_harmful | n | orig | edit (λ1) | Δ | rel. cut | McNemar p |", "|---|---|---|---|---|---|---|"]
        for k, v in lx["deltas"].items():
            rc = f"{v['relative_cut']:.2f}" if v["relative_cut"] is not None else "–"
            md.append(f"| {k} | {v['n']} | {v['lex_refusal_orig']:.3f} | {v['lex_refusal_edit']:.3f} | {v['delta']:+.3f} | {rc} | {v['mcnemar_p']:.2g} |")
    for k, v in table["RQ2_post_edit_refusal"].get("deltas", {}).items():
        md.append(f"- {k}: orig {v['refusal_orig']:.3f} -> edit {v['refusal_edit']:.3f} (McNemar p={v['mcnemar_p']:.3g}, n={v['n']})")
    md += ["", "## RQ3 capability gate (this artifact)", ""]
    for m, cc in table["RQ3_capability_gate"]["verdicts"].items():
        md.append(f"- {m}: " + ", ".join(f"{c}={v}" for c, v in cc.items()))
    md += ["", "## RQ4: see artifact 3", ""]
    (RESULTS / "p0_table.md").write_text("\n".join(md) + "\n")
    print(f"p0 table written; RQ2 status {table['RQ2_post_edit_refusal']['status']}")


if __name__ == "__main__":
    main()
