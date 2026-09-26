#!/usr/bin/env python3
"""STEP 3-4 model block (GPU): ONE NF4 load per model through Heretic's own Model class (identical to iter-1), then every
condition is a LoRA state swapped into the single 'default' adapter slot (no reload between conditions).

Conditions: orig (lora_B = 0, identity) | E_iter1 (iter-1 selected adapter, lambda 1) | E_iter1_l{0.5,1.5,2.0} (lora_B x lambda)
| rand_nm_j{1..5} (Heretic abliterate() with the SAME params, seeded random unit directions) | rand_c6_j1 (weights x 6)
| E_art2 (+ its random controls) if a round-3 selection is discovered.

Stages (each resumable; a stage/condition whose output file exists is skipped):
  build     construct / load all condition states, save adapters, manipulation check (Heretic first-token KL)
  pilot     SCREEN: orig only, 20 items/task, batch-vs-single loglik check, BOS check, timing
  util      lm-eval zero-shot MC (custom local-subset task YAMLs), per-sample logs
  belebele  lm-eval Belebele EN/SL/HU
  chat      chat-template sensitivity (ARC-C + BoolQ, 100 items, orig + E_iter1)
  scorer2   independent torch loglik scorer (second code path, 50 items/task)
  kl        first-token + 32-token KL(orig||cond) at batch size 1, 4 arms, + self-KL floor
  bpb       bits-per-byte on human-translated FLORES passages
  gen       128-token harmless generations (left-padded batches), for language consistency / degeneracy
"""
from __future__ import annotations

import argparse
import gc
import json
import math
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")  # no C compiler on this pod (iter-1/2 trap)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402

try:  # trap: torch 2.14 routes some ops to Triton 'native' kernels that need a C compiler (none on this pod)
    from torch._native import registry as _nr
    _nr.deregister_op_overrides(disable_dsl_names=["triton", "cutedsl", "helion", "nvmath"])
    TRITON_DEREG = "deregistered"
except (ImportError, AttributeError, RuntimeError, ValueError) as _e:
    TRITON_DEREG = f"not_deregistered:{_e}"

from common import (ADAPTERS, DATA, ITEMS, ITER1_EXP4, ITER1_SEED, ITER3_GENART, LOGS, MODELS, RESULTS, SEED,  # noqa: E402
                    UTIL_TASKS, append_jsonl, read_jsonl, setup_logger, sha256_file, write_jsonl)

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=list(MODELS))
ap.add_argument("--stages", default="build,util,belebele,kl,bpb,gen,scorer2,chat")
ap.add_argument("--n-util", type=int, default=300)
ap.add_argument("--n-util-lambda", type=int, default=100)
ap.add_argument("--n-bele", type=int, default=200)
ap.add_argument("--n-kl", type=int, default=200)
ap.add_argument("--n-bpb", type=int, default=150)
ap.add_argument("--n-gen", type=int, default=200)
ap.add_argument("--n-gen-lambda", type=int, default=100)
ap.add_argument("--gen-langs", default="en_bt,sl_mt,hu_mt")
ap.add_argument("--util-bs", type=int, default=8)
ap.add_argument("--gen-bs", type=int, default=16)
ap.add_argument("--util-conds", default="orig,E_iter1,rand_nm_j1")
ap.add_argument("--lambda-conds", default="E_iter1_l2.0,E_iter1_l1.5,E_iter1_l0.5")
ap.add_argument("--kl-conds", default="E_iter1,E_iter1_l0.5,E_iter1_l1.5,E_iter1_l2.0,rand_nm_j1,rand_nm_j2,rand_nm_j3,rand_nm_j4,rand_nm_j5,rand_c6_j1")
ap.add_argument("--bpb-conds", default="orig,E_iter1,E_iter1_l2.0,rand_nm_j1,rand_c6_j1")
ap.add_argument("--gen-conds", default="orig,E_iter1,rand_nm_j1")
ap.add_argument("--gen-lambda-conds", default="E_iter1_l2.0")
ap.add_argument("--bele-conds", default="orig,E_iter1,rand_nm_j1")
ap.add_argument("--pilot-n", type=int, default=20)
ap.add_argument("--kl-extra-conds", default="")
ap.add_argument("--art2-rand", action="store_true")
ap.add_argument("--deadline-epoch", type=float, default=0.0, help="stop starting new work after this epoch time")
ARGS = ap.parse_args()

M = ARGS.model
OUTM = RESULTS / "models" / M
OUTM.mkdir(parents=True, exist_ok=True)
logger = setup_logger(f"gpu_{M}")
T0 = time.time()
TIMING_P = OUTM / "timing.json"
TIMING = json.loads(TIMING_P.read_text()) if TIMING_P.exists() else {}
LAMBDAS = [0.5, 1.5, 2.0]


def tick(name: str, t: float) -> None:
    TIMING[name] = round(time.time() - t, 1)
    TIMING_P.write_text(json.dumps(TIMING, indent=2))
    logger.info(f"[time] {name}: {TIMING[name]}s (process total {time.time() - T0:.0f}s)")


def past_deadline() -> bool:
    return ARGS.deadline_epoch > 0 and time.time() > ARGS.deadline_epoch


# ------------------------------------------------------------------ Heretic load (verbatim iter-1 settings) ----------
import heretic.model as hm  # noqa: E402
from heretic.config import Settings  # noqa: E402
from heretic.model import AbliterationParameters, Model  # noqa: E402


def write_config_toml() -> Path:
    src = ITER1_EXP4 / "results" / M / "cfg" / "config.toml"
    txt = src.read_text()
    old_ckpt = [ln for ln in txt.splitlines() if ln.startswith("study_checkpoint_dir")][0]
    txt = txt.replace(old_ckpt, f'study_checkpoint_dir = "{OUTM}/heretic_ckpt_unused"')
    cfgdir = OUTM / "cfg"
    cfgdir.mkdir(exist_ok=True)
    (cfgdir / "config.toml").write_text(txt)
    return cfgdir


def load_settings(cfgdir: Path) -> Settings:
    old_argv, old_cwd = sys.argv, os.getcwd()
    sys.argv = [old_argv[0]]
    os.chdir(cfgdir)
    try:
        s = Settings(model=MODELS[M]["repo"], model_commit=MODELS[M]["revision"])
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)
    assert s.system_prompt == "" and s.quantization.value == "bnb_4bit", s
    return s


def patched_generate(self, prompts, **kwargs):  # iter-1 patch: drop the EMPTY system turn (identically for both models)
    chats = [([{"role": "system", "content": p.system}] if p.system else []) + [{"role": "user", "content": p.user}]
             for p in prompts]
    chat_prompts = self.tokenizer.apply_chat_template(chats, add_generation_prompt=True, tokenize=False)
    inputs = self.tokenizer(chat_prompts, return_tensors="pt", padding=True, return_token_type_ids=False).to(self.model.device)
    outputs = self.model.generate(**inputs, **kwargs, pad_token_id=self.tokenizer.pad_token_id, do_sample=False)
    return inputs, outputs


hm.Model.generate = patched_generate

torch.manual_seed(SEED)
torch.cuda.set_per_process_memory_fraction(0.92)
t = time.time()
settings = load_settings(write_config_toml())
HM = Model(settings)
TOK = HM.tokenizer
PM = HM.model  # PeftModel
NET = PM.base_model.model  # Gemma3ForConditionalGeneration with LoRA layers injected
NET.eval()
DEV = next(NET.parameters()).device
LORA = [(n, p) for n, p in PM.named_parameters() if "lora_" in n]
tick("load", t)
logger.info(f"loaded {M}: class={type(NET).__name__} lora_params={len(LORA)} vram={torch.cuda.memory_allocated() / 1e9:.2f}GB "
            f"bos={TOK.bos_token_id} add_bos={getattr(TOK, 'add_bos_token', None)} pad_side={TOK.padding_side}")
BOS = TOK.bos_token_id
EOS_IDS = {i for i in [TOK.eos_token_id, TOK.convert_tokens_to_ids("<end_of_turn>")] if isinstance(i, int) and i >= 0}

# ------------------------------------------------------------------ condition states ---------------------------------
STATES: dict[str, dict[str, torch.Tensor]] = {}
META: dict[str, dict] = {}


def snapshot() -> dict[str, torch.Tensor]:
    return {n: p.detach().clone() for n, p in LORA}


@torch.no_grad()
def apply_state(name: str) -> None:
    st = STATES[name]
    for n, p in LORA:
        v = st[n]
        if p.data.shape != v.shape:
            p.data = v.clone()
        else:
            p.data.copy_(v)


def zero_state() -> dict[str, torch.Tensor]:
    st = snapshot()
    return {n: (torch.zeros_like(v) if "lora_B" in n else v) for n, v in st.items()}


def load_adapter_state(adir: Path) -> dict[str, torch.Tensor]:
    from safetensors.torch import load_file
    sd = load_file(str(adir / "adapter_model.safetensors"))
    live = dict(LORA)
    st = {}
    for k, v in sd.items():
        kk = k.replace(".lora_A.weight", ".lora_A.default.weight").replace(".lora_B.weight", ".lora_B.default.weight")
        assert kk in live, f"adapter key {k} -> {kk} not in live model"
        st[kk] = v.to(device=live[kk].device, dtype=live[kk].dtype)
    missing = [n for n in live if n not in st]
    assert not missing, f"{len(missing)} live lora params missing from adapter, e.g. {missing[:2]}"
    cfg = json.loads((adir / "adapter_config.json").read_text())
    assert cfg["lora_alpha"] / cfg["r"] == 1.0, cfg
    return st


def save_state(name: str, st: dict[str, torch.Tensor], meta: dict) -> Path:
    """Save as a peft adapter dir (same key layout + config as iter-1's selected adapter)."""
    from safetensors.torch import save_file
    out = ADAPTERS / M / name
    out.mkdir(parents=True, exist_ok=True)
    sd = {n.replace(".lora_A.default.weight", ".lora_A.weight").replace(".lora_B.default.weight", ".lora_B.weight"):
          v.detach().to("cpu").contiguous() for n, v in st.items()}
    save_file(sd, str(out / "adapter_model.safetensors"))
    cfg = json.loads((ITER1_EXP4 / "results" / M / "selected_adapter" / "adapter_config.json").read_text())
    (out / "adapter_config.json").write_text(json.dumps(cfg, indent=2))
    (out / "construction.json").write_text(json.dumps(meta, indent=2))
    return out


def lora_norms(st: dict[str, torch.Tensor]) -> dict:
    b = [float(v.float().norm()) for n, v in st.items() if "lora_B" in n]
    return {"sum_lora_B_norm": round(sum(b), 4), "n_nonzero_B": int(sum(x > 0 for x in b))}


def find_art2() -> dict | None:
    """Discover artifact 2 (B' dose curve) selected adapter for THIS model, if it exists."""
    for cfgp in sorted(ITER3_GENART.glob("*/**/adapter_config.json")):
        d = cfgp.parent
        if "gen_art_experiment_12" in str(d) or "selected" not in str(d).lower():
            continue
        if M not in str(d) and not ((M == "gams3_it" and "gams" in str(d).lower()) or (M == "gemma_it" and "gemma" in str(d).lower())):
            continue
        root = [p for p in d.parents if p.parent == ITER3_GENART][0]
        txt = " ".join(p.read_text(errors="ignore")[:20000] for p in [root / "README.md", root / "protocol.yaml"] if p.exists())
        if "B'" in txt or "dose" in txt.lower():
            sel = [p for p in d.parent.glob("*selection*.json")] + [p for p in d.glob("*selection*.json")]
            return {"adapter_dir": str(d), "selection_json": str(sel[0]) if sel else None, "root": str(root),
                    "mtime": os.path.getmtime(cfgp)}
    return None


# ------------------------------------------------------------------ first-token / multi-token KL helpers -------------
def render_chat(user: str) -> list[int]:
    s = TOK.apply_chat_template([{"role": "user", "content": user}], add_generation_prompt=True, tokenize=False)
    ids = TOK(s, add_special_tokens=False, return_token_type_ids=False)["input_ids"]
    assert ids[0] == BOS and not (len(ids) > 1 and ids[1] == BOS), "BOS missing or doubled"
    return ids


@torch.no_grad()
def logprobs_last(ids: list[int], n_keep: int) -> torch.Tensor:
    """log-softmax (fp32) of the logits at the last n_keep positions, batch size 1, no padding."""
    x = torch.tensor([ids], device=DEV)
    try:
        out = NET(input_ids=x, logits_to_keep=n_keep, use_cache=False)
    except TypeError:
        out = NET(input_ids=x, use_cache=False)
    lg = out.logits[0, -n_keep:].float()
    return F.log_softmax(lg, dim=-1)


def kl_rows(lp_o: torch.Tensor, lp_c: torch.Tensor) -> torch.Tensor:
    """per-position KL(p_orig || p_cond)"""
    return (lp_o.exp() * (lp_o - lp_c)).sum(-1)


def heretic_kl_prompts() -> list[list[int]]:
    from datasets import load_dataset
    ds = load_dataset("mlabonne/harmless_alpaca", split="test[:100]")
    return [render_chat(r["text"]) for r in ds]


def add_art2(rand_dirs=None) -> None:
    """E_art2 discovery; if found, load it and (when its selection JSON carries Heretic params) build rand_art2_j1..5."""
    art2 = find_art2()
    (OUTM / "art2_discovery.json").write_text(json.dumps({"found": art2 is not None, "info": art2, "checked_at": time.time()}, indent=2))
    if not art2:
        logger.info("E_art2 not found (PENDING)")
        return
    try:
        STATES["E_art2"] = load_adapter_state(Path(art2["adapter_dir"]))
        META["E_art2"] = {"kind": "art2_selected", "lambda": 1.0, **art2,
                          "sha256": sha256_file(Path(art2["adapter_dir"]) / "adapter_model.safetensors")}
        logger.info(f"E_art2 FOUND: {art2}")
    except (AssertionError, FileNotFoundError, KeyError, ValueError) as e:
        logger.error(f"E_art2 found but not loadable: {e!r}")
        return
    try:
        sel = json.loads(Path(art2["selection_json"]).read_text()) if art2.get("selection_json") else {}
        par = sel.get("parameters")
        if not par and isinstance(sel.get("params"), dict):  # artifact 2 format: flattened "attn.o_proj.max_weight"
            par = {}
            for k, v in sel["params"].items():
                for comp in ("attn.o_proj", "mlp.down_proj"):
                    if k.startswith(comp + "."):
                        par.setdefault(comp, {})[k[len(comp) + 1:]] = v
        if not ARGS.art2_rand:
            par = None  # own random controls for E_art2 not built (time); rand_nm_* (iter-1 params) is the random reference
        if par and rand_dirs is not None:
            params = {k: AbliterationParameters(**v) for k, v in par.items()}
            for j in range(1, 6):
                HM.reset_model()
                HM.abliterate(rand_dirs(j), sel.get("direction_index"), params)
                STATES[f"rand_art2_j{j}"] = snapshot()
                META[f"rand_art2_j{j}"] = {"kind": "random_norm_matched_art2", "j": j, "params_from": art2["selection_json"]}
            HM.reset_model()
    except (OSError, ValueError, KeyError, TypeError) as e:
        logger.error(f"art2 random controls not built: {e!r}")


# ------------------------------------------------------------------ STAGE build --------------------------------------
def stage_build() -> None:
    t = time.time()
    if (OUTM / "manipulation_check.json").exists() and (OUTM / "conditions.json").exists():
        meta = json.loads((OUTM / "conditions.json").read_text())
        for name, mt in meta.items():
            if name == "orig":
                STATES["orig"] = zero_state()
            elif name == "E_iter1":
                STATES[name] = load_adapter_state(Path(mt["adapter_dir"]))
            else:
                p = Path(mt["saved_adapter_dir"])
                if sha256_file(p / "adapter_model.safetensors") != mt["saved_sha256"]:
                    raise RuntimeError(f"saved adapter {p} sha mismatch")
                STATES[name] = load_adapter_state(p)
            META[name] = mt
        mc = json.loads((OUTM / "manipulation_check.json").read_text())
        logger.info(f"RESUME: reloaded {len(STATES)} saved condition states (sha-verified); manipulation check already "
                    f"done (all_pass={mc['checks']['all_pass']})")
        # cheap live re-verification that the reloaded E_iter1 is the same edit: 10-prompt first-token KL
        prompts = heretic_kl_prompts()[:10]
        apply_state("orig")
        base = [logprobs_last(ids, 1)[0] for ids in prompts]
        apply_state("E_iter1")
        k = float(np.mean([float(kl_rows(b[None], logprobs_last(ids, 1))[0]) for b, ids in zip(base, prompts)]))
        apply_state("orig")
        logger.info(f"RESUME re-check: E_iter1 first-token KL on 10 prompts = {k:.4f}")
        if "E_art2" not in STATES:
            L1, d = torch.load(ITER1_EXP4 / "results" / M / "residual_directions.pt", map_location="cpu").shape
            add_art2(lambda j: F.normalize(torch.randn(L1, d, generator=torch.Generator().manual_seed(ITER1_SEED + j)), p=2, dim=1))
            new = [n for n in STATES if n.startswith(("E_art2", "rand_art2"))]
            for name in new:
                if name not in META or "saved_adapter_dir" not in META[name]:
                    META[name].update(lora_norms(STATES[name]))
                    p = save_state(name, STATES[name], META[name])
                    META[name].update({"saved_adapter_dir": str(p), "saved_sha256": sha256_file(p / "adapter_model.safetensors")})
            if new:  # manipulation check for the late-discovered edit(s), same protocol as the build stage
                prompts = heretic_kl_prompts()
                apply_state("orig")
                base = [logprobs_last(ids, 1)[0] for ids in prompts]
                mcp = OUTM / "manipulation_check.json"
                mcj = json.loads(mcp.read_text())
                for name in new:
                    apply_state(name)
                    kv = float(np.mean([float(kl_rows(b[None], logprobs_last(ids, 1))[0]) for b, ids in zip(base, prompts)]))
                    mcj["heretic_style_kl"][name] = kv
                    if name == "E_art2":
                        try:
                            ref = json.loads(Path(META[name]["selection_json"]).read_text()).get("kl")
                        except (OSError, TypeError, ValueError):
                            ref = None
                        mcj["checks"]["E_art2"] = {"kl": kv, "art2_logged_kl": ref,
                                                   "rel_err": (kv / ref - 1) if ref else None,
                                                   "pass": bool(ref and abs(kv / ref - 1) <= 0.25)}
                    logger.info(f"late manipulation check {name}: KL={kv:.4f}")
                apply_state("orig")
                mcp.write_text(json.dumps(mcj, indent=2))
                (OUTM / "conditions.json").write_text(json.dumps(META, indent=2, default=str))
        tick("build_resume", t)
        return
    STATES["orig"] = zero_state()
    META["orig"] = {"kind": "original", "lambda": 0.0}
    sel_dir = ITER1_EXP4 / "results" / M / "selected_adapter"
    pick = json.loads((ITER1_EXP4 / "results" / M / "selection_pick.json").read_text())
    params = {k: AbliterationParameters(**v) for k, v in pick["parameters"].items()}
    didx = pick["direction_index"]
    STATES["E_iter1"] = load_adapter_state(sel_dir)
    META["E_iter1"] = {"kind": "iter1_selected", "lambda": 1.0, "adapter_dir": str(sel_dir),
                       "sha256": sha256_file(sel_dir / "adapter_model.safetensors"), "pick": pick}
    for lam in LAMBDAS:
        name = f"E_iter1_l{lam}"
        STATES[name] = {n: (v * lam if "lora_B" in n else v.clone()) for n, v in STATES["E_iter1"].items()}
        META[name] = {"kind": "lambda_scaled", "lambda": lam, "base": "E_iter1", "rule": "every lora_B tensor x lambda"}
    # random directions: iter-1 rand_dirs(j) verbatim (shape from iter-1 residual directions; seed ITER1_SEED + j)
    L1, d = torch.load(ITER1_EXP4 / "results" / M / "residual_directions.pt", map_location="cpu").shape

    def rand_dirs(j: int) -> torch.Tensor:
        g = torch.Generator().manual_seed(ITER1_SEED + j)
        return F.normalize(torch.randn(L1, d, generator=g), p=2, dim=1)

    def scaled(c: float) -> dict:
        return {k: AbliterationParameters(max_weight=v.max_weight * c, max_weight_position=v.max_weight_position,
                                          min_weight=v.min_weight * c, min_weight_distance=v.min_weight_distance)
                for k, v in params.items()}

    for j in range(1, 6):
        HM.reset_model()
        HM.abliterate(rand_dirs(j), didx, params)
        STATES[f"rand_nm_j{j}"] = snapshot()
        META[f"rand_nm_j{j}"] = {"kind": "random_norm_matched", "j": j, "seed": ITER1_SEED + j, "c": 1.0,
                                 "construction": "heretic Model.abliterate(rand_dirs(j), direction_index, SAME params)"}
    HM.reset_model()
    HM.abliterate(rand_dirs(1), didx, scaled(6.0))
    STATES["rand_c6_j1"] = snapshot()
    META["rand_c6_j1"] = {"kind": "random_c6", "j": 1, "seed": ITER1_SEED + 1, "c": 6.0,
                          "construction": "rand_dirs(1) with max/min weights x 6 (iter-1 largest random edit)"}
    HM.reset_model()
    add_art2(rand_dirs)
    for name, st in STATES.items():
        META[name].update(lora_norms(st))
        if name != "orig":
            p = save_state(name, st, META[name])
            META[name]["saved_adapter_dir"] = str(p)
            META[name]["saved_sha256"] = sha256_file(p / "adapter_model.safetensors")
    tick("build_states", t)

    # ---- MANIPULATION CHECK: Heretic first-token KL on harmless_alpaca test[:100] (chat template, no system) ----
    t = time.time()
    prompts = heretic_kl_prompts()
    apply_state("orig")
    base = [logprobs_last(ids, 1)[0] for ids in prompts]
    mc = {}
    check_conds = ["orig", "E_iter1"] + [f"E_iter1_l{lam}" for lam in LAMBDAS] + [f"rand_nm_j{j}" for j in range(1, 6)] + \
        ["rand_c6_j1"] + (["E_art2"] if "E_art2" in STATES else [])
    for c in check_conds:
        apply_state(c)
        kls = [float(kl_rows(b[None], logprobs_last(ids, 1))[0]) for b, ids in zip(base, prompts)]
        mc[c] = float(np.mean(kls))
        logger.info(f"manipulation check {c}: heretic-style first-token KL = {mc[c]:.5f}")
    # T3: disable_adapter() == orig (lora_B = 0)
    apply_state("E_iter1")
    with PM.disable_adapter():
        kd = float(np.mean([float(kl_rows(b[None], logprobs_last(ids, 1))[0]) for b, ids in zip(base[:10], prompts[:10])]))
    apply_state("orig")
    ref = json.loads((ITER1_EXP4 / "results" / M / "random_edits.json").read_text())
    ref_rand = {e["j"]: e["heretic_kl"] for e in ref["edits"] if e["variant"] == "norm_matched"}
    ref_c6 = [e["heretic_kl"] for e in ref["edits"] if e["variant"] == "en_kl_matched" and e["j"] == 1][0]
    pick_kl = META["E_iter1"]["pick"]["kl"]
    checks = {
        "E_iter1": {"kl": mc["E_iter1"], "iter1_pick_kl": pick_kl, "rel_err": mc["E_iter1"] / pick_kl - 1,
                    "pass": abs(mc["E_iter1"] / pick_kl - 1) <= 0.25},
        "orig_self": {"kl": mc["orig"], "pass": mc["orig"] < 1e-4},
        "disable_adapter_vs_orig": {"kl": kd, "pass": kd < 1e-4},
        "rand_c6_j1": {"kl": mc["rand_c6_j1"], "iter1": ref_c6, "ratio": mc["rand_c6_j1"] / max(ref_c6, 1e-12),
                       "pass": 0.1 <= mc["rand_c6_j1"] / max(ref_c6, 1e-12) <= 10},
    }
    for j in range(1, 6):
        r = mc[f"rand_nm_j{j}"] / max(ref_rand[j], 1e-12)
        checks[f"rand_nm_j{j}"] = {"kl": mc[f"rand_nm_j{j}"], "iter1": ref_rand[j], "ratio": r, "pass": 0.1 <= r <= 10}
    checks["lambda_monotone"] = {"kl": [mc["E_iter1_l0.5"], mc["E_iter1"], mc["E_iter1_l1.5"], mc["E_iter1_l2.0"]],
                                 "pass": mc["E_iter1_l0.5"] < mc["E_iter1"] < mc["E_iter1_l1.5"] < mc["E_iter1_l2.0"]}
    if "E_art2" in mc:
        checks["E_art2"] = {"kl": mc["E_art2"]}
    checks["all_pass"] = all(v.get("pass", True) for v in checks.values() if isinstance(v, dict))
    (OUTM / "manipulation_check.json").write_text(json.dumps({"heretic_style_kl": mc, "checks": checks}, indent=2))
    (OUTM / "conditions.json").write_text(json.dumps(META, indent=2, default=str))
    logger.info(f"manipulation checks: all_pass={checks['all_pass']} | {json.dumps({k: v.get('pass') for k, v in checks.items() if isinstance(v, dict)})}")
    tick("manipulation_check", t)
    if not checks["E_iter1"]["pass"]:
        logger.error("E_iter1 manipulation check FAILED -> E_iter1 labelled UNVERIFIED (F3); continuing")


def ensure_states() -> None:
    if not STATES:
        stage_build()


# ------------------------------------------------------------------ lm-eval utility ----------------------------------
_HFLM = None
_TM = None


def get_hflm(bs: int):
    global _HFLM
    from lm_eval.models.huggingface import HFLM
    if _HFLM is None:
        _HFLM = HFLM(pretrained=NET, tokenizer=TOK, batch_size=bs, max_length=2048, add_bos_token=True, backend="causal")
    _HFLM.batch_size_per_gpu = bs
    return _HFLM


TASK_DIR = Path(__file__).resolve().parent.parent / "tasks"


def task_yaml(name: str, path: Path, wino: bool) -> None:
    TASK_DIR.mkdir(exist_ok=True)
    if wino:
        body = ("doc_to_text: !function utils.wino_text\ndoc_to_target: !function utils.wino_target\n"
                "doc_to_choice: !function utils.wino_choice\n")
    else:
        body = 'doc_to_text: "{{query}}"\ndoc_to_target: "{{gold}}"\ndoc_to_choice: "{{choices}}"\n'
    y = (f"task: {name}\ndataset_path: json\ndataset_kwargs:\n  data_files:\n    test: {path}\ntest_split: test\n"
         f"output_type: multiple_choice\n{body}"
         "metric_list:\n  - metric: acc\n    aggregation: mean\n    higher_is_better: true\n"
         "  - metric: acc_norm\n    aggregation: mean\n    higher_is_better: true\nmetadata:\n  version: 1.0\n")
    (TASK_DIR / f"{name}.yaml").write_text(y)


def ensure_task_files() -> dict[str, dict]:
    (TASK_DIR / "utils.py").write_text(
        '"""Winogrande partial scoring (lm-eval convention) on the {query=continuation, choices=contexts, gold} schema."""\n\n\n'
        "def wino_text(doc):\n    return int(doc['gold'])\n\n\n"
        "def wino_target(doc):\n    return doc['query']\n\n\n"
        "def wino_choice(doc):\n    return list(doc['choices'])\n")
    tasks = {}
    for task in UTIL_TASKS:
        for lang in ("en", "sl"):
            name = f"rq3_{task}_{lang}"
            p = DATA / "util" / f"{task}_{lang}.jsonl"
            task_yaml(name, p, wino=(task == "winogrande"))
            tasks[name] = {"task": task, "lang": lang, "path": p}
    for lang in ("en", "sl", "hu"):
        name = f"rq3_belebele_{lang}"
        p = DATA / "belebele" / f"belebele_{lang}.jsonl"
        task_yaml(name, p, wino=False)
        tasks[name] = {"task": "belebele", "lang": lang, "path": p}
    return tasks


def run_lmeval(task_names: list[str], limit: int, bs: int, chat: bool = False) -> dict:
    import lm_eval
    global _TM
    if _TM is None:
        from lm_eval.tasks import TaskManager
        # index ONLY our local YAMLs (the 14k built-in YAMLs take minutes to scan on the network FS)
        _TM = TaskManager(include_path=str(TASK_DIR), include_defaults=False)
    tm = _TM
    res = lm_eval.simple_evaluate(model=get_hflm(bs), tasks=task_names, num_fewshot=0, limit=limit, log_samples=True,
                                  task_manager=tm, random_seed=SEED, numpy_random_seed=SEED, torch_random_seed=SEED,
                                  fewshot_random_seed=SEED, apply_chat_template=chat, bootstrap_iters=0)
    return res


def lmeval_to_rows(res: dict, tasks: dict, cond: str, variant: str) -> list[dict]:
    rows = []
    for tname, samples in res["samples"].items():
        info = tasks[tname]
        for s in samples:
            doc = s["doc"]
            # filtered_resps = [(loglik, is_greedy), ...] one per choice (lm-eval 0.4.x)
            lls = [float(r[0]) for r in s["filtered_resps"]]
            rows.append({"model": M, "cond": cond, "variant": variant, "task": info["task"], "lang": info["lang"],
                         "item_id": doc["id"], "pair_id": doc.get("pair_id"), "gold": int(doc["gold"]),
                         "n_choices": len(doc["choices"]), "acc": float(s["acc"]), "acc_norm": float(s["acc_norm"]),
                         "lls": lls})
    return rows


def stage_util_generic(kind: str, conds: list[str], task_names: list[str], limit: int, bs: int, chat: bool = False) -> None:
    tasks = ensure_task_files()
    for cond in conds:
        if cond not in STATES:
            logger.warning(f"{kind}: condition {cond} unavailable -> skipped")
            continue
        out = ITEMS / f"{kind}_{M}_{cond}.jsonl"
        if out.exists():
            logger.info(f"{kind}/{cond}: exists, skip")
            continue
        if past_deadline():
            logger.warning(f"deadline reached before {kind}/{cond}")
            return
        t = time.time()
        apply_state(cond)
        res = run_lmeval(task_names, limit, bs, chat=chat)
        rows = lmeval_to_rows(res, tasks, cond, kind)
        write_jsonl(out, rows)
        summ = {tn: {k: round(v, 4) for k, v in r.items() if k in ("acc,none", "acc_norm,none")} for tn, r in res["results"].items()}
        logger.info(f"{kind}/{cond} ({len(rows)} rows): {json.dumps(summ)}")
        tick(f"{kind}_{cond}", t)
    apply_state("orig")


def util_task_names(tasks_subset=None) -> list[str]:
    ts = tasks_subset or UTIL_TASKS
    return [f"rq3_{t}_{lang}" for t in ts for lang in ("en", "sl")]


# ------------------------------------------------------------------ STAGE pilot (screen) -----------------------------
def stage_pilot() -> None:
    t = time.time()
    tasks = ensure_task_files()
    apply_state("orig")
    res = run_lmeval(util_task_names(), ARGS.pilot_n, ARGS.util_bs)
    rows = lmeval_to_rows(res, tasks, "orig", "pilot")
    (RESULTS / "screen").mkdir(exist_ok=True)
    write_jsonl(RESULTS / "screen" / f"pilot_{M}.jsonl", rows)
    el = time.time() - t
    summ = {tn: {k: round(v, 3) for k, v in r.items() if k in ("acc,none", "acc_norm,none")} for tn, r in res["results"].items()}
    logger.info(f"PILOT {M}: {json.dumps(summ)} in {el:.0f}s")
    # batch-vs-single check on 32 loglik requests (own forward; exercising right-padding like lm-eval)
    items = read_jsonl(DATA / "util" / "arc_challenge_en.jsonl")[:8] + read_jsonl(DATA / "util" / "boolq_sl.jsonl")[:8]
    reqs = []
    for it in items:
        for ch in it["choices"][:2]:
            reqs.append((it["query"], " " + ch))
    reqs = reqs[:32]
    single = [ll_pair(c, x) for c, x in reqs]
    batched = ll_batch(reqs)
    d = [abs(a - b) for a, b in zip(single, batched)]
    agree = sum(int((single[i] > single[i + 1]) == (batched[i] > batched[i + 1])) for i in range(0, len(reqs) - 1, 2))
    enc = TOK("Question: test", add_special_tokens=True)["input_ids"]
    chk = {"pilot_seconds": round(el, 1), "n_items": len(rows), "sec_per_item": round(el / max(1, len(rows)), 3),
           "batch_vs_single_max_abs_dloglik": max(d), "batch_vs_single_pair_argmax_agree": f"{agree}/{len(reqs) // 2}",
           "bos_first": enc[0] == BOS, "bos_doubled": len(enc) > 1 and enc[1] == BOS, "summary": summ}
    (RESULTS / "screen" / f"pilot_{M}.json").write_text(json.dumps(chk, indent=2))
    logger.info(f"pilot checks: {chk}")
    tick("pilot", t)


# ------------------------------------------------------------------ own scorer (second code path) --------------------
def split_ctx_cont(ctx: str, cont: str) -> tuple[list[int], list[int]]:
    """lm-eval HFLM._encode_pair logic: move trailing context spaces to the continuation, encode whole, split."""
    n_sp = len(ctx) - len(ctx.rstrip())
    if n_sp > 0:
        cont = ctx[-n_sp:] + cont
        ctx = ctx[:-n_sp]
    whole = TOK(ctx + cont, add_special_tokens=False)["input_ids"]
    c_ids = TOK(ctx, add_special_tokens=False)["input_ids"]
    return [BOS] + c_ids, whole[len(c_ids):]


@torch.no_grad()
def ll_pair(ctx: str, cont: str) -> float:
    c_ids, x_ids = split_ctx_cont(ctx, cont)
    ids = (c_ids + x_ids)[-2048:]
    lp = logprobs_last(ids, len(x_ids) + 1)[:-1]
    return float(lp.gather(1, torch.tensor(x_ids, device=DEV)[:, None]).sum())


@torch.no_grad()
def ll_batch(reqs: list[tuple[str, str]], chunk: int = 8) -> list[float]:
    """Right-padded batched scoring (lm-eval style), in chunks of `chunk` requests."""
    if len(reqs) > chunk:
        return [v for i in range(0, len(reqs), chunk) for v in ll_batch(reqs[i:i + chunk], chunk)]
    enc = [split_ctx_cont(c, x) for c, x in reqs]
    L = max(len(a) + len(b) for a, b in enc)
    pad = TOK.pad_token_id if TOK.pad_token_id is not None else 0
    x = torch.full((len(enc), L), pad, dtype=torch.long)
    att = torch.zeros((len(enc), L), dtype=torch.long)
    for i, (a, b) in enumerate(enc):
        s = a + b
        x[i, :len(s)] = torch.tensor(s)
        att[i, :len(s)] = 1
    lg = NET(input_ids=x.to(DEV), attention_mask=att.to(DEV), use_cache=False).logits
    out = []
    for i, (a, b) in enumerate(enc):
        lp = F.log_softmax(lg[i, len(a) - 1:len(a) + len(b) - 1].float(), -1)
        out.append(float(lp.gather(1, torch.tensor(b, device=DEV)[:, None]).sum()))
    return out


def stage_scorer2_wino() -> None:
    """Verification of the Winogrande template deviation: lm-eval prepends its target delimiter ' ' to a continuation
    that already starts with ' ' (double space). Re-score 50 SL + 50 EN Winogrande items with the double-space
    continuation under orig and compare with lm-eval's logged logliks."""
    out = ITEMS / f"scorer2wino_{M}_orig.jsonl"
    if out.exists() or past_deadline():
        return
    t = time.time()
    apply_state("orig")
    rows = []
    for lang in ("sl", "en"):
        for it in read_jsonl(DATA / "util" / f"winogrande_{lang}.jsonl")[:50]:
            rows.append({"model": M, "cond": "orig", "task": "winogrande", "lang": lang, "item_id": it["id"],
                         "lls_double_space": [ll_pair(c, " " + it["query"]) for c in it["choices"]],
                         "lls_single_space": [ll_pair(c, it["query"]) for c in it["choices"]]})
    write_jsonl(out, rows)
    tick("scorer2_wino", t)


def stage_scorer2() -> None:
    """Own minimal torch scorer on 50 items per task (language alternates by task), orig + E_iter1."""
    lang_of = {"arc_challenge": "en", "boolq": "sl", "hellaswag": "en", "openbookqa": "sl", "piqa": "en", "winogrande": "sl"}
    for cond in ("orig", "E_iter1"):
        out = ITEMS / f"scorer2_{M}_{cond}.jsonl"
        if out.exists() or past_deadline():
            continue
        t = time.time()
        apply_state(cond)
        rows = []
        for task, lang in lang_of.items():
            for it in read_jsonl(DATA / "util" / f"{task}_{lang}.jsonl")[:50]:
                if task == "winogrande":  # partial scoring: contexts vary, continuation fixed
                    lls = [ll_pair(c, it["query"]) for c in it["choices"]]
                else:
                    lls = [ll_pair(it["query"], " " + ch) for ch in it["choices"]]
                rows.append({"model": M, "cond": cond, "task": task, "lang": lang, "item_id": it["id"], "lls": lls,
                             "pred": int(np.argmax(lls)), "gold": it["gold"]})
        write_jsonl(out, rows)
        tick(f"scorer2_{cond}", t)
    apply_state("orig")


# ------------------------------------------------------------------ KL -----------------------------------------------
@torch.no_grad()
def greedy_batch(prompts_ids: list[list[int]], max_new: int, bs: int) -> list[list[int]]:
    """Left-padded batched greedy generation; returns new token ids (cut at first EOS/<end_of_turn>, exclusive)."""
    pad = TOK.pad_token_id if TOK.pad_token_id is not None else 0
    order = sorted(range(len(prompts_ids)), key=lambda i: len(prompts_ids[i]))
    res: list[list[int]] = [[] for _ in prompts_ids]
    i = 0
    cur_bs = bs
    while i < len(order):
        idx = order[i:i + cur_bs]
        L = max(len(prompts_ids[k]) for k in idx)
        x = torch.full((len(idx), L), pad, dtype=torch.long)
        att = torch.zeros((len(idx), L), dtype=torch.long)
        for r, k in enumerate(idx):
            s = prompts_ids[k]
            x[r, L - len(s):] = torch.tensor(s)
            att[r, L - len(s):] = 1
        try:
            out = NET.generate(input_ids=x.to(DEV), attention_mask=att.to(DEV), max_new_tokens=max_new, do_sample=False,
                               pad_token_id=pad, disable_compile=True)
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            cur_bs = max(1, cur_bs // 2)
            logger.warning(f"generate OOM -> bs {cur_bs}")
            continue
        for r, k in enumerate(idx):
            new = out[r, L:].tolist()
            cut = []
            for tkn in new:
                if tkn in EOS_IDS or tkn == pad:
                    break
                cut.append(tkn)
            res[k] = cut
        i += len(idx)
    return res


def kl_items() -> list[dict]:
    rows = [r for r in read_jsonl(DATA / "harmless" / "harmless_mt.jsonl") if not r.get("spare")][:ARGS.n_kl]
    return rows


def stage_kl() -> None:
    out = ITEMS / f"kl_{M}.jsonl"
    done = {(r["item_id"], r["arm"]) for r in read_jsonl(out)}
    conds = [c for c in ARGS.kl_conds.split(",") if c in STATES] + [c for c in STATES if c.startswith(("E_art2", "rand_art2"))]
    items = kl_items()
    cont_p = OUTM / "kl_orig_continuations.jsonl"
    cont = {(r["item_id"], r["arm"]): r["cont_ids"] for r in read_jsonl(cont_p)}
    t = time.time()
    apply_state("orig")
    todo_prompts = []
    for arm in ("en_orig", "en_bt", "sl_mt", "hu_mt"):
        for it in items:
            if (it["id"], arm) not in cont:
                todo_prompts.append((it["id"], arm, render_chat(it[arm])))
    if todo_prompts:
        gens = greedy_batch([p[2] for p in todo_prompts], 32, ARGS.gen_bs * 2)
        append_jsonl(cont_p, [{"item_id": a, "arm": b, "cont_ids": g} for (a, b, _), g in zip(todo_prompts, gens)])
        for (a, b, _), g in zip(todo_prompts, gens):
            cont[(a, b)] = g
    tick("kl_orig_continuations", t)
    t = time.time()
    n_done = 0
    for arm in ("en_orig", "en_bt", "sl_mt", "hu_mt"):
        for it in items:
            if (it["id"], arm) in done:
                continue
            if past_deadline():
                logger.warning("deadline reached inside KL stage")
                return
            ids = render_chat(it[arm])
            c = cont[(it["id"], arm)][:32]
            seq = ids + c
            n_keep = len(c) + 1
            apply_state("orig")
            lp_o = logprobs_last(seq, n_keep)[:max(1, len(c))]
            row = {"model": M, "item_id": it["id"], "arm": arm, "n_prompt": len(ids), "n_cont": len(c), "kl": {}}
            for cond in conds:
                apply_state(cond)
                lp_c = logprobs_last(seq, n_keep)[:max(1, len(c))]
                k = kl_rows(lp_o, lp_c)
                row["kl"][cond] = {"first": float(k[0]), "multi": float(k.mean())}
            apply_state("orig")  # self-KL floor: orig re-run after the adapters were swapped in and out
            lp_s = logprobs_last(seq, n_keep)[:max(1, len(c))]
            k = kl_rows(lp_o, lp_s)
            row["kl"]["self"] = {"first": float(k[0]), "multi": float(k.mean())}
            append_jsonl(out, [row])
            n_done += 1
            if n_done % 50 == 0:
                logger.info(f"KL {n_done} rows done ({(time.time() - t) / n_done:.2f}s/row); last {arm}: "
                            f"E_iter1={row['kl'].get('E_iter1', {}).get('first', float('nan')):.4f} self={row['kl']['self']['first']:.2e}")
    apply_state("orig")
    tick("kl", t)


def stage_kl_extra() -> None:
    """KL for conditions discovered AFTER the main KL stage (e.g. E_art2): same items, arms, continuations and
    batch-size-1 protocol; the original model is re-run per item (self floor is exactly 0 at bs 1)."""
    conds = [c for c in ARGS.kl_extra_conds.split(",") if c and c in STATES]
    if not conds:
        return
    out = ITEMS / f"klextra_{M}.jsonl"
    done = {(r["item_id"], r["arm"]) for r in read_jsonl(out)}
    cont = {(r["item_id"], r["arm"]): r["cont_ids"] for r in read_jsonl(OUTM / "kl_orig_continuations.jsonl")}
    t = time.time()
    for arm in ("en_orig", "en_bt", "sl_mt", "hu_mt"):
        for it in kl_items():
            if (it["id"], arm) in done or (it["id"], arm) not in cont:
                continue
            if past_deadline():
                logger.warning("deadline reached inside KL-extra stage")
                return
            ids = render_chat(it[arm])
            c = cont[(it["id"], arm)][:32]
            seq, n_keep = ids + c, len(c) + 1
            apply_state("orig")
            lp_o = logprobs_last(seq, n_keep)[:max(1, len(c))]
            row = {"model": M, "item_id": it["id"], "arm": arm, "n_prompt": len(ids), "n_cont": len(c), "kl": {}}
            for cond in conds:
                apply_state(cond)
                k = kl_rows(lp_o, logprobs_last(seq, n_keep)[:max(1, len(c))])
                row["kl"][cond] = {"first": float(k[0]), "multi": float(k.mean())}
            append_jsonl(out, [row])
    apply_state("orig")
    tick("kl_extra", t)


@torch.no_grad()
def first_token_lp_batched(prompts_ids: list[list[int]], bs: int) -> torch.Tensor:
    """Heretic-style: LEFT-padded batches, next-token log-probs at the last position (fp32)."""
    pad = TOK.pad_token_id if TOK.pad_token_id is not None else 0
    outs = []
    for i in range(0, len(prompts_ids), bs):
        chunk = prompts_ids[i:i + bs]
        L = max(len(x) for x in chunk)
        x = torch.full((len(chunk), L), pad, dtype=torch.long)
        att = torch.zeros((len(chunk), L), dtype=torch.long)
        for r, sq in enumerate(chunk):
            x[r, L - len(sq):] = torch.tensor(sq)
            att[r, L - len(sq):] = 1
        lg = NET(input_ids=x.to(DEV), attention_mask=att.to(DEV), logits_to_keep=1, use_cache=False).logits[:, -1].float()
        outs.append(F.log_softmax(lg, -1))
    return torch.cat(outs)


def stage_hkl_batched() -> None:
    """DIAGNOSTIC for the Gemma manipulation-check gap: Heretic's evaluator measured the pick KL on LEFT-PADDED batches
    (batch_size 128); this recomputes the same first-token KL on harmless_alpaca test[:100] with left-padded batches of
    100 and of 16, next to the batch-size-1 value, for orig (self-KL under padding), E_iter1 and E_art2."""
    out = OUTM / "manipulation_check_batched.json"
    if out.exists() or past_deadline():
        return
    t = time.time()
    prompts = heretic_kl_prompts()
    res = {}
    for bs in (100, 16):
        apply_state("orig")
        base_b = first_token_lp_batched(prompts, bs)
        res[f"bs{bs}"] = {}
        for c in [c for c in ("orig", "E_iter1", "E_art2") if c in STATES]:
            apply_state(c)
            lp = first_token_lp_batched(prompts, bs)
            res[f"bs{bs}"][c] = float(kl_rows(base_b, lp).mean())
    apply_state("orig")
    base1 = torch.stack([logprobs_last(ids, 1)[0] for ids in prompts])
    base100 = first_token_lp_batched(prompts, 100)
    res["orig_bs100_vs_orig_bs1_selfKL"] = float(kl_rows(base1, base100).mean())
    mc = json.loads((OUTM / "manipulation_check.json").read_text())["heretic_style_kl"]
    res["bs1_from_manipulation_check"] = {c: mc.get(c) for c in ("E_iter1", "E_art2") if c in mc}
    out.write_text(json.dumps(res, indent=2))
    logger.info(f"batched Heretic-style KL diagnostic: {res}")
    tick("hkl_batched", t)


def stage_hkl_sys() -> None:
    """DIAGNOSTIC 2 for the Gemma manipulation-check gap: batching did not explain it, so test prompt rendering.
    Heretic's unpatched path renders [system:'', user:x]; iter-1 found the empty system turn CHANGES the Gemma string.
    Recompute the batch-size-1 first-token KL on harmless_alpaca test[:100] with that rendering."""
    out = OUTM / "manipulation_check_sysrender.json"
    if out.exists() or past_deadline():
        return
    from datasets import load_dataset
    t = time.time()
    ds = load_dataset("mlabonne/harmless_alpaca", split="test[:100]")
    prompts = []
    for r in ds:
        s_ = TOK.apply_chat_template([{"role": "system", "content": ""}, {"role": "user", "content": r["text"]}],
                                     add_generation_prompt=True, tokenize=False)
        prompts.append(TOK(s_, add_special_tokens=False)["input_ids"])
    changed = s_ != TOK.apply_chat_template([{"role": "user", "content": r["text"]}], add_generation_prompt=True, tokenize=False)
    apply_state("orig")
    base = [logprobs_last(ids, 1)[0] for ids in prompts]
    res = {"empty_system_changes_rendering": bool(changed), "example": s_[:300]}
    for c in [c for c in ("E_iter1", "E_art2") if c in STATES]:
        apply_state(c)
        res[c] = float(np.mean([float(kl_rows(b[None], logprobs_last(ids, 1))[0]) for b, ids in zip(base, prompts)]))
    apply_state("orig")
    out.write_text(json.dumps(res, indent=2))
    logger.info(f"system-render KL diagnostic: {res}")
    tick("hkl_sys", t)


# ------------------------------------------------------------------ BPB ----------------------------------------------
def stage_bpb() -> None:
    out = ITEMS / f"bpb_{M}.jsonl"
    done = {(r["item_id"], r["lang"]) for r in read_jsonl(out)}
    conds = [c for c in ARGS.bpb_conds.split(",") if c in STATES] + (["E_art2"] if "E_art2" in STATES else [])
    t = time.time()
    for lang in ("en", "sl", "hu"):
        for it in read_jsonl(DATA / "fluency" / f"passages_{lang}.jsonl")[:ARGS.n_bpb]:
            if (it["id"], lang) in done:
                continue
            if past_deadline():
                return
            ids = [BOS] + TOK(it["text"], add_special_tokens=False)["input_ids"]
            ids = ids[:1024]
            tgt = torch.tensor(ids[1:], device=DEV)[:, None]
            nbytes = len(TOK.decode(ids[1:]).encode("utf-8"))
            row = {"model": M, "item_id": it["id"], "lang": lang, "n_tokens": len(ids) - 1, "n_bytes": nbytes, "nll": {}}
            for cond in conds:
                apply_state(cond)
                lp = logprobs_last(ids, len(ids))[:-1]
                row["nll"][cond] = float(-lp.gather(1, tgt).sum())
            row["bpb"] = {c: v / (nbytes * math.log(2)) for c, v in row["nll"].items()}
            append_jsonl(out, [row])
    apply_state("orig")
    tick("bpb", t)


# ------------------------------------------------------------------ generations --------------------------------------
def stage_gen() -> None:
    items = kl_items()
    arms = ARGS.gen_langs.split(",")
    plan = [(c, ARGS.n_gen) for c in ARGS.gen_conds.split(",")] + \
        [(c, ARGS.n_gen_lambda) for c in ARGS.gen_lambda_conds.split(",") if c] + \
        ([("E_art2", ARGS.n_gen)] if "E_art2" in STATES else [])
    for cond, n in plan:
        if cond not in STATES:
            continue
        out = ITEMS / f"gen_{M}_{cond}.jsonl"
        if out.exists():
            continue
        if past_deadline():
            return
        t = time.time()
        apply_state(cond)
        prompts = [(it["id"], arm, render_chat(it[arm])) for arm in arms for it in items[:n]]
        gens = greedy_batch([p[2] for p in prompts], 128, ARGS.gen_bs)
        rows = [{"model": M, "cond": cond, "item_id": a, "arm": b, "n_new": len(g), "text": TOK.decode(g, skip_special_tokens=True)}
                for (a, b, _), g in zip(prompts, gens)]
        write_jsonl(out, rows)
        tick(f"gen_{cond}", t)
    apply_state("orig")


# ------------------------------------------------------------------ main ---------------------------------------------
@logger.catch(reraise=True)
def main() -> None:
    stages = ARGS.stages.split(",")
    stage_build()
    if "pilot" in stages:
        stage_pilot()
    lam_tasks = util_task_names(["arc_challenge", "boolq", "openbookqa", "winogrande"])
    for st in stages:
        if past_deadline():
            logger.warning(f"deadline reached; not starting {st}")
            break
        if st == "util":
            stage_util_generic("util", [c for c in ARGS.util_conds.split(",")] + (["E_art2", "rand_art2_j1"] if "E_art2" in STATES else []),
                               util_task_names(), ARGS.n_util, ARGS.util_bs)
            stage_util_generic("utillam", [c for c in ARGS.lambda_conds.split(",") if c], lam_tasks, ARGS.n_util_lambda, ARGS.util_bs)
        elif st == "belebele":
            stage_util_generic("bele", ARGS.bele_conds.split(",") + (["E_art2"] if "E_art2" in STATES else []),
                               [f"rq3_belebele_{l}" for l in ("en", "sl", "hu")], ARGS.n_bele, max(1, ARGS.util_bs // 2))
        elif st == "chat":
            stage_util_generic("chat", ["orig", "E_iter1"], util_task_names(["arc_challenge", "boolq"]), 100, ARGS.util_bs, chat=True)
        elif st == "scorer2":
            stage_scorer2()
            stage_scorer2_wino()
        elif st == "kl":
            stage_kl()
        elif st == "kl_extra":
            stage_kl_extra()
        elif st == "hkl":
            stage_hkl_batched()
        elif st == "hkl_sys":
            stage_hkl_sys()
        elif st == "bpb":
            stage_bpb()
        elif st == "gen":
            stage_gen()
    logger.info(f"DONE {M} stages={stages} total {time.time() - T0:.0f}s")


if __name__ == "__main__":
    main()
