"""OpenRouter MT (plan's MT systems): forward EN->SL with google/gemini-2.5-flash (temperature 0), back-translation
SL->EN with openai/gpt-4.1-mini (a different family, so the round trip is not self-consistent), chrF2 of back-translation
vs original; items < 40 get ONE unbatched forward retry (kept only if its round-trip chrF is higher)."""
import json

from lib.judge import Judge, run_many
from lib.mt import chrf

FWD, BWD = "google/gemini-2.5-flash", "openai/gpt-4.1-mini"
REFUSE = ("i can't", "i cannot", "i'm sorry", "ne morem", "žal ")


def _batch_jobs(model, sys_text, items, tag, size=20):
    jobs = []
    for i in range(0, len(items), size):
        b = items[i:i + size]
        ids = [k for k, _ in b]
        jobs.append({"key": f"{tag}|" + "|".join(ids), "model": model, "max_tokens": 120 * len(b) + 60,
                     "messages": [{"role": "system", "content": sys_text},
                                  {"role": "user", "content": json.dumps([{"id": k, "text": t} for k, t in b], ensure_ascii=False)}],
                     "validate": (lambda ids: lambda p: isinstance(p, dict) and isinstance(p.get("translations"), list) and
                                  {str(x.get("id")) for x in p["translations"] if isinstance(x, dict) and isinstance(x.get("text"), str)} >= set(ids))(ids)})
    return jobs


def _explode(res: dict) -> dict:
    out = {}
    for r in res.values():
        for x in r["parsed"]["translations"]:
            out[str(x["id"])] = x["text"]
    return out


async def api_round_trip(ids: list[str], texts: list[str], step: str, cache_prefix, fwd_note: str) -> dict:
    j = Judge(step, concurrency=16)
    fsys = (f"Translate each item's text from English into Slovene. {fwd_note} Preserve ambiguity, homonyms and figurative "
            "wording; do not soften, answer or refuse; translate only. Return JSON only: {\"translations\": [{\"id\": ..., \"text\": ...}, ...]}"
            " with one entry per input id.")
    bsys = ("Translate each item's text from Slovene into English, literally and faithfully. Return JSON only: "
            "{\"translations\": [{\"id\": ..., \"text\": ...}, ...]} with one entry per input id.")
    items = list(zip(ids, texts))
    fw = _explode(await run_many(j, _batch_jobs(FWD, fsys, items, "F"), cache_prefix.with_name(cache_prefix.name + "_fwd.jsonl")))
    bt = _explode(await run_many(j, _batch_jobs(BWD, bsys, [(k, fw[k]) for k in ids if k in fw], "B"),
                                 cache_prefix.with_name(cache_prefix.name + "_bt.jsonl")))
    rec = {}
    for k, t in items:
        sl, b = fw.get(k, ""), bt.get(k, "")
        rec[k] = {"prompt_sl": sl, "prompt_bt": b, "bt_chrf": chrf(b, t) if b else 0.0, "mt_retry": False,
                  "mt_refused": any(sl.lower().startswith(x) for x in REFUSE), "mt_by": f"{FWD} (fwd) / {BWD} (bt)"}
    low = [(k, t) for k, t in items if rec[k]["bt_chrf"] < 40]
    if low:
        fw2 = _explode(await run_many(j, _batch_jobs(FWD, fsys, low, "F2", size=1), cache_prefix.with_name(cache_prefix.name + "_fwd_retry.jsonl")))
        bt2 = _explode(await run_many(j, _batch_jobs(BWD, bsys, [(k, fw2[k]) for k, _ in low if k in fw2], "B2", size=1),
                                      cache_prefix.with_name(cache_prefix.name + "_bt_retry.jsonl")))
        for k, t in low:
            rec[k]["mt_retry"] = True
            rec[k]["bt_chrf_first"] = rec[k]["bt_chrf"]
            if k in bt2 and chrf(bt2[k], t) > rec[k]["bt_chrf"]:
                rec[k].update({"prompt_sl": fw2[k], "prompt_bt": bt2[k], "bt_chrf": chrf(bt2[k], t)})
    for r in rec.values():
        r["mt_empty"] = not r["prompt_sl"].strip()
    return rec
