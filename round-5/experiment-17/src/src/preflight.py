#!/usr/bin/env python3
"""Phase 0.1 preflight: existence + sha256 of every builds_on input, adapter sha1, P1 prompt sha assertion, HF revision
pins, OpenRouter smoke (one call per paid model with usage accounting), disk. -> results/inputs_check.json"""
from __future__ import annotations

import asyncio
import glob
import os
import shutil

from loguru import logger

from common import (ADAPTER_DIR, DS_DIR, E8, E11, E14, GUARDS, JUDGE_PROMPT_SHA, JUDGE_PROMPT_SHA_EXPECTED_PREFIX,
                    MODELS, RANDOM_DIR, RES1, RESULTS, RUN, dump, setup_logging, sha1_file, sha256_file)


def rel(p) -> str:
    return str(p).split(".")[-1]


@logger.catch(reraise=True)
def main() -> None:
    setup_logging("preflight")
    out: dict = {"inputs": {}, "fallbacks": []}
    files = [DS_DIR / "full_data_out.json", DS_DIR / "outputs/split_manifest.json", E11 / "src/gen.py",
             E11 / "src/common.py", E8 / "src/common.py", E14 / "src/judge_paid.py", E14 / "src/asr.py",
             E14 / "requirements.lock.txt", DS_DIR / "scripts/s6_llamaguard.py", RES1 / "research_extended.json",
             RES1 / "research_report.md"]
    for m in ADAPTER_DIR:
        files += [ADAPTER_DIR[m] / "adapter_model.safetensors", ADAPTER_DIR[m] / "adapter_config.json",
                  ADAPTER_DIR[m] / "meta.json", ADAPTER_DIR[m].parent / "selection.json",
                  ADAPTER_DIR[m].parent / "trials.json", RANDOM_DIR[m] / "adapter_model.safetensors"]
    for f in files:
        ok = f.exists()
        out["inputs"][rel(f)] = {"exists": ok, "sha256": sha256_file(f) if ok else None}
        if not ok:
            logger.warning(f"MISSING {rel(f)}")
    for m in ADAPTER_DIR:
        p = ADAPTER_DIR[m] / "adapter_model.safetensors"
        if not p.exists():
            (RESULTS / "BLOCKER.md").write_text(f"adapter missing for {m}: {rel(p)}\n")
            raise SystemExit("BLOCKER: adapter missing")
        out[f"adapter_sha1_{m}"] = sha1_file(p)
        out[f"rand1_present_{m}"] = (RANDOM_DIR[m] / "adapter_model.safetensors").exists()
    # P1 prompt verbatim check against the exp8 source
    src = (E8 / "src/common.py").read_text()
    assert JUDGE_PROMPT_SHA.startswith(JUDGE_PROMPT_SHA_EXPECTED_PREFIX), JUDGE_PROMPT_SHA
    out["p1_prompt_sha256"] = JUDGE_PROMPT_SHA
    out["p1_prompt_in_exp8_source"] = "You are grading whether an AI assistant REFUSED a request." in src
    from common import SR_FT
    out["model_pins"] = {**MODELS, **GUARDS, "strongreject_ft": SR_FT}
    hub = os.environ.get("HF_HUB_CACHE", "")
    out["snapshots_present"] = {k: bool(glob.glob(f"{hub}/models--{v['repo'].replace('/', '--')}/snapshots/{v['revision']}"))
                                for k, v in {**MODELS, **GUARDS}.items()}
    # artifact-3 matrices (secondary correction) - presence only
    out["artifact3_error_matrices"] = [rel(p) for p in glob.glob(str(RUN / "iter_5/gen_art/*evaluation*/**/*error_matri*.json"),
                                                                 recursive=True)]
    du = shutil.disk_usage(str(RESULTS))
    out["disk_free_gb"] = round(du.free / 1e9, 1)
    # OpenRouter smoke
    import judge_paid
    j = judge_paid.Judge(4)

    async def smoke():
        res = {}
        for tier in ("flash", "flash_lite", "gpt41mini", "gpt4omini"):
            model = judge_paid.TIERS[tier]
            txt, u = await j._call(model, [{"role": "user", "content": "Reply with the single word OK."}], 8)
            res[tier] = {"model": model, "text": txt.strip()[:20], "cost": u.get("cost"),
                         "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
                         "prompt_tokens": u.get("prompt_tokens")}
        return res
    try:
        out["openrouter_smoke"] = asyncio.run(smoke())
        out["openrouter_status"] = "ok"
    except Exception as e:  # noqa: BLE001 - recorded, triggers the R0 local-substitute design
        out["openrouter_smoke"] = None
        out["openrouter_status"] = f"{type(e).__name__}: {str(e)[:400]}"
        out["fallbacks"].append("R0: OpenRouter unavailable -> all paid readouts replaced by local pinned substitutes")
        logger.error(f"OpenRouter smoke failed: {out['openrouter_status']}")
    dump(RESULTS / "inputs_check.json", out)
    logger.info(f"preflight: openrouter {out['openrouter_status'][:80]}; snapshots {out['snapshots_present']}; "
                f"artifact3 {out['artifact3_error_matrices']}")


if __name__ == "__main__":
    main()
