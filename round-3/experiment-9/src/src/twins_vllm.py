#!/usr/bin/env python3
"""GPU twin generation (vLLM): identical prompts/decoding to prep_data.stage_twins (Qwen3-8B greedy rewrite, thinking off;
SAFE screen by Qwen3-8B and Llama-3.1-8B-Instruct, 4 greedy tokens). Writes data/twins_raw.json; then run
`python src/prep_data.py twins_finalize` (main env) for the overlap filters, T150 and blocks."""
from __future__ import annotations

import gc
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, read_jsonl  # noqa: E402

REWRITE_PROMPT = SAFE_PROMPT = None


def main():
    import importlib.util
    spec = importlib.util.spec_from_file_location("pd_consts", str(Path(__file__).with_name("prep_data.py")))
    src = Path(__file__).with_name("prep_data.py").read_text()
    # read the frozen prompt strings without importing torch/datasets-heavy prep_data
    ns: dict = {}
    start = src.index("REWRITE_PROMPT = (")
    end = src.index("def clean(")
    exec(src[start:end], ns)  # noqa: S102 - only string constants
    rp, sp_ = ns["REWRITE_PROMPT"], ns["SAFE_PROMPT"]
    del spec
    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams
    import torch
    P = read_jsonl(DATA / "probe_P300.jsonl")[:200]

    def chat(tok, prompts, qwen):
        kw = {"enable_thinking": False} if qwen else {}
        return [tok.apply_chat_template([{"role": "user", "content": p}], add_generation_prompt=True, tokenize=False, **kw)
                for p in prompts]

    def clean_twin(t: str) -> str:
        t = (t or "").strip()
        t = t.split("\n")[0] if t.count("\n") > 2 else t.replace("\n", " ")
        t = t.strip()
        if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
            t = t[1:-1].strip()
        return t

    out = [{"source_item_id": p["item_id"]} for p in P]
    repo = "Qwen/Qwen3-8B"
    tok = AutoTokenizer.from_pretrained(repo)
    llm = LLM(model=repo, dtype="bfloat16", max_model_len=2048, gpu_memory_utilization=0.85, seed=0)
    res = llm.generate(chat(tok, [rp.format(req=p["en_orig"]) for p in P], True),
                       SamplingParams(temperature=0.0, max_tokens=110), use_tqdm=False)
    for o, r in zip(out, res):
        o["raw"] = r.outputs[0].text.strip()
    res = llm.generate(chat(tok, [sp_.format(req=clean_twin(o["raw"])) for o in out], True),
                       SamplingParams(temperature=0.0, max_tokens=4), use_tqdm=False)
    for o, r in zip(out, res):
        o.setdefault("screen_raw", {})["qwen3_8b"] = r.outputs[0].text
    del llm
    gc.collect()
    torch.cuda.empty_cache()
    repo = "meta-llama/Llama-3.1-8B-Instruct"
    tok = AutoTokenizer.from_pretrained(repo)
    llm = LLM(model=repo, dtype="bfloat16", max_model_len=2048, gpu_memory_utilization=0.85, seed=0)
    res = llm.generate(chat(tok, [sp_.format(req=clean_twin(o["raw"])) for o in out], False),
                       SamplingParams(temperature=0.0, max_tokens=4), use_tqdm=False)
    for o, r in zip(out, res):
        o["screen_raw"]["llama31_8b"] = r.outputs[0].text
    (DATA / "twins_raw.json").write_text(json.dumps({"engine": "vllm_gpu", "rows": out}, indent=0))
    print("twins_raw written", len(out))


if __name__ == "__main__":
    main()
