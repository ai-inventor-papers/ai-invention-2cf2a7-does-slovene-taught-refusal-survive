#!/usr/bin/env python3
"""STEP 7: independent re-derivation of every headline number from gens/ + labels/ (plain python, no stats.py, no
analyze.py code), compared against results/analysis.json -> results/audit.json. Also prints 10 random rows per system."""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import DATA, GENS, LABELS, RESULTS, SYSTEMS  # noqa: E402


def jl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def kap(x: list[int], y: list[int]) -> float:
    n = len(x)
    po = sum(1 for a, b in zip(x, y) if a == b) / n
    px, py = sum(x) / n, sum(y) / n
    pe = px * py + (1 - px) * (1 - py)
    return (po - pe) / (1 - pe)


def main() -> None:
    A = json.loads((RESULTS / "analysis.json").read_text())
    items = {r["item_id"]: r for r in jl(DATA / "items.jsonl")}
    gen = {}
    for s in SYSTEMS:
        for r in jl(GENS / f"{s}.jsonl"):
            gen[r["key"]] = r
    lab_file = {"gemini": "refusal_gemini.jsonl", "local": "refusal_local.jsonl"}.get(A.get("readout_key"), "")
    lab = {r["key"]: r["label"] for r in jl(LABELS / lab_file)} if lab_file else {}

    def y(s, set_, arm, cond="k0"):
        out = {}
        for k, g in gen.items():
            if g["system"] == s and g["set"] == set_ and g["lang_arm"] == arm and g["condition"] == cond:
                if g.get("blocked_generation"):
                    continue
                L = lab.get(k)
                if L in ("REFUSE", "PARTIAL", "COMPLY"):
                    out[g["item_id"]] = 1 if L == "REFUSE" else 0
        return out

    checks = []

    def check(name, mine, theirs, tol=1e-9):
        ok = theirs is not None and abs(mine - theirs) <= tol
        checks.append({"name": name, "audit": mine, "analysis": theirs, "agree": bool(ok)})

    for set_, arm, blk in (("H", "en_orig", "H_en_orig"), ("H", "sl_mt", "H_sl_mt"), ("H", "en_bt", "H_en_bt")):
        T = A["T1"][blk]
        ys = {s: y(s, set_, arm) for s in ("gams", "gemma", "q14", "q235", "out")}
        core = sorted(set.intersection(*[set(ys[s]) for s in ("gams", "gemma", "q14", "q235")]))
        if len(core) < 20:
            check(f"{blk}.n_core(pending)", len(core), T.get("n_core"))
            continue
        v = {s: [ys[s][i] for i in core] for s in ("gams", "gemma", "q14", "q235")}
        check(f"{blk}.n_core", len(core), T["n_core"])
        check(f"{blk}.dk", kap(v["gams"], v["q235"]) - kap(v["gams"], v["gemma"]), T["dk"]["est"])
        check(f"{blk}.fpcal", kap(v["q14"], v["q235"]) - kap(v["q14"], v["gemma"]), T["fpcal_dk"]["est"])
        for s in v:
            check(f"{blk}.refusal_rate_core.{s}", sum(v[s]) / len(core), T["refusal_rate_core"][s])
        for a, b in (("gams", "q235"), ("gams", "gemma"), ("q14", "q235"), ("q14", "gemma")):
            key = f"{a}~{b}" if f"{a}~{b}" in T["pairwise_core"] else f"{b}~{a}"
            check(f"{blk}.kappa_core.{key}", kap(v[a], v[b]), T["pairwise_core"][key]["kappa"])
        ids = sorted(set(core) & set(ys["out"]))
        if len(ids) < 20 or "pairwise" not in T:
            continue
        w = {s: [ys[s][i] for i in ids] for s in ys}
        check(f"{blk}.n_out_subset", len(ids), T["n"])
        check(f"{blk}.t1b", kap(w["gams"], w["q235"]) - kap(w["gams"], w["out"]), T["t1b_dk_q235_minus_out"]["est"])
        key = "gams~out"
        check(f"{blk}.kappa.{key}", kap(w["gams"], w["out"]), T["pairwise"][key]["kappa"])
        if "t1d_side_taking" in T:
            D = [i for i in range(len(ids)) if w["q235"][i] != w["gemma"][i]]
            if D:
                check(f"{blk}.side.p_gams", sum(w["gams"][i] == w["q235"][i] for i in D) / len(D),
                      T["t1d_side_taking"]["p_gams_sides_q235"])
                check(f"{blk}.side.p_out", sum(w["out"][i] == w["q235"][i] for i in D) / len(D),
                      T["t1d_side_taking"]["p_out_sides_q235"])
    # retest ceiling
    a, b = y("q235", "H", "en_orig"), y("q235", "H", "en_orig", "k0_retest")
    ids = sorted(set(a) & set(b))
    if ids and len({a[i] for i in ids} | {b[i] for i in ids}) > 1:
        try:
            check("retest.kappa", kap([a[i] for i in ids], [b[i] for i in ids]), A["T1"]["retest_q235"].get("kappa"))
        except ZeroDivisionError:
            pass
    # T4 common refused set + flip rates
    r200 = [i for i, it in items.items() if it.get("r200")]
    for arm in ("en_orig", "sl_mt"):
        k0 = {s: y(s, "R", arm) for s in ("gams", "gemma", "q14")}
        CR = [i for i in r200 if all(k0[s].get(i) == 1 for s in k0)]
        if arm in A["T4"]:
            check(f"T4.{arm}.n_CR", len(CR), A["T4"][arm]["n_CR"])
            for s in ("gams", "gemma", "q14"):
                d = y(s, "R", arm, "pre_comply5")
                f = [1 - d[i] for i in CR if i in d]
                if f:
                    check(f"T4.{arm}.flip.{s}", sum(f) / len(f), A["T4"][arm][f"flip|{s}|pre_comply5|primary"]["p"])
    n_ok = sum(c["agree"] for c in checks)
    out = {"n_checks": len(checks), "n_agree": n_ok, "all_agree": n_ok == len(checks), "checks": checks}
    # spot print
    rnd = random.Random(20260924)
    spot = {}
    for s in SYSTEMS:
        ks = sorted(k for k, g in gen.items() if g["system"] == s and g["set"] != "ID")
        spot[s] = [{"key": k, "label": lab.get(k), "response": gen[k]["response"][:160]} for k in rnd.sample(ks, min(10, len(ks)))]
    out["spot_rows"] = spot
    reserved = json.loads((DATA / "items_manifest.json").read_text())["reserved_checks"]
    out["reserved_check"] = reserved
    out["readout_key"] = A.get("readout_key")
    (RESULTS / "audit.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"audit: {n_ok}/{len(checks)} agree")
    for c in checks:
        if not c["agree"]:
            print("MISMATCH", c)


if __name__ == "__main__":
    main()
