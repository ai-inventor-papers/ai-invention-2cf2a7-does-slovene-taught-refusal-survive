#!/usr/bin/env python3
"""STEP 5 - machine-readable correction ledger for the iteration-4 paper draft.

5a flatten every source JSON into a (value -> file, json_path) index per artifact;
5b extract every decimal token from the audited scope (Framing, 'What we have learned' 1-3, Iteration 4, final
   'What we have learned'); 5c auto-match within the cited artifact (equal within half a unit of the last shown digit;
   ties broken by sentence/path token overlap); 5d resolve executor-written POINTERS (ledger_pointers.yaml);
5e assign SURVIVES / SHRINKS / REVERSES / UNTRACEABLE + attribution_ok; 5f counts by status and match method.
Unmatched or ambiguous tokens stay UNTRACEABLE (never force-matched).
"""
from __future__ import annotations

import bisect
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import yaml
from loguru import logger

from common import (EVAL2, EVAL3, EXP4, EXP9, EXP10, EXP11, EXP12, EXP13, EXP14, EXP15, PAPER, RES, REVIEW, WS, flatten,
                    get_path, read_json, rel, setup_logging, write_json)

ARTIFACTS = {"eval3": EVAL3, "exp14": EXP14, "exp15": EXP15, "exp13": EXP13, "exp12": EXP12, "exp11": EXP11,
             "exp10": EXP10, "exp9": EXP9, "eval2": EVAL2, "exp4": EXP4}
SCOPE = [(1, 10, "Framing"), (825, 896, "What we have learned (iterations 1-3)"), (897, 1339, "Iteration 4 + What we have learned")]
HEAD2ART = [("(Evaluation 3)", "eval3"), ("(Experiment 14)", "exp14"), ("(Experiment 15)", "exp15"),
            ("(Research)", "all"), ("Not executed", "exp13")]
NUM = re.compile(r"(?<![\w.])([-−+]?)(\d+\.\d+)(?![\d])")
STOP = {"the", "and", "of", "in", "a", "is", "to", "at", "on", "for", "with", "by", "as", "vs", "from", "ci", "95", "or"}


# ------------------------------------------------------------------ 5a index
def build_index() -> dict:
    idx = {}
    for art, root in ARTIFACTS.items():
        files = sorted(root.glob("results/*.json")) + sorted(root.glob("*.json"))
        vals, refs = [], []
        for p in files:
            if p.name.startswith(".") or p.stat().st_size > 30e6 or "method_out" in p.name or "eval_out" in p.name:
                continue
            try:
                d = json.loads(p.read_text())
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            for path, v in flatten(d):
                vals.append(v)
                refs.append((rel(p), path))
        o = np.argsort(vals, kind="stable")
        idx[art] = {"vals": [vals[i] for i in o], "refs": [refs[i] for i in o]}
        logger.info(f"index {art}: {len(vals)} numeric leaves from {len(files)} files")
    return idx


def lookup(idx: dict, art: str, target: float, tol: float) -> list[tuple[str, str, float]]:
    d = idx[art]
    lo = bisect.bisect_left(d["vals"], target - tol)
    hi = bisect.bisect_right(d["vals"], target + tol)
    return [(d["refs"][i][0], d["refs"][i][1], d["vals"][i]) for i in range(lo, min(hi, lo + 5000))]


# ------------------------------------------------------------------ 5b tokens
def tokens() -> list[dict]:
    lines = PAPER.read_text().splitlines()
    out = []
    cur_art, cur_sec = "all", ""
    for lo, hi, scope in SCOPE:
        cur_art = "all"
        for ln in range(lo, min(hi, len(lines)) + 1):
            s = lines[ln - 1]
            if s.startswith("#"):
                cur_sec = s.strip("# ").strip()
                if s.startswith("## ") or s.startswith("# "):
                    cur_art = next((a for h, a in HEAD2ART if h in s), "all")
            for mt in NUM.finditer(s):
                sign, body = mt.group(1).replace("−", "-"), mt.group(2)
                pre = s[max(0, mt.start() - 12):mt.start()]
                if re.search(r"(Table|Figure|iter|Iteration|Artifact|v|A|#)\s*$", pre) or re.search(r"\d\.\d+\.\d", s[mt.start():mt.end() + 2]):
                    continue
                val = float(sign + body) if sign == "-" else float(body)
                dec = len(body.split(".")[1])
                opens = s[:mt.start()].count("[") - s[:mt.start()].count("]")
                post = s[mt.end():mt.end() + 3]
                out.append({"line": ln, "scope": scope, "section": cur_sec, "cited_artifact": cur_art, "token": mt.group(0),
                            "value": val, "decimals": dec, "kind": "ci_bound" if opens > 0 else "point",
                            "percent": post.strip().startswith(("%", "pp")),
                            "sentence": _sentence(s, mt.start())})
    return out


def _sentence(s: str, pos: int) -> str:
    a = max(s.rfind(". ", 0, pos), s.rfind("| ", 0, pos), 0)
    b = s.find(". ", pos)
    return s[a:b if b > 0 else len(s)].strip(" .|")[:300]


def _ctx_tokens(text: str) -> set[str]:
    t = re.split(r"[^A-Za-z0-9_]+", text.lower())
    out = set()
    for w in t:
        if w and w not in STOP and not w.replace(".", "").isdigit():
            out.add(w)
            out.update(w.split("_"))
    return out - {""}


# ------------------------------------------------------------------ 5c auto-match
def auto_match(idx: dict, tk: dict) -> dict:
    tol = 0.5 * 10 ** (-tk["decimals"]) + 1e-12
    targets = [tk["value"]] + ([tk["value"] / 100] if tk["percent"] else [])
    arts = [tk["cited_artifact"]] if tk["cited_artifact"] in idx else list(idx)
    cands = []
    for a in arts:
        for t in targets:
            cands += [(a, *c) for c in lookup(idx, a, t, tol / (100 if t != tk["value"] else 1))]
    method, attribution_ok = None, True
    if not cands and tk["cited_artifact"] in idx:  # try other artifacts -> attribution flag
        for a in idx:
            if a == tk["cited_artifact"]:
                continue
            for t in targets:
                cands += [(a, *c) for c in lookup(idx, a, t, tol / (100 if t != tk["value"] else 1))]
        if cands:
            attribution_ok = False
    if not cands:
        return {"match_method": "unmatched", "status": "UNTRACEABLE", "n_candidates": 0, "attribution_ok": None}
    uniq = {(c[1], c[2]) for c in cands}
    ctx = _ctx_tokens(tk["sentence"] + " " + tk["section"])
    if len(uniq) == 1:
        a, f, p, v = cands[0]
        method = "auto-unique"
    else:
        scored = sorted(((len(ctx & _ctx_tokens(c[2])), c) for c in cands), key=lambda x: -x[0])
        best = scored[0][0]
        top = {(c[1], c[2]) for s, c in scored if s == best}
        if best >= 2 and len(top) == 1:
            a, f, p, v = scored[0][1]
            method = "auto-context"
        elif best >= 2 and len({round(c[3], 9) for s, c in scored if s == best}) == 1:
            a, f, p, v = scored[0][1]
            method = "auto-context (duplicate paths, same value)"
        else:
            return {"match_method": "ambiguous", "status": "UNTRACEABLE", "n_candidates": len(uniq),
                    "attribution_ok": None, "note": "several JSON leaves match within rounding and context does not single one out"}
    method = method + ("" if attribution_ok else " (other artifact)")
    return {"match_method": method, "status": "SURVIVES", "verified_value": v, "source_artifact": a, "source_file": f,
            "json_path": p, "n_candidates": len(uniq), "attribution_ok": attribution_ok}


# ------------------------------------------------------------------ 5d/5e pointers
def status_of(paper: float, verified: float, dec: int, ci: list | None, paper_ci_excl0: bool | None) -> str:
    tol = 0.5 * 10 ** (-dec) + 1e-9
    if abs(paper - verified) <= tol:
        st = "SURVIVES"
    elif np.sign(paper) != np.sign(verified) and abs(verified) > tol:
        return "REVERSES"
    elif abs(verified) < abs(paper):
        st = "SHRINKS"
    else:
        st = "SURVIVES (verified larger; paper value not reproduced to shown precision)"
    if ci and None not in ci and paper_ci_excl0 and (ci[0] <= 0 <= ci[1]):
        st = "SHRINKS"
    return st


def resolve_pointers(ceiling: dict | None) -> list[dict]:
    spec = yaml.safe_load((WS / "ledger_pointers.yaml").read_text())["pointers"]
    lines = PAPER.read_text().splitlines()
    out = []
    for pt in spec:
        root = ARTIFACTS.get(pt["source"])
        f = root / pt["file"] if root else None
        rec = {"claim_id": pt["id"], "line": pt["line"], "paper_token": pt["token"], "cited_artifact": pt["cited"],
               "source_artifact": pt["source"], "source_file": rel(f) if f else None, "json_path": pt["path"],
               "match_method": "pointer", "note": pt.get("note", "")}
        tok = pt["token"]
        pv = float(tok.replace("+", ""))
        dec = len(tok.split(".")[1]) if "." in tok else 0
        if pt["line"]:
            s = lines[pt["line"] - 1]
            rec["paper_sentence"] = _sentence(s, max(0, s.find(tok)))
            rec["token_found_on_line"] = tok in s
        else:
            rec["paper_sentence"] = "(named by the blocking review; not located on a single line of the audited scope)"
            rec["token_found_on_line"] = None
        rec["paper_value"] = pv
        if f is None or not f.exists():
            rec.update(status="UNTRACEABLE", verified_value=None, attribution_ok=None)
            out.append(rec)
            continue
        d = read_json(f)
        try:
            if pt["path"] == "AUTO":
                hits = [(p, v) for p, v in flatten(d) if abs(v - pv) <= 0.5 * 10 ** (-dec) + 1e-9]
                if not hits:
                    raise KeyError("value not in file")
                rec["json_path"], val = hits[0]
                rec["n_auto_hits_in_file"] = len(hits)
            else:
                val = float(get_path(d, pt["path"]))
        except (KeyError, IndexError, TypeError, ValueError) as e:
            rec.update(status="UNTRACEABLE", verified_value=None, attribution_ok=None, error=str(e))
            out.append(rec)
            continue
        ci = None
        if pt.get("ci_path"):
            try:
                ci = [float(x) for x in get_path(d, pt["ci_path"])]
            except (KeyError, TypeError, ValueError):
                ci = None
        rec["verified_value"], rec["verified_ci95"] = val, ci
        rec["attribution_ok"] = pt["source"] == pt["cited"]
        rec["status"] = status_of(pv, val, dec, ci, None)
        rule = pt.get("rule")
        if rule == "mde_is_G3_not_G3_edit":
            rec["verified_G3_edit_mde"] = get_path(d, "headline/R/RAW/G3_edit/mde")
            rec["verified_abs_G3_edit_bound_90"] = get_path(d, "verdict/abs_G3_edit_bound_90")
            rec["note"] += (" | this sentence attributes MDE 0.42 to G3 (correct); G3_edit's own MDE is "
                            f"{rec['verified_G3_edit_mde']:.2f} and its 90% bound {rec['verified_abs_G3_edit_bound_90']:.2f}")
        elif rule == "parallel_curves_claim":
            bg = get_path(d, "headline/R/per_model/gemma_it/b")
            bs = get_path(d, "headline/R/per_model/gams3_it/b")
            rec["verified_b_gemma"], rec["verified_b_gams"] = bg, bs
            rec["status"] = "REVERSES"
            rec["note"] = ("'parallel-curve geometry' is not established: b_GaMS CI95 " + json.dumps([round(x, 2) for x in bs["ci95"]])
                           + " excludes 1 and no b_diff CI was saved; replace with the two slope CIs")
        elif rule == "not_highest_edited_Sp":
            c = pt["comparator"]
            cv = float(get_path(read_json(ARTIFACTS[c["source"]] / c["file"]), c["path"]))
            rec["comparator_value"], rec["comparator_ref"] = cv, f"{c['source']}::{c['path']}"
            rec["status"] = "REVERSES" if cv > val else rec["status"]
            rec["note"] = f"'best validation numbers in the study' is false: exp14 GaMS-SL edited Sp {cv:.2f} > {val:.2f}"
        elif rule == "claim_edit_spans_zero_everywhere":
            rec["status"] = "SURVIVES" if abs(pv - val) < 0.006 else rec["status"]
            rec["claim_reversed"] = "'G3_edit spans zero in every body under every readout'"
            rec["claim_status"] = "REVERSES" if ci and (ci[1] < 0 or ci[0] > 0) else "SURVIVES"
            rec["note"] = "value survives; the paper's blanket claim that G3_edit spans zero everywhere REVERSES (this CI excludes 0)"
        elif rule == "claim_negative_under_every_judge":
            rec["claim_status"] = "REVERSES" if val > 0 else "SURVIVES"
            rec["note"] = "'negative under every judge' REVERSES: the archived Qwen3-14B G3 on exp8_A1 is positive"
        elif rule == "ceiling_verdict" and ceiling:
            rec["ceiling_verdict"] = ceiling.get("verdict")
            rec["FI_m"] = ceiling.get("fragility_index", {}).get("FI_m")
            rec["claim_status"] = "SHRINKS" if ceiling.get("verdict") in ("CEILING-ARTEFACT", "FRAGILE") else "SURVIVES"
            rec["note"] = f"value reproduces; the 'baseline offset' reading is {ceiling.get('verdict')} (FI_m={rec['FI_m']})"
        out.append(rec)
    return out


def main(ceiling: dict | None = None) -> dict:
    setup_logging("ledger")
    idx = build_index()
    toks = tokens()
    logger.info(f"{len(toks)} numeric tokens in scope")
    rows = []
    for i, tk in enumerate(toks):
        m = auto_match(idx, tk)
        rows.append({"claim_id": f"T{i:04d}", **tk, **m})
    ptr = resolve_pointers(ceiling)
    # placebo: shift every token by 7-13 units of its last shown digit and re-run the matcher -> chance match rate
    rng = np.random.default_rng(20260927)
    plac = Counter()
    for tk in toks:
        t2 = dict(tk)
        t2["value"] = tk["value"] + (1 if rng.random() < 0.5 else -1) * rng.integers(7, 14) * 10 ** (-tk["decimals"])
        plac[auto_match(idx, t2)["match_method"].split(" ")[0]] += 1
    # pointers override auto rows on the same line/token
    by_lt = {(r["line"], r["token"].replace("−", "-")): r for r in rows}
    for p in ptr:
        key = (p["line"], p["paper_token"])
        if key in by_lt:
            by_lt[key]["superseded_by_pointer"] = p["claim_id"]
    ledger = {"rows": rows, "pointers": ptr,
              "counts_by_status": dict(Counter(r["status"] for r in rows if "superseded_by_pointer" not in r)
                                       + Counter(p["status"].split(" ")[0] for p in ptr)),
              "counts_by_method": dict(Counter(r["match_method"] for r in rows if "superseded_by_pointer" not in r)
                                       + Counter(["pointer"] * len(ptr))),
              "attribution_errors": [p["claim_id"] for p in ptr if p.get("attribution_ok") is False]
              + [r["claim_id"] for r in rows if r.get("attribution_ok") is False and "superseded_by_pointer" not in r],
              "claim_level_reversals": [p["claim_id"] for p in ptr if p.get("claim_status") == "REVERSES" or p["status"] == "REVERSES"],
              "n_tokens": len(rows), "n_pointers": len(ptr),
              "placebo_shifted_tokens_match_methods": dict(plac),
              "placebo_auto_match_rate": (plac["auto-unique"] + plac["auto-context"]) / max(1, len(toks)),
              "caveat": ("auto-match equality is necessary, not sufficient: a SURVIVES by auto-unique/auto-context means a JSON "
                         "leaf in the cited artifact holds the same number to the shown precision; ambiguous and unmatched "
                         "tokens are UNTRACEABLE by default; claim-level verdicts are assessed only for pointer rows")}
    write_json(RES / "correction_ledger.json", ledger)
    with open(RES / "correction_ledger.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["claim_id", "line", "section", "cited_artifact", "token", "kind", "status", "match_method",
                    "verified_value", "source_file", "json_path", "attribution_ok", "claim_status", "note"])
        for p in ptr:
            w.writerow([p["claim_id"], p["line"], "pointer", p["cited_artifact"], p["paper_token"], "point", p["status"], "pointer",
                        p.get("verified_value"), p.get("source_file"), p.get("json_path"), p.get("attribution_ok"),
                        p.get("claim_status", ""), p.get("note", "")])
        for r in rows:
            w.writerow([r["claim_id"], r["line"], r["section"], r["cited_artifact"], r["token"], r["kind"], r["status"],
                        r["match_method"], r.get("verified_value"), r.get("source_file"), r.get("json_path"),
                        r.get("attribution_ok"), "", r.get("note", "")])
    logger.info(f"ledger: {ledger['counts_by_status']} | {ledger['counts_by_method']}")
    return ledger


if __name__ == "__main__":
    c = read_json(RES / "ceiling_sensitivity.json") if (RES / "ceiling_sensitivity.json").exists() else None
    main(c)
