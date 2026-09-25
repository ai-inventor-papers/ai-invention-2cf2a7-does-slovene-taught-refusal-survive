#!/usr/bin/env python3
"""Step 6 ($0, GPU): Llama-Guard-3-8B hazard votes with plain transformers (bf16, left-padded batched greedy decoding,
official chat template, prompt-only single user turn). Parses 'safe' | 'unsafe\\nS<k>[,S<j>]'. Extra vote only: never
part of the 'pure' definitions. Resumable (labels/llamaguard3_raw.jsonl)."""
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd
import torch
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.common import LABELS, WORK, setup_logging  # noqa: E402

setup_logging("s6_llamaguard")
REPO = "meta-llama/Llama-Guard-3-8B"


def parse(txt: str) -> dict:
    t = txt.strip()
    cats = re.findall(r"S\d{1,2}", t)
    v = "unsafe" if t.lower().startswith("unsafe") else ("safe" if t.lower().startswith("safe") else "unparsed")
    return {"lg_verdict": v, "lg_cats": cats, "lg_top": cats[0] if cats else None}


@logger.catch(reraise=True)
def main() -> None:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    ev = pd.read_parquet(WORK / "eval_items.parquet")
    calib = pd.read_parquet(WORK / "calib_items.parquet")
    hard = pd.read_parquet(WORK / "hard_mt.parquet")
    rx = pd.read_parquet(WORK / "refuseu_x_mt.parquet")
    items = pd.concat([ev[["item_id", "prompt"]].assign(set="eval"), calib[["item_id", "prompt"]].assign(set="calib"),
                       hard[["item_id", "prompt"]].assign(set="hard_en", item_id=lambda d: d.item_id + "_en"),
                       hard[["item_id", "prompt_sl"]].rename(columns={"prompt_sl": "prompt"}).assign(set="hard_sl", item_id=lambda d: d.item_id + "_sl"),
                       rx[["item_id", "prompt_sl"]].rename(columns={"prompt_sl": "prompt"}).assign(set="refuseu_x")], ignore_index=True)
    n = int(sys.argv[1]) if len(sys.argv) > 1 else len(items)
    items = items.head(n)
    cache = LABELS / "llamaguard3_raw.jsonl"
    done = {}
    if cache.exists():
        done = {json.loads(l)["key"]: json.loads(l)["raw"] for l in cache.open() if l.strip()}
    tok = AutoTokenizer.from_pretrained(REPO)
    tok.padding_side = "left"
    tok.pad_token = tok.pad_token or tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(REPO, dtype=torch.bfloat16).cuda().eval()
    todo = items[~items.item_id.isin(done)]
    texts = [tok.apply_chat_template([{"role": "user", "content": p[:4000]}], tokenize=False) for p in todo.prompt]
    order = sorted(range(len(texts)), key=lambda i: -len(texts[i]))
    logger.info(f"{len(done)} cached, {len(todo)} to classify")
    bs, i, t0 = 32, 0, time.time()
    with cache.open("a") as f:
        while i < len(order):
            idx = order[i:i + bs]
            try:
                enc = tok([texts[j] for j in idx], return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
                with torch.inference_mode():
                    out = model.generate(**enc, max_new_tokens=12, do_sample=False, pad_token_id=tok.pad_token_id)
                dec = tok.batch_decode(out[:, enc.input_ids.shape[1]:], skip_special_tokens=True)
                for j, d in zip(idx, dec):
                    k = todo.item_id.iloc[j]
                    done[k] = d
                    f.write(json.dumps({"key": k, "raw": d, "model": REPO}) + "\n")
                i += bs
                if (i // bs) % 20 == 0:
                    logger.info(f"{i}/{len(order)} in {time.time() - t0:.0f}s")
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                bs = max(1, bs // 2)
                logger.warning(f"OOM -> bs {bs}")
    out = items.assign(raw=items.item_id.map(done))
    out = pd.concat([out.reset_index(drop=True), pd.DataFrame([parse(x or "") for x in out.raw])], axis=1)
    out.drop(columns=["prompt"]).to_parquet(LABELS / "llamaguard3_votes.parquet")
    logger.info(out.groupby("set").lg_verdict.value_counts().to_dict())


if __name__ == "__main__":
    main()
