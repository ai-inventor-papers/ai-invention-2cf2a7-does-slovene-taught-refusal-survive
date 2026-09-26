#!/usr/bin/env python3
"""Independent re-derivation (raw files, own code path) of the identity C1 and MT-arm headline numbers, with placebos.
Writes results/rederive2.json."""
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT, RES = ROOT / "outputs", ROOT / "results"
L = lambda k, n: math.log(((k + .5) / (n + 1)) / (1 - (k + .5) / (n + 1)))  # noqa: E731


def load(p):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def main():
    rep = json.loads((RES / "analysis_results.json").read_text())
    out = {}
    # ---- identity C1 from raw judge export + raw identity generations
    items = {json.loads(l)["iid"]: json.loads(l) for l in (ROOT / "data/identity_items.jsonl").read_text().splitlines()}
    lab = {(r["key"], r["model"]): r["label"] for r in load(OUT / "judge_idname.jsonl")}
    own = {"gemma_it": "Gemma", "gams3_it": "GaMS"}
    M = {}
    for mk in own:
        for r in load(OUT / f"identity_{mk}.jsonl"):
            if items[r["iid"]]["type"] != "identity":
                continue
            M.setdefault(r["iid"], {})[(mk, r["lang"])] = int(lab.get((r["key"], mk)) == own[mk])
    ids = [i for i in M if len(M[i]) == 4]

    def did_id(rows):
        n = len(rows)
        k = {c: sum(M[i][c] for i in rows) for c in [("gemma_it", "en"), ("gemma_it", "sl"), ("gams3_it", "en"), ("gams3_it", "sl")]}
        return (L(k[("gams3_it", "sl")], n) - L(k[("gams3_it", "en")], n)) - (L(k[("gemma_it", "sl")], n) - L(k[("gemma_it", "en")], n))
    obs = did_id(ids)
    # placebo: swap EN/SL labels within each question at random (null of no language effect for both models)
    rnd = random.Random(7)
    null = []
    for _ in range(1000):
        saved = {i: dict(M[i]) for i in ids}
        for i in ids:
            if rnd.random() < .5:
                for mk in own:
                    M[i][(mk, "en")], M[i][(mk, "sl")] = M[i][(mk, "sl")], M[i][(mk, "en")]
        null.append(did_id(ids))
        for i in ids:
            M[i] = saved[i]
    out["identity"] = {"n": len(ids), "DiD_id_rederived": obs, "reported": rep["identity"]["DiD_id"],
                       "lang_swap_placebo_mean": sum(null) / len(null),
                       "perm_p": sum(abs(x) >= abs(obs) for x in null) / len(null)}
    # ---- MT arm (R_judge, pp) from raw judge export
    j = {(r["key"], r["model"]): r["label"] for r in load(OUT / "judge_gemini.jsonl")}
    mt_ids = sorted({r["pair_id"] for r in load(OUT / "gen_mt_gams3_it.jsonl")} & {r["pair_id"] for r in load(OUT / "gen_mt_gemma_it.jsonl")})
    rows = []
    for p in mt_ids:
        v = [j.get((f"{p}|en|original", "gemma_it")), j.get((f"{p}|sl|mt_from_en", "gemma_it")),
             j.get((f"{p}|en|original", "gams3_it")), j.get((f"{p}|sl|mt_from_en", "gams3_it"))]
        if None not in v and "UNPARSED" not in v and "BLOCKED" not in v:
            rows.append([int(x == "REFUSE") for x in v])
    n = len(rows)
    rate = [sum(r[c] for r in rows) / n for c in range(4)]
    pp = 100 * ((rate[3] - rate[2]) - (rate[1] - rate[0]))
    null = []
    for _ in range(1000):  # placebo: swap model labels within pair
        rr = [[r[2], r[3], r[0], r[1]] if rnd.random() < .5 else r for r in rows]
        rt = [sum(r[c] for r in rr) / n for c in range(4)]
        null.append(100 * ((rt[3] - rt[2]) - (rt[1] - rt[0])))
    out["mt_arm_R_judge"] = {"n": n, "rates": rate, "DiD_pp_rederived": pp,
                             "reported_pp": rep["mt_arm"]["R_judge"]["risk_difference"]["overall_pp"]["est"],
                             "model_swap_placebo_mean": sum(null) / len(null),
                             "perm_p": sum(abs(x) >= abs(pp) for x in null) / len(null)}
    (RES / "rederive2.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
