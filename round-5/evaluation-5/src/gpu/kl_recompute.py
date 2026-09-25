#!/usr/bin/env python3
"""STEP 2c (optional, gated) - per-prompt first-token KL recompute of exp15's 40-prompt C5a measurement.

load_model / _hook / _suffix / attach_adapter / set_lambda / render / first_logits are copied VERBATIM from
iter-4 exp15 src/gen.py (same NF4 double-quant bf16 config, same forward-hook LoRA, same chat template, same prompts =
exp9 data/gate_harmless40.jsonl EN-BT / SL-MT). The ONLY change vs exp15 phase_kl: the per-prompt KL vector is saved.
Scope: lambda 0 base, E_exp9, rand_1, rand_2 at the four random-matched lambdas, one model at a time.
Reproduction gate: recomputed kl_mean within 5% of the saved kl_mean for E_exp9 at the top dose in both languages.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.pop("TRANSFORMERS_CACHE", None)

import torch  # noqa: E402
from loguru import logger  # noqa: E402

WS = Path(__file__).resolve().parents[1]
RUN = Path(os.environ.get("AII_RUN_ROOT", str(WS.parents[2]))).resolve()  # same single constant as src/common.py
EXP9 = RUN / "iter_3/gen_art/gen_art_experiment_9"
EXP15 = RUN / "iter_4/gen_art/gen_art_experiment_15"
OUT = WS / "results/kl_items_exp15_recomputed.jsonl"
MODELS = {"gemma_it": {"repo": "google/gemma-3-12b-it", "revision": "96b6f1eccf38110c56df3a15bffe176da04bfd80"},
          "gams3_it": {"repo": "cjvt/GaMS3-12B-Instruct", "revision": "1d0b27af5748784482600d24779409e7e1dc9adc"}}
EDITS = {"E_exp9": {m: EXP9 / "selected" / m / "adapter" for m in MODELS},
         **{f"rand_{i}": {m: EXP9 / "adapters" / m / f"rand_{i}" for m in MODELS} for i in range(1, 3)}}
LAMBDA_R = {"gemma_it": [0.7695, 1.1551, 1.5603, 2.0], "gams3_it": [0.3013, 0.6313, 0.978, 1.5375]}  # exp15 analysis.json random_arm.lambda_R

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|kl_gpu|{message}")
logger.add(WS / "logs/kl_gpu.log", rotation="30 MB", level="DEBUG")


def disable_torch_native_triton() -> str:
    """verbatim exp15 src/common.py"""
    try:
        from torch._native import registry as _nr
        _nr.deregister_op_overrides(disable_dsl_names=["triton", "cutedsl", "helion", "nvmath"])
        return "deregistered"
    except (ImportError, AttributeError, RuntimeError, ValueError) as e:
        return f"not_deregistered:{e}"


NATIVE = disable_torch_native_triton()


# ------------------------------------------------------------------ verbatim from exp15 src/gen.py
def load_model(mkey: str):
    from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    spec = MODELS[mkey]
    cfg = AutoConfig.from_pretrained(spec["repo"], revision=spec["revision"])
    arch = (cfg.architectures or ["?"])[0]
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             llm_int8_skip_modules=["vision_tower", "multi_modal_projector", "lm_head"])
    kw = dict(revision=spec["revision"], quantization_config=bnb, dtype=torch.bfloat16, device_map="cuda:0",
              attn_implementation="sdpa")
    t0 = time.time()
    if "ConditionalGeneration" in arch:
        from transformers import Gemma3ForConditionalGeneration
        model = Gemma3ForConditionalGeneration.from_pretrained(spec["repo"], **kw)
    else:
        model = AutoModelForCausalLM.from_pretrained(spec["repo"], **kw)
    model.eval()
    tok = AutoTokenizer.from_pretrained(spec["repo"], revision=spec["revision"])
    tok.padding_side = "left"
    info = {"arch": arch, "load_s": round(time.time() - t0, 1), "vram_gb": round(torch.cuda.memory_allocated() / 1e9, 2),
            "native_triton": NATIVE, "torch": torch.__version__, "revision": spec["revision"]}
    logger.info(f"loaded {mkey} {info}")
    return model, tok, info


_LORA: dict = {"lam": 0.0, "handles": [], "n": 0, "edit": None}


def _hook(A: torch.Tensor, B: torch.Tensor, scale: float):
    def fn(mod, args, out):
        lam = _LORA["lam"]
        if lam == 0.0:
            return out
        x = args[0]
        return out + (lam * scale) * ((x.to(A.dtype) @ A.t()) @ B.t()).to(out.dtype)
    return fn


def _suffix(name: str) -> str:
    i = name.find("layers.")
    return name[i:] if i >= 0 else name


def attach_adapter(model, mkey: str, edit: str) -> dict:
    from safetensors.torch import load_file
    ad = Path(EDITS[edit][mkey])
    cfg = json.loads((ad / "adapter_config.json").read_text())
    scale = float(cfg["lora_alpha"]) / float(cfg["r"])
    sd = load_file(str(ad / "adapter_model.safetensors"))
    mods = {_suffix(n): m for n, m in model.named_modules() if "layers." in n and "vision" not in n}
    pairs: dict = {}
    for k, v in sd.items():
        name = _suffix(k.rsplit(".lora_", 1)[0])
        pairs.setdefault(name, {})["A" if ".lora_A." in k else "B"] = v
    missing = [n for n in pairs if n not in mods]
    assert not missing, f"adapter targets not in model: {missing[:4]}"
    assert all(len(ab) == 2 for ab in pairs.values()), "adapter with unpaired A/B"
    for h in _LORA["handles"]:
        h.remove()
    _LORA["handles"] = []
    ranks = set()
    for name, ab in pairs.items():
        A = ab["A"].to("cuda:0", torch.bfloat16)
        B = ab["B"].to("cuda:0", torch.bfloat16)
        ranks.add(int(A.shape[0]))
        _LORA["handles"].append(mods[name].register_forward_hook(_hook(A, B, scale)))
    _LORA["n"], _LORA["edit"] = len(pairs), edit
    return {"edit": edit, "n_lora_modules": len(pairs), "ranks": sorted(ranks), "scaling": scale}


def set_lambda(lam: float) -> None:
    _LORA["lam"] = float(lam)


def render(tok, text: str) -> str:
    return tok.apply_chat_template([{"role": "user", "content": text}], add_generation_prompt=True, tokenize=False)


@torch.inference_mode()
def first_logits(model, tok, texts: list[str]) -> torch.Tensor:
    enc = [tok(render(tok, t), add_special_tokens=False).input_ids for t in texts]
    Lm = max(len(x) for x in enc)
    pad = tok.pad_token_id if tok.pad_token_id is not None else 0
    inp = torch.tensor([[pad] * (Lm - len(x)) + x for x in enc], device="cuda:0")
    att = torch.tensor([[0] * (Lm - len(x)) + [1] * len(x) for x in enc], device="cuda:0")
    return model(input_ids=inp, attention_mask=att, logits_to_keep=1).logits[:, -1, :].float().cpu()


# ------------------------------------------------------------------ phase_kl with the per-prompt vector saved
def phase_kl_items(model, tok, mkey: str) -> list[dict]:
    hl = [json.loads(x) for x in (EXP9 / "data" / "gate_harmless40.jsonl").read_text().splitlines() if x.strip()]
    out = []
    for lang, key in (("en", "en_bt"), ("sl", "sl_mt")):
        prompts = [h.get(key) or h["en_orig"] for h in hl]
        ids = [h.get("item_id") or h.get("id") or str(i) for i, h in enumerate(hl)]
        attach_adapter(model, mkey, "E_exp9")
        set_lambda(0.0)
        base = torch.log_softmax(first_logits(model, tok, prompts), -1)
        for edit in ["E_exp9", "rand_1", "rand_2"]:
            attach_adapter(model, mkey, edit)
            for lam in LAMBDA_R[mkey]:
                set_lambda(lam)
                lp = torch.log_softmax(first_logits(model, tok, prompts), -1)
                kl = (base.exp() * (base - lp)).sum(-1)
                out.append({"model": mkey, "edit": edit, "lambda": lam, "lang": lang, "kl_mean": float(kl.mean()),
                            "kl_median": float(kl.median()), "n": len(prompts), "item_ids": ids,
                            "kl_items": [float(x) for x in kl.tolist()]})
                logger.info(f"{mkey} {lang} {edit} lam={lam} kl_mean={float(kl.mean()):.5f}")
    set_lambda(0.0)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="gemma_it,gams3_it")
    a = ap.parse_args()
    torch.manual_seed(20260926)
    torch.cuda.set_per_process_memory_fraction(0.9)
    OUT.parent.mkdir(exist_ok=True)
    for mkey in a.models.split(","):
        model, tok, info = load_model(mkey)
        rows = phase_kl_items(model, tok, mkey)
        with open(OUT, "a") as f:
            for r in rows:
                f.write(json.dumps({**r, "load_info": info}) + "\n")
        for h in _LORA["handles"]:
            h.remove()
        _LORA["handles"] = []
        del model, tok
        gc.collect()
        torch.cuda.empty_cache()
    logger.info("done")


if __name__ == "__main__":
    main()
