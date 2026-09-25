#!/usr/bin/env python3
"""S3/S5/S6 GPU blocks. One model load per invocation. NF4 (double quant, bf16 compute), greedy, 128 new tokens,
empty system turn dropped (single user turn), left padding, length-sorted batches, disable_compile.

Edit = iter-1 exp4 selected Heretic LoRA (rank 3, alpha 3 -> base scaling 1). Dose = every LoraLayer.scaling = lambda
(exp8 A1 method): delta W(lambda) = lambda * delta W_saved.

Phases (comma list):
  mini       T3: template print, lambda=0 == no-adapter logits, lambda=1 manip check, throughput ladder
  regen      exp5 regeneration check (64 FINAL rows, no adapter)
  dev        DEV lambda-calibration grid on DEV EN_BT (writes results/dev/gens_<model>.jsonl)
  final      FINAL jobs in pre-registered priority order (requires frozen protocol; curve needs calibration file)
  public     ARM 3 public checkpoint block (no adapter)
  bele       Belebele accuracy + FLORES NLL/byte at lambda 0 and 1 (within) or as-is (public)
  batchcheck 16 items at lambda=1 batched vs single
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.pop("TRANSFORMERS_CACHE", None)

import torch  # noqa: E402

from common import disable_torch_native_triton  # noqa: E402

NATIVE = disable_torch_native_triton()
from loguru import logger  # noqa: E402

from common import (ADAPTERS, DATA, DEV_DIR, E5, FINAL_DIR, MAX_NEW, MODELS, RESULTS, ROOT, SEED,  # noqa: E402
                    append_jsonl, degenerate, guard_final, lex_hit, read_jsonl, setup_logging, sha1_int,
                    sha256_file, truncate)

GEMMA_TOK = ("google/gemma-3-12b-it", "96b6f1eccf38110c56df3a15bffe176da04bfd80")
TOKEN_BUDGET = int(os.environ.get("AII_TOKEN_BUDGET", "26000"))  # KV-cache tokens per batch (bs * (prompt + 128))
MAX_BS = int(os.environ.get("AII_MAX_BS", "192"))


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------------ model / adapter
def load_model(mkey: str):
    from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    spec = MODELS[mkey]
    is_local = spec["kind"] == "public"
    src = str(ROOT / spec["local_dir"]) if is_local else spec["repo"]
    rev = None if is_local else spec["revision"]
    cfg = AutoConfig.from_pretrained(src, revision=rev)
    arch = (cfg.architectures or ["?"])[0]
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             llm_int8_skip_modules=["vision_tower", "multi_modal_projector", "lm_head"])
    kw = dict(revision=rev, quantization_config=bnb, dtype=torch.bfloat16, device_map="cuda:0",
              attn_implementation=os.environ.get("AII_ATTN", "sdpa"))
    t0 = time.time()
    if "ConditionalGeneration" in arch:
        from transformers import Gemma3ForConditionalGeneration
        model = Gemma3ForConditionalGeneration.from_pretrained(src, **kw)
    else:
        model = AutoModelForCausalLM.from_pretrained(src, **kw)
    model.eval()
    # template held constant: within-study models use their own (byte-identical, exp5-verified) template; public
    # checkpoints ALWAYS use the pinned google/gemma-3-12b-it tokenizer + template.
    if spec["kind"] == "public":
        tok = AutoTokenizer.from_pretrained(GEMMA_TOK[0], revision=GEMMA_TOK[1])
    else:
        tok = AutoTokenizer.from_pretrained(spec["repo"], revision=spec["revision"])
    tok.padding_side = "left"
    info = {"arch": arch, "load_s": round(time.time() - t0, 1), "vram_gb": round(torch.cuda.memory_allocated() / 1e9, 2),
            "native_triton": NATIVE, "torch": torch.__version__, "src": src, "revision": spec["revision"]}
    logger.info(f"loaded {mkey} {info}")
    return model, tok, info


_LORA: dict = {"lam": 1.0, "handles": [], "n": 0}


def _hook(A: torch.Tensor, B: torch.Tensor):
    def fn(mod, args, out):
        lam = _LORA["lam"]
        if lam == 0.0:
            return out
        x = args[0]
        return out + lam * ((x.to(A.dtype) @ A.t()) @ B.t()).to(out.dtype)
    return fn


def attach_adapter(model, mkey: str):
    """Attach the saved LoRA (r=3, alpha=3 -> scaling 1) as forward hooks on the NF4 o_proj / down_proj modules:
    out += lambda * B(A(x)). Equivalent to peft's LoraLayer with scaling = lambda (exp8 A1 dose) but without peft's
    per-layer clone/fp32 casting (throughput). lambda = 0 skips the hook, so it is bit-identical to the base."""
    from safetensors.torch import load_file
    ad = ADAPTERS[mkey]
    cfg = json.loads((ad / "adapter_config.json").read_text())
    assert cfg["r"] == cfg["lora_alpha"], cfg
    sd = load_file(str(ad / "adapter_model.safetensors"))
    mods = dict(model.named_modules())
    pairs: dict = {}
    for k, v in sd.items():
        name = k.replace("base_model.model.", "", 1).rsplit(".lora_", 1)[0]
        pairs.setdefault(name, {})["A" if ".lora_A." in k else "B"] = v
    missing = [n for n in pairs if n not in mods]
    assert not missing, f"adapter targets not in model: {missing[:4]}"
    for h in _LORA["handles"]:
        h.remove()
    _LORA["handles"] = []
    for name, ab in pairs.items():
        A = ab["A"].to("cuda:0", torch.bfloat16)
        B = ab["B"].to("cuda:0", torch.bfloat16)
        _LORA["handles"].append(mods[name].register_forward_hook(_hook(A, B)))
    _LORA["n"] = len(pairs)
    assert _LORA["n"] * 2 == len(sd) == 192, (_LORA["n"], len(sd))
    info = {"adapter_dir": str(ad), "adapter_sha256": sha256_file(ad / "adapter_model.safetensors"),
            "n_tensors": len(sd), "n_lora_modules": _LORA["n"], "impl": "forward hooks, bf16, scaling = lambda",
            "peft_version_of_adapter": cfg.get("peft_version")}
    logger.info(f"adapter attached {info}")
    return model, info


def set_lambda(model, lam: float) -> None:
    _LORA["lam"] = float(lam)


class lora_off:
    """context manager: adapter disabled (lambda = 0), restored afterwards."""
    def __enter__(self):
        self.prev = _LORA["lam"]
        _LORA["lam"] = 0.0

    def __exit__(self, *a):
        _LORA["lam"] = self.prev


# ------------------------------------------------------------------ generation
def render(tok, text: str) -> str:
    return tok.apply_chat_template([{"role": "user", "content": text}], add_generation_prompt=True, tokenize=False)


def eos_ids(tok) -> list[int]:
    return sorted({tok.eos_token_id, tok.convert_tokens_to_ids("<end_of_turn>")})


@torch.inference_mode()
def generate_batch(model, tok, texts: list[str], max_new: int = MAX_NEW) -> list[dict]:
    enc = [tok(render(tok, t), add_special_tokens=False).input_ids for t in texts]
    Lm = max(len(x) for x in enc)
    pad = tok.pad_token_id if tok.pad_token_id is not None else 0
    inp = torch.tensor([[pad] * (Lm - len(x)) + x for x in enc], device="cuda:0")
    att = torch.tensor([[0] * (Lm - len(x)) + [1] * len(x) for x in enc], device="cuda:0")
    eids = eos_ids(tok)
    out = model.generate(input_ids=inp, attention_mask=att, do_sample=False, max_new_tokens=max_new,
                         eos_token_id=eids, pad_token_id=pad, top_p=None, top_k=None, temperature=None,
                         disable_compile=True)
    res = []
    for i, seq in enumerate(out[:, Lm:].tolist()):
        cut, hit = [], False
        for t in seq:
            if t in eids:
                hit = True
                break
            cut.append(t)
        raw = tok.decode(cut, skip_special_tokens=False)
        res.append({"response": tok.decode(cut, skip_special_tokens=True), "n_new_tokens": len(cut), "hit_eos": hit,
                    "prompt_len": len(enc[i]), "template_leak": ("<start_of_turn>" in raw) or ("<end_of_turn>" in raw)})
    return res


class Runner:
    def __init__(self, model, tok, mkey: str, bs: int, edit_source: str, deadline: float | None):
        self.model, self.tok, self.mkey, self.bs = model, tok, mkey, bs
        self.edit_source, self.deadline = edit_source, deadline
        self.sha = MODELS[mkey]["revision"]

    def out_of_time(self) -> bool:
        f = RESULTS / f"deadline_{self.mkey}.txt"
        if f.exists():
            try:
                self.deadline = float(f.read_text().split()[0])
            except (ValueError, IndexError):
                pass
        return bool(self.deadline and time.time() > self.deadline)

    def run(self, items: list[dict], out_path: Path, condition: str, lam: float, tag: str) -> dict:
        """items: rows of data/items.jsonl. Appends generation rows; resumable by key."""
        keyf = lambda it: f"{it['gid']}|{self.mkey}|{condition}|{lam:g}"  # noqa: E731
        done = {r["key"] for r in read_jsonl(out_path)}
        todo = [it for it in items if keyf(it) not in done]
        logger.info(f"[{tag}] {self.mkey} {condition} lam={lam:g}: {len(todo)} to generate ({len(items) - len(todo)} done)")
        if not todo:
            return {"n": 0}
        if "lam" in condition or condition == "edit":
            set_lambda(self.model, lam)
        f = RESULTS / f"bs_{self.mkey}.txt"
        if f.exists():
            try:
                self.bs = int(f.read_text().split()[0])
            except (ValueError, IndexError):
                pass
        t0, n, bs = time.time(), 0, self.bs
        budget = TOKEN_BUDGET
        fb = RESULTS / "token_budget.txt"
        if fb.exists():
            try:
                budget = int(fb.read_text().split()[0])
            except (ValueError, IndexError):
                pass
        for x in todo:
            if "_plen" not in x:
                x["_plen"] = len(self.tok(render(self.tok, x["text"]), add_special_tokens=False).input_ids)
        todo = sorted(todo, key=lambda r: r["_plen"])
        queue, cur = [], []
        for x in todo:
            if cur and (len(cur) + 1) * (max(cur[-1]["_plen"], x["_plen"]) + MAX_NEW) > budget or len(cur) >= MAX_BS:
                queue.append(cur)
                cur = []
            cur.append(x)
        if cur:
            queue.append(cur)
        degen = 0
        while queue:
            if self.out_of_time():
                logger.warning(f"[{tag}] deadline hit after {n}; resumable")
                break
            b = queue.pop(0)
            tb = time.time()
            try:
                gens = generate_batch(self.model, self.tok, [x["text"] for x in b])
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                if len(b) == 1:
                    raise
                h = len(b) // 2
                logger.warning(f"OOM at bs={len(b)} -> halving")
                queue = [b[:h], b[h:]] + queue
                continue
            dt = time.time() - tb
            rows = []
            for x, g in zip(b, gens):
                dg = degenerate(g["response"])
                degen += dg
                rows.append({"key": keyf(x), "gid": x["gid"], "set": x["set"], "split": x["split"],
                             "item_id": x["item_id"], "pair_id": x["pair_id"], "arm": x["arm"],
                             "prompt_lang": x["prompt_lang"], "is_harmful": x.get("is_harmful"),
                             "model": self.mkey, "condition": condition, "lambda": lam,
                             "edit_source": self.edit_source if condition != "orig" else "none",
                             "prompt_text": x["text"], **g, "degenerate": dg,
                             "lex": lex_hit(g["response"], x["prompt_lang"]), "batch_size": len(b),
                             "model_sha": self.sha, "t_gen": utc(), "batch_s": round(dt, 2), "tag": tag})
            append_jsonl(out_path, rows)
            n += len(b)
            el = time.time() - t0
            if n % (4 * bs) < len(b) or not queue:
                logger.info(f"[{tag}] {n}/{len(todo)} {el:.0f}s ({n / max(el, 1e-9):.2f}/s) degen {degen / n:.3f} "
                            f"ETA {(len(todo) - n) / max(n / max(el, 1e-9), 1e-9) / 60:.1f} min")
        return {"n": n, "s": round(time.time() - t0, 1), "rate": round(n / max(time.time() - t0, 1e-9), 3)}


# ------------------------------------------------------------------ Belebele / NLL
@torch.inference_mode()
def belebele_acc(model, tok, rows: list[dict], bs: int = 16) -> dict:
    letters = ["A", "B", "C", "D"]
    lid = [tok(x, add_special_tokens=False).input_ids[-1] for x in letters]
    prompts = []
    for r in rows:
        opts = "\n".join(f"{l}. {o}" for l, o in zip(letters, r["options"]))
        u = (f"{r['passage']}\n\nQuestion: {r['question']}\n{opts}\n\nAnswer with the letter only (A, B, C or D).")
        prompts.append(render(tok, u))
    correct, preds = 0, []
    for i in range(0, len(prompts), bs):
        enc = [tok(p, add_special_tokens=False).input_ids for p in prompts[i:i + bs]]
        Lm = max(len(x) for x in enc)
        pad = tok.pad_token_id or 0
        inp = torch.tensor([[pad] * (Lm - len(x)) + x for x in enc], device="cuda:0")
        att = torch.tensor([[0] * (Lm - len(x)) + [1] * len(x) for x in enc], device="cuda:0")
        logits = model(input_ids=inp, attention_mask=att, logits_to_keep=1).logits[:, -1, :].float()
        sel = logits[:, lid]
        for j, p in enumerate(sel.argmax(-1).tolist()):
            r = rows[i + j]
            preds.append(p + 1)
            correct += int(p + 1 == r["answer"])
        del logits
    return {"n": len(rows), "acc": round(correct / max(1, len(rows)), 4), "preds": preds}


@torch.inference_mode()
def nll_per_byte(model, tok, texts: list[str], bs: int = 4) -> float:
    tot_nll, tot_bytes = 0.0, 0
    for i in range(0, len(texts), bs):
        chunk = texts[i:i + bs]
        enc = [[tok.bos_token_id] + tok(t, add_special_tokens=False).input_ids[:1023] for t in chunk]
        Lm = max(len(x) for x in enc)
        pad = tok.pad_token_id or 0
        inp = torch.tensor([x + [pad] * (Lm - len(x)) for x in enc], device="cuda:0")
        att = torch.tensor([[1] * len(x) + [0] * (Lm - len(x)) for x in enc], device="cuda:0")
        logits = model(input_ids=inp, attention_mask=att).logits.float()
        lp = torch.log_softmax(logits[:, :-1], -1)
        tgt = inp[:, 1:]
        nll = -lp.gather(-1, tgt.unsqueeze(-1)).squeeze(-1) * att[:, 1:]
        tot_nll += float(nll.sum())
        for t, x in zip(chunk, enc):
            tot_bytes += len(tok.decode(x[1:]).encode("utf-8"))
        del logits, lp
    return tot_nll / max(1, tot_bytes)


def bele_block(model, tok, mkey: str, condition: str, lam: float, adapter: bool) -> None:
    p = RESULTS / "competence.jsonl"
    done = {(r["model"], r["condition"], r["lambda"], r["lang"]) for r in read_jsonl(p)}
    if adapter:
        set_lambda(model, lam)
    bb = read_jsonl(DATA / "belebele.jsonl")
    fl = read_jsonl(DATA / "flores_passages.jsonl")
    for lang in ("en", "sl", "hu"):
        if (mkey, condition, lam, lang) in done:
            continue
        t0 = time.time()
        acc = belebele_acc(model, tok, [r for r in bb if r["lang"] == lang])
        nll = nll_per_byte(model, tok, [r["text"] for r in fl if r["lang"] == lang])
        row = {"model": mkey, "condition": condition, "lambda": lam, "lang": lang, "belebele_acc": acc["acc"],
               "belebele_n": acc["n"], "belebele_preds": acc["preds"], "nll_per_byte": round(nll, 5),
               "n_passages": sum(r["lang"] == lang for r in fl), "t": utc()}
        append_jsonl(p, [row])
        logger.info(f"competence {mkey} {condition} lam={lam} {lang}: acc {acc['acc']} nll/byte {nll:.4f} "
                    f"({time.time() - t0:.0f}s)")


# ------------------------------------------------------------------ item selection
def items_all() -> list[dict]:
    return read_jsonl(DATA / "items.jsonl")


def select(items, set_, arms, ids=None, split="FINAL", harmful=None):
    ids = set(ids) if ids is not None else None
    return [r for r in items if r["set"] == set_ and r["arm"] in arms and r["split"] == split
            and (ids is None or r["item_id"] in ids) and (harmful is None or r.get("is_harmful") == harmful)]


# ------------------------------------------------------------------ phases
def phase_mini(model, tok, mkey, runner, adapter_on, info) -> None:
    it = items_all()
    dev = select(it, "refuseu_x", ["EN_BT", "SL_MT", "L3_MT"], split="DEV")
    ids = sorted({r["item_id"] for r in dev}, key=lambda i: sha1_int(i + "mini"))[:8]
    sub = [r for r in dev if r["item_id"] in ids]
    out = {"model": mkey, "load": info, "rendered_template": render(tok, "HELLO"), "eos_ids": eos_ids(tok)}
    out["has_system_block"] = "system" in out["rendered_template"].lower()
    if adapter_on:
        # lambda=0 == no-adapter first-token logits (8 prompts)
        enc = [tok(render(tok, r["text"]), add_special_tokens=False).input_ids for r in sub[:8]]
        diffs = []
        with torch.inference_mode():
            for x in enc:
                ids_t = torch.tensor([x], device="cuda:0")
                set_lambda(model, 0.0)
                a = model(input_ids=ids_t, logits_to_keep=1).logits[0, -1].float()
                for h in _LORA["handles"]:
                    h.remove()
                b = model(input_ids=ids_t, logits_to_keep=1).logits[0, -1].float()
                attach_adapter(model, mkey)
                set_lambda(model, 1.0)
                c = model(input_ids=ids_t, logits_to_keep=1).logits[0, -1].float()
                diffs.append((float((a - b).abs().max()), float((c - b).abs().max())))
        out["lam0_vs_noadapter_maxabs"] = max(x[0] for x in diffs)
        out["lam1_vs_noadapter_maxabs_mean"] = sum(x[1] for x in diffs) / len(diffs)
        logger.info(f"lambda=0 vs no-hooks max|dlogit| = {out['lam0_vs_noadapter_maxabs']:.2e}; lambda=1 moves logits "
                    f"by {out['lam1_vs_noadapter_maxabs_mean']:.2f} (mean max|d|)")
    p = DEV_DIR / f"mini_{mkey}.jsonl"
    for lam in ((0.0, 0.3, 1.0) if adapter_on else (0.0,)):
        st = runner.run(sub, p, "lam" if adapter_on else "orig", lam, f"mini-{lam}")
        rows = [r for r in read_jsonl(p) if r["lambda"] == lam]
        out[f"lam{lam}"] = {"stats": st, "lex_by_arm": {a: sum(r["lex"] for r in rows if r["arm"] == a) for a in
                                                        ("EN_BT", "SL_MT", "L3_MT")},
                            "n_new_mean": sum(r["n_new_tokens"] for r in rows) / max(1, len(rows)),
                            "examples": [truncate(r["response"], 160) for r in rows[:3]]}
    # throughput ladder at lambda=1 (edited) on DEV EN_BT+SL_MT
    lad = {}
    if os.environ.get("AII_SKIP_LADDER") == "1":
        (DEV_DIR / f"mini_{mkey}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
        return
    pool = select(it, "refuseu_x", ["EN_BT", "SL_MT"], split="DEV")
    if adapter_on:
        set_lambda(model, 1.0)
    for bs in (64, 96):
        b = pool[:bs]
        torch.cuda.reset_peak_memory_stats()
        t0 = time.time()
        try:
            generate_batch(model, tok, [x["text"] for x in b])
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            lad[bs] = "OOM"
            break
        dt = time.time() - t0
        lad[bs] = {"s": round(dt, 1), "rate": round(bs / dt, 2),
                   "peak_gb": round(torch.cuda.max_memory_allocated() / 1e9, 1)}
        logger.info(f"ladder bs={bs}: {lad[bs]}")
    out["ladder"] = lad
    (DEV_DIR / f"mini_{mkey}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))


def phase_regen(model, tok, mkey, runner) -> None:
    """exp5 regeneration check: 32 EN_BT + 32 SL_MT exp5 FINAL rows, no adapter; compare first-128-token prefix."""
    e5 = read_jsonl(E5 / "outputs/final" / f"gen_{mkey}.jsonl")
    e5 = [r for r in e5 if r["set"] == "refuseu_x"]
    pick = []
    for arm in ("EN_BT", "SL_MT"):
        pick += sorted([r for r in e5 if r["arm"] == arm], key=lambda r: sha1_int(r["gid"] + "regen"))[:32]
    items = [{"gid": f"regen|{r['gid']}", "set": "refuseu_x", "split": "FINAL", "item_id": r["pair_id"],
              "pair_id": r["pair_id"], "arm": r["arm"], "prompt_lang": r["prompt_lang"], "text": r["prompt_text"],
              "is_harmful": True} for r in pick]
    p = DEV_DIR / f"regen_{mkey}.jsonl"
    runner.run(items, p, "orig", 0.0, "regen")
    ours = {r["gid"]: r for r in read_jsonl(p)}
    exact, lexeq, rows = 0, 0, []
    for r in pick:
        o = ours[f"regen|{r['gid']}"]
        ids5 = tok(r["response"], add_special_tokens=False).input_ids[:MAX_NEW]
        pre5 = tok.decode(ids5, skip_special_tokens=True)
        same = pre5.strip() == o["response"].strip()
        le = lex_hit(pre5, r["prompt_lang"]) == o["lex"]
        exact += same
        lexeq += le
        rows.append({"gid": r["gid"], "exact_prefix": same, "lex_equal": le})
    res = {"model": mkey, "n": len(pick), "exact_prefix_rate": exact / len(pick), "lex_equiv_rate": lexeq / len(pick),
           "gate": "exact >= 0.90 and lex_equiv == 1.0", "pass": exact / len(pick) >= 0.9 and lexeq == len(pick),
           "rows": rows}
    (DEV_DIR / f"regen_check_{mkey}.json").write_text(json.dumps(res, indent=1))
    logger.info(f"regen check {mkey}: exact {exact}/{len(pick)} lex-equal {lexeq}/{len(pick)} pass={res['pass']}")


def phase_batchcheck(model, tok, mkey, adapter_on) -> None:
    p = DEV_DIR / f"batchcheck_{mkey}.jsonl"
    if read_jsonl(p):
        return
    if adapter_on:
        set_lambda(model, 1.0)
    pool = select(items_all(), "refuseu_x", ["EN_BT", "SL_MT"], split="DEV")
    sel = sorted(pool, key=lambda r: sha1_int(r["gid"] + "bc"))[:8]
    filler = [r for r in pool if r not in sel][:48]
    batched = generate_batch(model, tok, [r["text"] for r in sel + filler])[:8]
    single = [generate_batch(model, tok, [r["text"]])[0] for r in sel]
    rows = []
    for r, a, b in zip(sel, single, batched):
        rows.append({"gid": r["gid"], "prompt_lang": r["prompt_lang"], "request": r["text"], "single": a["response"],
                     "batched": b["response"], "identical": a["response"] == b["response"],
                     "lex_single": lex_hit(a["response"], r["prompt_lang"]),
                     "lex_batched": lex_hit(b["response"], r["prompt_lang"])})
    append_jsonl(p, rows)
    logger.info(f"batchcheck {mkey}: identical {sum(r['identical'] for r in rows)}/8, lex-agree "
                f"{sum(r['lex_single'] == r['lex_batched'] for r in rows)}/8")


def phase_dev(runner, grid: list[float]) -> None:
    it = items_all()
    dev = select(it, "refuseu_x", ["EN_BT"], split="DEV")
    p = DEV_DIR / f"gens_{runner.mkey}.jsonl"
    for lam in grid:
        runner.run(dev, p, "lam", lam, f"dev-{lam}")


def final_jobs(mkey: str, proto: dict, calib: dict | None) -> list[dict]:
    """Pre-registered FINAL job order (protocol.yaml:final_jobs). Each job = (name, items, condition, lambda)."""
    it = items_all()
    man = json.loads((DATA / "split_manifest_iter3.json").read_text())
    S = proto["subsets"]
    curve = man["CURVE_rank"][:S["curve_n"]]
    hs50 = man["HARDSAFE50"][:S["hardsafe50_n"]]
    hs100 = man["HARDSAFE100"][:S["hardsafe100_n"]]
    unsafe = man["HARD_UNSAFE_rank"]
    jo = json.loads((RESULTS / "job_order.json").read_text()) if (RESULTS / "job_order.json").exists() else {}
    l3x = man["CURVE_rank"][:jo.get("l3_refuseu_n", S["l3_refuseu_n"])]
    l3_unsafe = unsafe[:jo.get("l3_hard_unsafe_n", S["l3_hard_unsafe_n"])]
    l3_safe = man["HARDSAFE50"][:jo.get("l3_hard_safe_n", S["l3_hard_safe_n"])]
    jobs = []
    cur_x = select(it, "refuseu_x", ["EN_BT", "SL_MT"], ids=curve)
    cur_h = select(it, "hard", ["EN_BT", "SL_MT"], ids=hs100)
    # J1 lambda = 1 anchor on the curve items
    jobs.append(("J1_lam1_curve_items", cur_x + cur_h, "edit", 1.0))
    # J2 FINAL lambda curve (frozen lambdas), low to high
    if calib:
        for lam in calib["lambdas"][mkey]:
            jobs.append((f"J2_curve_{lam:g}", cur_x + cur_h, "lam", float(lam)))
    # J3 lambda = 1 on the rest of RefusEU-x FINAL (RQ2 operating point)
    jobs.append(("J3_lam1_refuseu_x", select(it, "refuseu_x", ["EN_BT", "SL_MT"]), "edit", 1.0))
    # J4 lambda = 1 HARD unsafe (all 349) + HARDSAFE50 subset
    jobs.append(("J4_lam1_hard", select(it, "hard", ["EN_BT", "SL_MT"], ids=unsafe + hs50), "edit", 1.0))
    # J5 L3 at lambda = 0 and 1 (C-MOD reduced two-point)
    l3 = select(it, "refuseu_x", ["L3_MT"], ids=l3x) + select(it, "hard", ["L3_MT"], ids=l3_unsafe + l3_safe)
    jobs.append(("J5a_orig_l3", l3, "orig", 0.0))
    jobs.append(("J5b_lam1_l3", l3, "edit", 1.0))
    # J6 MT-noise control at lambda = 1: EN_orig on the curve items
    jobs.append(("J6_lam1_en_orig", select(it, "refuseu_x", ["EN_orig"], ids=curve), "edit", 1.0))
    # J7 identity at lambda = 1 (calibration check only)
    jobs.append(("J7_lam1_identity", [r for r in it if r["set"] == "identity"], "edit", 1.0))
    # J8 originals regenerated in this pipeline (only if pre-registered True)
    if proto.get("regenerate_originals", {}).get(mkey, False):
        jobs.append(("J8_orig_refuseu_x", select(it, "refuseu_x", ["EN_BT", "SL_MT"]), "orig", 0.0))
    if jo:  # timestamped amendment (results/protocol_amendments.json)
        order = jo["order"]
        jobs = sorted(jobs, key=lambda j: order.index(j[0].split("_")[0]) if j[0].split("_")[0] in order else 99)
    return jobs


def load_proto() -> dict:
    import yaml
    from common import protocol_frozen
    t0 = time.time()
    while not protocol_frozen() and time.time() - t0 < 2400:
        logger.info("waiting for protocol freeze before FINAL generation ...")
        time.sleep(20)
    guard_final("FINAL generation")
    return yaml.safe_load((ROOT / "protocol.yaml").read_text())


def load_calib() -> dict | None:
    p, s = DEV_DIR / "lambda_calibration.json", DEV_DIR / "lambda_calibration.sha256"
    if p.exists() and s.exists() and sha256_file(p) == s.read_text().split()[0]:
        return json.loads(p.read_text())
    return None


def phase_final(runner, mkey: str, adapter_on: bool, wait_calib_s: int) -> None:
    proto = load_proto()
    calib = load_calib()
    p = FINAL_DIR / f"gens_{mkey}.jsonl"
    done_jobs = set()
    t_wait0 = time.time()
    while True:
        jobs = final_jobs(mkey, proto, calib)
        pending = [j for j in jobs if j[0] not in done_jobs]
        if not pending:
            break
        for name, items, cond, lam in pending:
            if runner.out_of_time():
                return
            if cond == "orig" and adapter_on:
                with lora_off():
                    runner.run(items, p, cond, lam, name)
            else:
                runner.run(items, p, cond, lam, name)
            done_jobs.add(name)
        if calib is None:
            calib = load_calib()
            if calib is None:
                while calib is None and time.time() - t_wait0 < wait_calib_s:
                    logger.info("waiting for frozen lambda calibration ...")
                    time.sleep(30)
                    calib = load_calib()
            if calib is None:
                logger.error("no lambda calibration; curve not run")
                break


def phase_public(runner, mkey: str) -> None:
    proto = load_proto()
    S = proto["subsets"]
    it = items_all()
    man = json.loads((DATA / "split_manifest_iter3.json").read_text())
    jo = json.loads((RESULTS / "job_order.json").read_text()) if (RESULTS / "job_order.json").exists() else {}
    pn, phn = jo.get("pub_n", S["pub_n"]), jo.get("pub_hard_n", S["pub_hard_n"])
    pub = man["CURVE_rank"][:pn]
    h_u, h_s = man["HARD_UNSAFE_rank"][:phn], man["HARDSAFE50"][:phn]
    p = FINAL_DIR / f"gens_{mkey}.jsonl"
    runner.run(select(it, "refuseu_x", ["EN_BT", "SL_MT", "L3_MT"], ids=pub), p, "public", 0.0, "pub_refuseu_x")
    runner.run(select(it, "hard", ["EN_BT", "SL_MT", "L3_MT"], ids=h_u + h_s), p, "public", 0.0, "pub_hard")


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=list(MODELS))
    ap.add_argument("--phases", default="mini")
    ap.add_argument("--bs", type=int, default=64)
    ap.add_argument("--deadline_epoch", type=float, default=0.0)
    ap.add_argument("--dev_grid", default="0.1,0.2,0.3,0.4,0.5,0.6,0.8,1.0")
    ap.add_argument("--wait_calib_s", type=int, default=1800)
    args = ap.parse_args()
    setup_logging(f"gen_{args.model}")
    torch.cuda.set_per_process_memory_fraction(0.95)
    torch.manual_seed(SEED)
    phases = args.phases.split(",")
    model, tok, info = load_model(args.model)
    adapter_on = MODELS[args.model]["kind"] == "within"
    edit_source = "none"
    if adapter_on:
        model, ainfo = attach_adapter(model, args.model)
        info["adapter"] = ainfo
        edit_source = "iter1_exp4_selected_adapter"
    (RESULTS / f"load_info_{args.model}.json").write_text(json.dumps(info, indent=1))
    runner = Runner(model, tok, args.model, args.bs, edit_source, args.deadline_epoch or None)
    for ph in phases:
        t0 = time.time()
        if ph == "mini":
            phase_mini(model, tok, args.model, runner, adapter_on, info)
        elif ph == "regen":
            if adapter_on:
                with lora_off():
                    phase_regen(model, tok, args.model, runner)
            else:
                phase_regen(model, tok, args.model, runner)
        elif ph == "batchcheck":
            phase_batchcheck(model, tok, args.model, adapter_on)
        elif ph == "dev":
            phase_dev(runner, [float(x) for x in args.dev_grid.split(",")])
        elif ph == "bele":
            if adapter_on:
                with lora_off():
                    bele_block(model, tok, args.model, "orig", 0.0, False)
                bele_block(model, tok, args.model, "edit", 1.0, True)
            elif not (RESULTS / "skip_bele_public.flag").exists():
                bele_block(model, tok, args.model, "public", 0.0, False)
            else:
                logger.warning("public Belebele block skipped (amendment AM3)")
        elif ph == "final":
            phase_final(runner, args.model, adapter_on, args.wait_calib_s)
        elif ph == "public":
            phase_public(runner, args.model)
        logger.info(f"phase {ph} done in {time.time() - t0:.0f}s")
    del model
    gc.collect()
    torch.cuda.empty_cache()
    logger.info("GPU block finished; model evicted")


if __name__ == "__main__":
    main()
