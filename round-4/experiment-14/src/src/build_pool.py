#!/usr/bin/env python3
"""0.2 POOL: external harmful items (HarmBench standard, StrongREJECT, JBB-Behaviors harmful, SORRY-Bench if accessible),
deduplicated against every earlier probe of this run + Heretic's own objective sets, hash-split B/C, 200 C-half harmful
items stratified by source; 100 benign twins (JBB benign C-half + gpt-4.1-mini top-up twins).

Writes data/pool_candidates.jsonl, data/dedup_log.jsonl, data/pool_harmful.jsonl, data/pool_benign_pre.jsonl,
data/pool_manifest.json. If parallel artifact 2 already wrote a pool file, it is READ instead (path='read')."""
from __future__ import annotations

import glob
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from loguru import logger

from common import (DATA, DS_DIR, E8, E9, E10, E11, ITER4, ROOT, SEED, dump, half_of, norm, read_jsonl, sha256_file,
                    setup_logging, write_jsonl)

MAX_WORDS = 60
N_HARM, N_BENIGN = 200, 100


def grams8(t: str) -> list[tuple]:
    w = norm(t).split()
    return [tuple(w[i:i + 8]) for i in range(len(w) - 7)]


def strings_of(obj, out: list[str], min_len: int = 25) -> None:
    if isinstance(obj, str):
        if len(obj) >= min_len:
            out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            strings_of(v, out, min_len)
    elif isinstance(obj, list):
        for v in obj:
            strings_of(v, out, min_len)


def load_targets() -> tuple[dict[str, list[str]], dict[str, str]]:
    """returns {target_name: [texts]} and {target_name: status}. Every string field >= 25 chars counts."""
    tg: dict[str, list[str]] = {}
    status: dict[str, str] = {}

    def add_files(name: str, pats: list[str]):
        texts: list[str] = []
        files = []
        for p in pats:
            files += glob.glob(str(p), recursive=True)
        for f in sorted(set(files)):
            try:
                if f.endswith(".jsonl"):
                    for r in read_jsonl(Path(f)):
                        strings_of(r, texts)
                elif f.endswith(".json"):
                    strings_of(json.loads(Path(f).read_text()), texts)
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"target {name}: cannot read {f}: {e}")
        tg[name] = texts
        status[name] = f"ok: {len(files)} files, {len(texts)} strings" if texts else "EMPTY/missing"
        logger.info(f"target {name}: {status[name]}")

    # (7) dataset artifact: RefusEU eval EN/SL + hard blocks (read programmatically; the file is large)
    try:
        ds = json.loads((DS_DIR / "full_data_out.json").read_text())
        texts = [e["input"] for b in ds["datasets"] for e in b["examples"]
                 if b["dataset"] in ("refuseu_eval", "hard_xstest", "hard_orbench_hard1k", "hard_orbench_toxic300",
                                     "refuseu_gold_calib")]
        tg["art_EG6OpEkGvysx"] = texts
        status["art_EG6OpEkGvysx"] = f"ok: {len(texts)} strings"
        del ds
    except (OSError, json.JSONDecodeError, KeyError) as e:
        status["art_EG6OpEkGvysx"] = f"FAILED {e}"
    add_files("exp8_P200", [E8 / "data/*.jsonl"])
    add_files("exp9_P300_T150", [E9 / "data/probe_P300.jsonl", E9 / "data/twins_T150.jsonl", E9 / "data/dev12.jsonl"])
    add_files("exp10_items", [E10 / "data/*.jsonl"])
    add_files("exp11_items", [E11 / "data/items.jsonl"])
    # HF objective sets and public sets
    from datasets import load_dataset
    for name, repo, cfg, split, col in [
        ("mlabonne/harmful_behaviors", "mlabonne/harmful_behaviors", None, None, "text"),
        ("mlabonne/harmless_alpaca", "mlabonne/harmless_alpaca", None, None, "text"),
        ("NASK-PIB/RefusEU", "NASK-PIB/RefusEU", "evaluation", None, None),
    ]:
        try:
            d = load_dataset(repo, cfg) if split is None else {split: load_dataset(repo, cfg, split=split)}
            texts = []
            for sp in d:
                cols = [col] if col and col in d[sp].column_names else [c for c in d[sp].column_names
                                                                       if d[sp].features[c].dtype == "string"]
                for c in cols:
                    texts += [x for x in d[sp][c] if isinstance(x, str) and len(x) >= 10]
            tg[name] = texts
            status[name] = f"ok: {len(texts)} strings"
        except Exception as e:  # noqa: BLE001 - any hub failure is logged and dedup is reported partial
            status[name] = f"FAILED {type(e).__name__}: {str(e)[:160]}"
        logger.info(f"target {name}: {status[name]}")
    try:  # AdvBench: HF mirror gated -> canonical llm-attacks CSV
        import csv
        f = DATA / "raw/harmful_behaviors.csv"
        tg["AdvBench"] = [r["goal"] for r in csv.DictReader(f.open())]
        status["AdvBench"] = f"ok: {len(tg['AdvBench'])} strings (github llm-attacks, sha256 {sha256_file(f)[:16]})"
    except (OSError, KeyError) as e:
        status["AdvBench"] = f"FAILED {e}"
    logger.info(f"target AdvBench: {status['AdvBench']}")
    return tg, status


def load_sources() -> tuple[list[dict], dict[str, str], list[dict]]:
    from datasets import load_dataset
    cands, status, benign = [], {}, []
    import csv
    raw = DATA / "raw"
    # HF mirrors (walledai/HarmBench, walledai/StrongREJECT) are gated for this token -> canonical GitHub CSVs
    try:
        f = raw / "harmbench_behaviors_text_all.csv"
        n = 0
        for r in csv.DictReader(f.open()):
            if r["FunctionalCategory"] == "standard":
                cands.append({"src": "HarmBench", "text": r["Behavior"], "category": r["SemanticCategory"],
                              "hb_id": r["BehaviorID"]})
                n += 1
        status["HarmBench"] = f"ok standard {n} (github centerforaisafety/HarmBench main, sha256 {sha256_file(f)[:16]})"
    except (OSError, KeyError) as e:
        status["HarmBench"] = f"FAILED {e}"
    try:
        f = raw / "strongreject_dataset.csv"
        n = 0
        for r in csv.DictReader(f.open()):
            cands.append({"src": "StrongREJECT", "text": r["forbidden_prompt"], "category": r["category"],
                          "sr_source": r["source"]})
            n += 1
        status["StrongREJECT"] = f"ok {n} (github alexandrasouly/strongreject main, sha256 {sha256_file(f)[:16]})"
    except (OSError, KeyError) as e:
        status["StrongREJECT"] = f"FAILED {e}"
    try:
        d = load_dataset("JailbreakBench/JBB-Behaviors", "behaviors")
        for r in d["harmful"]:
            cands.append({"src": "JBB", "text": r["Goal"], "category": r.get("Category"),
                          "jbb_behavior": r.get("Behavior"), "jbb_source": r.get("Source")})
        for r in d["benign"]:
            benign.append({"src": "JBB-benign", "text": r["Goal"], "category": r.get("Category"),
                           "jbb_behavior": r.get("Behavior")})
        status["JBB"] = f"ok harmful {len(d['harmful'])} benign {len(d['benign'])}"
    except Exception as e:  # noqa: BLE001
        status["JBB"] = f"FAILED {e}"
    try:
        d = load_dataset("sorry-bench/sorry-bench-202503", split="train")
        n = 0
        for r in d:
            if r.get("prompt_style", "base") == "base":
                t = r["turns"][0] if isinstance(r.get("turns"), list) else r.get("prompt")
                cands.append({"src": "SORRY-Bench", "text": t, "category": r.get("category")})
                n += 1
        status["SORRY-Bench"] = f"ok base {n}"
    except Exception as e:  # noqa: BLE001
        status["SORRY-Bench"] = f"SKIPPED (gated/unavailable): {type(e).__name__}: {str(e)[:120]}"
    for k, v in status.items():
        logger.info(f"source {k}: {v}")
    return cands, status, benign


def dedup(cands: list[dict], tg: dict[str, list[str]]) -> tuple[list[dict], list[dict]]:
    exact: dict[str, str] = {}
    gram_owner: dict[tuple, str] = {}
    for name, texts in tg.items():
        for t in texts:
            exact.setdefault(norm(t), name)
            for g in grams8(t):
                gram_owner.setdefault(g, name)
    kept, log = [], []
    seen_exact: dict[str, str] = {}
    seen_grams: dict[tuple, str] = {}
    for c in cands:
        n = norm(c["text"])
        rule = target = None
        if n in exact:
            rule, target = "exact", exact[n]
        else:
            gs = grams8(c["text"])
            if gs:
                hits = [gram_owner[g] for g in gs if g in gram_owner]
                if len(hits) / len(gs) > 0.5:
                    rule, target = "8gram>0.5", Counter(hits).most_common(1)[0][0]
        if rule is None:  # within-pool dedup
            if n in seen_exact:
                rule, target = "within_pool_exact", seen_exact[n]
            else:
                gs = grams8(c["text"])
                if gs:
                    hits = [seen_grams[g] for g in gs if g in seen_grams]
                    if len(hits) / len(gs) > 0.5:
                        rule, target = "within_pool_8gram>0.5", Counter(hits).most_common(1)[0][0]
        if rule:
            log.append({"text": c["text"], "source": c["src"], "matched_target": target, "rule": rule})
            continue
        seen_exact[n] = c["src"]
        for g in grams8(c["text"]):
            seen_grams.setdefault(g, c["src"])
        kept.append(c)
    return kept, log


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("build_pool")
    # (11) parallel artifact 2's pool?
    other = [p for p in glob.glob(str(ITER4 / "*/**/*pool*.json*"), recursive=True)
             if not p.startswith(str(ROOT))]
    logger.info(f"artifact-2 pool files at start-up: {other}")
    tg, tstatus = load_targets()
    cands, sstatus, benign = load_sources()
    for c in cands + benign:
        c["text"] = re.sub(r"\s+", " ", (c["text"] or "")).strip()
    cands = [c for c in cands if c["text"]]
    kept, log = dedup(cands, tg)
    bkept, blog = dedup(benign, tg)
    write_jsonl(DATA / "dedup_log.jsonl", log + [dict(x, kind="benign") for x in blog])
    for c in kept + bkept:
        c["n_words"] = len(c["text"].split())
        c["half"] = half_of(c["text"])
    long_ = [c for c in kept if c["n_words"] > MAX_WORDS]
    kept = [c for c in kept if c["n_words"] <= MAX_WORDS]
    write_jsonl(DATA / "pool_candidates.jsonl", kept)
    C = [c for c in kept if c["half"] == "C"]
    logger.info(f"candidates {len(cands)} -> dedup kept {len(kept) + len(long_)} -> <= {MAX_WORDS} words {len(kept)};"
                f" C-half {len(C)} by source {Counter(c['src'] for c in C)}")
    # stratified by source: proportional allocation (largest remainder), seeded order within source
    rng = random.Random(SEED)
    by = defaultdict(list)
    for c in C:
        by[c["src"]].append(c)
    for s in by:
        by[s].sort(key=lambda c: norm(c["text"]))
        rng.shuffle(by[s])
    tot = len(C)
    n_take = min(N_HARM, tot)
    alloc = {s: n_take * len(v) / tot for s, v in by.items()}
    base = {s: int(a) for s, a in alloc.items()}
    rem = n_take - sum(base.values())
    for s in sorted(alloc, key=lambda s: -(alloc[s] - base[s]))[:rem]:
        base[s] += 1
    harm = []
    for s in sorted(by):
        harm += by[s][:base[s]]
    for k, c in enumerate(sorted(harm, key=lambda c: (c["src"], norm(c["text"])))):
        c["item_id"] = f"h{k:03d}"
        c["kind"] = "harmful"
    harm = sorted(harm, key=lambda c: c["item_id"])
    write_jsonl(DATA / "pool_harmful.jsonl", harm)
    # benign: JBB benign C-half first (prefer those whose harmful sibling behavior is in our C harmful set)
    beh_in = {c.get("jbb_behavior") for c in harm if c["src"] == "JBB"}
    bC = [b for b in bkept if b["half"] == "C" and b["n_words"] <= MAX_WORDS]
    bC.sort(key=lambda b: (b.get("jbb_behavior") not in beh_in, norm(b["text"])))
    ben = bC[:N_BENIGN]
    for k, b in enumerate(ben):
        b["item_id"] = f"b{k:03d}"
        b["kind"] = "benign"
        b["twin_of"] = next((c["item_id"] for c in harm if c["src"] == "JBB" and c.get("jbb_behavior") ==
                             b.get("jbb_behavior")), None)
    write_jsonl(DATA / "pool_benign_pre.jsonl", ben)
    man = {"path": "rebuilt", "artifact2_pool_files_at_startup": other, "seed": SEED,
           "rule": "norm = NFKC lower, strip punct, collapse ws; drop if exact norm match OR share of candidate word "
                   "8-grams found in targets > 0.5; within-pool the same; > 60 words excluded; half = 'B' if "
                   "int(sha256('20260926|'+norm)[:8],16) % 2 == 0 else 'C'",
           "labse_flag": "not run (optional in plan; skipped for time, logged)",
           "sources": sstatus, "targets": tstatus, "n_candidates": len(cands),
           "dedup_dropped": dict(Counter(x["rule"] for x in log)),
           "dedup_dropped_by_target": dict(Counter(x["matched_target"] for x in log)),
           "n_after_dedup": len(kept) + len(long_), "n_long_excluded": len(long_), "n_pool": len(kept),
           "half_sizes": dict(Counter(c["half"] for c in kept)), "C_by_source": dict(Counter(c["src"] for c in C)),
           "harmful_selected": len(harm), "harmful_by_source": dict(Counter(c["src"] for c in harm)),
           "benign_jbb_C": len(ben), "benign_needed_topup": N_BENIGN - len(ben)}
    dump(DATA / "pool_manifest.json", man)
    logger.info(json.dumps(man, indent=1, default=str)[:3000])


if __name__ == "__main__":
    main()
