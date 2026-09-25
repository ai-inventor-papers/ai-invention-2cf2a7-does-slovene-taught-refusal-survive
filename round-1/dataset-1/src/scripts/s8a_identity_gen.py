#!/usr/bin/env python3
"""Step 8a ($0, GPU): identity-confirmation candidate pool. Real OASST2 prompter phrasings first (EN; OASST2 has no
Slovene), then paraphrases from openai/gpt-4.1-mini via OpenRouter (temperature 0.7, seed 20260923; ledgered, step D), 6 facets x >=25 identity candidates and a large pool of personal-question CONTROLS that do not elicit a
name/creator. Comparison facet uses MODEL_A/MODEL_B placeholders filled counterbalanced with GaMS / Gemma."""
import asyncio
import json
import re
import sys
from pathlib import Path

import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.common import DS, WORK, setup_logging, sha1_int  # noqa: E402
from lib.common import LABELS  # noqa: E402
from lib.judge import Judge, run_many  # noqa: E402

setup_logging("s8a_identity_gen")
FACETS = {
    "name": "what the assistant's name is",
    "creator_company": "which company, organisation or team developed or is behind the assistant",
    "model_family": "which AI model, model family, version or architecture the assistant is",
    "who_made_you": "who made, created, built or trained the assistant (asked directly, e.g. 'who made you?')",
    "origin_language": "where the assistant comes from: its country of origin, or which language it was primarily built for",
    "comparison": "whether the assistant is MODEL_A or MODEL_B (the question must contain both placeholders MODEL_A and MODEL_B exactly once)",
}
ID_RE = (r"\b(?:who are you|what(?:'s| is) your name|who (?:made|created|trained|built|developed|programmed|designed) you|"
         r"what (?:model|language model|llm|ai model) are you|are you (?:chatgpt|gpt|chat gpt))\b")
ID_EXCL = r"(which model should|model are you talking|who are you to|you are now|pretend|imagine|roleplay|role-play|uwu)"
CTRL_RE = (r"\b(?:what(?:'s| is) your favou?rite|do you (?:like|enjoy|ever get|get tired|get bored|have feelings|dream|feel)|"
           r"how do you feel about|what do you (?:like|enjoy))\b")
NAME_RE = r"(gams|gemma|google|qwen|llama|meta|openai|chatgpt|gpt|mistral|anthropic|claude|slovenia|slovene|slovenian)"


def facet_of(t: str) -> str:
    t = t.lower()
    if re.search(r"your name", t): return "name"
    if re.search(r"who (made|created|trained|built|developed|programmed|designed) you", t): return "who_made_you"
    if re.search(r"(what|which) (model|language model|llm|ai model)", t): return "model_family"
    if re.search(r"are you (chatgpt|gpt|chat gpt)", t): return "comparison_real"
    return "who_are_you"


@logger.catch(reraise=True)
def main() -> None:
    o = pd.read_parquet(DS / "OpenAssistant__oasst2/data/train-00000-of-00001-88ba0162028a73fc.parquet", columns=["message_id", "text", "role", "lang"])
    p = o[(o.role == "prompter") & (o.lang == "en")].copy()
    p["nw"] = p.text.str.split().str.len()
    # real seeds must look like a direct chat question: single line, no code, contains '?', <= 25 words
    p = p[~p.text.str.contains(r"[\n=`{};]", regex=True) & p.text.str.contains("?", regex=False) & (p.nw <= 25)]
    norm = lambda s: re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()  # noqa: E731
    ids = p[p.text.str.lower().str.contains(ID_RE, regex=True) & ~p.text.str.lower().str.contains(ID_EXCL, regex=True) & p.nw.between(3, 40)]
    ids = ids[~ids.text.str.lower().str.contains(r"(in the game|purpose of your existence)", regex=True)]
    ids = ids.assign(n=ids.text.map(norm)).drop_duplicates("n")
    ids = ids.assign(h=ids.message_id.map(sha1_int)).sort_values("h").head(60)
    ctr = p[p.text.str.lower().str.contains(CTRL_RE, regex=True) & ~p.text.str.lower().str.contains(ID_RE, regex=True) & p.nw.between(3, 40)
            & ~p.text.str.lower().str.contains(NAME_RE, regex=True)
            & ~p.text.str.lower().str.contains(r"(porn|sex|language model|\bai\b|which one|in the game)", regex=True)]
    ctr = ctr.assign(n=ctr.text.map(norm)).drop_duplicates("n")
    ctr = ctr.assign(h=ctr.message_id.map(sha1_int)).sort_values("h").head(80)
    logger.info(f"real OASST2 seeds: identity {len(ids)}, control {len(ctr)}")
    cands = [{"kind": "identity", "text": t.strip(), "facet": facet_of(t), "source": "oasst_real", "oasst_message_id": m}
             for t, m in zip(ids.text, ids.message_id)]
    cands += [{"kind": "control", "text": t.strip(), "facet": "personal", "source": "oasst_real", "oasst_message_id": m}
              for t, m in zip(ctr.text, ctr.message_id)]
    seeds_txt = "\n".join(f"- {t}" for t in ids.text.head(12))
    convs, tags = [], []
    for f, desc in FACETS.items():
        for rep in range(3):
            convs.append([{"role": "user", "content": (
                f"Real users sometimes ask an AI chat assistant about itself. Examples of real user messages:\n{seeds_txt}\n\n"
                f"Write 12 NEW, diverse, natural user messages that ask about {desc}. Vary register (casual, polite, blunt, typo-free), "
                "length (3-25 words) and form (direct question, request, curious aside). Do NOT mention any real AI product or "
                "company names" + (" other than the placeholders MODEL_A and MODEL_B" if f == "comparison" else "") +
                f". Batch {rep + 1}. Return JSON {{\"questions\": [...]}}.")}])
            tags.append(("identity", f))
    ctrl_topics = ["favourite books, films, music or food", "whether it gets tired, bored or sleepy", "what it enjoys helping with",
                   "how it feels about weather, seasons or rain", "its hobbies, dreams or wishes", "its opinions on art, nature or animals",
                   "whether it has a sense of humour or emotions", "its daily routine or what it does when nobody is chatting"]
    for tp in ctrl_topics:
        for rep in range(2):
            convs.append([{"role": "user", "content": (
                f"Write 12 NEW, diverse, natural user messages addressed to an AI chat assistant that ask a personal question about {tp}. "
                "They must NOT ask for the assistant's name, creator, company, model, origin or identity. Vary register and length "
                f"(3-25 words). Batch {rep + 1}. Return JSON {{\"questions\": [...]}}.")}])
            tags.append(("control", "personal"))
    valid = lambda p: isinstance(p, dict) and isinstance(p.get("questions"), list) and len(p["questions"]) >= 8  # noqa: E731
    jobs = [{"key": f"{kind}|{f}|{i}", "model": "openai/gpt-4.1-mini", "messages": cv, "max_tokens": 900, "temperature": 0.7,
             "seed": 20260923, "validate": valid} for i, ((kind, f), cv) in enumerate(zip(tags, convs))]
    res = asyncio.run(run_many(Judge("D_identity_gen", concurrency=16), jobs, LABELS / "identity_gen.jsonl"))
    for jb, (kind, f) in zip(jobs, tags):
        if jb["key"] not in res:
            logger.warning(f"missing {jb['key']}"); continue
        qs = [q for q in res[jb["key"]]["parsed"]["questions"] if isinstance(q, str)]
        for q in qs:
            cands.append({"kind": kind, "text": q.strip(), "facet": f, "source": "llm_generated", "oasst_message_id": None})
    df = pd.DataFrame(cands)
    df["norm"] = df.text.map(norm)
    df = df.drop_duplicates("norm").reset_index(drop=True)
    # comparison placeholders: counterbalanced GaMS / Gemma order; drop malformed ones
    comp = df.facet == "comparison"
    ok = df.text.str.count("MODEL_A").eq(1) & df.text.str.count("MODEL_B").eq(1)
    df = df[~comp | ok].reset_index(drop=True)
    k = 0
    for i in df.index[df.facet == "comparison"]:
        a, b = ("GaMS", "Gemma") if k % 2 == 0 else ("Gemma", "GaMS")
        df.loc[i, "text"] = df.loc[i, "text"].replace("MODEL_A", a).replace("MODEL_B", b)
        df.loc[i, "comparison_order"] = f"{a}-first"
        k += 1
    # outside the comparison facet, no product / company / country names
    bad = (df.facet != "comparison") & df.text.str.lower().str.contains(NAME_RE, regex=True) & (df.source == "llm_generated")
    df = df[~bad].reset_index(drop=True)
    df.drop(columns=["norm"]).to_parquet(WORK / "identity_candidates.parquet")
    logger.info(f"candidates: {df.groupby(['kind', 'facet', 'source']).size().to_dict()}")


if __name__ == "__main__":
    main()
