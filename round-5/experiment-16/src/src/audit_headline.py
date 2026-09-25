#!/usr/bin/env python3
"""Headline audit (separate code path; imports nothing from src/): recompute the raw headline contrasts straight from
gens/*.jsonl + labels/gemini.jsonl with plain dicts, run the same paired bootstrap 'CI excludes 0' test on the REAL
labels and on within-item SHUFFLED cell labels (the test must fail on the shuffle), and write results/audit_headline.json.
"""
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def rows(p):
    return [json.loads(x) for x in Path(p).read_text().splitlines() if x.strip()]


def L(k, n):  # protocol bounding: safe rate k/n clipped to [0.5/(n+1), 1 - 0.5/(n+1)], then logit
    lo = 0.5 / (n + 1)
    p = min(max(k / n, lo), 1 - lo)
    return math.log(p / (1 - p))


def main():
    lab = {}
    for r in rows(ROOT / "labels/gemini.jsonl"):
        if r["readout"] == "gemini" and r.get("score") is not None:
            lab[r["key"]] = r
    import yaml
    ds = {m: yaml.safe_load((ROOT / f"dose_addendum_{m}.yaml").read_text())["dose_star_tag"] for m in ("gemma_it", "gams3_it")}
    cell = {}
    for m in ds:
        for r in rows(ROOT / f"gens/{m}.jsonl"):
            if r["kind"] == "harmful" and r["arm"] != "EN_orig" and r["dose_tag"] == ds[m] and r["key"] in lab:
                cell.setdefault((m, r["cell"]), {})[r["item_id"]] = 1 - int(lab[r["key"]]["U"])  # safe = 1

    def out(m, a="EN>SL", b="EN>EN"):
        items = sorted(set(cell[(m, a)]) & set(cell[(m, b)]))
        return items, [cell[(m, a)][i] for i in items], [cell[(m, b)][i] for i in items]

    def stat(xa, xb):
        n = len(xa)
        return L(sum(xa), n) - L(sum(xb), n)

    def boot_ci(xa, xb, B=2000, seed=7):
        rng = random.Random(seed)
        n = len(xa)
        v = []
        for _ in range(B):
            idx = [rng.randrange(n) for _ in range(n)]
            v.append(stat([xa[i] for i in idx], [xb[i] for i in idx]))
        v.sort()
        return [v[int(0.025 * B)], v[int(0.975 * B) - 1]]

    res = {}
    for m in ds:
        items, xa, xb = out(m)
        ci = boot_ci(xa, xb)
        res[f"OUT_raw_gemini|{m}"] = {"n": len(items), "est": stat(xa, xb), "ci95": ci, "excludes_0": ci[0] > 0 or ci[1] < 0}
        rng = random.Random(11)
        sa, sb = [], []
        for x, y in zip(xa, xb):  # within-item shuffle of the two cells' labels
            if rng.random() < 0.5:
                x, y = y, x
            sa.append(x)
            sb.append(y)
        cis = boot_ci(sa, sb)
        res[f"PLACEBO_shuffled|{m}"] = {"est": stat(sa, sb), "ci95": cis, "excludes_0": cis[0] > 0 or cis[1] < 0}
    g, s = res["OUT_raw_gemini|gemma_it"]["est"], res["OUT_raw_gemini|gams3_it"]["est"]
    res["dOUT_raw_gemini"] = {"est": s - g}
    A = json.loads((ROOT / "results/analysis.json").read_text())["estimands"]
    res["matches_analysis"] = {
        "OUT_gemma": abs(g - A["OUT|gemma_it|dose*"]["raw_gemini"]["est"]) < 1e-9,
        "OUT_gams": abs(s - A["OUT|gams3_it|dose*"]["raw_gemini"]["est"]) < 1e-9,
        "dOUT": abs((s - g) - A["dOUT|dose*"]["raw_gemini"]["est"]) < 1e-9}
    (ROOT / "results/audit_headline.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
