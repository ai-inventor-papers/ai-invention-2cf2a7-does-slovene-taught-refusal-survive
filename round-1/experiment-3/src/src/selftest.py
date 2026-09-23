#!/usr/bin/env python3
"""T1/G1/G2 self-certification for one model: chat rendering, batching ladder (batch-1 vs left-padded vs no-pad
buckets), hook no-op and projection tests, s route agreement (cache-copy vs concatenation), timing.
Writes results/selftest_{model}.json."""
from __future__ import annotations

import argparse
import json
import time

import numpy as np
import torch
from loguru import logger

from common import RES, lex_classify, read_jsonl, DATA, setup_logging
from engine import Engine


def first_div(a: list[str], b: list[str]) -> list[bool]:
    return [x == y for x, y in zip(a, b)]


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--attn", default="sdpa")
    a = ap.parse_args()
    setup_logging(f"selftest_{a.model}")
    torch.manual_seed(0)
    E = Engine(a.model, attn=a.attn)
    out = {"model": a.model, "attn": a.attn, "load_seconds": E.load_seconds, "model_class": E.model_class,
           "backbone": E.backbone_name, "mem_gb": torch.cuda.memory_allocated() / 1e9}
    c200 = read_jsonl(DATA / "construct200.jsonl")
    ren_en, ren_sl = E.render(c200[0]["prompt_en"]), E.render(c200[0]["prompt_sl"])
    out["rendered_en"], out["rendered_sl"] = ren_en, ren_sl
    assert "You are" not in ren_en.split(c200[0]["prompt_en"][:20])[0], "system text injected?"
    logger.info(f"rendered EN: {ren_en!r}")
    prompts = [p["prompt_en"] for p in c200[40:48]] + [p["prompt_sl"] for p in c200[40:48]]
    langs = ["en"] * 8 + ["sl"] * 8
    ids = [E.encode_prompt(p)[0] for p in prompts]
    # ---- batch-1 reference
    t0 = time.time()
    ref = [E.run_batch([x], None, 64, False)[0][0] for x in ids]
    out["t_batch1_per_prompt"] = (time.time() - t0) / len(ids)
    # ---- left-padded batch-16
    t0 = time.time()
    lp = E.run_batch(ids, None, 64, False)[0]
    out["t_leftpad16_per_prompt"] = (time.time() - t0) / len(ids)
    # ---- same prompts, different batch composition/pad amounts (two batches of 8 in reversed order)
    lp2 = E.run_batch(ids[:8][::-1], None, 64, False)[0][::-1] + E.run_batch(ids[8:][::-1], None, 64, False)[0][::-1]
    # ---- no-pad: each prompt duplicated 4x in its own exact-length batch (same kernels as batched, no pad)
    nopad = [E.run_batch([x] * 4, None, 64, False)[0][0] for x in ids]
    out["G1"] = {
        "leftpad16_vs_batch1_identical": int(sum(first_div(lp, ref))),
        "nopad4_vs_batch1_identical": int(sum(first_div(nopad, ref))),
        "leftpad16_vs_nopad4_identical": int(sum(first_div(lp, nopad))),
        "leftpad16_vs_leftpad8_identical": int(sum(first_div(lp, lp2))),
        "R_agree_leftpad_vs_batch1": int(sum(lex_classify(x)[0] == lex_classify(y)[0] for x, y in zip(lp, ref))),
        "R_agree_nopad_vs_batch1": int(sum(lex_classify(x)[0] == lex_classify(y)[0] for x, y in zip(nopad, ref))),
        "n": len(ids),
        "examples": [{"batch1": r[:200], "leftpad": l[:200]} for r, l in zip(ref[:3], lp[:3])],
    }
    logger.info(f"G1: {json.dumps({k: v for k, v in out['G1'].items() if k != 'examples'})}")
    # ---- s: cache route (left-padded batch) vs concat route
    s_cache_en = E.run_batch(ids[:8], "en", 0, True)[2]["s"]
    s_cache_sl = E.run_batch(ids[8:], "sl", 0, True)[2]["s"]
    s_cache = np.concatenate([s_cache_en, s_cache_sl])
    s_cat = np.array([E.s_concat(x, lg) for x, lg in zip(ids, langs)])
    s_b1 = np.array([E.run_batch([x], lg, 0, True)[2]["s"][0] for x, lg in zip(ids, langs)])
    out["s_route"] = {"max_abs_cache_vs_concat": float(np.abs(s_cache - s_cat).max()),
                      "max_abs_cachebatch_vs_cache_b1": float(np.abs(s_cache - s_b1).max()),
                      "s_cache": s_cache.tolist(), "s_concat": s_cat.tolist()}
    logger.info(f"s route: {out['s_route']['max_abs_cache_vs_concat']:.4f} / batch-vs-b1 {out['s_route']['max_abs_cachebatch_vs_cache_b1']:.4f}")
    # ---- hook tests
    x = ids[0]
    E.hook_state["mode"] = None
    base = E.run_batch([x], "en", 0, True)[2]["s"][0]
    with E.ablating({l: np.zeros(3840, dtype=np.float32) for l in range(48)}):
        noop = E.run_batch([x], "en", 0, True)[2]["s"][0]
    rng = np.random.default_rng(0)
    u = rng.standard_normal(3840).astype(np.float32); u /= np.linalg.norm(u)
    w = E.last_token_weights([x])
    cap = E.capture([x], w, [31, 32, 40, 47], ablate={l: u for l in range(32, 48)})
    proj = {l: float(abs(cap[l][0] @ u) / np.linalg.norm(cap[l][0])) for l in cap}
    out["hooks"] = {"noop_s_diff": float(abs(base - noop)), "rel_proj_after_ablation": proj}
    logger.info(f"hooks: {out['hooks']}")
    assert out["hooks"]["noop_s_diff"] == 0.0
    assert all(proj[l] < 1e-3 for l in (32, 40, 47)) and proj[31] > proj[32]
    # ---- timing of a bigger batch (throughput)
    big = [E.encode_prompt(p["prompt_en"])[0] for p in c200[:48]]
    for bs in (24, 48):
        torch.cuda.synchronize(); t0 = time.time()
        E.run_batch(big[:bs], "en", 64, True)
        torch.cuda.synchronize()
        out[f"t_gen64_s_bs{bs}_per_prompt"] = (time.time() - t0) / bs
        out[f"maxmem_bs{bs}_gb"] = torch.cuda.max_memory_allocated() / 1e9
        logger.info(f"bs={bs}: {out[f't_gen64_s_bs{bs}_per_prompt']:.3f}s/prompt, maxmem {out[f'maxmem_bs{bs}_gb']:.1f}GB")
    (RES / f"selftest_{a.model}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    logger.info("selftest done")


if __name__ == "__main__":
    main()
