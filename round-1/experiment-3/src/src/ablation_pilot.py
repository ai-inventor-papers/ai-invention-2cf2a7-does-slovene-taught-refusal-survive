#!/usr/bin/env python3
"""CONSTRUCT-phase pilot (no SCORE items): the pre-registered zero-projection ablation h - (h.u)u was catastrophic in
GaMS (persona AND random directions; see results/mc_gams.json a_late). Compare ablation variants on a subset of the
manipulation-check items: zero vs mean-projection (h - ((h.u) - mu.u)u, mu = mean residual over non-BOS positions of
CONSTRUCT reference prompts), each with/without skipping the BOS position. Also computes and saves mu per layer.
Writes results/ablation_pilot_{model}.json and results/directions/{model}_mu.npz."""
from __future__ import annotations

import argparse
import json
import time

import numpy as np
from loguru import logger

from common import DATA, DIRS, LATE, RES, read_jsonl, setup_logging
from engine import Engine
from gpu_run import CFG, OWN_RE, generate


def compute_mu(E: Engine, key: str) -> np.ndarray:
    f = DIRS / f"{key}_mu.npz"
    if f.exists():
        return np.load(f)["mu"]
    cdir = read_jsonl(DATA / "construct_dir.jsonl")[:150]
    hcon = [r for r in read_jsonl(DATA / "harmless.jsonl") if r["set"] == "HARMLESS-CONSTRUCT"]
    ids = [E.encode_prompt(p[f"prompt_{lg}"])[0] for lg in ["en", "sl"] for p in cdir] + \
          [E.encode_prompt(r[f"prompt_{lg}"])[0] for lg in ["en", "sl"] for r in hcon]
    ws = []
    for x in ids:
        w = np.zeros(len(x), dtype=np.float32)
        nb = [i for i, t in enumerate(x) if t != E.tok.bos_token_id]
        w[nb] = 1.0 / len(nb)
        ws.append(w)
    cap = E.capture(ids, ws, list(range(48)))
    mu = np.stack([cap[l].mean(0) for l in range(48)]).astype(np.float32)
    np.savez_compressed(f, mu=mu, n_prompts=len(ids), note="mean residual over non-BOS positions, CONSTRUCT-DIR 150x2 + HARMLESS-CONSTRUCT 100x2")
    return mu


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    a = ap.parse_args()
    setup_logging(f"ablation_pilot_{a.model}")
    CFG.update({"budget": 10000, "max_bs": 40})
    E = Engine(a.model)
    t0 = time.time()
    mu = compute_mu(E, a.model)
    logger.info(f"mu computed in {time.time() - t0:.0f}s")
    D = np.load(DIRS / f"{a.model}.npz")
    ident = json.loads((DATA / "identity_items.json").read_text())
    mc40 = read_jsonl(DATA / "mc_harm40.jsonl")[:20]
    heval = [r for r in read_jsonl(DATA / "harmless.jsonl") if r["set"] == "HARMLESS-EVAL"][:10]
    items = ([{"prompt": q[li], "lang": lg, "set": "id"} for li, lg in enumerate(["en", "sl"]) for q in ident["ID_CHECK"][:20]] +
             [{"prompt": p[f"prompt_{lg}"], "lang": lg, "set": "harm"} for lg in ["en", "sl"] for p in mc40] +
             [{"prompt": r[f"prompt_{lg}"], "lang": lg, "set": "harmless"} for lg in ["en", "sl"] for r in heval])
    dirs = {"persona_a": D["persona_a"], "persona_b": D["persona_b"], "iso0": D["iso_a"][0], "var0": D["var_a"][0]}
    res = {}

    def summarize(rows):
        out = {}
        for s in ["id", "harm", "harmless"]:
            for lg in ["en", "sl"]:
                rr = [r for r, it in zip(rows, items) if it["set"] == s and it["lang"] == lg]
                out[f"{s}|{lg}"] = {"R": float(np.mean([r["R_lexv1"] for r in rr])),
                                    "own": float(np.mean([bool(OWN_RE[a.model].search(r["response"])) for r in rr])),
                                    "degen": float(np.mean([r["degenerate"] for r in rr])),
                                    "lang_ok": float(np.mean([r["resp_lang"] == lg for r in rr])),
                                    "ex": rr[0]["response"][:100]}
        return out

    E.skip_bos = False
    res["original"] = summarize(generate(E, items, lambda g: None, 64, False, "orig"))
    for variant, (mean, skip) in {"zero_skipbos": (False, True), "mean_all": (True, False), "mean_skipbos": (True, True)}.items():
        E.skip_bos = skip
        for dn, U in dirs.items():
            dd = {l: U[l] for l in LATE}
            cc = {l: float(mu[l] @ U[l]) for l in LATE} if mean else None
            rows = []
            with E.ablating(dd, cc):
                rows = generate(E, items, lambda g: None, 64, False, f"{variant}-{dn}")
            res[f"{variant}|{dn}"] = summarize(rows)
            s = res[f"{variant}|{dn}"]
            logger.info(f"{variant}|{dn}: " + " ".join(f"{k}:R={v['R']:.2f},own={v['own']:.2f},dg={v['degen']:.2f},lg={v['lang_ok']:.2f}" for k, v in s.items()))
    (RES / f"ablation_pilot_{a.model}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
