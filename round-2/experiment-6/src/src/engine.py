"""GPU engine (adapted from iter-1 experiment_3 src/engine.py): NF4 loading, chat rendering, residual capture at chosen
positions during the prefill forward, additive steering from the prefix end onward, batched left-padded greedy decoding,
and teacher-forced continuation scoring (first-token KL / continuation NLL under steering)."""
from __future__ import annotations

import gc
import time

import numpy as np
import torch
from loguru import logger
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from common import CAP_LAYERS, HIDDEN, MODELS, N_LAYERS

MAX_PROMPT_TOK = 448


class Engine:
    def __init__(self, key: str, attn: str = "sdpa"):
        cfg = MODELS[key]
        self.key = key
        t0 = time.time()
        self.tok = AutoTokenizer.from_pretrained(cfg["repo"], revision=cfg["revision"])
        q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                               bnb_4bit_compute_dtype=torch.bfloat16,
                               llm_int8_skip_modules=["lm_head", "vision_tower", "multi_modal_projector"])
        self.model = AutoModelForCausalLM.from_pretrained(cfg["repo"], revision=cfg["revision"], quantization_config=q,
                                                          device_map="cuda:0", attn_implementation=attn,
                                                          torch_dtype=torch.bfloat16)
        self.model.eval()
        self.model_class = type(self.model).__name__
        self.layers, self.backbone = None, None
        for name, mod in self.model.named_modules():
            if isinstance(mod, torch.nn.ModuleList) and len(mod) == N_LAYERS and "DecoderLayer" in type(mod[0]).__name__ \
                    and "Siglip" not in type(mod[0]).__name__:
                self.layers = mod
                self.backbone = self.model.get_submodule(name.rsplit(".", 1)[0]) if "." in name else self.model
                self.backbone_name = name.rsplit(".", 1)[0]
                break
        assert self.layers is not None and len(self.layers) == N_LAYERS
        self.lm_head = self.model.get_output_embeddings()
        tcfg = self.backbone.config
        assert tcfg.hidden_size == HIDDEN, tcfg.hidden_size
        self.softcap = getattr(tcfg, "final_logit_softcapping", None)
        self.pad_id = self.tok.pad_token_id if self.tok.pad_token_id is not None else 0
        self.eot_id = self.tok.convert_tokens_to_ids("<end_of_turn>")
        self.stop_ids = sorted({i for i in [self.tok.eos_token_id, self.eot_id] if i is not None and i >= 0})
        self.stop_t = torch.tensor(self.stop_ids, device="cuda")
        self.state: dict = {}
        self._handles = [lay.register_forward_hook(self._make_hook(i)) for i, lay in enumerate(self.layers)]
        self.load_seconds = time.time() - t0
        self.sha = cfg["revision"]
        logger.info(f"loaded {key} ({self.model_class}, backbone={self.backbone_name}) in {self.load_seconds:.0f}s; "
                    f"mem={torch.cuda.memory_allocated() / 1e9:.1f}GB; stop={self.stop_ids}")

    # ------------------------------------------------------------------ hooks
    def _make_hook(self, li: int):
        def hook(mod, inp, out):
            st = self.state
            if not st:
                return None
            h = out[0] if isinstance(out, tuple) else out
            changed = False
            steer = st.get("steer")
            if steer is not None and li in steer:
                v = steer[li]  # (B,d) float32 on cuda (already scaled)
                if h.shape[1] == 1:
                    h = (h.float() + v[:, None, :]).to(h.dtype)
                else:
                    T = h.shape[1]
                    m = (torch.arange(T, device=h.device)[None, :] >= st["steer_from"][:, None]).float()  # (B,T)
                    h = (h.float() + m[..., None] * v[:, None, :]).to(h.dtype)
                changed = True
            cap = st.get("cap_pos")
            if cap is not None and h.shape[1] > 1 and li in st["cap_layers"]:
                B = h.shape[0]
                idx = cap  # (B,P) long on cuda, padded coordinates
                g = h[torch.arange(B, device=h.device)[:, None], idx]  # (B,P,d)
                st["captured"][li] = g.float().cpu()
            if changed:
                return (h,) + tuple(out[1:]) if isinstance(out, tuple) else h
            return None
        return hook

    # ------------------------------------------------------------------ text
    def render(self, prompt: str) -> str:
        return self.tok.apply_chat_template([{"role": "user", "content": prompt}], add_generation_prompt=True,
                                            tokenize=False)

    def encode_prompt(self, prompt: str) -> tuple[list[int], bool]:
        ids = self.tok.encode(self.render(prompt), add_special_tokens=False)
        if len(ids) <= MAX_PROMPT_TOK:
            return ids, False
        cids = self.tok.encode(prompt, add_special_tokens=False)
        over = len(ids) - MAX_PROMPT_TOK
        cut = self.tok.decode(cids[: max(len(cids) - over - 4, 8)])
        ids = self.tok.encode(self.render(cut), add_special_tokens=False)
        return ids[:MAX_PROMPT_TOK], True

    def positions(self, prompt_ids: list[int], total_len: int) -> tuple[int, int, int]:
        """(t_inst, t_post, t_last) in unpadded coordinates. t_inst = last user-content token before the first
        <end_of_turn>; t_post = last template token ('\\n' after '<start_of_turn>model'); t_last = last input token."""
        e = prompt_ids.index(self.eot_id)
        return e - 1, len(prompt_ids) - 1, total_len - 1

    # ------------------------------------------------------------------ forward primitives
    def _logits(self, h: torch.Tensor) -> torch.Tensor:
        lg = self.lm_head(h).float()
        if self.softcap:
            lg = torch.tanh(lg / self.softcap) * self.softcap
        return lg

    @torch.no_grad()
    def generate(self, id_lists: list[list[int]], max_new: int, cap_pos: list[list[int]] | None = None,
                 cap_layers: list[int] | None = None, steer_vecs: dict[int, np.ndarray] | None = None,
                 return_first_logits: bool = False):
        """Left-padded prefill (+ capture at cap_pos, unpadded coords) -> greedy decode with optional additive steering
        (applied from the last input position onward). Returns dict(texts, n_new, hit_eos, captured, first_lp)."""
        B = len(id_lists)
        T = max(len(x) for x in id_lists)
        ids = torch.full((B, T), self.pad_id, dtype=torch.long)
        mask = torch.zeros((B, T), dtype=torch.long)
        for b, x in enumerate(id_lists):
            ids[b, T - len(x):] = torch.tensor(x)
            mask[b, T - len(x):] = 1
        ids, mask = ids.cuda(), mask.cuda()
        pos = (mask.cumsum(-1) - 1).clamp(min=0)
        st: dict = {}
        if cap_pos is not None:
            off = [T - len(x) for x in id_lists]
            st["cap_pos"] = torch.tensor([[p + off[b] for p in cp] for b, cp in enumerate(cap_pos)], device="cuda")
            st["cap_layers"] = set(cap_layers or CAP_LAYERS)
            st["captured"] = {}
        if steer_vecs:
            st["steer"] = {int(l): torch.as_tensor(np.asarray(v, dtype=np.float32), device="cuda").reshape(-1, HIDDEN)
                           .expand(B, HIDDEN).contiguous() for l, v in steer_vecs.items()}
            st["steer_from"] = torch.full((B,), T - 1, device="cuda")
        self.state = st
        try:
            out = self.backbone(input_ids=ids, attention_mask=mask, position_ids=pos, use_cache=max_new > 0)
            captured = st.get("captured", {})
            st.pop("cap_pos", None)
            h_last = out.last_hidden_state[:, -1]
            cache = out.past_key_values if max_new > 0 else None
            del out
            logits0 = self._logits(h_last)
            first_lp = torch.log_softmax(logits0, -1).cpu() if return_first_logits else None
            gen = torch.full((B, max(max_new, 1)), -1, dtype=torch.long, device="cuda")
            done = torch.zeros(B, dtype=torch.bool, device="cuda")
            hit = torch.zeros(B, dtype=torch.bool, device="cuda")
            n_new = torch.zeros(B, dtype=torch.long, device="cuda")
            if max_new > 0:
                nxt = logits0.argmax(-1)
                cur_mask, cur_pos = mask, pos[:, -1]
                for step in range(max_new):
                    is_stop = torch.isin(nxt, self.stop_t)
                    newly = (~done) & is_stop
                    hit |= newly
                    done |= is_stop
                    keep = ~done
                    gen[keep, step] = nxt[keep]
                    n_new += keep.long()
                    if bool(done.all()) or step == max_new - 1:
                        break
                    cur_mask = torch.cat([cur_mask, torch.ones((B, 1), dtype=cur_mask.dtype, device="cuda")], 1)
                    cur_pos = cur_pos + 1
                    o = self.backbone(input_ids=nxt[:, None], attention_mask=cur_mask, position_ids=cur_pos[:, None],
                                      past_key_values=cache, use_cache=True)
                    cache = o.past_key_values
                    nxt = self._logits(o.last_hidden_state[:, -1]).argmax(-1)
                    del o
            gl = gen.cpu().tolist()
            nn_ = n_new.cpu().tolist()
            texts = [self.tok.decode([t for t in g[:n] if t >= 0], skip_special_tokens=True) for g, n in zip(gl, nn_)]
            del cache
        finally:
            self.state = {}
        return {"texts": texts, "n_new": nn_, "hit_eos": hit.cpu().tolist(), "captured": captured,
                "first_lp": first_lp, "gen_ids": [[t for t in g[:n] if t >= 0] for g, n in zip(gl, nn_)]}

    @torch.no_grad()
    def score_continuation(self, id_lists: list[list[int]], conts: list[list[int]],
                           steer_vecs: dict[int, np.ndarray] | None = None) -> tuple[np.ndarray, np.ndarray]:
        """teacher-forced pass over input+continuation; steering applied from the last input position onward.
        Returns (first-token log-probs (B,V) as float32 numpy, mean NLL of the continuation per row)."""
        seqs = [x + c for x, c in zip(id_lists, conts)]
        B = len(seqs)
        T = max(len(s) for s in seqs)
        ids = torch.full((B, T), self.pad_id, dtype=torch.long)
        mask = torch.zeros((B, T), dtype=torch.long)
        for b, s in enumerate(seqs):
            ids[b, T - len(s):] = torch.tensor(s)
            mask[b, T - len(s):] = 1
        ids, mask = ids.cuda(), mask.cuda()
        pos = (mask.cumsum(-1) - 1).clamp(min=0)
        last_in = [T - len(s) + len(x) - 1 for s, x in zip(seqs, id_lists)]
        st: dict = {}
        if steer_vecs:
            st["steer"] = {int(l): torch.as_tensor(np.asarray(v, dtype=np.float32), device="cuda").reshape(-1, HIDDEN)
                           .expand(B, HIDDEN).contiguous() for l, v in steer_vecs.items()}
            st["steer_from"] = torch.tensor(last_in, device="cuda")
        self.state = st
        try:
            h = self.backbone(input_ids=ids, attention_mask=mask, position_ids=pos, use_cache=False).last_hidden_state
        finally:
            self.state = {}
        first, nll = [], []
        for b in range(B):
            li, c = last_in[b], conts[b]
            hh = h[b, li: li + len(c)] if len(c) else h[b, li: li + 1]
            lp = torch.log_softmax(self._logits(hh), -1)
            first.append(lp[0].cpu())
            if len(c):
                tgt = torch.tensor(c, device="cuda")
                nll.append(float(-lp[torch.arange(len(c)), tgt].mean()))
            else:
                nll.append(float("nan"))
            del lp
        return torch.stack(first).numpy(), np.array(nll)

    def close(self):
        for hd in self._handles:
            hd.remove()
        del self.model
        gc.collect()
        torch.cuda.empty_cache()


def length_batches(lengths: list[int], max_bs: int, budget_tokens: int) -> list[list[int]]:
    """sort by length (desc) and cut batches bounded by count and padded-token budget."""
    order = sorted(range(len(lengths)), key=lambda i: -lengths[i])
    out, cur, cur_max = [], [], 0
    for i in order:
        m = max(cur_max, lengths[i])
        if cur and (m * (len(cur) + 1) > budget_tokens or len(cur) >= max_bs):
            out.append(cur)
            cur, m = [], lengths[i]
        cur.append(i)
        cur_max = m
    if cur:
        out.append(cur)
    return out
