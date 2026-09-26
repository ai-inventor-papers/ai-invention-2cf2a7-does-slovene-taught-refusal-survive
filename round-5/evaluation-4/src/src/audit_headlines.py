#!/usr/bin/env python3
"""Short independent audit of the README headline numbers (TODO 5): reads the RAW label files (not results/*.json
aggregates), recomputes point estimates with plain Python, and runs each contrast on shuffled input (output-language
labels permuted within item) to confirm the effect disappears there. Writes results/audit_headlines.json."""
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def jl(p):
    return [json.loads(x) for x in open(p) if x.strip()]


def lo(k, n):  # Hautus log-odds of the SAFE outcome given k unsafe out of n
    p = 1 - (k + 0.5) / (n + 1)
    return math.log(p / (1 - p))


def contrast(sl, en):  # dicts item -> U (0/1)
    return lo(sum(sl.values()), len(sl)) - lo(sum(en.values()), len(en))


def shuffled(sl, en, reps=2000, seed=7):
    rnd = random.Random(seed)
    common = sorted(set(sl) & set(en))
    vals = []
    for _ in range(reps):
        a, b = {}, {}
        for it in common:
            x, y = sl[it], en[it]
            if rnd.random() < 0.5:
                x, y = y, x
            a[it], b[it] = x, y
        vals.append(contrast(a, b))
    vals.sort()
    return {"null_mean": sum(vals) / len(vals), "null_95": [vals[int(0.025 * reps)], vals[int(0.975 * reps)]]}


def main():
    out = {}
    gem = {}
    for r in jl(ROOT / "labels/sr_gemini_paid.jsonl"):
        if r.get("parsed"):
            gem[(r["key"], r["variant"])] = int(r["score"] >= 0.5)

    def cell(model, o, variant):
        d = {}
        for (k, v), u in gem.items():
            f = k.split("|")
            if f[1] == model and f[2] == "en" and f[3] == o and f[4] in ("1", "1.0") and f[5] == "edit" and v == variant:
                d[f[0]] = u
        return d
    # Gemma hi = lambda 1.0 (key field 4); GaMS hi = 0.625
    sl, en = cell("gemma_it", "sl", "orig"), cell("gemma_it", "en", "orig")
    out["gemini_OUT_U_gemma_hi"] = {"est": contrast(sl, en), "n": [len(sl), len(en)], "shuffled": shuffled(sl, en)}
    slt = cell("gemma_it", "sl", "tr")
    out["gemini_tr_OUT_U_gemma_hi"] = {"est": contrast(slt, en), "n": [len(slt), len(en)]}
    # truncation-matched: EN->EN replaced by its trunc_sl score where it exists
    ent = dict(en)
    for (k, v), u in gem.items():
        f = k.split("|")
        if v == "trunc_sl" and f[1] == "gemma_it" and f[4] in ("1", "1.0"):
            ent[f[0]] = u
    out["gemini_trunc_OUT_U_gemma_hi_approx"] = {"est": contrast(sl, ent), "n": [len(sl), len(ent)],
                                                 "note": "uncut rows keep their original score (same rule as analysis)"}
    # sonnet reference (pilot labels in the cache + sonnet_ref.jsonl), harmful_content
    frame = {r["fid"]: r for r in jl(ROOT / "results/adj_frame.jsonl")}
    son = {}
    for r in jl(ROOT / "labels/api_cache.jsonl"):
        if r.get("model") == "anthropic/claude-sonnet-4.5" and str(r.get("tag", "")).startswith("adj|"):
            fid = r["tag"].split("|")[1]
            try:
                t = r["text"]
                d = json.loads(t[t.index("{"): t.rindex("}") + 1])
                son[frame[fid]["key"]] = int(d["harmful_content"])
            except (ValueError, KeyError, json.JSONDecodeError):
                pass
    for r in jl(ROOT / "labels/sonnet_ref.jsonl"):
        if r.get("label"):
            son[r["key"]] = int(r["label"]["harmful_content"])
    s_sl = {k.split("|")[0]: u for k, u in son.items() if k.split("|")[1] == "gemma_it" and k.split("|")[3] == "sl"
            and k.split("|")[4] in ("1", "1.0")}
    s_en = {k.split("|")[0]: u for k, u in son.items() if k.split("|")[1] == "gemma_it" and k.split("|")[3] == "en"
            and k.split("|")[2] == "en" and k.split("|")[4] in ("1", "1.0")}
    out["sonnet_OUT_U_gemma_hi"] = {"est": contrast(s_sl, s_en), "n": [len(s_sl), len(s_en)],
                                    "U_rates": [sum(s_sl.values()) / len(s_sl), sum(s_en.values()) / len(s_en)],
                                    "note": "different sampled items per cell, so no within-item shuffle is possible"}
    # compare with results
    s1 = json.load(open(ROOT / "results/step1_harmful_content.json"))["readouts"]
    ref = {"gemini_OUT_U_gemma_hi": s1["U_orig"]["contrasts"]["OUT|gemma_it|hi"]["est"],
           "gemini_tr_OUT_U_gemma_hi": s1["U_tr"]["contrasts"]["OUT|gemma_it|hi"]["est"],
           "gemini_trunc_OUT_U_gemma_hi_approx": s1["U_orig_trunc"]["contrasts"]["OUT|gemma_it|hi"]["est"],
           "sonnet_OUT_U_gemma_hi": s1["son_U"]["contrasts"]["OUT|gemma_it|hi"]["est"]}
    for k, v in ref.items():
        out[k]["reported"] = v
        out[k]["match_1e-6"] = abs(out[k]["est"] - v) < 1e-6
    sh = out["gemini_OUT_U_gemma_hi"]["shuffled"]
    out["shuffle_test_fails_as_expected"] = bool(sh["null_95"][0] < 0 < sh["null_95"][1]
                                               and out["gemini_OUT_U_gemma_hi"]["est"] > sh["null_95"][1])
    json.dump(out, open(ROOT / "results/audit_headlines.json", "w"), indent=1)
    print(json.dumps({k: (v if not isinstance(v, dict) else {a: b for a, b in v.items() if a in ("est", "reported", "match_1e-6", "n", "shuffled")}) for k, v in out.items()}, indent=1))


if __name__ == "__main__":
    main()
