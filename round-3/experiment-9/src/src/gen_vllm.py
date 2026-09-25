#!/usr/bin/env python3
"""S4 ENGINE GATE + S6 PHASE B: vLLM generation (bitsandbytes 4-bit in-flight quantisation + exported Heretic LoRA adapters).

Prompts are rendered AND tokenised with the HF tokenizer exactly as Heretic / phase_a do (official chat template, no system
turn, tokenizer(rendered) with default special tokens -> the double <bos> of Heretic 3521f86 is reproduced), and passed to
vLLM as token ids, so HF and vLLM see byte-identical inputs. Greedy, 128 new tokens.

Steps (per model): orig (no adapter) + lambda {.25..2} (8) + trial 1..N + rand 1..R.
  orig / lambda : P300 x {EN-BT, SL-MT} + T150 x {EN-BT, SL-MT}; EN-orig arm (P300 + T150) only at orig and lambda=1
  trial k       : (C + R[(k-1) mod 4]) x {EN-BT, SL-MT} + (HC + HR[(k-1) mod 3]) x {EN-BT, SL-MT}
  rand s        : C x 2 arms + HC x 2 arms
Output: results/{model}/gens.jsonl (append-only; resumable per step).

Usage: .venv_vllm/bin/python src/gen_vllm.py --model gemma_it --mode gate|full [--order staged] [--max-trials 40]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, MODELS, RESULTS, WS, Lexicon, append_jsonl, degenerate, langid_sl, read_jsonl, setup_logger  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=list(MODELS))
ap.add_argument("--mode", default="full", choices=["gate", "full", "gate_full"])
ap.add_argument("--max-trials", type=int, default=40)
ap.add_argument("--n-random", type=int, default=5)
ap.add_argument("--gpu-util", type=float, default=0.88)
# vLLM 0.30 removed the "bitsandbytes" quantization method; "fp8" quantises the bf16 checkpoint online (W8A8, Ada/L4).
ap.add_argument("--quant", default="fp8")
ap.add_argument("--core-only", action="store_true", help="A5 reduced design: score C + HC at every step except orig")
ap.add_argument("--skip-gate", action="store_true")
ap.add_argument("--max-num-seqs", type=int, default=256)
ap.add_argument("--steps", default="", help="comma list of step names to run (default: all, staged order)")
ap.add_argument("--deadline-epoch", type=float, default=0.0, help="stop starting new steps after this time")
ARGS = ap.parse_args()
M = ARGS.model
OUT = RESULTS / M
logger = setup_logger(f"gen_vllm_{M}_{ARGS.mode}")
LAMBDAS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]
ADIR = WS / "adapters" / M


def heretic_markers() -> list[str]:
    import tomllib
    cfg = tomllib.loads((OUT / "cfg" / "config.toml").read_text())
    return list(cfg["scorer"]["KeywordRate"]["keyword_markers"])


def build_steps(P, T) -> list[dict]:
    Rb = {b: [p for p in P if p["block"] == b] for b in ("C", "R1", "R2", "R3", "R4")}
    Hb = {b: [t for t in T if t["block"] == b] for b in ("HC", "HR1", "HR2", "HR3")}
    steps = []

    def full_step(name, curve, step, adapter, en_orig):
        req = []
        for kind, items in (("harmful", P), ("benign", T)):
            for arm in (("en_bt", "sl_mt", "en_orig") if en_orig else ("en_bt", "sl_mt")):
                req += [(it, arm, kind) for it in items]
        return {"name": name, "curve": curve, "step": step, "adapter": adapter, "req": req}

    def core_step(name, curve, step, adapter):
        req = [(it, arm, "harmful") for arm in ("en_bt", "sl_mt") for it in Rb["C"]]
        req += [(it, arm, "benign") for arm in ("en_bt", "sl_mt") for it in Hb["HC"]]
        return {"name": name, "curve": curve, "step": step, "adapter": adapter, "req": req}

    # REDUCED DESIGN (amendment A5): full probe only at the two reference points; core blocks elsewhere
    steps.append(full_step("orig", "orig", 0.0, None, True))
    for lam in LAMBDAS:
        a = ADIR / f"lambda_{lam:.2f}"
        steps.append(full_step(f"lambda_{lam:.2f}", "lambda", lam, a, True) if (lam == 1.0 and not ARGS.core_only)
                     else core_step(f"lambda_{lam:.2f}", "lambda", lam, a))
    ntr = len(list(ADIR.glob("trial_*")))
    for k in range(1, min(ARGS.max_trials, ntr) + 1):
        hb = Rb["C"] if ARGS.core_only else Rb["C"] + Rb[f"R{(k - 1) % 4 + 1}"]
        bb = Hb["HC"] if ARGS.core_only else Hb["HC"] + Hb[f"HR{(k - 1) % 3 + 1}"]
        req = [(it, arm, "harmful") for arm in ("en_bt", "sl_mt") for it in hb]
        req += [(it, arm, "benign") for arm in ("en_bt", "sl_mt") for it in bb]
        steps.append({"name": f"trial_{k:02d}", "curve": "trial", "step": float(k), "adapter": ADIR / f"trial_{k:02d}", "req": req})
    for s in range(1, ARGS.n_random + 1):
        if not (ADIR / f"rand_{s}").exists():
            continue
        req = [(it, arm, "harmful") for arm in ("en_bt", "sl_mt") for it in Rb["C"]]
        req += [(it, arm, "benign") for arm in ("en_bt", "sl_mt") for it in Hb["HC"]]
        steps.append({"name": f"rand_{s}", "curve": "rand", "step": float(s), "adapter": ADIR / f"rand_{s}", "req": req})
    # staged order (T5): orig, lambda=1, trials 1-3 first; then the rest
    first = ["orig", "lambda_1.00", "trial_01", "trial_02", "trial_03"]
    steps.sort(key=lambda s: (0, first.index(s["name"])) if s["name"] in first else (1, 0))
    return steps


def main():
    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams
    from vllm.inputs import TokensPrompt
    from vllm.lora.request import LoRARequest
    import probe_tok as PT

    repo, rev = MODELS[M]["repo"], MODELS[M]["revision"]
    tok = AutoTokenizer.from_pretrained(repo, revision=rev)
    lex = Lexicon(heretic_markers())
    t = time.time()
    llm = LLM(model=repo, revision=rev, tokenizer=repo, tokenizer_revision=rev, quantization=(ARGS.quant or None),
              dtype="bfloat16", enable_lora=True, max_lora_rank=8, max_loras=2, max_model_len=1024,
              gpu_memory_utilization=ARGS.gpu_util, max_num_seqs=ARGS.max_num_seqs, seed=0,
              limit_mm_per_prompt={"image": 0} if M == "gemma_it" else None, enable_prefix_caching=True)
    logger.info(f"vLLM loaded in {time.time() - t:.0f}s")
    sp = SamplingParams(temperature=0.0, max_tokens=128, logprobs=1)
    lr_cache: dict[str, LoRARequest] = {}

    def lora_for(path):
        if path is None:
            return None
        key = str(path)
        if key not in lr_cache:
            lr_cache[key] = LoRARequest(Path(path).name, len(lr_cache) + 1, key)
        return lr_cache[key]

    def run(prompts_ids: list[list[int]], lora) -> list[dict]:
        outs = llm.generate([TokensPrompt(prompt_token_ids=ids) for ids in prompts_ids], sp, lora_request=lora,
                            use_tqdm=False)
        res = []
        for o in outs:
            c = o.outputs[0]
            res.append({"response": c.text, "n_tokens": len(c.token_ids), "finish": c.finish_reason,
                        "first_tok": c.token_ids[0] if c.token_ids else None})
        return res

    if ARGS.mode in ("gate", "gate_full") and not ARGS.skip_gate and not (OUT / "engine_gate.json").exists():
        rows = read_jsonl(OUT / "engine_gate_hf.jsonl")
        items = {}
        for d in read_jsonl(DATA / "dev12.jsonl"):
            items[(d["item_id"], "en_bt")] = d["en_bt"]
            items[(d["item_id"], "sl_mt")] = d["sl_mt"]
        for h in read_jsonl(DATA / "gate_harmless40.jsonl"):
            items[(h["item_id"], "en_orig")] = h["en_orig"]
        out = []
        tt = {}
        for lam in (0.0, 1.0):
            sub = [r for r in rows if r["lambda"] == lam]
            ids = PT.encode_users(tok, [items[(r["item_id"], r["arm"])] for r in sub])
            t = time.time()
            res = run(ids, lora_for(WS / "selected" / M / "adapter") if lam else None)
            tt[str(lam)] = round(len(ids) / (time.time() - t), 3)
            for r, g in zip(sub, res):
                out.append({**{k: r[k] for k in ("item_id", "arm", "kind", "lambda")}, "response_vllm": g["response"],
                            "response_hf": r["response"], "first_vllm": g["first_tok"], "first_hf": r["first_top1"],
                            "lex_vllm": lex.hit(g["response"]), "lex_hf": r["lex"]})
        # throughput on a realistic batch (one full trial-sized step with the selected adapter)
        P = read_jsonl(DATA / "probe_P300.jsonl")
        ids = PT.encode_users(tok, [p[a] for a in ("en_bt", "sl_mt") for p in P])
        t = time.time()
        res = run(ids, lora_for(WS / "selected" / M / "adapter"))
        thr = len(ids) / (time.time() - t)
        from statistics import mean
        rep = {"n": len(out), "throughput_small_items_per_s": tt, "throughput_600_items_per_s": round(thr, 3),
               "mean_new_tokens_600": mean(r["n_tokens"] for r in res),
               "first_token_top1_agree": {str(l): mean(int(o["first_vllm"] == o["first_hf"]) for o in out if o["lambda"] == l)
                                          for l in (0.0, 1.0)},
               "lex_outcome_agree": {str(l): mean(int(o["lex_vllm"] == o["lex_hf"]) for o in out if o["lambda"] == l)
                                     for l in (0.0, 1.0)},
               "first40_agree": {str(l): mean(int(o["response_vllm"].strip()[:40] == o["response_hf"].strip()[:40])
                                              for o in out if o["lambda"] == l) for l in (0.0, 1.0)},
               "adapter_changes_outputs_frac": mean(
                   int(a["response_vllm"].strip()[:60] != b["response_vllm"].strip()[:60])
                   for a in out if a["lambda"] == 1.0 for b in out if b["lambda"] == 0.0 and b["item_id"] == a["item_id"]
                   and b["arm"] == a["arm"])}
        (OUT / "engine_gate_vllm.jsonl").write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in out))
        (OUT / "engine_gate.json").write_text(json.dumps(rep, indent=2))
        hf_thr = json.loads((OUT / "phase_a_checks.json").read_text()).get("hf_gate_throughput_items_per_s", {})
        rep["hf_throughput_items_per_s"] = hf_thr
        rep["throughput_ratio_vs_hf"] = round(rep["throughput_600_items_per_s"] / max(1e-9, min(hf_thr.values())), 2) if hf_thr else None
        rep["pass"] = {"first_token_top1_ge_0.9": all(v >= 0.9 for v in rep["first_token_top1_agree"].values()),
                       "lex_outcome_ge_0.9": all(v >= 0.9 for v in rep["lex_outcome_agree"].values()),
                       "adapter_changes_ge_0.2": rep["adapter_changes_outputs_frac"] >= 0.2,
                       "throughput_ge_4x": (rep["throughput_ratio_vs_hf"] or 0) >= 4}
        rep["PASS"] = all(rep["pass"].values())
        rep["note"] = "outcome agreement under the primary judge J1 is computed post hoc (results/engine_gate_j1.json)"
        (OUT / "engine_gate.json").write_text(json.dumps(rep, indent=2))
        logger.info(f"ENGINE GATE {M}: {rep}")
        if ARGS.mode == "gate" or not rep["PASS"]:
            if not rep["PASS"]:
                logger.error("ENGINE GATE FAILED -> not running Phase B in vLLM (fallback F1)")
            return

    P = read_jsonl(DATA / "probe_P300.jsonl")
    T = read_jsonl(DATA / "twins_T150.jsonl")
    steps = build_steps(P, T)
    if ARGS.steps:
        want = set(ARGS.steps.split(","))
        steps = [s for s in steps if s["name"] in want]
    cuts = json.loads((RESULTS / "cut_ladder.json").read_text()) if (RESULTS / "cut_ladder.json").exists() else {}
    gpath = OUT / "gens.jsonl"
    done = {}
    for r in read_jsonl(gpath):
        done[r["step_name"]] = done.get(r["step_name"], 0) + 1
    timing = json.loads((OUT / "gen_timing.json").read_text()) if (OUT / "gen_timing.json").exists() else {}
    t_all = time.time()
    rate = None
    for si, st in enumerate(steps):
        # ---- CUT LADDER A (applied to steps not yet generated; recorded in results/cut_ladder.json) ----
        if cuts.get("core_only_trials") and st["curve"] == "trial":
            st = dict(st, req=[q for q in st["req"] if q[0]["block"] in ("C", "HC")])
        if cuts.get("max_trials") and st["curve"] == "trial" and st["step"] > cuts["max_trials"]:
            logger.warning(f"cut ladder: skipping {st['name']} (max_trials={cuts['max_trials']})")
            continue
        if cuts.get("max_random") and st["curve"] == "rand" and st["step"] > cuts["max_random"]:
            continue
        if done.get(st["name"], 0) >= len(st["req"]):
            continue
        if done.get(st["name"], 0):
            logger.warning(f"step {st['name']} partially written ({done[st['name']]}/{len(st['req'])}); regenerating missing rows")
        if ARGS.deadline_epoch and rate is not None:
            remaining = sum(len(x["req"]) for x in steps[si:])
            proj = remaining / rate
            left = ARGS.deadline_epoch - time.time()
            if proj > left:
                new_cuts = dict(cuts)
                if not new_cuts.get("core_only_trials"):
                    new_cuts["core_only_trials"] = True
                    new_cuts["reason_core_only"] = f"projected {proj / 60:.0f} min > {left / 60:.0f} min left at step {st['name']}"
                elif not new_cuts.get("max_random"):
                    new_cuts["max_random"] = 3
                else:
                    kept = max(20, int(new_cuts.get("max_trials", ARGS.max_trials) * left / max(proj, 1e-9)))
                    new_cuts["max_trials"] = kept
                    new_cuts["reason_max_trials"] = f"projected {proj / 60:.0f} min > {left / 60:.0f} min left"
                cuts = new_cuts
                (RESULTS / "cut_ladder.json").write_text(json.dumps(cuts, indent=1))
                logger.warning(f"CUT LADDER A applied: {cuts}")
                if cuts.get("core_only_trials") and st["curve"] == "trial":
                    st = dict(st, req=[q for q in st["req"] if q[0]["block"] in ("C", "HC")])
                if cuts.get("max_trials") and st["curve"] == "trial" and st["step"] > cuts["max_trials"]:
                    continue
        have = {(r["item_id"], r["arm"]) for r in read_jsonl(gpath) if r["step_name"] == st["name"]} if done.get(st["name"]) else set()
        req = [q for q in st["req"] if (q[0]["item_id"], q[1]) not in have]
        t = time.time()
        ids = PT.encode_users(tok, [it[arm] for it, arm, _ in req])
        res = run(ids, lora_for(st["adapter"]))
        rows = []
        for (it, arm, kind), g in zip(req, res):
            r = {"item_id": it["item_id"], "model": M, "curve": st["curve"], "step": st["step"], "step_name": st["name"],
                 "arm": arm, "kind": kind, "block": it["block"], **g, "lex": lex.hit(g["response"]),
                 "degenerate": degenerate(g["response"])}
            if arm == "sl_mt":
                r["langid"], r["lang_ok"] = langid_sl(g["response"])
            rows.append(r)
        append_jsonl(gpath, rows)
        dt = time.time() - t
        rate = len(req) / dt if rate is None else 0.7 * rate + 0.3 * (len(req) / dt)
        timing[st["name"]] = {"n": len(req), "s": round(dt, 1), "items_per_s": round(len(req) / dt, 2),
                              "mean_tokens": round(sum(x["n_tokens"] for x in rows) / len(rows), 1)}
        (OUT / "gen_timing.json").write_text(json.dumps(timing, indent=1))
        en = [r["lex"] for r in rows if r["arm"] == "en_bt" and r["kind"] == "harmful"]
        sl = [r["lex"] for r in rows if r["arm"] == "sl_mt" and r["kind"] == "harmful"]
        logger.info(f"{M} {st['name']}: {len(req)} gens in {dt:.0f}s ({len(req) / dt:.1f}/s); lex EN-BT {sum(en) / len(en):.2f} "
                    f"SL {sum(sl) / len(sl):.2f}; total {time.time() - t_all:.0f}s")
    logger.info(f"PHASE B DONE {M} in {time.time() - t_all:.0f}s")


if __name__ == "__main__":
    main()
