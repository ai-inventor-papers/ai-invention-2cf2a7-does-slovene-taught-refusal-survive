#!/usr/bin/env python3
"""LOCAL open-weight judge (Qwen/Qwen3-8B, non-thinking), with the frozen v2 judge prompt.

Why this exists (protocol_amendment_5.json): the run's OpenRouter budget was exhausted ($7.02 of $7.00) after 9,313
gemini labels and 113 gpt-4.1 labels, and the free-model tier is also rate-limited out (1000/day, exhausted). No paid
or free API judge is available, so every remaining row has to be judged locally at $0. The API labels that DO exist
(gpt-4.1 on DEV P5, and the blind Claude adjudication) become the validation set for this judge.

Runs on GPU, greedy, batched, resumable. Ledger: results/judge/local_ledger.jsonl (same row format as the API ledgers,
with model_id 'local:Qwen/Qwen3-8B', cost 0).

  python local_judge.py --validate     # T0 + gpt-4.1 DEV rows + Claude adjudication rows only
  python local_judge.py --all          # every unjudged generation row (resumable)
"""
from __future__ import annotations

import argparse
import gc
import json
import time
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from common import RESULTS, append_jsonl, read_jsonl, setup_logger
from judge import T0_ITEMS, _gen_rows
from judge_prompt import JUDGE_PROMPT, parse

logger = setup_logger("local_judge")
JD = RESULTS / "judge"
LED = JD / "local_ledger.jsonl"  # overridden by --ledger
MODEL_ID = "Qwen/Qwen3-8B"
MAX_NEW = 32
RESP_MAX_CHARS = 1200

ap = argparse.ArgumentParser()
ap.add_argument("--validate", action="store_true")
ap.add_argument("--all", action="store_true")
ap.add_argument("--batch", type=int, default=16)
ap.add_argument("--nf4", action="store_true", help="4-bit load (default bf16)")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--model", default=MODEL_ID)
ap.add_argument("--score", action="store_true", help="prefill-only label scoring (one forward pass, no decode loop)")
ap.add_argument("--ledger", default="")
ap.add_argument("--plan", default="", help="targeted queue: 'primary' (see JOB_PLAN) instead of --all")
ap.add_argument("--hwcheck", action="store_true", help="amendment 9: re-score 96 already-judged rows on the current GPU")
ARGS = ap.parse_args()


class LocalJudge:
    def __init__(self) -> None:
        t0 = time.time()
        self.mid = ARGS.model
        self.tok = AutoTokenizer.from_pretrained(self.mid, padding_side="left")
        kw = {"dtype": torch.bfloat16, "device_map": "cuda:0"}
        if ARGS.nf4:
            kw["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                                           bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
        self.model = AutoModelForCausalLM.from_pretrained(self.mid, **kw).eval()
        if self.tok.pad_token_id is None:
            self.tok.pad_token = self.tok.eos_token
        self.lab_ids = {}
        for name in ("REFUSE", "PARTIAL", "COMPLY"):
            ids = self.tok.encode(name, add_special_tokens=False)
            self.lab_ids[name] = ids[0]
        assert len({*self.lab_ids.values()}) == 3, f"label first-tokens collide: {self.lab_ids}"
        logger.info(f"loaded {self.mid} in {time.time() - t0:.0f}s, {torch.cuda.memory_allocated() / 1e9:.1f} GB")

    def render(self, prompt: str, response: str) -> str:
        msg = [{"role": "user", "content": JUDGE_PROMPT.format(prompt=prompt, response=response[:RESP_MAX_CHARS])}]
        # Qwen3 is a hybrid-reasoning model: judging must be non-thinking so the answer is the JSON itself.
        t = self.tok.apply_chat_template(msg, tokenize=False, add_generation_prompt=True, enable_thinking=False)
        # --score: force the JSON opening so the next token IS the label word; one forward pass, no decode loop.
        return t + '{"label": "' if ARGS.score else t

    @torch.inference_mode()
    def score(self, jobs: list[dict]) -> list[str]:
        texts = [self.render(j["prompt"], j["response"]) for j in jobs]
        enc = self.tok(texts, return_tensors="pt", padding=True, add_special_tokens=False).to("cuda:0")
        lg = self.model(**enc, logits_to_keep=1).logits[:, -1, :].float()  # last position only (identical values, no full-vocab x seq buffer)
        names = list(self.lab_ids)
        sub = lg[:, [self.lab_ids[n] for n in names]]
        pick = sub.argmax(1).tolist()
        pr = torch.softmax(sub, 1).tolist()
        return [json.dumps({"label": names[p], "late_refusal": False, "off_language": False,
                            "p": {n: round(v, 4) for n, v in zip(names, row)}}) for p, row in zip(pick, pr)]

    @torch.inference_mode()
    def batch(self, jobs: list[dict]) -> list[dict]:
        texts = [self.render(j["prompt"], j["response"]) for j in jobs]
        enc = self.tok(texts, return_tensors="pt", padding=True, add_special_tokens=False).to("cuda:0")
        out = self.model.generate(**enc, max_new_tokens=MAX_NEW, do_sample=False,
                                  pad_token_id=self.tok.pad_token_id)
        gen = out[:, enc["input_ids"].shape[1]:]
        return [self.tok.decode(g, skip_special_tokens=True) for g in gen]


def jobs_validate() -> list[dict]:
    """T0 synthetic items + every row that already has a gpt-4.1 or blind-adjudication label."""
    jobs = [{"key": f"t0|{i}", "prompt": p, "response": r, "cell": f"T0|{lg}|{exp}", "expected": exp}
            for i, (lg, p, r, exp) in enumerate(T0_ITEMS)]
    ref = {r["key"] for r in read_jsonl(JD / "gpt41_ledger.jsonl") if r.get("ok")}
    ref |= {r["key"] for r in read_jsonl(JD / "select" / "openai__gpt-4.1.jsonl") if r.get("ok")}
    ref |= {r["key"] for r in read_jsonl(RESULTS / "adjudication" / "claude_labels.jsonl")}
    seen = set()
    for r in _gen_rows_all():
        if r["key"] in ref and r["key"] not in seen:
            seen.add(r["key"])
            jobs.append(r)
    logger.info(f"validation jobs: 12 T0 + {len(seen)} rows with an API/adjudication reference label")
    return jobs


def _gen_rows_all() -> list[dict]:
    """every judgeable row, including DEV P5 (the judge-selection reference set)."""
    rows = _gen_rows()
    have = {r["key"] for r in rows}
    for m in ("gemma_it", "gams3_it"):
        for r in read_jsonl(RESULTS / m / "dev_gen.jsonl"):
            if r["key"] not in have:
                rows.append({"key": r["key"], "prompt": r["prompt_text"], "response": (r.get("prefix_text") or "") + r["continuation"],
                             "cell": f"{m}|{r['arm']}|{r['cond']}|DEV", "prio": 0, "second": False})
                have.add(r["key"])
    return rows


def run(jobs: list[dict]) -> None:
    global LED
    if ARGS.ledger:
        LED = JD / ARGS.ledger
    done = {r["key"] for r in read_jsonl(LED)}
    todo = [j for j in jobs if j["key"] not in done]
    if ARGS.limit:
        todo = todo[:ARGS.limit]
    logger.info(f"{len(jobs)} jobs, {len(todo)} to do")
    if not todo:
        return
    lj = LocalJudge()
    # length buckets keep padding small
    todo.sort(key=lambda j: (j.get("prio", 9), len(j["prompt"]) + len(j["response"])))
    t0 = time.time()
    n = 0
    for i in range(0, len(todo), ARGS.batch):
        part = todo[i:i + ARGS.batch]
        try:
            outs = lj.score(part) if ARGS.score else lj.batch(part)
        except torch.cuda.OutOfMemoryError:
            gc.collect(); torch.cuda.empty_cache()
            outs = []
            for j in part:
                outs += (lj.score([j]) if ARGS.score else lj.batch([j]))
        rows = []
        for j, o in zip(part, outs):
            p = parse(o)
            rows.append({"key": j["key"], "cell": j["cell"], "model_id": f"local:{MODEL_ID}", "ok": bool(p),
                         "status": 200, "label": p["label"] if p else None, "judge_model": lj.mid,
                         "late_refusal": p["late_refusal"] if p else None, "off_language": p["off_language"] if p else None,
                         "raw": o[:300], "cost": 0.0, "ts": time.time(), "judge_mode": "score" if ARGS.score else "generate"})
        append_jsonl(LED, rows)
        n += len(part)
        if (i // ARGS.batch) % 20 == 0:
            el = time.time() - t0
            logger.info(f"{n}/{len(todo)} rows, {n / el:.1f} rows/s, eta {(len(todo) - n) / max(n / el, 1e-9) / 60:.1f} min, "
                        f"parse-ok {np.mean([r['ok'] for r in rows]):.2f}")
    logger.info(f"done in {(time.time() - t0) / 60:.1f} min")


# Targeted judging queue (amendment 7): at the measured local-judge throughput (~1.1 rows/s on the L4) only about
# 8k of the 23k rows can be judged in the time left, so the queue is ordered by what the design needs, and the rest is
# reported as unjudged. Item set D300 for every cell, so all cells share the same items.
JOB_PLAN = [
    # (conds, arms, item set)   -- in judging order
    (("k0", "P5", "N5"), ("sl_mt", "en_bt"), "D300"),      # primary contrast + neutral specificity + conditioning
    (("k0", "P5"), ("en_orig",), "D300"),                   # MT-noise arm
    (("P10", "Pfull"), ("sl_mt", "en_bt"), "D300"),         # depth curve
    (("X5",), ("sl_mt", "en_bt"), "D300"),                  # cross-language 2x2
    (("P3", "P20"), ("sl_mt", "en_bt"), "D300"),            # rest of the curve
]


def _grid_jobs(fname: str, tag: str, prio: int) -> list[dict]:
    """amendment 9, stages 6-7: every row of the causal / collateral grid (no a=0 gating)."""
    out = []
    for m in ("gemma_it", "gams3_it"):
        for r in read_jsonl(RESULTS / m / f"{fname}.jsonl"):
            out.append({"key": r["key"], "prompt": r["prompt_text"], "response": (r["prefix_text"] or "") + r["continuation"],
                        "cell": f"{m}|{r['arm']}|{r['dir']}|{r['alpha']}|{tag}", "prio": prio, "second": False})
    return out


def jobs_plan() -> list[dict]:
    d300 = {it["item_id"] for it in read_jsonl(RESULTS.parent / "data" / "depth600.jsonl") if it.get("in_d300")}
    rows = {r["key"]: r for r in _gen_rows_all()}
    meta = {}
    for m in ("gemma_it", "gams3_it"):
        for r in read_jsonl(RESULTS / m / "final_gen.jsonl"):
            meta[r["key"]] = r
    out, seen = [], set()
    for prio, (conds, arms, _set) in enumerate(JOB_PLAN):
        for k, r in meta.items():
            if k in seen or k not in rows:
                continue
            if r["cond"] in conds and r["arm"] in arms and r["item_id"] in d300:
                j = dict(rows[k]); j["prio"] = prio
                out.append(j); seen.add(k)
    n5 = len(out)
    for j in _grid_jobs("causal", "CAUSAL", len(JOB_PLAN)) + _grid_jobs("collateral", "COLLATERAL", len(JOB_PLAN) + 1):
        if j["key"] not in seen:
            out.append(j); seen.add(j["key"])
    logger.info(f"targeted plan: {n5} rows over {len(JOB_PLAN)} stages + {len(out) - n5} causal/collateral rows (amendment 9)")
    return out


def jobs_hwcheck() -> list[dict]:
    """amendment 9: the 96 lowest sha1(key+'hwjudge') stage-1 rows already judged on the previous GPU."""
    import hashlib
    done = {r["key"] for r in read_jsonl(JD / "local8b.jsonl")}
    stage1 = [j for j in jobs_plan() if j["prio"] == 0 and j["key"] in done]
    stage1.sort(key=lambda j: hashlib.sha1((j["key"] + "hwjudge").encode()).hexdigest())
    return stage1[:96]


def main() -> None:
    if ARGS.hwcheck:
        run(jobs_hwcheck())
        return
    if ARGS.plan:
        run(jobs_plan())
        return
    if ARGS.validate:
        run(jobs_validate())
    elif ARGS.all:
        run(_gen_rows_all())
    else:
        raise SystemExit("pass --validate or --all")


if __name__ == "__main__":
    with logger.catch(reraise=True):
        main()
