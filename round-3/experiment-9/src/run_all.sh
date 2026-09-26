#!/usr/bin/env bash
# Full pipeline in execution order (one L4 23 GB GPU). Each step is resumable from its saved outputs.
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python          # HF + Heretic env (requirements.lock.txt)
PYV=.venv_vllm/bin/python    # vLLM env (requirements_vllm.lock.txt)

# S1 key probe (records whether the paid judges are reachable -> READOUT_MODE)
(cd src && ../$PY key_probe.py)
# S2 data: pool/exclusions/P300/DEV12 + NLLB (GPU)
(cd src && ../$PY prep_data.py pool)
# S5 Phase A (Heretic, HF NF4): 40 paired start-up trials, adapters, lambda/random adapters, C5a, engine-gate HF refs
$PY -u src/phase_a.py --model gemma_it
# J1 distilled judge (can share the GPU with phase A; capped at ~4 GB)
$PY -u src/judge_distill.py train
# twins: vLLM rewrite + 2-family SAFE screen -> filters/blocks -> NLLB
$PYV src/twins_vllm.py
(cd src && ../$PY prep_data.py twins_finalize && ../$PY prep_data.py twins_mt)
$PY -u src/phase_a.py --model gams3_it
# S3 freeze (before any confirmation generation)
(cd src && ../$PY write_protocol.py)
# S4 + S6 engine gate then Phase B generation (vLLM, bnb 4-bit + LoRA)
$PYV -u src/gen_vllm.py --model gemma_it --mode gate_full
$PYV -u src/gen_vllm.py --model gams3_it --mode gate_full
# S7 judging: J1 on all rows, J2 (second family) on core blocks G/GH + adjudication rows
$PY -u src/judge_distill.py predict --files results/gemma_it/gens.jsonl,results/gams3_it/gens.jsonl
$PYV -u src/judge_llm.py calib
$PYV -u src/judge_llm.py score --models gemma_it,gams3_it
# blind adjudication sample (labels written by the executing agent into results/adjudication_labels.json)
(cd src && ../$PY adjudicate.py 40)
# S8/S9 analysis, audit, figures, method_out.json
$PY method.py
$PY -m pytest -c pytest.ini tests/
