#!/usr/bin/env python3
"""P5/P6 (GPU) for one instruct checkpoint (gemma = google/gemma-3-12b-it, gams = cjvt/GaMS3-12B-Instruct):
 a) template log + checks; c) CONSTRUCT extraction at L_pt (own EN/SL/pooled refusal dirs, lang-ID dir, N_bar);
 d) R on 100 CONSTRUCT pairs; e) s on all SCORE pairs + SCORE-harmless; f) R on SCORE-400;
 g) C4 induction at L_pt (per-row steering vectors, exact-length buckets) with R and s per generation.
Every stage writes its own file and is skipped if the file exists (resumable).
Usage: python src/instruct_run.py --model gemma|gams [--stages acdefg] [--limit N --tag _smoke]"""
from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np
import torch
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

ROOT = C.ROOT
ALPHA_MULTS = np.geomspace(0.03, 3.0, 12)  # pre-registered k = 0..11
_R = (3.0 / 0.03) ** (1 / 11)
# D14 (declared before any induction output was seen): N_bar is ~16x the own-direction raw norm, so the pre-registered
# grid may start above the positive control's crossing. Three lower log-steps (k = -2, -3, -4) are added for EVERY
# direction; k = -1 is the shared alpha = 0 baseline.
EXT_MULTS = {-2: 0.03 / _R, -3: 0.03 / _R ** 2, -4: 0.03 / _R ** 3}


def mult_of(k: int) -> float:
    return 0.0 if k == -1 else float(EXT_MULTS[k]) if k < -1 else float(ALPHA_MULTS[k])


def load_items(limit: int | None):
    pairs = C.read_jsonl(ROOT / "data/refuseu_pairs.jsonl")
    alp = C.read_jsonl(ROOT / "data/alpaca_harmless.jsonl")
    if limit:
        pairs = [p for p in pairs if p["role"] == "CONSTRUCT"][:limit] + [p for p in pairs if p["role"] == "SCORE" and p["in_score400"]][:limit] + \
                [p for p in pairs if p["role"] == "SCORE" and not p["in_score400"]][:limit]
        alp = [a for a in alp if a["role"] == "CONSTRUCT"][:limit] + [a for a in alp if a["role"] == "SCORE" and a["induction"]][:limit] + \
              [a for a in alp if a["role"] == "SCORE" and not a["induction"]][:limit]
    return pairs, alp


def random_dirs(d: int) -> np.ndarray:
    p = ROOT / "results/shared/random_dirs.npy"
    if p.exists():
        return np.load(p)
    g = torch.Generator().manual_seed(C.SEED)
    R = torch.randn(5, d, generator=g).numpy().astype(np.float32)
    R = R / np.linalg.norm(R, axis=1, keepdims=True)
    p.parent.mkdir(parents=True, exist_ok=True)
    np.save(p, R)
    return R


def classify(text: str, lang: str) -> dict:
    hit_u, m_u = C.lexicon_hit(text, None)
    hit_l, _ = C.lexicon_hit(text, lang)
    deg = C.is_degenerate(text)
    return {"R_lex": int(hit_u and not deg), "R_lex_langonly": int(hit_l and not deg), "lex_hit_any": int(hit_u),
            "markers": m_u[:5], "degenerate": int(deg)}


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--stages", default="acdefg")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--tag", default="")
    ap.add_argument("--gen_bs", type=int, default=64)
    ap.add_argument("--ind_bs", type=int, default=96)
    ap.add_argument("--s_bs", type=int, default=32)
    ap.add_argument("--ind_budget_min", type=float, default=55.0)
    ap.add_argument("--s_mode", default="cache")
    a = ap.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (150 * 1024**3, 150 * 1024**3))
    out = ROOT / f"results/inst_{a.model}{a.tag}"
    out.mkdir(parents=True, exist_ok=True)
    logger.add(ROOT / f"logs/instruct_run_{a.model}{a.tag}.log", rotation="30 MB", level="DEBUG")
    L = json.loads((ROOT / "results/base_pt/layer_choice.json").read_text())["L_pt"]
    logger.info(f"model {a.model}: steering/extraction layer L_pt={L}")
    pairs, alp = load_items(a.limit)
    model, tok = C.load_model("tiny_it" if a.model.startswith("tiny") else a.model)
    d = C.hidden_size(model)

    # ---------------- a) template checks
    if "a" in a.stages:
        lines = []
        for lang in ["en", "sl"]:
            for p in pairs[:3]:
                s = tok.apply_chat_template([{"role": "user", "content": p[lang]}], add_generation_prompt=True, tokenize=False)
                ids = C.chat_ids(tok, p[lang])
                lines.append(f"--- {lang} {p['pair_id']} n_tok={len(ids)} n_bos={ids.count(tok.bos_token_id)}\n{s!r}")
        (out / "template_log.txt").write_text("\n".join(lines))

    for p in pairs:
        p["ids_en"], p["ids_sl"] = C.chat_ids(tok, p["en"]), C.chat_ids(tok, p["sl"])
    for x in alp:
        x["ids_en"], x["ids_sl"] = C.chat_ids(tok, x["en"]), C.chat_ids(tok, x["sl"])

    # ---------------- c) CONSTRUCT extraction at L (own dirs, lang-ID, N_bar)
    dirs_path = out / "own_dirs.npz"
    if "c" in a.stages and not dirs_path.exists():
        rows = []
        for p in pairs:
            if p["role"] == "CONSTRUCT":
                for lang in ["en", "sl"]:
                    rows.append({"uid": f"h|{p['pair_id']}|{lang}", "ids": p[f"ids_{lang}"], "k": "harm", "lang": lang})
        for x in alp:
            if x["role"] == "CONSTRUCT":
                for lang in ["en", "sl"]:
                    rows.append({"uid": f"b|{x['hid']}|{lang}", "ids": x[f"ids_{lang}"], "k": "harmless", "lang": lang})
        t0 = time.time()
        res, norms = C.residuals_all_layers(model, rows, max_bs=a.s_bs, norm_layer=L)
        logger.info(f"CONSTRUCT extraction {len(rows)} prompts {time.time()-t0:.0f}s")
        means = {}
        for k in ["harm", "harmless"]:
            for lang in ["en", "sl"]:
                means[f"{k}_{lang}"] = np.mean([res[r["uid"]].astype(np.float32) for r in rows if r["k"] == k and r["lang"] == lang], 0)
        own = {lang: means[f"harm_{lang}"] - means[f"harmless_{lang}"] for lang in ["en", "sl"]}
        own["pooled"] = (own["en"] + own["sl"]) / 2
        langid = means["harmless_sl"] - means["harmless_en"]
        hl = [norms[r["uid"]] for r in rows if r["k"] == "harmless"]
        n_bar = sum(s for s, _ in hl) / sum(c for _, c in hl)
        np.savez(dirs_path, **{f"allL_raw_{k}": v for k, v in own.items()}, allL_langid_raw=langid,
                 **{f"unit_{k}": C.unit(v[L]) for k, v in own.items()}, unit_langid=C.unit(langid[L]),
                 **{f"mean_{k}": v for k, v in means.items()}, n_bar=np.array(n_bar), L=np.array(L))
        logger.info(f"N_bar(L={L}) = {n_bar:.2f}; |own pooled raw| = {np.linalg.norm(own['pooled'][L]):.2f}")
    D = np.load(dirs_path)
    n_bar = float(D["n_bar"])
    rnd = random_dirs(d)

    def build_dir_tab() -> dict:
        """unit vectors at L in this model's residual space (base dirs re-read at call time: gb may finish later)"""
        tab = {}
        for src, path in [("pt", ROOT / "results/base_pt/directions.npz"), ("gb", ROOT / "results/base_gb/directions.npz")]:
            if path.exists():
                tab[src] = np.load(path)["unit_pooled"][L]
        tab["own_pooled"], tab["own_en"], tab["own_sl"] = D["unit_pooled"], D["unit_en"], D["unit_sl"]
        tab["langid"] = D["unit_langid"]
        for i in range(5):
            tab[f"rand{i}"] = rnd[i]
        cos = {f"{x}~{y}": float(np.dot(tab[x], tab[y])) for i, x in enumerate(tab) for y in list(tab)[i + 1:]}
        (out / "direction_cosines.json").write_text(json.dumps({"L": L, "cos": cos}, indent=1))
        logger.info("cos: " + ", ".join(f"{k} {v:+.3f}" for k, v in cos.items() if "rand" not in k))
        return tab
    dir_tab = build_dir_tab()

    # ---------------- d) R on 100 CONSTRUCT pairs (lowest sha1) -> m (D2)
    p_d = out / "r_construct100.jsonl"
    if "d" in a.stages and not p_d.exists():
        cp = sorted([p for p in pairs if p["role"] == "CONSTRUCT"], key=lambda p: p["sha1"])[:100]
        rows = [{"uid": f"{p['pair_id']}|{lang}", "ids": p[f"ids_{lang}"], "pair_id": p["pair_id"], "lang": lang}
                for p in cp for lang in ["en", "sl"]]
        t0 = time.time()
        g = C.generate(model, tok, rows, max_bs=a.gen_bs)
        logger.info(f"CONSTRUCT-100 generation {len(rows)} in {time.time()-t0:.0f}s")
        C.write_jsonl(p_d, [{"model": a.model, "pair_id": r["pair_id"], "lang": r["lang"], "text": g[r["uid"]]["text"],
                             "n_tok": g[r["uid"]]["n_tok"], **classify(g[r["uid"]]["text"], r["lang"])} for r in rows])

    # ---------------- e) s on all SCORE pairs + SCORE-harmless
    p_e = out / "s_score.jsonl"
    if "e" in a.stages and not p_e.exists():
        rows = [{"uid": f"h|{p['pair_id']}|{lang}", "ids": p[f"ids_{lang}"], "lang": lang, "kind": "harm",
                 "item": p["pair_id"], "category": p["category"], "in_score400": p["in_score400"]}
                for p in pairs if p["role"] == "SCORE" for lang in ["en", "sl"]]
        rows += [{"uid": f"b|{x['hid']}|{lang}", "ids": x[f"ids_{lang}"], "lang": lang, "kind": "harmless",
                  "item": x["hid"], "category": "harmless", "in_score400": False}
                 for x in alp if x["role"] == "SCORE" for lang in ["en", "sl"]]
        # equivalence check cache vs concat on 16 prompts
        chk = rows[:8] + [r for r in rows if r["lang"] == "sl"][:8]
        s1 = C.score_s(model, tok, chk, max_bs=a.s_bs, mode="cache")
        s2 = C.score_s(model, tok, chk, max_bs=a.s_bs, mode="concat")
        diffs = [abs(s1[r["uid"]]["s"] - s2[r["uid"]]["s"]) for r in chk]
        # D13: in fp32 the two paths agree to 1e-4 (smoke_test.json); in bf16/NF4 they differ by O(0.1-0.6) nats of
        # kernel-path noise on either side of the fp32 value, so only a gross discrepancy (> 0.5 nats) triggers concat.
        ok = max(diffs) < 0.5
        (out / "s_equivalence_check.json").write_text(json.dumps({"max_abs_diff": max(diffs), "diffs": diffs, "pass": ok}))
        logger.info(f"s KV-reuse vs concat: max |diff| {max(diffs):.4f} -> {'PASS' if ok else 'FAIL -> concat'}")
        mode = a.s_mode if ok else "concat"
        t0 = time.time()
        s = C.score_s(model, tok, rows, max_bs=a.s_bs, mode=mode)
        logger.info(f"s on {len(rows)} prompts ({mode}) in {time.time()-t0:.0f}s")
        C.write_jsonl(p_e, [{"model": a.model, "item": r["item"], "kind": r["kind"], "lang": r["lang"],
                             "category": r["category"], "in_score400": r["in_score400"], "s_mode": mode, **s[r["uid"]]}
                            for r in rows])

    # ---------------- f) R on SCORE-400
    p_f = out / "r_score400.jsonl"
    if "f" in a.stages and not p_f.exists():
        sp = [p for p in pairs if p["in_score400"]]
        rows = [{"uid": f"{p['pair_id']}|{lang}", "ids": p[f"ids_{lang}"], "pair_id": p["pair_id"], "lang": lang,
                 "category": p["category"]} for p in sp for lang in ["en", "sl"]]
        t0 = time.time()
        g = C.generate(model, tok, rows, max_bs=a.gen_bs)
        logger.info(f"SCORE-400 generation {len(rows)} in {time.time()-t0:.0f}s")
        C.write_jsonl(p_f, [{"model": a.model, "pair_id": r["pair_id"], "lang": r["lang"], "category": r["category"],
                             "text": g[r["uid"]]["text"], "n_tok": g[r["uid"]]["n_tok"], "first_tok": g[r["uid"]]["first_tok"],
                             **classify(g[r["uid"]]["text"], r["lang"])} for r in rows])

    # ---------------- g) C4 induction
    if "g" in a.stages:
        dir_tab = build_dir_tab()
        if "gb" not in dir_tab:
            logger.warning("GaMS-base direction not available at induction start -> omitted (cut 6)")
        p_g = out / "induction.jsonl"
        done = set()
        if p_g.exists():
            for r in C.read_jsonl(p_g):
                done.add((r["direction"], r["alpha_k"]))
        ind = [x for x in alp if x["induction"]]
        ind = sorted(ind, key=lambda x: x["sha1"])
        alphas = n_bar * ALPHA_MULTS
        steer = C.Steerer(model, L)
        # (direction, alpha indices, prompt items)
        full_k = [-4, -3, -2] + list(range(12))
        tierB_k = [-4, -2, 0, 2, 4, 6, 8, 10, 11]
        # residual-norm profile at L (why N_bar is large): CONSTRUCT-harmless, non-BOS positions
        prof_p = out / "norm_profile.json"
        if not prof_p.exists():
            rows_n = [{"uid": f"{x['hid']}|{lang}", "ids": x[f"ids_{lang}"]} for x in alp if x["role"] == "CONSTRUCT" for lang in ["en", "sl"]]
            norms_all = []
            with torch.inference_mode():
                for b in C.buckets(rows_n, 32):
                    ids = torch.tensor([r["ids"] for r in b], device="cuda")
                    hs = model(input_ids=ids, output_hidden_states=True, logits_to_keep=1).hidden_states[L]
                    nn_ = hs[:, 1:, :].float().norm(dim=-1)
                    norms_all.append(nn_.flatten().cpu().numpy())
                    if len(norms_all) == 1:
                        first_pos = nn_[:, :6].mean(0).cpu().numpy().tolist()
            v = np.concatenate(norms_all)
            prof = {"n_positions": int(len(v)), "mean": float(v.mean()), "median": float(np.median(v)),
                    "p10": float(np.percentile(v, 10)), "p90": float(np.percentile(v, 90)), "p99": float(np.percentile(v, 99)),
                    "max": float(v.max()), "mean_first6_nonBOS_positions_bucket0": first_pos,
                    "own_pooled_raw_norm": float(np.linalg.norm(D["allL_raw_pooled"][L])), "n_bar": n_bar}
            prof_p.write_text(json.dumps(prof, indent=1))
            logger.info(f"norm profile at L={L}: {prof}")
        plan = [("none", [-1], ind)]
        plan += [("pt", full_k, ind), ("own_pooled", full_k, ind), ("langid", full_k, ind)]
        plan += [(f"rand{i}", full_k, ind[:20]) for i in range(5)]
        plan += [("gb", full_k, ind), ("own_en", full_k, ind), ("own_sl", full_k, ind)]
        plan = [p for p in plan if p[0] == "none" or p[0] in dir_tab]
        tier = "A"
        t_start = time.time()
        n_done_gen = 0
        for di, (dname, ks, items) in enumerate(plan):
            if tier == "B":
                if dname.startswith("rand") and int(dname[4:]) >= 3:
                    logger.warning(f"TIER B: skip {dname}")
                    continue
                if dname in ("gb", "own_en", "own_sl"):
                    ks = tierB_k
            ks = [k for k in ks if (dname, k) not in done]
            if not ks:
                continue
            rows = []
            for k in ks:
                alpha = n_bar * mult_of(k)
                v = torch.zeros(d) if dname == "none" else torch.tensor(dir_tab[dname] * alpha, dtype=torch.float32)
                v = v.to(torch.bfloat16)
                for x in items:
                    for lang in ["en", "sl"]:
                        rows.append({"uid": f"{dname}|{k}|{x['hid']}|{lang}", "ids": x[f"ids_{lang}"], "vec": v,
                                     "lang": lang, "hid": x["hid"], "k": k, "alpha": alpha})
            t0 = time.time()
            g = C.generate(model, tok, rows, max_bs=a.ind_bs, steerer=steer, progress_every=0)
            s = C.score_s(model, tok, rows, max_bs=a.ind_bs, steerer=steer, mode="cache")
            dt = time.time() - t0
            n_done_gen += len(rows)
            recs = [{"model": a.model, "direction": dname, "alpha_k": r["k"], "alpha_mult": mult_of(r["k"]),
                     "alpha_abs": r["alpha"], "hid": r["hid"], "lang": r["lang"], "text": g[r["uid"]]["text"],
                     "n_tok": g[r["uid"]]["n_tok"], "s": s[r["uid"]]["s"], "tier": tier, **classify(g[r["uid"]]["text"], r["lang"])}
                    for r in rows]
            C.write_jsonl(p_g, recs, mode="a")
            el = (time.time() - t_start) / 60
            rate = el / n_done_gen
            remaining = sum(len(p[1]) * len(p[2]) * 2 for p in plan[di + 1:])
            proj = el + rate * remaining
            byk = {}
            for r in recs:
                byk.setdefault(r["alpha_k"], []).append(r["R_lex"])
            logger.info(f"induction {dname}: {len(rows)} gens in {dt:.0f}s; R by k: " +
                        " ".join(f"{k}:{np.mean(v):.2f}" for k, v in sorted(byk.items())) +
                        f" | elapsed {el:.1f} min, projected total {proj:.1f} min")
            if tier == "A" and di >= 3 and proj > a.ind_budget_min:
                tier = "B"
                logger.warning(f"projected induction {proj:.1f} min > {a.ind_budget_min} -> TIER B for remaining directions")
                (out / "induction_tier.json").write_text(json.dumps({"tier": "B", "switched_after": dname, "projected_min": proj}))
        steer.remove()
        if tier == "A":
            (out / "induction_tier.json").write_text(json.dumps({"tier": "A"}))
    C.unload(model)
    logger.info("done")


if __name__ == "__main__":
    main()
