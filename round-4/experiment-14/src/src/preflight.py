#!/usr/bin/env python3
"""0.1 PREFLIGHT: existence check of every read-only input (builds_on 1-12), adapter sha1s, P1 prompt sha assertion,
HF revision pins (+ C-EXT candidates), GaMS3 Hungarian check (model card), OpenRouter smoke with usage accounting.
Writes results/inputs_check.json and results/provenance_code.json. The API key is never printed."""
from __future__ import annotations

import glob
import hashlib
import json
import re
import shutil

import requests
from loguru import logger

from common import (ADAPTER_DIR, DS_DIR, E8, E9, E10, E11, E12, EV2, ITER4, JUDGE_PROMPT_SHA, MODELS, RANDOM_DIR,
                    RESULTS, ROOT, dump, setup_logging, sha1_file, sha256_file)

EXPECTED_P1 = "97332090"


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("preflight")
    out: dict = {"checks": {}}
    need = {
        "gemma_adapter": ADAPTER_DIR["gemma_it"] / "adapter_model.safetensors",
        "gams_adapter": ADAPTER_DIR["gams3_it"] / "adapter_model.safetensors",
        "gemma_selection": E9 / "selected/gemma_it/selection.json",
        "gams_selection": E9 / "selected/gams3_it/selection.json",
        "gemma_random": RANDOM_DIR["gemma_it"] / "adapter_model.safetensors",
        "gams_random": RANDOM_DIR["gams3_it"] / "adapter_model.safetensors",
        "exp11_gen": E11 / "src/gen.py", "exp11_stats_core": E11 / "src/stats_core.py",
        "exp11_build_items": E11 / "src/build_items.py", "exp8_common_P1": E8 / "src/common.py",
        "eval2_adjudication": EV2 / "adjudication/blind_items.jsonl",
        "exp11_adjudication": E11 / "results/adjudication/adjudication_labels.jsonl",
        "exp10_adjudication": E10 / "results/adjudication_blind_gemma_it.jsonl",
        "dataset_artifact": DS_DIR / "full_data_out.json", "exp9_P300": E9 / "data/probe_P300.jsonl",
        "exp8_P200": E8 / "data/probe_P200.jsonl", "exp11_items": E11 / "data/items.jsonl",
        "exp12_gates": E12 / "results/gates.json", "exp8_harmless_dev32": E8 / "data/harmless_dev32.jsonl",
    }
    for k, p in need.items():
        out["checks"][k] = {"path": str(p).replace(str(ROOT.parent.parent.parent.parent), "<run>/3_invention_loop"),
                            "exists": p.exists()}
        if not p.exists():
            logger.error(f"MISSING {k}: {p}")
    assert out["checks"]["gemma_adapter"]["exists"] and out["checks"]["gams_adapter"]["exists"], \
        "BLOCKER: exp9 selected adapters missing"
    out["adapters"] = {m: {"sha1": sha1_file(ADAPTER_DIR[m] / "adapter_model.safetensors"),
                           "meta": json.loads((ADAPTER_DIR[m] / "meta.json").read_text()).get("lora_sha1"),
                           "selection": json.loads((E9 / f"selected/{m}/selection.json").read_text())}
                       for m in ("gemma_it", "gams3_it")}
    out["random_adapters"] = {m: {"sha1": sha1_file(RANDOM_DIR[m] / "adapter_model.safetensors"),
                                  "meta": json.loads((RANDOM_DIR[m] / "meta.json").read_text())}
                              for m in ("gemma_it", "gams3_it")}
    # P1 sha: recompute from exp8's source file and assert equality with our verbatim copy
    src8 = (E8 / "src/common.py").read_text()
    ns: dict = {}
    m = re.search(r"JUDGE_PROMPT = \((.*?)\)\nJUDGE_PRIMARY", src8, re.S)
    exec("JP = (" + m.group(1) + ")", ns)  # noqa: S102 - evaluates a string-literal concatenation only
    sha8 = hashlib.sha256(ns["JP"].encode()).hexdigest()
    out["p1"] = {"sha256_ours": JUDGE_PROMPT_SHA, "sha256_exp8": sha8, "expected_prefix": EXPECTED_P1,
                 "equal": sha8 == JUDGE_PROMPT_SHA, "prefix_ok": sha8.startswith(EXPECTED_P1)}
    assert sha8 == JUDGE_PROMPT_SHA, "P1 prompt differs from exp8"
    logger.info(f"P1 sha {JUDGE_PROMPT_SHA[:12]} equal to exp8: True; expected prefix {EXPECTED_P1}: "
                f"{out['p1']['prefix_ok']}")
    # exp12 E_art2 verdict (cited, not re-tested)
    try:
        g = json.loads((E12 / "results/gates.json").read_text())
        out["exp12_gates_excerpt"] = {k: v for k, v in g.items() if "art2" in k.lower() or "E_art" in k}
        if not out["exp12_gates_excerpt"]:
            out["exp12_gates_excerpt"] = str(g)[:1500]
    except (OSError, json.JSONDecodeError) as e:
        out["exp12_gates_excerpt"] = f"unreadable: {e}"
    # HF pins
    from huggingface_hub import HfApi
    api = HfApi()
    out["hf"] = {}
    for k, v in MODELS.items():
        try:
            info = api.model_info(v["repo"], revision=v["revision"], files_metadata=True)
            size = sum((s.size or 0) for s in info.siblings if s.rfilename.endswith(".safetensors"))
            out["hf"][k] = {"repo": v["repo"], "revision": info.sha, "pinned": v["revision"],
                            "match": info.sha == v["revision"], "gated": bool(getattr(info, "gated", False)),
                            "safetensors_gb": round(size / 1e9, 2),
                            "architectures": (info.config or {}).get("architectures")}
        except Exception as e:  # noqa: BLE001
            out["hf"][k] = {"repo": v["repo"], "error": f"{type(e).__name__}: {str(e)[:160]}"}
        logger.info(f"HF {k}: {out['hf'][k]}")
    # GaMS3 Hungarian check: model card at the pinned revision
    try:
        url = f"https://huggingface.co/cjvt/GaMS3-12B-Instruct/raw/{MODELS['gams3_it']['revision']}/README.md"
        txt = requests.get(url, timeout=30).text
        hits = [ln.strip() for ln in txt.splitlines() if re.search(r"Hungar|madžar|\bhu_|\bhun\b", ln)]
        langs = [ln.strip() for ln in txt.splitlines() if re.search(r"Croatian|Bosnian|Serbian|English|Slovene|"
                                                                   r"Slovenian|Italian|German", ln)][:12]
        out["gams_hungarian_check"] = {"url": url, "hungarian_lines": hits, "language_lines_sample": langs,
                                       "hungarian_present_in_card": bool(hits)}
    except requests.RequestException as e:
        out["gams_hungarian_check"] = {"error": str(e)}
    logger.info(f"GaMS Hungarian check: {out['gams_hungarian_check']}")
    # artifact-2 pool file?
    out["artifact2_pool_files"] = [p for p in glob.glob(str(ITER4 / "*/**/*pool*.json*"), recursive=True)
                                   if not p.startswith(str(ROOT))]
    out["disk_free_gb"] = round(shutil.disk_usage(str(ROOT)).free / 1e9, 1)
    # OpenRouter smoke
    import judge_paid
    smoke = judge_paid.run([{"tier": t, "task": "gen", "req": "Reply with the single word OK.", "meta": {"t": t}}
                            for t in ("flash_lite", "flash", "gpt41mini")], tag="smoke")
    out["openrouter_smoke"] = [{k: s.get(k) for k in ("model", "text", "reasoning_tokens", "cost", "tokens_in",
                                                         "tokens_out", "err")} for s in smoke]
    logger.info(f"smoke {out['openrouter_smoke']}")
    dump(RESULTS / "inputs_check.json", out)
    prov = {"copied_from": {
        "src/stats_core.py": {"source": "round-3/experiment-11/src/src/stats_core.py",
                              "sha256_source": sha256_file(E11 / "src/stats_core.py"),
                              "sha256_copy": sha256_file(ROOT / "src/stats_core.py")},
        "src/gen.py (load_model/_hook/attach_adapter/generate_batch/Runner)":
            {"source": "round-3/experiment-11/src/src/gen.py", "sha256_source": sha256_file(E11 / "src/gen.py")},
        "src/build_items.py (NLLB200/split/join/chrf)":
            {"source": "round-3/experiment-11/src/src/build_items.py",
             "sha256_source": sha256_file(E11 / "src/build_items.py")},
        "src/common.py (JUDGE_PROMPT P1)": {"source": "round-2/experiment-8/src/src/common.py",
                                            "sha256_source": sha256_file(E8 / "src/common.py")}}}
    dump(RESULTS / "provenance_code.json", prov)


if __name__ == "__main__":
    main()
