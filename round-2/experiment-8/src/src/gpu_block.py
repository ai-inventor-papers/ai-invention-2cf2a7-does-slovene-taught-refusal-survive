#!/usr/bin/env python3
"""STEP 3 per-model GPU block (identical code path for both models), CONFIRM-SPEC v2.

LOAD (heretic.Model, NF4) -> CHECKS (DEV20) -> [smoke] -> 3C depth on the original model -> 3A1 lambda-scaled iter-1 Heretic
adapter -> 3A2 graded mean-projection ablation of an own-EN refusal direction (+ centred-variance random control) -> 3D C5a
(KL leakage vs centred-variance random LoRA edits) -> 3B fresh Heretic trials (seed 20260924) with an off-objective
bilingual logger.  Every phase is resumable (skips if its output file is complete).

Usage: .venv/bin/python src/gpu_block.py --model gemma_it --gpu-deadline-epoch <t> [--smoke-only]
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402

try:  # trap (a): torch 2.14 routes some ops to Triton 'native' kernels that need a C compiler (none on this pod)
    from torch._native import registry as _nr
    _nr.deregister_op_overrides(disable_dsl_names=["triton", "cutedsl", "helion", "nvmath"])
    TRITON_DEREG = "deregistered"
except (ImportError, AttributeError, RuntimeError, ValueError) as _e:
    TRITON_DEREG = f"not_deregistered:{_e}"

from common import (COMP_PREFIX, DATA, ITER1_EXP4, MODEL_ORDER, MODELS, PREFILL, REF_PREFIX, RESULTS, SEED, WS, Lexicon,  # noqa: E402
                    append_jsonl, degenerate, langid_sl, read_jsonl, setup_logger, write_jsonl)
import probe as P  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=list(MODELS))
ap.add_argument("--gpu-deadline-epoch", type=float, required=True, help="all GPU work of BOTH models must end by this time")
ap.add_argument("--smoke-only", action="store_true")
ap.add_argument("--skip-smoke", action="store_true")
ap.add_argument("--phases", default="C,A1,A2,C5a,B")
ap.add_argument("--heretic-bs", type=int, default=128)
ap.add_argument("--budget", type=int, default=0, help="override generation token budget")
ap.add_argument("--max-bs", type=int, default=128)
ap.add_argument("--wait-pid", type=int, default=0, help="block (after imports) until this PID exits")
ARGS = ap.parse_args()

M = ARGS.model
OUT = RESULTS / M
OUT.mkdir(parents=True, exist_ok=True)
DEVOUT = RESULTS / "dev" / M
DEVOUT.mkdir(parents=True, exist_ok=True)
logger = setup_logger(f"gpu_{M}")
T0 = time.time()
TIMING = json.loads((OUT / "timing.json").read_text()) if (OUT / "timing.json").exists() else {}
CHECKS = json.loads((OUT / "checks.json").read_text()) if (OUT / "checks.json").exists() else {}
AMEND = RESULTS / "protocol_amendments.json"
PROTOCOL = json.loads((WS / "protocol.json").read_text())
GRID = PROTOCOL["grids"]

import heretic.model as hm  # noqa: E402
from heretic.config import Settings  # noqa: E402
from heretic.evaluator import Evaluator  # noqa: E402
from heretic.model import AbliterationParameters, Model  # noqa: E402
from heretic.utils import load_prompts  # noqa: E402
import optuna  # noqa: E402
from optuna.samplers import TPESampler  # noqa: E402
from optuna.storages import JournalStorage  # noqa: E402
from optuna.storages.journal import JournalFileBackend  # noqa: E402
from optuna.trial import Trial  # noqa: E402

optuna.logging.set_verbosity(optuna.logging.WARNING)


def patched_generate(self, prompts, **kwargs):
    """iter-1 template patch: drop an EMPTY system turn (identically for both models); disable_compile (trap a)."""
    chats = [([{"role": "system", "content": p.system}] if p.system else []) + [{"role": "user", "content": p.user}]
             for p in prompts]
    chat_prompts = self.tokenizer.apply_chat_template(chats, add_generation_prompt=True, tokenize=False)
    if self.settings.response_prefix:
        chat_prompts = [c + self.settings.response_prefix for c in chat_prompts]
    inputs = self.tokenizer(chat_prompts, return_tensors="pt", padding=True, return_token_type_ids=False).to(
        self.model.device)
    outputs = self.model.generate(**inputs, **kwargs, pad_token_id=self.tokenizer.pad_token_id, do_sample=False,
                                  disable_compile=True)
    return inputs, outputs


hm.Model.generate = patched_generate


# ---------------------------------------------------------------------------------------------------------------
def save_state():
    (OUT / "timing.json").write_text(json.dumps(TIMING, indent=2))
    (OUT / "checks.json").write_text(json.dumps(CHECKS, indent=2, ensure_ascii=False, default=str))


def tick(name: str, t: float):
    dt = round(time.time() - t, 1)
    if name in TIMING and TIMING[name] > dt:  # resumed phase: keep the full-run timing (time-box rule reads it)
        name = f"{name}_resumed"
    TIMING[name] = dt
    logger.info(f"[time] {name}: {TIMING[name]}s  (process total {time.time() - T0:.0f}s)")
    save_state()


def amend(key: str, value: dict):
    """protocol_amendments.json entry written (and git-committed) BEFORE the affected generation."""
    a = json.loads(AMEND.read_text()) if AMEND.exists() else {}
    if key in a:
        return a[key]
    value = {**value, "timestamp_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), "written_by": M}
    a[key] = value
    AMEND.write_text(json.dumps(a, indent=2))
    try:
        subprocess.run(["git", "-C", str(WS), "add", str(AMEND)], check=False, capture_output=True)
        subprocess.run(["git", "-C", str(WS), "commit", "-q", "-m", f"protocol amendment: {key}"], check=False,
                       capture_output=True)
    except OSError as e:
        logger.warning(f"git commit of amendment failed: {e}")
    logger.info(f"AMENDMENT {key}: {value}")
    return value


def get_amend(key: str):
    a = json.loads(AMEND.read_text()) if AMEND.exists() else {}
    return a.get(key)


def write_settings() -> Settings:
    txt = (ITER1_EXP4 / "results" / "gemma_it" / "cfg" / "config.toml").read_text()
    rep = {"seed = 20260923\n": f"seed = {SEED}\n",
           "n_trials = 80": f"n_trials = {GRID['B']['n_trials']}",
           "n_startup_trials = 25": f"n_startup_trials = {GRID['B']['n_startup']}",
           "batch_size = 128  #": f"batch_size = {ARGS.heretic_bs}  #"}
    for a, b in rep.items():
        assert a in txt, a
        txt = txt.replace(a, b)
    txt = txt.replace(str(ITER1_EXP4 / "results" / "gemma_it" / "heretic_ckpt"), str(OUT / "heretic_ckpt"))
    cfgdir = OUT / "cfg"
    cfgdir.mkdir(exist_ok=True)
    (cfgdir / "config.toml").write_text(txt)
    old_argv, old_cwd = sys.argv, os.getcwd()
    sys.argv = [old_argv[0]]
    os.chdir(cfgdir)
    try:
        s = Settings(model=MODELS[M]["repo"], model_commit=MODELS[M]["revision"])
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)
    assert s.system_prompt == "" and s.seed == SEED and s.quantization.value == "bnb_4bit", s
    return s


def lora_hash(model: Model) -> str:
    h = hashlib.sha1()
    for n, p in model.model.named_parameters():
        if "lora_" in n:
            h.update(p.detach().float().cpu().numpy().tobytes())
    return h.hexdigest()


def lora_modules(model: Model):
    from peft.tuners.lora import LoraLayer
    return [(n, m) for n, m in model.model.named_modules() if isinstance(m, LoraLayer)]


# ---------------------------------------------------------------------------------------------------------------
class Ctx:
    """Everything the phases share."""

    def __init__(self, model: Model, settings: Settings):
        self.model, self.settings = model, settings
        self.tok = model.tokenizer
        self.lex = Lexicon(settings.model_extra["scorer"]["KeywordRate"]["keyword_markers"])
        self.first_ids = {}
        for lang in ("en", "sl"):
            r = sorted({self.tok(q, add_special_tokens=False)["input_ids"][0] for q in REF_PREFIX[lang]})
            c = sorted({self.tok(q, add_special_tokens=False)["input_ids"][0] for q in COMP_PREFIX[lang]})
            self.first_ids[lang] = (r, c)
        self.pre_ids = {lang: self.tok(PREFILL[lang], add_special_tokens=False)["input_ids"] for lang in ("en", "sl")}

    def enc(self, users: list[str]) -> list[list[int]]:
        return P.encode(self.tok, P.render(self.tok, users, self.settings.response_prefix))

    def s1_from_lp(self, lp: torch.Tensor, lang: str) -> list[float]:
        r, c = self.first_ids[lang]
        return (torch.logsumexp(lp[:, r], -1) - torch.logsumexp(lp[:, c], -1)).tolist()

    def gen_rows(self, seqs, meta: list[dict], max_new: int, want_s1: bool = True) -> list[dict]:
        """greedy generation + s1 (separate first-token forward) + lexicon/degeneracy/langid per row."""
        texts, _ = P.generate(self.model.model, self.tok, seqs, max_new)
        s1 = [None] * len(seqs)
        if want_s1:
            lp = P.first_token_logprobs(self.model.model, seqs)
            for lang in ("en", "sl"):
                idx = [i for i, m in enumerate(meta) if m["lang"] == lang]
                if idx:
                    vals = self.s1_from_lp(lp[idx], lang)
                    for i, v in zip(idx, vals):
                        s1[i] = v
            del lp
        rows = []
        for i, (m, t) in enumerate(zip(meta, texts)):
            n_tok = len(self.tok(t, add_special_tokens=False)["input_ids"])
            r = {**m, "model": M, "response": t, "s1": s1[i], "lex": self.lex.hit(t), "degenerate": degenerate(t),
                 "n_tokens": n_tok, "max_new": max_new}
            if m["lang"] == "sl":
                r["langid"], r["lang_ok"] = langid_sl(t)
            rows.append(r)
        return rows


def items_arms(items: list[dict], arms: list[str]):
    seq_users, meta = [], []
    for a in arms:
        for it in items:
            seq_users.append(it[a])
            meta.append({"item_id": it["item_id"], "arm": a, "lang": "sl" if a == "sl_mt" else "en"})
    return seq_users, meta


def done_count(path: Path, **filt) -> int:
    return sum(all(r.get(k) == v for k, v in filt.items()) for r in read_jsonl(path))


# ---------------------------------------------------------------------------------------------------------------
# A1: iter-1 selected adapter, linearly scaled
def load_iter1_adapter(ctx: Ctx) -> dict:
    from safetensors.torch import load_file
    sd = load_file(str(ITER1_EXP4 / "results" / M / "selected_adapter" / "adapter_model.safetensors"))
    params = dict(ctx.model.model.named_parameters())
    n_set, missing = 0, []
    for k, v in sd.items():
        name = k.replace(".lora_A.weight", ".lora_A.default.weight").replace(".lora_B.weight", ".lora_B.default.weight")
        if name not in params:
            missing.append(k)
            continue
        assert params[name].shape == v.shape, (name, params[name].shape, v.shape)
        params[name].data = v.to(params[name].device, params[name].dtype)
        n_set += 1
    assert not missing, f"adapter keys not found in model: {missing[:5]}"
    base_scaling = sorted({round(float(m.scaling["default"]), 6) for _, m in lora_modules(ctx.model)})
    return {"n_tensors_loaded": n_set, "n_in_file": len(sd), "base_scaling": base_scaling}


def set_scaling(ctx: Ctx, lam: float):
    for _, m in lora_modules(ctx.model):
        m.scaling["default"] = float(lam)


# ---------------------------------------------------------------------------------------------------------------
# A2: mean-projection ablation hooks (skip BOS and pad positions)
class Ablator:
    def __init__(self, ctx: Ctx, band: list[int]):
        self.ctx, self.band = ctx, band
        self.handles, self.skip = [], None
        self.u = None  # [d] float32
        self.c = {}  # layer -> offset (mu_l . u)
        self.s = 0.0
        self.bos = ctx.tok.bos_token_id

    def pre(self, ids, am):
        self.skip = (ids == self.bos) | (am == 0)

    def _hook(self, li):
        def fn(mod, args, kwargs):
            if self.s == 0.0 or self.u is None:
                return None
            if "hidden_states" in kwargs:
                h = kwargs["hidden_states"]
            else:
                h = args[0]
            u = self.u.to(h.device, torch.float32)
            hf = h.float()
            proj = hf @ u  # [B, T]
            delta = (proj - self.c[li]) * self.s
            if self.skip is not None and self.skip.shape[1] == h.shape[1] and self.skip.shape[0] == h.shape[0]:
                delta = delta.masked_fill(self.skip.to(h.device), 0.0)
            hn = (hf - delta[..., None] * u).to(h.dtype)
            if "hidden_states" in kwargs:
                kwargs = dict(kwargs)
                kwargs["hidden_states"] = hn
                return args, kwargs
            return (hn,) + tuple(args[1:]), kwargs
        return fn

    def attach(self):
        layers = self.ctx.model.get_layers()
        for li in self.band:
            self.handles.append(layers[li].register_forward_pre_hook(self._hook(li), with_kwargs=True))
        P.PRE_HOOK = self.pre

    def detach(self):
        for h in self.handles:
            h.remove()
        self.handles = []
        P.PRE_HOOK = None
        self.skip = None

    def set(self, u: torch.Tensor | None, mu: torch.Tensor | None, s: float):
        self.u, self.s = u, s
        self.c = {li: float(mu[li] @ u) for li in self.band} if u is not None else {}


@torch.inference_mode()
def residuals_last(ctx: Ctx, users: list[str]) -> torch.Tensor:
    """hidden_states[l] (input to decoder layer l; l = n_layers is the final norm input) at the last prompt token.
    Returns [N, L+1, d] float32 on CPU."""
    seqs = ctx.enc(users)
    out = [None] * len(seqs)
    mdl = ctx.model.model
    dev = mdl.device

    def fn(sub):
        ids, am = P._left_pad([seqs[i] for i in sub], 0, dev)
        pos = (am.cumsum(-1) - 1).clamp(min=0)
        o = mdl(input_ids=ids, attention_mask=am, position_ids=pos, output_hidden_states=True, use_cache=False,
                logits_to_keep=1)
        hs = torch.stack([h[:, -1, :].float() for h in o.hidden_states], dim=1).cpu()
        return [(i, hs[r]) for r, i in enumerate(sub)]

    for b in P._batches([len(s) for s in seqs], 1, budget=8000):
        for i, v in P._run_with_oom(fn, b):
            out[i] = v
    return torch.stack(out)


def winsorize(x: torch.Tensor, q: float = 0.995) -> torch.Tensor:
    """per-coordinate winsorization at the (1-q, q) quantiles over the sample dim (dim 0). x: [N, d]."""
    lo = torch.quantile(x, 1 - q, dim=0, keepdim=True)
    hi = torch.quantile(x, q, dim=0, keepdim=True)
    return torch.max(torch.min(x, hi), lo)


@torch.inference_mode()
def stem_nll(ctx: Ctx, users: list[str]) -> list[float]:
    """mean token NLL of the stem text itself (raw text, no chat template) - collateral damage readout."""
    mdl = ctx.model.model
    dev = mdl.device
    seqs = [ctx.tok(u, add_special_tokens=True)["input_ids"] for u in users]
    out = [None] * len(seqs)

    def fn(sub):
        L = max(len(seqs[i]) for i in sub)
        ids = torch.full((len(sub), L), ctx.tok.pad_token_id, dtype=torch.long)
        am = torch.zeros((len(sub), L), dtype=torch.long)
        for r, i in enumerate(sub):
            ids[r, :len(seqs[i])] = torch.tensor(seqs[i])
            am[r, :len(seqs[i])] = 1
        ids, am = ids.to(dev), am.to(dev)
        if P.PRE_HOOK is not None:
            P.PRE_HOOK(ids, am)
        o = mdl(input_ids=ids, attention_mask=am, use_cache=False)
        lp = F.log_softmax(o.logits[:, :-1].float(), -1)
        tgt = ids[:, 1:]
        nll = -lp.gather(-1, tgt[..., None])[..., 0]
        m = am[:, 1:].float()
        v = ((nll * m).sum(1) / m.sum(1).clamp(min=1)).tolist()
        del o, lp
        return list(zip(sub, v))

    for b in P._batches([len(s) for s in seqs], 1, budget=4000, max_bs=16):
        for i, v in P._run_with_oom(fn, b):
            out[i] = v
    return out


def kl_vs(ctx: Ctx, seqs, base_lp) -> list[float]:
    return P.kl_items(ctx.model.model, seqs, base_lp)


# =====================================================================================================
@logger.catch(reraise=True)
def main():
    if ARGS.wait_pid:
        logger.info(f"waiting for PID {ARGS.wait_pid} to exit before touching the GPU")
        while True:
            try:
                os.kill(ARGS.wait_pid, 0)
            except OSError:
                break
            time.sleep(5)
    torch.manual_seed(SEED)
    torch.cuda.set_per_process_memory_fraction(0.95)
    settings = write_settings()
    CHECKS["triton"] = TRITON_DEREG
    t = time.time()
    model = Model(settings)
    tick("load", t)
    ctx = Ctx(model, settings)
    tok = ctx.tok
    CHECKS["vram_after_load_GB"] = round(torch.cuda.memory_allocated() / 1e9, 2)
    CHECKS["n_layers"] = len(model.get_layers())
    CHECKS["components"] = model.get_abliterable_components()
    try:
        from huggingface_hub import HfApi
        CHECKS["hub_sha"] = HfApi().model_info(MODELS[M]["repo"], revision=MODELS[M]["revision"]).sha
    except Exception as e:  # noqa: BLE001
        CHECKS["hub_sha"] = f"unavailable: {e}"[:200]
    CHECKS["requested_revision"] = MODELS[M]["revision"]
    logger.info(f"loaded {M}: layers={CHECKS['n_layers']} vram={CHECKS['vram_after_load_GB']}GB sha={CHECKS['hub_sha']}")
    nL = CHECKS["n_layers"]

    P200 = read_jsonl(DATA / "probe_P200.jsonl")
    P100 = [r for r in P200 if r["in_P100"]]
    DEV = read_jsonl(DATA / "dev20.jsonl")
    H100 = read_jsonl(DATA / "harmless100.jsonl")
    sel_kl = read_jsonl(DATA / "sel_kl.jsonl")
    eval_kl = read_jsonl(DATA / "eval_kl.jsonl")
    assert len(P200) == 200 and len(P100) == 100

    # ---------------- template check ----------------
    x = P200[0]["en_orig"]
    ours = P.render(tok, [x], settings.response_prefix)[0]
    no_sys = tok.apply_chat_template([[{"role": "user", "content": x}]], add_generation_prompt=True, tokenize=False)[0]
    with_empty = tok.apply_chat_template([[{"role": "system", "content": ""}, {"role": "user", "content": x}]],
                                         add_generation_prompt=True, tokenize=False)[0]
    ids = tok(ours, return_token_type_ids=False)["input_ids"]
    CHECKS["template"] = {"rendered": ours, "sha1": hashlib.sha1(ours.encode()).hexdigest(), "equals_no_system": ours == no_sys,
                          "empty_system_changes_string": with_empty != ours, "double_bos": ids[0] == ids[1] == tok.bos_token_id,
                          "prefill_token_counts": {k: len(v) for k, v in ctx.pre_ids.items()},
                          "prefill_tokens": {k: tok.convert_ids_to_tokens(v) for k, v in ctx.pre_ids.items()}}
    logger.info(f"template: {CHECKS['template']['sha1']} no_sys_equal={ours == no_sys} prefill k_actual="
                f"{CHECKS['template']['prefill_token_counts']}")
    save_state()

    # ---------------- Heretic setup (response prefix, evaluator, residual directions: verbatim logic) ----------------
    t = time.time()
    good_prompts = load_prompts(settings, settings.good_prompts)
    bad_prompts = load_prompts(settings, settings.bad_prompts)
    if settings.response_prefix is None:
        from os.path import commonprefix
        import re
        dummy = tok.apply_chat_template([{"role": "user", "content": "This is a dummy prompt."}], add_generation_prompt=True,
                                        tokenize=False)
        for cot_init, closed in settings.chain_of_thought_skips:
            if re.search(rf"{re.escape(cot_init)}\s*$", dummy):
                settings.response_prefix = closed
                break
        if settings.response_prefix is None:
            responses = model.get_responses_batched(good_prompts[:100] + bad_prompts[:100])
            settings.response_prefix = commonprefix(responses).rstrip(" ")
    CHECKS["response_prefix"] = settings.response_prefix
    assert not settings.response_prefix, f"unexpected response prefix {settings.response_prefix!r}"
    evaluator = Evaluator(settings, model)
    CHECKS["heretic_baseline_scores"] = {n: s.value for n, s in evaluator.baseline_scores}
    rd_path = OUT / "residual_directions.pt"
    good_means = model.get_residuals_mean(good_prompts)
    bad_means = model.get_residuals_mean(bad_prompts)
    residual_directions = F.normalize(bad_means - good_means, p=2, dim=1)
    if settings.orthogonalize_direction:
        good_directions = F.normalize(good_means, p=2, dim=1)
        proj = torch.sum(residual_directions * good_directions, dim=1)
        residual_directions = F.normalize(residual_directions - proj.unsqueeze(1) * good_directions, p=2, dim=1)
    if rd_path.exists():
        # RESUME (e.g. after a pod restart on different hardware): keep the directions the earlier trials used, and log
        # how far a fresh recomputation on the current GPU drifts from them
        rd_saved = torch.load(rd_path).to(residual_directions.device, residual_directions.dtype)
        cos_r = (residual_directions * rd_saved).sum(1)
        CHECKS.setdefault("residual_directions_resume", []).append(
            {"gpu": torch.cuda.get_device_name(0), "cos_recomputed_vs_saved_min": float(cos_r.min()),
             "cos_recomputed_vs_saved_median": float(cos_r.median()), "used": "saved"})
        logger.info(f"residual directions: using saved file; recomputed-vs-saved cos min {float(cos_r.min()):.5f}")
        residual_directions = rd_saved
    else:
        torch.save(residual_directions, rd_path)
    rd1 = torch.load(ITER1_EXP4 / "results" / M / "residual_directions.pt")
    cos = (residual_directions * rd1).sum(1)
    CHECKS["residual_directions_cos_vs_iter1"] = {"min": float(cos.min()), "median": float(cos.median())}
    del good_means, bad_means
    tick("heretic_setup", t)
    logger.info(f"heretic baseline {CHECKS['heretic_baseline_scores']}; dir cos vs iter1 {CHECKS['residual_directions_cos_vs_iter1']}")

    # ---------------- base first-token log-probs (original model) for KL readouts ----------------
    t = time.time()
    model.reset_model()
    set_scaling(ctx, 1.0)
    enc = {}
    for lang, key in (("en", "en_orig"), ("sl", "sl_mt")):
        enc[("h100", lang)] = ctx.enc([h[key] for h in H100])
    for lang in ("en", "sl"):
        enc[("sel", lang)] = ctx.enc([p[lang] for p in sel_kl])
        enc[("eval", lang)] = ctx.enc([p[lang] for p in eval_kl])
    base_lp = {k: P.first_token_logprobs(model.model, v).half() for k, v in enc.items()}
    kl0 = kl_vs(ctx, enc[("h100", "en")][:16], base_lp[("h100", "en")][:16])
    CHECKS["unedited_kl_noise_floor_max"] = max(kl0)
    tick("base_lp", t)

    # ---------------- CHECKS on DEV20 ----------------
    t = time.time()
    if "batch_vs_single" not in CHECKS:
        users, meta = items_arms(DEV, ["en_orig", "sl_mt"])
        users, meta = users[:32], meta[:32]
        seqs = ctx.enc(users)
        bt, _ = P.generate(model.model, tok, seqs, 32)
        st = [P.generate(model.model, tok, [s], 32)[0][0] for s in seqs]
        CHECKS["batch_vs_single"] = {"n": 32, "max_new": 32, "token_identical": sum(a == b for a, b in zip(bt, st)),
                                     "lex_outcome_agree": sum(ctx.lex.hit(a) == ctx.lex.hit(b) for a, b in zip(bt, st)),
                                     "first40_agree": sum(a.strip()[:40] == b.strip()[:40] for a, b in zip(bt, st))}
        logger.info(f"batch-vs-single: {CHECKS['batch_vs_single']}")
        tick("check_batch_vs_single", t)

    # ---------------- throughput probe (DEV only) ----------------
    if "throughput" not in CHECKS and ARGS.budget:
        CHECKS["throughput"] = {"skipped": "budget fixed by amendment grid_override_F3 (measured on gemma_it)", "chosen": f"budget{ARGS.budget}_bs{ARGS.max_bs}_128tok_items_per_s"}
    if "throughput" not in CHECKS:
        users, meta = items_arms(DEV, ["en_orig", "sl_mt", "en_bt"])
        seqs = ctx.enc(users[:60])
        res = {}
        for budget, mbs in ((22000, 96), (14000, 64)):
            P.set_budget(budget, mbs)
            torch.cuda.synchronize()
            tt = time.time()
            P.generate(model.model, tok, seqs, 128)
            torch.cuda.synchronize()
            res[f"budget{budget}_bs{mbs}_128tok_items_per_s"] = round(len(seqs) / (time.time() - tt), 3)
        tt = time.time()
        P.set_budget(22000, 96)
        P.generate(model.model, tok, seqs, 64)
        res["budget22000_64tok_items_per_s"] = round(len(seqs) / (time.time() - tt), 3)
        res["peak_vram_GB"] = round(torch.cuda.max_memory_allocated() / 1e9, 2)
        best = max((k for k in res if k.startswith("budget") and "128tok" in k), key=lambda k: res[k])
        res["chosen"] = best
        CHECKS["throughput"] = res
        logger.info(f"throughput: {res}")
        save_state()
    b = CHECKS["throughput"]["chosen"]
    P.set_budget(int(b.split("_")[0][6:]), int(b.split("_")[1][2:]))
    if ARGS.budget:
        P.set_budget(ARGS.budget, ARGS.max_bs)
        CHECKS["generation_budget"] = {"token_budget": ARGS.budget, "max_bs": ARGS.max_bs}
    # grid overrides recorded in protocol_amendments.json (F3 cuts) BEFORE the affected FINAL generations
    gov = get_amend("grid_override_F3") or {}
    for cv in ("A1", "A2"):
        for kk, vv in gov.get(cv, {}).items():
            GRID[cv][kk] = vv

    # ---------------- mini smoke (DEV; results/dev) ----------------
    if not ARGS.skip_smoke and not (DEVOUT / "smoke_done.json").exists():
        t = time.time()
        smoke = {}
        d4 = DEV[:4]
        users, meta = items_arms(d4, ["en_bt", "sl_mt"])
        seqs = ctx.enc(users)
        r0 = ctx.gen_rows(seqs, [{**m, "curve": "smoke_orig", "step": 0.0} for m in meta], 64)
        info = load_iter1_adapter(ctx)
        set_scaling(ctx, 0.0)
        lp0 = P.first_token_logprobs(model.model, seqs)
        set_scaling(ctx, 1.0)
        r1 = ctx.gen_rows(seqs, [{**m, "curve": "smoke_lambda", "step": 1.0} for m in meta], 64)
        lp1 = P.first_token_logprobs(model.model, seqs)
        model.reset_model()
        set_scaling(ctx, 1.0)
        lpb = P.first_token_logprobs(model.model, seqs)
        smoke["adapter"] = info
        smoke["lam0_max_abs_dlogprob_vs_base"] = float((lp0 - lpb).abs().max())
        smoke["lam1_s1_differs"] = [a["s1"] for a in r1[:2]] != [a["s1"] for a in r0[:2]]
        smoke["lam1_mean_abs_dlogprob"] = float((lp1 - lpb).abs().mean())
        write_jsonl(DEVOUT / "smoke_gens.jsonl", r0 + r1)
        smoke["n_rows"] = len(r0) + len(r1)
        smoke["samples"] = [(r["arm"], r["step"], r["response"][:100]) for r in (r0[:2] + r1[:2])]
        (DEVOUT / "smoke_done.json").write_text(json.dumps(smoke, indent=2, ensure_ascii=False))
        logger.info(f"SMOKE: {json.dumps(smoke, ensure_ascii=False)[:1500]}")
        del lp0, lp1, lpb
        tick("smoke", t)
    if ARGS.smoke_only:
        logger.info("smoke only -> exit")
        return

    phases = ARGS.phases.split(",")
    # ================= 3C DEPTH (original model) =================
    if "C" in phases:
        t = time.time()
        path = OUT / "depth_orig.jsonl"
        model.reset_model()
        set_scaling(ctx, 1.0)
        if done_count(path) < 1000:
            path.unlink(missing_ok=True)
            users, meta = items_arms(P200, ["en_orig", "en_bt", "sl_mt"])
            rows = ctx.gen_rows(ctx.enc(users), [{**m, "curve": "orig", "step": 0.0, "k": 0} for m in meta], 128)
            append_jsonl(path, rows)
            users, meta = items_arms(P200, ["en_bt", "sl_mt"])
            seqs = ctx.enc(users)
            seqs = [s + ctx.pre_ids[m["lang"]] for s, m in zip(seqs, meta)]
            rows = ctx.gen_rows(seqs, [{**m, "curve": "prefill", "step": 0.0, "k": len(ctx.pre_ids[m["lang"]]),
                                        "prefill": PREFILL[m["lang"]]} for m in meta], 128)
            append_jsonl(path, rows)
        rr = read_jsonl(path)
        for arm in ("en_orig", "en_bt", "sl_mt"):
            v = [r["lex"] for r in rr if r["curve"] == "orig" and r["arm"] == arm]
            logger.info(f"C orig {arm}: lex R={np.mean(v):.3f} s1={np.mean([r['s1'] for r in rr if r['curve'] == 'orig' and r['arm'] == arm]):.2f}")
        tick("C_depth", t)

    # ================= 3A1 LAMBDA CURVE (iter-1 selected adapter, scaled) =================
    if "A1" in phases:
        t = time.time()
        path = OUT / "curve_lambda.jsonl"
        info = load_iter1_adapter(ctx)
        CHECKS["A1_adapter"] = info
        assert info["base_scaling"] == [1.0], info
        # manipulation check 1: lam = 0 reproduces the original first-token distribution (harmless EN/SL)
        set_scaling(ctx, 0.0)
        CHECKS["A1_lam0_harmless_kl_max"] = max(kl_vs(ctx, enc[("h100", "en")][:32], base_lp[("h100", "en")][:32]))
        # manipulation check 2: lam = 1 reproduces iter-1 Heretic keyword refusals on its own eval prompts
        set_scaling(ctx, 1.0)
        if "A1_lam1_heretic_scores" not in CHECKS:
            sc = evaluator.get_scores()
            ov = evaluator.get_objective_values(sc)
            names = evaluator.get_objective_names()
            CHECKS["A1_lam1_heretic_scores"] = dict(zip(names, [float(v) for v in ov]))
            ref = json.loads((ITER1_EXP4 / "results" / M / "selection_pick.json").read_text())
            CHECKS["A1_lam1_iter1_reference"] = {"refusals": ref["refusals"], "kl": ref["kl"]}
            logger.info(f"A1 lam=1 heretic scores {CHECKS['A1_lam1_heretic_scores']} vs iter-1 {CHECKS['A1_lam1_iter1_reference']}")
        save_state()
        users, meta = items_arms(P200, ["en_bt", "sl_mt"])
        seqs = ctx.enc(users)
        lam_list = list(GRID["A1"]["tier1"])
        kl_meta = []
        if get_amend("tier2_fills"):
            lam_list += list(GRID["A1"]["tier2"])
        done_steps = {r["step"] for r in read_jsonl(path) if r["arm"] in ("en_bt", "sl_mt")}
        for lam in lam_list:
            set_scaling(ctx, lam)
            if lam not in done_steps:
                tt = time.time()
                rows = ctx.gen_rows(seqs, [{**m, "curve": "lambda", "step": lam, "k": 0} for m in meta], 128)
                append_jsonl(path, rows)
                logger.info(f"A1 lam={lam}: lex EN-BT {np.mean([r['lex'] for r in rows if r['arm'] == 'en_bt']):.3f} "
                            f"SL {np.mean([r['lex'] for r in rows if r['arm'] == 'sl_mt']):.3f} "
                            f"degen {np.mean([r['degenerate'] for r in rows]):.3f} ({time.time() - tt:.0f}s)")
            kls = {lang: kl_vs(ctx, enc[("h100", lang)], base_lp[("h100", lang)]) for lang in ("en", "sl")}
            kl_meta.append({"lam": lam, "harmless_kl_en": float(np.mean(kls["en"])), "harmless_kl_sl": float(np.mean(kls["sl"]))})
        # EN-orig at lam = 1.0 (MT-noise check under edit)
        set_scaling(ctx, 1.0)
        if done_count(path, arm="en_orig") < 200:
            u2, m2 = items_arms(P200, ["en_orig"])
            append_jsonl(path, ctx.gen_rows(ctx.enc(u2), [{**m, "curve": "lambda", "step": 1.0, "k": 0} for m in m2], 128))
        # harmless over-refusal at lam in {0 (orig), 0.6, 1.2}
        hpath = OUT / "harmless_gens.jsonl"
        hdone = {(r["curve"], r["step"]) for r in read_jsonl(hpath)}
        hu, hm_ = [], []
        for h in H100:
            hu.append(h["en_orig"])
            hm_.append({"item_id": h["item_id"], "arm": "en_orig", "lang": "en"})
        for h in H100:
            hu.append(h["sl_mt"])
            hm_.append({"item_id": h["item_id"], "arm": "sl_mt", "lang": "sl"})
        hseqs = ctx.enc(hu)
        for lam in gov.get("harmless_lams", [0.0, 0.6, 1.2]):
            if ("harmless_lambda", lam) in hdone:
                continue
            set_scaling(ctx, lam)
            append_jsonl(hpath, ctx.gen_rows(hseqs, [{**m, "curve": "harmless_lambda", "step": lam, "k": 0} for m in hm_], 64))
        # extension {1.5, 2.0}: judge unavailable during the GPU block -> pre-registered lexicon proxy (amendment)
        rows12 = [r for r in read_jsonl(path) if r["step"] == 1.2 and r["arm"] == "en_bt"]
        lex12 = float(np.mean([r["lex"] for r in rows12])) if rows12 else 1.0
        ext_rule = get_amend("A1_extension_rule")
        thr = ext_rule["lex_threshold"] if ext_rule else 0.20
        CHECKS["A1_lex_en_bt_at_1.2"] = lex12
        if lex12 > thr:
            for lam in GRID["A1"]["extension"]:
                set_scaling(ctx, lam)
                if lam not in {r["step"] for r in read_jsonl(path)}:
                    rows = ctx.gen_rows(seqs, [{**m, "curve": "lambda", "step": lam, "k": 0} for m in meta], 128)
                    append_jsonl(path, rows)
                    logger.info(f"A1 EXT lam={lam}: lex EN-BT {np.mean([r['lex'] for r in rows if r['arm'] == 'en_bt']):.3f} "
                                f"degen {np.mean([r['degenerate'] for r in rows]):.3f}")
                kls = {lang: kl_vs(ctx, enc[("h100", lang)], base_lp[("h100", lang)]) for lang in ("en", "sl")}
                kl_meta.append({"lam": lam, "harmless_kl_en": float(np.mean(kls["en"])), "harmless_kl_sl": float(np.mean(kls["sl"]))})
        (OUT / "lambda_harmless_kl.json").write_text(json.dumps(kl_meta, indent=2))
        # ---- 3D C5a for the lam = 1 adapter (first-token KL on SEL/EVAL stems) ----
        set_scaling(ctx, 1.0)
        c5 = []
        for key, items in (("sel", sel_kl), ("eval", eval_kl)):
            for lang in ("en", "sl"):
                kls = kl_vs(ctx, enc[(key, lang)], base_lp[(key, lang)])
                c5 += [{"edit": "heretic_lam1", "draw": 0, "set": key, "lang": lang, "item_id": p["pair_id"], "kl": k}
                       for p, k in zip(items, kls)]
        write_jsonl(OUT / "c5a_edit.jsonl", c5)
        model.reset_model()
        set_scaling(ctx, 1.0)
        tick("A1_lambda", t)

    # ================= 3A2 GRADED OWN-EN-DIRECTION ABLATION =================
    acts_h = None
    if "A2" in phases or "C5a" in phases:
        t = time.time()
        model.reset_model()
        set_scaling(ctx, 1.0)
        cons = read_jsonl(DATA / "construct_A2.jsonl")
        hdir = read_jsonl(DATA / "harmless_dir400.jsonl")
        n = min(len(cons), len(hdir), 400)
        acts_b = residuals_last(ctx, [c["en"] for c in cons[:n]]).clone()  # [n, L+1, d]; clone: leave inference mode
        acts_h = residuals_last(ctx, [h["en"] for h in hdir[:n]]).clone()
        U, MU = [], []
        for li in range(acts_b.shape[1]):
            pooled = winsorize(torch.cat([acts_b[:, li], acts_h[:, li]], 0))
            hb, hh = pooled[:n], pooled[n:]
            U.append(F.normalize(hb.mean(0) - hh.mean(0), dim=0))
            MU.append(hh.mean(0))
            acts_h[:, li] = hh  # keep the winsorized harmless activations (random controls, C5a)
        U, MU = torch.stack(U), torch.stack(MU)
        torch.save({"U": U, "MU": MU}, OUT / "a2_directions.pt")
        del acts_b
        gc.collect()
        tick("A2_directions", t)

    if "A2" in phases:
        t = time.time()
        band = list(range(GRID["A2"]["band"][0], min(GRID["A2"]["band"][1], nL - 1) + 1))
        abl = Ablator(ctx, band)
        abl.attach()
        try:
            # ---- layer-selection RULE on DEV20 ----
            sel = get_amend(f"A2_layer_{M}")
            if sel is None:
                dev_seqs = ctx.enc([d["en_orig"] for d in DEV])
                hdev = read_jsonl(DATA / "harmless_dev32.jsonl")
                hseq = ctx.enc([h["en"] for h in hdev])
                abl.set(None, None, 0.0)
                hbase = P.first_token_logprobs(model.model, hseq)
                s1_base = float(np.mean(ctx.s1_from_lp(P.first_token_logprobs(model.model, dev_seqs), "en")))
                cands = []
                for L in GRID["A2"]["candidate_layers"]:
                    abl.set(U[L], MU, 1.0)
                    s1 = float(np.mean(ctx.s1_from_lp(P.first_token_logprobs(model.model, dev_seqs), "en")))
                    kl = float(np.mean(kl_vs(ctx, hseq, hbase)))
                    cands.append({"L": L, "dev_s1_en": s1, "harmless_kl": kl})
                    logger.info(f"A2 DEV L={L}: s1 {s1:.2f} (base {s1_base:.2f}) KL {kl:.3f}")
                ok = [c for c in cands if c["harmless_kl"] < 0.5]
                pick = min(ok, key=lambda c: c["dev_s1_en"]) if ok else min(cands, key=lambda c: c["harmless_kl"])
                sel = amend(f"A2_layer_{M}", {"L_star": pick["L"], "candidates": cands, "dev_s1_base": s1_base,
                                               "rule": "argmin DEV20 EN-orig mean s1 s.t. harmless first-token KL < 0.5 (else min KL)",
                                               "qualified": bool(ok)})
            Ls = sel["L_star"]
            u, mu = U[Ls], MU
            path = OUT / "curve_ablate.jsonl"
            users, meta = items_arms(P200, ["en_bt", "sl_mt"])
            seqs = ctx.enc(users)
            s_list = list(GRID["A2"]["tier1"]) + (list(GRID["A2"]["tier2"]) if get_amend("tier2_fills") else [])
            done_steps = {r["step"] for r in read_jsonl(path)}
            for s in s_list:
                if s in done_steps:
                    continue
                abl.set(u, mu, s)
                tt = time.time()
                rows = ctx.gen_rows(seqs, [{**m, "curve": "ablate", "step": s, "k": 0, "L_star": Ls} for m in meta], 128)
                append_jsonl(path, rows)
                logger.info(f"A2 s={s}: lex EN-BT {np.mean([r['lex'] for r in rows if r['arm'] == 'en_bt']):.3f} "
                            f"SL {np.mean([r['lex'] for r in rows if r['arm'] == 'sl_mt']):.3f} "
                            f"degen {np.mean([r['degenerate'] for r in rows]):.3f} ({time.time() - tt:.0f}s)")
            # ---- centred-variance-matched random directions ----
            rpath = OUT / "curve_ablate_rand.jsonl"
            X = acts_h[:, Ls]  # winsorized harmless activations at L*
            Xc = X - X.mean(0, keepdim=True)
            var_u = float((Xc @ u).var())
            g = torch.Generator().manual_seed(SEED)
            cands, kept = [], []
            for j in range(200):
                z = torch.randn(Xc.shape[0], generator=g)
                r = F.normalize(Xc.T @ z, dim=0)  # ~ N(0, Sigma_w) direction
                ratio = float((Xc @ r).var()) / var_u
                cands.append(ratio)
                if 0.8 <= ratio <= 1.25 and len(kept) < 3:
                    kept.append((j, r, ratio))
            match_status = "matched"
            if len(kept) < 3:
                order = sorted(range(200), key=lambda j: abs(math.log(cands[j])))
                g = torch.Generator().manual_seed(SEED)
                allr = []
                for j in range(200):
                    z = torch.randn(Xc.shape[0], generator=g)
                    allr.append(F.normalize(Xc.T @ z, dim=0))
                kept = [(j, allr[j], cands[j]) for j in order[:3]]
                match_status = "closest (no draw inside [0.8,1.25])"
            rinfo = {"var_u": var_u, "ratios_first20": cands[:20], "kept": [(j, ratio) for j, _, ratio in kept],
                     "status": match_status, "ratio_quantiles": np.quantile(cands, [0.05, 0.5, 0.95]).tolist()}
            CHECKS["A2_random_directions"] = rinfo
            logger.info(f"A2 random directions: {rinfo}")
            users_r, meta_r = items_arms(P100, ["en_bt", "sl_mt"])
            seqs_r = ctx.enc(users_r)
            rdone = {r["step"] for r in read_jsonl(rpath)}
            n_rand = int(gov.get("n_random_directions", 3))
            for j, r, ratio in kept[:n_rand]:
                if float(j) in rdone:
                    continue
                abl.set(r, mu, 1.0)
                rows = ctx.gen_rows(seqs_r, [{**m, "curve": "ablate_rand", "step": float(j), "k": 0, "var_ratio": ratio,
                                              "L_star": Ls} for m in meta_r], 128)
                append_jsonl(rpath, rows)
                logger.info(f"A2 RAND j={j}: lex EN-BT {np.mean([x['lex'] for x in rows if x['arm'] == 'en_bt']):.3f} "
                            f"SL {np.mean([x['lex'] for x in rows if x['arm'] == 'sl_mt']):.3f}")
            # ---- collateral: harmless first-token KL + stem NLL (64 eval_kl stems) for real (s=1) vs random ----
            coll = []
            abl.set(None, None, 0.0)
            nll0 = {lang: stem_nll(ctx, [p[lang] for p in eval_kl[:64]]) for lang in ("en", "sl")}
            for name, dvec in [("real_s1", u)] + [(f"rand_{j}", r) for j, r, _ in kept[:n_rand]]:
                abl.set(dvec, mu, 1.0)
                rec = {"edit": name}
                for lang in ("en", "sl"):
                    rec[f"harmless_kl_{lang}"] = float(np.mean(kl_vs(ctx, enc[("h100", lang)], base_lp[("h100", lang)])))
                    nl = stem_nll(ctx, [p[lang] for p in eval_kl[:64]])
                    rec[f"stem_nll_delta_{lang}"] = float(np.mean(np.array(nl) - np.array(nll0[lang])))
                coll.append(rec)
                logger.info(f"A2 collateral {rec}")
            (OUT / "a2_collateral.json").write_text(json.dumps({"base_nll": {k: float(np.mean(v)) for k, v in nll0.items()},
                                                                  "edits": coll}, indent=2))
        finally:
            abl.detach()
        tick("A2_ablate", t)

    # ================= 3D C5a random LoRA edits =================
    if "C5a" in phases and not (OUT / "c5a_rand.jsonl").exists():
        t = time.time()
        pick = json.loads((ITER1_EXP4 / "results" / M / "selection_pick.json").read_text())
        params = {k: AbliterationParameters(**v) for k, v in pick["parameters"].items()}
        rd1 = torch.load(ITER1_EXP4 / "results" / M / "residual_directions.pt")  # [L+1, d] (index 0 = embeddings)
        # centred variance of harmless activations along each layer's Heretic direction; hidden_states[l+1] = output of layer l
        g = torch.Generator().manual_seed(SEED + 7)
        rows = []
        meta_draws = []
        for draw in range(1, 4):
            R = torch.zeros_like(rd1)
            ratios = []
            for li in range(rd1.shape[0]):
                X = acts_h[:, li]
                Xc = X - X.mean(0, keepdim=True)
                vu = float((Xc @ rd1[li].float()).var())
                best, best_ratio = None, None
                for _ in range(50):
                    z = torch.randn(Xc.shape[0], generator=g)
                    r = F.normalize(Xc.T @ z, dim=0)
                    ratio = float((Xc @ r).var()) / max(vu, 1e-12)
                    if best is None or abs(math.log(max(ratio, 1e-12))) < abs(math.log(max(best_ratio, 1e-12))):
                        best, best_ratio = r, ratio
                    if 0.8 <= ratio <= 1.25:
                        break
                R[li] = best
                ratios.append(best_ratio)
            model.reset_model()
            model.abliterate(R, None, params)
            for key, items in (("sel", sel_kl), ("eval", eval_kl)):
                for lang in ("en", "sl"):
                    kls = kl_vs(ctx, enc[(key, lang)], base_lp[(key, lang)])
                    rows += [{"edit": "random_cv", "draw": draw, "set": key, "lang": lang, "item_id": p["pair_id"], "kl": k}
                             for p, k in zip(items, kls)]
            inb = float(np.mean([0.8 <= x <= 1.25 for x in ratios]))
            meta_draws.append({"draw": draw, "frac_layers_ratio_in_band": inb, "ratio_median": float(np.median(ratios))})
            logger.info(f"C5a random draw {draw}: in-band {inb:.2f}; mean KL EN "
                        f"{np.mean([r['kl'] for r in rows if r['draw'] == draw and r['lang'] == 'en']):.4f} SL "
                        f"{np.mean([r['kl'] for r in rows if r['draw'] == draw and r['lang'] == 'sl']):.4f}")
        write_jsonl(OUT / "c5a_rand.jsonl", rows)
        CHECKS["C5a_random_draws"] = meta_draws
        model.reset_model()
        tick("C5a", t)
    if acts_h is not None:
        del acts_h
        gc.collect()

    # ================= 3B FRESH HERETIC TRIALS =================
    if "B" in phases:
        t = time.time()
        run_trials(ctx, evaluator, residual_directions, P100)
        tick("B_trials", t)
    CHECKS["timing"] = TIMING
    save_state()
    logger.info(f"DONE {M} in {time.time() - T0:.0f}s")


# =====================================================================================================
def run_trials(ctx: Ctx, evaluator, residual_directions, P100):
    model, settings = ctx.model, ctx.settings
    journal = OUT / "heretic_study.journal"
    probe_path = OUT / "trial_probe.jsonl"
    users, meta = items_arms(P100, ["en_bt", "sl_mt"])
    seqs = ctx.enc(users)
    state = {"trial_index": 0, "t_trials": []}

    def objective(trial: Trial) -> tuple[float, ...]:
        # ---------------- verbatim Heretic objective (main.py @3521f864) ----------------
        t_start = time.perf_counter()
        state["trial_index"] += 1
        trial_index = state["trial_index"]
        trial.set_user_attr("index", trial_index)
        direction_scope = trial.suggest_categorical("direction_scope", ["global", "per layer"])
        last_layer_index = len(model.get_layers()) - 1
        direction_index = trial.suggest_float("direction_index", 0.4 * last_layer_index, 0.9 * last_layer_index)
        if direction_scope == "per layer":
            direction_index = None
        parameters = {}
        for component in model.get_abliterable_components():
            max_weight_lower_bound = -0.25 if component == "mlp.down_proj" else 0.8
            max_weight = max(0.0, trial.suggest_float(f"{component}.max_weight", max_weight_lower_bound, 1.5))
            max_weight_position = trial.suggest_float(f"{component}.max_weight_position", 0.6 * last_layer_index,
                                                      1.0 * last_layer_index)
            min_weight = trial.suggest_float(f"{component}.min_weight", 0.0, 1.0)
            min_weight_distance = trial.suggest_float(f"{component}.min_weight_distance", 1.0,
                                                      max(0.6 * last_layer_index, 1.0))
            parameters[component] = AbliterationParameters(max_weight=max_weight, max_weight_position=max_weight_position,
                                                           min_weight=(min_weight * max_weight),
                                                           min_weight_distance=min_weight_distance)
        trial.set_user_attr("direction_index", direction_index)
        trial.set_user_attr("parameters", {k: asdict(v) for k, v in parameters.items()})
        model.reset_model()
        model.abliterate(residual_directions, direction_index, parameters)
        scores = evaluator.get_scores()
        objective_values = evaluator.get_objective_values(scores)
        trial.set_user_attr("scores", evaluator.get_paired_score_records(scores))
        t_obj = time.perf_counter() - t_start
        # ---------------- ADDED: off-objective bilingual logger (does not touch objective_values) ----------------
        hb = lora_hash(model)
        curve = "trial_f5" if trial_index > state.get("n_b", 10 ** 9) else "trial"
        rows = ctx.gen_rows(seqs, [{**m, "curve": curve, "step": float(trial_index), "k": 0} for m in meta], 64)
        assert lora_hash(model) == hb, "probe modified LoRA weights"
        for r in rows:
            r["heretic_refusals"], r["heretic_kl"] = float(objective_values[0]), float(objective_values[1])
            r["trial_number"] = trial.number
        append_jsonl(probe_path, rows)
        summ = {a: float(np.mean([r["lex"] for r in rows if r["arm"] == a])) for a in ("en_bt", "sl_mt")}
        trial.set_user_attr("bilingual_lex", summ)
        trial.set_user_attr("t_objective_s", round(t_obj, 1))
        trial.set_user_attr("t_total_s", round(time.perf_counter() - t_start, 1))
        state["t_trials"].append(time.perf_counter() - t_start)
        logger.info(f"trial {trial_index}: obj={tuple(round(v, 4) for v in objective_values)} lex={summ} "
                    f"t={time.perf_counter() - t_start:.0f}s (obj {t_obj:.0f}s)")
        return objective_values

    storage = JournalStorage(JournalFileBackend(str(journal)))
    study = optuna.create_study(
        sampler=TPESampler(n_startup_trials=settings.n_startup_trials, n_ei_candidates=128, multivariate=True,
                           seed=settings.seed),
        storage=storage, directions=evaluator.get_objective_directions(), study_name="heretic", load_if_exists=True)
    study.set_user_attr("settings", settings.model_dump_json())
    n_done = len([tr for tr in study.trials if tr.values is not None])
    if len(study.trials) != n_done:
        # a trial left RUNNING by a killed process: mark it FAIL (no other process owns this journal), so it neither
        # counts toward n_B nor shifts the trial index; its re-run gets the same index
        stale = [tr for tr in study.trials if tr.state == optuna.trial.TrialState.RUNNING]
        for tr in stale:
            study._storage.set_trial_state_values(tr._trial_id, optuna.trial.TrialState.FAIL)
        CHECKS.setdefault("B_resume", []).append({"stale_running_marked_fail": [tr.number for tr in stale],
                                                  "n_done": n_done, "gpu": torch.cuda.get_device_name(0),
                                                  "time_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())})
        logger.warning(f"journal has {len(study.trials) - n_done} unfinished trials (crash) -> marked FAIL: {[t.number for t in stale]}")
    state["trial_index"] = n_done
    # RESUME PAIRING: TPE start-up draws come from the sampler's seeded RandomSampler, whose RNG restarts at the seed in a
    # new process (it would re-draw trial 1's parameters). The other model ran the uninterrupted seeded sequence, whose
    # start-up draws are identical to this model's up to n_done (pairing check), so the remaining start-up indices are
    # enqueued with the other model's parameters, i.e. exactly what the uninterrupted sampler would have drawn. TPE's own
    # RNG is not consumed during start-up, so post-start-up proposals are unaffected by the restart.
    other = [m for m in MODEL_ORDER if m != M][0]
    other_tj = RESULTS / other / "trials.json"
    if 0 < n_done < settings.n_startup_trials and other_tj.exists():
        ot = {t["user_attrs"].get("index"): t for t in json.loads(other_tj.read_text()) if t.get("values")}
        mine = {tr.user_attrs.get("index"): tr.params for tr in study.trials if tr.values is not None}
        assert all(ot[i]["params"] == mine[i] for i in mine if i in ot), "start-up draws already differ across models"
        enq = [i for i in range(n_done + 1, settings.n_startup_trials + 1) if i in ot]
        for i in enq:
            study.enqueue_trial(ot[i]["params"], user_attrs={"resume_enqueued_from": other})
        CHECKS.setdefault("B_resume", []).append({"enqueued_startup_indices_from_" + other: enq})
        logger.info(f"resume: enqueued start-up trials {enq} with {other}'s parameters")
    nb = get_amend("n_B")
    if nb is None:
        # time-box rule (first model only): measure 2 trials, then fix n_B for BOTH models
        if n_done < 2:
            study.optimize(objective, n_trials=2 - n_done)
        t_trial = float(np.mean(state["t_trials"])) if state["t_trials"] else 150.0
        fixed_other = sum(TIMING.get(k, 0) for k in ("load", "heretic_setup", "base_lp", "check_batch_vs_single", "C_depth",
                                                        "A1_lambda", "A2_directions", "A2_ablate", "C5a"))
        t_left = ARGS.gpu_deadline_epoch - time.time()
        n_fit = int(math.floor((t_left - fixed_other - 5 * 60 + 2 * t_trial) / (2 * t_trial)))  # 2 already done here
        n_b = max(GRID["B"]["floor"], min(GRID["B"]["n_trials"], n_fit))
        nb = amend("n_B", {"n_B": n_b, "t_trial_s": round(t_trial, 1), "measured_on": M, "fixed_other_model_s_est": fixed_other,
                           "t_left_s": round(t_left), "n_fit": n_fit,
                           "rule": "n_B = min(30, floor((T_left - fixed(other model) - 5 min) / (2 t_trial))), floor 15; identical for both models; the 45-min analysis reserve is outside the GPU deadline"})
    n_b = nb["n_B"]
    state["n_b"] = n_b
    CHECKS["n_B"] = n_b
    save_state()

    def stop_cb(st, tr):
        if (RESULTS / f"STOP_B_{M}").exists():
            logger.warning("STOP file -> stopping study")
            st.stop()

    remaining = n_b - len([tr for tr in study.trials if tr.values is not None])
    if remaining > 0:
        study.optimize(objective, n_trials=remaining, callbacks=[stop_cb])
    # ---- non-interference replay of trial 1 (objective values identical with/without the logger in between) ----
    tr1 = [tr for tr in study.trials if tr.user_attrs.get("index") == 1 and tr.values is not None]
    if tr1 and "B_replay_trial1" not in CHECKS:
        tr1 = tr1[0]
        p1 = {k: AbliterationParameters(**v) for k, v in tr1.user_attrs["parameters"].items()}
        model.reset_model()
        model.abliterate(residual_directions, tr1.user_attrs["direction_index"], p1)
        ov = evaluator.get_objective_values(evaluator.get_scores())
        CHECKS["B_replay_trial1"] = {"original": list(tr1.values), "replay": [float(v) for v in ov],
                                     "identical": [round(a, 6) for a in tr1.values] == [round(float(b), 6) for b in ov]}
        logger.info(f"replay trial 1: {CHECKS['B_replay_trial1']}")
        model.reset_model()
    # ---- F5 (pre-registered fallback): extra enqueued trials = iter-1 pick parameters x max_weight scale; tagged
    # curve 'trial_f5', never pooled with the TPE draws; identical enqueued params for both models (amendment) ----
    f5 = get_amend("F5_extra_trials")
    if f5 and len(study.trials) >= n_b and not (RESULTS / f"STOP_B_{M}").exists():
        pick = json.loads((ITER1_EXP4 / "results" / M / "selection_pick.json").read_text())["parameters"]
        last = len(model.get_layers()) - 1
        todo = f5["max_weight_scales"][max(0, len(study.trials) - n_b):]
        for sc in todo:
            fixed = {"direction_scope": "per layer", "direction_index": 0.65 * last}
            for comp, pv in pick.items():
                fixed[f"{comp}.max_weight"] = pv["max_weight"] * sc
                fixed[f"{comp}.max_weight_position"] = pv["max_weight_position"]
                fixed[f"{comp}.min_weight"] = pv["min_weight"] / pv["max_weight"]  # Heretic samples min_weight as a fraction
                fixed[f"{comp}.min_weight_distance"] = pv["min_weight_distance"]
            study.enqueue_trial(fixed, user_attrs={"F5_scale": sc})
        if todo:
            logger.info(f"F5: enqueued {len(todo)} trials at max_weight scales {todo}")
            study.optimize(objective, n_trials=len(todo))
    trials = [{"number": tr.number, "values": list(tr.values) if tr.values else None, "params": tr.params,
               "user_attrs": tr.user_attrs, "state": str(tr.state)} for tr in study.trials]
    (OUT / "trials.json").write_text(json.dumps(trials, indent=1, default=str))
    CHECKS["n_trials_completed"] = sum(tr["values"] is not None for tr in trials)


if __name__ == "__main__":
    main()
