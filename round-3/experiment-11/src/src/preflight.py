#!/usr/bin/env python3
"""S0 PREFLIGHT: dependency existence + hashes, OpenRouter relay probe (status only, never the key), L3 verification
against the GaMS3 model card (pinned revision), public checkpoint pins, sibling iter-3 adapter search."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import requests

from common import DS_DIR, E4, E5, E8, EV1, MODELS, RESULTS, SIBLING_ITER3, sha256_file


def main() -> None:
    paths = [DS_DIR / "full_data_out.json", DS_DIR / "outputs/split_manifest.json", E5 / "data/refuseu_x.jsonl",
             E5 / "data/hard.jsonl", E5 / "data/identity.jsonl", E5 / "outputs/final/gen_gemma_it.jsonl",
             E5 / "outputs/final/gen_gams3_it.jsonl", E5 / "outputs/final/labels_refusal.jsonl",
             E5 / "results/analysis_final.json", E8 / "results/items_final.jsonl", E8 / "data/probe_P200.jsonl",
             E4 / "results/gemma_it/selected_adapter/adapter_model.safetensors",
             E4 / "results/gams3_it/selected_adapter/adapter_model.safetensors",
             EV1 / "labels/harmonised_P1.jsonl.gz"]
    pre = {"utc": datetime.now(timezone.utc).isoformat(), "paths": {}}
    for p in paths:
        e = p.exists()
        pre["paths"][str(p)] = {"exists": e, "bytes": p.stat().st_size if e else None,
                                "sha256": sha256_file(p) if e and p.stat().st_size < 3e8 else None}
    # relay probe (status only)
    url = os.environ["OPENROUTER_BASE_URL"].rstrip("/") + "/chat/completions"
    probe = {}
    for m in ("google/gemini-2.5-flash", "openai/gpt-4.1-mini"):
        pl = {"model": m, "messages": [{"role": "user", "content": "Reply OK"}], "max_tokens": 3, "temperature": 0}
        try:
            r = requests.post(url, headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"}, json=pl,
                              timeout=60)
            body = r.text[:400]
            code = None
            try:
                code = r.json().get("error", {}).get("code")
            except ValueError:
                pass
            probe[m] = {"http": r.status_code, "error_code": code, "body_head": body if r.status_code != 200 else "ok"}
        except requests.RequestException as ex:
            probe[m] = {"http": None, "error": str(ex)[:200]}
    pre["openrouter_probe"] = probe
    pre["judge_mode"] = "paid" if all(v.get("http") == 200 for v in probe.values()) else "local"
    # sibling iter-3 selected adapter
    sib = [str(p) for p in SIBLING_ITER3.glob("*/results/*/selected_adapter*/adapter_config.json")]
    sib += [str(p) for p in SIBLING_ITER3.glob("*/selected/**/adapter_config.json")]
    pre["sibling_selected_adapters"] = sib
    pre["edit_source"] = "iter1_exp4_selected_adapter" if not sib else "CHECK"
    pre["gpu"] = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                                capture_output=True, text=True).stdout.strip()
    pre["disk_free_gb"] = round(shutil.disk_usage(RESULTS).free / 1e9, 1)
    pre["public_checkpoints"] = {k: {"repo": v["repo"], "revision": v["revision"],
                                     "local_dir_exists": (RESULTS.parent / v["local_dir"]).exists()}
                                 for k, v in MODELS.items() if v["kind"] == "public"}
    for k, v in MODELS.items():
        if v["kind"] == "public":
            d = RESULTS.parent / v["local_dir"]
            cfg = json.loads((d / "config.json").read_text())
            st = sorted(d.glob("*.safetensors"))
            pre["public_checkpoints"][k].update({"architectures": cfg.get("architectures"),
                                                 "torch_dtype": cfg.get("torch_dtype") or cfg.get("dtype"),
                                                 "safetensors_gb": round(sum(p.stat().st_size for p in st) / 1e9, 1)})
            tpl = None
            for f in ("chat_template.jinja", "chat_template.json", "tokenizer_config.json"):
                if (d / f).exists():
                    txt = (d / f).read_text()
                    tpl = txt if f.endswith("jinja") else (json.loads(txt).get("chat_template"))
                    if tpl:
                        break
            pre["public_checkpoints"][k]["own_chat_template_sha1"] = \
                __import__("hashlib").sha1((tpl or "").encode()).hexdigest() if tpl else None
    (RESULTS / "preflight.json").write_text(json.dumps(pre, indent=1))
    # L3 verification: model card at the pinned revision
    from huggingface_hub import hf_hub_download
    card = Path(hf_hub_download("cjvt/GaMS3-12B-Instruct", "README.md",
                                revision=MODELS["gams3_it"]["revision"])).read_text()
    quotes = [card[max(0, m.start() - 150): m.end() + 150] for m in
              re.finditer(r"(?i)continually pretrained on|\*\*Languages:\*\*|Base CPT\*\*", card)]
    l3 = {"candidate": "Hungarian (hun_Latn)", "hungarian_mentioned_in_card": bool(re.search(r"(?i)hungar", card)),
          "lithuanian_mentioned": bool(re.search(r"(?i)lithuan", card)), "card_quotes": quotes,
          "card_revision": MODELS["gams3_it"]["revision"],
          "decision": "L3 = Hungarian (absent from the CPT and SFT language lists)" if not re.search(r"(?i)hungar", card)
          else "Hungarian present -> switch to Lithuanian",
          "arxiv_2603_01691": "not fetched in this run (time); the model card at the pinned revision is the evidence"}
    (RESULTS / "l3_verification.json").write_text(json.dumps(l3, indent=1))
    print(json.dumps({"judge_mode": pre["judge_mode"], "l3": l3["decision"], "sibling": sib}, indent=1))


if __name__ == "__main__":
    main()
