#!/usr/bin/env python3
"""STEP 5.3 (V5): judge-language check. Translate FINAL SL responses to English with facebook/nllb-200-distilled-1.3B
(fp16, sentence by sentence), re-judge them with the PRIMARY judge (under deviation D5 the local Qwen3-14B, same frozen
prompt; request = the EN back-translation arm text of the same item), and report agreement and the refusal-rate shift
SL-judged vs EN-judged per model. Sets: RefusEU SL_MT (as planned) + HARD SL_MT (added: the SDT instrument is where
judge-language asymmetry would bias F and H), 100 responses per model per set, stratified by the primary label.
(The planned gemini re-judge was impossible: the run's OpenRouter budget was exhausted.) FINAL-guarded.
Usage: python judge_lang_check.py
"""
from __future__ import annotations

import asyncio
import json
import os
import random
from collections import defaultdict

os.environ.setdefault("HF_HUB_OFFLINE", "0")
os.environ.pop("TRANSFORMERS_CACHE", None)

from loguru import logger

from common import RESULTS, SEED, guard_final, read_jsonl, setup_logging
import prompts as P
import stats_lib as S

NLLB = "facebook/nllb-200-distilled-1.3B"


def select() -> list[dict]:
    items = read_jsonl(RESULTS / "items_final.jsonl")
    bt = {(r["set"], r["item_id"]): r["prompt_text"] for r in items if r["arm"] == "EN_BT"}
    rng = random.Random(SEED)
    out = []
    for st in ("refuseu_x", "hard"):
        rows = [r for r in items if r["set"] == st and r["arm"] == "SL_MT"
                and r["judge_primary"] in ("REFUSE", "PARTIAL", "COMPLY")]
        for mk in ("gemma_it", "gams3_it"):
            by = defaultdict(list)
            for r in rows:
                if r["model"] == mk:
                    by[r["judge_primary"]].append(r)
            n_tot = sum(len(v) for v in by.values())
            quota = {k: max(min(15, len(v)), round(100 * len(v) / n_tot)) for k, v in by.items()}
            while sum(quota.values()) > 100:
                kmax = max(quota, key=quota.get)
                quota[kmax] -= 1
            for k in sorted(by):
                for r in rng.sample(by[k], min(quota[k], len(by[k]))):
                    out.append({**r, "req_en": bt.get((st, r["item_id"]), "")})
    return out


def _segments(text: str) -> list[str]:
    """NLLB is sentence-level: split on line breaks and sentence ends, keep list markers attached."""
    import re
    segs = []
    for line in text.split("\n"):
        line = line.strip()
        if line:
            segs += [x for x in re.split(r"(?<=[.!?:])\s+", line) if x.strip()]
    return segs or [text]


def translate(texts: list[str]) -> list[str]:
    """Sentence-by-sentence SL->EN with NLLB-200-distilled-1.3B (fp16, beam 2); segments rejoined per response."""
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(NLLB, src_lang="slv_Latn")
    model = AutoModelForSeq2SeqLM.from_pretrained(NLLB, dtype=torch.float16).cuda().eval()
    seg_lists = [_segments(t) for t in texts]
    flat = [x for sl in seg_lists for x in sl]
    order = sorted(range(len(flat)), key=lambda i: len(flat[i]))
    tr: list[str] = [""] * len(flat)
    for i in range(0, len(order), 48):
        idx = order[i:i + 48]
        enc = tok([flat[j] for j in idx], return_tensors="pt", padding=True, truncation=True,
                  max_length=256).to("cuda")
        with torch.inference_mode():
            gen = model.generate(**enc, forced_bos_token_id=tok.convert_tokens_to_ids("eng_Latn"),
                                 max_new_tokens=256, num_beams=2)
        for j, o in zip(idx, tok.batch_decode(gen, skip_special_tokens=True)):
            tr[j] = o
    out, p = [], 0
    for sl in seg_lists:
        out.append(" ".join(tr[p:p + len(sl)]))
        p += len(sl)
    logger.info(f"translated {len(texts)} responses ({len(flat)} segments)")
    del model
    torch.cuda.empty_cache()
    return out


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("judge_lang_check")
    guard_final("judge_lang_check")
    sel = select()
    logger.info(f"selected {len(sel)} SL responses")
    cache = RESULTS / "judge_lang_check_translations.jsonl"
    tr = {r["key"]: r["resp_en"] for r in read_jsonl(cache)} if cache.exists() else {}
    todo = [r for r in sel if r["key"] not in tr]
    if todo:
        en = translate([r["response"] for r in todo])
        tr.update({r["key"]: e for r, e in zip(todo, en)})
        cache.write_text("".join(json.dumps({"key": k, "resp_en": v}, ensure_ascii=False) + "\n" for k, v in tr.items()))
    import judge_local as JL
    m, tok = JL.load()
    cand = JL.first_tokens(tok, P.LABELS)
    texts = [JL.render(tok, P.JUDGE_SYSTEM_V1, P.JUDGE_USER_V1.format(req=r["req_en"], resp=tr[r["key"]])) for r in sel]
    lps = JL.label_logits(m, tok, texts, cand, 8)
    en_lab = {r["key"]: P.LABELS[max(range(3), key=lambda k: lp[k])] for r, lp in zip(sel, lps)}
    (RESULTS / "judge_lang_check_labels.jsonl").write_text("".join(
        json.dumps({"key": r["key"], "set": r["set"], "model": r["model"], "label_SL_judged": r["judge_primary"],
                    "label_EN_judged": en_lab[r["key"]], "resp_en": tr[r["key"]][:400]}, ensure_ascii=False) + "\n"
        for r in sel))
    res = {"judge": "Qwen/Qwen3-14B local (primary under D5)", "translator": NLLB + " sentence-level, beam 2"}
    for st in ("refuseu_x", "hard"):
        for mk in ("gemma_it", "gams3_it"):
            pairs = [(r["judge_primary"], en_lab[r["key"]]) for r in sel if r["model"] == mk and r["set"] == st]
            n = len(pairs)
            d = {"n": n, "agree_3way": sum(a == b for a, b in pairs) / max(n, 1),
                 "agree_binary": sum((a == "REFUSE") == (b == "REFUSE") for a, b in pairs) / max(n, 1),
                 "kappa_binary": S.cohen_kappa([a == "REFUSE" for a, _ in pairs], [b == "REFUSE" for _, b in pairs]),
                 "refusal_rate_SL_judged": sum(a == "REFUSE" for a, _ in pairs) / max(n, 1),
                 "refusal_rate_EN_judged": sum(b == "REFUSE" for _, b in pairs) / max(n, 1),
                 "note": "stratified sample (minority labels over-sampled) -> rates are NOT population rates; "
                         "the SL-vs-EN shift is the quantity of interest"}
            d["shift_EN_minus_SL"] = d["refusal_rate_EN_judged"] - d["refusal_rate_SL_judged"]
            res[f"{st}|{mk}"] = d
        res[f"{st}|did_of_shift_gams_minus_gemma"] = (res[f"{st}|gams3_it"]["shift_EN_minus_SL"]
                                                      - res[f"{st}|gemma_it"]["shift_EN_minus_SL"])
    (RESULTS / "judge_lang_check.json").write_text(json.dumps(res, indent=1))
    logger.info(json.dumps(res))


if __name__ == "__main__":
    main()
