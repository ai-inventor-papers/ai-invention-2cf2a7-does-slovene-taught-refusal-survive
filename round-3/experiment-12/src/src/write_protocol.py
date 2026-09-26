#!/usr/bin/env python3
"""STEP 2: freeze protocol.yaml (conditions, item-file sha256s, metrics, gate rule, cut order) BEFORE any edited-condition
forward pass. Writes protocol.yaml + protocol.sha256 and git-commits them."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import yaml  # noqa: E402

from common import (DATA, GATE_LOSS, HEADROOM_FLOOR, N_BOOT, PRIMARY_METRIC, SEED, UTIL_TASKS, WS, read_jsonl,  # noqa: E402
                    sha256_file)


def main() -> None:
    man = {str(q.relative_to(DATA)): sha256_file(q) for q in sorted(DATA.rglob("*.jsonl"))}
    (DATA / "manifest.json").write_text(json.dumps(man, indent=2))
    chance = {}
    for t in UTIL_TASKS:
        rows = read_jsonl(DATA / "util" / f"{t}_en.jsonl")[:300]
        chance[t] = sum(1 / len(r["choices"]) for r in rows) / len(rows)
    chance["belebele"] = 0.25
    proto = {
        "artifact": "iter3 gen_art_experiment_12 - RQ3 capability control (does de-censoring hurt Slovene skills more?)",
        "frozen_at_unix": int(time.time()),
        "seed": SEED,
        "models": {"gams3_it": "cjvt/GaMS3-12B-Instruct@1d0b27af5748784482600d24779409e7e1dc9adc",
                   "gemma_it": "google/gemma-3-12b-it@96b6f1eccf38110c56df3a15bffe176da04bfd80"},
        "precision": "bnb NF4 (Heretic Model loader, quantization=bnb_4bit, iter-1 config.toml verbatim)",
        "conditions": {
            "orig": "LoRA B = 0 (identity); equals disable_adapter()",
            "E_iter1": "iter-1 selected Heretic adapter (lambda 1) read-only from iter_1/gen_art_experiment_4/results/<model>/selected_adapter",
            "E_iter1_l{0.5,1.5,2.0}": "every lora_B x lambda (LoRA-delta scaling, as exp8 A1)",
            "rand_nm_j{1..5}": "Heretic Model.abliterate(rand_dirs(j), direction_index, SAME params); rand_dirs = iter-1 seeded per-layer unit Gaussian (seed 20260923+j)",
            "rand_c6_j1": "rand_dirs(1) with max/min weights x 6 (iter-1 largest random edit); KL/NLL only",
            "E_art2": "artifact-2 selected edit if discovered at block start; else PENDING",
        },
        "manipulation_check": "Heretic first-token KL on mlabonne/harmless_alpaca test[:100] (chat template, no system) must reproduce iter-1 pick KL within +/-25% and iter-1 random KLs within 10x",
        "utility": {
            "harness": "lm-evaluation-harness 0.4.13, custom local-subset YAMLs (tasks/), zero-shot, HFLM(add_bos_token=True, max_length=2048), no chat template",
            "tasks": UTIL_TASKS, "n_items_per_task_lang": 300, "lambda_variants": "100 items x {arc_challenge, boolq, openbookqa, winogrande}",
            "belebele": "EN/SL/HU 200 items paired by (link, question_number); harness prompt P/Q/A-D/Answer",
            "primary_metric": PRIMARY_METRIC, "chance": chance,
            "winogrande": "lm-eval partial scoring (context = sentence up to _ with option; continuation = remainder)",
        },
        "primary_estimand": {
            "H": "(acc_cond - chance)/(acc_orig - chance) - 1 per model x lang x task; loss = -H",
            "headroom_floor": HEADROOM_FLOOR,
            "macro": "mean H over eligible tasks (orig headroom >= 0.10) per model x lang x cond; pooled = mean(EN, SL)",
            "F6_rule": "if >= 3 of 6 tasks ineligible in a cell, the gate for that cell uses raw-pp macro loss with a 5 pp threshold",
            "bootstrap": {"draws": N_BOOT, "resample": "pair indices within task (same indices for orig/cond and EN/SL)", "ci": [90, 95]},
            "asymmetry": "A = H_SL - H_EN within model; interaction I = A_GaMS - A_Gemma per edit",
            "random_adjusted": "H_excess = H_edit - H_rand(j=1)",
            "mcnemar": "exact binomial on discordant pairs per task, Holm within condition",
        },
        "gate": {"rule": f"CATASTROPHIC if macro headroom-normalised loss > {GATE_LOSS} in EN OR SL (point estimate); "
                         f"POSSIBLY_CATASTROPHIC if only the 95% upper bound of the loss exceeds {GATE_LOSS}; else OK; PENDING if not run",
                 "lambda_gate_curve": "largest lambda that stays OK is reported"},
        "kl": {"set": "fresh Dolly-15k harmless (never used for selection; 8-gram/exact excluded vs harmless_alpaca, alpaca, exp8/iter-1 sets)",
               "arms": ["en_orig", "en_bt", "sl_mt", "hu_mt"], "n": 200, "mt": "NLLB-200-distilled-1.3B beam 4",
               "first_token": "KL(p_orig||p_cond) fp32 full vocab at the generation position, chat template no system, batch size 1 no padding",
               "multi_token": "mean per-position KL over the original model's greedy 32-token continuation (teacher forced)",
               "self_floor": "orig re-run after adapter swaps; >1e-4 reported as noise floor",
               "ratio": "RATIO = mean KL(SL-MT)/mean KL(EN-BT); RATIO_rand uses per-item KL averaged over rand_nm j1..5; EXCESS = RATIO_edit/RATIO_rand (item bootstrap)",
               "unreadable": "ratio UNREADABLE if mean random KL < 5x self floor"},
        "bpb": "sum NLL / (UTF-8 bytes x ln 2) on 150 human-translated FLORES passages per language (EN/SL/HU), BOS + raw text",
        "generations": {"tokens": 128, "decoding": "greedy, left-padded batches, chat template no system",
                        "language_consistency": "lingua restricted to EN,SL,HU,HR,SR,BS,DE,IT; consistent iff detected == prompt language; HR/BS/SR separate failure category for SL; gate >= 95%",
                        "degenerate": "empty, <5 tokens, distinct-4-gram ratio < 0.5 over >= 20 tokens, or zlib ratio < 0.25; gate < 10%"},
        "cut_order": ["GSM8K optional", "chat-template sensitivity", "rand_c6", "lambda variants -> 2.0 only",
                      "Belebele 200->100 and HU generations dropped", "300 -> 200 items per task", "drop HellaSwag and PIQA",
                      "random-edit utility Gemma only"],
        "never_cut": ["paired EN/SL", "headroom normalisation", "catastrophe gate per edit", "random-edit KL control", "manipulation check"],
        "pooling_constants": {"m": 0.675, "m_local": 0.20},
        "item_files_sha256": man,
    }
    p = WS / "protocol.yaml"
    p.write_text(yaml.safe_dump(proto, sort_keys=False, allow_unicode=True, width=140))
    sha = sha256_file(p)
    (WS / "protocol.sha256").write_text(sha + "  protocol.yaml\n")
    print("protocol sha256", sha)
    subprocess.run(["git", "-C", str(WS), "add", "protocol.yaml", "protocol.sha256", "src", "data/manifest.json",
                    "data/prep_report.json"], check=False)
    subprocess.run(["git", "-C", str(WS), "commit", "-q", "-m", "Freeze RQ3 protocol before edited-condition forward passes\n\n"
                    "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"], check=False)


if __name__ == "__main__":
    main()
