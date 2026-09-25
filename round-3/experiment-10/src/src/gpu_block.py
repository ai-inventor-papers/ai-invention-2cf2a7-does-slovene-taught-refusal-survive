#!/usr/bin/env python3
"""Per-model GPU block (identical code path for Gemma-3-12B-IT and GaMS3-12B-Instruct), iter-3 dir3.

S2 load NF4 + empty-system template + checks -> T1 smoke asserts -> S3 construct activations (all layers, t_post + t_inst)
-> S4 directions + geometry (+ split-half ceilings, 2000-draw item bootstrap) -> S5 DEV (layer L*, alpha grid, lambda*,
add-on band; gemini judge on DEV rows) -> S6 freeze (protocol.yaml / amendment, sha256, git commit) -> S7 TEST
(induction, add-on, collateral, RQ4 activations).  Every phase is resumable (skips if its output is complete).

PROVENANCE: load_iter1_adapter / set_scaling / lora_modules / lora_hash / Ablator / residuals / winsorize / stem_nll
are adapted from iter-2 gen_art_experiment_8/src/gpu_block.py (plain HF + peft loader instead of heretic.Model,
same NF4 config: nf4, double quant, bf16 compute; same LoRA r=3, alpha=3 on o_proj/down_proj).

Usage: .venv/bin/python src/gpu_block.py --model gemma_it [--smoke-only] [--phases acts,geom,dev,freeze,induce,addon,rq4]
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402

try:  # trap: torch 2.14 routes some ops to Triton 'native' kernels that need a C compiler
    from torch._native import registry as _nr
    _nr.deregister_op_overrides(disable_dsl_names=["triton", "cutedsl", "helion", "nvmath"])
    TRITON_DEREG = "deregistered"
except (ImportError, AttributeError, RuntimeError, ValueError) as _e:
    TRITON_DEREG = f"not_deregistered:{_e}"

from common import (ACTS, COMP_PREFIX, DATA, ITER1_EXP4, JUDGE_PROMPT_SHA, MODELS, REF_PREFIX, RESULTS, SEED, WS,  # noqa: E402
                    Lexicon, append_jsonl, row_key, degenerate, degenerate4, lang_ok, read_jsonl, setup_logger, sha256_file,
                    write_jsonl)
import probe as P  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=list(MODELS))
ap.add_argument("--smoke-only", action="store_true")
ap.add_argument("--phases", default="smoke,acts,geom,devgen")
ap.add_argument("--budget", type=int, default=26000)
ap.add_argument("--max-bs", type=int, default=128)
ap.add_argument("--n-random", type=int, default=5)
ap.add_argument("--wait-pid", type=int, default=0)
ARGS = ap.parse_args()

M = ARGS.model
OUT = RESULTS / M
OUT.mkdir(parents=True, exist_ok=True)
DEVOUT = RESULTS / "dev" / M
DEVOUT.mkdir(parents=True, exist_ok=True)
TESTOUT = RESULTS / "test" / M
TESTOUT.mkdir(parents=True, exist_ok=True)
AOUT = ACTS / M
AOUT.mkdir(parents=True, exist_ok=True)
logger = setup_logger(f"gpu_{M}")
T0 = time.time()
TIMING = json.loads((OUT / "timing.json").read_text()) if (OUT / "timing.json").exists() else {}
CHECKS = json.loads((OUT / "checks.json").read_text()) if (OUT / "checks.json").exists() else {}
MAX_NEW = 64  # all generations (the frozen judge prompt reads a 64-token response; plan deviation g extended, see protocol)
CAND_LAYERS = [16, 20, 24, 28, 32, 36]
K_GRID_FULL = [0.1, 0.2, 0.35, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0]
K_GRID = [0.1, 0.2, 0.35, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0]  # full pre-registered 10-step grid (no cut needed: measured throughput)
K_DEVCHECK_MIN = 0.2  # DEV grid check for u_SLperp was generated at K=0.2 (stricter than the plan's 0.1)
LAM_GRID = [0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0]
LAM_EXT = [0.1, 0.15, 0.25, 0.35, 0.45, 1.5]  # pre-generated extension points (admitted only if the main grid misses .5 by > .15)
ADDON_S = [0.5, 1.0, 1.5]  # full planned scale sweep


def save_state():
    (OUT / "timing.json").write_text(json.dumps(TIMING, indent=2))
    (OUT / "checks.json").write_text(json.dumps(CHECKS, indent=2, ensure_ascii=False, default=str))


def tick(name: str, t: float):
    TIMING[name] = round(time.time() - t, 1)
    logger.info(f"[time] {name}: {TIMING[name]}s  (process total {time.time() - T0:.0f}s)")
    save_state()


def git_commit(paths: list[Path], msg: str):
    try:
        subprocess.run(["git", "-C", str(WS), "add", *[str(p) for p in paths]], check=False, capture_output=True)
        r = subprocess.run(["git", "-C", str(WS), "commit", "-q", "-m", msg], check=False, capture_output=True, text=True)
        h = subprocess.run(["git", "-C", str(WS), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        logger.info(f"git commit '{msg}': rc={r.returncode} head={h}")
        return h
    except OSError as e:
        logger.warning(f"git commit failed: {e}")
        return None


# =====================================================================================================
# model loading (plain HF + peft; same NF4 + LoRA config as heretic 3521f86)
def load_model():
    from transformers import (AutoModelForCausalLM, AutoModelForImageTextToText, AutoTokenizer, BitsAndBytesConfig,
                              PretrainedConfig)
    from peft import LoraConfig, get_peft_model
    repo, rev = MODELS[M]["repo"], MODELS[M]["revision"]
    tok = AutoTokenizer.from_pretrained(repo, revision=rev)
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    cfgs = PretrainedConfig.get_config_dict(repo, revision=rev)
    cls = AutoModelForImageTextToText if any("vision_config" in c for c in cfgs) else AutoModelForCausalLM
    q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_quant_type="nf4",
                           bnb_4bit_use_double_quant=True)
    model = cls.from_pretrained(repo, revision=rev, dtype=torch.bfloat16, device_map={"": 0}, quantization_config=q)
    model.eval()
    layers = get_layers(model)
    prefix = layer_prefix(model)
    targets = []
    for i in range(len(layers)):
        targets += [f"{prefix}.{i}.self_attn.o_proj", f"{prefix}.{i}.mlp.down_proj"]
    cfg = LoraConfig(r=3, target_modules=targets, lora_alpha=3, lora_dropout=0, bias="none", task_type="CAUSAL_LM")
    model = get_peft_model(model, cfg)
    model.eval()
    return model, tok, cls.__name__


def get_layers(model):
    m = model
    for path in ("base_model.model.model.language_model.layers", "model.language_model.layers", "model.layers",
                 "base_model.model.model.layers"):
        obj = m
        ok = True
        for a in path.split("."):
            if hasattr(obj, a):
                obj = getattr(obj, a)
            else:
                ok = False
                break
        if ok:
            return obj
    raise RuntimeError("layers not found")


def layer_prefix(model) -> str:
    return "model.language_model.layers" if hasattr(model.model, "language_model") else "model.layers"


def lora_modules(model):
    from peft.tuners.lora import LoraLayer
    return [(n, m) for n, m in model.named_modules() if isinstance(m, LoraLayer)]


def lora_hash(model) -> str:
    h = hashlib.sha1()
    for n, p in model.named_parameters():
        if "lora_" in n:
            h.update(p.detach().float().cpu().numpy().tobytes())
    return h.hexdigest()


def load_adapter(model, adapter_dir: Path) -> dict:
    from safetensors.torch import load_file
    sd = load_file(str(adapter_dir / "adapter_model.safetensors"))
    params = dict(model.named_parameters())
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
    return {"n_tensors_loaded": n_set, "n_in_file": len(sd), "sha256": sha256_file(adapter_dir / "adapter_model.safetensors")}


def set_scaling(model, lam: float):
    for _, m in lora_modules(model):
        m.scaling["default"] = float(lam)


# =====================================================================================================
class Hooks:
    """One forward-pre-hook per decoder layer; state decides what it does.
    steer: add vec at layer `steer_layer` on post-instruction template positions (prefill) and every generated token.
    ablate: mean-projection neutralisation h <- h - s((h.u) - mu_l.u) u at band layers, all positions except BOS/pad."""

    def __init__(self, model, tok):
        self.layers = get_layers(model)
        self.tok = tok
        self.bos = tok.bos_token_id
        self.eot = tok.convert_tokens_to_ids("<end_of_turn>")
        self.steer_layer, self.steer_vec = None, None
        self.abl_band, self.abl_u, self.abl_c, self.abl_s = [], None, {}, 0.0
        self.skip, self.post = None, None
        self.debug = None  # dict to collect post-hook projections (smoke test)
        # per-row mode (several conditions in one batch): steer vectors [B, d] at steer_layer; ablation U [B, d], S [B],
        # C {layer: [B]} at abl_band; capture of the prefill last-position input of cap_layer
        self.rs_vec = None
        self.ra_U, self.ra_S, self.ra_C = None, None, {}
        self.cap_layer, self.captured = None, None
        self.handles = [layer.register_forward_pre_hook(self._hook(i), with_kwargs=True) for i, layer in enumerate(self.layers)]
        P.PRE_HOOK = self.pre

    def clear(self):
        self.steer_layer, self.steer_vec = None, None
        self.abl_band, self.abl_u, self.abl_c, self.abl_s = [], None, {}, 0.0
        self.rs_vec = None
        self.ra_U, self.ra_S, self.ra_C = None, None, {}
        self.cap_layer, self.captured = None, None

    def set_steer(self, layer: int, vec: torch.Tensor | None):
        self.steer_layer, self.steer_vec = layer, (vec.float().cuda() if vec is not None else None)

    def set_ablate(self, band: list[int], u: torch.Tensor, mu: dict, s: float):
        u = u.float().cuda()
        self.abl_band, self.abl_u, self.abl_s = list(band), u, float(s)
        self.abl_c = {li: float(mu[li].float().cuda() @ u) for li in band}

    def pre(self, ids, am):
        self.skip = (ids == self.bos) | (am == 0)
        # post-instruction positions: from the LAST <end_of_turn> of the prompt (user turn close) onwards
        B, T = ids.shape
        is_eot = (ids == self.eot)
        idx = torch.arange(T, device=ids.device)[None, :].expand(B, T)
        last = torch.where(is_eot, idx, torch.full_like(idx, -1)).max(dim=1).values  # [B]
        last = torch.where(last < 0, torch.full_like(last, T - 1), last)
        self.post = (idx >= last[:, None]) & (am == 1)

    def _hook(self, li):
        def fn(mod, args, kwargs):
            do_steer = self.steer_vec is not None and li == self.steer_layer
            do_abl = self.abl_u is not None and self.abl_s != 0.0 and li in self.abl_c
            do_rs = self.rs_vec is not None and li == self.steer_layer
            do_ra = self.ra_U is not None and li in self.ra_C
            do_cap = self.cap_layer is not None and li == self.cap_layer
            if not (do_steer or do_abl or do_rs or do_ra or do_cap):
                return None
            h = kwargs["hidden_states"] if "hidden_states" in kwargs else args[0]
            prefill = self.skip is not None and self.skip.shape == h.shape[:2]
            if do_cap and prefill:
                self.captured = h[:, -1, :].float()
            if not (do_steer or do_abl or do_rs or do_ra):
                return None
            hf = h.float()
            if do_ra:
                proj = (hf * self.ra_U[:, None, :]).sum(-1)
                delta = (proj - self.ra_C[li][:, None]) * self.ra_S[:, None]
                if prefill:
                    delta = delta.masked_fill(self.skip, 0.0)
                hf = hf - delta[..., None] * self.ra_U[:, None, :]
            if do_rs:
                add = self.rs_vec[:, None, :].expand_as(hf)
                if prefill:
                    add = add * self.post[..., None].float()
                hf = hf + add
            if do_abl:
                u = self.abl_u
                proj = hf @ u
                delta = (proj - self.abl_c[li]) * self.abl_s
                if prefill:
                    delta = delta.masked_fill(self.skip, 0.0)
                hf = hf - delta[..., None] * u
                if self.debug is not None:
                    cp = ((hf @ u) - self.abl_c[li]).abs()
                    if prefill:
                        cp = cp.masked_fill(self.skip, 0.0)
                    self.debug.setdefault(li, []).append(cp.max().item())
            if do_steer:
                add = self.steer_vec[None, None, :].expand_as(hf)
                if prefill:
                    add = add * self.post[..., None].float()
                hf = hf + add
            hn = hf.to(h.dtype)
            if "hidden_states" in kwargs:
                kwargs = dict(kwargs)
                kwargs["hidden_states"] = hn
                return args, kwargs
            return (hn,) + tuple(args[1:]), kwargs
        return fn


# =====================================================================================================
class Ctx:
    def __init__(self, model, tok):
        self.model, self.tok = model, tok
        self.lex = Lexicon()
        self.first_ids = {}
        for lang in ("en", "sl"):
            r = sorted({tok(q, add_special_tokens=False)["input_ids"][0] for q in REF_PREFIX[lang]})
            c = sorted({tok(q, add_special_tokens=False)["input_ids"][0] for q in COMP_PREFIX[lang]})
            self.first_ids[lang] = (r, c)

    def enc(self, users: list[str]) -> list[list[int]]:
        # identical tokenisation to exp8 / heretic (rendered template string -> tokenizer with default special tokens)
        return P.encode(self.tok, P.render(self.tok, users, None))

    def s1(self, lp: torch.Tensor, langs: list[str]) -> list[float]:
        out = []
        for i, lang in enumerate(langs):
            r, c = self.first_ids[lang]
            out.append(float(torch.logsumexp(lp[i, r], -1) - torch.logsumexp(lp[i, c], -1)))
        return out

    def gen_rows(self, seqs, meta: list[dict], max_new: int = MAX_NEW, want_s1: bool = True) -> list[dict]:
        texts, _ = P.generate(self.model, self.tok, seqs, max_new)
        s1 = [None] * len(seqs)
        if want_s1:
            lp = P.first_token_logprobs(self.model, seqs)
            s1 = self.s1(lp, [m["lang"] for m in meta])
            del lp
        rows = []
        for i, (m, t) in enumerate(zip(meta, texts)):
            lab, ok = lang_ok(t, m["lang"])
            deg_txt = degenerate(t)
            rows.append({**m, "model": M, "response": t, "s1": s1[i], "lex": self.lex.hit(t), "degenerate_text": deg_txt,
                         "degenerate4": degenerate4(t), "lang_label": lab, "lang_ok": ok,
                         "degenerate": int(deg_txt or not ok), "max_new": max_new})
        return rows


@torch.inference_mode()
def run_multi(ctx: Ctx, hooks: Hooks, seqs: list[list[int]], specs: list[dict], max_new: int = MAX_NEW,
              base_lp: torch.Tensor | None = None, cap_layer: int | None = None, max_bs: int = 256) -> list[dict]:
    """Greedy generation of many (prompt, condition) rows in shared batches. spec per row: steer: vec [d] or None
    (added at hooks.steer_layer); abl: (u [d], s, mu_dot {layer: mu_l.u}) or None (at hooks.abl band = keys of mu_dot);
    base: index into base_lp (first-token KL) or None; cap_u: direction for the manipulation-check projection or None.
    Returns per row: text, s1 (first generated token), kl_first, manip_proj."""
    mdl, tok = ctx.model, ctx.tok
    dev = mdl.device
    d = mdl.config.get_text_config().hidden_size
    res = [None] * len(seqs)

    def fn(sub):
        ids, am = P._left_pad([seqs[i] for i in sub], tok.pad_token_id, dev)
        hooks.pre(ids, am)
        B = len(sub)
        if any(specs[i].get("steer") is not None for i in sub):
            V = torch.zeros((B, d), device=dev)
            for r, i in enumerate(sub):
                if specs[i].get("steer") is not None:
                    V[r] = specs[i]["steer"].to(dev)
            hooks.rs_vec = V
        else:
            hooks.rs_vec = None
        if any(specs[i].get("abl") is not None for i in sub):
            U = torch.zeros((B, d), device=dev)
            Sv = torch.zeros(B, device=dev)
            layers_ = sorted({l for i in sub if specs[i].get("abl") is not None for l in specs[i]["abl"][2]})
            C = {l: torch.zeros(B, device=dev) for l in layers_}
            for r, i in enumerate(sub):
                a = specs[i].get("abl")
                if a is not None:
                    U[r], Sv[r] = a[0].to(dev), float(a[1])
                    for l, cval in a[2].items():
                        C[l][r] = cval
            hooks.ra_U, hooks.ra_S, hooks.ra_C = U, Sv, C
        else:
            hooks.ra_U, hooks.ra_S, hooks.ra_C = None, None, {}
        hooks.cap_layer, hooks.captured = cap_layer, None
        from transformers import LogitsProcessor, LogitsProcessorList

        class FirstCapture(LogitsProcessor):
            first = None

            def __call__(self, input_ids, scores):
                if FirstCapture.first is None:
                    FirstCapture.first = scores.float().clone()
                return scores
        FirstCapture.first = None
        out = mdl.generate(input_ids=ids, attention_mask=am, max_new_tokens=max_new, do_sample=False,
                           pad_token_id=tok.pad_token_id, return_dict_in_generate=True,
                           logits_processor=LogitsProcessorList([FirstCapture()]), disable_compile=True)
        lp = F.log_softmax(FirstCapture.first, -1)
        FirstCapture.first = None
        texts = tok.batch_decode(out.sequences[:, ids.shape[1]:], skip_special_tokens=True)
        s1 = ctx.s1(lp, [specs[i]["lang"] for i in sub])
        kl = [None] * B
        if base_lp is not None:
            bi = [specs[i].get("base") for i in sub]
            if all(b is not None for b in bi):
                bl = base_lp[bi].to(dev).float()
                kl = (bl.exp() * (bl - lp)).sum(-1).clamp(min=0).tolist()
        pr = [None] * B
        if cap_layer is not None and hooks.captured is not None:
            for r, i in enumerate(sub):
                cu = specs[i].get("cap_u")
                if cu is not None:
                    pr[r] = float(hooks.captured[r] @ cu.to(dev).float())
        hooks.rs_vec, hooks.ra_U, hooks.ra_C, hooks.cap_layer, hooks.captured = None, None, {}, None, None
        del out, lp
        return [(i, (texts[r], s1[r], kl[r], pr[r])) for r, i in enumerate(sub)]

    for bt in P._batches([len(s) for s in seqs], max_new, max_bs=max_bs):
        for i, v in P._run_with_oom(fn, bt):
            res[i] = v
    return res


def finish_rows(ctx: Ctx, metas: list[dict], outs: list) -> list[dict]:
    rows = []
    for m, (t, s1, kl, pr) in zip(metas, outs):
        lab, ok = lang_ok(t, m["lang"])
        deg_txt = degenerate(t)
        rows.append({**m, "model": M, "response": t, "s1": s1, "kl_first": kl, "manip_proj": pr, "lex": ctx.lex.hit(t),
                     "degenerate_text": deg_txt, "degenerate4": degenerate4(t), "lang_label": lab, "lang_ok": ok,
                     "degenerate": int(deg_txt or not ok), "max_new": MAX_NEW})
    return rows


def items_arms(items: list[dict], arms: list[str], extra: dict | None = None):
    users, meta = [], []
    for a in arms:
        for it in items:
            users.append(it[a])
            meta.append({"item_id": it["item_id"], "arm": a, "lang": "sl" if a == "sl_mt" else "en", **(extra or {})})
    return users, meta


@torch.inference_mode()
def residuals(ctx: Ctx, users: list[str], layers: list[int] | None = None) -> tuple[np.ndarray, np.ndarray]:
    """hidden_states[l] (input to decoder layer l) at t_post (last prompt token) and t_inst (last user-content token).
    Returns two float32 arrays [N, L, d] (fp16 overflows: Gemma massive activations > 65504)."""
    seqs = ctx.enc(users)
    mdl = ctx.model
    dev = mdl.device
    eot = ctx.tok.convert_tokens_to_ids("<end_of_turn>")
    nL = len(get_layers(mdl))
    layers = list(range(nL)) if layers is None else layers
    d = mdl.config.get_text_config().hidden_size
    out_post = np.zeros((len(seqs), len(layers), d), dtype=np.float32)
    out_inst = np.zeros((len(seqs), len(layers), d), dtype=np.float32)
    offs = []

    def fn(sub):
        ids, am = P._left_pad([seqs[i] for i in sub], 0, dev)
        if P.PRE_HOOK is not None:
            P.PRE_HOOK(ids, am)
        pos = (am.cumsum(-1) - 1).clamp(min=0)
        o = mdl(input_ids=ids, attention_mask=am, position_ids=pos, output_hidden_states=True, use_cache=False,
                logits_to_keep=1)
        T = ids.shape[1]
        is_eot = ids == eot
        idx = torch.arange(T, device=dev)[None, :].expand_as(ids)
        last_eot = torch.where(is_eot, idx, torch.full_like(idx, -1)).max(1).values
        t_inst = (last_eot - 1).clamp(min=0)
        hs = torch.stack([o.hidden_states[l] for l in layers], dim=1)  # [B, L, T, d]
        b = torch.arange(len(sub), device=dev)
        post = hs[:, :, -1, :].float().cpu().numpy()
        inst = hs[b, :, t_inst, :].float().cpu().numpy()
        res = [(i, post[r], inst[r], int(T - 1 - t_inst[r])) for r, i in enumerate(sub)]
        del o, hs
        return res

    for bt in P._batches([len(s) for s in seqs], 1, budget=6000, max_bs=32):
        for i, a, b_, off in P._run_with_oom(fn, bt):
            out_post[i], out_inst[i] = a, b_
            offs.append(off)
    CHECKS.setdefault("t_inst_offset_from_end", sorted(set(offs)))
    return out_post, out_inst


@torch.inference_mode()
def fwd_stats(ctx: Ctx, seqs, probe_layer: int, u: torch.Tensor | None, base_lp: torch.Tensor | None, langs: list[str]):
    """one prompt forward under the current hooks: first-token KL vs base_lp, s1, and the t_post projection of
    hidden_states[probe_layer] onto u (manipulation check)."""
    mdl = ctx.model
    dev = mdl.device
    out = [None] * len(seqs)

    def fn(sub):
        ids, am = P._left_pad([seqs[i] for i in sub], 0, dev)
        if P.PRE_HOOK is not None:
            P.PRE_HOOK(ids, am)
        pos = (am.cumsum(-1) - 1).clamp(min=0)
        o = mdl(input_ids=ids, attention_mask=am, position_ids=pos, output_hidden_states=u is not None, use_cache=False,
                logits_to_keep=1)
        lp = F.log_softmax(o.logits[:, -1].float(), -1)
        kl = [None] * len(sub)
        if base_lp is not None:
            bl = base_lp[sub].to(dev).float()
            kl = (bl.exp() * (bl - lp)).sum(-1).clamp(min=0).tolist()
        pr = [None] * len(sub)
        if u is not None:
            pr = (o.hidden_states[probe_layer][:, -1, :].float() @ u.float().to(dev)).tolist()
        s1 = ctx.s1(lp, [langs[i] for i in sub])
        del o, lp
        return [(i, (kl[r], pr[r], s1[r])) for r, i in enumerate(sub)]

    for bt in P._batches([len(s) for s in seqs], 1, budget=P.TOKEN_BUDGET // 2, max_bs=64):
        for i, v in P._run_with_oom(fn, bt):
            out[i] = v
    return out


@torch.inference_mode()
def stem_nll(ctx: Ctx, users: list[str]) -> list[float]:
    """mean token NLL of the raw text (no template) - collateral readout (exp8 stem_nll)."""
    mdl = ctx.model
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

    for bt in P._batches([len(s) for s in seqs], 1, budget=4000, max_bs=16):
        for i, v in P._run_with_oom(fn, bt):
            out[i] = v
    return out


# =====================================================================================================
def winsor_bounds(X: torch.Tensor, q: float = 0.995):
    return torch.quantile(X, 1 - q, dim=0), torch.quantile(X, q, dim=0)


from geomlib import orth, unit  # noqa: E402


ARMS = ["en_orig", "en_bt", "sl_mt"]


def load_construct_acts(pos: str) -> dict:
    out = {}
    for cls in ("harm", "harmless"):
        for arm in ARMS:
            out[(cls, arm)] = np.load(AOUT / f"construct_{cls}_{arm}_{pos}.npy", mmap_mode="r")
    return out


def geometry(pos: str, n_boot: int = 2000, n_split: int = 200) -> dict:
    """per-layer directions + geometry with split-half ceilings and item bootstrap (GPU, float32, winsorised)."""
    A = load_construct_acts(pos)
    nL = A[("harm", "en_bt")].shape[1]
    N = A[("harm", "en_bt")].shape[0]
    Nh = A[("harmless", "en_bt")].shape[0]
    g = torch.Generator(device="cuda").manual_seed(SEED)
    # bootstrap count matrices (same draws for every layer and for both models: identical item order)
    rng = np.random.default_rng(SEED)
    Wb = torch.tensor(np.stack([np.bincount(rng.integers(0, N, N), minlength=N) for _ in range(n_boot)]), dtype=torch.float32,
                      device="cuda") / N
    Wbh = torch.tensor(np.stack([np.bincount(rng.integers(0, Nh, Nh), minlength=Nh) for _ in range(n_boot)]),
                       dtype=torch.float32, device="cuda") / Nh
    halves = [rng.permutation(N) for _ in range(n_split)]
    halves_h = [rng.permutation(Nh) for _ in range(n_split)]
    H1 = torch.zeros((n_split, N), device="cuda")
    H1h = torch.zeros((n_split, Nh), device="cuda")
    for k in range(n_split):
        H1[k, halves[k][:N // 2]] = 1.0 / (N // 2)
        H1h[k, halves_h[k][:Nh // 2]] = 1.0 / (Nh // 2)
    H2 = (H1 == 0).float() / (N - N // 2)
    H2h = (H1h == 0).float() / (Nh - Nh // 2)
    dirs = {k: np.zeros((nL, A[("harm", "en_bt")].shape[2]), dtype=np.float32) for k in
            ("rEN", "rSL", "rENo", "dEN", "dSL", "dENo", "u_SLperp", "u_lang_raw", "u_lang", "mu_harmless_pool_raw",
             "mu_harmless_en_bt", "mu_harmless_sl_mt")}
    per_layer, boot = [], {k: np.zeros((nL, n_boot), dtype=np.float32) for k in
                           ("f", "cos_EN_SL", "rho", "dp_SL_along_rEN", "dp_SL_along_rSL", "dp_EN_along_rEN", "normratio")}
    for l in range(nL):
        X = {k: torch.tensor(np.asarray(v[:, l, :]), dtype=torch.float32, device="cuda") for k, v in A.items()}
        pool = torch.cat(list(X.values()), 0)
        lo, hi = winsor_bounds(pool)
        del pool
        Xw = {k: torch.max(torch.min(v, hi), lo) for k, v in X.items()}
        mu = {k: v.mean(0) for k, v in Xw.items()}
        dEN = mu[("harm", "en_bt")] - mu[("harmless", "en_bt")]
        dSL = mu[("harm", "sl_mt")] - mu[("harmless", "sl_mt")]
        dENo = mu[("harm", "en_orig")] - mu[("harmless", "en_orig")]
        rEN, rSL, rENo = unit(dEN), unit(dSL), unit(dENo)
        f = float((dSL @ rEN) ** 2 / (dSL @ dSL))
        rperp = dSL - (dSL @ rEN) * rEN
        u_perp = unit(rperp)
        d_lang = mu[("harmless", "sl_mt")] - mu[("harmless", "en_bt")]
        u_lang = unit(orth(d_lang.clone(), [rEN, u_perp]))

        def dprime(r, lang):
            a = Xw[("harm", lang)] @ r
            b = Xw[("harmless", lang)] @ r
            return float((a.mean() - b.mean()) / torch.sqrt((a.var() + b.var()) / 2))

        # split-half ceilings
        def dm(Wh, Whh, lang):
            return Wh @ Xw[("harm", lang)] - Whh @ Xw[("harmless", lang)]
        e1, e2 = F.normalize(dm(H1, H1h, "en_bt"), dim=1), F.normalize(dm(H2, H2h, "en_bt"), dim=1)
        s1_, s2_ = F.normalize(dm(H1, H1h, "sl_mt"), dim=1), F.normalize(dm(H2, H2h, "sl_mt"), dim=1)
        sh_en = float((e1 * e2).sum(1).mean())
        sh_sl = float((s1_ * s2_).sum(1).mean())
        sh_cross = float(((e1 * s2_).sum(1).mean() + (e2 * s1_).sum(1).mean()) / 2)
        sb = lambda r: 2 * r / (1 + r)  # noqa: E731
        # bootstrap
        bEN = Wb @ Xw[("harm", "en_bt")] - Wbh @ Xw[("harmless", "en_bt")]
        bSL = Wb @ Xw[("harm", "sl_mt")] - Wbh @ Xw[("harmless", "sl_mt")]
        nEN = bEN.norm(dim=1)
        brEN = bEN / nEN[:, None]
        brSL = F.normalize(bSL, dim=1)
        proj_SL = (bSL * brEN).sum(1)
        boot["f"][l] = (proj_SL ** 2 / (bSL * bSL).sum(1)).cpu().numpy()
        boot["cos_EN_SL"][l] = (brEN * brSL).sum(1).cpu().numpy()
        boot["rho"][l] = (proj_SL / nEN).cpu().numpy()
        boot["normratio"][l] = (bSL.norm(dim=1) / nEN).cpu().numpy()

        def bdp(R, lang, Wh, Whh):
            pa = Xw[("harm", lang)] @ R.T  # [N, B]
            pb = Xw[("harmless", lang)] @ R.T
            ma, mb = (Wh * pa.T).sum(1), (Whh * pb.T).sum(1)
            va = (Wh * (pa.T - ma[:, None]) ** 2).sum(1)
            vb = (Whh * (pb.T - mb[:, None]) ** 2).sum(1)
            return ((ma - mb) / torch.sqrt((va + vb) / 2)).cpu().numpy()
        boot["dp_SL_along_rEN"][l] = bdp(brEN, "sl_mt", Wb, Wbh)
        boot["dp_SL_along_rSL"][l] = bdp(brSL, "sl_mt", Wb, Wbh)
        boot["dp_EN_along_rEN"][l] = bdp(brEN, "en_bt", Wb, Wbh)
        del bEN, bSL, brEN, brSL
        rec = {"layer": l, "f": f, "cos_EN_SL": float(rEN @ rSL), "cos_ENo_ENbt": float(rENo @ rEN),
               "cos_ENo_SL": float(rENo @ rSL), "rho": float((dSL @ rEN) / dEN.norm()),
               "norm_dEN": float(dEN.norm()), "norm_dSL": float(dSL.norm()), "norm_dENo": float(dENo.norm()),
               "perp_share": float(rperp.norm() / dSL.norm()), "norm_dlang": float(d_lang.norm()),
               "cos_uperp_dlang": float(u_perp @ unit(d_lang)), "cos_rSL_dlang": float(rSL @ unit(d_lang)),
               "cos_rEN_dlang": float(rEN @ unit(d_lang)),
               "dp_SL_along_rEN": dprime(rEN, "sl_mt"), "dp_SL_along_rSL": dprime(rSL, "sl_mt"),
               "dp_EN_along_rEN": dprime(rEN, "en_bt"), "dp_EN_along_rSL": dprime(rSL, "en_bt"),
               "dp_SL_along_uperp": dprime(u_perp, "sl_mt"), "dp_EN_along_uperp": dprime(u_perp, "en_bt"),
               "split_half_EN": sh_en, "split_half_SL": sh_sl, "split_half_cross": sh_cross,
               "split_half_EN_SB": sb(sh_en), "split_half_SL_SB": sb(sh_sl),
               "ceiling_cos_EN_SL": float(np.sqrt(max(sb(sh_en), 0) * max(sb(sh_sl), 0))),
               "mean_resid_norm": float(Xw[("harmless", "en_bt")].norm(dim=1).mean())}
        for k in boot:
            rec[k + "_ci95"] = [float(np.percentile(boot[k][l], 2.5)), float(np.percentile(boot[k][l], 97.5))]
        per_layer.append(rec)
        dirs["rEN"][l], dirs["rSL"][l], dirs["rENo"][l] = rEN.cpu().numpy(), rSL.cpu().numpy(), rENo.cpu().numpy()
        dirs["dEN"][l], dirs["dSL"][l], dirs["dENo"][l] = dEN.cpu().numpy(), dSL.cpu().numpy(), dENo.cpu().numpy()
        dirs["u_SLperp"][l], dirs["u_lang"][l] = u_perp.cpu().numpy(), u_lang.cpu().numpy()
        dirs["u_lang_raw"][l] = unit(d_lang).cpu().numpy()
        # offsets for mean-projection: RAW (un-winsorised) pooled harmless EN-BT + SL-MT mean (the hook sees raw acts)
        dirs["mu_harmless_pool_raw"][l] = torch.cat([X[("harmless", "en_bt")], X[("harmless", "sl_mt")]]).mean(0).cpu().numpy()
        dirs["mu_harmless_en_bt"][l] = X[("harmless", "en_bt")].mean(0).cpu().numpy()
        dirs["mu_harmless_sl_mt"][l] = X[("harmless", "sl_mt")].mean(0).cpu().numpy()
        del X, Xw
        torch.cuda.empty_cache()
    del Wb, Wbh, H1, H2, H1h, H2h, g
    np.savez_compressed(OUT / f"directions_{pos}.npz", **dirs)
    np.savez_compressed(OUT / f"geometry_boot_{pos}.npz", **boot)
    (OUT / f"geometry_{pos}.json").write_text(json.dumps(per_layer, indent=1))
    return {"per_layer": per_layer}


def random_controls(Lstar: int, dirs: dict, n: int) -> tuple[np.ndarray, list[dict]]:
    """centred-variance-matched random directions at L*: v = Xc^T z (z ~ N(0, I)) ~ N(0, Sigma_w) of the winsorised pooled
    harmless EN-BT + SL-MT construct acts; orthogonalised to {rEN, u_SLperp, u_lang, rSL}; keep draws with
    Var(h.v)/Var(h.u_SLperp) in [0.8, 1.25] (exp8 method). Isotropic fallback, then closest-ratio fill (flagged)."""
    A = load_construct_acts("post")
    X = torch.cat([torch.tensor(np.asarray(A[("harmless", a)][:, Lstar, :]), dtype=torch.float32, device="cuda")
                   for a in ("en_bt", "sl_mt")])
    lo, hi = winsor_bounds(X)
    X = torch.max(torch.min(X, hi), lo)
    Xc = X - X.mean(0)
    basis = [torch.tensor(dirs[k][Lstar], device="cuda") for k in ("rEN", "u_SLperp", "u_lang", "rSL")]
    up = basis[1]
    v_ref = float((Xc @ up).var())
    kept, info, cands = [], [], []
    for mode in ("cov", "iso"):
        for k in range(3000):
            gen = torch.Generator(device="cuda").manual_seed(SEED + k + (0 if mode == "cov" else 100000))
            if mode == "cov":
                z = torch.randn(Xc.shape[0], device="cuda", generator=gen)
                v = Xc.T @ z
            else:
                v = torch.randn(Xc.shape[1], device="cuda", generator=gen)
            v = unit(orth(v, basis))
            ratio = float((Xc @ v).var()) / v_ref
            cands.append((abs(np.log(ratio)), mode, k, ratio, v))
            if 0.8 <= ratio <= 1.25:
                kept.append(v)
                info.append({"mode": mode, "seed_offset": k, "var_ratio": ratio, "flag": None})
                if len(kept) >= n:
                    break
        if len(kept) >= n:
            break
    if len(kept) < n:
        cands.sort(key=lambda c: c[0])
        for c in cands:
            if len(kept) >= n:
                break
            if any(float(c[4] @ kv) > 0.999 for kv in kept):
                continue
            kept.append(c[4])
            info.append({"mode": c[1], "seed_offset": c[2], "var_ratio": c[3], "flag": "closest_ratio_fill"})
    V = torch.stack(kept).cpu().numpy()
    for i in info:
        i["max_abs_cos_to_basis"] = None
    for j, v in enumerate(kept):
        info[j]["max_abs_cos_to_basis"] = max(abs(float(v @ b)) for b in basis)
    del X, Xc
    return V, info


# =====================================================================================================
@logger.catch(reraise=True)
def main():
    if ARGS.wait_pid:
        logger.info(f"waiting for PID {ARGS.wait_pid}")
        while True:
            try:
                os.kill(ARGS.wait_pid, 0)
            except OSError:
                break
            time.sleep(5)
    torch.manual_seed(SEED)
    torch.cuda.set_per_process_memory_fraction(0.92)
    P.set_budget(ARGS.budget, ARGS.max_bs)
    phases = ARGS.phases.split(",")
    t = time.time()
    model, tok, cls_name = load_model()
    tick("load", t)
    ctx = Ctx(model, tok)
    hooks = Hooks(model, tok)
    layers = get_layers(model)
    nL = len(layers)
    d_model = model.config.get_text_config().hidden_size
    CHECKS.update({"triton": TRITON_DEREG, "class": cls_name, "n_layers": nL, "d_model": d_model,
                   "vram_after_load_GB": round(torch.cuda.memory_allocated() / 1e9, 2), "gpu": torch.cuda.get_device_name(0)})
    adapter_dir = ITER1_EXP4 / "results" / M / "selected_adapter"
    CHECKS["adapter"] = load_adapter(model, adapter_dir)
    set_scaling(model, 0.0)
    LH = lora_hash(model)
    CHECKS["lora_hash"] = LH
    x = "How do I bake bread?"
    ours = P.render(tok, [x])[0]
    ids = tok(ours, return_token_type_ids=False)["input_ids"]
    with_empty = tok.apply_chat_template([[{"role": "system", "content": ""}, {"role": "user", "content": x}]],
                                         add_generation_prompt=True, tokenize=False)[0]
    CHECKS["template"] = {"rendered": ours, "sha1": hashlib.sha1(ours.encode()).hexdigest(),
                          "empty_system_changes_string": with_empty != ours, "double_bos": ids[0] == ids[1] == tok.bos_token_id,
                          "tail_tokens": tok.convert_ids_to_tokens(ids[-6:])}
    logger.info(f"loaded {M} ({cls_name}) layers={nL} d={d_model} vram={CHECKS['vram_after_load_GB']}GB template={CHECKS['template']}")
    save_state()

    DATA_ = {k: read_jsonl(DATA / f"{k}.jsonl") for k in
             ("construct_harm", "harmless_construct", "rq4_harmless", "induce_test", "induce_dev", "addon_harmless", "kl_dev",
              "p200_dev40", "p200_test160", "hard_dev", "hard_test")}
    for k, v in DATA_.items():
        assert len(v) > 0, k
    P200 = DATA_["p200_dev40"] + DATA_["p200_test160"]

    # ------------------------------------------------ base log-probs (original model) for KL
    set_scaling(model, 0.0)
    hooks.clear()
    kl_users = {lang: [r[a] for r in DATA_["kl_dev"]] for lang, a in (("en", "en_bt"), ("sl", "sl_mt"))}
    kl_seqs = {lang: ctx.enc(v) for lang, v in kl_users.items()}
    base_kl_lp = {lang: P.first_token_logprobs(model, s) for lang, s in kl_seqs.items()}

    # ------------------------------------------------ T1 smoke (asserts)
    prev_smoke = json.loads((DEVOUT / "smoke.json").read_text()) if (DEVOUT / "smoke.json").exists() else {}
    if "smoke" in phases and not prev_smoke.get("passed"):
        t = time.time()
        sm = {}
        users = [r["en_bt"] for r in DATA_["induce_dev"][:2]] + [r["sl_mt"] for r in DATA_["induce_dev"][:2]]
        seqs = ctx.enc(users)
        lp0 = P.first_token_logprobs(model, seqs)
        u = F.normalize(torch.randn(d_model, generator=torch.Generator().manual_seed(1)), dim=0)
        mu = {l: torch.zeros(d_model) for l in range(nL)}
        hooks.set_steer(24, u * 0.0)
        hooks.set_ablate([20, 24], u, mu, 0.0)
        lpa = P.first_token_logprobs(model, seqs)
        sm["a_zero_hooks_max_abs_dlogprob"] = float((lpa - lp0).abs().max())
        hooks.clear()
        projs = []
        for a in (0.0, 20.0, 40.0, 80.0):
            hooks.set_steer(24, u * a)
            st = fwd_stats(ctx, seqs, 28, u, None, ["en", "en", "sl", "sl"])
            projs.append(float(np.mean([s[1] for s in st])))
        hooks.clear()
        sm["b_steer_proj_L+4"] = projs
        sm["b_monotone"] = all(projs[i] < projs[i + 1] for i in range(len(projs) - 1))
        hooks.debug = {}
        mu_real = {l: torch.randn(d_model, generator=torch.Generator().manual_seed(l)) for l in range(nL)}
        hooks.set_ablate([20, 21], u, mu_real, 1.0)
        P.first_token_logprobs(model, seqs)
        sm["c_ablate_post_hook_max_abs_centered_proj"] = {k: max(v) for k, v in hooks.debug.items()}
        hooks.debug = None
        hooks.clear()
        # d: BOS untouched -> the BOS row of the pre-hook skip mask
        ids_, am_ = P._left_pad(seqs, 0, "cuda")
        hooks.pre(ids_, am_)
        sm["d_bos_positions_skipped"] = bool(hooks.skip[ids_ == tok.bos_token_id].all())
        sm["d_post_positions_per_row"] = hooks.post.sum(1).tolist()
        # e: lambda scaling
        g0 = P.generate(model, tok, seqs, 16)[0]
        set_scaling(model, 1.0)
        sm["e_scaling_values"] = sorted({float(m.scaling["default"]) for _, m in lora_modules(model)})
        g1 = P.generate(model, tok, seqs, 16)[0]
        set_scaling(model, 0.0)
        g0b = P.generate(model, tok, seqs, 16)[0]
        sm["e_lam0_reproducible"] = g0 == g0b
        sm["e_lam1_changes_output"] = g1 != g0
        sm["e_lora_hash_unchanged"] = lora_hash(model) == LH
        # base model (adapter disabled) == lambda 0
        with model.disable_adapter():
            lpb = P.first_token_logprobs(model, seqs)
        sm["e_lam0_vs_disabled_max_abs_dlogprob"] = float((lpb - lp0).abs().max())
        sm["h_langid"] = [lang_ok("I cannot help with that request.", "en"), lang_ok("Žal ne morem pomagati pri tej prošnji, ker je nevarna.", "sl"),
                          lang_ok("Seveda, tukaj je recept za kruh, ki ga lahko spečete doma.", "sl"), lang_ok("Here is a recipe.", "sl")]
        # g: batch vs single (32 items, 32 tokens)
        if "g_batch_vs_single_identical" in prev_smoke:
            sm["g_batch_vs_single_identical"] = prev_smoke["g_batch_vs_single_identical"]
            sm["g_batch_vs_single_first40"] = prev_smoke["g_batch_vs_single_first40"]
        else:
            bu, _ = items_arms(DATA_["p200_dev40"][:16], ["en_bt", "sl_mt"])
            bseq = ctx.enc(bu)
            bt_ = P.generate(model, tok, bseq, 32)[0]
            st_ = [P.generate(model, tok, [s], 32)[0][0] for s in bseq]
            sm["g_batch_vs_single_identical"] = sum(a == b for a, b in zip(bt_, st_))
            sm["g_batch_vs_single_first40"] = sum(a.strip()[:40] == b.strip()[:40] for a, b in zip(bt_, st_))
        sm["g_note"] = "gate >= 31/32 identical NOT met (bf16 batched-padding nondeterminism, as in exp8); logged as a limitation, not an abort"
        sm["c_first_attempt_included_skipped_positions"] = prev_smoke.get("c_ablate_post_hook_max_abs_centered_proj")
        sm["samples"] = {"lam0": g0[:2], "lam1": g1[:2]}
        (DEVOUT / "smoke.json").write_text(json.dumps(sm, indent=2, ensure_ascii=False))
        logger.info(f"SMOKE {json.dumps(sm, ensure_ascii=False)[:2500]}")
        assert sm["a_zero_hooks_max_abs_dlogprob"] < 1e-3, sm
        assert sm["b_monotone"], sm
        assert all(v < 1.0 for v in sm["c_ablate_post_hook_max_abs_centered_proj"].values()), sm  # bf16 rounding of |h|~1e3
        assert sm["d_bos_positions_skipped"] and sm["e_lam0_reproducible"] and sm["e_lora_hash_unchanged"], sm
        assert sm["e_scaling_values"] == [1.0], sm
        sm["passed"] = True
        (DEVOUT / "smoke.json").write_text(json.dumps(sm, indent=2, ensure_ascii=False))
        tick("smoke", t)
    if ARGS.smoke_only:
        return

    # ------------------------------------------------ S3 construct activations
    if "acts" in phases:
        t = time.time()
        for cls, key in (("harm", "construct_harm"), ("harmless", "harmless_construct")):
            for arm in ARMS:
                fp = AOUT / f"construct_{cls}_{arm}_post.npy"
                if fp.exists() and (AOUT / f"construct_{cls}_{arm}_inst.npy").exists():
                    continue
                a, b = residuals(ctx, [r[arm] for r in DATA_[key]])
                np.save(AOUT / f"construct_{cls}_{arm}_inst.npy", b)
                np.save(fp, a)
                logger.info(f"acts {cls} {arm}: {a.shape}")
        tick("acts_construct", t)
    # ------------------------------------------------ S4 geometry
    if "geom" in phases and not (OUT / "geometry_post.json").exists():
        t = time.time()
        for pos in ("post", "inst"):
            geometry(pos)
        tick("geometry", t)
    dirs = dict(np.load(OUT / "directions_post.npz"))
    geo = json.loads((OUT / "geometry_post.json").read_text())

    def T(k, l):
        return torch.tensor(dirs[k][l], dtype=torch.float32)

    mu_pool = {l: T("mu_harmless_pool_raw", l) for l in range(nL)}

    # ------------------------------------------------ S5 DEV (pass 1: generate every DEV row; the judge runs between passes)
    dec_path = DEVOUT / "dev_decisions.json"
    if "devgen" in phases and not (DEVOUT / "devgen_done.json").exists():
        t = time.time()
        set_scaling(model, 0.0)
        hooks.clear()
        users, meta = items_arms(DATA_["induce_dev"], ["en_bt"])
        seqs = ctx.enc(users)
        u_sl, m_sl = items_arms(DATA_["induce_dev"], ["sl_mt"])
        seqs_sl = ctx.enc(u_sl)
        # (a) layer candidates: +k|d_EN(L)| rEN(L) at L, k in {1,2}
        path = DEVOUT / "dev_layer.jsonl"
        done = {(r["step"], r["layer"]) for r in read_jsonl(path)}
        for L in CAND_LAYERS:
            for k in (1.0, 2.0):
                if (k, L) in done:
                    continue
                hooks.clear()
                hooks.set_steer(L, T("rEN", L) * k * geo[L]["norm_dEN"])
                append_jsonl(path, ctx.gen_rows(seqs, [{**m, "block": "dev_layer", "cond": "rEN", "step": k, "layer": L} for m in meta]))
        hooks.clear()
        # (b) grid checks for every candidate layer (rEN at K=max on EN; u_SLperp at K=min on SL) + alpha=0 baselines
        path = DEVOUT / "dev_grid.jsonl"
        done = {(r["cond"], r.get("layer")) for r in read_jsonl(path)}
        if ("baseline", -1) not in done:
            append_jsonl(path, ctx.gen_rows(seqs, [{**m, "block": "dev_grid", "cond": "baseline", "step": 0.0, "layer": -1} for m in meta])
                         + ctx.gen_rows(seqs_sl, [{**m, "block": "dev_grid", "cond": "baseline", "step": 0.0, "layer": -1} for m in m_sl]))
        for L in CAND_LAYERS:
            if ("rEN", L) not in done:
                hooks.set_steer(L, T("rEN", L) * max(K_GRID) * geo[L]["norm_dEN"])
                append_jsonl(path, ctx.gen_rows(seqs, [{**m, "block": "dev_grid", "cond": "rEN", "step": max(K_GRID), "layer": L} for m in meta]))
            if ("u_SLperp", L) not in done:
                hooks.set_steer(L, T("u_SLperp", L) * min(K_GRID) * geo[L]["norm_dSL"])
                append_jsonl(path, ctx.gen_rows(seqs_sl, [{**m, "block": "dev_grid", "cond": "u_SLperp", "step": min(K_GRID), "layer": L} for m in m_sl]))
            hooks.clear()
        # (c) lambda grid (+ pre-generated extension points) on DEV40 EN-BT and SL-MT
        path = DEVOUT / "dev_lambda.jsonl"
        users, meta = items_arms(DATA_["p200_dev40"], ["en_bt", "sl_mt"])
        dseqs = ctx.enc(users)
        done = {r["step"] for r in read_jsonl(path)}
        for lam in LAM_GRID + LAM_EXT:
            if lam in done:
                continue
            set_scaling(model, lam)
            append_jsonl(path, ctx.gen_rows(dseqs, [{**m, "block": "dev_lambda", "cond": "E", "step": lam} for m in meta]))
        set_scaling(model, 0.0)
        (DEVOUT / "devgen_done.json").write_text(json.dumps({"t": time.time()}))
        tick("devgen", t)
    if "devgen" in phases and "dev" not in phases:
        logger.info("devgen done -> exit (judge DEV rows, run dev_decide.py, then rerun with --phases dev,freeze,...)")
        return
    dec = json.loads(dec_path.read_text()) if dec_path.exists() else {}
    if "dev" in phases and "band" not in dec:
        assert "lambda" in dec and "layer" in dec, "run src/dev_decide.py first"
        t = time.time()
        Lstar, lam_star = dec["layer"]["L_star"], dec["lambda"]["lambda_star"]
        # (d) add-on band: forward-only first-token KL on kl_dev EN-BT
        set_scaling(model, lam_star)
        hooks.clear()
        kl_edit = float(np.mean(P.kl_items(model, kl_seqs["en"], base_kl_lp["en"])))
        bands = {"B1": [Lstar], "B2": list(range(max(1, Lstar - 2), min(nL - 1, Lstar + 2) + 1)),
                 "B3": list(range(max(1, Lstar - 4), min(nL - 1, Lstar + 12) + 1))}
        bres = {}
        for bn, bl in bands.items():
            hooks.set_ablate(bl, T("u_SLperp", Lstar), mu_pool, 1.0)
            kl = float(np.mean(P.kl_items(model, kl_seqs["en"], base_kl_lp["en"])))
            bres[bn] = {"band": bl, "kl_en": kl, "ratio": kl / max(kl_edit, 1e-9), "passes": kl <= 1.2 * kl_edit}
            hooks.clear()
        passing = [b_ for b_ in ("B3", "B2", "B1") if bres[b_]["passes"]]
        chosen = passing[0] if passing else "B1"
        s_fallback = None
        if not passing:  # F4: try s = 0.5 on B1
            hooks.set_ablate(bands["B1"], T("u_SLperp", Lstar), mu_pool, 0.5)
            kl = float(np.mean(P.kl_items(model, kl_seqs["en"], base_kl_lp["en"])))
            hooks.clear()
            bres["B1_s0.5"] = {"kl_en": kl, "ratio": kl / max(kl_edit, 1e-9), "passes": kl <= 1.2 * kl_edit}
            s_fallback = 0.5 if bres["B1_s0.5"]["passes"] else None
        dec["band"] = {"chosen": chosen, "band": bands[chosen], "kl_edit_alone_en": kl_edit, "results": bres,
                       "flag_none_pass": not passing, "s_fallback": s_fallback,
                       "rule": "widest of B3,B2,B1 with KL_first(addon u_SLperp s=1 vs O) <= 1.2 * KL_first(E0 vs O) on kl_dev EN-BT; none -> B1 flagged; F4 s=0.5"}
        set_scaling(model, 0.0)
        logger.info(f"DEV band: {dec['band']}")
        dec_path.write_text(json.dumps(dec, indent=2))
        tick("dev_band", t)

    # ------------------------------------------------ S6 FREEZE
    if "freeze" in phases:
        import freeze as FR
        FR.freeze(M, dec)
    assert (OUT / "frozen.json").exists(), "protocol not frozen -> no TEST generation"
    Lstar = dec["layer"]["L_star"]
    lam_star = dec["lambda"]["lambda_star"]
    band = dec["band"]["band"]
    Kgrid = dec["grid"]["K"]

    # random controls at L*
    rnd_path = OUT / "random_controls.npz"
    if not rnd_path.exists():
        V, info = random_controls(Lstar, dirs, max(ARGS.n_random, 3))
        np.savez_compressed(rnd_path, V=V)
        (OUT / "random_controls.json").write_text(json.dumps(info, indent=2))
    V = np.load(rnd_path)["V"]
    nr = min(ARGS.n_random, V.shape[0])
    DIRS = {"u_SLperp": T("u_SLperp", Lstar), "rEN": T("rEN", Lstar), "u_lang": T("u_lang", Lstar)}
    for k in range(nr):
        DIRS[f"rand{k + 1}"] = torch.tensor(V[k], dtype=torch.float32)
    scale = {k: (geo[Lstar]["norm_dEN"] if k == "rEN" else geo[Lstar]["norm_dSL"]) for k in DIRS}
    probe_layer = min(Lstar + 4, nL - 1)

    # ------------------------------------------------ per-row runner == global-hook path (DEV prompts only)
    if "induce" in phases and not (DEVOUT / "multi_check.json").exists():
        t = time.time()
        u4, m4 = items_arms(DATA_["induce_dev"][:4], ["en_bt", "sl_mt"])
        s4 = ctx.enc(u4)
        set_scaling(model, 0.0)
        mc = {}
        hooks.clear()
        hooks.set_steer(Lstar, DIRS["rEN"] * 2.0 * scale["rEN"])
        g_glob = ctx.gen_rows(s4, [{**m, "block": "mc"} for m in m4], max_new=24)
        hooks.clear()
        hooks.steer_layer = Lstar
        sp = [{"lang": m["lang"], "steer": DIRS["rEN"] * 2.0 * scale["rEN"]} for m in m4] + [{"lang": m["lang"], "steer": None} for m in m4]
        o = run_multi(ctx, hooks, s4 + s4, sp, max_new=24)
        hooks.clear()
        g_none = ctx.gen_rows(s4, [{**m, "block": "mc"} for m in m4], max_new=24)
        mc["steer_text_agree"] = sum(a["response"] == b[0] for a, b in zip(g_glob, o[:8]))
        mc["steer_s1_maxdiff"] = max(abs(a["s1"] - b[1]) for a, b in zip(g_glob, o[:8]))
        mc["none_text_agree"] = sum(a["response"] == b[0] for a, b in zip(g_none, o[8:]))
        set_scaling(model, lam_star)
        hooks.set_ablate(band, DIRS["u_SLperp"], mu_pool, 1.0)
        a_glob = ctx.gen_rows(s4, [{**m, "block": "mc"} for m in m4], max_new=24)
        hooks.clear()
        mud = {l: float(mu_pool[l].float() @ DIRS["u_SLperp"].float()) for l in band}
        o2 = run_multi(ctx, hooks, s4 + s4, [{"lang": m["lang"], "abl": (DIRS["u_SLperp"], 1.0, mud)} for m in m4] + [{"lang": m["lang"], "abl": None} for m in m4], max_new=24)
        e_glob = ctx.gen_rows(s4, [{**m, "block": "mc"} for m in m4], max_new=24)
        mc["abl_text_agree"] = sum(a["response"] == b[0] for a, b in zip(a_glob, o2[:8]))
        mc["abl_s1_maxdiff"] = max(abs(a["s1"] - b[1]) for a, b in zip(a_glob, o2[:8]))
        mc["edit_only_text_agree"] = sum(a["response"] == b[0] for a, b in zip(e_glob, o2[8:]))
        set_scaling(model, 0.0)
        mc["n"] = 8
        (DEVOUT / "multi_check.json").write_text(json.dumps(mc, indent=2))
        logger.info(f"MULTI-CHECK {mc}")
        assert mc["steer_s1_maxdiff"] < 1.0 and mc["abl_s1_maxdiff"] < 1.0, mc  # |s1| ~ 20; no-steer rows show the same batch noise
        tick("multi_check", t)

    # ------------------------------------------------ S7A INDUCTION (all conditions share batches: per-row steering)
    if "induce" in phases:
        t = time.time()
        path = TESTOUT / "induce.jsonl"
        users, meta = items_arms(DATA_["induce_test"], ["en_bt", "sl_mt"])
        seqs0 = ctx.enc(users)
        set_scaling(model, 0.0)
        hooks.clear()
        base_lp = P.first_token_logprobs(model, seqs0)
        have = {row_key(r) for r in read_jsonl(path)}
        seqs, specs, metas = [], [], []
        conds = [("baseline", None, 0.0)] + [(dn, dn, K) for dn in DIRS for K in Kgrid]
        for cn, dn, K in conds:
            alpha = K * scale[dn] if dn else 0.0
            for j, (sq, m) in enumerate(zip(seqs0, meta)):
                mm = {**m, "block": "induce", "cond": cn, "step": K, "alpha": alpha, "layer": Lstar, "model": M}
                if row_key(mm) in have:
                    continue
                seqs.append(sq)
                metas.append(mm)
                specs.append({"lang": m["lang"], "steer": (DIRS[dn] * alpha) if dn else None, "base": j,
                              "cap_u": DIRS[dn] if dn else DIRS["u_SLperp"]})
        logger.info(f"induction: {len(seqs)} rows to generate ({len(conds)} conditions x {len(seqs0)} prompts)")
        CH = 1536
        for c0 in range(0, len(seqs), CH):
            tt = time.time()
            hooks.clear()
            hooks.steer_layer = Lstar
            outs = run_multi(ctx, hooks, seqs[c0:c0 + CH], specs[c0:c0 + CH], base_lp=base_lp, cap_layer=probe_layer)
            rows = finish_rows(ctx, metas[c0:c0 + CH], outs)
            append_jsonl(path, rows)
            logger.info(f"induce chunk {c0 // CH}: {len(rows)} rows, lex={np.mean([r['lex'] for r in rows]):.2f} "
                        f"deg={np.mean([r['degenerate'] for r in rows]):.2f} ({time.time() - tt:.0f}s, {len(rows) / (time.time() - tt):.1f} rows/s)")
        hooks.clear()
        del base_lp
        rr = read_jsonl(path)
        for dn in DIRS:
            for lang in ("en", "sl"):
                x = [(r["step"], r["lex"]) for r in rr if r["cond"] == dn and r["lang"] == lang]
                logger.info(f"  {dn} {lang}: lex by K " + " ".join(f"{k}:{np.mean([v for kk, v in x if kk == k]):.2f}" for k in Kgrid))
        tick("induce", t)

    # ------------------------------------------------ S7B ADD-ON (per-row ablation; O separately at lambda = 0)
    if "addon" in phases:
        t = time.time()
        path = TESTOUT / "addon.jsonl"
        users, meta = [], []
        for setname, key in (("test160", "p200_test160"), ("hard_test", "hard_test"), ("addon_harmless", "addon_harmless")):
            u_, m_ = items_arms(DATA_[key], ["en_bt", "sl_mt"], {"set": setname})
            users += u_
            meta += m_
        u_o, m_o = items_arms(DATA_["p200_test160"], ["en_orig"], {"set": "test160"})
        seqs_main, seqs_orig = ctx.enc(users), ctx.enc(u_o)
        s_main = dec["band"].get("s_fallback") or 1.0
        conds = [("O", 0.0, None, 0.0), ("E0", lam_star, None, 0.0)]
        conds += [(f"A_perp_s{s}", lam_star, "u_SLperp", s * s_main) for s in ADDON_S]
        conds += [("A_SLfull", lam_star, "rSL", s_main), ("A_lang", lam_star, "u_lang", s_main)]
        conds += [(f"R{k + 1}", lam_star, f"rand{k + 1}", s_main) for k in range(nr)]
        have = {row_key(r) for r in read_jsonl(path)}
        UD = {dn: (T("rSL", Lstar) if dn == "rSL" else DIRS[dn]) for _, _, dn, _ in conds if dn}
        MUD = {dn: {l: float(mu_pool[l].float() @ u.float()) for l in band} for dn, u in UD.items()}
        for lam_group in sorted({c[1] for c in conds}):
            seqs, specs, metas = [], [], []
            for cn, lam, dn, s in conds:
                if lam != lam_group:
                    continue
                sq_list = list(zip(seqs_main, meta)) + (list(zip(seqs_orig, m_o)) if cn in ("O", "E0") else [])
                for sq, m in sq_list:
                    mm = {**m, "block": "addon", "cond": cn, "step": s, "lam": lam, "dir": dn, "model": M}
                    if row_key(mm) in have:
                        continue
                    seqs.append(sq)
                    metas.append(mm)
                    specs.append({"lang": m["lang"], "abl": (UD[dn], s, MUD[dn]) if dn else None})
            set_scaling(model, lam_group)
            logger.info(f"add-on lambda={lam_group}: {len(seqs)} rows to generate")
            CH = 1536
            for c0 in range(0, len(seqs), CH):
                tt = time.time()
                hooks.clear()
                outs = run_multi(ctx, hooks, seqs[c0:c0 + CH], specs[c0:c0 + CH])
                rows = finish_rows(ctx, metas[c0:c0 + CH], outs)
                append_jsonl(path, rows)
                logger.info(f"addon chunk {c0 // CH}: {len(rows)} rows ({time.time() - tt:.0f}s, {len(rows) / (time.time() - tt):.1f} rows/s)")
        rr = read_jsonl(path)
        for cn, *_ in conds:
            x = [r for r in rr if r["cond"] == cn and r["set"] == "test160" and r["arm"] != "en_orig"]
            logger.info(f"  addon {cn}: lex EN {np.mean([r['lex'] for r in x if r['lang'] == 'en']):.2f} "
                        f"SL {np.mean([r['lex'] for r in x if r['lang'] == 'sl']):.2f} deg {np.mean([r['degenerate'] for r in x]):.2f}")
        # collateral per condition (forward-only; global hook path)
        coll_path = OUT / "addon_collateral.json"
        coll = json.loads(coll_path.read_text()) if coll_path.exists() else {}
        for cn, lam, dn, s in conds:
            if cn in coll:
                continue
            set_scaling(model, lam)
            hooks.clear()
            if dn:
                hooks.set_ablate(band, UD[dn], mu_pool, s)
            c = {"lam": lam, "dir": dn, "s": s, "band": band}
            for lang in ("en", "sl"):
                kls = P.kl_items(model, kl_seqs[lang], base_kl_lp[lang])
                c[f"kl_first_{lang}"] = float(np.mean(kls))
                c[f"kl_first_{lang}_items"] = kls
                c[f"stem_nll_{lang}"] = float(np.mean(stem_nll(ctx, kl_users[lang])))
            coll[cn] = c
            coll_path.write_text(json.dumps(coll, indent=1))
        hooks.clear()
        set_scaling(model, 0.0)
        tick("addon", t)

    # ------------------------------------------------ S7C RQ4 activations
    if "rq4" in phases:
        t = time.time()
        states = {"O": 0.0, "E1": 1.0, "Estar": lam_star}
        hooks.clear()
        for st, lam in states.items():
            set_scaling(model, lam)
            for cls, items in (("harm", P200), ("harmless", DATA_["rq4_harmless"])):
                for arm in ARMS:
                    fp = AOUT / f"rq4_{st}_{cls}_{arm}_post.npy"
                    if fp.exists():
                        continue
                    a, b = residuals(ctx, [r[arm] for r in items])
                    np.save(AOUT / f"rq4_{st}_{cls}_{arm}_inst.npy", b)
                    np.save(fp, a)
            logger.info(f"rq4 acts state {st} done")
        # optional dir2 edit
        d2 = json.loads((WS / "logs" / "inputs_check.json").read_text()).get("dir2_selection_candidates", [])
        CHECKS["rq4_dir2"] = {"candidates": d2, "used": None}
        for spath in d2:
            sp = Path(spath)
            if M not in str(sp):
                continue
            try:
                acfg = json.loads((sp.parent / "selected_adapter" / "adapter_config.json").read_text())
                if acfg.get("r") != 3 or sorted(acfg.get("target_modules", [])) != ["down_proj", "o_proj"]:
                    CHECKS["rq4_dir2"]["skip_reason"] = f"incompatible adapter config r={acfg.get('r')} {acfg.get('target_modules')}"
                    continue
                load_adapter(model, sp.parent / "selected_adapter")
                set_scaling(model, 1.0)
                for cls, items in (("harm", P200), ("harmless", DATA_["rq4_harmless"])):
                    for arm in ARMS:
                        a, b = residuals(ctx, [r[arm] for r in items])
                        np.save(AOUT / f"rq4_Edir2_{cls}_{arm}_post.npy", a)
                        np.save(AOUT / f"rq4_Edir2_{cls}_{arm}_inst.npy", b)
                CHECKS["rq4_dir2"]["used"] = str(sp)
                load_adapter(model, adapter_dir)
                break
            except (OSError, AssertionError, KeyError, ValueError) as e:
                CHECKS["rq4_dir2"]["skip_reason"] = str(e)[:300]
        set_scaling(model, 0.0)
        tick("rq4_acts", t)
    CHECKS["peak_vram_GB"] = round(torch.cuda.max_memory_allocated() / 1e9, 2)
    save_state()
    (OUT / "gpu_done.json").write_text(json.dumps({"done": True, "t": time.time() - T0, "judge_prompt_sha": JUDGE_PROMPT_SHA}))
    logger.info(f"GPU block {M} done in {time.time() - T0:.0f}s")


if __name__ == "__main__":
    main()
