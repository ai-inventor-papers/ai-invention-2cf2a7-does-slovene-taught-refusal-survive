#!/usr/bin/env python3
"""TODO-5 re-derivation (third code path: pandas groupby over raw results/items, no analyze/audit helpers).
Recomputes headline numbers and runs each statistic on SHUFFLED labels to confirm it collapses to ~0."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

IT = Path(__file__).resolve().parent.parent / "results" / "items"
MET = {"arc_challenge": "acc_norm", "hellaswag": "acc_norm", "openbookqa": "acc_norm", "piqa": "acc_norm", "boolq": "acc", "winogrande": "acc"}
rows = []
for f in IT.glob("util_*.jsonl"):
    for line in f.read_text().splitlines():
        r = json.loads(line)
        rows.append({"model": r["model"], "cond": r["cond"], "lang": r["lang"], "task": r["task"], "item": r["item_id"],
                     "y": r[MET[r["task"]]], "ch": 1 / r["n_choices"]})
df = pd.DataFrame(rows)
o = df[df.cond == "orig"].set_index(["model", "lang", "task", "item"])


def macro(d_cond, o_ref):
    g = d_cond.groupby(["lang", "task"]).y.mean()
    go = o_ref.groupby(["lang", "task"]).agg(y=("y", "mean"), ch=("ch", "mean"))
    H = (g - go.ch) / (go.y - go.ch) - 1
    H = H[(go.y - go.ch) >= 0.10 - 1e-9]
    return H.groupby("lang").mean()


out = {}
rng = np.random.default_rng(7)
for m in ["gams3_it", "gemma_it"]:
    om = o.loc[m].reset_index()
    for c in ["E_iter1", "E_art2", "rand_nm_j1"]:
        d = df[(df.model == m) & (df.cond == c)]
        if d.empty:
            continue
        mh = macro(d, om)
        # shuffled placebo: swap orig/cond labels per item (joined on item) -> H should be ~0
        j = d.merge(om, on=["lang", "task", "item"], suffixes=("", "_o"))
        sw = rng.random(len(j)) < 0.5
        a = j.assign(y=np.where(sw, j.y_o, j.y))
        b = j.assign(y=np.where(sw, j.y, j.y_o), ch=j.ch)
        pl = macro(a[["lang", "task", "item", "y", "ch"]], b[["lang", "task", "item", "y", "ch"]])
        out[f"{m}/{c}"] = {"loss_en": round(-mh["en"], 5), "loss_sl": round(-mh["sl"], 5), "A": round(mh["sl"] - mh["en"], 5),
                           "placebo_shuffled_H_en": round(pl["en"], 5), "placebo_shuffled_H_sl": round(pl["sl"], 5)}
for c in ["E_iter1", "E_art2"]:
    if f"gams3_it/{c}" in out and f"gemma_it/{c}" in out:
        out[f"I/{c}"] = round(out[f"gams3_it/{c}"]["A"] - out[f"gemma_it/{c}"]["A"], 5)
# KL multi-token EXCESS (SL-MT/EN-BT of edit over random avg), plus shuffled-arm placebo (-> ~1)
for m in ["gams3_it", "gemma_it"]:
    kl = [json.loads(l) for l in (IT / f"kl_{m}.jsonl").read_text().splitlines()]
    ex = {}
    for l in (IT / f"klextra_{m}.jsonl").read_text().splitlines() if (IT / f"klextra_{m}.jsonl").exists() else []:
        r = json.loads(l); ex[(r["item_id"], r["arm"])] = r["kl"]
    k = pd.DataFrame([{"item": r["item_id"], "arm": r["arm"], "edit": r["kl"]["E_iter1"]["multi"],
                       "rand": np.mean([r["kl"][f"rand_nm_j{j}"]["multi"] for j in range(1, 6)])} for r in kl])
    p = k.pivot(index="item", columns="arm")
    exc = (p.edit.sl_mt.mean() / p.edit.en_bt.mean()) / (p.rand.sl_mt.mean() / p.rand.en_bt.mean())
    sw = rng.random(len(p)) < 0.5
    sl_s = np.where(sw, p.edit.en_bt, p.edit.sl_mt); en_s = np.where(sw, p.edit.sl_mt, p.edit.en_bt)
    out[f"{m}/KL_multi_EXCESS_E_iter1"] = round(exc, 4)
    out[f"{m}/KL_edit_ratio_arm_shuffled_placebo"] = round(sl_s.mean() / en_s.mean(), 4)
A = json.loads((IT.parent / "analysis.json").read_text())
cmp = {}
for key, v in out.items():
    if "/" in key and key.split("/")[1] in ("E_iter1", "E_art2", "rand_nm_j1") and not key.startswith("I/"):
        m, c = key.split("/")
        mac = A["utility"]["macros"][m][c]
        cmp[key] = abs(v["loss_en"] - mac["en"]["macro_loss"]) < 1e-4 and abs(v["loss_sl"] - mac["sl"]["macro_loss"]) < 1e-4
out["agrees_with_analysis_json"] = cmp
out["I_analysis"] = {c: A["utility"]["interaction"][c]["I"] for c in ("E_iter1", "E_art2") if c in A["utility"]["interaction"]}
out["KL_EXCESS_analysis"] = {m: A["kl"][m]["ratios"]["E_iter1"]["multi"]["sl_over_enbt"]["excess_vs_rand"]["excess"] for m in A["kl"]}
(IT.parent / "rederive_headlines.json").write_text(json.dumps(out, indent=2, default=float))
print(json.dumps(out, indent=1, default=float))
