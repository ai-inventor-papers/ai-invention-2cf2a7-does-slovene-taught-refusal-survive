#!/usr/bin/env python3
"""Mini end-to-end test on SYNTHETIC labels (never mixed with real outputs): unit tests of kappa/JSD/bootstrap, then
analyze.py on a fake root (AII_TEST_ROOT) where Q14 and GaMS are planted to resemble Q235.
Run: AII_TEST_ROOT=<scratch dir> .venv/bin/python tests/test_pipeline.py"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
TEST_ROOT = Path(os.environ["AII_TEST_ROOT"])


def unit_tests() -> None:
    from sklearn.metrics import cohen_kappa_score

    from stats import boot_idx, jsd, kappa, kappa_rows
    rng = np.random.default_rng(0)
    a = rng.integers(0, 2, 300).astype(float)
    b = np.where(rng.random(300) < .8, a, 1 - a)
    assert abs(kappa(a, b) - cohen_kappa_score(a, b)) < 1e-12, "kappa != sklearn"
    B = boot_idx(300)
    kr = kappa_rows(a[B], b[B])
    assert abs(kr[0] - cohen_kappa_score(a[B[0]], b[B[0]])) < 1e-12
    assert np.array_equal(boot_idx(300), B), "bootstrap not reproducible"
    p, q = {"x": 3, "y": 1}, {"x": 1, "y": 3}
    assert jsd(p, p) == 0 and abs(jsd(p, q) - jsd(q, p)) < 1e-12, "JSD not symmetric / 0 on identical"
    print("unit tests OK")


def synth() -> None:
    from common import read_jsonl, row_key, write_jsonl
    if TEST_ROOT.exists():
        shutil.rmtree(TEST_ROOT)
    for d in ("data", "gens", "labels", "results"):
        (TEST_ROOT / d).mkdir(parents=True)
    for f in ("items.jsonl", "h_en_bt.jsonl", "ref_sft.jsonl", "prefill_strings.json", "items_manifest.json"):
        shutil.copy(REPO / "data" / f, TEST_ROOT / "data" / f)
    items = read_jsonl(REPO / "data/items.jsonl")
    rng = np.random.default_rng(1)
    en_ref = ["I'm sorry, but I can't help with that.", "I cannot fulfill this request.", "Sorry, I can't assist."]
    sl_ref = ["Oprostite, vendar vam pri tem ne morem pomagati.", "Ne morem pomagati s tem.", "Žal ne morem."]
    style = {"q235": 0, "q14": 0, "gams": 0, "gemma": 1, "out": 2}
    gens, labs, labs2, ids = {s: [] for s in style}, [], [], []
    for it in items:
        arms = list(it["arms"]) + (["en_bt"] if it["set"] == "H" else [])
        base = rng.random() < (0.8 if it.get("is_harmful") else 0.2)
        teacher = base if rng.random() < .85 else not base
        for arm in arms:
            conds = ["k0"] + (["pre_comply5", "pre_neutral"] if it.get("r200") and arm in ("en_orig", "sl_mt") else [])
            for cond in conds:
                for s in style:
                    if cond != "k0" and s in ("q235", "out"):
                        continue
                    if s in ("q235",):
                        y = teacher
                    elif s in ("q14", "gams"):
                        y = teacher if rng.random() < .85 else not teacher
                    else:
                        y = base if rng.random() < .8 else rng.random() < .5
                    if cond == "pre_comply5":
                        y = y and rng.random() < (0.3 if s != "gemma" else 0.8)
                    lang = "sl" if arm.startswith("sl") else "en"
                    ref = (sl_ref if lang == "sl" else en_ref)[style[s]]
                    resp = ref + " extra words here" if y else "Here is how you can do it: step one."
                    if it["set"] == "ID":
                        resp = "I am Qwen, created by Alibaba Cloud." if s in ("q235", "q14") else "I am Gemma."
                    k = row_key(it["item_id"], s, arm, cond)
                    gens[s].append({"key": k, "item_id": it["item_id"], "set": it["set"], "lang_arm": arm,
                                    "condition": cond, "system": s, "response": resp, "prompt_sha1": "x"})
                    if it["set"] == "ID":
                        ids.append({"key": k, "label": "Qwen" if s in ("q235", "q14") else "Gemma"})
                    else:
                        lab = "REFUSE" if y else ("PARTIAL" if rng.random() < .1 else "COMPLY")
                        labs.append({"key": k, "system": s, "item_id": it["item_id"], "set": it["set"],
                                     "lang_arm": arm, "condition": cond, "label": lab, "judge_src": "synthetic"})
                        if rng.random() < .15:
                            labs2.append(dict(labs[-1], label=lab if rng.random() < .93 else "COMPLY"))
    for s, rows in gens.items():
        write_jsonl(TEST_ROOT / "gens" / f"{s}.jsonl", rows)
    write_jsonl(TEST_ROOT / "labels/refusal_gemini.jsonl", labs)
    write_jsonl(TEST_ROOT / "labels/refusal_gpt41.jsonl", labs2)
    write_jsonl(TEST_ROOT / "labels/idname.jsonl", ids)
    # substitute-readout path: the same synthetic labels as the 'local' judge (validation labels = the gemini file)
    write_jsonl(TEST_ROOT / "labels/refusal_local.jsonl", labs)
    write_jsonl(TEST_ROOT / "labels/idname_local.jsonl", ids)
    print(f"synthetic: {sum(len(v) for v in gens.values())} gens, {len(labs)} labels")


def main() -> None:
    unit_tests()
    synth()
    env = dict(os.environ, AII_TEST_ROOT=str(TEST_ROOT))
    for readout, out in (("gemini", "analysis_gemini_partial.json"), ("local", "analysis.json")):
        r = subprocess.run([sys.executable, str(REPO / "src/analyze.py"), "--readout", readout, "--out", out], env=env,
                           capture_output=True, text=True, cwd=REPO / "src")
        print(r.stdout[-1500:], r.stderr[-1500:])
        assert r.returncode == 0, f"analyze.py --readout {readout} failed on synthetic data"
    A = json.loads((TEST_ROOT / "results/analysis.json").read_text())
    h = A["T1"]["H_en_orig"]
    print("FP-cal", h["fpcal_dk"], "\nT1 dk", h["dk"], "\nverdicts", json.dumps(A["verdicts"], default=str)[:1500])
    assert h["fpcal_dk"]["est"] > 0 and h["dk"]["est"] > 0, "planted resemblance not recovered"
    assert abs(A["T1"]["placebo"]["gams_vs_out"]["perm_mean"]) < 0.05, "placebo does not centre at 0"
    print("pipeline test OK")


if __name__ == "__main__":
    main()
