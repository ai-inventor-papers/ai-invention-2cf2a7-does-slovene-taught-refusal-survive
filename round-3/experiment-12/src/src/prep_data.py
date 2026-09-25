#!/usr/bin/env python3
"""STEP 1 (CPU part): build every item set used by the RQ3 capability control.

1a utility: 6 tasks x 300 paired EN/SL items (+100 ordered reserve), EN rendered into the SL {query, choices, gold} schema
1b Belebele EN/SL/HU (200 items, paired by (link, question_number))
1c harmless Dolly-15k KL/generation set (EN originals; MT arms are added by src/prep_mt.py on GPU)
1d fluency passages (150 unique FLORES passages, parallel EN/SL/HU)
1e overlap audit vs every block of the dataset dependency art_EG6OpEkGvysx and the selection harmless sets
Writes data/** and data/manifest.json (sha256 of every file).
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from datasets import load_dataset  # noqa: E402

from common import (DATA, ITER1_DATASET, ITER2_EXP8, ITER1_EXP4, SEED, UTIL_TASKS, sha1_int, sha256_file,  # noqa: E402
                    setup_logger, write_jsonl, read_jsonl)

logger = setup_logger("prep_data")
SL_REPO, SL_REV = "cjvt/slovenian-llm-eval", "ca2f68d373"
N_UTIL, N_RESERVE, N_BELE, N_KL, N_KL_SPARE, N_FLU = 300, 100, 200, 200, 60, 150


def sl_load(task: str):
    try:
        return load_dataset(SL_REPO, task, split="test", revision=SL_REV)
    except Exception as e:  # noqa: BLE001 - revision prefix may not resolve; fall back to main and log it
        logger.warning(f"revision {SL_REV} failed for {task} ({e!r}); loading main")
        return load_dataset(SL_REPO, task, split="test")


def hs_preprocess(text: str) -> str:
    """lm-eval hellaswag utils.preprocess (verbatim logic)."""
    text = text.strip()
    text = text.replace(" [title]", ". ")
    text = re.sub("\\[.*?\\]", "", text)
    text = text.replace("  ", " ")
    return text


def wino_partial(sentence: str, o1: str, o2: str) -> tuple[list[str], str] | None:
    """lm-eval winogrande partial scoring: contexts = sentence[:_] with option, continuation = rest after _."""
    if sentence.count("_") != 1:
        return None
    idx = sentence.index("_")
    cont = sentence[idx + 1:].strip()
    if not cont:
        return None
    ctxs = [sentence[:idx] + o1, sentence[:idx] + o2]
    return ctxs, " " + cont


def build_pairs(task: str) -> tuple[list[dict], dict]:
    """Returns a list of pair dicts {pair_id, en:{...}, sl:{...}} rendered into the {query, choices, gold} schema."""
    sl = sl_load(task)
    info: dict = {"task": task, "n_sl": len(sl)}
    pairs = []
    if task == "arc_challenge":
        en = load_dataset("allenai/ai2_arc", "ARC-Challenge", split="test")
        by_id = {r["id"]: r for r in en}
        for r in sl:
            e = by_id.get(r["id"])
            if e is None:
                continue
            en_gold = e["choices"]["label"].index(e["answerKey"])
            pairs.append({"pair_id": f"arc_challenge:{r['id']}",
                          "en": {"query": f"Question: {e['question']}\nAnswer:", "choices": list(e["choices"]["text"]),
                                 "gold": en_gold},
                          "sl": {"query": r["query"], "choices": list(r["choices"]), "gold": int(r["gold"])}})
    elif task == "boolq":
        en = load_dataset("aps/super_glue", "boolq", split="validation")
        assert len(en) == len(sl), (len(en), len(sl))
        for i, (a, b) in enumerate(zip(sl, en)):
            assert str(a["idx"]) == str(b["idx"]), (a["idx"], b["idx"])
            qs = a["question"].strip().rstrip("?")
            pairs.append({"pair_id": f"boolq:{b['idx']}",
                          "en": {"query": f"{b['passage']}\nQuestion: {b['question']}?\nAnswer:", "choices": ["no", "yes"],
                                 "gold": int(b["label"])},
                          "sl": {"query": f"{a['passage']}\nVprašanje: {qs}?\nOdgovor:", "choices": ["ne", "da"],
                                 "gold": int(a["label"])}})
    elif task == "hellaswag":
        en = load_dataset("Rowan/hellaswag", split="validation")
        assert len(en) == len(sl), (len(en), len(sl))
        for i, (a, b) in enumerate(zip(sl, en)):
            ctx = b["ctx_a"] + " " + b["ctx_b"].capitalize()
            pairs.append({"pair_id": f"hellaswag:{i}",
                          "en": {"query": hs_preprocess(b["activity_label"] + ": " + ctx),
                                 "choices": [hs_preprocess(x) for x in b["endings"]], "gold": int(b["label"])},
                          "sl": {"query": a["query"], "choices": list(a["choices"]), "gold": int(a["gold"])}})
    elif task == "openbookqa":
        en = load_dataset("allenai/openbookqa", "main", split="test")
        assert len(en) == len(sl), (len(en), len(sl))
        for i, (a, b) in enumerate(zip(sl, en)):
            pairs.append({"pair_id": f"openbookqa:{b['id']}",
                          "en": {"query": b["question_stem"], "choices": list(b["choices"]["text"]),
                                 "gold": b["choices"]["label"].index(b["answerKey"])},
                          "sl": {"query": a["query"], "choices": list(a["choices"]), "gold": int(a["gold"])}})
    elif task == "piqa":
        en = load_dataset("baber/piqa", split="validation")
        assert len(en) == len(sl), (len(en), len(sl))
        for i, (a, b) in enumerate(zip(sl, en)):
            pairs.append({"pair_id": f"piqa:{i}",
                          "en": {"query": f"Question: {b['goal']}\nAnswer:", "choices": [b["sol1"], b["sol2"]],
                                 "gold": int(b["label"])},
                          "sl": {"query": f"Vprašanje: {a['goal']}\nOdgovor:", "choices": list(a["choices"]),
                                 "gold": int(a["gold"])}})
    elif task == "winogrande":
        en = load_dataset("allenai/winogrande", "winogrande_xl", split="validation")
        assert len(en) == len(sl), (len(en), len(sl))
        # SL rows are NOT in EN row order: SL id - min(id) is the EN winogrande_xl validation row index
        # (verified: gold agreement 1267/1267 under this mapping vs 0.50 under row order)
        off = min(int(r["id"]) for r in sl)
        n_bad = 0
        for a in sl:
            i = int(a["id"]) - off
            b = en[i]
            pe = wino_partial(b["sentence"], b["option1"], b["option2"])
            ps = wino_partial(a["sentence"], a["option1"], a["option2"])
            if pe is None or ps is None:
                n_bad += 1
                continue
            pairs.append({"pair_id": f"winogrande:{i}",
                          "en": {"query": pe[1], "choices": pe[0], "gold": int(b["answer"]) - 1, "wino_partial": True},
                          "sl": {"query": ps[1], "choices": ps[0], "gold": int(a["answer"]) - 1, "wino_partial": True}})
        info["n_dropped_no_blank_or_empty_continuation"] = n_bad
    else:
        raise ValueError(task)
    agree = sum(int(p["en"]["gold"] == p["sl"]["gold"]) for p in pairs) / max(1, len(pairs))
    ratios = sorted(len(p["sl"]["query"] + "".join(p["sl"]["choices"])) /
                    max(1, len(p["en"]["query"] + "".join(p["en"]["choices"]))) for p in pairs)
    info.update({"n_pairs": len(pairs), "gold_agreement": round(agree, 4),
                 "len_ratio_median": round(ratios[len(ratios) // 2], 3),
                 "len_ratio_p05_p95": [round(ratios[int(0.05 * len(ratios))], 3), round(ratios[int(0.95 * len(ratios))], 3)],
                 "paired": agree >= 0.98})
    return pairs, info


def build_util() -> dict:
    out = {}
    for task in UTIL_TASKS:
        pairs, info = build_pairs(task)
        if info["paired"]:
            # only items whose gold agrees are used (the pair shares one gold label)
            pool = [p for p in pairs if p["en"]["gold"] == p["sl"]["gold"]]
            pool.sort(key=lambda p: sha1_int(f"{SEED}:{task}:{p['pair_id']}"))
            chosen = pool[:N_UTIL + N_RESERVE]
            en_rows = [{"id": p["pair_id"], "pair_id": p["pair_id"], "order": k, "reserve": k >= N_UTIL, **p["en"]}
                       for k, p in enumerate(chosen)]
            sl_rows = [{"id": p["pair_id"], "pair_id": p["pair_id"], "order": k, "reserve": k >= N_UTIL, **p["sl"]}
                       for k, p in enumerate(chosen)]
        else:  # F5: unpaired -> independent seeded samples per language
            logger.warning(f"{task}: gold agreement {info['gold_agreement']} < 0.98 -> UNPAIRED")
            en_rows, sl_rows = [], []
            for lang, rows in (("en", en_rows), ("sl", sl_rows)):
                pool = sorted(pairs, key=lambda p: sha1_int(f"{SEED}:{task}:{lang}:{p['pair_id']}"))
                for k, p in enumerate(pool[:N_UTIL + N_RESERVE]):
                    rows.append({"id": f"{p['pair_id']}:{lang}", "pair_id": None, "order": k, "reserve": k >= N_UTIL, **p[lang]})
        for lang, rows in (("en", en_rows), ("sl", sl_rows)):
            write_jsonl(DATA / "util" / f"{task}_{lang}.jsonl", rows)
        info["n_written"] = len(en_rows)
        info["chance"] = sum(1 / len(r["choices"]) for r in en_rows[:N_UTIL]) / N_UTIL
        for lang, rows in (("en", en_rows), ("sl", sl_rows)):
            for r in rows[:2]:
                logger.info(f"[{task}/{lang}] query={r['query'][-200:]!r} choices={[c[:60] for c in r['choices']]} gold={r['gold']}")
        logger.info(f"{task}: {info}")
        out[task] = info
    return out


def build_belebele() -> dict:
    cfg = {"en": "eng_Latn", "sl": "slv_Latn", "hu": "hun_Latn"}
    ds = {lang: load_dataset("facebook/belebele", c, split="test") for lang, c in cfg.items()}
    keyed = {lang: {(r["link"], str(r["question_number"])): r for r in d} for lang, d in ds.items()}
    common = sorted(set.intersection(*[set(k.keys()) for k in keyed.values()]))
    agree = [k for k in common if len({str(keyed[l][k]["correct_answer_num"]) for l in cfg}) == 1]
    pool = sorted(agree, key=lambda k: sha1_int(f"{SEED}:belebele:{k[0]}:{k[1]}"))[:N_BELE]
    for lang in cfg:
        rows = []
        for k in pool:
            r = keyed[lang][k]
            q = (f"P: {r['flores_passage']}\nQ: {r['question']}\nA: {r['mc_answer1']}\nB: {r['mc_answer2']}\n"
                 f"C: {r['mc_answer3']}\nD: {r['mc_answer4']}\nAnswer:")
            rows.append({"id": f"belebele:{k[0]}#{k[1]}", "pair_id": f"belebele:{k[0]}#{k[1]}", "query": q,
                         "choices": ["A", "B", "C", "D"], "gold": int(r["correct_answer_num"]) - 1})
        write_jsonl(DATA / "belebele" / f"belebele_{lang}.jsonl", rows)
    # 1d fluency passages: unique passages (by link), parallel across languages
    links = sorted({k[0] for k in common}, key=lambda s: sha1_int(f"{SEED}:flores:{s}"))
    # passages used by the Belebele QA items are allowed (BPB is a separate measure); take first 150 by sha1
    flu = links[:N_FLU]
    first_q = {}
    for k in common:
        first_q.setdefault(k[0], k)
    for lang in cfg:
        rows = [{"id": f"flores:{l}", "text": keyed[lang][first_q[l]]["flores_passage"].strip()} for l in flu]
        write_jsonl(DATA / "fluency" / f"passages_{lang}.jsonl", rows)
    return {"n_common": len(common), "n_answer_agree": len(agree), "n_items": len(pool), "n_passages": len(flu),
            "gold_dist": dict(Counter(int(keyed["en"][k]["correct_answer_num"]) for k in pool))}


def ngrams(text: str, n: int = 8) -> set:
    toks = re.findall(r"\w+", text.lower())
    return {" ".join(toks[i:i + n]) for i in range(len(toks) - n + 1)}


def norm(s: str) -> str:
    return " ".join(re.findall(r"\w+", s.lower()))


def build_harmless() -> dict:
    dolly = load_dataset("databricks/databricks-dolly-15k", split="train")
    cats = {"open_qa", "brainstorming", "general_qa", "creative_writing", "classification"}
    cand = [(i, r) for i, r in enumerate(dolly) if r["category"] in cats and not r["context"].strip()
            and 20 <= len(r["instruction"].strip()) <= 300]
    # exclusion corpora: every prompt ever used for selection / earlier harmless sets
    excl_texts = []
    for split in ("train", "test"):
        try:
            excl_texts += [r["text"] for r in load_dataset("mlabonne/harmless_alpaca", split=split)]
        except Exception as e:  # noqa: BLE001
            logger.warning(f"harmless_alpaca {split}: {e!r}")
    try:
        alp = load_dataset("tatsu-lab/alpaca", split="train")
        excl_texts += [(r["instruction"] + " " + r["input"]).strip() for r in alp]
    except Exception as e:  # noqa: BLE001
        logger.warning(f"tatsu-lab/alpaca: {e!r}")
    for f in (ITER2_EXP8 / "data").glob("harmless*.jsonl"):
        for r in read_jsonl(f):
            for k in ("en", "text", "prompt", "input", "sl"):
                if isinstance(r.get(k), str):
                    excl_texts.append(r[k])
    for f in (ITER1_EXP4 / "data" / "splits").glob("*.jsonl"):
        for r in read_jsonl(f):
            for k in ("en", "sl", "text"):
                if isinstance(r.get(k), str):
                    excl_texts.append(r[k])
    excl_exact = {norm(t) for t in excl_texts}
    excl_ng = set()
    for t in excl_texts:
        excl_ng |= ngrams(t)
    logger.info(f"harmless exclusion corpus: {len(excl_texts)} texts, {len(excl_ng)} 8-grams")
    cand.sort(key=lambda x: sha1_int(f"{SEED}:dolly:{x[0]}"))
    kept, dropped = [], Counter()
    seen = set()
    for i, r in cand:
        t = r["instruction"].strip()
        n = norm(t)
        if n in seen:
            dropped["dup"] += 1
            continue
        if n in excl_exact:
            dropped["exact"] += 1
            continue
        g = ngrams(t)
        if g and len(g & excl_ng) / len(g) > 0.5:
            dropped["8gram>50%"] += 1
            continue
        seen.add(n)
        kept.append({"id": f"dolly:{i}", "category": r["category"], "en": t})
        if len(kept) >= N_KL + N_KL_SPARE:
            break
    for k, r in enumerate(kept):
        r["spare"] = k >= N_KL
    write_jsonl(DATA / "harmless" / "dolly_en.jsonl", kept)
    return {"n_candidates": len(cand), "n_kept": len(kept), "dropped": dict(dropped),
            "categories": dict(Counter(r["category"] for r in kept[:N_KL]))}


def overlap_audit() -> dict:
    """1e: zero-overlap check of every item set vs every block of art_EG6OpEkGvysx (RESERVED items never used)."""
    full = json.loads((ITER1_DATASET / "full_data_out.json").read_text())
    dep_ng, dep_exact, per_block = set(), set(), {}
    for b in full["datasets"]:
        per_block[b["dataset"]] = len(b["examples"])
        for ex in b["examples"]:
            t = str(ex.get("input", ""))
            dep_exact.add(norm(t))
            dep_ng |= ngrams(t)
            for k in ("metadata_source_prompt_en",):
                if isinstance(ex.get(k), str):
                    dep_exact.add(norm(ex[k]))
                    dep_ng |= ngrams(ex[k])
    del full
    res = {"dependency_blocks": per_block, "n_dep_8grams": len(dep_ng)}
    files = sorted((DATA / "util").glob("*.jsonl")) + sorted((DATA / "belebele").glob("*.jsonl")) + \
        [DATA / "harmless" / "dolly_en.jsonl"] + sorted((DATA / "fluency").glob("*.jsonl"))
    for f in files:
        rows = read_jsonl(f)
        n_exact = n_ng = 0
        for r in rows:
            t = r.get("en") or r.get("text") or r.get("query", "")
            if norm(t) in dep_exact:
                n_exact += 1
            g = ngrams(t)
            if g and len(g & dep_ng) / len(g) > 0.5:
                n_ng += 1
        res[f.name] = {"n": len(rows), "exact_overlap": n_exact, "8gram_gt50pct_overlap": n_ng}
    sm = ITER1_DATASET / "outputs" / "split_manifest.json"
    res["split_manifest_sha256"] = sha256_file(sm) if sm.exists() else "MISSING"
    res["full_data_out_sha256"] = sha256_file(ITER1_DATASET / "full_data_out.json")
    return res


@logger.catch(reraise=True)
def main() -> None:
    report = {"seed": SEED, "sl_repo": SL_REPO, "sl_revision": SL_REV}
    report["util"] = build_util()
    report["belebele"] = build_belebele()
    logger.info(f"belebele: {report['belebele']}")
    report["harmless"] = build_harmless()
    logger.info(f"harmless: {report['harmless']}")
    report["overlap_audit"] = overlap_audit()
    logger.info(f"overlap audit: {json.dumps(report['overlap_audit'])[:1500]}")
    (DATA / "prep_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    man = {str(p.relative_to(DATA)): sha256_file(p) for p in sorted(DATA.rglob("*.jsonl"))}
    (DATA / "manifest.json").write_text(json.dumps(man, indent=2))
    logger.info(f"wrote {len(man)} data files")


if __name__ == "__main__":
    main()
