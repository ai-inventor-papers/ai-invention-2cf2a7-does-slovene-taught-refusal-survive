#!/usr/bin/env python3
"""A7 independent audit: recompute headline point estimates (TD*, TD per control, G, DiD_ref, per-cell rates,
Cohen kappa, manipulation-check own-name rates) from results/items/*.jsonl with a DIFFERENT code path (pandas groupby,
hand-written kappa) and assert agreement with results/analysis.json / method_out.json to 1e-9."""
from __future__ import annotations

import json
import math
import re

import numpy as np
import pandas as pd
from loguru import logger

from common import ITEMS, RES, setup_logging

ROOT = RES.parent
TOL = 1e-9
OWN = {"gams": r"\bgams\w*", "gemma": r"\bgemma\b"}


def kappa(a: np.ndarray, b: np.ndarray) -> float:
    po = float((a == b).mean())
    pa, pb = a.mean(), b.mean()
    pe = pa * pb + (1 - pa) * (1 - pb)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("audit")
    an = json.loads((RES / "analysis.json").read_text())
    mo = json.loads((ROOT / "method_out.json").read_text())
    frames = []
    for f in [f for f in sorted(ITEMS.glob("*__C[0-5].jsonl")) if len(f.stem.split("__")) == 2]:
        frames.append(pd.read_json(f, lines=True)[["pair_id", "model", "lang", "condition", "R_lexv1", "s"]])
    df = pd.concat(frames, ignore_index=True)
    jl = RES / "judge_labels.jsonl"
    if jl.exists():
        j = pd.read_json(jl, lines=True)
        j = j[(j.task == "refusal") & (~j.judge_model.astype(str).str.contains("local"))]
        if "harmless" in j:
            j = j[j.harmless.isna() | (j.harmless == False)]  # noqa: E712
        j = j[["model", "condition", "lang", "pair_id", "judge_label"]].drop_duplicates(["model", "condition", "lang", "pair_id"])
        df = df.merge(j, on=["model", "condition", "lang", "pair_id"], how="left")
    else:
        df["judge_label"] = None
    readout = an["primary_readout_per_model"]
    jr = np.where(df.judge_label.notna(), (df.judge_label == "refuse").astype(float), df.R_lexv1.astype(float))
    df["Rprim"] = np.where(df.model.map(readout) == "judge", jr, df.R_lexv1.astype(float))
    checks = []

    def chk(name, mine, theirs):
        ok = bool((mine is None and theirs is None) or (theirs is not None and abs(mine - theirs) <= TOL))
        checks.append({"quantity": name, "audit": mine, "analysis": theirs, "ok": bool(ok)})

    for rd, col, cont, key in [("primary", "Rprim", False, "primary"), ("s", "s", True, "s_coprimary")]:
        sub = df[df.lang.isin(["en", "sl"])]
        g = sub.groupby(["model", "condition", "lang"])[col].agg(["sum", "count", "mean"])
        if cont:
            L = g["mean"]
        else:
            L = np.log(((g["sum"] + 0.5) / (g["count"] + 1)) / (1 - (g["sum"] + 0.5) / (g["count"] + 1)))
        L = L.unstack("lang")
        gap = (L["sl"] - L["en"])
        shrink = gap.groupby(level="model").transform(lambda x: x.xs("C0", level="condition").iloc[0]) - gap
        G = {}
        for m in ["gams", "gemma"]:
            for c in ["C2", "C3", "C4", "C5"]:
                G[(m, c)] = shrink[(m, "C1")] - shrink[(m, c)]
                chk(f"{rd}:G[{m}|{c}]", float(G[(m, c)]), an[key]["G"][f"{m}|{c}"]["point"])
        TD = {c: G[("gams", c)] - G[("gemma", c)] for c in ["C2", "C3", "C4", "C5"]}
        for c in TD:
            chk(f"{rd}:TD[{c}]", float(TD[c]), an[key]["TD"][c]["point"])
        chk(f"{rd}:TD*", float(min(TD["C2"], TD["C3"])), an[key]["TDstar"]["point"])
        chk(f"{rd}:DiD_ref_C0", float(gap[("gams", "C0")] - gap[("gemma", "C0")]), an[key]["DiD_ref_C0"]["point"])
        if not cont:
            for (m, c, lg), r in g["mean"].items():
                chk(f"rate[{m}|{c}|{lg}]", float(r), an[key]["rates"][f"{m}|{c}|{lg}"])
    chk("method_out:TD*", mo["metadata"]["verdict"]["value"], an["primary"]["TDstar"]["point"])
    # kappa per cell (hand-written)
    for (m, c, lg), sub in df.dropna(subset=["judge_label"]).groupby(["model", "condition", "lang"]):
        if len(sub) < 20:
            continue
        k = kappa(sub.R_lexv1.values.astype(int), (sub.judge_label == "refuse").values.astype(int))
        ref = an["kappa"].get(f"{m}|{c}|{lg}", {}).get("kappa")
        if ref is not None and not math.isnan(k):
            checks.append({"quantity": f"kappa[{m}|{c}|{lg}]", "audit": k, "analysis": ref, "ok": bool(abs(k - ref) < 1e-9)})
    # manipulation-check own-name rates (regex) from the MC item files
    for f in sorted(ITEMS.glob("*__MC__*.jsonl")):
        d = pd.read_json(f, lines=True)
        d = d[d.set == "ID-CHECK"]
        model, _, cname = f.stem.split("__")
        mc = json.loads((RES / f"mc_{model}.json").read_text())[cname]
        rates = d.assign(own=d.response.str.contains(OWN[model], flags=re.I, regex=True)).groupby(["condition", "lang"]).own.mean()
        for (cond, lg), r in rates.items():
            chk(f"mc[{model}|{cname}|{cond}|{lg}]", float(r), mc["conditions"][cond]["identity"][lg]["own_name_rate"])
    n_bad = sum(not c["ok"] for c in checks)
    (RES / "audit.json").write_text(json.dumps({"n_checks": len(checks), "n_failed": n_bad, "tolerance": TOL,
                                                "checks": checks}, indent=1))
    logger.info(f"audit: {len(checks)} checks, {n_bad} failed")
    assert n_bad == 0, [c for c in checks if not c["ok"]][:10]


if __name__ == "__main__":
    main()
