"""Shared GPU/CPU utilities: model loading (NF4), decoder-layer finder, per-row steering hook, exact-length
bucketing (NO padding: left-padded batches corrupt Gemma-3 outputs), KV-reuse refusal-prefix scorer s, greedy
generation, frozen bilingual lexicon, degeneracy flag."""
from __future__ import annotations

import copy
import gc
import json
import math
import re
import time
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import torch
from loguru import logger

ROOT = Path(__file__).resolve().parents[1]
SEED = 20260923
MODELS = {
    "pt": ("google/gemma-3-12b-pt", "295efb63d01a7017928f273a94ebb86105c9526f"),
    "gb": ("cjvt/GaMS3-12B", "46127695de173a5de72e1da9dc43846f58553477"),
    "gemma": ("google/gemma-3-12b-it", "96b6f1eccf38110c56df3a15bffe176da04bfd80"),
    "gams": ("cjvt/GaMS3-12B-Instruct", "1d0b27af5748784482600d24779409e7e1dc9adc"),
    # smoke-test stand-ins (same code paths)
    "tiny_pt": ("google/gemma-3-270m", None),
    "tiny_it": ("google/gemma-3-270m-it", None),
}
LEX = json.loads((ROOT / "config/lexicon.json").read_text())
PREFIXES = json.loads((ROOT / "config/prefixes.json").read_text())


# ----------------------------------------------------------------------------- lexicon / text utils
def fold(s: str) -> str:
    s = s.lower().replace("’", "'").replace("‘", "'").replace("`", "'")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s)


EN_MARKERS = [fold(m) for m in LEX["en"]]
SL_MARKERS = sorted({fold(m) for m in LEX["sl"]})


def lexicon_hit(text: str, lang: str | None) -> tuple[bool, list[str]]:
    """lang='en' -> EN markers, 'sl' -> SL markers, None -> union (D6, induction)."""
    t = fold(text)
    ms = EN_MARKERS if lang == "en" else SL_MARKERS if lang == "sl" else EN_MARKERS + SL_MARKERS
    hits = [m for m in ms if m in t]
    return bool(hits), hits


def is_degenerate(text: str) -> bool:
    words = re.findall(r"[^\W\d_]+", text, flags=re.UNICODE)
    if len(words) < 3:
        return True
    toks = text.split()
    grams = [tuple(toks[i:i + 4]) for i in range(len(toks) - 3)]
    if len(grams) >= 4:
        dup = 1.0 - len(set(grams)) / len(grams)
        if dup > 0.5:
            return True
    return False


# ----------------------------------------------------------------------------- model loading
def load_model(key: str, bits: int = 4):
    from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    repo, rev = MODELS[key]
    cfg = AutoConfig.from_pretrained(repo, revision=rev)
    if bits == 4:
        q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                               bnb_4bit_compute_dtype=torch.bfloat16,
                               llm_int8_skip_modules=["vision_tower", "multi_modal_projector", "lm_head"])
    elif bits == 8:
        q = BitsAndBytesConfig(load_in_8bit=True, llm_int8_skip_modules=["vision_tower", "multi_modal_projector", "lm_head"])
    else:
        q = None
    t0 = time.time()
    if cfg.model_type == "gemma3":  # multimodal wrapper; text path only
        from transformers import Gemma3ForConditionalGeneration
        model = Gemma3ForConditionalGeneration.from_pretrained(repo, revision=rev, quantization_config=q,
                                                               dtype=torch.bfloat16, device_map="cuda:0",
                                                               attn_implementation="sdpa")
    else:
        model = AutoModelForCausalLM.from_pretrained(repo, revision=rev, quantization_config=q, dtype=torch.bfloat16,
                                                     device_map="cuda:0", attn_implementation="sdpa")
    model.eval()
    tok = AutoTokenizer.from_pretrained(repo, revision=rev)
    logger.info(f"loaded {repo}@{rev} bits={bits} in {time.time()-t0:.0f}s; "
                f"GPU mem {torch.cuda.memory_allocated()/1e9:.1f} GB")
    return model, tok


def unload(model) -> None:
    del model
    gc.collect()
    torch.cuda.empty_cache()


def decoder_layers(model) -> torch.nn.ModuleList:
    n = None
    for c in [getattr(model.config, "text_config", None), model.config]:
        if c is not None and getattr(c, "num_hidden_layers", None):
            n = c.num_hidden_layers
            break
    for name, mod in model.named_modules():
        if isinstance(mod, torch.nn.ModuleList) and len(mod) == n and type(mod[0]).__name__.endswith("DecoderLayer"):
            return mod
    raise RuntimeError("decoder ModuleList not found")


def hidden_size(model) -> int:
    c = getattr(model.config, "text_config", None) or model.config
    return c.hidden_size


def bos_id(tok) -> int:
    return tok.bos_token_id


# ----------------------------------------------------------------------------- prompts
def chat_ids(tok, prompt: str) -> list[int]:
    s = tok.apply_chat_template([{"role": "user", "content": prompt}], add_generation_prompt=True, tokenize=False)
    assert s.endswith("<start_of_turn>model\n"), s[-60:]
    assert "system" not in s.split("<start_of_turn>user")[0], s[:80]
    ids = tok(s, add_special_tokens=False)["input_ids"]
    assert ids.count(tok.bos_token_id) == 1 and ids[0] == tok.bos_token_id, "BOS check failed"
    return ids


def plain_ids(tok, prompt: str) -> list[int]:
    ids = tok(prompt, add_special_tokens=True)["input_ids"]
    assert ids[0] == tok.bos_token_id and ids.count(tok.bos_token_id) == 1
    return ids


def buckets(items: list[dict], max_bs: int, key: Callable[[dict], tuple] = lambda r: (len(r["ids"]),)) -> list[list[dict]]:
    """Exact-length buckets (zero padding), each split into chunks of <= max_bs."""
    g: dict[tuple, list[dict]] = defaultdict(list)
    for r in items:
        g[key(r)].append(r)
    out = []
    for k in sorted(g):
        rows = g[k]
        for i in range(0, len(rows), max_bs):
            out.append(rows[i:i + max_bs])
    return out


# ----------------------------------------------------------------------------- steering hook
class Steerer:
    """Adds a per-row vector (alpha*r_hat, shape [B, d]) to the output of one decoder block at every position
    except BOS (position 0; no padding is ever used, so position 0 == BOS)."""

    def __init__(self, model, layer_l: int):
        self.layers = decoder_layers(model)
        self.block = self.layers[layer_l - 1]  # D4: 'layer l' == hidden_states[l] == output of block l-1
        self.vec: torch.Tensor | None = None
        self.handle = self.block.register_forward_hook(self._hook, with_kwargs=True)

    def _hook(self, module, args, kwargs, output):
        if self.vec is None:
            return output
        hs = output[0] if isinstance(output, tuple) else output
        B, T, _ = hs.shape
        pos = kwargs.get("position_ids")
        if pos is None:
            pos = kwargs.get("cache_position")
        if pos is None:
            raise RuntimeError("no position info in decoder-layer kwargs")
        pos = pos.to(hs.device)
        if pos.dim() == 1:
            pos = pos.unsqueeze(0).expand(B, T)
        mask = (pos != 0).to(hs.dtype).unsqueeze(-1)
        v = self.vec.to(device=hs.device, dtype=hs.dtype)
        if v.shape[0] != B:
            raise RuntimeError(f"steer batch mismatch {v.shape} vs {B}")
        hs = hs + mask * v[:, None, :]
        if isinstance(output, tuple):
            return (hs,) + tuple(output[1:])
        return hs

    def set(self, vec: torch.Tensor | None) -> None:
        self.vec = vec

    def remove(self) -> None:
        self.handle.remove()


# ----------------------------------------------------------------------------- forward passes
@torch.inference_mode()
def residuals_all_layers(model, rows: list[dict], max_bs: int = 32, keep_layers: list[int] | None = None,
                         norm_layer: int | None = None, pool: str = "last") -> tuple[dict, dict]:
    """Last-token residual at all hidden_states layers for each row (rows need 'uid','ids').
    Returns {uid: np.float32 [L+1, d]} and optionally {uid: (sum of L2 norms over non-BOS positions at norm_layer, count)}."""
    out, norms = {}, {}
    for b in buckets(rows, max_bs):
        ids = torch.tensor([r["ids"] for r in b], device="cuda")
        o = model(input_ids=ids, attention_mask=torch.ones_like(ids), output_hidden_states=True, use_cache=False,
                  logits_to_keep=1)
        hs = o.hidden_states
        layers = range(len(hs)) if keep_layers is None else keep_layers
        if pool == "last":
            stack = torch.stack([hs[l][:, -1, :] for l in layers], dim=1).float().cpu().numpy()
        else:  # mean over non-BOS positions (exploratory format-confound check)
            stack = torch.stack([hs[l][:, 1:, :].float().mean(1) for l in layers], dim=1).cpu().numpy()
        for i, r in enumerate(b):
            out[r["uid"]] = stack[i]
        if norm_layer is not None:
            nn_ = hs[norm_layer][:, 1:, :].float().norm(dim=-1)  # exclude BOS
            for i, r in enumerate(b):
                norms[r["uid"]] = (float(nn_[i].sum()), int(nn_.shape[1]))
        del o, hs
    return out, norms


def _prefix_token_ids(tok, lang: str) -> dict[str, list[tuple[str, list[int]]]]:
    res = {}
    for kind in ["refusal", "compliance"]:
        res[kind] = [(p, tok(p, add_special_tokens=False)["input_ids"]) for p in PREFIXES[kind][lang]]
    return res


@torch.inference_mode()
def score_s(model, tok, rows: list[dict], max_bs: int = 32, steerer: Steerer | None = None,
            mode: str = "cache") -> dict:
    """s = logsumexp(refusal prefix log-probs) - logsumexp(compliance prefix log-probs), teacher-forced after the
    chat template, prefixes in the row's language. rows need 'uid','ids','lang' and (if steerer) 'vec' [d] tensor.
    mode='cache': prompt forward once, each multi-token prefix continued from a deep-copied KV cache.
    mode='concat': full concatenation (reference implementation)."""
    ptoks = {lang: _prefix_token_ids(tok, lang) for lang in ["en", "sl"]}
    out = {}
    for b in buckets(rows, max_bs, key=lambda r: (r["lang"], len(r["ids"]))):
        lang = b[0]["lang"]
        B = len(b)
        ids = torch.tensor([r["ids"] for r in b], device="cuda")
        if steerer is not None:
            steerer.set(torch.stack([r["vec"] for r in b]).cuda())
        lps: dict[str, list[torch.Tensor]] = {"refusal": [], "compliance": []}
        if mode == "cache":
            o = model(input_ids=ids, attention_mask=torch.ones_like(ids), use_cache=True, logits_to_keep=1)
            last = torch.log_softmax(o.logits[:, -1, :].float(), dim=-1)
            cache = o.past_key_values
            for kind in ["refusal", "compliance"]:
                for _, pt in ptoks[lang][kind]:
                    lp = last[:, pt[0]].clone()
                    if len(pt) > 1:
                        c2 = copy.deepcopy(cache)
                        pids = torch.tensor([pt] * B, device="cuda")
                        am = torch.ones(B, ids.shape[1] + len(pt), device="cuda", dtype=torch.long)
                        o2 = model(input_ids=pids, attention_mask=am, past_key_values=c2, use_cache=True,
                                   cache_position=torch.arange(ids.shape[1], ids.shape[1] + len(pt), device="cuda"))
                        l2 = torch.log_softmax(o2.logits[:, :-1, :].float(), dim=-1)
                        tgt = pids[:, 1:]
                        lp = lp + l2.gather(-1, tgt.unsqueeze(-1)).squeeze(-1).sum(-1)
                        del c2, o2, l2
                    lps[kind].append(lp)
            del o, cache
        else:
            for kind in ["refusal", "compliance"]:
                for _, pt in ptoks[lang][kind]:
                    full = torch.cat([ids, torch.tensor([pt] * B, device="cuda")], dim=1)
                    o = model(input_ids=full, attention_mask=torch.ones_like(full), use_cache=False,
                              logits_to_keep=len(pt) + 1)
                    l = torch.log_softmax(o.logits[:, :-1, :].float(), dim=-1)  # predicts the prefix tokens
                    tgt = full[:, -len(pt):]
                    lps[kind].append(l.gather(-1, tgt.unsqueeze(-1)).squeeze(-1).sum(-1))
                    del o, l
        r_ = torch.logsumexp(torch.stack(lps["refusal"], 1), 1)
        c_ = torch.logsumexp(torch.stack(lps["compliance"], 1), 1)
        s = (r_ - c_).cpu().numpy()
        for i, r in enumerate(b):
            out[r["uid"]] = {"s": float(s[i]), "lse_ref": float(r_[i]), "lse_comp": float(c_[i])}
    if steerer is not None:
        steerer.set(None)
    return out


@torch.inference_mode()
def generate(model, tok, rows: list[dict], max_bs: int = 64, max_new_tokens: int = 64,
             steerer: Steerer | None = None, progress_every: int = 20) -> dict:
    """Greedy generation in exact-length buckets (no padding). rows need 'uid','ids' (+ 'vec' if steerer)."""
    out = {}
    bl = buckets(rows, max_bs)
    t0 = time.time()
    eos = [tok.eos_token_id]
    eot = tok.convert_tokens_to_ids("<end_of_turn>")
    if isinstance(eot, int) and eot != tok.unk_token_id:
        eos.append(eot)
    for bi, b in enumerate(bl):
        ids = torch.tensor([r["ids"] for r in b], device="cuda")
        if steerer is not None:
            steerer.set(torch.stack([r["vec"] for r in b]).cuda())
        g = model.generate(input_ids=ids, attention_mask=torch.ones_like(ids), do_sample=False,
                           max_new_tokens=max_new_tokens, eos_token_id=eos, pad_token_id=tok.pad_token_id,
                           top_p=None, top_k=None, temperature=None)
        gen = g[:, ids.shape[1]:].cpu().tolist()
        for i, r in enumerate(b):
            toks = gen[i]
            cut = len(toks)
            for j, t in enumerate(toks):
                if t in eos or t == tok.pad_token_id:
                    cut = j
                    break
            out[r["uid"]] = {"text": tok.decode(toks[:cut], skip_special_tokens=True), "n_tok": cut,
                             "first_tok": toks[0] if toks else None}
        if steerer is not None:
            steerer.set(None)
        if progress_every and (bi + 1) % progress_every == 0:
            el = time.time() - t0
            logger.info(f"  gen batch {bi+1}/{len(bl)} ({sum(len(x) for x in bl[:bi+1])} seqs) {el:.0f}s, "
                        f"ETA {el/(bi+1)*(len(bl)-bi-1):.0f}s")
    return out


def write_jsonl(path: Path, rows: Iterable[dict], mode: str = "w") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open(mode) as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def unit(v: np.ndarray) -> np.ndarray:
    return v / (np.linalg.norm(v) + 1e-12)
