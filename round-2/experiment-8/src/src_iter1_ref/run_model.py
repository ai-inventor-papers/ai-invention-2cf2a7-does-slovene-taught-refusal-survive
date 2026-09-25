#!/usr/bin/env python3
# NOTE (published copy): this file names server paths this repository
# does not publish (a stage it does not ship, or another run's workspace),
# so the steps that read them will not run from a clone as written:
#   /ai-inventor/aii_data/runs/run_FVi3e3O9CH5I/iter_1/gen_hypo/claude_agent/work/heretic_config.default.toml
"""Per-model GPU block: LOAD -> checks -> Heretic directions -> PHASE O (original) -> PHASE H (Heretic study with
bilingual off-objective logging) -> PHASE P (selection, random edits, lambda curve) -> save.

Usage: .venv/bin/python src/run_model.py --model gemma_it --h-minutes 70 [--n-trials N] [--smoke]
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import random
import sys
import time
from dataclasses import asdict
from pathlib import Path

os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")
# no C compiler on this pod: transformers auto-compiles generate() for Gemma-3 hybrid caches -> disable dynamo
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402

from common import (MODELS, RESULTS, SEED, SPLITS, DATA, Lexicon, append_jsonl, read_jsonl,  # noqa: E402
                    setup_logger, write_jsonl)
import probe as P  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=list(MODELS))
ap.add_argument("--h-minutes", type=float, default=70.0)
ap.add_argument("--n-trials", type=int, default=0, help="force n (0 = time-box rule / amendment file)")
ap.add_argument("--smoke", action="store_true")
ap.add_argument("--deadline-epoch", type=float, default=0.0, help="hard stop for Phase H")
ap.add_argument("--probe-r", type=int, default=50, help="items per language for per-trial R generation")
ap.add_argument("--lambda-grid", type=str, default="0.2,0.4,0.6,0.8,1.2")
ap.add_argument("--prefill-ks", type=str, default="5,10,20")
ap.add_argument("--rank-pairs", type=int, default=100)
ap.add_argument("--save-baseline-lp", action="store_true",
                help="cache O2 first-token log-probs to disk as <90 MB float16 shards (400 prompts x 262k vocab ~ 400 MB "
                     "per model). OFF by default: nothing downstream reads it and it exceeds the 100 MB publish limit.")
ap.add_argument("--rank-variant", default="projected", choices=["projected", "raw", "none"])
ap.add_argument("--probe-new-tokens", type=int, default=40, help="per-trial probe generation length (amendment 2; plan: 64)")
ap.add_argument("--skip-replay", action="store_true", help="skip non-interference replay (already passed on this model+code; see logs)")
ap.add_argument("--probe-s-full", action="store_true", help="multi-token s per trial (default: s1 only, amendment 2)")
ap.add_argument("--no-mech-c", dest="mech_c", action="store_false", help="skip Mechanistic Question C at the end of Phase P")
ap.add_argument("--prefill-deep-n", type=int, default=100, help="refused items per lang for k=10/20 depth curve")
ARGS = ap.parse_args()

M = ARGS.model
OUT = RESULTS / M
OUT.mkdir(parents=True, exist_ok=True)
logger = setup_logger(f"run_{M}{'_smoke' if ARGS.smoke else ''}")
T0 = time.time()
TIMING = {}
AMEND = RESULTS / "protocol_amendments.json"
CHECKS = {}

import heretic.model as hm  # noqa: E402
from heretic.config import Settings  # noqa: E402
from heretic.evaluator import Evaluator  # noqa: E402
from heretic.model import AbliterationParameters, Model  # noqa: E402
from heretic.utils import Prompt, load_prompts  # noqa: E402
import optuna  # noqa: E402
from optuna.samplers import TPESampler  # noqa: E402
from optuna.storages import JournalStorage  # noqa: E402
from optuna.storages.journal import JournalFileBackend  # noqa: E402
from optuna.trial import Trial  # noqa: E402

optuna.logging.set_verbosity(optuna.logging.WARNING)


# ---------------- template patch: drop an EMPTY system turn (identically for both models) ----------------
def patched_generate(self, prompts, **kwargs):
    chats = [([{"role": "system", "content": p.system}] if p.system else []) + [{"role": "user", "content": p.user}]
             for p in prompts]
    chat_prompts = self.tokenizer.apply_chat_template(chats, add_generation_prompt=True, tokenize=False)
    if self.settings.response_prefix:
        chat_prompts = [c + self.settings.response_prefix for c in chat_prompts]
    inputs = self.tokenizer(chat_prompts, return_tensors="pt", padding=True, return_token_type_ids=False).to(
        self.model.device)
    outputs = self.model.generate(**inputs, **kwargs, pad_token_id=self.tokenizer.pad_token_id, do_sample=False)
    return inputs, outputs


ORIG_GENERATE = hm.Model.generate
hm.Model.generate = patched_generate


def tick(name: str, t: float):
    TIMING[name] = round(time.time() - t, 1)
    logger.info(f"[time] {name}: {TIMING[name]}s  (total {time.time() - T0:.0f}s)")
    (OUT / "timing.json").write_text(json.dumps(TIMING, indent=2))


def write_config_toml() -> Path:
    src = Path("/ai-inventor/aii_data/runs/run_FVi3e3O9CH5I/iter_1/gen_hypo/claude_agent/work/heretic_config.default.toml")
    txt = src.read_text()
    rep = {'quantization = "none"': 'quantization = "bnb_4bit"',
           'system_prompt = "You are a helpful assistant."': 'system_prompt = ""',
           "n_trials = 200": "n_trials = 80",
           "n_startup_trials = 60": "n_startup_trials = 25",
           'study_checkpoint_dir = "checkpoints"': f'study_checkpoint_dir = "{OUT}/heretic_ckpt"',
           "batch_size = 0  # auto": "batch_size = 128  # fixed (identical for both models; = Heretic max_batch_size; not auto-benchmarked)"}
    for a, b in rep.items():
        assert a in txt, a
        txt = txt.replace(a, b)
    txt = "seed = 20260923\n" + txt
    cfgdir = OUT / "cfg"
    cfgdir.mkdir(exist_ok=True)
    (cfgdir / "config.toml").write_text(txt)
    return cfgdir


def load_settings(cfgdir: Path) -> Settings:
    old_argv, old_cwd = sys.argv, os.getcwd()
    sys.argv = [old_argv[0]]
    os.chdir(cfgdir)
    try:
        kw = {"model": MODELS[M]["repo"]}
        if MODELS[M]["revision"]:
            kw["model_commit"] = MODELS[M]["revision"]
        s = Settings(**kw)
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


def langid_sl(text: str) -> tuple[str, int]:
    import langid
    langid.set_languages(["sl", "hr", "bs", "sr", "en"])
    lab, _ = langid.classify(text or " ")
    t = f" {text.lower()} "
    sl_markers = [" lahko ", " tudi ", " vendar ", " kot ", " ki ", " žal ", " zato ", " oziroma ", " ali ", " tega "]
    ok = int(lab == "sl" or (lab in ("hr", "bs", "sr") and sum(m in t for m in sl_markers) >= 2))
    return lab, ok


# =====================================================================================================
@logger.catch(reraise=True)
def main():
    torch.manual_seed(SEED)
    cfgdir = write_config_toml()
    settings = load_settings(cfgdir)
    logger.info(f"Settings: model={settings.model} commit={settings.model_commit} quant={settings.quantization} "
                f"seed={settings.seed} sys='{settings.system_prompt}' bs={settings.batch_size} "
                f"max_resp={settings.max_response_length}")
    lex = Lexicon(settings.model_extra["scorer"]["KeywordRate"]["keyword_markers"])

    # ---------------- LOAD ----------------
    t = time.time()
    model = Model(settings)
    tok = model.tokenizer
    tick("load", t)
    CHECKS["vram_after_load_GB"] = round(torch.cuda.memory_allocated() / 1e9, 2)
    CHECKS["n_layers"] = len(model.get_layers())
    CHECKS["components"] = model.get_abliterable_components()
    CHECKS["model_class"] = type(model.model.base_model.model).__name__
    CHECKS["resolved_snapshot"] = getattr(model.model.base_model.model.config, "_name_or_path", None)
    try:
        from huggingface_hub import HfApi
        CHECKS["hub_sha"] = HfApi().model_info(MODELS[M]["repo"], revision=MODELS[M]["revision"]).sha
    except Exception as e:  # noqa: BLE001
        CHECKS["hub_sha"] = f"unavailable: {e}"[:200]
    logger.info(f"loaded: {CHECKS}")

    # ---------------- DATA ----------------
    s400 = read_jsonl(SPLITS / "score400.jsonl")
    tp = read_jsonl(SPLITS / "trial_probe.jsonl")
    construct = read_jsonl(SPLITS / "construct.jsonl")
    sel_kl = read_jsonl(SPLITS / "sel_kl.jsonl")
    eval_kl = read_jsonl(SPLITS / "eval_kl.jsonl")
    spare = read_jsonl(SPLITS / "kl_spare.jsonl")
    if ARGS.smoke:
        s400, tp, sel_kl, eval_kl = s400[:16], tp[:8], sel_kl[:8], eval_kl[:8]

    rp = lambda users: P.render(tok, users, settings.response_prefix)  # noqa: E731

    # ---------------- TEMPLATE CHECK ----------------
    t = time.time()
    tchk = []
    for lang in ("en", "sl"):
        for p in s400[:2]:
            x = p[lang]
            heretic_str = model.tokenizer.apply_chat_template(
                [[{"role": "user", "content": x}]], add_generation_prompt=True, tokenize=False)[0]
            # what patched Heretic renders for Prompt(system='', user=x)
            chats = [([{"role": "system", "content": ""}] if "" else []) + [{"role": "user", "content": x}]]
            patched = model.tokenizer.apply_chat_template(chats, add_generation_prompt=True, tokenize=False)[0]
            unpatched = model.tokenizer.apply_chat_template([[{"role": "system", "content": ""}, {"role": "user", "content": x}]],
                                                            add_generation_prompt=True, tokenize=False)[0]
            ours = P.render(tok, [x])[0]
            assert patched == heretic_str == ours
            ids = tok(ours, return_token_type_ids=False)["input_ids"]
            tchk.append({"lang": lang, "rendered": ours, "unpatched_heretic_with_empty_system": unpatched,
                         "empty_system_changes_string": unpatched != ours, "first_ids": ids[:4],
                         "double_bos": len(ids) > 1 and ids[0] == ids[1] == tok.bos_token_id})
    CHECKS["template"] = tchk
    logger.info(f"template check OK; empty-system changes string: {tchk[0]['empty_system_changes_string']}; "
                f"double BOS: {tchk[0]['double_bos']}")

    # ---------------- LEFT-PAD CHECK (batched == unbatched, 16 prompts) ----------------
    ids16 = P.encode(tok, rp([p["en"] for p in s400[:4]] + [p["sl"] for p in s400[:4]]))
    bt, _ = P.generate(model.model, tok, ids16, 32)
    ut = []
    for s in ids16:
        o, _ = P.generate(model.model, tok, [s], 32)
        ut.append(o[0])
    same = sum(a == b for a, b in zip(bt, ut))
    same60 = sum(a.strip()[:60] == b.strip()[:60] for a, b in zip(bt, ut))
    # Heretic's own padded path (heretic.Model.get_responses) vs unbatched
    her = model.get_responses([Prompt(system="", user=u) for u in ([p["en"] for p in s400[:4]] + [p["sl"] for p in s400[:4]])],
                              skip_special_tokens=True)
    her_same = sum(a.strip()[:60] == b.strip()[:60] for a, b in zip(her, ut))
    CHECKS["leftpad"] = {"bucketed_vs_unbatched_identical": same, "heretic_padded_vs_unbatched_first60chars": her_same,
                         "bucketed_vs_unbatched_first60chars": same60, "n": len(ids16), "examples": [{"batched": a[:150], "unbatched": b[:150]} for a, b in zip(bt[:3], ut[:3])]}
    logger.info(f"left-pad check: bucketed==unbatched {same}/{len(ids16)} (60ch {same60}); heretic padded==unbatched(60ch) {her_same}/{len(ids16)}")
    for a in ut[:4]:
        logger.info(f"   sample: {a[:120]!r}")
    tick("checks", t)

    # ---------------- HERETIC: prompts, response prefix, evaluator, directions (verbatim logic) ----------------
    t = time.time()
    good_prompts = load_prompts(settings, settings.good_prompts)
    bad_prompts = load_prompts(settings, settings.bad_prompts)
    if settings.response_prefix is None:
        from os.path import commonprefix
        prefix_check_prompts = good_prompts[:100] + bad_prompts[:100]
        dummy = tok.apply_chat_template([{"role": "user", "content": "This is a dummy prompt."}], add_generation_prompt=True,
                                        tokenize=False)
        import re
        for cot_init, closed in settings.chain_of_thought_skips:
            if re.search(rf"{re.escape(cot_init)}\s*$", dummy):
                settings.response_prefix = closed
                break
        if settings.response_prefix is None:
            responses = model.get_responses_batched(prefix_check_prompts)
            settings.response_prefix = commonprefix(responses).rstrip(" ")
    CHECKS["response_prefix"] = settings.response_prefix
    logger.info(f"response prefix: {settings.response_prefix!r}")
    evaluator = Evaluator(settings, model)
    CHECKS["baseline_scores"] = {n: s.value for n, s in evaluator.baseline_scores}
    good_means = model.get_residuals_mean(good_prompts)
    bad_means = model.get_residuals_mean(bad_prompts)
    residual_directions = F.normalize(bad_means - good_means, p=2, dim=1)
    if settings.orthogonalize_direction:
        good_directions = F.normalize(good_means, p=2, dim=1)
        projection_vector = torch.sum(residual_directions * good_directions, dim=1)
        residual_directions = residual_directions - projection_vector.unsqueeze(1) * good_directions
        residual_directions = F.normalize(residual_directions, p=2, dim=1)
    torch.save(residual_directions, OUT / "residual_directions.pt")
    del good_means, bad_means
    tick("heretic_setup", t)
    logger.info(f"baseline heretic scores: {CHECKS['baseline_scores']}")

    # ---------------- probe sets ----------------
    enc = {}
    for lang in ("en", "sl"):
        enc[("s400", lang)] = P.encode(tok, rp([p[lang] for p in s400]))
        enc[("tp", lang)] = P.encode(tok, rp([p[lang] for p in tp]))
        enc[("sel", lang)] = P.encode(tok, rp([p[lang] for p in sel_kl]))
        enc[("eval", lang)] = P.encode(tok, rp([p[lang] for p in eval_kl]))
    tp_idx_in_s400 = {p["pair_id"]: i for i, p in enumerate(s400)}

    # ---------------- PHASE O ----------------
    def score_block(tag: str, items: list[dict], key: str, gen_n: int | None = None, max_new: int = 64,
                    extra: dict | None = None) -> list[dict]:
        rows = []
        for lang in ("en", "sl"):
            seqs = enc[(key, lang)]
            n = len(seqs) if gen_n is None else min(gen_n, len(seqs))
            texts, _ = P.generate(model.model, tok, seqs[:n], max_new)
            s, s1 = P.score_s(model.model, tok, seqs, lang)
            for i, p in enumerate(items):
                r = {"model": M, "cond": tag, "pair_id": p["pair_id"], "lang": lang, "category": p["category"],
                     "dose_group": p["dose_group"], "s": s[i], "s1": s1[i]}
                if i < n:
                    r.update({"R": lex.hit(texts[i], lang), "text": texts[i][:400]})
                    if lang == "sl":
                        r["langid"], r["sl_consistent"] = langid_sl(texts[i])
                if extra:
                    r.update(extra)
                rows.append(r)
        return rows

    t = time.time()
    o1 = read_jsonl(OUT / "orig_score400.jsonl")
    if len(o1) == 2 * len(s400) and not ARGS.smoke:
        logger.info("O1 RESUMED from orig_score400.jsonl (deterministic greedy; identical inputs)")
        CHECKS["O1_resumed"] = True
    else:
        o1 = score_block("orig", s400, "s400")
        write_jsonl(OUT / "orig_score400.jsonl", o1)
    for lang in ("en", "sl"):
        rr = [r["R"] for r in o1 if r["lang"] == lang]
        logger.info(f"O1 {lang}: R={np.mean(rr):.3f} n={len(rr)}")
    tick("O1_score400", t)

    t = time.time()
    base_lp = load_baseline_lp(OUT)
    if base_lp is None:
        base_lp = {}
        for key in ("sel", "eval"):
            for lang in ("en", "sl"):
                base_lp[(key, lang)] = P.first_token_logprobs(model.model, enc[(key, lang)])
        if ARGS.save_baseline_lp:
            save_baseline_lp(OUT, base_lp)
    else:
        logger.info("O2 baseline log-probs loaded from the on-disk shards")
    # sanity: unedited KL vs cached baseline == 0
    kl0 = P.kl_items(model.model, enc[("eval", "en")][:8], base_lp[("eval", "en")][:8])
    CHECKS["unedited_kl_vs_baseline_max"] = max(kl0)
    logger.info(f"O2 baseline lp cached; unedited KL max {max(kl0):.2e}")
    tick("O2_baseline_lp", t)

    # ---------------- O3 PREFILL (ALT-4) ----------------
    t = time.time()
    pre_rows = read_jsonl(OUT / "prefill.jsonl")
    ks = [int(k) for k in ARGS.prefill_ks.split(",") if k]
    if pre_rows and not ARGS.smoke and {r["k"] for r in pre_rows} == set(ks) and {r["lang"] for r in pre_rows} == {"en", "sl"}:
        logger.info(f"O3 RESUMED from prefill.jsonl ({len(pre_rows)} rows)")
        CHECKS["O3_resumed"] = True
        langs_todo = []
    else:
        pre_rows = []
        langs_todo = ["en", "sl"]
    for lang in langs_todo:
        refused = [i for i, r in enumerate([r for r in o1 if r["lang"] == lang]) if r.get("R") == 1]
        for k in ks:
            pid = P.prefill_ids(tok, lang, k)
            use = refused if k == 5 else refused[:ARGS.prefill_deep_n]
            seqs = [enc[("s400", lang)][i] + pid for i in use]
            texts, _ = P.generate(model.model, tok, seqs, 48)
            for i, txt in zip(use, texts):
                pre_rows.append({"model": M, "pair_id": s400[i]["pair_id"], "lang": lang, "k": k,
                                 "category": s400[i]["category"], "prefill": tok.decode(pid),
                                 "R_cont": lex.hit(txt, lang), "flip": 1 - lex.hit(txt, lang), "text": txt[:300]})
            fr = np.mean([r["flip"] for r in pre_rows if r["lang"] == lang and r["k"] == k]) if refused else float("nan")
            logger.info(f"O3 prefill {lang} k={k}: n_refused={len(refused)} flip={fr:.3f}")
    write_jsonl(OUT / "prefill.jsonl", pre_rows)
    tick("O3_prefill", t)

    # ---------------- O4 RANK-k ABLATION (ALT-4) ----------------
    t = time.time()
    rank_out = (run_rank_k(model, tok, settings, lex, s400, o1, construct, spare, rp, variant=ARGS.rank_variant)
                if ARGS.rank_variant != "none" else {"skipped": "amendment 2 (time)"})
    tick("O4_rank_k", t)

    # ---------------- PHASE H ----------------
    t = time.time()
    H = run_heretic_study(model, tok, settings, evaluator, residual_directions, lex, tp, enc, base_lp, sel_kl, eval_kl)
    tick("H_study", t)

    # ---------------- PHASE P ----------------
    t = time.time()
    run_phase_p(model, tok, settings, evaluator, residual_directions, lex, s400, tp, enc, base_lp, sel_kl, eval_kl,
                H, score_block)
    tick("P_posthoc", t)

    if ARGS.mech_c:
        t = time.time()
        run_mech_c(model, settings, construct)
        tick("mech_c", t)
    CHECKS["timing"] = TIMING
    CHECKS["rank_k_summary"] = rank_out
    (OUT / "checks.json").write_text(json.dumps(CHECKS, indent=2, ensure_ascii=False, default=str))
    logger.info(f"DONE {M} in {time.time() - T0:.0f}s")


# =====================================================================================================
def run_rank_k(model, tok, settings, lex, s400, o1, construct, spare, rp, variant: str = "projected") -> dict:
    """Rank-1 vs rank-5 PCA ablation share (ALT-4 supporting), activation hooks outside Heretic.
    variant raw: Arditi-style mean difference (plan as written). On Gemma-3 this DESTROYS the model (KL 20-53 nats at
    every candidate layer; attempt kept in results/gemma_it/rank_k_raw*), because the raw harm-harmless mean difference
    carries the harmless-mean (massive-activation) component; even the RANDOM 5-dim basis R5 destroyed it. variant
    projected (default, amendment): the scan directions, the PCA basis AND the random basis are orthogonalised against the
    span of the per-layer harmless-mean directions (generalising Heretic's orthogonalize_direction=true)."""
    sfx = "" if variant == "projected" else "_raw"
    if ARGS.smoke:
        return {"skipped": "smoke"}
    rng = random.Random(SEED)
    cons = sorted(construct, key=lambda p: p["sha1"])
    harm_en = [p["en"] for p in cons[:300]]
    harm_sl = [p["sl"] for p in cons[:300]]
    harmless_en = [r["en"] for r in read_jsonl(DATA / "harmless_sl_mt.jsonl")] or None
    alp = __import__("datasets").load_dataset("mlabonne/harmless_alpaca", split="train[400:600]")["text"]
    harmless_en = list(alp)
    mt = read_jsonl(DATA / "harmless_sl_mt.jsonl")
    if len(mt) >= 150:
        harmless_sl, harmless_sl_src = [r["sl"] for r in mt], "gemini-2.5-flash MT of harmless_alpaca train[400:600]"
        kl_spare = spare[:50]
    else:
        harmless_sl, harmless_sl_src = [p["sl"] for p in spare[:200]], "SUBSTITUTE: slovenian-llm-eval ARC/HellaSwag stems (KL-SPARE[:200]); MT unavailable (OpenRouter 403)"
        kl_spare = spare[200:250]
    res = {"harmless_sl_source": harmless_sl_src}
    t = time.time()
    to_p = lambda xs: [Prompt(system="", user=x) for x in xs]  # noqa: E731
    bs0 = settings.batch_size
    settings.batch_size = 8  # all-layer hidden states of long RefusEU prompts OOM at 128 on the 16 GB card
    R_harm = torch.cat([model.get_residuals_batched(to_p(harm_en)), model.get_residuals_batched(to_p(harm_sl))])
    R_less = torch.cat([model.get_residuals_batched(to_p(harmless_en)), model.get_residuals_batched(to_p(harmless_sl))])
    settings.batch_size = bs0
    logger.info(f"rank-k residuals: harm {tuple(R_harm.shape)} harmless {tuple(R_less.shape)} ({time.time() - t:.0f}s)")
    L = R_harm.shape[1] - 1
    cands = list(range(int(round(0.4 * L)), int(round(0.8 * L)) + 1, 2))
    # projected variant: orthonormal basis Q of the per-layer harmless-mean directions (all L+1 residual positions);
    # these carry Gemma-3's massive-activation dims, whose smearing destroyed even a RANDOM 5-dim ablation (raw run).
    Qm, _ = torch.linalg.qr(F.normalize(R_less.mean(0), dim=1).T.double())  # [d, L+1]

    def perp(v: torch.Tensor) -> torch.Tensor:
        v = v.double()
        return (v - Qm @ (Qm.T @ v)).float()
    layers = model.get_layers()
    embed = model.model.get_input_embeddings()
    lsel_items = cons[:32]
    lsel_seqs = {lang: P.encode(tok, rp([p[lang] for p in lsel_items])) for lang in ("en", "sl")}
    kl_seqs = P.encode(tok, rp([p["sl"] if i % 2 else p["en"] for i, p in enumerate(kl_spare)]))
    kl_base = P.first_token_logprobs(model.model, kl_seqs)
    s_base = {lang: float(np.mean(P.score_s(model.model, tok, lsel_seqs[lang], lang)[0])) for lang in ("en", "sl")}
    layer_scan = []
    for l in cands:
        d = F.normalize(R_harm[:, l].mean(0) - R_less[:, l].mean(0), dim=0)
        if variant == "projected":
            d = F.normalize(perp(d), dim=0)
        with P.ablation_hooks(embed, layers, d[:, None]):
            ss = [np.mean(P.score_s(model.model, tok, lsel_seqs[lang], lang)[0]) for lang in ("en", "sl")]
            kl = float(np.mean(P.kl_items(model.model, kl_seqs, kl_base)))
        layer_scan.append({"layer": l, "mean_s": float(np.mean(ss)), "s_en": float(ss[0]), "s_sl": float(ss[1]), "kl": kl})
        logger.info(f"  layer {l}: s_en={ss[0]:.2f} s_sl={ss[1]:.2f} kl={kl:.3f}")
    ok = [x for x in layer_scan if x["kl"] < 0.5]
    res["kl_filter_met"] = bool(ok)
    if ok:
        lstar = min(ok, key=lambda x: x["mean_s"])["layer"]
    else:  # flagged fallback: no layer keeps KL < 0.5 -> least-damaging layer
        lstar = min(layer_scan, key=lambda x: x["kl"])["layer"]
    X = (R_harm[:, lstar] - R_less[:, lstar].mean(0)).double()
    if variant == "projected":
        X = perp(X.T).T.double()
    _, Sv, Vh = torch.linalg.svd(X, full_matrices=False)
    U1, U5 = Vh[:1].T.float(), Vh[:5].T.float()
    res["variant"] = variant
    g = torch.Generator().manual_seed(SEED)
    R5raw = torch.randn(X.shape[1], 5, generator=g)
    R5, _ = torch.linalg.qr(perp(R5raw) if variant == "projected" else R5raw)
    cos_pc1_mean = float(F.cosine_similarity(Vh[0].float(), (R_harm[:, lstar].mean(0) - R_less[:, lstar].mean(0)), dim=0))
    res.update({"layer_scan": layer_scan, "l_star": lstar, "s_base_construct": s_base,
                "sv_top10": [float(x) for x in Sv[:10]], "cos_pc1_meandiff": cos_pc1_mean})
    sub = sorted(s400, key=lambda p: p["sha1"])[:ARGS.rank_pairs]
    rows = []
    for cond, U in (("U1", U1), ("U5", U5), ("R5", R5)):
        with P.ablation_hooks(embed, layers, U):
            for lang in ("en", "sl"):
                seqs = P.encode(tok, rp([p[lang] for p in sub]))
                texts, _ = P.generate(model.model, tok, seqs, 64)
                s, _ = P.score_s(model.model, tok, seqs, lang)
                for p, tx, sv in zip(sub, texts, s):
                    rows.append({"model": M, "cond": cond, "variant": variant, "pair_id": p["pair_id"], "lang": lang,
                                 "R": lex.hit(tx, lang), "s": sv, "text": tx[:300]})
                logger.info(f"  rank {cond} {lang}: R={np.mean([r['R'] for r in rows if r['cond'] == cond and r['lang'] == lang]):.3f}")
    write_jsonl(OUT / f"rank_k{sfx}.jsonl", rows)
    (OUT / f"rank_k_meta{sfx}.json").write_text(json.dumps(res, indent=2))
    torch.save({"U1": U1, "U5": U5, "R5": R5, "l_star": lstar}, OUT / f"rank_k_bases{sfx}.pt")
    del R_harm, R_less, X
    gc.collect()
    return {"l_star": lstar, "harmless_sl_source": harmless_sl_src}


# =====================================================================================================
def bilingual_probe(model, tok, lex, tp, enc, base_lp, sel_kl, eval_kl, trial_no: int, tag: str,
                    n_r: int) -> dict:
    """Off-objective bilingual logging. Reads the model; never writes to it."""
    rows, klrows = [], []
    summ = {}
    # one generate call for both languages (length-sorted batches); split back afterwards
    both = enc[("tp", "en")][:n_r] + enc[("tp", "sl")][:n_r]
    texts_all, _ = P.generate(model.model, tok, both, ARGS.probe_new_tokens) if n_r > 0 else ([], None)
    gen_texts = {"en": texts_all[:n_r], "sl": texts_all[n_r:]}
    for lang in ("en", "sl"):
        seqs = enc[("tp", lang)]
        texts = gen_texts[lang]
        if ARGS.probe_s_full:
            s, s1 = P.score_s(model.model, tok, seqs, lang)
        else:  # s1 only: first-token readout from one prompt forward (amendment 2)
            s1 = P.score_s1(model.model, tok, seqs, lang)
            s = [None] * len(seqs)
        for i, p in enumerate(tp):
            r = {"trial": trial_no, "tag": tag, "pair_id": p["pair_id"], "lang": lang, "dose_group": p["dose_group"],
                 "category": p["category"], "s": s[i], "s1": s1[i]}
            if i < n_r:
                r["R"] = lex.hit(texts[i], lang)
                r["text"] = texts[i][:400]
            rows.append(r)
        if n_r > 0:
            summ[f"R_{lang}"] = float(np.mean([r["R"] for r in rows if r["lang"] == lang and "R" in r]))
        summ[f"s1_{lang}"] = float(np.mean(s1))
        for key, items in (("sel", sel_kl), ("eval", eval_kl)):
            kls = P.kl_items(model.model, enc[(key, lang)], base_lp[(key, lang)])
            for p, k in zip(items, kls):
                klrows.append({"trial": trial_no, "tag": tag, "set": key, "lang": lang, "pair_id": p["pair_id"], "kl": k})
            summ[f"KL_{key}_{lang}"] = float(np.mean(kls))
    return {"rows": rows, "klrows": klrows, "summary": summ}


# ---------------- O2 baseline log-prob cache (sharded; nothing downstream reads it, so saving is opt-in) ----------
SHARD_MAX_BYTES = 90 * 1024 ** 2  # keep every published file under the 100 MB GitHub limit


def save_baseline_lp(out_dir, base_lp: dict, max_bytes: int = SHARD_MAX_BYTES) -> list:
    """Write {(set, lang): [N, V] tensor} as float16 shards of at most max_bytes each."""
    shard, shard_bytes, paths = {}, 0, []

    def flush():
        nonlocal shard, shard_bytes
        if shard:
            q = out_dir / f"baseline_lp_part_{len(paths) + 1:03d}.pt"
            torch.save(shard, q)
            paths.append(q)
            shard, shard_bytes = {}, 0

    for (key, lang), v in base_lp.items():
        v = v.half()
        rows = max(1, int(max_bytes // max(1, v[0].numel() * 2)))
        for i in range(0, len(v), rows):
            # .clone() is required: torch.save on a slice would serialise the WHOLE underlying storage
            chunk = v[i:i + rows].clone()
            nbytes = chunk.numel() * 2
            if shard_bytes + nbytes > max_bytes:
                flush()
            shard[f"{key}_{lang}_{i}"] = chunk
            shard_bytes += nbytes
    flush()
    return paths


def load_baseline_lp(out_dir):
    """Reassemble the shards written by save_baseline_lp; None when no cache is present."""
    parts = sorted(out_dir.glob("baseline_lp_part_*.pt"))
    if not parts:
        return None
    chunks = {}
    for q in parts:
        for name, v in torch.load(q).items():
            key, lang, off = name.rsplit("_", 2)
            chunks.setdefault((key, lang), []).append((int(off), v))
    return {k: torch.cat([v for _, v in sorted(c)]).float() for k, c in chunks.items()}


def _replay(model, evaluator, residual_directions, last, fixed, n_r, ctx_probe, probe_path, kl_path, t):
    """NON-INTERFERENCE (b): replay a fixed parameter set with and without the probe."""
    model.reset_model()
    model.abliterate(residual_directions, 0.65 * last, fixed)
    obj1 = evaluator.get_objective_values(evaluator.get_scores())
    h1 = lora_hash(model)
    pr = bilingual_probe(model, trial_no=-1, tag="replay", n_r=n_r, **ctx_probe)
    h2 = lora_hash(model)
    model.reset_model()
    model.abliterate(residual_directions, 0.65 * last, fixed)
    obj2 = evaluator.get_objective_values(evaluator.get_scores())
    CHECKS["noninterference"] = {"obj_with_probe_first": list(obj1), "obj_replay": list(obj2), "identical": list(obj1) == list(obj2),
                                 "lora_hash_unchanged_by_probe": h1 == h2, "replay_probe_summary": pr["summary"],
                                 "seconds": round(time.time() - t, 1)}
    logger.info(f"non-interference: {CHECKS['noninterference']}")
    append_jsonl(probe_path, pr["rows"])
    append_jsonl(kl_path, pr["klrows"])


def run_heretic_study(model, tok, settings, evaluator, residual_directions, lex, tp, enc, base_lp, sel_kl, eval_kl):
    journal = OUT / ("heretic_study_smoke.journal" if ARGS.smoke else "heretic_study.journal")
    if ARGS.smoke and journal.exists():
        journal.unlink()
    probe_path = OUT / ("trial_probe_smoke.jsonl" if ARGS.smoke else "trial_probe.jsonl")
    kl_path = OUT / ("trial_kl_smoke.jsonl" if ARGS.smoke else "trial_kl.jsonl")
    n_r = ARGS.probe_r
    state = {"trial_index": 0, "start_index": 0, "start_time": time.perf_counter(), "t_trials": []}
    ctx_probe = dict(tok=tok, lex=lex, tp=tp, enc=enc, base_lp=base_lp, sel_kl=sel_kl, eval_kl=eval_kl)

    # ---- NON-INTERFERENCE (b): replay a fixed parameter set with and without the probe ----
    last = len(model.get_layers()) - 1
    fixed = {c: AbliterationParameters(max_weight=1.0, max_weight_position=0.8 * last, min_weight=0.5,
                                       min_weight_distance=0.3 * last) for c in model.get_abliterable_components()}
    t = time.time()
    if ARGS.skip_replay:
        CHECKS["noninterference"] = "skipped in this process; passed in earlier attempts on the same model and code (logs/run_gemma_it_attempt*.log: identical objective values, LoRA hash unchanged)"
    else:
        _replay(model, evaluator, residual_directions, last, fixed, n_r, ctx_probe, probe_path, kl_path, t)

    # ---------------- verbatim Heretic objective (main.py @3521f864) + ADDED probe lines ----------------
    def objective(trial: Trial) -> tuple[float, ...]:
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
        # ---- ADDED (does not touch objective_values) ----
        hb = lora_hash(model)
        pr = bilingual_probe(model, trial_no=trial_index, tag="trial", n_r=n_r, **ctx_probe)
        assert lora_hash(model) == hb, "probe modified LoRA weights"
        append_jsonl(probe_path, pr["rows"])
        append_jsonl(kl_path, pr["klrows"])
        trial.set_user_attr("bilingual", pr["summary"])
        trial.set_user_attr("t_objective_s", round(t_obj, 1))
        trial.set_user_attr("t_total_s", round(time.perf_counter() - t_start, 1))
        state["t_trials"].append(time.perf_counter() - t_start)
        logger.info(f"trial {trial_index}: obj={tuple(round(v, 4) for v in objective_values)} "
                    f"probe={ {k: round(v, 3) for k, v in pr['summary'].items()} } t={time.perf_counter() - t_start:.0f}s "
                    f"(obj {t_obj:.0f}s)")
        # ---- END ADDED ----
        return objective_values

    storage = JournalStorage(JournalFileBackend(str(journal)))
    study = optuna.create_study(
        sampler=TPESampler(n_startup_trials=settings.n_startup_trials, n_ei_candidates=128, multivariate=True,
                           seed=settings.seed),
        storage=storage, directions=evaluator.get_objective_directions(), study_name="heretic", load_if_exists=True)
    study.set_user_attr("settings", settings.model_dump_json())
    state["start_index"] = state["trial_index"] = len(study.trials)

    deadline = ARGS.deadline_epoch or (time.time() + ARGS.h_minutes * 60)

    def stop_cb(st, tr):
        if time.time() > deadline or (RESULTS / f"STOP_H_{M}").exists():
            logger.warning("Phase H deadline reached -> stopping study")
            st.stop()

    if ARGS.smoke:
        study.optimize(objective, n_trials=2)
    else:
        # time-box: measure 3 trials, then fix n (equal across models via the amendment file)
        n_meas = max(0, 3 - len(study.trials))
        if n_meas:
            study.optimize(objective, n_trials=n_meas, callbacks=[stop_cb])
        amend = json.loads(AMEND.read_text()) if AMEND.exists() else {}
        t_trial = float(np.mean(state["t_trials"])) if state["t_trials"] else 120.0
        if ARGS.n_trials:
            n = ARGS.n_trials
            rule = "forced by CLI"
        elif "n_trials" in amend:
            n = amend["n_trials"]
            rule = "from amendment (set on first model)"
        else:
            n = min(80, int(math.floor(ARGS.h_minutes * 60 / (t_trial * 1.10))))
            n = max(n, 40)
            amend.update({"n_trials": n, "n_startup_trials": 25, "t_trial_s_measured_on": M, "t_trial_s": round(t_trial, 1),
                          "h_minutes_budget": ARGS.h_minutes, "probe_r_items_per_lang": ARGS.probe_r,
                          "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                          "note": "time-box amendment made BEFORE any SCORE statistic was computed; n = min(80, floor(budget/(1.1 t_trial))), floor 40, equal for both models"})
            AMEND.write_text(json.dumps(amend, indent=2))
            rule = "time-box"
        logger.info(f"n_trials = {n} ({rule}); measured t_trial={t_trial:.0f}s")
        CHECKS["n_trials_target"] = n
        remaining = n - len(study.trials)
        if remaining > 0:
            study.optimize(objective, n_trials=remaining, callbacks=[stop_cb])

    trials = []
    for tr in study.trials:
        if tr.values is None:
            continue
        trials.append({"number": tr.number, "values": list(tr.values), "params": tr.params,
                       "user_attrs": tr.user_attrs, "state": str(tr.state)})
    (OUT / ("trials_smoke.json" if ARGS.smoke else "trials.json")).write_text(json.dumps(trials, indent=1, default=str))
    CHECKS["n_trials_completed"] = len(trials)
    logger.info(f"Phase H: {len(trials)} trials completed")
    return {"trials": trials}


# =====================================================================================================
def run_phase_p(model, tok, settings, evaluator, residual_directions, lex, s400, tp, enc, base_lp, sel_kl, eval_kl,
                H, score_block):
    trials = H["trials"]
    if not trials:
        logger.error("no trials; skipping Phase P")
        return
    # objective order: [Refusals (fraction), KL]
    names = evaluator.get_objective_names()
    ir = [i for i, n in enumerate(names) if "Refusal" in n][0]
    ik = [i for i, n in enumerate(names) if "KL" in n][0]
    ok = [t for t in trials if t["values"][ir] <= 0.10 + 1e-9]
    if ok:
        pick = min(ok, key=lambda t: t["values"][ik])
        flag = None
    else:
        pick = min(trials, key=lambda t: (t["values"][ir], t["values"][ik]))
        flag = "selection_rule_fallback"
    sel = {"pick_trial_index": pick["user_attrs"]["index"], "pick_number": pick["number"], "refusals": pick["values"][ir],
           "kl": pick["values"][ik], "flag": flag, "direction_index": pick["user_attrs"]["direction_index"],
           "parameters": pick["user_attrs"]["parameters"],
           "rule": "argmin EN_KL among trials with keyword_refusals <= 10/100; else min refusals then min KL (flagged)"}
    (OUT / "selection_pick.json").write_text(json.dumps(sel, indent=2))
    logger.info(f"P1 pick: trial {sel['pick_trial_index']} refusals={sel['refusals']} kl={sel['kl']:.4f} flag={flag}")
    params = {k: AbliterationParameters(**v) for k, v in pick["user_attrs"]["parameters"].items()}
    didx = pick["user_attrs"]["direction_index"]
    kl_scorer = [e.scorer for e in evaluator._scorer_entries if type(e.scorer).__name__ == "KLDivergence"][0]
    from heretic.scorer import Context

    def heretic_kl() -> float:
        return float(kl_scorer.get_score(Context(settings=settings, model=model)).value)

    # ---- P2 selected edit on SCORE-400 ----
    t = time.time()
    model.reset_model()
    model.abliterate(residual_directions, didx, params)
    try:
        model.model.save_pretrained(str(OUT / "selected_adapter"))
    except Exception as e:  # noqa: BLE001
        logger.error(f"adapter save failed: {e}")
    rows = score_block("selected", s400, "s400")
    for lang in ("en", "sl"):
        kls = P.kl_items(model.model, enc[("eval", lang)], base_lp[("eval", lang)])
        rows += [{"model": M, "cond": "selected", "set": "eval", "lang": lang, "pair_id": p["pair_id"], "kl": k, "kind": "kl"}
                 for p, k in zip(eval_kl, kls)]
    write_jsonl(OUT / "selected_score400.jsonl", rows)
    for lang in ("en", "sl"):
        rr = [r["R"] for r in rows if r.get("lang") == lang and "R" in r]
        logger.info(f"P2 selected {lang}: R={np.mean(rr):.3f}")
    logger.info(f"[time] P2 {time.time() - t:.0f}s")
    pick_kl_heretic = heretic_kl()

    # ---- P3 random edits (norm-matched: identical parameters, only the direction differs) ----
    t = time.time()
    rand_rows, rand_meta = [], []
    probe_path = OUT / "posthoc_probe.jsonl"
    kl_path = OUT / "posthoc_kl.jsonl"
    ctx_probe = dict(tok=tok, lex=lex, tp=tp, enc=enc, base_lp=base_lp, sel_kl=sel_kl, eval_kl=eval_kl)
    per_layer = didx is None
    L1, d = residual_directions.shape

    def rand_dirs(j: int) -> torch.Tensor:
        g = torch.Generator().manual_seed(SEED + j)
        return F.normalize(torch.randn(L1, d, generator=g), p=2, dim=1)

    n_rand = 5 if not ARGS.smoke else 1
    for j in range(1, n_rand + 1):
        model.reset_model()
        model.abliterate(rand_dirs(j), didx, params)
        if j == 1:  # Heretic keyword refusals only for j=1 (sanity: random edit keeps EN refusal); KL for all (amendment 2)
            ov = evaluator.get_objective_values(evaluator.get_scores())
        else:
            ov = [float("nan"), float("nan")]
            ov[ik] = heretic_kl()
        pr = bilingual_probe(model, trial_no=1000 + j, tag=f"rand_nm_{j}", n_r=0, **ctx_probe)  # KL + s1 only (amendment 2)
        append_jsonl(probe_path, pr["rows"])
        append_jsonl(kl_path, pr["klrows"])
        rand_meta.append({"j": j, "variant": "norm_matched", "c": 1.0, "heretic_refusals": ov[ir], "heretic_kl": ov[ik],
                          **pr["summary"]})
        logger.info(f"P3 rand_nm {j}: {rand_meta[-1]}")
    logger.info(f"[time] P3a {time.time() - t:.0f}s")

    # ---- EN-KL-matched random: bisect scale c on direction j=1 (log-space, c in [0.1, 6]) ----
    t = time.time()

    def scaled(c: float) -> dict:
        return {k: AbliterationParameters(max_weight=v.max_weight * c, max_weight_position=v.max_weight_position,
                                          min_weight=v.min_weight * c, min_weight_distance=v.min_weight_distance)
                for k, v in params.items()}

    def kl_at(c: float, j: int = 1) -> float:
        model.reset_model()
        model.abliterate(rand_dirs(j), didx, scaled(c))
        return heretic_kl()

    target = pick_kl_heretic
    lo, hi = 0.1, 6.0
    k1 = rand_meta[0]["heretic_kl"]
    bis = [{"c": 1.0, "kl": k1}]
    c_star, status = 1.0, "matched"
    if abs(k1 - target) / max(target, 1e-9) > 0.10:
        khi = kl_at(hi)
        bis.append({"c": hi, "kl": khi})
        if khi < target * 0.9:
            c_star, status = hi, "unmatchable (c=6 still short)"
        else:
            if k1 > target:
                lo, hi = 0.1, 1.0
            else:
                lo, hi = 1.0, 6.0
            for _ in range(8):
                mid = math.exp((math.log(lo) + math.log(hi)) / 2)
                km = kl_at(mid)
                bis.append({"c": mid, "kl": km})
                if abs(km - target) / max(target, 1e-9) <= 0.10:
                    c_star = mid
                    break
                if km < target:
                    lo = mid
                else:
                    hi = mid
                c_star = mid
            else:
                status = "approx (8 bisection steps)"
    logger.info(f"KL-matched c*={c_star:.3f} status={status} target={target:.4f} steps={bis}")
    for j in range(1, n_rand + 1):
        model.reset_model()
        model.abliterate(rand_dirs(j), didx, scaled(c_star))
        hk = heretic_kl()
        summ = {}
        for key, items in (("sel", sel_kl), ("eval", eval_kl)):
            for lang in ("en", "sl"):
                kls = P.kl_items(model.model, enc[(key, lang)], base_lp[(key, lang)])
                append_jsonl(kl_path, [{"trial": 2000 + j, "tag": f"rand_klm_{j}", "set": key, "lang": lang,
                                        "pair_id": p["pair_id"], "kl": k} for p, k in zip(items, kls)])
                summ[f"KL_{key}_{lang}"] = float(np.mean(kls))
        rand_meta.append({"j": j, "variant": "en_kl_matched", "c": c_star, "status": status, "heretic_kl": hk, **summ})
        logger.info(f"P3 rand_klm {j}: {rand_meta[-1]}")
    (OUT / "random_edits.json").write_text(json.dumps({"pick_heretic_kl": pick_kl_heretic, "bisection": bis,
                                                       "c_star": c_star, "status": status, "edits": rand_meta,
                                                       "per_layer_scope": per_layer}, indent=2))
    logger.info(f"[time] P3b {time.time() - t:.0f}s")

    # ---- P4 lambda curve ----
    t = time.time()
    lam_meta = []
    for lam in [float(x) for x in ARGS.lambda_grid.split(",") if x]:
        model.reset_model()
        model.abliterate(residual_directions, didx, scaled(lam))
        sc = evaluator.get_scores()
        ov = evaluator.get_objective_values(sc)
        pr = bilingual_probe(model, trial_no=int(3000 + round(lam * 100)), tag=f"lambda_{lam}", n_r=ARGS.probe_r, **ctx_probe)
        append_jsonl(probe_path, pr["rows"])
        append_jsonl(kl_path, pr["klrows"])
        lam_meta.append({"lambda": lam, "heretic_refusals": ov[ir], "heretic_kl": ov[ik], **pr["summary"]})
        logger.info(f"P4 lambda {lam}: {lam_meta[-1]}")
    (OUT / "lambda_curve.json").write_text(json.dumps(lam_meta, indent=2))
    logger.info(f"[time] P4 {time.time() - t:.0f}s")
    model.reset_model()


# =====================================================================================================
def run_mech_c(model, settings, construct, n: int = 150):
    """EXTENSION (plan doc Mechanistic Question C): is harmfulness still linearly represented after the selected
    Heretic edit removes refusal? Held-out prompts never used by Heretic: RefusEU CONSTRUCT harmful (EN/SL, sha1-first n)
    vs harmless_alpaca train[400:600] EN + gemini-2.5-flash SL translation (n each). Last-token residuals every 4th layer,
    ORIGINAL vs SELECTED edit: AUROC of the projection on the ORIGINAL Heretic direction (fixed probe), 5-fold CV
    accuracy of a refit logistic probe, and transfer accuracy of the ORIGINAL-trained probe to EDITED residuals."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.model_selection import cross_val_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    pick = json.loads((OUT / "selection_pick.json").read_text())
    dirs = torch.load(OUT / "residual_directions.pt")
    cons = sorted(construct, key=lambda p: p["sha1"])[:n]
    mt = read_jsonl(DATA / "harmless_sl_mt.jsonl")[:n]
    prompts = {("harm", "en"): [p["en"] for p in cons], ("harm", "sl"): [p["sl"] for p in cons],
               ("less", "en"): [r["en"] for r in mt], ("less", "sl"): [r["sl"] for r in mt]}
    bs0 = settings.batch_size
    settings.batch_size = 8
    res = {}
    for cond in ("orig", "selected"):
        model.reset_model()
        if cond == "selected":
            params = {k: AbliterationParameters(**v) for k, v in pick["parameters"].items()}
            model.abliterate(dirs, pick["direction_index"], params)
        for key, xs in prompts.items():
            res[(cond,) + key] = model.get_residuals_batched([Prompt(system="", user=x) for x in xs])
    settings.batch_size = bs0
    model.reset_model()
    L1 = res[("orig", "harm", "en")].shape[1]
    layers = list(range(4, L1, 4))
    rows = []
    for lang in ("en", "sl"):
        y = np.array([1] * len(cons) + [0] * len(mt))
        for l in layers:
            d = F.normalize(dirs[l], dim=0)
            ent = {"lang": lang, "layer": l}
            X = {}
            for cond in ("orig", "selected"):
                Xc = torch.cat([res[(cond, "harm", lang)][:, l], res[(cond, "less", lang)][:, l]]).float()
                X[cond] = Xc.numpy()
                proj = (Xc @ d).numpy()
                ent[f"auroc_fixed_dir_{cond}"] = float(roc_auc_score(y, proj))
                ent[f"mean_proj_harm_{cond}"] = float(proj[y == 1].mean())
                ent[f"mean_proj_less_{cond}"] = float(proj[y == 0].mean())
                clf = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=2000))
                ent[f"probe_cv_acc_{cond}"] = float(cross_val_score(clf, X[cond], y, cv=5).mean())
            clf = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=2000)).fit(X["orig"], y)
            ent["probe_transfer_orig_to_selected_acc"] = float(clf.score(X["selected"], y))
            rows.append(ent)
            logger.info(f"mech_c {lang} L{l}: " + str({k: round(v, 3) if isinstance(v, float) else v for k, v in ent.items()}))
    (OUT / "mech_c.json").write_text(json.dumps({"model": M, "n_per_side": len(cons), "layers": layers,
                                                 "pick_trial": pick["pick_trial_index"], "rows": rows}, indent=1))


if __name__ == "__main__":
    main()
