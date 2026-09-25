#!/usr/bin/env python3
"""STEP 8: independent audit. Plain-python recomputation (no import from stats_lib/analysis) of the headline point
estimates from results/items_final.jsonl, asserted against results/analysis_final.json to 1e-9; placebo permutations;
integrity checks (disjoint DEV/FINAL, split manifest, freeze/addendum timestamps precede FINAL generation/judging,
ledger spend). Writes results/audit.json.
"""
from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import NormalDist

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
Z = NormalDist().inv_cdf
CHECKS: list[dict] = []


def rj(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def check(name, cond, info=None):
    CHECKS.append({"name": name, "pass": bool(cond), "info": info})
    print(("PASS " if cond else "FAIL ") + name, "" if info is None else str(info)[:200])


def Lh(k, n):
    p = (k + 0.5) / (n + 1)
    return math.log(p / (1 - p))


def zh(k, n):
    return Z((k + 0.5) / (n + 1))


def did(v):  # v = [gemma_en, gemma_sl, gams_en, gams_sl]
    return (v[3] - v[2]) - (v[1] - v[0])


def pairs(rows, set_, en_arm, sl_arm, outcome, idkey):
    t, meta = {}, defaultdict(dict)
    for r in rows:
        if r["set"] != set_:
            continue
        meta[r[idkey]][r["arm"]] = r
        if r.get(outcome) is not None:
            t[(r[idkey], r["model"], r["arm"])] = r[outcome]
    out = []
    for k in sorted(meta):
        if en_arm in meta[k] and sl_arm in meta[k]:
            c = [t.get((k, "gemma_it", en_arm)), t.get((k, "gemma_it", sl_arm)), t.get((k, "gams3_it", en_arm)),
                 t.get((k, "gams3_it", sl_arm))]
            if None not in c:
                out.append((k, c, meta[k][en_arm], meta[k][sl_arm]))
    return out


def did_group(P, g=None, key="group"):
    k, n = [0] * 4, [0] * 4
    for _, c, mE, mS in P:
        for j in range(4):
            m = mE if j in (0, 2) else mS
            if g is None or m.get(key) == g:
                k[j] += c[j]
                n[j] += 1
    return did([Lh(k[j], n[j]) for j in range(4)])


def sdt_did(P):
    u = [p for p in P if p[2]["is_harmful"]]
    s = [p for p in P if not p[2]["is_harmful"]]
    dp, cc = [], []
    for j in range(4):
        zH = zh(sum(p[1][j] for p in u), len(u))
        zF = zh(sum(p[1][j] for p in s), len(s))
        dp.append(zH - zF)
        cc.append(-(zH + zF) / 2)
    return did(dp), did(cc), dp, cc


def sdt_D(P):
    out = {}
    for g in ("low", "high"):
        u = [p for p in P if p[2]["is_harmful"] and p[2]["group"] == g]
        s = [p for p in P if not p[2]["is_harmful"] and p[2]["group"] == g]
        out[g] = did([zh(sum(p[1][j] for p in u), len(u)) - zh(sum(p[1][j] for p in s), len(s)) for j in range(4)])
    return out["low"] - out["high"]


def main() -> None:
    rows = rj(RES / "items_final.jsonl")
    A = json.loads((RES / "analysis_final.json").read_text())
    tol = 1e-9
    # ---- recomputation
    P = pairs(rows, "refuseu_nat", "EN_nat", "SL_nat", "R", "pair_id")
    ov, lo, hi = did_group(P), did_group(P, "low"), did_group(P, "high")
    c2 = A["C2_refuseu"]
    check("recompute_DiD_ref", abs(ov - c2["DiD_overall"]["est"]) < tol, [ov, c2["DiD_overall"]["est"]])
    check("recompute_D", abs((lo - hi) - c2["D"]["est"]) < tol, [lo - hi, c2["D"]["est"]])
    check("recompute_n_pairs", len(P) == c2["n_pairs"], [len(P), c2["n_pairs"]])
    for cell, v in c2["cells"].items():
        mk, lg, g = cell.split("|")
        j = {"gemma_it": 0, "gams3_it": 2}[mk] + (lg == "sl")
        sel = [p for p in P if g == "all" or (p[2] if lg == "en" else p[3]).get("group") == g]
        k = sum(p[1][j] for p in sel)
        if v["n"] != len(sel) or v["k"] != k:
            check(f"recompute_cell_{cell}", False, [k, len(sel), v])
    check("recompute_cells_refuseu", True, len(c2["cells"]))
    PX = pairs(rows, "refuseu_x", "EN_BT", "SL_MT", "R", "item_id")
    mt = did_group(PX)
    a_mt = A["C2_refuseu_sensitivities"]["item_matched_MT_ENBT"]["DiD_overall"]["est"]
    check("recompute_DiD_ref_MT", abs(mt - a_mt) < tol, [mt, a_mt])
    PI = [p for p in pairs(rows, "identity", "EN", "SL", "own_name", "pair_id") if p[2]["kind"] == "identity"]
    did_id = did([Lh(sum(p[1][j] for p in PI), len(PI)) for j in range(4)])
    a_id = A["C1"]["identity"]["DiD_id"]["est"]
    check("recompute_DiD_id", abs(did_id - a_id) < tol, [did_id, a_id])
    PH = pairs(rows, "hard", "EN_BT", "SL_MT", "R", "item_id")
    dd, dc, dp, cc = sdt_did(PH)
    h = A["C2_hard_sdt"]["primary_SLMT_vs_ENBT"]
    check("recompute_DiD_dprime", abs(dd - h["DiD_dprime"]["est"]) < tol, [dd, h["DiD_dprime"]["est"]])
    check("recompute_DiD_c", abs(dc - h["DiD_c"]["est"]) < tol, [dc, h["DiD_c"]["est"]])
    check("recompute_dprime_cells", all(abs(a - b) < tol for a, b in zip(dp, h["cells"]["dprime"])), dp)
    check("recompute_c_cells", all(abs(a - b) < tol for a, b in zip(cc, h["cells"]["c"])), cc)
    Dd = sdt_D(PH)
    check("recompute_D_dprime", abs(Dd - h["D_dprime"]["est"]) < tol, [Dd, h["D_dprime"]["est"]])
    # ---- placebos
    rng = random.Random(20260924)
    perm_did, perm_D = [], []
    for _ in range(1000):
        Q = []
        for k, c, mE, mS in P:
            if rng.random() < 0.5:  # swap model labels within the pair
                c = [c[2], c[3], c[0], c[1]]
            Q.append((k, c, mE, mS))
        perm_did.append(did_group(Q))
        perm_D.append(did_group(Q, "low") - did_group(Q, "high"))
    med = lambda v: sorted(v)[len(v) // 2]  # noqa: E731
    check("placebo_model_swap_DiD_ref_centred", abs(med(perm_did)) < 0.1, med(perm_did))
    check("placebo_model_swap_D_centred", abs(med(perm_D)) < 0.1, med(perm_D))
    perm_dd = []
    for _ in range(300):
        Q = [(k, [c[2], c[3], c[0], c[1]] if rng.random() < .5 else c, mE, mS) for k, c, mE, mS in PH]
        perm_dd.append(sdt_did(Q)[0])
    check("placebo_model_swap_DiD_dprime_centred", abs(med(perm_dd)) < 0.1, med(perm_dd))
    perm_g = []
    gE = [p[2]["group"] for p in P]
    gS = [p[3]["group"] for p in P]
    for _ in range(1000):
        order = list(range(len(P)))
        rng.shuffle(order)
        Q = [(P[i][0], P[i][1], {"group": gE[order[i]]}, {"group": gS[order[i]]}) for i in range(len(P))]
        perm_g.append(did_group(Q, "low") - did_group(Q, "high"))
    check("placebo_group_permutation_D_centred", abs(med(perm_g)) < 0.1, med(perm_g))
    obs_D = lo - hi
    p_perm = sum(abs(x) >= abs(obs_D) for x in perm_g) / len(perm_g)
    perm_lang = []
    for _ in range(1000):
        Q = [(k, [c[1], c[0], c[3], c[2]] if rng.random() < .5 else c, mE, mS) for k, c, mE, mS in PX]
        perm_lang.append(did_group(Q))
    check("placebo_language_arm_swap_DiD_MT_centred", abs(med(perm_lang)) < 0.1, med(perm_lang))
    # ---- integrity
    man = {}
    for s in ("refuseu_nat", "refuseu_x", "hard", "identity"):
        for r in rj(ROOT / "data" / f"{s}.jsonl"):
            man[r["gid"]] = r
    dev_ids = {(r["set"], r["item_id"]) for r in man.values() if r["split"] == "DEV"}
    fin_ids = {(r["set"], r["item_id"]) for r in man.values() if r["split"] == "FINAL"}
    check("dev_final_disjoint", not (dev_ids & fin_ids))
    sm = json.loads((Path(__file__).resolve().parents[4] / "round-1/dataset-1/src/outputs/split_manifest.json").read_text())
    dev_pairs = sorted({r["pair_id"] for r in man.values() if r["set"] == "refuseu_nat" and r["split"] == "DEV"})
    check("refuseu_dev_equals_split_manifest", dev_pairs == sorted(sm["refuseu_eval"]["DEV"]["ids"]))
    hard_dev_man = set(sm["hard"]["DEV"]["ids"])
    check("hard_dev_subset_of_manifest", {r["item_id"] for r in man.values() if r["set"] == "hard"
                                          and r["split"] == "DEV"} <= hard_dev_man)
    fin_keys = {r["key"] for r in rows}
    dev_keys = set()
    for p in (ROOT / "outputs/dev").glob("gen_*.jsonl"):
        dev_keys |= {r["key"] for r in rj(p)}
    check("no_final_key_in_dev", not (fin_keys & dev_keys))
    check("final_rows_all_FINAL_split", all(r["split"] == "FINAL" for r in rows))
    pc = json.loads((ROOT / "protocol/protocol_commit.json").read_text())
    ac = json.loads((ROOT / "protocol/addendum_commit.json").read_text())
    t_first_final_gen = min(datetime.fromisoformat(r["t_gen"]) for p in (ROOT / "outputs/final").glob("gen_*.jsonl")
                            for r in rj(p))
    check("protocol_commit_before_first_FINAL_generation",
          datetime.fromisoformat(pc["commit_time"]) <= t_first_final_gen, [pc["commit_time"], str(t_first_final_gen)])
    fin_ledger_ts = [datetime.fromisoformat(r["ts"]) for p in (ROOT / "outputs/ledgers").glob("ledger_final_*.jsonl")
                     for r in rj(p) if r.get("ts")]
    check("addendum_commit_before_first_FINAL_ledger_line",
          bool(fin_ledger_ts) and datetime.fromisoformat(ac["commit_time"]) <= min(fin_ledger_ts),
          [ac["commit_time"], str(min(fin_ledger_ts)) if fin_ledger_ts else None])
    import subprocess
    def commit_time(path):
        out = subprocess.run(["git", "log", "-1", "--format=%cI", "--", path], cwd=ROOT, capture_output=True,
                             text=True).stdout.strip()
        return datetime.fromisoformat(out) if out else None
    d1 = commit_time("protocol/deviation_1.json")
    check("deviation1_commit_before_any_judge_ledger_line",
          d1 is not None and all(d1 <= datetime.fromisoformat(r["ts"]) for p in (ROOT / "outputs/ledgers").glob(
              "ledger_*.jsonl") for r in rj(p) if r.get("ts")), str(d1))
    d2 = commit_time("protocol/deviation_2.json")
    t_res = [datetime.fromtimestamp(p.stat().st_mtime).astimezone() for p in (RES.glob("analysis_final.json"))]
    check("deviation2_commit_before_final_analysis_written",
          d2 is not None and all(d2 <= t for t in t_res), [str(d2), [str(t) for t in t_res]])
    spend = sum(float(r.get("cost") or 0) for p in (ROOT / "outputs/ledgers").glob("ledger_*.jsonl") for r in rj(p))
    rep = json.loads((RES / "spend.json").read_text())["total_usd"] if (RES / "spend.json").exists() else None
    check("ledger_spend_equals_reported", rep is not None and abs(spend - rep) < 1e-9, [spend, rep])
    check("spend_under_cap_10usd", spend < 10.0, spend)
    out = {"n_checks": len(CHECKS), "n_pass": sum(c["pass"] for c in CHECKS), "checks": CHECKS,
           "placebo_summaries": {"model_swap_DiD_ref_median": med(perm_did), "model_swap_D_median": med(perm_D),
                                 "model_swap_DiD_dprime_median": med(perm_dd), "group_perm_D_median": med(perm_g),
                                 "group_perm_two_sided_p_for_observed_D": p_perm,
                                 "lang_swap_DiD_MT_median": med(perm_lang)}}
    (RES / "audit.json").write_text(json.dumps(out, indent=1, default=str))
    print(f"audit: {out['n_pass']}/{out['n_checks']}")


if __name__ == "__main__":
    main()
