"""GPU probe helpers: rendering, bucketed greedy generation, prefix log-odds s, first-token KL, ablation hooks.

All batching sorts by token length (minimal left padding) and halves the batch on CUDA OOM.
Tokenisation mirrors Heretic 3521f864 Model.generate: tokenizer(rendered_chat_string) with default
add_special_tokens, left padding, greedy decoding.
"""
from __future__ import annotations

import copy
import gc
from contextlib import contextmanager

import torch
import torch.nn.functional as F

from common import COMP_PREFIX, REF_PREFIX

TOKEN_BUDGET = 22000  # (batch x (padded length + new tokens)) budget per call on the 23 GB L4 (KV ~393 KB/token)
MAX_BS = 96
PRE_HOOK = None  # callable(ids, am) set by the A2 ablation context (marks BOS / pad positions)


def set_budget(budget: int, max_bs: int) -> None:
    global TOKEN_BUDGET, MAX_BS
    TOKEN_BUDGET, MAX_BS = budget, max_bs


def render(tok, users: list[str], response_prefix: str | None = None) -> list[str]:
    """Official chat template, NO system turn (empty system dropped), generation prompt appended."""
    out = tok.apply_chat_template([[{"role": "user", "content": u}] for u in users], add_generation_prompt=True,
                                  tokenize=False)
    if response_prefix:
        out = [o + response_prefix for o in out]
    return out


def encode(tok, texts: list[str]) -> list[list[int]]:
    return [tok(t, return_token_type_ids=False)["input_ids"] for t in texts]


def _batches(lengths: list[int], extra: int, budget: int | None = None, max_bs: int | None = None):
    budget = TOKEN_BUDGET if budget is None else budget
    max_bs = MAX_BS if max_bs is None else max_bs
    order = sorted(range(len(lengths)), key=lambda i: lengths[i])
    i = 0
    while i < len(order):
        bs = 1
        while (i + bs < len(order) and bs < max_bs and (bs + 1) * (lengths[order[i + bs]] + extra) <= budget):
            bs += 1
        yield order[i:i + bs]
        i += bs


def _left_pad(seqs: list[list[int]], pad_id: int, device):
    L = max(len(s) for s in seqs)
    ids = torch.full((len(seqs), L), pad_id, dtype=torch.long)
    am = torch.zeros((len(seqs), L), dtype=torch.long)
    for r, s in enumerate(seqs):
        ids[r, L - len(s):] = torch.tensor(s)
        am[r, L - len(s):] = 1
    return ids.to(device), am.to(device)


def _run_with_oom(fn, idx: list[int]):
    """fn(sub_idx) -> list results; halves on OOM."""
    try:
        return fn(idx)
    except torch.cuda.OutOfMemoryError:
        gc.collect()
        torch.cuda.empty_cache()
        if len(idx) == 1:
            raise
        h = len(idx) // 2
        return _run_with_oom(fn, idx[:h]) + _run_with_oom(fn, idx[h:])


@torch.inference_mode()
def generate(model, tok, seqs: list[list[int]], max_new: int, want_first_logits: bool = False):
    """Greedy generation. Returns (texts, first_token_logprobs or None) in input order."""
    dev = model.device
    texts = [None] * len(seqs)
    firsts = [None] * len(seqs) if want_first_logits else None

    def fn(sub):
        ids, am = _left_pad([seqs[i] for i in sub], tok.pad_token_id, dev)
        if PRE_HOOK is not None:
            PRE_HOOK(ids, am)
        out = model.generate(input_ids=ids, attention_mask=am, max_new_tokens=max_new, do_sample=False,
                             pad_token_id=tok.pad_token_id, return_dict_in_generate=True,
                             output_logits=want_first_logits, disable_compile=True)
        new = out.sequences[:, ids.shape[1]:]
        dec = tok.batch_decode(new, skip_special_tokens=True)
        res = []
        for r, i in enumerate(sub):
            fl = None
            if want_first_logits:
                fl = F.log_softmax(out.logits[0][r].float(), dim=-1).cpu()
            res.append((i, dec[r], fl))
        del out, ids, am
        return res

    for b in _batches([len(s) for s in seqs], max_new):
        for i, t, fl in _run_with_oom(fn, b):
            texts[i] = t
            if want_first_logits:
                firsts[i] = fl
    return texts, firsts


@torch.inference_mode()
def first_token_logprobs(model, seqs: list[list[int]], device_out: str = "cpu") -> torch.Tensor:
    """log_softmax of last-position logits of each (unpadded) sequence. [N, V] float32."""
    dev = model.device
    out = [None] * len(seqs)

    def fn(sub):
        ids, am = _left_pad([seqs[i] for i in sub], 0, dev)
        if PRE_HOOK is not None:
            PRE_HOOK(ids, am)
        pos = (am.cumsum(-1) - 1).clamp(min=0)
        o = model(input_ids=ids, attention_mask=am, position_ids=pos, logits_to_keep=1, use_cache=False)
        lp = F.log_softmax(o.logits[:, -1].float(), dim=-1)
        lp = lp.to(device_out)
        return [(i, lp[r]) for r, i in enumerate(sub)]

    for b in _batches([len(s) for s in seqs], 1, budget=TOKEN_BUDGET):
        for i, v in _run_with_oom(fn, b):
            out[i] = v
    return torch.stack(out)


@torch.inference_mode()
def kl_items(model, seqs: list[list[int]], base_lp: torch.Tensor) -> list[float]:
    """Per-item KL(base || current) on the first generated token; Heretic's batchmean == mean of these."""
    dev = model.device
    out = [None] * len(seqs)

    def fn(sub):
        ids, am = _left_pad([seqs[i] for i in sub], 0, dev)
        if PRE_HOOK is not None:
            PRE_HOOK(ids, am)
        pos = (am.cumsum(-1) - 1).clamp(min=0)
        o = model(input_ids=ids, attention_mask=am, position_ids=pos, logits_to_keep=1, use_cache=False)
        cur = F.log_softmax(o.logits[:, -1].float(), dim=-1)
        base = base_lp[sub].to(dev).float()
        kl = (base.exp() * (base - cur)).sum(-1).clamp(min=0.0).tolist()
        return list(zip(sub, kl))

    for b in _batches([len(s) for s in seqs], 1, budget=TOKEN_BUDGET):
        for i, v in _run_with_oom(fn, b):
            out[i] = v
    return out


def prefix_ids(tok, lang: str) -> tuple[list[list[int]], list[list[int]]]:
    ref = [tok(q, add_special_tokens=False)["input_ids"] for q in REF_PREFIX[lang]]
    comp = [tok(q, add_special_tokens=False)["input_ids"] for q in COMP_PREFIX[lang]]
    return ref, comp


@torch.inference_mode()
def score_s(model, tok, seqs: list[list[int]], lang: str) -> tuple[list[float], list[float]]:
    """s = logsumexp_{q in REF} log p(q|p) - logsumexp_{q in COMP} log p(q|p), teacher-forced over full prefixes
    (prompt KV cache reused across the 10 prefixes). Also returns s1 (first-token-only version)."""
    ref, comp = prefix_ids(tok, lang)
    allq = ref + comp
    nref = len(ref)
    dev = model.device
    s_out = [None] * len(seqs)
    s1_out = [None] * len(seqs)

    def fn(sub):
        ids, am = _left_pad([seqs[i] for i in sub], 0, dev)
        B = ids.shape[0]
        pos = (am.cumsum(-1) - 1).clamp(min=0)
        o = model(input_ids=ids, attention_mask=am, position_ids=pos, logits_to_keep=1, use_cache=True)
        last = F.log_softmax(o.logits[:, -1].float(), dim=-1)
        past = o.past_key_values
        last_pos = pos[:, -1]
        lps = torch.zeros((B, len(allq)), device=dev)
        lps1 = torch.zeros((B, len(allq)), device=dev)
        for qi, q in enumerate(allq):
            lp = last[:, q[0]].clone()
            lps1[:, qi] = lp
            if len(q) > 1:
                pk = copy.deepcopy(past)
                qin = torch.tensor([q[:-1]] * B, device=dev)
                am2 = torch.cat([am, torch.ones((B, len(q) - 1), dtype=am.dtype, device=dev)], dim=1)
                pos2 = last_pos[:, None] + 1 + torch.arange(len(q) - 1, device=dev)[None, :]
                o2 = model(input_ids=qin, attention_mask=am2, position_ids=pos2, past_key_values=pk, use_cache=True)
                l2 = F.log_softmax(o2.logits.float(), dim=-1)
                tgt = torch.tensor(q[1:], device=dev)
                lp = lp + l2[:, torch.arange(len(q) - 1, device=dev), tgt].sum(-1)
                del pk, o2, l2
            lps[:, qi] = lp
        s = torch.logsumexp(lps[:, :nref], -1) - torch.logsumexp(lps[:, nref:], -1)
        # s1: dedupe identical first tokens within each set
        r1 = sorted({q[0] for q in ref})
        c1 = sorted({q[0] for q in comp})
        s1 = torch.logsumexp(last[:, r1], -1) - torch.logsumexp(last[:, c1], -1)
        del o, past
        return [(i, float(s[r]), float(s1[r])) for r, i in enumerate(sub)]

    for b in _batches([len(x) for x in seqs], 8, budget=TOKEN_BUDGET // 2):
        for i, v, v1 in _run_with_oom(fn, b):
            s_out[i] = v
            s1_out[i] = v1
    return s_out, s1_out


@torch.inference_mode()
def score_s1(model, tok, seqs: list[list[int]], lang: str) -> list[float]:
    """First-token-only s (one prompt forward, deduplicated first tokens of the SCREEN-SPEC prefix sets)."""
    ref, comp = prefix_ids(tok, lang)
    r1 = sorted({q[0] for q in ref})
    c1 = sorted({q[0] for q in comp})
    lp = first_token_logprobs(model, seqs, device_out="cpu")
    return (torch.logsumexp(lp[:, r1], -1) - torch.logsumexp(lp[:, c1], -1)).tolist()


