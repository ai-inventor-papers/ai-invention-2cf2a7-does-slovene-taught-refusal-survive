#!/usr/bin/env python3
"""AM2 substitute for the paid TTJ judge: exp9's archived J1 (mdeberta-v3 distilled from 12,639 REAL gemini-2.5-flash P1
labels, kappa_R 0.84 vs gemini) applied to (a) the NLLB English translations of SL responses and (b) the EN_BT responses,
each paired with the ENGLISH source request, so the judge's input language is English in EVERY cell. The SAME J1 is also
applied to the ORIGINAL-language rows of the same frame (direct arm) so R-JUDGE contrasts one instrument with itself.
Writes work/ttj_j1_labels.jsonl {key, kind: ttj|direct|rt, label}.

The model is exp9's byte-identical checkpoint, loaded read-only from that artifact's workspace (reassembled into this
workspace's work/j1_model/ so nothing outside is written).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from loguru import logger

from common import E9, SEED, WORK, setup_logger

LAB = ["REFUSE", "PARTIAL", "COMPLY"]  # exp9 src/judge_distill.py LAB order
MAXLEN = 256
OUT = WORK / "ttj_j1_labels.jsonl"
MDIR = WORK / "j1_model"


def ensure_model() -> Path:
    src = E9 / "judge_model/mdeberta_gemini_distill"
    MDIR.mkdir(exist_ok=True)
    for f in ("config.json", "tokenizer.json", "tokenizer_config.json"):
        if not (MDIR / f).exists():
            shutil.copy(src / f, MDIR / f)
    # transformers 4.57 expects extra_special_tokens to be a dict; exp9 saved it as a [] with an older version.
    # Only this local COPY is normalised; the exp9 checkpoint and its weights are untouched.
    tc = MDIR / "tokenizer_config.json"
    cfg = json.loads(tc.read_text())
    if isinstance(cfg.get("extra_special_tokens"), list):
        cfg["extra_special_tokens"] = {}
        tc.write_text(json.dumps(cfg, indent=1))
        logger.info("normalised extra_special_tokens [] -> {} in the local tokenizer_config copy")
    dst = MDIR / "model.safetensors"
    if not dst.exists():
        man = json.loads((src / "model_parts/manifest.json").read_text())
        with dst.open("wb") as out:
            for name in man["parts"]:
                out.write((src / "model_parts" / name).read_bytes())
        import hashlib
        h = hashlib.sha256()
        with dst.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest() != man["sha256"]:
            dst.unlink()
            raise RuntimeError("reassembled J1 checkpoint sha256 mismatch")
        logger.info(f"J1 checkpoint reassembled, sha256 {h.hexdigest()[:16]}… matches exp9 manifest")
    return MDIR


@torch.inference_mode()
def predict(resp: list[str], req: list[str], bs: int = 64) -> list[str]:
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(str(MDIR))
    model = AutoModelForSequenceClassification.from_pretrained(str(MDIR), num_labels=3, dtype=torch.float32).cuda().eval()
    out = []
    for i in range(0, len(resp), bs):
        enc = tok(resp[i:i + bs], req[i:i + bs], truncation="only_second", max_length=MAXLEN, padding=True,
                  return_tensors="pt").to("cuda")
        out += [LAB[int(j)] for j in model(**enc).logits.argmax(1).cpu()]
        if (i // bs) % 20 == 0:
            logger.info(f"J1 {i + bs}/{len(resp)}")
    del model
    torch.cuda.empty_cache()
    return out


def main():
    setup_logger("ttj_j1")
    ensure_model()
    df = pd.read_parquet(WORK / "frame.parquet")
    tr = {}
    for line in (WORK / "ttj_translations.jsonl").read_text().splitlines():
        r = json.loads(line)
        tr[(r["key"], r["kind"])] = r["text_en"]
    import label_passes as lp
    rows = lp.ttj_rows(df)
    jobs = []  # (key, kind, response_text_for_judge, english_request)
    for r in rows.itertuples():
        jobs.append((r.key, "direct", r.response, r.request))  # judge sees the row as generated (SL request for SL rows)
        if r.lang == "en":
            jobs.append((r.key, "ttj", r.response, r.request_en))
        elif (r.key, "ttj") in tr:
            jobs.append((r.key, "ttj", tr[(r.key, "ttj")], r.request_en))
    kk = df.set_index("key")
    for (k, kind), t in tr.items():
        if kind == "rt" and k in kk.index:
            jobs.append((k, "rt", t, kk.loc[k, "request_en"]))
    logger.info(f"J1 jobs {len(jobs)} ({sum(1 for j in jobs if j[1] == 'ttj')} ttj, {sum(1 for j in jobs if j[1] == 'rt')} round-trip)")
    labs = predict([j[2] or "" for j in jobs], [j[3] or "" for j in jobs])
    with OUT.open("w") as f:
        for j, l in zip(jobs, labs):
            f.write(json.dumps({"key": j[0], "kind": j[1], "label": l, "judge": "exp9_J1_mdeberta_gemini_distill"}) + "\n")
    logger.info(f"wrote {len(labs)} J1 labels to {OUT}")


if __name__ == "__main__":
    main()
