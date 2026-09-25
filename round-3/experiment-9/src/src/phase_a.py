#!/usr/bin/env python3
"""S5 PHASE A (HF + Heretic @3521f86, NF4; identical code path for both siblings).

LOAD -> CHECKS (template sha1, 32-item batch-vs-single on DEV12) -> Heretic setup (fresh residual directions; cosine vs exp8)
-> 40 paired start-up trials (TPESampler(seed=20260925, n_startup_trials=40, multivariate=True): every draw is a seeded
random draw, so the parameters are identical across models by construction; the English objective is untouched; NOTHING
is logged inside the objective) -> each trial's PEFT adapter saved to adapters/{model}/trial_KK/ -> non-interference replay
of trial 1 (objective values + LoRA hash) -> SELECT (Heretic rule, pre-registered fallbacks) -> selected/{model}/ (adapter,
journal, trials.json) -> lambda adapters (lora_B x lambda; lambda=1 reproduction of the Heretic scores) -> 5 random-direction
edits (per module: orthogonal to the Heretic direction, massive dim zeroed, ||dW||_F matched to the selected edit; each
with its own first-token KL) -> C5a (first-token KL on exp8 eval_kl EN/SL stems; selected vs random) -> HF reference
generations for the vLLM engine gate (Gemma only: DEV12 x {EN-BT, SL-MT} + 40 dolly harmless at lambda in {0, 1}).

Usage: .venv/bin/python src/phase_a.py --model gemma_it [--n-trials 40]
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import shutil
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

try:  # trap: torch 2.14 routes some ops to Triton 'native' kernels that need a C compiler
    from torch._native import registry as _nr
    _nr.deregister_op_overrides(disable_dsl_names=["triton", "cutedsl", "helion", "nvmath"])
    TRITON_DEREG = "deregistered"
except (ImportError, AttributeError, RuntimeError, ValueError) as _e:
    TRITON_DEREG = f"not_deregistered:{_e}"

from common import (DATA, EXP4, EXP8, MODELS, RESULTS, SEED, WS, Lexicon, read_jsonl, setup_logger,  # noqa: E402
                    write_jsonl)
import probe as P  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=list(MODELS))
ap.add_argument("--n-trials", type=int, default=40)
ap.add_argument("--n-random", type=int, default=5)
ap.add_argument("--heretic-bs", type=int, default=128)
ARGS = ap.parse_args()

M = ARGS.model
OUT = RESULTS / M
OUT.mkdir(parents=True, exist_ok=True)
ADIR = WS / "adapters" / M
ADIR.mkdir(parents=True, exist_ok=True)
SEL = WS / "selected" / M
logger = setup_logger(f"phase_a_{M}")
T0 = time.time()
CHECKS = json.loads((OUT / "phase_a_checks.json").read_text()) if (OUT / "phase_a_checks.json").exists() else {}
TIMING = CHECKS.setdefault("timing", {})
LAMBDAS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]

import heretic.model as hm  # noqa: E402
from heretic.config import Settings  # noqa: E402
from heretic.evaluator import Evaluator  # noqa: E402
from heretic.model import AbliterationParameters, Model  # noqa: E402
from heretic.utils import load_prompts  # noqa: E402
import optuna  # noqa: E402
from optuna.samplers import TPESampler  # noqa: E402
from optuna.storages import JournalStorage  # noqa: E402
from optuna.storages.journal import JournalFileBackend  # noqa: E402

optuna.logging.set_verbosity(optuna.logging.WARNING)


def patched_generate(self, prompts, **kwargs):
    """iter-1 template patch: drop an EMPTY system turn (identically for both models); disable_compile."""
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


def save():
    (OUT / "phase_a_checks.json").write_text(json.dumps(CHECKS, indent=2, ensure_ascii=False, default=str))


def tick(name: str, t: float):
    TIMING[name] = round(time.time() - t, 1)
    logger.info(f"[time] {name}: {TIMING[name]}s (total {time.time() - T0:.0f}s)")
    save()


def write_settings() -> Settings:
    txt = (EXP4 / "results" / "gemma_it" / "cfg" / "config.toml").read_text()
    rep = {"seed = 20260923\n": f"seed = {SEED}\n", "n_trials = 80": f"n_trials = {ARGS.n_trials}",
           "n_startup_trials = 25": f"n_startup_trials = {ARGS.n_trials}",
           "batch_size = 128  #": f"batch_size = {ARGS.heretic_bs}  #"}
    for a, b in rep.items():
        assert a in txt, a
        txt = txt.replace(a, b)
    txt = txt.replace(str(EXP4 / "results" / "gemma_it" / "heretic_ckpt"), str(OUT / "heretic_ckpt"))
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
    assert s.n_startup_trials == ARGS.n_trials == s.n_trials
    return s


def lora_modules(model: Model):
    from peft.tuners.lora import LoraLayer
    return [(n, m) for n, m in model.model.named_modules() if isinstance(m, LoraLayer)]


def lora_state(model: Model) -> dict[str, torch.Tensor]:
    return {n: p.detach().float().cpu().clone() for n, p in model.model.named_parameters() if "lora_" in n}


def lora_hash(model: Model) -> str:
    h = hashlib.sha1()
    for n, p in model.model.named_parameters():
        if "lora_" in n:
            h.update(p.detach().float().cpu().numpy().tobytes())
    return h.hexdigest()


def load_lora_state(model: Model, st: dict[str, torch.Tensor], lam: float = 1.0):
    params = dict(model.model.named_parameters())
    for n, v in st.items():
        vv = v * lam if "lora_B" in n else v
        params[n].data = vv.to(params[n].device, params[n].dtype)


def save_adapter(model: Model, path: Path, st: dict[str, torch.Tensor] | None = None, lam: float = 1.0, meta: dict | None = None):
    """PEFT-format adapter (adapter_config.json + adapter_model.safetensors); lora_B pre-multiplied by lambda."""
    path.mkdir(parents=True, exist_ok=True)
    if st is not None:
        load_lora_state(model, st, lam)
    model.model.save_pretrained(str(path))
    if meta:
        (path / "meta.json").write_text(json.dumps(meta, indent=1, default=str))


def dW_norms(st: dict[str, torch.Tensor]) -> dict[str, float]:
    """per LoRA module ||B A||_F (exact for low rank): sqrt(trace((B^T B)(A A^T)))."""
    out = {}
    for n, A in st.items():
        if "lora_A" not in n:
            continue
        B = st[n.replace("lora_A", "lora_B")]
        out[n.rsplit(".lora_A", 1)[0]] = float(torch.sqrt(torch.trace((B.T @ B) @ (A @ A.T)).clamp(min=0)))
    return out


@torch.inference_mode()
def residuals_last(model: Model, tok, users: list[str]) -> torch.Tensor:
    seqs = P.encode(tok, P.render(tok, users))
    out = [None] * len(seqs)
    mdl = model.model
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


@logger.catch(reraise=True)
def main():
    torch.manual_seed(SEED)
    torch.cuda.set_per_process_memory_fraction(0.95)
    settings = write_settings()
    CHECKS["triton"] = TRITON_DEREG
    t = time.time()
    model = Model(settings)
    tick("load", t)
    tok = model.tokenizer
    lex = Lexicon(settings.model_extra["scorer"]["KeywordRate"]["keyword_markers"])
    nL = len(model.get_layers())
    CHECKS.update({"n_layers": nL, "components": model.get_abliterable_components(),
                   "vram_after_load_GB": round(torch.cuda.memory_allocated() / 1e9, 2), "gpu": torch.cuda.get_device_name(0),
                   "lora_rank": model.peft_config.r, "row_normalization": str(settings.row_normalization)})
    DEV = read_jsonl(DATA / "dev12.jsonl")
    # ---- template ----
    x = DEV[0]["en_orig"]
    ours = P.render(tok, [x])[0]
    no_sys = tok.apply_chat_template([[{"role": "user", "content": x}]], add_generation_prompt=True, tokenize=False)[0]
    ref8 = read_jsonl(EXP8 / "data" / "probe_P200.jsonl")[0]["en_orig"]  # exp8 logged sha1 of this rendered string
    r8 = P.render(tok, [ref8])[0]
    ids = tok(ours, return_token_type_ids=False)["input_ids"]
    CHECKS["template"] = {"exp8_ref_rendered_sha1": hashlib.sha1(r8.encode()).hexdigest(),
                          "expected_sha1": "389de5ab5394afc45819e628137462d5145239e8",
                          "matches_expected": hashlib.sha1(r8.encode()).hexdigest() == "389de5ab5394afc45819e628137462d5145239e8",
                          "equals_no_system": ours == no_sys, "double_bos": ids[0] == ids[1] == tok.bos_token_id}
    logger.info(f"template {CHECKS['template']}")
    save()
    # ---- batch vs single (DEV12 only) ----
    if "batch_vs_single" not in CHECKS:
        t = time.time()
        users = [d["en_bt"] for d in DEV] + [d["sl_mt"] for d in DEV] + [d["en_orig"] for d in DEV[:8]]
        seqs = P.encode(tok, P.render(tok, users))
        bt, _ = P.generate(model.model, tok, seqs, 32)
        st_ = [P.generate(model.model, tok, [s], 32)[0][0] for s in seqs]
        CHECKS["batch_vs_single"] = {"n": len(seqs), "max_new": 32, "token_identical": sum(a == b for a, b in zip(bt, st_)),
                                     "lex_outcome_agree": sum(lex.hit(a) == lex.hit(b) for a, b in zip(bt, st_))}
        CHECKS["four_vs_eight_bit"] = "skipped (time budget; logged per SHARED SPEC (2))"
        tick("batch_vs_single", t)
        logger.info(f"batch-vs-single {CHECKS['batch_vs_single']}")

    # ---- Heretic setup (verbatim logic) ----
    t = time.time()
    good_prompts = load_prompts(settings, settings.good_prompts)
    bad_prompts = load_prompts(settings, settings.bad_prompts)
    settings.response_prefix = settings.response_prefix or ""
    evaluator = Evaluator(settings, model)
    CHECKS["heretic_baseline_scores"] = {n: s.value for n, s in evaluator.baseline_scores}
    good_means = model.get_residuals_mean(good_prompts)
    bad_means = model.get_residuals_mean(bad_prompts)
    rd = F.normalize(bad_means - good_means, p=2, dim=1)
    if settings.orthogonalize_direction:
        gd = F.normalize(good_means, p=2, dim=1)
        proj = torch.sum(rd * gd, dim=1)
        rd = F.normalize(rd - proj.unsqueeze(1) * gd, p=2, dim=1)
    torch.save(rd.cpu(), OUT / "residual_directions.pt")
    try:
        rd8 = torch.load(EXP8 / "results" / M / "residual_directions.pt").to(rd.device, rd.dtype)
        cos = (rd * rd8).sum(1)[1:]  # index 0 = embeddings (zero direction in exp8)
        CHECKS["residual_directions_cos_vs_exp8"] = {"min_layers1plus": float(cos.min()), "median": float(cos.median()),
                                                     "n_ge_0.99": int((cos >= 0.99).sum()), "n": int(cos.numel())}
    except (FileNotFoundError, RuntimeError) as e:
        CHECKS["residual_directions_cos_vs_exp8"] = f"unavailable: {e}"
    del good_means, bad_means
    tick("heretic_setup", t)
    logger.info(f"baseline {CHECKS['heretic_baseline_scores']}; cos vs exp8 {CHECKS['residual_directions_cos_vs_exp8']}")

    # ---- 40 paired start-up trials ----
    journal = OUT / "heretic_study.journal"
    storage = JournalStorage(JournalFileBackend(str(journal)))
    study = optuna.create_study(
        sampler=TPESampler(n_startup_trials=settings.n_startup_trials, n_ei_candidates=128, multivariate=True,
                           seed=settings.seed),
        storage=storage, directions=evaluator.get_objective_directions(), study_name="heretic", load_if_exists=True)
    state = {"i": len([tr for tr in study.trials if tr.values is not None])}
    assert state["i"] == len(study.trials), "journal has unfinished trials; delete it and restart (start-up RNG would desync)"

    def objective(trial):
        # ---------------- verbatim Heretic objective (main.py @3521f864); nothing else is logged inside ----------------
        t_start = time.perf_counter()
        state["i"] += 1
        k = state["i"]
        trial.set_user_attr("index", k)
        direction_scope = trial.suggest_categorical("direction_scope", ["global", "per layer"])
        last = nL - 1
        direction_index = trial.suggest_float("direction_index", 0.4 * last, 0.9 * last)
        if direction_scope == "per layer":
            direction_index = None
        params = {}
        for comp in model.get_abliterable_components():
            lb = -0.25 if comp == "mlp.down_proj" else 0.8
            max_weight = max(0.0, trial.suggest_float(f"{comp}.max_weight", lb, 1.5))
            max_weight_position = trial.suggest_float(f"{comp}.max_weight_position", 0.6 * last, 1.0 * last)
            min_weight = trial.suggest_float(f"{comp}.min_weight", 0.0, 1.0)
            min_weight_distance = trial.suggest_float(f"{comp}.min_weight_distance", 1.0, max(0.6 * last, 1.0))
            params[comp] = AbliterationParameters(max_weight=max_weight, max_weight_position=max_weight_position,
                                                  min_weight=(min_weight * max_weight), min_weight_distance=min_weight_distance)
        trial.set_user_attr("direction_index", direction_index)
        trial.set_user_attr("parameters", {c: asdict(v) for c, v in params.items()})
        model.reset_model()
        model.abliterate(rd, direction_index, params)
        scores = evaluator.get_scores()
        ov = evaluator.get_objective_values(scores)
        trial.set_user_attr("scores", evaluator.get_paired_score_records(scores))
        trial.set_user_attr("t_objective_s", round(time.perf_counter() - t_start, 1))
        # adapter export happens AFTER the objective values are fixed (does not touch them)
        save_adapter(model, ADIR / f"trial_{k:02d}", meta={"index": k, "values": [float(v) for v in ov],
                                                            "params": trial.params, "lora_sha1": lora_hash(model)})
        logger.info(f"trial {k}: refusals={ov[0]:.3f} KL={ov[1]:.4f} t={time.perf_counter() - t_start:.0f}s")
        return ov

    t = time.time()
    rem = ARGS.n_trials - state["i"]
    if rem > 0:
        study.optimize(objective, n_trials=rem)
    tick("trials", t)
    trials = [{"number": tr.number, "values": list(tr.values) if tr.values else None, "params": tr.params,
               "user_attrs": tr.user_attrs, "state": str(tr.state)} for tr in study.trials]
    (OUT / "trials.json").write_text(json.dumps(trials, indent=1, default=str))

    # ---- non-interference replay of trial 1 ----
    tr1 = [tr for tr in study.trials if tr.user_attrs.get("index") == 1][0]
    p1 = {k: AbliterationParameters(**v) for k, v in tr1.user_attrs["parameters"].items()}
    model.reset_model()
    model.abliterate(rd, tr1.user_attrs["direction_index"], p1)
    ov = evaluator.get_objective_values(evaluator.get_scores())
    meta1 = json.loads((ADIR / "trial_01" / "meta.json").read_text())
    CHECKS["replay_trial1"] = {"original": list(tr1.values), "replay": [float(v) for v in ov],
                               "identical_values": [round(a, 6) for a in tr1.values] == [round(float(b), 6) for b in ov],
                               "lora_sha1_identical": lora_hash(model) == meta1["lora_sha1"]}
    logger.info(f"replay {CHECKS['replay_trial1']}")

    # ---- SELECT ----
    done = [(tr.user_attrs["index"], tr.values[0], tr.values[1], tr) for tr in study.trials if tr.values]
    rule = "heretic: lowest KL among refusals <= 0.10"
    cand = [d for d in done if d[1] <= 0.10]
    if cand:
        pick = min(cand, key=lambda d: d[2])
    else:
        cand = [d for d in done if d[2] <= 0.5]
        if cand:
            rule = "fallback F4: lowest-refusal trial with KL <= 0.5 (ties -> lower KL)"
            pick = min(cand, key=lambda d: (d[1], d[2]))
        else:
            rule = "fallback 2: lowest KL among the 5 lowest-refusal trials"
            pick = min(sorted(done, key=lambda d: d[1])[:5], key=lambda d: d[2])
    k_sel = pick[0]
    CHECKS["selection"] = {"index": k_sel, "refusals": pick[1], "kl": pick[2], "rule": rule,
                           "params": pick[3].params, "direction_index": pick[3].user_attrs["direction_index"]}
    logger.info(f"SELECTED trial {k_sel}: {CHECKS['selection']}")
    if SEL.exists():
        shutil.rmtree(SEL)
    shutil.copytree(ADIR / f"trial_{k_sel:02d}", SEL / "adapter")
    shutil.copy(journal, SEL / "heretic_study.journal")
    shutil.copy(OUT / "trials.json", SEL / "trials.json")
    shutil.copy(OUT / "residual_directions.pt", SEL / "residual_directions.pt")
    (SEL / "selection.json").write_text(json.dumps(CHECKS["selection"], indent=1, default=str))

    # ---- lambda adapters + lambda=1 reproduction ----
    psel = {k: AbliterationParameters(**v) for k, v in pick[3].user_attrs["parameters"].items()}
    model.reset_model()
    model.abliterate(rd, pick[3].user_attrs["direction_index"], psel)
    st_sel = lora_state(model)
    ov1 = evaluator.get_objective_values(evaluator.get_scores())
    CHECKS["lambda1_reproduction"] = {"trial_values": [pick[1], pick[2]], "rebuilt": [float(v) for v in ov1],
                                      "identical": [round(pick[1], 6), round(pick[2], 6)] == [round(float(v), 6) for v in ov1]}
    lam_scores = {}
    for lam in LAMBDAS:
        load_lora_state(model, st_sel, lam)
        save_adapter(model, ADIR / f"lambda_{lam:.2f}", meta={"lambda": lam, "selected_trial": k_sel})
        if lam in (0.5, 1.0, 1.5, 2.0):
            lam_scores[lam] = [float(v) for v in evaluator.get_objective_values(evaluator.get_scores())]
    CHECKS["lambda_heretic_scores"] = lam_scores
    logger.info(f"lambda=1 repro {CHECKS['lambda1_reproduction']}; lambda heretic scores {lam_scores}")
    save()

    # ---- base first-token log-probs for KL readouts (C5a stems + harmless dolly) ----
    eval_kl = read_jsonl(EXP8 / "data" / "eval_kl.jsonl")
    enc = {lang: P.encode(tok, P.render(tok, [p[lang] for p in eval_kl])) for lang in ("en", "sl")}
    model.reset_model()
    base_lp = {lang: P.first_token_logprobs(model.model, enc[lang]).half() for lang in ("en", "sl")}

    def kl_now() -> dict:
        return {lang: P.kl_items(model.model, enc[lang], base_lp[lang]) for lang in ("en", "sl")}

    c5a_rows = []
    load_lora_state(model, st_sel, 1.0)
    kl = kl_now()
    c5a_rows += [{"edit": "selected", "seed": 0, "lang": lang, "item_id": p["pair_id"], "kl": v}
                 for lang in kl for p, v in zip(eval_kl, kl[lang])]

    # ---- random-direction edits: orthogonal to the Heretic direction, massive dim zeroed, ||dW||_F matched ----
    t = time.time()
    dev_users = [d["en_orig"] for d in read_jsonl(DATA / "gate_harmless40.jsonl")[:32]]
    model.reset_model()
    hs = residuals_last(model, tok, dev_users)  # [N, L+1, d]
    massive = int(hs[:, 1:].abs().mean(dim=(0, 1)).argmax())
    CHECKS["massive_dim"] = {"argmax_mean_abs_last_token": massive, "expected_gemma": 2339}
    del hs
    norms_sel = dW_norms(st_sel)
    di = pick[3].user_attrs["direction_index"]
    if di is None:
        Hdir = rd.clone()
    else:
        w, idx = math.modf(di + 1)
        g = F.normalize(rd[int(idx)].lerp(rd[int(idx) + 1], w), p=2, dim=0)
        Hdir = g.unsqueeze(0).expand_as(rd).clone()
    rand_meta = []
    s, n_repl = 1, 0
    while len(rand_meta) < ARGS.n_random and s <= ARGS.n_random + 3:
        gen = torch.Generator().manual_seed(SEED + s)
        R = torch.randn(rd.shape, generator=gen).to(rd.device, rd.dtype)
        R[:, massive] = 0.0
        hd = Hdir.to(R.device, R.dtype)
        R = R - (R * hd).sum(1, keepdim=True) * hd
        R[:, massive] = 0.0
        R = F.normalize(R, p=2, dim=1)
        model.reset_model()
        model.abliterate(R, None, psel)
        st_r = lora_state(model)
        nr = dW_norms(st_r)
        for n in list(st_r):
            if "lora_B" in n:
                key = n.rsplit(".lora_B", 1)[0]
                a, b = norms_sel.get(key, 0.0), nr.get(key, 0.0)
                st_r[n] = st_r[n] * (a / b if b > 0 else 0.0)
        load_lora_state(model, st_r, 1.0)
        nr2 = dW_norms(st_r)
        match = float(np.median([nr2[k] / norms_sel[k] for k in norms_sel if norms_sel[k] > 0]))
        kl = kl_now()
        kl_en_mean = float(np.mean(kl["en"]))
        ov_r = [float(v) for v in evaluator.get_objective_values(evaluator.get_scores())]
        kl_sel_en = float(np.mean([r["kl"] for r in c5a_rows if r["edit"] == "selected" and r["lang"] == "en"]))
        catastrophic = ov_r[1] > 3 * max(pick[2], 1e-6) and kl_en_mean > 3 * max(kl_sel_en, 1e-6)
        if catastrophic and n_repl < 3:
            n_repl += 1
            logger.warning(f"random seed {s} catastrophic (KL {ov_r[1]:.3f}) -> replaced")
            CHECKS.setdefault("random_replaced_seeds", []).append({"seed": SEED + s, "heretic_scores": ov_r})
            s += 1
            continue
        j = len(rand_meta) + 1
        save_adapter(model, ADIR / f"rand_{j}", meta={"seed": SEED + s, "norm_match_median_ratio": match})
        c5a_rows += [{"edit": "random", "seed": j, "lang": lang, "item_id": p["pair_id"], "kl": v}
                     for lang in kl for p, v in zip(eval_kl, kl[lang])]
        rand_meta.append({"rand_index": j, "seed": SEED + s, "norm_match_median_ratio": match, "heretic_scores": ov_r,
                          "kl_eval_en_mean": kl_en_mean, "kl_eval_sl_mean": float(np.mean(kl["sl"]))})
        logger.info(f"random {j} (seed {SEED + s}): heretic {ov_r} match {match:.4f} KL en {kl_en_mean:.4f} "
                    f"sl {np.mean(kl['sl']):.4f}")
        s += 1
    CHECKS["random_edits"] = rand_meta
    CHECKS["random_replacements"] = n_repl
    write_jsonl(OUT / "c5a_kl.jsonl", c5a_rows)
    tick("random_c5a", t)

    # ---- HF reference generations for the engine gate (both models; cheap) ----
    t = time.time()
    gate_h = read_jsonl(DATA / "gate_harmless40.jsonl")
    users, meta = [], []
    for d in DEV:
        for arm in ("en_bt", "sl_mt"):
            users.append(d[arm])
            meta.append({"item_id": d["item_id"], "arm": arm, "kind": "harmful"})
    for h in gate_h:
        users.append(h["en_orig"])
        meta.append({"item_id": h["item_id"], "arm": "en_orig", "kind": "harmless"})
    seqs = P.encode(tok, P.render(tok, users))
    rows = []
    for lam in (0.0, 1.0):
        model.reset_model()
        if lam:
            load_lora_state(model, st_sel, 1.0)
        tt = time.time()
        texts, _ = P.generate(model.model, tok, seqs, 128)
        dt = time.time() - tt
        lp = P.first_token_logprobs(model.model, seqs)
        top1 = lp.argmax(-1).tolist()
        for m_, tx, t1 in zip(meta, texts, top1):
            rows.append({**m_, "model": M, "lambda": lam, "response": tx, "first_top1": t1, "lex": lex.hit(tx)})
        CHECKS.setdefault("hf_gate_throughput_items_per_s", {})[str(lam)] = round(len(seqs) / dt, 3)
    write_jsonl(OUT / "engine_gate_hf.jsonl", rows)
    tick("engine_gate_hf", t)
    model.reset_model()
    CHECKS["done"] = True
    save()
    logger.info(f"PHASE A DONE {M} in {time.time() - T0:.0f}s")


if __name__ == "__main__":
    main()
