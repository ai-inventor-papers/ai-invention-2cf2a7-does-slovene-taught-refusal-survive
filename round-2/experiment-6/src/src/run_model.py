#!/usr/bin/env python3
"""Per-model GPU pass (section 4): smoke -> DEV generation -> directions (DEV + harmless only) -> protocol freeze /
addendum -> FINAL generation (tiers A->B->C->D, timing gate + cut order) -> causal restoration -> harmless collateral.

All generations: NF4, greedy, official chat template (user turn only = empty system turn), left-padded length-bucketed
batches, 160 new tokens (96 for causal/collateral). Every row is appended to JSONL keyed item|model|arm|cond (resumable).
The OpenRouter judge is NOT called here (judge.py runs separately and reads these files).

Usage: python run_model.py --model gemma_it [--stages smoke,dev,dirs,final,causal,collateral] [--limit N]
"""
from __future__ import annotations

import argparse
import gc
import json
import math
import time
from pathlib import Path

import numpy as np
import torch

from common import (ALPHAS, CAP_LAYERS, CONDITIONS, DATA, FINAL_ORDER, HIDDEN, LSTAR_RANGE, MASSIVE_FACTOR, MAX_NEW, MAX_NEW_CAUSAL,
                    MIN_P_TOKENS, MODELS, N_BASE, N_EXT, P_BASE, P_EXT, P_EXT2, RESULTS, SEED, T2, T3, Lexicon,
                    append_jsonl, read_jsonl, repetitive, row_key, setup_logger, sha1_int)

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, choices=list(MODELS))
ap.add_argument("--stages", default="smoke,dev,dirs,final,causal,collateral")
ap.add_argument("--limit", type=int, default=0, help="limit FINAL items per condition (staged scale-up)")
ap.add_argument("--max-bs", type=int, default=64)
ap.add_argument("--budget-tokens", type=int, default=64 * 360)
ap.add_argument("--final-budget-min", type=float, default=75.0, help="projected FINAL GPU minutes before cuts apply")
ap.add_argument("--n-causal", type=int, default=100)
ap.add_argument("--tiers", default="A,B,C,D")
ARGS = ap.parse_args()
M = ARGS.model
OUT = RESULTS / M
OUT.mkdir(parents=True, exist_ok=True)
logger = setup_logger(f"run_{M}")
torch.manual_seed(SEED)
np.random.seed(SEED)
LEX = Lexicon()
TIMING: dict = {}
CHECKS: dict = {}

try:
    from lingua import Language, LanguageDetectorBuilder
    _DET = LanguageDetectorBuilder.from_languages(Language.ENGLISH, Language.SLOVENE, Language.CROATIAN,
                                                  Language.SERBIAN, Language.BOSNIAN, Language.GERMAN,
                                                  Language.ITALIAN, Language.SPANISH, Language.FRENCH).build()
except ImportError:  # pragma: no cover
    _DET = None


def lang_id(text: str) -> str | None:
    t = text.strip()
    if not t or _DET is None:
        return None
    lg = _DET.detect_language_of(t)
    return lg.iso_code_639_1.name.lower() if lg is not None else None


def tick(name: str, t0: float) -> None:
    TIMING[name] = round(time.time() - t0, 1)
    logger.info(f"[time] {name}: {TIMING[name]}s")
    (OUT / "timing.json").write_text(json.dumps({"timing": TIMING, "checks": CHECKS}, indent=2, default=str))


# ------------------------------------------------------------------ data
D600 = read_jsonl(DATA / "depth600.jsonl")
DEV = read_jsonl(DATA / "dev_items.jsonl")
NAT = read_jsonl(DATA / "dev_nat_sl.jsonl")
HARMLESS = read_jsonl(DATA / "harmless.jsonl")
H_CON = [r for r in HARMLESS if r["use"] == "H_con"]
H_COL = [r for r in HARMLESS if r["use"] == "H_col"]
SETS = {"D600": D600, "D300": [it for it in D600 if it["in_d300"]], "D200": [it for it in D600 if it["in_d200"]]}
ARM_LANG = {"en_orig": "en", "sl_mt": "sl", "en_bt": "en", "sl_nat": "sl"}

# ------------------------------------------------------------------ engine
from engine import Engine, length_batches  # noqa: E402  (import after arg parsing: torch init is slow)

torch.cuda.set_per_process_memory_fraction(0.92)
t0 = time.time()
ENG = Engine(M)
tok = ENG.tok
tick("load", t0)

# chat template identity across models (both share the 262k tokenizer)
_probe = ENG.render("Test prompt: kako se imaš?")
tmpl_file = RESULTS / "template_render_gemma_it.txt"
if M == "gemma_it":
    tmpl_file.write_text(_probe)
    CHECKS["template_identical_to_gemma"] = True
elif tmpl_file.exists():
    CHECKS["template_identical_to_gemma"] = (tmpl_file.read_text() == _probe)
    assert CHECKS["template_identical_to_gemma"], "chat templates differ between Gemma and GaMS"
CHECKS["template_render"] = _probe
CHECKS["vocab_size"] = len(tok)


# ------------------------------------------------------------------ prefixes
def build_prefixes() -> dict:
    tab = {}
    for lg in ("en", "sl"):
        pstar = P_BASE[lg] + P_EXT[lg]
        pids = tok.encode(pstar, add_special_tokens=False)
        if len(pids) < MIN_P_TOKENS:
            pstar = pstar + P_EXT2[lg]
            pids = tok.encode(pstar, add_special_tokens=False)
        nstar = N_BASE[lg] + N_EXT[lg]
        nids = tok.encode(nstar, add_special_tokens=False)
        for k in (3, 5, 10, 20):
            tab[("P", k, lg)] = pids[:k]
        tab[("P", "full", lg)] = tok.encode(P_BASE[lg], add_special_tokens=False)
        tab[("N", 5, lg)] = nids[:5]
        tab[("N", "full", lg)] = tok.encode(N_BASE[lg], add_special_tokens=False)
        tab[("T2", "full", lg)] = tok.encode(T2[lg], add_special_tokens=False)
        tab[("T3", "full", lg)] = tok.encode(T3[lg], add_special_tokens=False)
        tab[("none", 0, lg)] = []
        CHECKS[f"pstar_{lg}"] = {"text": pstar, "n_tokens": len(pids)}
        CHECKS[f"nstar_{lg}"] = {"text": nstar, "n_tokens": len(nids)}
    return tab


PREF = build_prefixes()
PREF_INFO = {f"{f}|{k}|{lg}": {"ids": v, "n_tokens": len(v), "text": tok.decode(v), "n_chars": len(tok.decode(v))}
             for (f, k, lg), v in PREF.items()}
(OUT / "prefix_table.json").write_text(json.dumps(PREF_INFO, indent=1, ensure_ascii=False))
logger.info("prefixes: " + "; ".join(f"{k}={v['text']!r}({v['n_tokens']}t)" for k, v in PREF_INFO.items()))


def prefix_for(cond: str, arm: str) -> tuple[list[int], str]:
    c = CONDITIONS[cond]
    plang = ARM_LANG[arm]
    fam = c["fam"]
    if fam == "X":  # cross-language: the prefix is in the other language
        plang = "en" if plang == "sl" else "sl"
        fam = "P"
    return PREF[(fam, c["k"], plang)], plang


# ------------------------------------------------------------------ directions state
DIRS: dict | None = None  # loaded from directions.npz after the dirs stage


def load_dirs() -> dict | None:
    p = OUT / "directions.npz"
    if not p.exists():
        return None
    z = np.load(p)
    return {k: z[k] for k in z.files}


def project(captured: dict[int, torch.Tensor], b: int) -> dict:
    """captured[layer]: (B,3,d) positions (inst, post, last). Clip with DEV thresholds, project onto pooled harm/ref
    directions at every captured layer, and per-language directions at L*."""
    out = {"harm_inst": [], "harm_post": [], "harm_last": [], "ref_inst": [], "ref_post": [], "ref_last": []}
    lstar = int(DIRS["lstar"])
    lang_proj = {}
    for li, L in enumerate(CAP_LAYERS):
        x = captured[L][b].numpy().astype(np.float32)  # (3,d)
        x = np.clip(x, DIRS["clip_lo"][li], DIRS["clip_hi"][li])
        ph = x @ DIRS["harm_pooled"][li]
        pr = x @ DIRS["ref_pooled"][li]
        out["harm_inst"].append(float(ph[0])); out["harm_post"].append(float(ph[1])); out["harm_last"].append(float(ph[2]))
        out["ref_inst"].append(float(pr[0])); out["ref_post"].append(float(pr[1])); out["ref_last"].append(float(pr[2]))
        if L == lstar:
            for lg in ("en", "sl"):
                lang_proj[f"harm_last_{lg}"] = float(x[2] @ DIRS[f"harm_{lg}"][li])
                lang_proj[f"ref_last_{lg}"] = float(x[2] @ DIRS[f"ref_{lg}"][li])
                lang_proj[f"ref_post_{lg}"] = float(x[1] @ DIRS[f"ref_{lg}"][li])
    return {"proj": out, "proj_lstar_lang": lang_proj}


# ------------------------------------------------------------------ generic job runner
def make_job(item: dict, arm: str, cond: str, split: str) -> dict:
    text = item[arm]
    pids, plang = prefix_for(cond, arm)
    return {"key": row_key(item["item_id"], M, arm, cond), "item_id": item["item_id"], "cat": item["cat"],
            "group": item["group"], "pure": item["pure"], "arm": arm, "cond": cond, "split": split,
            "prompt_lang": ARM_LANG[arm], "prefix_lang": plang if pids else None, "prompt_text": text,
            "prefix_ids": pids, "in_d300": item.get("in_d300", False)}


def gen_oom_safe(ids, max_new, cap_pos, steer=None, first=False):
    try:
        return ENG.generate(ids, max_new, cap_pos=cap_pos, steer_vecs=steer, return_first_logits=first)
    except torch.cuda.OutOfMemoryError:
        gc.collect(); torch.cuda.empty_cache()
        if len(ids) == 1:
            raise
        h = len(ids) // 2
        logger.warning(f"OOM at batch {len(ids)} -> split")
        a = gen_oom_safe(ids[:h], max_new, cap_pos[:h] if cap_pos else None, steer, first)
        b = gen_oom_safe(ids[h:], max_new, cap_pos[h:] if cap_pos else None, steer, first)
        cap = {L: torch.cat([a["captured"][L], b["captured"][L]]) for L in a["captured"]}
        fl = torch.cat([a["first_lp"], b["first_lp"]]) if first else None
        return {k: a[k] + b[k] for k in ("texts", "n_new", "hit_eos", "gen_ids")} | {"captured": cap, "first_lp": fl}


LSTAR_RES: dict[str, np.ndarray] = {}  # key -> (d,) float32 last-token residual at L* (FINAL D300 subset)
LSTAR_SAVE_CONDS = {"k0", "P5", "P10", "Pfull"}


def run_jobs(jobs: list[dict], out_path: Path, max_new: int, keep_raw: bool = False, tag: str = "") -> list[dict]:
    done = {r["key"] for r in read_jsonl(out_path)}
    todo = [j for j in jobs if j["key"] not in done]
    logger.info(f"[{tag}] {len(jobs)} jobs, {len(todo)} to do -> {out_path.name}")
    if not todo:
        return []
    enc = []
    for j in todo:
        pids, trunc = ENG.encode_prompt(j["prompt_text"])
        ids = pids + j["prefix_ids"]
        ti, tp, tl = ENG.positions(pids, len(ids))
        enc.append((ids, [ti, tp, tl], trunc, len(pids)))
    batches = length_batches([len(e[0]) + max_new for e in enc], ARGS.max_bs, ARGS.budget_tokens)
    t_start = time.time()
    n_done = 0
    new_rows = []
    for bi, bidx in enumerate(batches):
        tb = time.time()
        res = gen_oom_safe([enc[i][0] for i in bidx], max_new, [enc[i][1] for i in bidx])
        dt = time.time() - tb
        rows = []
        for b, i in enumerate(bidx):
            j = todo[i]
            cont = res["texts"][b]
            pref_text = tok.decode(j["prefix_ids"]) if j["prefix_ids"] else ""
            r = {k: v for k, v in j.items() if k not in ("prefix_ids",)}
            r.update({"model": M, "k_tokens": len(j["prefix_ids"]), "k_chars": len(pref_text), "prefix_text": pref_text,
                      "continuation": cont, "n_new_tokens": res["n_new"][b], "hit_eos": bool(res["hit_eos"][b]),
                      "resp_lang": lang_id(cont), "lex_hit": LEX.hit(cont), "degenerate": repetitive(cont),
                      "prompt_truncated": enc[i][2], "n_prompt_tokens": enc[i][3],
                      "gen_seconds": round(dt / len(bidx), 3)})
            if DIRS is not None:
                r.update(project(res["captured"], b))
                if j["cond"] in LSTAR_SAVE_CONDS and j.get("in_d300") and j["arm"] in ("sl_mt", "en_bt") and j["split"] == "FINAL":
                    li = CAP_LAYERS.index(int(DIRS["lstar"]))
                    LSTAR_RES[j["key"]] = res["captured"][int(DIRS["lstar"])][b, 2].numpy().astype(np.float32)
            rows.append(r)
        append_jsonl(out_path, rows)
        new_rows += rows
        n_done += len(bidx)
        el = time.time() - t_start
        if bi % 5 == 0 or bi == len(batches) - 1:
            logger.info(f"[{tag}] batch {bi + 1}/{len(batches)} bs={len(bidx)} T={max(len(enc[i][0]) for i in bidx)} "
                        f"{dt:.1f}s | {n_done}/{len(todo)} rows, {n_done / el:.2f} rows/s, "
                        f"eta {(len(todo) - n_done) / max(n_done / el, 1e-6) / 60:.1f} min")
        del res
    return new_rows


# ------------------------------------------------------------------ stages
def stage_smoke() -> None:
    t0 = time.time()
    items = DEV[:8]
    # T1a prefix placement + k-token identity
    for arm in ("en_orig", "sl_mt", "en_bt"):
        for cond in ("k0", "P5", "N5", "Pfull", "X5"):
            if arm == "en_orig" and cond in ("N5", "X5"):
                continue
            j = make_job(items[0], arm, cond, "SMOKE")
            pids, _ = ENG.encode_prompt(j["prompt_text"])
            full = tok.decode(pids + j["prefix_ids"])
            ptxt = tok.decode(j["prefix_ids"])
            assert full.endswith("<start_of_turn>model\n" + ptxt), (arm, cond, full[-120:])
    lg = "sl"
    pst = tok.encode(CHECKS["pstar_sl"]["text"], add_special_tokens=False)
    assert PREF[("P", 5, lg)] == pst[:5]
    CHECKS["T1_prefix_placement"] = "ok"
    # T1b generation + stop + langid
    jobs = [make_job(it, arm, cond, "SMOKE") for it in items for arm in ("en_orig", "sl_mt", "en_bt")
            for cond in ("k0", "P5", "N5") if not (arm == "en_orig" and cond == "N5")]
    smoke_path = OUT / "smoke_gen.jsonl"
    smoke_path.unlink(missing_ok=True)
    rows = run_jobs(jobs, smoke_path, MAX_NEW, tag="smoke")
    CHECKS["T1_smoke_rows"] = len(rows)
    CHECKS["T1_smoke_hit_eos_rate"] = float(np.mean([r["hit_eos"] for r in rows]))
    CHECKS["T1_smoke_resp_lang"] = {f"{a}": sorted({str(r["resp_lang"]) for r in rows if r["arm"] == a})
                                    for a in ("en_orig", "sl_mt", "en_bt")}
    for r in rows[:6]:
        logger.info(f"SMOKE {r['arm']}|{r['cond']}: {r['prefix_text']!r} + {r['continuation'][:160]!r}")
    # T1c capture consistency: batch capture vs batch-1 capture at the last input position (2 items)
    ids = []
    for it in items[:4]:
        pids, _ = ENG.encode_prompt(it["sl_mt"])
        ids.append((pids + PREF[("P", 5, "sl")], ENG.positions(pids, len(pids) + 5)))
    rb = ENG.generate([x[0] for x in ids], 0, cap_pos=[list(x[1]) for x in ids])
    diffs = []
    for b in range(2):
        r1 = ENG.generate([ids[b][0]], 0, cap_pos=[list(ids[b][1])])
        for L in CAP_LAYERS:
            a1 = rb["captured"][L][b].numpy(); a2 = r1["captured"][L][0].numpy()
            diffs.append(float(np.abs(a1 - a2).max() / (np.abs(a2).max() + 1e-6)))
    CHECKS["T1_capture_batch_vs_single_max_rel_diff"] = max(diffs)
    # T1d steering no-op at a=0 (identical tokens on 4 items)
    g0 = ENG.generate([x[0] for x in ids], 24)
    g1 = ENG.generate([x[0] for x in ids], 24, steer_vecs={CAP_LAYERS[5]: np.zeros(HIDDEN, np.float32)})
    CHECKS["T1_steer_noop_identical"] = g0["gen_ids"] == g1["gen_ids"]
    assert CHECKS["T1_steer_noop_identical"], "steering hook at a=0 changed tokens"
    # batch-vs-single OUTCOME check (32 items, P5 SL-MT): texts saved; judged later (judge.py cell batch_check)
    bc_items = DEV[:32]
    bc_jobs = [make_job(it, "sl_mt", "P5", "BATCHCHECK") for it in bc_items]
    enc = [ENG.encode_prompt(j["prompt_text"])[0] + j["prefix_ids"] for j in bc_jobs]
    rb = ENG.generate(enc, MAX_NEW)
    single = [ENG.generate([e], MAX_NEW)["texts"][0] for e in enc]
    bc_rows = [{"key": j["key"] + "|batch", "item_id": j["item_id"], "arm": "sl_mt", "cond": "P5", "model": M,
                "prompt_text": j["prompt_text"], "prefix_text": tok.decode(j["prefix_ids"]), "continuation": tb,
                "continuation_single": ts, "token_identical": tb == ts,
                "lex_batch": LEX.hit(tb), "lex_single": LEX.hit(ts)} for j, tb, ts in zip(bc_jobs, rb["texts"], single)]
    from common import write_jsonl
    write_jsonl(OUT / "batch_check.jsonl", bc_rows)
    CHECKS["batch_check_token_identical"] = int(sum(r["token_identical"] for r in bc_rows))
    CHECKS["batch_check_lex_agree"] = int(sum(r["lex_batch"] == r["lex_single"] for r in bc_rows))
    logger.info(f"batch check: token-identical {CHECKS['batch_check_token_identical']}/32, lexicon outcome agree "
                f"{CHECKS['batch_check_lex_agree']}/32 (judge agreement computed by judge/analysis)")
    tick("smoke", t0)


def dev_jobs() -> list[dict]:
    jobs = []
    for cond in ["k0", "P5", "N5", "Pfull", "Nfull"]:
        for arm in CONDITIONS[cond]["arms"]:
            jobs += [make_job(it, arm, cond, "DEV") for it in DEV]
    jobs += [make_job(it, "sl_nat", "k0", "DEV") for it in NAT]
    return jobs


def capture_rows(jobs: list[dict]) -> dict[str, np.ndarray]:
    """forward-only (no generation) capture of (inst, post, last) residuals at CAP_LAYERS, float32."""
    enc = []
    for j in jobs:
        pids, _ = ENG.encode_prompt(j["prompt_text"])
        ids = pids + j["prefix_ids"]
        enc.append((ids, list(ENG.positions(pids, len(ids)))))
    out = {}
    for bidx in length_batches([len(e[0]) for e in enc], 64, 64 * 256):
        res = ENG.generate([enc[i][0] for i in bidx], 0, cap_pos=[enc[i][1] for i in bidx])
        for b, i in enumerate(bidx):
            out[jobs[i]["key"]] = np.stack([res["captured"][L][b].numpy() for L in CAP_LAYERS]).astype(np.float32)
    return out


def stage_dev() -> None:
    """DEV generation (resumable), then a forward-only capture pass of every DEV input (float32: Gemma has massive
    activations > fp16 range) saved to dev_raw_caps.npz (used to build directions and project DEV rows)."""
    t0 = time.time()
    jobs = dev_jobs()
    path = OUT / "dev_gen.jsonl"
    run_jobs(jobs, path, MAX_NEW, tag="dev")
    tick("dev_generation", t0)
    t1 = time.time()
    caps = capture_rows(jobs)
    keys = sorted(caps)
    np.savez(OUT / "dev_raw_caps.npz", keys=np.array(keys), caps=np.stack([caps[k] for k in keys]))
    tick("dev_capture", t1)


def stage_dirs() -> None:
    """4.2 DIRECTIONS on DEV + harmless (forward passes only). Harmful set = EN-orig DEV + SL-MT DEV + natural SL DEV
    (k0). The judge filter (refused at k0) is unavailable at this point (OpenRouter daily key limit), so the plan's
    fallback 'use all' is applied; judged-filter directions are rebuilt offline from the saved activations."""
    global DIRS
    t0 = time.time()
    z = np.load(OUT / "dev_raw_caps.npz")
    keys = list(z["keys"]); caps = z["caps"]  # (N,12,3,d) fp16
    kidx = {k: i for i, k in enumerate(keys)}
    harm_rows, harm_lang, harm_src = [], [], []
    for it in DEV:
        for arm in ("en_orig", "sl_mt"):
            harm_rows.append(kidx[row_key(it["item_id"], M, arm, "k0")]); harm_lang.append(ARM_LANG[arm]); harm_src.append(arm)
    for it in NAT:
        harm_rows.append(kidx[row_key(it["item_id"], M, "sl_nat", "k0")]); harm_lang.append("sl"); harm_src.append("sl_nat")
    Hh = caps[harm_rows][:, :, :2, :].astype(np.float32)  # (Nh,12,2,d) positions inst, post
    assert np.isfinite(Hh).all()
    # harmless forward passes (no generation)
    hl_ids, hl_pos, hl_lang = [], [], []
    for r in H_CON:
        for lg in ("en", "sl"):
            pids, _ = ENG.encode_prompt(r[lg])
            hl_ids.append(pids); hl_pos.append(list(ENG.positions(pids, len(pids)))); hl_lang.append(lg)
    Hl = np.zeros((len(hl_ids), len(CAP_LAYERS), 2, HIDDEN), np.float32)
    prev = OUT / "dir_acts.npz"
    if prev.exists():
        zp = np.load(prev)
        if zp["harmless"].shape == Hl.shape and list(zp["harm_keys"]) == [keys[i] for i in harm_rows]:
            Hl = zp["harmless"].astype(np.float32)
            logger.info("dirs: reusing saved harmless activations")
    for bidx in ([] if np.abs(Hl).sum() > 0 else length_batches([len(x) for x in hl_ids], 64, 64 * 200)):
        res = ENG.generate([hl_ids[i] for i in bidx], 0, cap_pos=[hl_pos[i] for i in bidx])
        for li, L in enumerate(CAP_LAYERS):
            Hl[bidx, li] = res["captured"][L][:, :2].numpy()
    np.savez(OUT / "dir_acts.npz", harm=Hh, harmless=Hl,
                        harm_lang=np.array(harm_lang), harm_src=np.array(harm_src),
                        harm_keys=np.array([keys[i] for i in harm_rows]), harmless_lang=np.array(hl_lang))
    D = build_directions(Hh, np.array(harm_lang), Hl, np.array(hl_lang), np.array(harm_src), filt=None)
    np.savez(OUT / "directions.npz", **D)
    DIRS = load_dirs()
    # project the DEV rows now (in-memory raw captures)
    rows = read_jsonl(OUT / "dev_gen.jsonl")
    for r in rows:
        c = caps[kidx[r["key"]]].astype(np.float32)
        cap = {L: torch.from_numpy(c[li][None]) for li, L in enumerate(CAP_LAYERS)}
        r.update(project(cap, 0))
    from common import write_jsonl
    write_jsonl(OUT / "dev_gen.jsonl", rows)
    summ = {k: (v.tolist() if isinstance(v, np.ndarray) and v.size < 64 else None) for k, v in D.items()}
    summ = {k: v for k, v in summ.items() if v is not None}
    (OUT / "directions_summary.json").write_text(json.dumps(summ, indent=1))
    li_ = CAP_LAYERS.index(int(D["lstar"]))
    CHECKS["T2_cv_dprime_ref_at_lstar"] = float(D["cv_dprime_ref_pooled"][li_])
    CHECKS["massive_dims_at_lstar"] = np.where(D["massive_mask"][li_])[0].tolist()
    assert D["cv_dprime_ref_pooled"][li_] > 1.0, "F6: refusal direction does not separate on DEV (CV d' <= 1)"
    logger.info(f"L* = {int(D['lstar'])}; CV d' (ref pooled) by layer: "
                + ", ".join(f"{L}:{d:.2f}" for L, d in zip(CAP_LAYERS, D['cv_dprime_ref_pooled'])))
    tick("directions", t0)


def unit(v: np.ndarray) -> np.ndarray:
    return v / (np.linalg.norm(v) + 1e-12)


def dprime(a: np.ndarray, b: np.ndarray) -> float:
    return float((a.mean() - b.mean()) / math.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2 + 1e-12))


def build_directions(Hh, hlang, Hl, llang, hsrc, filt=None) -> dict:
    """Hh (Nh,12,2,d) harmful acts at (inst, post); Hl (Nl,12,2,d) harmless. filt: boolean mask of harmful rows kept
    for the refusal direction (judge-refused at k0), None = all. Winsorize per dimension at q=.005/.995."""
    keep = np.ones(len(Hh), bool) if filt is None else np.asarray(filt, bool)
    nL = len(CAP_LAYERS)
    out = {k: np.zeros((nL, HIDDEN), np.float32) for k in ("clip_lo", "clip_hi", "harm_pooled", "ref_pooled",
                                                             "harm_en", "harm_sl", "ref_en", "ref_sl")}
    for k in ("cv_dprime_ref_pooled", "cv_dprime_harm_pooled", "cv_dprime_ref_en", "cv_dprime_ref_sl",
              "cv_dprime_harm_en", "cv_dprime_harm_sl", "cos_harm_ref", "cos_ref_en_sl", "cos_harm_en_sl",
              "sd_harm", "sd_ref", "norm_mean_post"):
        out[k] = np.zeros(nL, np.float32)
    # anchors [dir(harm,ref), lang(en,sl), pos(inst,post), layer] for harmful(-refused) and harmless means
    out["anchor_harmful"] = np.zeros((2, 2, 2, nL), np.float32)
    out["anchor_harmless"] = np.zeros((2, 2, 2, nL), np.float32)
    rng = np.random.default_rng(SEED)
    fold_h = rng.integers(0, 5, len(Hh)); fold_l = rng.integers(0, 5, len(Hl))
    rand = np.stack([unit(rng.standard_normal(HIDDEN).astype(np.float32)) for _ in range(3)])
    out["rand_dirs"] = rand
    out["rand_dirs_layer"] = np.zeros((nL, 3, HIDDEN), np.float32)
    out["massive_mask"] = np.zeros((nL, HIDDEN), bool)
    out["sd_rand"] = np.zeros((nL, 3), np.float32)
    for li in range(nL):
        allx = np.concatenate([Hh[:, li].reshape(-1, HIDDEN), Hl[:, li].reshape(-1, HIDDEN)])
        lo, hi = np.quantile(allx, 0.005, axis=0), np.quantile(allx, 0.995, axis=0)
        out["clip_lo"][li], out["clip_hi"][li] = lo, hi
        hh = np.clip(Hh[:, li], lo, hi); hl = np.clip(Hl[:, li], lo, hi)  # (N,2,d)
        # massive-activation dims (e.g. 2339): mean |x| > 50x the median dim -> excluded (zeroed) from every direction,
        # projection and steering vector. Winsorization alone cannot handle a dim that is massive for EVERY token.
        ma = np.abs(np.concatenate([hh.reshape(-1, HIDDEN), hl.reshape(-1, HIDDEN)])).mean(0)
        mask = ma > MASSIVE_FACTOR * np.median(ma)
        out["massive_mask"][li] = mask
        hh = hh.copy(); hl = hl.copy()
        hh[..., mask] = 0.0; hl[..., mask] = 0.0
        rl = rand.copy(); rl[:, mask] = 0.0
        rl = rl / np.linalg.norm(rl, axis=1, keepdims=True)
        out["rand_dirs_layer"][li] = rl
        out["norm_mean_post"][li] = float(np.linalg.norm(np.concatenate([hh[:, 1], hl[:, 1]]), axis=1).mean())

        def mk(pos, hmask, lmask):
            return unit(hh[hmask, pos].mean(0) - hl[lmask, pos].mean(0))
        allh, alll = np.ones(len(hh), bool), np.ones(len(hl), bool)
        out["harm_pooled"][li] = mk(0, allh, alll)
        out["ref_pooled"][li] = mk(1, keep, alll)
        for lg in ("en", "sl"):
            out[f"harm_{lg}"][li] = mk(0, hlang == lg, llang == lg)
            out[f"ref_{lg}"][li] = mk(1, keep & (hlang == lg), llang == lg)
        out["cos_harm_ref"][li] = float(out["harm_pooled"][li] @ out["ref_pooled"][li])
        out["cos_ref_en_sl"][li] = float(out["ref_en"][li] @ out["ref_sl"][li])
        out["cos_harm_en_sl"][li] = float(out["harm_en"][li] @ out["harm_sl"][li])
        # 5-fold CV d' (directions never scored on their own training items)
        for name, pos, hm in (("ref", 1, keep), ("harm", 0, allh)):
            oof_h = np.full(len(hh), np.nan); oof_l = np.full(len(hl), np.nan)
            for f in range(5):
                u = unit(hh[hm & (fold_h != f), pos].mean(0) - hl[fold_l != f, pos].mean(0))
                oof_h[fold_h == f] = hh[fold_h == f, pos] @ u
                oof_l[fold_l == f] = hl[fold_l == f, pos] @ u
            out[f"cv_dprime_{name}_pooled"][li] = dprime(oof_h[hm], oof_l)
            for lg in ("en", "sl"):
                out[f"cv_dprime_{name}_{lg}"][li] = dprime(oof_h[hm & (hlang == lg)], oof_l[llang == lg])
        # centred SDs (projection SD over all DEV activations at the direction's own position)
        out["sd_harm"][li] = float(np.std(np.concatenate([hh[:, 0], hl[:, 0]]) @ out["harm_pooled"][li]))
        out["sd_ref"][li] = float(np.std(np.concatenate([hh[:, 1], hl[:, 1]]) @ out["ref_pooled"][li]))
        post_all = np.concatenate([hh[:, 1], hl[:, 1]])
        out["sd_rand"][li] = np.std(post_all @ rl.T, axis=0)
        for di, dname in enumerate(("harm_pooled", "ref_pooled")):
            for gi, lg in enumerate(("en", "sl")):
                # EN anchors from EN-orig DEV; SL anchors from SL-MT DEV (same items; natural SL excluded)
                hmask = (hlang == lg) & (keep if dname == "ref_pooled" else allh) & (hsrc != "sl_nat")
                for pi in range(2):
                    out["anchor_harmful"][di, gi, pi, li] = float((hh[hmask, pi] @ out[dname][li]).mean())
                    out["anchor_harmless"][di, gi, pi, li] = float((hl[llang == lg, pi] @ out[dname][li]).mean())
    # L*: layer in [12,36] maximising CV d' of the pooled refusal projection; lowest layer within 0.1 of the max
    cand = [(li, L) for li, L in enumerate(CAP_LAYERS) if LSTAR_RANGE[0] <= L <= LSTAR_RANGE[1]]
    best = max(out["cv_dprime_ref_pooled"][li] for li, _ in cand)
    out["lstar"] = np.array(min(L for li, L in cand if out["cv_dprime_ref_pooled"][li] >= best - 0.1))
    out["layers"] = np.array(CAP_LAYERS)
    out["n_harm"] = np.array(len(Hh)); out["n_harm_ref_kept"] = np.array(int(keep.sum())); out["n_harmless"] = np.array(len(Hl))
    return out


def final_jobs(conds: list[str], limit: int = 0, caps: dict | None = None) -> list[dict]:
    jobs = []
    for cond in conds:
        c = CONDITIONS[cond]
        items = SETS[c["set"]]
        n = (caps or {}).get(cond, len(items))
        if limit:
            n = min(n, limit)
        items = sorted(items, key=lambda it: sha1_int(it["item_id"] + str(SEED)))[:n]
        for arm in c["arms"]:
            jobs += [make_job(it, arm, cond, "FINAL") for it in items]
    return jobs


def stage_final() -> None:
    global DIRS
    DIRS = load_dirs()
    assert DIRS is not None, "directions must exist before FINAL"
    from freeze import assert_frozen
    assert_frozen(M)  # protocol.json (+ GaMS addendum) must be committed before the first FINAL generation
    path = OUT / "final_gen.jsonl"
    tiers = ARGS.tiers.split(",")
    caps: dict = {}
    cut_log = []
    t_all = time.time()
    n_rows_total = 0
    for tier in ["A", "B", "C", "D"]:
        if tier not in tiers:
            continue
        conds = [c for c in FINAL_ORDER if CONDITIONS[c]["tier"] == tier and c not in caps.get("_dropped", [])]
        if not conds:
            continue
        t0 = time.time()
        jobs = final_jobs(conds, ARGS.limit, caps)
        rows = run_jobs(jobs, path, MAX_NEW, tag=f"final-{tier}")
        n_rows_total += len(rows)
        tick(f"final_tier_{tier}", t0)
        # timing gate: extrapolate the remaining tiers from observed rows/s
        el = time.time() - t_all
        rps = n_rows_total / el if n_rows_total else None
        if rps:
            remaining = []
            for t2 in "ABCD"[("ABCD".index(tier) + 1):]:
                if t2 in tiers:
                    remaining += [c for c in FINAL_ORDER if CONDITIONS[c]["tier"] == t2]
            rem_rows = len(final_jobs([c for c in remaining if c not in caps.get("_dropped", [])], ARGS.limit, caps))
            proj = (el + rem_rows / rps) / 60
            logger.info(f"[gate] after tier {tier}: {n_rows_total} rows in {el / 60:.1f} min ({rps:.2f} rows/s); "
                        f"projected FINAL total {proj:.1f} min vs budget {ARGS.final_budget_min}")
            for cut in ("T2+T3", "P3", "P20->150", "X5->150"):
                if proj <= ARGS.final_budget_min:
                    break
                if cut == "T2+T3":
                    caps.setdefault("_dropped", []).extend(["T2", "T3"])
                elif cut == "P3":
                    caps.setdefault("_dropped", []).append("P3")
                elif cut == "P20->150":
                    caps["P20"] = 150
                elif cut == "X5->150":
                    caps["X5"] = 150
                cut_log.append(cut)
                rem_rows = len(final_jobs([c for c in remaining if c not in caps.get("_dropped", [])], ARGS.limit, caps))
                proj = (el + rem_rows / rps) / 60
                logger.warning(f"[gate] CUT applied: {cut} -> projected {proj:.1f} min")
    CHECKS["final_cuts"] = cut_log
    CHECKS["final_caps"] = {k: v for k, v in caps.items()}
    if LSTAR_RES:
        ks = sorted(LSTAR_RES)
        prev = OUT / "lstar_residuals.npz"
        if prev.exists():
            z = np.load(prev)
            old = {k: v for k, v in zip(z["keys"], z["res"])}
            old.update(LSTAR_RES)
            ks = sorted(old); arr = np.stack([old[k] for k in ks])
        else:
            arr = np.stack([LSTAR_RES[k] for k in ks])
        np.savez_compressed(prev, keys=np.array(ks), res=arr, lstar=int(DIRS["lstar"]))
    tick("final_all", t_all)


# ------------------------------------------------------------------ causal restoration (6b) + collateral (6c)
def steer_vec(kind: str, a: float) -> tuple[dict, float]:
    lstar = int(DIRS["lstar"]); li = CAP_LAYERS.index(lstar)
    if kind == "own":
        v = a * DIRS["sd_ref"][li] * DIRS["ref_pooled"][li]
    elif kind == "harm":
        v = a * DIRS["sd_harm"][li] * DIRS["harm_pooled"][li]
    elif kind.startswith("rand") and kind.endswith("n"):  # norm-matched to the own direction at the same a
        r = int(kind[4]) - 1
        v = a * DIRS["sd_ref"][li] * DIRS["rand_dirs_layer"][li][r]
    elif kind.startswith("rand"):  # centred-variance matched (own SD units)
        r = int(kind[4]) - 1
        v = a * DIRS["sd_rand"][li][r] * DIRS["rand_dirs_layer"][li][r]
    else:
        raise ValueError(kind)
    return {lstar: v.astype(np.float32)}, float(np.linalg.norm(v))


CAUSAL_GRID = [("own", a) for a in [0.0] + ALPHAS + [12.0]] + [("harm", 2.0), ("harm", 6.0)] + \
              [("rand1", 2.0), ("rand1", 6.0), ("rand2", 2.0), ("rand2", 6.0), ("rand1n", 6.0)]


def causal_pool(n_per_lang: int) -> dict[str, list[dict]]:
    """Pool of likely-flipped FINAL items per arm. The pre-registered pool is JUDGE-flipped items; the judge is not
    available during the GPU pass, so the pool is ENRICHED by lexicon non-hit on the continuation and the restoration
    analysis is restricted afterwards to items the judge labels non-REFUSE at a=0 in the steering run itself."""
    rows = read_jsonl(OUT / "final_gen.jsonl")
    pool = {}
    for arm, conds in (("sl_mt", ["P5", "P10", "Pfull", "P20"]), ("en_bt", ["P5", "P10", "P20", "Pfull"])):
        sel, seen = [], set()
        for cond in conds:
            cand = [r for r in rows if r["arm"] == arm and r["cond"] == cond and r["lex_hit"] == 0 and not r["degenerate"]]
            cand.sort(key=lambda r: sha1_int(r["item_id"] + str(SEED)))
            for r in cand:
                if r["item_id"] not in seen and len(sel) < n_per_lang:
                    sel.append(r); seen.add(r["item_id"])
        pool[arm] = sel
        logger.info(f"causal pool {arm}: {len(sel)} items (lexicon-enriched), by cond "
                    f"{ {c: sum(1 for r in sel if r['cond'] == c) for c in conds} }")
    return pool


def stage_causal(grid=None) -> None:
    global DIRS
    DIRS = load_dirs()
    t0 = time.time()
    grid = grid or CAUSAL_GRID
    pool = causal_pool(ARGS.n_causal)
    path = OUT / "causal.jsonl"
    done = {r["key"] for r in read_jsonl(path)}
    item_by = {it["item_id"]: it for it in D600}
    norms = {}
    for kind, a in grid:
        sv, nrm = steer_vec(kind, a)
        norms[f"{kind}|{a}"] = nrm
        todo = []
        for arm, rs in pool.items():
            for r in rs:
                key = f"{r['key']}|{kind}|{a}"
                if key not in done:
                    todo.append((key, arm, r))
        if not todo:
            continue
        enc = []
        for key, arm, r in todo:
            j = make_job(item_by[r["item_id"]], arm, r["cond"], "CAUSAL")
            enc.append((ENG.encode_prompt(j["prompt_text"])[0] + j["prefix_ids"], j))
        out_rows = []
        for bidx in length_batches([len(e[0]) + MAX_NEW_CAUSAL for e in enc], ARGS.max_bs, ARGS.budget_tokens):
            res = gen_oom_safe([enc[i][0] for i in bidx], MAX_NEW_CAUSAL, None, steer=sv)
            for b, i in enumerate(bidx):
                key, arm, r = todo[i]
                j = enc[i][1]
                cont = res["texts"][b]
                out_rows.append({"key": key, "base_key": r["key"], "item_id": r["item_id"], "cat": r["cat"],
                                 "group": r["group"], "pure": r["pure"], "model": M, "arm": arm, "cond": r["cond"],
                                 "prompt_lang": ARM_LANG[arm], "prompt_text": j["prompt_text"],
                                 "prefix_text": tok.decode(j["prefix_ids"]), "dir": kind, "alpha": a,
                                 "vec_norm": nrm, "lstar": int(DIRS["lstar"]), "continuation": cont,
                                 "n_new_tokens": res["n_new"][b], "lex_hit": LEX.hit(cont),
                                 "degenerate": repetitive(cont), "resp_lang": lang_id(cont), "split": "CAUSAL"})
        append_jsonl(path, out_rows)
        logger.info(f"causal {kind} a={a} (|v|={nrm:.1f}): {len(out_rows)} rows; lex refusal "
                    f"{np.mean([r['lex_hit'] for r in out_rows]):.2f}; {time.time() - t0:.0f}s")
    CHECKS.setdefault("causal_vec_norms", {}).update(norms)
    CHECKS["causal_pool_n"] = {k: len(v) for k, v in pool.items()}
    tick("causal", t0)


# supplementary grid (post-hoc, run after the pre-registered grid showed degeneration from a~2-3 on Gemma):
# finer low alphas + norm-matched random / harm controls at the informative scale. Same pool, same hook.
CAUSAL_GRID2 = [("own", 0.25), ("own", 0.75), ("own", 1.5), ("rand1n", 0.5), ("rand1n", 1.0), ("rand1n", 2.0),
                ("rand2n", 1.0), ("harm", 0.5), ("harm", 1.0)]


def stage_hwcheck(n_p5: int = 48, n_k0: int = 16) -> None:
    """Hardware-consistency check (added after the mid-run 4090 -> L4 migration; see results/hardware_manifest.json):
    regenerate a sha1-sampled set of FINAL rows that were generated on the RTX 4090 (first N lines of final_gen.jsonl)
    on the current GPU, in fresh batches, and store both continuations. Judged outcomes are compared in analysis.py."""
    t0 = time.time()
    man = json.loads((RESULTS / "hardware_manifest.json").read_text())
    n_first = int(man.get(f"{M}_final_rows_on_4090", 0))
    rows = read_jsonl(OUT / "final_gen.jsonl")[:n_first]
    if not rows:
        logger.info("hwcheck: no 4090 rows recorded for this model"); return
    path = OUT / "hw_check.jsonl"
    if len(read_jsonl(path)) > 0:
        logger.info("hwcheck already done"); return
    sel = []
    for (arm, cond), n in ((("sl_mt", "P5"), n_p5), (("en_bt", "P5"), n_p5), (("sl_mt", "k0"), n_k0), (("en_bt", "k0"), n_k0)):
        c = sorted([r for r in rows if r["arm"] == arm and r["cond"] == cond], key=lambda r: sha1_int(r["key"] + "hw" + str(SEED)))
        sel += c[:n]
    item_by = {it["item_id"]: it for it in D600}
    enc = []
    for r in sel:
        j = make_job(item_by[r["item_id"]], r["arm"], r["cond"], "HWCHECK")
        enc.append(ENG.encode_prompt(j["prompt_text"])[0] + j["prefix_ids"])
    out_rows = []
    for bidx in length_batches([len(e) + MAX_NEW for e in enc], ARGS.max_bs, ARGS.budget_tokens):
        res = gen_oom_safe([enc[i] for i in bidx], MAX_NEW, None)
        for b, i in enumerate(bidx):
            r = sel[i]
            cont = res["texts"][b]
            out_rows.append({"key": r["key"] + "|hwL4", "orig_key": r["key"], "item_id": r["item_id"], "arm": r["arm"],
                             "cond": r["cond"], "model": M, "prompt_text": r["prompt_text"], "prefix_text": r["prefix_text"],
                             "continuation": cont, "continuation_orig": r["continuation"],
                             "token_identical": cont == r["continuation"], "lex_new": LEX.hit(cont), "lex_orig": r["lex_hit"],
                             "gpu": torch.cuda.get_device_name(0)})
    append_jsonl(path, out_rows)
    CHECKS["hwcheck_token_identical"] = int(sum(r["token_identical"] for r in out_rows))
    CHECKS["hwcheck_lex_agree"] = int(sum(r["lex_new"] == r["lex_orig"] for r in out_rows))
    CHECKS["hwcheck_n"] = len(out_rows)
    logger.info(f"hwcheck: {len(out_rows)} rows; token-identical {CHECKS['hwcheck_token_identical']}; lexicon agree "
                f"{CHECKS['hwcheck_lex_agree']}")
    tick("hwcheck", t0)


COLL_GRID = [("own", a) for a in [0.0] + ALPHAS + [12.0]] + [("rand1", 2.0), ("rand1", 4.0)]


def stage_collateral() -> None:
    global DIRS
    DIRS = load_dirs()
    t0 = time.time()
    path = OUT / "collateral.jsonl"
    if len(read_jsonl(path)) >= len(COLL_GRID) * 2 * len(H_COL):
        logger.info("collateral complete"); return
    path.unlink(missing_ok=True)
    enc, meta = [], []
    for r in H_COL:
        for lg in ("en", "sl"):
            pids = PREF[("P", "full", lg)]
            enc.append(ENG.encode_prompt(r[lg])[0] + pids)
            meta.append({"hid": r["hid"], "lang": lg, "prompt_text": r[lg], "prefix_text": tok.decode(pids)})
    bl = length_batches([len(e) + MAX_NEW_CAUSAL for e in enc], 50, 50 * 300)
    base_first, base_ids = [None] * len(enc), [None] * len(enc)
    rows = []
    for kind, a in COLL_GRID:
        sv, nrm = steer_vec(kind, a)
        for bidx in bl:
            res = gen_oom_safe([enc[i] for i in bidx], MAX_NEW_CAUSAL, None, steer=sv, first=True)
            if kind == "own" and a == 0.0:
                for b, i in enumerate(bidx):
                    base_first[i] = res["first_lp"][b].numpy(); base_ids[i] = res["gen_ids"][b]
            # teacher-forced NLL of the UNSTEERED continuation under this steering + first-token KL(unsteered||steered)
            flp, nll = ENG.score_continuation([enc[i] for i in bidx], [base_ids[i] for i in bidx], steer_vecs=sv)
            for b, i in enumerate(bidx):
                p0 = base_first[i]
                kl = float(np.sum(np.exp(p0) * (p0 - flp[b])))
                cont = res["texts"][b]
                rows.append({"key": f"{meta[i]['hid']}|{M}|{meta[i]['lang']}|coll|{kind}|{a}", "model": M,
                             "arm": f"harmless_{meta[i]['lang']}", "cond": "Pfull", "dir": kind, "alpha": a,
                             "vec_norm": nrm, "prompt_text": meta[i]["prompt_text"], "prefix_text": meta[i]["prefix_text"],
                             "hid": meta[i]["hid"], "prompt_lang": meta[i]["lang"],
                             "continuation": cont, "n_new_tokens": res["n_new"][b], "first_token_kl": kl,
                             "nll_unsteered_cont": float(nll[b]), "lex_hit": LEX.hit(cont),
                             "degenerate": repetitive(cont), "resp_lang": lang_id(cont), "split": "COLLATERAL"})
            del res
        logger.info(f"collateral {kind} a={a}: KL mean {np.mean([r['first_token_kl'] for r in rows if r['dir'] == kind and r['alpha'] == a]):.3f}")
    append_jsonl(path, rows)
    tick("collateral", t0)


def main() -> None:
    global DIRS
    stages = ARGS.stages.split(",")
    DIRS = load_dirs()
    if "smoke" in stages:
        stage_smoke()
    if "dev" in stages:
        stage_dev()
    if "dirs" in stages:
        stage_dirs()
    if "freeze" in stages:
        from freeze import freeze
        freeze(M)
    if "final" in stages:
        stage_final()
    if "causal" in stages:
        stage_causal()
    if "collateral" in stages:
        stage_collateral()
    if "causal2" in stages:
        stage_causal(CAUSAL_GRID2)
    if "hwcheck" in stages:
        stage_hwcheck()
    CHECKS["peak_mem_gb"] = torch.cuda.max_memory_allocated() / 1e9
    tick("done", time.time())
    ENG.close()


if __name__ == "__main__":
    with logger.catch(reraise=True):
        main()
