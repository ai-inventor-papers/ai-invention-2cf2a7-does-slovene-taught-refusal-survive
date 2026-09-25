"""Smoke tests: the common engine must reproduce each artifact's archived POINT headline from its archived label column."""
import json
import numpy as np, pandas as pd
from engine import Curve, point_g3, op_point, curve_stats
from common import WORK, RESULTS, write_json

def frames(df):
    f = {}
    h = df[(df.kind == "harmful") & df.arm.isin(["en_bt", "sl_mt"])]
    f["exp9_lambda"] = h[(h.source == "exp9") & h.curve.isin(["orig", "lambda"])]
    f["exp11_final"] = h[(h.source == "exp11") & (h.priority == 1)]
    e8 = h[h.source == "exp8"]
    f["exp8_A1"] = e8[e8.curve.isin(["orig", "lambda"])]
    b = e8[(e8.curve == "trial") & (e8.in_P100 == 1)]
    common = sorted(set(b[b.model == "gemma_it"].step) & set(b[b.model == "gams3_it"].step))
    f["exp8_B"] = b[b.step.isin(common)]
    f["exp10_op"] = h[h.source == "exp10"]
    return f

if __name__ == "__main__":
    df = pd.read_parquet(WORK / "frame.parquet")
    F = frames(df)
    res = {}
    tests = [("exp9_lambda", "arch_j1", True, -0.97, "exp9 analysis.json G3 lambda|j1|R1"),
             ("exp11_final", "arch_q14", False, -0.60, "exp11 G3 FINAL without orig step"),
             ("exp8_B", "arch_lex", True, -2.36, "exp8 lexicon G3 curve B"),
             ("exp8_A1", "arch_lex", False, -0.19, "exp8 lexicon G3 curve A1 (lambda only)")]
    for name, col, inc, target, desc in tests:
        cv = Curve(F[name], col)
        g = point_g3(cv, fit_include_orig=inc, fitter="exp8" if name.startswith("exp8") else "exp9")
        res[f"{name}|{col}|orig_in_fit={inc}"] = {"G3": g, "archived": target, "desc": desc, "match_1e-2": abs(g - target) < 0.01,
                                                  "note": "archived value is quoted to 2 dp; spec (fitter, orig in fit) frozen from this test"}
        print(name, col, inc, round(g, 4), target)
    # eval2 IG B under Qwen3-14B (local primary)
    cv = Curve(F["exp8_B"], "arch_q14")
    cs = curve_stats(cv, B=50, fitter="exp8")
    res["exp8_B|arch_q14|IG"] = {"IG": cs["IG"]["est"], "archived": -1.9514831814134705, "G3": cs["G3"]["est"],
                                 "match_1e-3": abs(cs["IG"]["est"] + 1.9514831814134705) < 1e-3, "desc": "eval2 step5 IG (Qwen3-14B, B)"}
    print("eval2 IG", cs["IG"]["est"], cs["G3"]["est"])
    op = op_point(F["exp10_op"], "arch_lex", B=50)
    res["exp10|arch_lex|G3_op"] = {"G3_op": op["G3_op"]["est"], "archived": -2.3053519378907783,
                                   "match_1e-3": abs(op["G3_op"]["est"] + 2.3053519378907783) < 1e-3,
                                   "desc": "exp10 G3_op proxy/lexicon (surrogate labels not in the frame; lexicon twin reproduces the -2.30 headline)"}
    print("exp10 lex G3_op", op["G3_op"]["est"])
    write_json(RESULTS / "smoke_tests.json", res)
