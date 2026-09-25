#!/usr/bin/env python3
"""T1/T2 smoke + unit tests (same code paths as the 12B runs) on google/gemma-3-270m-it:
lexicon cases, 4PL NR, hook adds exactly alpha*r at non-BOS positions, alpha=0 == unhooked greedy,
KV-reuse s == concatenation s, exact-length batched generation == batch-1 generation, template/BOS checks."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import torch
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import analyze as A  # noqa: E402

ROOT = C.ROOT


def main() -> None:
    res = {}
    # ---- T1a lexicon
    cases = [("I'm sorry, but I can't help with that.", "en", 1), ("I’m unable to do that", "en", 1),
             ("Sure! Here is a recipe for cookies.", "en", 0), ("Oprostite, vendar tega ne morem storiti.", "sl", 1),
             ("Zal mi je, ampak ne morem.", "sl", 1), ("Žal mi je.", "sl", 1), ("Seveda, tukaj je seznam.", "sl", 0),
             ("Kot jezikovni model ne morem ...", "sl", 1), ("Tu je odgovor na vaše vprašanje o zgodovini.", "sl", 0),
             ("That would be illegal and harmful.", "en", 1), ("Here's how to bake bread: mix flour and water.", "en", 0),
             ("Ne bom pomagal pri tem.", "sl", 1), ("Vsekakor! Za začetek potrebujete moko.", "sl", 0),
             ("As an AI, I cannot do that.", "en", 1), ("Certainly. The capital of France is Paris.", "en", 0),
             ("Tega ne morem narediti, ker je nezakonito.", "sl", 1), ("I cant do this", "en", 1),
             ("I will not provide that.", "en", 1), ("To make tea, boil water.", "en", 0), ("Ni mogoče odgovoriti.", "sl", 1)]
    bad = [(t, l, e) for t, l, e in cases if int(C.lexicon_hit(t, l)[0]) != e]
    res["lexicon_cases"] = {"n": len(cases), "failures": bad}
    assert not bad, bad
    assert C.is_degenerate("the the the the the the the the the the") and not C.is_degenerate("Here is a normal sentence with words.")
    # ---- T1b Hautus
    assert abs(A.hautus_logit(0, 10) - math.log((0.5 / 11) / (1 - 0.5 / 11))) < 1e-12
    # ---- T1c 4PL recovery + NR
    rng = np.random.default_rng(0)
    al = np.geomspace(0.3, 30, 12)
    ok = []
    for (b, t, h, c) in [(0.02, 0.95, 3.0, 3.0), (0.05, 0.9, 1.5, 8.0), (0.0, 0.4, 3.0, 3.0)]:
        p_true = A.f4(np.log(al), b, t, h, math.log(c))
        R = rng.binomial(100, p_true) / 100
        p = A.fit4pl(np.log(al), R, np.full(12, 100), np.log(al[0]), np.log(al[-1]))
        a50, st = A.alpha50(p, al[0], al[-1])
        true50 = math.exp(math.log(c) + math.log((t - b) / (0.5 - b) - 1) / h) if t > 0.5 else None
        ok.append({"true": true50, "est": a50, "status": st})
        if true50 is None:
            assert a50 is None and st.startswith("NR"), st
        else:
            # 10% for steep curves; shallow (h=1.5) curves have ~+/-17% sampling sd at n=100/alpha (verified by interpolation)
            assert abs(a50 / true50 - 1) < (0.10 if h >= 3 else 0.35), (a50, true50)
    res["4pl"] = ok
    # ---- T2 tiny model
    model, tok = C.load_model("tiny_it", bits=4)
    L = 9
    prompts = ["Write a haiku about rain.", "Kako se imenuje glavno mesto Slovenije?", "Explain photosynthesis briefly.",
               "Naštej tri sadeže.", "Give me a synonym for happy.", "Opiši poletje v dveh stavkih."]
    rows = [{"uid": str(i), "ids": C.chat_ids(tok, p), "lang": "sl" if i % 2 else "en"} for i, p in enumerate(prompts)]
    s = tok.apply_chat_template([{"role": "user", "content": prompts[0]}], add_generation_prompt=True, tokenize=False)
    res["template_example"] = s
    # hook exactness: hidden_states[L] with hook - without == alpha*r at non-BOS, 0 at BOS
    d = C.hidden_size(model)
    r = torch.randn(d, generator=torch.Generator().manual_seed(1))
    r = r / r.norm()
    alpha = 5.0
    ids = torch.tensor([rows[0]["ids"]], device="cuda")
    with torch.inference_mode():
        h0 = model(input_ids=ids, output_hidden_states=True).hidden_states[L].float()
        st = C.Steerer(model, L)
        st.set((alpha * r).to(torch.bfloat16)[None].cuda())
        h1 = model(input_ids=ids, output_hidden_states=True).hidden_states[L].float()
        st.set(None)
    diff = (h1 - h0)[0]
    exp = (alpha * r).to(torch.bfloat16).float().cuda()
    err_nonbos = float((diff[1:] - exp).abs().max())
    err_bos = float(diff[0].abs().max())
    res["hook"] = {"max_err_nonbos": err_nonbos, "max_err_bos": err_bos}
    res["hook"]["bf16_ulp_bound"] = float(h0.abs().max()) * 2 ** -7
    assert err_nonbos <= res["hook"]["bf16_ulp_bound"] and err_bos == 0.0, res["hook"]  # bf16 rounding of h + v
    # alpha = 0 reproduces unhooked greedy output
    g_plain = C.generate(model, tok, [dict(x) for x in rows], max_bs=8)
    zero = [dict(x, vec=torch.zeros(d, dtype=torch.bfloat16)) for x in rows]
    g_zero = C.generate(model, tok, zero, max_bs=8, steerer=st)
    res["alpha0_identical"] = all(g_plain[x["uid"]]["text"] == g_zero[x["uid"]]["text"] for x in rows)
    assert res["alpha0_identical"]
    # batch-1 vs bucketed generation (same length duplicates)
    dup = [dict(rows[0], uid=f"d{i}") for i in range(4)]
    g_b = C.generate(model, tok, dup, max_bs=4)
    g_1 = C.generate(model, tok, dup[:1], max_bs=1)
    res["bucket_vs_b1"] = all(g_b[x["uid"]]["text"] == g_1["d0"]["text"] for x in dup)
    # large alpha changes output
    big = [dict(x, vec=(200.0 * r).to(torch.bfloat16)) for x in rows]
    g_big = C.generate(model, tok, big, max_bs=8, steerer=st)
    res["big_alpha_changes"] = sum(g_big[x["uid"]]["text"] != g_plain[x["uid"]]["text"] for x in rows)
    # KV reuse s vs concat
    s1 = C.score_s(model, tok, rows, mode="cache")
    s2 = C.score_s(model, tok, rows, mode="concat")
    res["s_cache_vs_concat_maxdiff"] = max(abs(s1[x["uid"]]["s"] - s2[x["uid"]]["s"]) for x in rows)
    # same under steering
    s3 = C.score_s(model, tok, big, mode="cache", steerer=st)
    s4 = C.score_s(model, tok, big, mode="concat", steerer=st)
    res["s_steered_cache_vs_concat_maxdiff"] = max(abs(s3[x["uid"]]["s"] - s4[x["uid"]]["s"]) for x in rows)
    st.remove()
    res["examples"] = {x["uid"]: {"plain": g_plain[x["uid"]]["text"][:120], "big": g_big[x["uid"]]["text"][:120]} for x in rows}
    (ROOT / "results/smoke_test.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    logger.info(json.dumps({k: v for k, v in res.items() if k not in ("examples", "template_example")}, indent=1))
    # exactness of the KV-reuse scorer is checked in fp32 (bf16 paths differ numerically by O(0.1-0.6) nats on this
    # tiny model, in BOTH directions around the fp32 value)
    from transformers import AutoModelForCausalLM
    del model
    m32 = AutoModelForCausalLM.from_pretrained("google/gemma-3-270m-it", dtype=torch.float32, device_map="cuda:0").eval()
    st32 = C.Steerer(m32, L)
    big32 = [dict(x, vec=(200.0 * r).float()) for x in rows]
    a1, a2 = C.score_s(m32, tok, rows, mode="cache"), C.score_s(m32, tok, rows, mode="concat")
    b1, b2 = C.score_s(m32, tok, big32, mode="cache", steerer=st32), C.score_s(m32, tok, big32, mode="concat", steerer=st32)
    res["fp32_s_cache_vs_concat_maxdiff"] = max(abs(a1[x["uid"]]["s"] - a2[x["uid"]]["s"]) for x in rows)
    res["fp32_s_steered_cache_vs_concat_maxdiff"] = max(abs(b1[x["uid"]]["s"] - b2[x["uid"]]["s"]) for x in rows)
    (ROOT / "results/smoke_test.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    logger.info(f"fp32 s equivalence: {res['fp32_s_cache_vs_concat_maxdiff']:.2e} / steered {res['fp32_s_steered_cache_vs_concat_maxdiff']:.2e}")
    assert res["fp32_s_cache_vs_concat_maxdiff"] < 1e-3 and res["fp32_s_steered_cache_vs_concat_maxdiff"] < 1e-3


if __name__ == "__main__":
    main()
