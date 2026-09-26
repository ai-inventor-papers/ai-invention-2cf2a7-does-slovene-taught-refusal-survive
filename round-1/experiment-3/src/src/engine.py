"""GPU engine: NF4 loading, chat rendering, residual hooks (capture / directional ablation), batched greedy generation
with left padding (self-certified), and the continuous refusal readout s via KV-cache copies."""
from __future__ import annotations

import copy
import gc
import math
import time
from contextlib import contextmanager

import numpy as np
import torch
from loguru import logger
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from common import COMP_PREFIX, HIDDEN, MODELS, N_LAYERS, REF_PREFIX

MAX_PROMPT_TOK = 384


class Engine:
    def __init__(self, key: str, quant: str = "nf4", attn: str = "sdpa"):
        cfg = MODELS[key]
        self.key, self.quant = key, quant
        t0 = time.time()
        self.tok = AutoTokenizer.from_pretrained(cfg["repo"], revision=cfg["revision"])
        if quant == "nf4":
            q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                                   bnb_4bit_compute_dtype=torch.bfloat16,
                                   llm_int8_skip_modules=["lm_head", "vision_tower", "multi_modal_projector"])
        else:
            q = BitsAndBytesConfig(load_in_8bit=True, llm_int8_skip_modules=["lm_head", "vision_tower", "multi_modal_projector"])
        self.model = AutoModelForCausalLM.from_pretrained(cfg["repo"], revision=cfg["revision"], quantization_config=q,
                                                          device_map="cuda:0", attn_implementation=attn,
                                                          torch_dtype=torch.bfloat16)
        self.model.eval()
        self.model_class = type(self.model).__name__
        # locate decoder layers + text backbone generically
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
        self.stop_ids = {i for i in [self.tok.eos_token_id, self.tok.convert_tokens_to_ids("<end_of_turn>")]
                         if i is not None and i >= 0}
        self.hook_state = {"mode": None}
        self.skip_bos = False
        self._handles = [lay.register_forward_hook(self._make_hook(i)) for i, lay in enumerate(self.layers)]
        self.prefix_ids = {lg: {"ref": [self.tok.encode(p, add_special_tokens=False) for p in REF_PREFIX[lg]],
                                "comp": [self.tok.encode(p, add_special_tokens=False) for p in COMP_PREFIX[lg]]}
                           for lg in REF_PREFIX}
        self.load_seconds = time.time() - t0
        self.sha = cfg["revision"]
        logger.info(f"loaded {key} ({self.model_class}, backbone={self.backbone_name}, quant={quant}, attn={attn}) "
                    f"in {self.load_seconds:.0f}s; mem={torch.cuda.memory_allocated() / 1e9:.1f}GB; stop={self.stop_ids}")

    # ------------------------------------------------------------------ hooks
    def _make_hook(self, li: int):
        def hook(mod, inp, out):
            st = self.hook_state
            if st["mode"] is None:
                return None
            h = out[0] if isinstance(out, tuple) else out
            if st["mode"] == "ablate" and li in st["dirs"]:
                u = st["dirs"][li]  # (d,) float32 unit, or (B,d) per-row
                c = st.get("consts", {}).get(li)  # mean-projection constant (scalar or (B,)); None = zero-ablation
                hf = h.float()
                if u.dim() == 1:
                    proj = hf @ u
                    if c is not None:
                        proj = proj - c
                    delta = proj.unsqueeze(-1) * u
                else:
                    proj = torch.einsum("btd,bd->bt", hf, u)
                    if c is not None:
                        proj = proj - c[:, None]
                    delta = proj.unsqueeze(-1) * u[:, None, :]
                pm = st.get("posmask")
                if pm is not None and pm.shape[1] == hf.shape[1]:
                    delta = delta * pm[..., None]
                h2 = (hf - delta).to(h.dtype)
                if st.get("capture") is not None and li in st["capture_layers"]:
                    st["capture"][li] = torch.einsum("bt,btd->bd", st["weights"], h2.float()).cpu()
                return (h2,) + tuple(out[1:]) if isinstance(out, tuple) else h2
            if st.get("capture") is not None and li in st["capture_layers"]:
                st["capture"][li] = torch.einsum("bt,btd->bd", st["weights"], h.float()).cpu()
            return None
        return hook

    @contextmanager
    def ablating(self, dirs: dict | None, consts: dict | None = None):
        """dirs: {layer: unit direction (d,) or per-row (B,d)}; consts: {layer: mean projection (scalar or (B,))}
        -> mean-projection ablation h - ((h.u) - c) u; consts None -> zero-projection ablation. None/{} dirs = no-op."""
        if not dirs:
            yield
            return
        dd = {int(l): torch.as_tensor(np.asarray(u, dtype=np.float32) if not torch.is_tensor(u) else u,
                                      dtype=torch.float32, device="cuda") for l, u in dirs.items()}
        cc = {int(l): torch.as_tensor(np.asarray(v, dtype=np.float32), dtype=torch.float32, device="cuda")
              for l, v in (consts or {}).items()}
        old = dict(self.hook_state)
        self.hook_state.update({"mode": "ablate", "dirs": dd, "consts": cc})
        try:
            yield
        finally:
            self.hook_state.clear(); self.hook_state.update(old)

    def _set_posmask(self, ids: torch.Tensor) -> None:
        """positions excluded from ablation: the BOS token (Gemma-3 attention-sink / massive-activation position)."""
        if self.skip_bos:
            self.hook_state["posmask"] = (ids != self.tok.bos_token_id).float()
        else:
            self.hook_state.pop("posmask", None)

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

    # ------------------------------------------------------------------ forward primitives
    def _fwd(self, ids, mask, pos, cache):
        self._set_posmask(ids)
        out = self.backbone(input_ids=ids, attention_mask=mask, position_ids=pos, past_key_values=cache, use_cache=True)
        return out.last_hidden_state, out.past_key_values

    def _logits(self, h: torch.Tensor) -> torch.Tensor:
        lg = self.lm_head(h).float()
        if self.softcap:
            lg = torch.tanh(lg / self.softcap) * self.softcap
        return lg

    @staticmethod
    def batches(lengths: list[int], budget_tokens: int, max_bs: int) -> list[list[int]]:
        order = sorted(range(len(lengths)), key=lambda i: -lengths[i])
        out, cur, cur_max = [], [], 0
        for i in order:
            m = max(cur_max, lengths[i])
            if cur and (m * (len(cur) + 1) > budget_tokens or len(cur) >= max_bs):
                out.append(cur); cur, cur_max = [], 0; m = lengths[i]
            cur.append(i); cur_max = m
        if cur:
            out.append(cur)
        return out

    @torch.no_grad()
    def run_batch(self, id_lists: list[list[int]], lang: str | None, max_new: int, do_s: bool, pad_side: str = "left"):
        """Left-padded prefill -> (optional) s via cache copies -> greedy decode. Returns (texts, n_new, s_info)."""
        B = len(id_lists)
        T = max(len(x) for x in id_lists)
        ids = torch.full((B, T), self.pad_id, dtype=torch.long)
        mask = torch.zeros((B, T), dtype=torch.long)
        for b, x in enumerate(id_lists):
            if pad_side == "left":
                ids[b, T - len(x):] = torch.tensor(x); mask[b, T - len(x):] = 1
            else:
                ids[b, :len(x)] = torch.tensor(x); mask[b, :len(x)] = 1
        ids, mask = ids.cuda(), mask.cuda()
        pos = (mask.cumsum(-1) - 1).clamp(min=0)
        h, cache = self._fwd(ids, mask, pos, None)
        if pad_side == "left":
            last_h = h[:, -1]
            last_pos = pos[:, -1]
        else:
            L = mask.sum(-1) - 1
            last_h = h[torch.arange(B), L]
            last_pos = L
            assert max_new == 0, "right padding only for s passes"
        logits0 = self._logits(last_h)
        lp0 = torch.log_softmax(logits0, -1)
        s_info = None
        if do_s:
            s_info = self._s_from_cache(cache, mask, last_pos, lp0, lang, right=(pad_side != "left"))
        texts, n_new = [""] * B, [0] * B
        if max_new > 0:
            nxt = logits0.argmax(-1)
            gen = [[] for _ in range(B)]
            done = torch.zeros(B, dtype=torch.bool, device="cuda")
            cur_mask, cur_pos = mask, last_pos
            for step in range(max_new):
                for b in range(B):
                    if not done[b]:
                        t = int(nxt[b])
                        if t in self.stop_ids:
                            done[b] = True
                        else:
                            gen[b].append(t)
                if bool(done.all()) or step == max_new - 1:
                    break
                cur_mask = torch.cat([cur_mask, torch.ones((B, 1), dtype=cur_mask.dtype, device="cuda")], 1)
                cur_pos = cur_pos + 1
                hh, cache = self._fwd(nxt[:, None], cur_mask, cur_pos[:, None], cache)
                nxt = self._logits(hh[:, -1]).argmax(-1)
            texts = [self.tok.decode(g, skip_special_tokens=True) for g in gen]
            n_new = [len(g) for g in gen]
        del cache, h
        return texts, n_new, s_info

    def _s_from_cache(self, cache, mask, last_pos, lp0, lang, right: bool):
        B = mask.shape[0]
        res = {"ref": np.zeros((B, 5)), "comp": np.zeros((B, 5))}
        for kind in ("ref", "comp"):
            for j, pids in enumerate(self.prefix_ids[lang][kind]):
                total = lp0[:, pids[0]].clone()
                if len(pids) > 1:
                    c = copy.deepcopy(cache)
                    p = torch.tensor(pids[:-1], device="cuda")[None].expand(B, -1)
                    if right:
                        raise NotImplementedError
                    m2 = torch.cat([mask, torch.ones((B, len(pids) - 1), dtype=mask.dtype, device="cuda")], 1)
                    pos2 = last_pos[:, None] + 1 + torch.arange(len(pids) - 1, device="cuda")[None]
                    hh, _ = self._fwd(p, m2, pos2, c)
                    lp = torch.log_softmax(self._logits(hh), -1)
                    tgt = torch.tensor(pids[1:], device="cuda")
                    total = total + lp[:, torch.arange(len(pids) - 1), tgt].sum(-1)
                    del c, hh, lp
                res[kind][:, j] = total.cpu().numpy()
        s = torch.logsumexp(torch.tensor(res["ref"]), -1) - torch.logsumexp(torch.tensor(res["comp"]), -1)
        return {"s": s.numpy(), "logp_ref": res["ref"], "logp_comp": res["comp"]}

    @torch.no_grad()
    def s_concat(self, id_list: list[int], lang: str) -> float:
        """Reference route for s: full prompt+prefix sequences, batch of 10, right padded."""
        seqs, meta = [], []
        for kind in ("ref", "comp"):
            for pids in self.prefix_ids[lang][kind]:
                seqs.append(id_list + pids); meta.append((kind, len(pids)))
        T = max(len(x) for x in seqs)
        ids = torch.full((len(seqs), T), self.pad_id, dtype=torch.long)
        mask = torch.zeros_like(ids)
        for b, x in enumerate(seqs):
            ids[b, :len(x)] = torch.tensor(x); mask[b, :len(x)] = 1
        ids, mask = ids.cuda(), mask.cuda()
        pos = (mask.cumsum(-1) - 1).clamp(min=0)
        h, _ = self._fwd(ids, mask, pos, None)
        P = len(id_list)
        vals = {"ref": [], "comp": []}
        for b, (kind, n) in enumerate(meta):
            lp = torch.log_softmax(self._logits(h[b, P - 1:P - 1 + n]), -1)
            tgt = torch.tensor(seqs[b][P:P + n], device="cuda")
            vals[kind].append(float(lp[torch.arange(n), tgt].sum()))
        return float(torch.logsumexp(torch.tensor(vals["ref"]), 0) - torch.logsumexp(torch.tensor(vals["comp"]), 0))

    @torch.no_grad()
    def capture(self, id_lists: list[list[int]], weight_rows: list[np.ndarray], layers: list[int],
                budget_tokens: int = 12000, max_bs: int = 32, ablate: dict | None = None,
                consts: dict | None = None) -> dict[int, np.ndarray]:
        """Right-padded forwards; returns {layer: (N,d) float32} = sum_t w[t] * h_l[t] per sequence."""
        N = len(id_lists)
        out = {l: np.zeros((N, HIDDEN), dtype=np.float32) for l in layers}
        for bidx in self.batches([len(x) for x in id_lists], budget_tokens, max_bs):
            T = max(len(id_lists[i]) for i in bidx)
            ids = torch.full((len(bidx), T), self.pad_id, dtype=torch.long)
            mask = torch.zeros_like(ids)
            W = torch.zeros((len(bidx), T), dtype=torch.float32)
            for b, i in enumerate(bidx):
                x = id_lists[i]
                ids[b, :len(x)] = torch.tensor(x); mask[b, :len(x)] = 1
                W[b, :len(x)] = torch.tensor(weight_rows[i], dtype=torch.float32)
            ids, mask = ids.cuda(), mask.cuda()
            pos = (mask.cumsum(-1) - 1).clamp(min=0)
            st = self.hook_state
            old = dict(st)
            if ablate:
                dd = {int(l): torch.as_tensor(np.asarray(u, dtype=np.float32), device="cuda") for l, u in ablate.items()}
                cc = {int(l): torch.as_tensor(np.asarray(v, dtype=np.float32), device="cuda") for l, v in (consts or {}).items()}
                st.update({"mode": "ablate", "dirs": dd, "consts": cc})
            else:
                st.update({"mode": "capture"})
            st.update({"capture": {}, "capture_layers": set(layers), "weights": W.cuda()})
            try:
                self._set_posmask(ids)
                self.backbone(input_ids=ids, attention_mask=mask, position_ids=pos, use_cache=False)
                for l in layers:
                    out[l][bidx] = st["capture"][l].numpy()
            finally:
                st.clear(); st.update(old)
        return out

    def last_token_weights(self, id_lists: list[list[int]]) -> list[np.ndarray]:
        ws = []
        for x in id_lists:
            w = np.zeros(len(x), dtype=np.float32); w[-1] = 1.0; ws.append(w)
        return ws

    def close(self):
        for hd in self._handles:
            hd.remove()
        del self.model
        gc.collect(); torch.cuda.empty_cache()


def oom_safe(fn, *a, **k):
    """Call fn; on CUDA OOM halve k['budget'] and retry."""
    while True:
        try:
            return fn(*a, **k)
        except torch.cuda.OutOfMemoryError:
            gc.collect(); torch.cuda.empty_cache()
            k["budget"] = k["budget"] // 2
            logger.warning(f"OOM -> budget {k['budget']}")
            if k["budget"] < 256:
                raise
