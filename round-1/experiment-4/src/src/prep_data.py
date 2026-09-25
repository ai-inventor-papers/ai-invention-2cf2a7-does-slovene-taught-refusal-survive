#!/usr/bin/env python3
# NOTE (published copy): this file names server paths this repository
# does not publish (a stage it does not ship, or another run's workspace),
# so the steps that read them will not run from a clone as written:
#   /ai-inventor/aii_data/runs/run_FVi3e3O9CH5I/iter_3/gen_hypo/claude_agent/stage0b/refuseu_overlap.json
"""S0 DATA: RefusEU pairs + SCREEN-SPEC v1 splits, KL sets, harmless set (+SL MT), pair-correspondence grades.

NEVER loads the RefusEU 'evaluation' config (reserved confirmation split).
"""
from __future__ import annotations

import ast
import asyncio
import json
import random
import re
from collections import Counter, defaultdict

from datasets import load_dataset

from common import (DATA, HIGH_EN_CATS, LOW_EN_CATS, SEED, SPLITS, setup_logger, sha1_int, write_jsonl, read_jsonl)
from openrouter import ledger_key, run_batch

logger = setup_logger("prep_data")
OVERLAP_JSON = "/ai-inventor/aii_data/runs/run_FVi3e3O9CH5I/iter_3/gen_hypo/claude_agent/stage0b/refuseu_overlap.json"


def first_user(chosen) -> str:
    conv = ast.literal_eval(chosen) if isinstance(chosen, str) else chosen
    for m in conv:
        if m["role"] == "user":
            return m["content"].strip()
    raise ValueError("no user turn")


def build_refuseu() -> dict:
    """Pair EN<->SL by ROW INDEX within split (row_id is NOT unique: 279 row_ids occur twice with
    different categories). Asserted: category and row_id sequences identical across languages.
    pair_id = '{split}:{row_id}' for the last occurrence of a row_id (== sibling artifacts' dict-overwrite
    convention), '{split}:{row_id}:dup' for the earlier duplicate occurrence."""
    ds = {lang: load_dataset("NASK-PIB/RefusEU", f"lang_{lang}") for lang in ("en", "sl")}  # train+test only
    pairs = []
    n_dup = 0
    for split in ("train", "test"):
        e, s = ds["en"][split], ds["sl"][split]
        assert e["category"] == s["category"], "category sequences differ"
        assert e["row_id"] == s["row_id"], "row_id sequences differ"
        rids = e["row_id"]
        last = {r: i for i, r in enumerate(rids)}
        for i in range(len(e)):
            rid = rids[i]
            pid = f"{split}:{rid}" if last[rid] == i else f"{split}:{rid}:dup"
            n_dup += int(last[rid] != i)
            cat = e[i]["category"]
            dg = "low" if cat in LOW_EN_CATS else ("high" if cat in HIGH_EN_CATS else "mid")
            h = sha1_int(pid) % 4
            pairs.append({"pair_id": pid, "row_id": rid, "split": split, "category": cat, "dose_group": dg,
                          "role": "CONSTRUCT" if h == 0 else "SCORE", "sha1": format(sha1_int(pid), "040x"),
                          "en": first_user(e[i]["chosen"]), "sl": first_user(s[i]["chosen"])})
    assert len({p["pair_id"] for p in pairs}) == len(pairs)
    logger.info(f"paired by index: {len(pairs)} pairs ({n_dup} earlier-duplicate row_ids -> ':dup')")
    return {"pairs": pairs, "n_en": len(pairs), "n_sl": len(pairs), "n_dup": n_dup}


def score400(score: list[dict]) -> list[dict]:
    bycat = defaultdict(list)
    for p in score:
        bycat[p["category"]].append(p)
    for c in bycat:
        bycat[c].sort(key=lambda p: p["sha1"])
    chosen = []
    for c in LOW_EN_CATS:
        chosen += bycat.get(c, [])[:45]
    others = sorted(c for c in bycat if c not in LOW_EN_CATS)
    idx = {c: 0 for c in others}
    while len(chosen) < 400:
        progressed = False
        for c in others:
            if len(chosen) >= 400:
                break
            if idx[c] < len(bycat[c]):
                chosen.append(bycat[c][idx[c]])
                idx[c] += 1
                progressed = True
        if not progressed:
            break
    return chosen


def trial_probe(s400: list[dict]) -> list[dict]:
    low = sorted([p for p in s400 if p["dose_group"] == "low"], key=lambda p: p["sha1"])
    rest = sorted([p for p in s400 if p["dose_group"] != "low"], key=lambda p: p["sha1"])
    n_low = round(100 * len(low) / len(s400))
    return sorted(low[:n_low] + rest[:100 - n_low], key=lambda p: p["sha1"])


def build_kl_sets() -> dict:
    sl_arc = load_dataset("cjvt/slovenian-llm-eval", "arc_challenge", split="test")
    en_arc = load_dataset("allenai/ai2_arc", "ARC-Challenge", split="test")
    en_by_id = {r["id"]: r for r in en_arc}
    arc = []
    for r in sl_arc:
        if r["id"] in en_by_id:
            q = re.sub(r"^Vprašanje:\s*", "", r["query"]).replace("\nodgovor:", "").strip()
            arc.append({"pair_id": f"arc:{r['id']}", "task": "arc", "en": en_by_id[r["id"]]["question"].strip(), "sl": q})
    sl_hs = load_dataset("cjvt/slovenian-llm-eval", "hellaswag", split="test")
    en_hs = load_dataset("Rowan/hellaswag", split="validation")
    assert len(sl_hs) == len(en_hs), (len(sl_hs), len(en_hs))
    gold_agree = sum(int(str(a["gold"]) == str(b["label"])) for a, b in zip(sl_hs, en_hs)) / len(en_hs)
    logger.info(f"HellaSwag row-order alignment: gold==label agreement {gold_agree:.4f}")
    hs = []
    for i, (a, b) in enumerate(zip(sl_hs, en_hs)):
        hs.append({"pair_id": f"hs:{i}", "task": "hs", "en": f"{b['activity_label']}: {b['ctx']}".strip(), "sl": a["query"].strip()})
    # verification of 20 random matches per task
    rng = random.Random(SEED)
    checks = []
    for name, lst in (("arc", arc), ("hs", hs)):
        for p in rng.sample(lst, 20):
            ratio = len(p["sl"]) / max(1, len(p["en"]))
            nums_en = set(re.findall(r"\d+", p["en"]))
            nums_sl = set(re.findall(r"\d+", p["sl"]))
            checks.append({"task": name, "pair_id": p["pair_id"], "len_ratio": round(ratio, 2),
                           "len_ok": 0.6 <= ratio <= 1.8, "nums_ok": nums_en == nums_sl, "en": p["en"][:120], "sl": p["sl"][:120]})
    ok = sum(c["len_ok"] and c["nums_ok"] for c in checks)
    logger.info(f"KL pairing check: {ok}/40 pass length+number test")
    arc.sort(key=lambda p: sha1_int(p["pair_id"]))
    hs.sort(key=lambda p: sha1_int(p["pair_id"]))
    pool = arc[:200] + hs[:200]
    sel = [p for p in pool if sha1_int(p["pair_id"]) % 2 == 0]
    ev = [p for p in pool if sha1_int(p["pair_id"]) % 2 == 1]
    sel_kl, eval_kl = sel[:100], ev[:100]
    spare = sel[100:] + ev[100:] + arc[200:260] + hs[200:260]
    return {"sel": sel_kl, "eval": eval_kl, "spare": spare, "checks": checks, "hs_gold_agree": gold_agree,
            "n_arc_paired": len(arc)}


def build_harmless() -> list[dict]:
    ds = load_dataset("mlabonne/harmless_alpaca", split="train[400:600]")
    return [{"idx": 400 + i, "en": r["text"].strip()} for i, r in enumerate(ds)]


async def translate_harmless(items: list[dict]) -> list[dict]:
    # v2: v1 ('Translate to Slovene, output only the translation.' as system turn) made the MT model EXECUTE the
    # alpaca instructions instead of translating them; v2 quotes the text and forbids execution.
    jobs = [{"key": ledger_key("mt_harmless_sl_v2", it["idx"]),
             "messages": [{"role": "user", "content": "Translate the following English text into Slovene. It is an "
                           "instruction or question: translate it, do NOT answer or carry it out. Output only the "
                           "Slovene translation.\n\nTEXT:\n" + it["en"]}], "meta": {"task": "mt_harmless_v2", "idx": it["idx"]}}
            for it in items]
    res = await run_batch(jobs, max_tokens=400, logger=logger)
    out = []
    for it, j in zip(items, jobs):
        if j["key"] in res and res[j["key"]].strip():
            out.append({**it, "sl": res[j["key"]].strip()})
    return out


GRADE_PROMPT = """You compare two prompts from a parallel English/Slovene safety dataset.
EN: {en}
SL: {sl}
Classify their correspondence:
T = the Slovene is a translation of the English (same request, same details),
R = same underlying request but noticeably different wording/details,
U = different requests.
Answer with a single letter: T, R or U."""


async def grade_pairs(pairs: list[dict]) -> list[dict]:
    jobs = [{"key": ledger_key("pairgrade", p["pair_id"]),
             "messages": [{"role": "user", "content": GRADE_PROMPT.format(en=p["en"], sl=p["sl"])}],
             "meta": {"task": "pairgrade", "pair_id": p["pair_id"]}} for p in pairs]
    res = await run_batch(jobs, max_tokens=5, logger=logger)
    out = []
    for p, j in zip(pairs, jobs):
        c = res.get(j["key"], "").strip().upper()
        g = next((ch for ch in c if ch in "TRU"), None)
        out.append({"pair_id": p["pair_id"], "grade": g, "raw": c[:20]})
    return out


def shingles(text: str, n: int = 8) -> list[str]:
    toks = text.lower().split()
    return [" ".join(toks[i:i + n]) for i in range(max(0, len(toks) - n + 1))]


@logger.catch(reraise=True)
def main():
    r = build_refuseu()
    pairs = r["pairs"]
    cnt = Counter(p["role"] for p in pairs)
    logger.info(f"roles: {dict(cnt)}")
    cats = Counter(p["category"] for p in pairs)
    absent = [f"S{i}" for i in range(1, 15) if f"S{i}" not in cats]
    logger.info(f"categories present: {dict(sorted(cats.items()))}; absent: {absent}")
    construct = [p for p in pairs if p["role"] == "CONSTRUCT"]
    score = [p for p in pairs if p["role"] == "SCORE"]
    s400 = score400(score)
    probe = trial_probe(s400)
    logger.info(f"SCORE-400 per cat: {dict(sorted(Counter(p['category'] for p in s400).items()))}")
    logger.info(f"TRIAL-PROBE dose groups: {dict(Counter(p['dose_group'] for p in probe))}")
    write_jsonl(SPLITS / "construct.jsonl", construct)
    write_jsonl(SPLITS / "score.jsonl", score)
    write_jsonl(SPLITS / "score400.jsonl", s400)
    write_jsonl(SPLITS / "trial_probe.jsonl", probe)
    sh = [{"pair_id": p["pair_id"], "lang": lang, "shingles": shingles(p[lang])} for p in pairs for lang in ("en", "sl")]
    write_jsonl(DATA / "shingles.jsonl", sh)
    overlap = json.loads(open(OVERLAP_JSON).read())

    kl = build_kl_sets()
    write_jsonl(SPLITS / "sel_kl.jsonl", kl["sel"])
    write_jsonl(SPLITS / "eval_kl.jsonl", kl["eval"])
    write_jsonl(SPLITS / "kl_spare.jsonl", kl["spare"])
    write_jsonl(DATA / "kl_pair_checks.jsonl", kl["checks"])
    logger.info(f"SEL-KL {len(kl['sel'])}, EVAL-KL {len(kl['eval'])}, SPARE {len(kl['spare'])}")

    harmless = build_harmless()
    mt_path = DATA / "harmless_sl_mt.jsonl"
    harmless_mt = asyncio.run(translate_harmless(harmless))
    write_jsonl(mt_path, harmless_mt)
    logger.info(f"harmless EN 200, SL-MT {len(harmless_mt)}")

    rng = random.Random(SEED)
    probe_ids = {p["pair_id"] for p in probe}
    extra = rng.sample([p for p in s400 if p["pair_id"] not in probe_ids], 100)
    grades = asyncio.run(grade_pairs(probe + extra))
    for g in grades:
        g["set"] = "trial_probe" if g["pair_id"] in probe_ids else "score400_random"
    write_jsonl(DATA / "pair_grades.jsonl", grades)
    logger.info(f"pair grades: {dict(Counter(g['grade'] for g in grades))}")

    manifest = {"refuseu_rows_per_lang": {"en": r["n_en"], "sl": r["n_sl"]}, "n_dup_row_ids": r["n_dup"], "pairing": "by row index within split; row_id not unique", "n_pairs": len(pairs), "roles": dict(cnt),
                "categories": dict(sorted(cats.items())), "absent_categories": absent,
                "score400_per_cat": dict(sorted(Counter(p["category"] for p in s400).items())),
                "trial_probe_dose": dict(Counter(p["dose_group"] for p in probe)),
                "overlap_decision": {"source": OVERLAP_JSON, "content": overlap,
                                     "decision": "drop nothing: file holds counts only (<=9 items/lang of ~2,889); shingles written to data/shingles.jsonl for eval-side dedup next iteration"},
                "kl": {"n_arc_paired": kl["n_arc_paired"], "hs_gold_label_agreement": kl["hs_gold_agree"],
                       "pair_checks_pass": sum(c["len_ok"] and c["nums_ok"] for c in kl["checks"]),
                       "pair_checks_len_pass": sum(c["len_ok"] for c in kl["checks"])},
                "harmless": {"source": "mlabonne/harmless_alpaca train[400:600]", "n_en": len(harmless), "n_sl_mt": len(harmless_mt),
                             "mt_model": "google/gemini-2.5-flash"},
                "pair_grades": dict(Counter(g["grade"] for g in grades)),
                "reserved_split_touched": False}
    (DATA / "data_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    logger.info("data prep done")


if __name__ == "__main__":
    main()
