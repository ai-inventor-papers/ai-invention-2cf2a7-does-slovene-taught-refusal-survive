#!/usr/bin/env python3
"""FALLBACK F1: Phase B generation in the HF/Heretic path (NF4), used if the vLLM engine gate fails.

Same steps, same items, same prompts and the same output schema as src/gen_vllm.py (results/{model}/gens.jsonl), so the
two engines are interchangeable for the analysis. Adapters are loaded from adapters/{model}/... into the PEFT model.
Because HF NF4 generation runs at ~1.2 items/s on the L4, this path uses the pre-registered REDUCED design:
trial steps score the core blocks only (C + HC), the number of trial steps is chosen from the measured rate and the
deadline, and the random-edit arm is cut to 3 seeds. Every cut is written to results/cut_ladder.json.

Usage: .venv/bin/python src/gen_hf.py --model gemma_it --deadline-epoch <t>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch  # noqa: E402

try:
    from torch._native import registry as _nr
    _nr.deregister_op_overrides(disable_dsl_names=["triton", "cutedsl", "helion", "nvmath"])
except (ImportError, AttributeError, RuntimeError, ValueError):
    pass

from common import DATA, MODELS, RESULTS, WS, Lexicon, append_jsonl, degenerate, langid_sl, read_jsonl, setup_logger  # noqa: E402
import probe as P  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=list(MODELS))
ap.add_argument("--deadline-epoch", type=float, default=0.0)
ap.add_argument("--max-trials", type=int, default=40)
ap.add_argument("--n-random", type=int, default=3)
ap.add_argument("--budget", type=int, default=22000)
ap.add_argument("--max-bs", type=int, default=96)
ARGS = ap.parse_args()
M = ARGS.model
OUT = RESULTS / M
ADIR = WS / "adapters" / M
logger = setup_logger(f"gen_hf_{M}")
LAMBDAS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]


def heretic_markers() -> list[str]:
    import tomllib
    return list(tomllib.loads((OUT / "cfg" / "config.toml").read_text())["scorer"]["KeywordRate"]["keyword_markers"])


def main():
    import phase_a as PA  # reuses write_settings / load_lora_state / Model

    torch.cuda.set_per_process_memory_fraction(0.95)
    P.set_budget(ARGS.budget, ARGS.max_bs)
    settings = PA.write_settings()
    from heretic.model import Model
    model = Model(settings)
    tok = model.tokenizer
    lex = Lexicon(heretic_markers())
    from safetensors.torch import load_file

    def apply_adapter(path: Path | None):
        model.reset_model()
        if path is None:
            return
        sd = load_file(str(path / "adapter_model.safetensors"))
        params = dict(model.model.named_parameters())
        for k, v in sd.items():
            name = k.replace(".lora_A.weight", ".lora_A.default.weight").replace(".lora_B.weight", ".lora_B.default.weight")
            if name.startswith("base_model.model.") and name not in params:
                name = name[len("base_model.model."):]
            assert name in params, name
            params[name].data = v.to(params[name].device, params[name].dtype)

    Pit = read_jsonl(DATA / "probe_P300.jsonl")
    T = read_jsonl(DATA / "twins_T150.jsonl")
    Rb = {b: [p for p in Pit if p["block"] == b] for b in ("C", "R1", "R2", "R3", "R4")}
    Hb = {b: [t for t in T if t["block"] == b] for b in ("HC", "HR1", "HR2", "HR3")}
    cuts = json.loads((RESULTS / "cut_ladder.json").read_text()) if (RESULTS / "cut_ladder.json").exists() else {}
    cuts.setdefault("engine", "hf_fallback_F1")
    cuts.setdefault("core_only_trials", True)
    cuts.setdefault("max_random", ARGS.n_random)

    steps = []
    steps.append(("orig", "orig", 0.0, None, True))
    for lam in LAMBDAS:
        steps.append((f"lambda_{lam:.2f}", "lambda", lam, ADIR / f"lambda_{lam:.2f}", lam == 1.0))
    for k in range(1, ARGS.max_trials + 1):
        if (ADIR / f"trial_{k:02d}").exists():
            steps.append((f"trial_{k:02d}", "trial", float(k), ADIR / f"trial_{k:02d}", False))
    for s in range(1, ARGS.n_random + 1):
        if (ADIR / f"rand_{s}").exists():
            steps.append((f"rand_{s}", "rand", float(s), ADIR / f"rand_{s}", False))
    first = ["orig", "lambda_1.00", "trial_01", "trial_02", "trial_03"]
    steps.sort(key=lambda s: (0, first.index(s[0])) if s[0] in first else (1, 0))

    def req_for(curve, step):
        if curve in ("orig", "lambda"):
            en_orig = curve == "orig" or step == 1.0
            arms = ("en_bt", "sl_mt", "en_orig") if en_orig else ("en_bt", "sl_mt")
            return [(it, a, "harmful") for a in arms for it in Pit] + [(it, a, "benign") for a in arms for it in T]
        if curve == "trial":
            k = int(step)
            hb = Rb["C"] if cuts.get("core_only_trials") else Rb["C"] + Rb[f"R{(k - 1) % 4 + 1}"]
            bb = Hb["HC"] if cuts.get("core_only_trials") else Hb["HC"] + Hb[f"HR{(k - 1) % 3 + 1}"]
        else:
            hb, bb = Rb["C"], Hb["HC"]
        return [(it, a, "harmful") for a in ("en_bt", "sl_mt") for it in hb] + \
               [(it, a, "benign") for a in ("en_bt", "sl_mt") for it in bb]

    gpath = OUT / "gens.jsonl"
    done = {}
    for r in read_jsonl(gpath):
        done[(r["step_name"], r["item_id"], r["arm"])] = 1
    timing = json.loads((OUT / "gen_timing.json").read_text()) if (OUT / "gen_timing.json").exists() else {}
    rate = None
    t_all = time.time()
    for si, (name, curve, step, adapter, _) in enumerate(steps):
        req = [q for q in req_for(curve, step) if (name, q[0]["item_id"], q[1]) not in done]
        if not req:
            continue
        if ARGS.deadline_epoch and rate is not None:
            left = ARGS.deadline_epoch - time.time()
            remaining = sum(len(req_for(c, s)) for (n_, c, s, _a, _e) in steps[si:])
            if remaining / rate > left:
                keep = [s for s in steps[si:] if s[1] != "trial"]
                n_tr = max(0, int((left * rate - sum(len(req_for(c, s)) for (_n, c, s, _a, _e) in keep)) //
                                  max(1, len(req_for("trial", 1.0)))))
                allowed = {s[0] for s in steps[si:] if s[1] == "trial"}
                allowed = set(sorted(allowed)[:n_tr])
                cuts["max_trials_named"] = sorted(allowed)
                cuts["reason"] = f"projected {(remaining / rate) / 60:.0f} min > {left / 60:.0f} min left"
                (RESULTS / "cut_ladder.json").write_text(json.dumps(cuts, indent=1))
                logger.warning(f"CUT LADDER: keeping trial steps {sorted(allowed)}")
                if curve == "trial" and name not in allowed:
                    continue
        if cuts.get("max_trials_named") is not None and curve == "trial" and name not in set(cuts["max_trials_named"]):
            continue
        apply_adapter(adapter)
        t = time.time()
        seqs = P.encode(tok, P.render(tok, [it[a] for it, a, _ in req]))
        texts, _ = P.generate(model.model, tok, seqs, 128)
        rows = []
        for (it, a, kind), tx in zip(req, texts):
            r = {"item_id": it["item_id"], "model": M, "curve": curve, "step": step, "step_name": name, "arm": a,
                 "kind": kind, "block": it["block"], "response": tx,
                 "n_tokens": len(tok(tx, add_special_tokens=False)["input_ids"]), "finish": None,
                 "first_tok": None, "lex": lex.hit(tx), "degenerate": degenerate(tx)}
            if a == "sl_mt":
                r["langid"], r["lang_ok"] = langid_sl(tx)
            rows.append(r)
        append_jsonl(gpath, rows)
        dt = time.time() - t
        rate = len(req) / dt if rate is None else 0.7 * rate + 0.3 * (len(req) / dt)
        timing[name] = {"n": len(req), "s": round(dt, 1), "items_per_s": round(len(req) / dt, 2), "engine": "hf"}
        (OUT / "gen_timing.json").write_text(json.dumps(timing, indent=1))
        en = [r["lex"] for r in rows if r["arm"] == "en_bt" and r["kind"] == "harmful"]
        sl = [r["lex"] for r in rows if r["arm"] == "sl_mt" and r["kind"] == "harmful"]
        logger.info(f"{M} {name}: {len(req)} gens in {dt:.0f}s ({len(req) / dt:.2f}/s); lex EN {sum(en) / max(1, len(en)):.2f} "
                    f"SL {sum(sl) / max(1, len(sl)):.2f}; total {time.time() - t_all:.0f}s")
    (RESULTS / "cut_ladder.json").write_text(json.dumps(cuts, indent=1))
    logger.info(f"GEN_HF DONE {M} in {time.time() - t_all:.0f}s")


if __name__ == "__main__":
    main()
