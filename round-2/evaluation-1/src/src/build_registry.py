#!/usr/bin/env python3
"""STEP 0: build the unified response registry over all four iter-1 screens (read-only, $0).

One row per saved model response that a refusal readout can be applied to:
  uid, artifact, model, cell, lang, pair_id, trial, k, req, resp, req_sha (normalised request), en_sha (cluster id =
  normalised EN prompt of the item), category, dose_group, native labels (each artifact's own judge prompt), R_lex,
  existing P1 labels (exp1 gemini / gpt-4.1-mini), exact-identity P1 propagation (label_P1_exact).
Also writes the item registry (artifact, pair_id, lang) -> prompt sha and the request lookup coverage.
Output: work/registry.jsonl.gz, work/item_registry.json, work/registry_summary.json
"""
from __future__ import annotations

import collections
import json

from loguru import logger

from common import (EXP1, EXP2, EXP3, EXP4, WORK, jdump, norm_text, psha, read_jsonl, setup_logging, sha1,
                    write_jsonl)

M2 = {"gemma": "gemma_it", "gams": "gams3_it"}


def exp1_rows(out: list, items: dict) -> None:
    pairs = {p["pair_id"]: p for p in read_jsonl(EXP1 / "data/pairs.jsonl")}
    mt = {r["pair_id"]: r for r in read_jsonl(EXP1 / "data/mt_parallel.jsonl")}
    gem = {(r["model"], r["key"]): r for r in read_jsonl(EXP1 / "outputs/judge_gemini.jsonl")}
    gpt = {(r["model"], r["key"]): r for r in read_jsonl(EXP1 / "outputs/judge_gpt41mini.jsonl")}
    for mk in ("gemma_it", "gams3_it"):
        for fname, cell in ((f"gen_{mk}.jsonl", "score"), (f"gen_mt_{mk}.jsonl", "mt"),
                            (f"gen_construct_{mk}.jsonl", "construct")):
            for r in read_jsonl(EXP1 / "outputs" / fname):
                p = pairs[r["pair_id"]]
                req = mt[r["pair_id"]]["prompt_sl_mt"] if cell == "mt" else p[f"prompt_{r['lang']}"]
                g = gem.get((mk, r["key"]))
                o = gpt.get((mk, r["key"]))
                lang = "slmt" if cell == "mt" else r["lang"]
                out.append({"uid": f"exp1|{mk}|{cell}|{lang}|{r['pair_id']}", "artifact": "exp1", "model": mk, "cell": cell,
                            "lang": lang, "pair_id": r["pair_id"], "trial": -1, "k": None, "req": req, "resp": r["response"],
                            "en_sha": psha(p["prompt_en"]), "category": p["category"], "dose_group": None,
                            "native_prompt": "P1", "native_label": g["label"] if g else None,
                            "native_fallback": bool(g and g.get("fallback")),
                            "gpt41mini_P1": o["label"] if o else None, "R_lex": None})
                items[("exp1", r["pair_id"], lang)] = psha(req)


def exp2_rows(out: list, items: dict) -> None:
    pairs = {p["pair_id"]: p for p in read_jsonl(EXP2 / "data/refuseu_pairs.jsonl")}
    J = {r["key"]: r for r in read_jsonl(EXP2 / "results/shared/judge_labels.jsonl")}
    for short, mk in M2.items():
        for fname, cell in (("r_score400.jsonl", "score400"), ("r_construct100.jsonl", "construct100")):
            for r in read_jsonl(EXP2 / f"results/inst_{short}" / fname):
                p = pairs[r["pair_id"]]
                req = p[r["lang"]]
                j = J.get(f"orig|{short}|{r['lang']}|{r['pair_id']}") if cell == "score400" else None
                nat = None
                if j:
                    nat = "INCOHERENT" if j["incoherent"] else j["label"].upper()
                out.append({"uid": f"exp2|{mk}|{cell}|{r['lang']}|{r['pair_id']}", "artifact": "exp2", "model": mk,
                            "cell": cell, "lang": r["lang"], "pair_id": r["pair_id"], "trial": -1, "k": None, "req": req,
                            "resp": r["text"], "en_sha": psha(p["en"]), "category": p["category"], "dose_group": None,
                            "native_prompt": "EXP2" if j else None, "native_label": nat, "native_fallback": False,
                            "gpt41mini_P1": None, "R_lex": r.get("R_lex"), "degenerate_native": r.get("degenerate")})
                items[("exp2", r["pair_id"], r["lang"])] = psha(req)


def exp3_rows(out: list, items: dict, miss: collections.Counter) -> None:
    s400 = read_jsonl(EXP3 / "data/score400.jsonl")
    look = {}
    en_of = {}
    for p in s400:
        for lg in ("en", "sl"):
            look[sha1(p[f"prompt_{lg}"])] = p[f"prompt_{lg}"]
        en_of[p["pair_id"]] = p["prompt_en"]
    J = {}
    for r in read_jsonl(EXP3 / "results/judge_labels.jsonl"):
        if r.get("task") == "refusal" and "pair_id" in r:
            J[(r["file"], r["pair_id"], r["lang"])] = r
    for mk_s, mk in M2.items():
        for c in ("C0", "C1", "C2", "C3", "C4", "C5"):
            fname = f"{mk_s}__{c}.jsonl"
            for r in read_jsonl(EXP3 / "results/items" / fname):
                req = look.get(r["prompt_sha1"])
                if req is None:
                    miss["exp3"] += 1
                    continue
                j = J.get((fname, r["pair_id"], r["lang"]))
                nat = None
                if j and j.get("judge_label"):
                    nat = j["judge_label"].upper()
                out.append({"uid": f"exp3|{mk}|{c}|{r['lang']}|{r['pair_id']}", "artifact": "exp3", "model": mk, "cell": c,
                            "lang": r["lang"], "pair_id": r["pair_id"], "trial": -1, "k": None, "req": req,
                            "resp": r["response"], "en_sha": psha(en_of[r["pair_id"]]), "category": r["category"],
                            "dose_group": r.get("dose_group"), "native_prompt": "SYS_REF" if nat else None,
                            "native_label": nat, "native_degenerate": (j or {}).get("judge_degenerate"),
                            "native_fallback": False, "gpt41mini_P1": None, "R_lex": r.get("R_lexv1"),
                            "degenerate_native": int(bool(r.get("degenerate")))})
                if c == "C0":
                    items[("exp3", r["pair_id"], r["lang"])] = psha(req)


def exp4_rows(out: list, items: dict) -> None:
    s400 = {p["pair_id"]: p for p in read_jsonl(EXP4 / "data/splits/score400.jsonl")}
    for p in read_jsonl(EXP4 / "data/splits/trial_probe.jsonl"):
        s400.setdefault(p["pair_id"], p)
    J2 = {(r["model"], r["cell"], r["lang"], r["pair_id"], r["trial"]): r["judge"] for r in read_jsonl(EXP4 / "results/judge.jsonl")}
    J1 = {(r["model"], r["cell"], r["lang"], r["pair_id"], r["trial"]): r["judge"] for r in read_jsonl(EXP4 / "results/judge_v1.jsonl")}
    for mk in ("gemma_it", "gams3_it"):
        d = EXP4 / "results" / mk
        srcs = [("orig", [r for r in read_jsonl(d / "orig_score400.jsonl") if "text" in r], lambda r: "orig"),
                ("selected", [r for r in read_jsonl(d / "selected_score400.jsonl") if "text" in r and "R" in r], lambda r: "selected"),
                ("trialpool", [r for r in read_jsonl(d / "trial_probe.jsonl") if r.get("tag") == "trial" and "text" in r], lambda r: "trialpool"),
                ("replay", [r for r in read_jsonl(d / "trial_probe.jsonl") if r.get("tag") == "replay" and "text" in r], lambda r: "replay"),
                ("posthoc", [r for r in read_jsonl(d / "posthoc_probe.jsonl") if "text" in r], lambda r: f"posthoc:{r['tag']}"),
                ("prefill", read_jsonl(d / "prefill.jsonl"), lambda r: f"prefill{r['k']}")]
        for _, rows, cf in srcs:
            for r in rows:
                cell = cf(r)
                p = s400[r["pair_id"]]
                req = p[r["lang"]]
                resp = (r["prefill"] + r["text"]) if cell.startswith("prefill") else r["text"]
                tr = r.get("trial", -1)
                key = (mk, cell, r["lang"], r["pair_id"], tr)
                nat = J2.get(key)
                out.append({"uid": f"exp4|{mk}|{cell}|{r['lang']}|{r['pair_id']}|{tr}", "artifact": "exp4", "model": mk,
                            "cell": cell, "lang": r["lang"], "pair_id": r["pair_id"], "trial": tr, "k": r.get("k"),
                            "req": req, "resp": resp, "cont": r["text"] if cell.startswith("prefill") else None,
                            "en_sha": psha(p["en"]), "category": p.get("category"), "dose_group": p.get("dose_group"),
                            "native_prompt": "JP2" if nat else None, "native_label": nat.upper() if nat else None,
                            "jp_v1": (J1.get(key) or "").upper() or None, "native_fallback": False, "gpt41mini_P1": None,
                            "R_lex": r.get("R_cont") if cell.startswith("prefill") else r.get("R")})
                if cell == "orig":
                    items[("exp4", r["pair_id"], r["lang"])] = psha(req)


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("build_registry")
    out: list[dict] = []
    items: dict = {}
    miss: collections.Counter = collections.Counter()
    exp1_rows(out, items)
    exp2_rows(out, items)
    exp3_rows(out, items, miss)
    exp4_rows(out, items)
    logger.info(f"registry rows {len(out)}; unresolved requests {dict(miss)}")
    # exact-identity P1 propagation: (normalised request, exact response) -> exp1 gemini P1 label
    src = collections.defaultdict(set)
    for r in out:
        if r["artifact"] == "exp1" and r["native_label"] in ("REFUSE", "PARTIAL", "COMPLY"):
            src[(psha(r["req"]), r["resp"])].add(r["native_label"])
    n_conf = sum(len(v) > 1 for v in src.values())
    for r in out:
        r["req_sha"] = psha(r["req"])
        labs = src.get((r["req_sha"], r["resp"]))
        r["label_P1_exact"] = next(iter(labs)) if labs and len(labs) == 1 else None
        r["p1_source"] = ("exp1_native" if r["artifact"] == "exp1" and r["native_label"] else
                          ("exact_propagation" if r["label_P1_exact"] else None))
        r["resp_sha"] = sha1(r["resp"])
    write_jsonl(WORK / "registry.jsonl.gz", out)
    cov = collections.defaultdict(lambda: collections.Counter())
    for r in out:
        c = cov[f"{r['artifact']}|{r['model']}|{r['cell'].split(':')[0]}|{r['lang']}"]
        c["n"] += 1
        c["native"] += r["native_label"] is not None
        c["P1_exact_or_native"] += r["label_P1_exact"] is not None
    jdump({"n_rows": len(out), "unresolved": dict(miss), "conflicting_exact_keys": n_conf,
           "coverage": {k: dict(v) for k, v in sorted(cov.items())}}, WORK / "registry_summary.json")
    jdump({"|".join(k): v for k, v in items.items()}, WORK / "item_registry.json")
    logger.info("done")


if __name__ == "__main__":
    main()
