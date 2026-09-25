# Reproducibility — exp16 (iter-5 held-out confirmation of C-OUT)

Everything below is what was actually run (2026-09-25, UTC), in order. All paths are relative to this folder.

## 1. Get the artifact
This folder is one directory of the AI-Inventor run's public GitHub repository.
```bash
git clone <this-repository-url>
cd <repo>/3_invention_loop/iter_5/gen_art/gen_art_experiment_16
```
Inputs produced by other artifacts are read (read-only) from **sibling folders of the same clone**, through the single
constant `RUN` in `src/common.py`: the enclosing `3_invention_loop` directory (found by walking up from
`src/common.py`), or `$AII_RUN_ROOT` if you set it. Sibling artifacts used, by folder / id:
* `iter_4/gen_art/gen_art_experiment_13` — item pool, split manifest, twins, JBB benign, StrongREJECT templates.
* `iter_4/gen_art/gen_art_experiment_14` — screen harness (code provenance), suffixes, rows used for dedup.
* `iter_4/gen_art/gen_art_experiment_15`, `iter_2/.../gen_art_experiment_8`, `iter_3/.../gen_art_experiment_9|10|11`
  — dedup references; exp9 also supplies the Heretic LoRA adapters, the random-direction control and the J1 judge parts.
* `iter_1/gen_art/gen_art_dataset_1` (id `art_EG6OpEkGvysx`) — RefusEU eval rows (dedup reference only).
* `iter_4/gen_art/gen_art_research_1` (id `art_NZ9n2Ej5RtGt`) — method specs (read, not executed).
No user-uploaded file is used (the uploaded research plan is private and not published; it is not needed to run).

## 2. Environment
* Ubuntu 22.04-class Linux, NVIDIA driver 570 (CUDA 12.8), **one NVIDIA L4 (23 GB)**, 48 CPU cores.
* Python 3.12 and `uv` (no pip). `uv sync` builds `.venv` from `pyproject.toml` + `uv.lock`; every dependency is
  pinned to the exact installed version (`requirements.lock.txt` = `uv pip freeze`). Key pins: torch 2.14.0+cu126
  (from the PyTorch cu126 index, configured in `pyproject.toml`; amendment A0), transformers 4.57.6,
  bitsandbytes 0.50.2, peft 0.21.0, accelerate 1.15.0, sacrebleu 2.6.0, lingua-language-detector 2.2.0,
  openai 3.19.2, numpy 2.5.3, pandas 3.0.6, scipy 1.18.1.
```bash
uv sync
```

## 3. Downloads, secrets
* Models (pinned revisions; `./dl.sh` fetches them into the HF cache, never into this folder):
  `google/gemma-3-12b-it@96b6f1eccf38110c56df3a15bffe176da04bfd80`,
  `cjvt/GaMS3-12B-Instruct@1d0b27af5748784482600d24779409e7e1dc9adc`,
  `p-e-w/gemma-3-12b-it-heretic@e037e6e112ea85777fc3858469cdc31fdfceaa13`, `facebook/nllb-200-distilled-1.3B`,
  `qylu4156/strongreject-15k-v1` (+ its base `google/gemma-2b`). Gemma repos are gated: env `HF_TOKEN` (name only).
* Dataset `NASK-PIB/RefusEU@5523ce30b9` (dedup reference; HF datasets).
* OpenRouter: env `OPENROUTER_BASE_URL`, `OPENROUTER_API_KEY` (names only; never stored). Models:
  `google/gemini-2.5-flash` (primary, reasoning off), `openai/gpt-4.1` + `anthropic/claude-haiku-4.5` (blind
  adjudication), `deepseek/deepseek-chat-v3.1` (tie-break). Total spend **$4.009** (`ledger/ledger.jsonl`,
  `results/paid_summary.json`); hard stop $4.00 (the last concurrent batch overshot by $0.009).

## 4. Commands actually run (seed 20260927)
```bash
./dl.sh                                    # ~8 min
cd src
../.venv/bin/python items.py               # S1 CONF 294 / DEV 37 / twins 100, dedup, NLLB arms   (~5 min)
../.venv/bin/python freeze.py              # S2 protocol.yaml + sha256, git commit (before any generation)
cd ..
AII_TOKEN_BUDGET=15000 ./run_chain.sh      # S3-S7 GPU chain (~3 h): Gemma (deadline 02:17) -> TTJ -> GaMS3 (68 min)
                                           #   -> TTJ -> C-EXT pew (16 min) -> TTJ + round-trip -> local scoring
./paid_chain.sh                            # S8/S9 paid labels in the A1/A4 order (smoke run first: paid.py --mode smoke)
cd src
../.venv/bin/python paid.py --mode drift   # drift check, then --mode pd until the hard stop (amendment A7)
../.venv/bin/python score_local.py --mode sr   # re-run after the Triton fix (the chain's scoring step crashed)
../.venv/bin/python analysis.py            # S10  (~5 min)
../.venv/bin/python rederive.py            # S11 independent re-derivation -> results/audit.json
../.venv/bin/python figures.py && ../.venv/bin/python make_outputs.py
cd .. && .venv/bin/python -m pytest -q tests/
```
`method.py` wraps the same stages (`uv run method.py --stages items,freeze,gpu,paid,analysis,rederive,figures,outputs,tests`).
The chain was stopped and relaunched twice by PID (amendments A2: queue priority fix; A3: token budget 24000 ->
15000 after OOM thrash); generation resumes by row key, so no row was regenerated or discarded. Every departure is in
`results/amendments.jsonl`, each committed before the work it affects (git log). Freeze order is checked
programmatically in `results/freeze_order_check.json`.

## 5. What you should get
* `results/verdicts.json` (D1-D8 + F9 per-adjudicator + SB), `results/analysis.json`, `results/RESULTS_tables.md`
  (T1-T8, generated; no hand-typed numbers), `results/error_matrices.json`, `results/audit.json`.
* The README "Results summary" block is generated from `results/analysis.json` by `src/make_outputs.py`.
* Figures `figures/fig1`-`fig5` (PDF + PNG), drawn only from `results/analysis.json`.
* Greedy decoding is deterministic up to NF4 / CUDA-kernel / batch-composition numerics; absolute rates are
  engine-specific (exp9 A5), so compare contrasts, not absolute rates, across machines.
