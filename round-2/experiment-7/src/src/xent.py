#!/usr/bin/env python3
"""EXPLORATORY (added after the freeze; not in protocol.json): white-box wording-likelihood test.

For every H/R k0 item, score the TEACHER's (Qwen3-235B) and the OUTGROUP's (Llama-3.3-70B) actual responses under a local
scorer model (teacher forcing, same chat template and empty system turn as generation), taking the first 64 response
tokens and reporting NLL per CHARACTER (tokenizer-neutral). Per item and scorer m:
    delta_m(i) = nll_m(Llama text_i) - nll_m(Qwen text_i)     (> 0: m finds the teacher's wording more likely)
Contrast (analysis): mean_i[delta_GaMS(i) - delta_Gemma(i)] with item bootstrap; Qwen3-14B = same-family positive control.
Usage: python xent.py --model gams|gemma|q14 [--texts q235,out] [--limit N]
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import time

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.pop("TRANSFORMERS_CACHE", None)
import torch  # noqa: E402

from common import disable_torch_native_triton  # noqa: E402

NATIVE = disable_torch_native_triton()
from common import DATA, GENS, read_jsonl, setup_logging  # noqa: E402

MAX_RESP_TOK = 64


@torch.inference_mode()
def main() -> None:
    import gpu_gen
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=["gams", "gemma", "q14"])
    ap.add_argument("--texts", default="q235,out")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--bs", type=int, default=16)
    a = ap.parse_args()
    logger = setup_logging(f"xent_{a.model}")
    gpu_gen.logger = logger
    torch.cuda.set_per_process_memory_fraction(0.92)
    items = {i["item_id"]: i for i in read_jsonl(DATA / "items.jsonl")}
    bt = {r["item_id"]: r["en_bt"] for r in read_jsonl(DATA / "h_en_bt.jsonl")}
    rows = []
    for s in a.texts.split(","):
        for g in read_jsonl(GENS / f"{s}.jsonl"):
            if g["set"] in ("H", "R") and g["condition"] == "k0" and g["lang_arm"] in ("en_orig", "sl_mt") \
                    and not g.get("blocked_generation") and g.get("response"):
                it = items[g["item_id"]]
                rows.append({"key": g["key"], "src": s, "item_id": g["item_id"], "set": g["set"],
                             "lang_arm": g["lang_arm"], "prompt": it["arms"][g["lang_arm"]], "resp": g["response"]})
    if a.limit:
        rows = rows[: a.limit]
    out_p = GENS / f"xent_{a.model}.jsonl"
    done = {r["key"] for r in read_jsonl(out_p)}
    rows = [r for r in rows if r["key"] not in done]
    logger.info(f"xent {a.model}: {len(rows)} texts to score")
    if not rows:
        return
    model, tok, _ = gpu_gen.load_model(a.model)
    pad = tok.pad_token_id if tok.pad_token_id is not None else 0
    for r in rows:
        ctx = tok(gpu_gen.render(tok, a.model, r["prompt"]), add_special_tokens=False).input_ids
        rid = tok(r["resp"], add_special_tokens=False).input_ids[:MAX_RESP_TOK]
        r["_ctx"], r["_rid"] = ctx, rid
        r["_nchar"] = len(tok.decode(rid))
    rows.sort(key=lambda r: len(r["_ctx"]) + len(r["_rid"]))
    t0 = time.time()
    with out_p.open("a") as f:
        for i in range(0, len(rows), a.bs):
            b = rows[i:i + a.bs]
            seqs = [r["_ctx"] + r["_rid"] for r in b]
            L = max(len(s) for s in seqs)
            inp = torch.tensor([[pad] * (L - len(s)) + s for s in seqs], device="cuda:0")
            att = torch.tensor([[0] * (L - len(s)) + [1] * len(s) for s in seqs], device="cuda:0")
            K = min(MAX_RESP_TOK + 1, L)  # only the last K positions are needed (left padding right-aligns every response)
            logits = model(input_ids=inp, attention_mask=att, logits_to_keep=K).logits.float()
            lp = torch.log_softmax(logits[:, :-1], -1)
            tgt = inp[:, L - K + 1:]
            tok_lp = lp.gather(-1, tgt.unsqueeze(-1)).squeeze(-1)
            for j, r in enumerate(b):
                n = len(r["_rid"])
                nll = float(-tok_lp[j, K - 1 - n: K - 1].sum())
                f.write(json.dumps({"key": r["key"], "scorer": a.model, "src": r["src"], "item_id": r["item_id"],
                                    "set": r["set"], "lang_arm": r["lang_arm"], "n_tok": n, "n_char": r["_nchar"],
                                    "nll_sum": nll, "nll_per_char": nll / max(1, r["_nchar"])}) + "\n")
            del logits, lp
            if (i // a.bs) % 20 == 0:
                logger.info(f"{i + len(b)}/{len(rows)} in {time.time() - t0:.0f}s")
    logger.info(f"xent {a.model} done in {time.time() - t0:.0f}s")
    del model
    gc.collect()
    torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
