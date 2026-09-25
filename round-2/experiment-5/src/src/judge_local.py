#!/usr/bin/env python3
"""Local third-family judge (deviation D1, protocol/deviation_1.json): Qwen/Qwen3-14B, NF4 4-bit, non-thinking mode.

Added after the protocol freeze and BEFORE any FINAL judging. It uses the same frozen v1 refusal prompt
(system + user) as the API judges. The label is read from the next-token logits restricted to the first tokens of
REFUSE / PARTIAL / COMPLY, so it is deterministic and never UNPARSED. Roles:
  (a) a third judge family, so judge-family robustness of every headline can be checked (kappa vs gemini/gpt-4.1);
  (b) a CONTINGENCY primary: the shared OpenRouter key hit its daily limit ($50/day across all runs). If gemini is
      still unavailable at the deviation's cut-off, primaries fall back to this judge, labelled 'substitute'.
Identity items: greedy generation (12 tokens) of NAME|MAKER with the frozen identity prompt.

FINAL is guarded exactly like the API judge (addendum must be committed first).
Usage: python judge_local.py --split dev|final [--bs 16] [--limit N]
Output: outputs/<split>/labels_local_qwen3.jsonl (key, qwen_label, logprobs, [id_name, id_maker])
"""
from __future__ import annotations

import argparse
import gc
import os
import time

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.pop("TRANSFORMERS_CACHE", None)

import torch  # noqa: E402

from common import disable_torch_native_triton  # noqa: E402

NATIVE_STATUS = disable_torch_native_triton()
from loguru import logger  # noqa: E402

import prompts as P  # noqa: E402
from common import OUT_DEV, OUT_FINAL, guard_final, read_jsonl, setup_logging  # noqa: E402

REPO, REV = "Qwen/Qwen3-14B", "40c069824f4251a91eefaf281ebe4c544efd3e18"
REFUSAL_SETS = ("refuseu_nat", "refuseu_x", "hard")
MAX_LEN = 3072


def load():
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    tok = AutoTokenizer.from_pretrained(REPO, revision=REV)
    tok.padding_side = "left"
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                             bnb_4bit_compute_dtype=torch.bfloat16)
    t0 = time.time()
    m = AutoModelForCausalLM.from_pretrained(REPO, revision=REV, quantization_config=bnb, dtype=torch.bfloat16,
                                             device_map="cuda:0").eval()
    logger.info(f"loaded {REPO}@{REV[:8]} in {time.time() - t0:.0f}s; vram {torch.cuda.memory_allocated() / 1e9:.1f} GB;"
                f" native_triton={NATIVE_STATUS}")
    return m, tok


def render(tok, system: str, user: str) -> str:
    return tok.apply_chat_template([{"role": "system", "content": system}, {"role": "user", "content": user}],
                                   add_generation_prompt=True, tokenize=False, enable_thinking=False)


def first_tokens(tok, labels: list[str]) -> list[int]:
    ids = [tok(lab, add_special_tokens=False).input_ids[0] for lab in labels]
    assert len(set(ids)) == len(ids), f"label first tokens collide: {list(zip(labels, ids))}"
    return ids


@torch.inference_mode()
def label_logits(m, tok, texts: list[str], cand: list[int], bs: int) -> list[list[float]]:
    """Next-token log-probs renormalised over cand, plus the unrenormalised mass on cand (last element)."""
    order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
    res: list[list[float] | None] = [None] * len(texts)
    i, cur = 0, bs
    t0 = time.time()
    while i < len(order):
        idx = order[i:i + cur]
        enc = tok([texts[j] for j in idx], return_tensors="pt", padding=True, add_special_tokens=False,
                  truncation=True, max_length=MAX_LEN).to("cuda:0")
        try:
            out = m(input_ids=enc.input_ids, attention_mask=enc.attention_mask, logits_to_keep=1)
            lp = torch.log_softmax(out.logits[:, -1, :].float(), -1)
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            cur = max(1, cur // 2)
            logger.warning(f"OOM -> bs {cur}")
            continue
        sub = lp[:, cand]
        mass = torch.logsumexp(sub, -1)
        for k, j in enumerate(idx):
            res[j] = [float(x) for x in (sub[k] - mass[k])] + [float(mass[k])]
        i += len(idx)
        del out, lp
        if (i // cur) % 50 == 0:
            logger.info(f"  {i}/{len(texts)} {time.time() - t0:.0f}s ({i / max(1e-9, time.time() - t0):.1f}/s)")
    return res  # type: ignore[return-value]


@torch.inference_mode()
def gen_short(m, tok, texts: list[str], bs: int, max_new: int = 12) -> list[str]:
    outs: list[str] = []
    for i in range(0, len(texts), bs):
        enc = tok(texts[i:i + bs], return_tensors="pt", padding=True, add_special_tokens=False,
                  truncation=True, max_length=MAX_LEN).to("cuda:0")
        g = m.generate(**enc, max_new_tokens=max_new, do_sample=False, pad_token_id=tok.pad_token_id,
                       disable_compile=True, temperature=None, top_p=None, top_k=None)
        outs += [tok.decode(x[enc.input_ids.shape[1]:], skip_special_tokens=True).strip() for x in g]
    return outs


def gen_rows(split: str) -> list[dict]:
    d = OUT_FINAL if split == "final" else OUT_DEV
    if split == "final":
        guard_final("judge_local.py FINAL generations")
    rows = []
    for p in sorted(d.glob("gen_*.jsonl")):
        rows += read_jsonl(p)
    if split == "dev":
        for p in sorted(OUT_DEV.glob("batchcheck_*.jsonl")):
            for r in read_jsonl(p):
                rows.append({**r, "set": "batchcheck", "arm": r["mode"]})
    return rows


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True, choices=["dev", "final"])
    ap.add_argument("--bs", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--identity", action="store_true",
                    help="also label identity items (OFF: a 40-item DEV probe showed Qwen3 projects its own identity, "
                         "answering Qwen|Alibaba for responses that never name themselves; logs/qwen3_identity_selfbias_probe_dev40.jsonl)")
    args = ap.parse_args()
    setup_logging(f"judge_local_{args.split}")
    torch.cuda.set_per_process_memory_fraction(0.95)
    out = (OUT_FINAL if args.split == "final" else OUT_DEV) / "labels_local_qwen3.jsonl"
    done = {r["key"] for r in read_jsonl(out)}
    rows = [r for r in gen_rows(args.split) if r["key"] not in done
            and (args.identity or r["set"] != "identity")]
    if args.limit:
        rows = rows[:args.limit]
    ref = [r for r in rows if r["set"] in REFUSAL_SETS or r["set"] == "batchcheck"]
    prio = {("refuseu_nat", "EN_nat"): 0, ("refuseu_nat", "SL_nat"): 0, ("hard", "SL_MT"): 1, ("hard", "EN_BT"): 1,
            ("refuseu_x", "SL_MT"): 2, ("refuseu_x", "EN_BT"): 2, ("hard", "EN_orig"): 3}
    ref.sort(key=lambda r: prio.get((r["set"], r["arm"]), 4))  # primary arms first, so a partial run covers them
    idr = [r for r in rows if r["set"] == "identity"] if args.identity else []
    logger.info(f"[{args.split}] local judge: {len(ref)} refusal + {len(idr)} identity rows ({len(done)} done)")
    if not rows:
        return
    m, tok = load()
    cand = first_tokens(tok, P.LABELS)
    texts = [render(tok, P.JUDGE_SYSTEM_V1, P.JUDGE_USER_V1.format(req=r["prompt_text"], resp=r["response"]))
             for r in ref]
    logger.info(f"rendered example (truncated): {texts[0][:300]!r} ... {texts[0][-80:]!r}" if texts else "no refusal rows")
    CH = 1024
    for c0 in range(0, len(ref), CH):
        chunk = ref[c0:c0 + CH]
        lps = label_logits(m, tok, texts[c0:c0 + CH], cand, args.bs)
        with out.open("a") as f:
            import json
            for r, lp in zip(chunk, lps):
                lab = P.LABELS[max(range(3), key=lambda k: lp[k])]
                f.write(json.dumps({"key": r["key"], "qwen_label": lab, "lp": [round(x, 4) for x in lp],
                                    "judge": f"{REPO}@{REV[:8]}|nf4|logits"}) + "\n")
        logger.info(f"refusal chunk {c0 + len(chunk)}/{len(ref)} written")
    if idr:
        itexts = [render(tok, P.JUDGE_SYSTEM_V1, P.ID_USER_V1.format(q=r["prompt_text"], resp=r["response"]))
                  for r in idr]
        gens = gen_short(m, tok, itexts, bs=args.bs)
        import json
        with out.open("a") as f:
            for r, g in zip(idr, gens):
                name, maker = P.parse_id(g)
                f.write(json.dumps({"key": r["key"], "qwen_raw": g[:60], "id_name": name, "id_maker": maker,
                                    "judge": f"{REPO}@{REV[:8]}|nf4|greedy12"}) + "\n")
        logger.info(f"identity rows written: {len(idr)}")
    del m
    gc.collect()
    torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
