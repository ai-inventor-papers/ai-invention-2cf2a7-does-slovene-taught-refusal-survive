# Reproducibility: re-scoring saved replies (gen_art_evaluation_4, SCREEN)

This file records what was actually run, in order. All paths are relative to this folder.

## 1. Get the artifact

```bash
git clone <this run's public repository>
cd <repo>/3_invention_loop/iter_5/gen_art/gen_art_evaluation_4
```

This artifact generates no replies itself. It reads the saved replies and labels of upstream artifacts through one
root, `AII_DEPS_ROOT`. The default is `../../..` relative to this folder, i.e. the folder that holds `iter_4/` and
`iter_5/` (see `src/common.py`). The repository publishes the upstream artifacts as sibling folders:

| artifact id | folder under `AII_DEPS_ROOT` | used for |
|---|---|---|
| art_4Mf1Fazk33yZ (exp14) | `iter_4/gen_art/gen_art_experiment_14` | `results/rows_final.jsonl`, `results/labels/ttj_translations.jsonl`, `data/items.jsonl`, `data/strongreject_judge_templates.json`, `results/analysis.json`, `results/cells_compliance.json` |
| art_piu0nI9vij_F (exp15) | `iter_4/gen_art/gen_art_experiment_15` | `results/rows_final.jsonl`, `results/ttj.jsonl`, `results/analysis.json`, `data/items.jsonl` |
| art_gOdYt7zLWvfr (eval3) | `iter_4/gen_art/gen_art_evaluation_3` | `results/judge_error_matrices_v2.json`, `labels/readout_rows.jsonl.gz` (copied, cited only) |
| art_4V4_5HnuN2ka (eval2) | `iter_3/gen_art/gen_art_evaluation_2` | `judge_error_matrices.json` (copied, cited only) |

If those folders live elsewhere, `export AII_DEPS_ROOT=/path/to/folder-with-iter_4`. No user-uploaded file is read.

## 2. Environment (as actually used)

- Ubuntu/Debian 12 container, Python 3.12.
- Hardware: 1x NVIDIA L4 (23 GB VRAM), driver with CUDA 12.8; 6 CPUs, 57 GB RAM (cgroup limits).

```bash
uv venv .venv --python=3.12
uv pip install --python .venv/bin/python -r requirements.lock.txt   # exact versions actually installed (114 pins)
# torch must be the CUDA 12.8 build for a CUDA-12.8 driver (the default PyPI wheel, cu130, fails to initialise CUDA):
uv pip install --python .venv/bin/python torch==2.8.0 --index-url https://download.pytorch.org/whl/cu128
```

The direct dependencies are pinned in `pyproject.toml`, for example transformers 4.49.0, peft 0.21.0, torch
2.8.0+cu128, numpy 2.5.3, scipy 1.18.1 and pandas 3.0.6.

## 3. Models, data and keys (names only)

- `HF_TOKEN` is needed for the gated `google/gemma-2b`. The other models are `facebook/nllb-200-distilled-1.3B` and
  `qylu4156/strongreject-15k-v1` (PEFT adapter). All three download automatically on first use into the HF cache.
- `OPENROUTER_API_KEY` and `OPENROUTER_BASE_URL` are needed for every LLM call (OpenRouter only).
- Paid models: `google/gemini-2.5-flash`, `openai/gpt-4.1-mini`, `anthropic/claude-sonnet-4.5`.
- Free models: `nvidia/nemotron-3-ultra-550b-a55b:free`, `poolside/laguna-s-2.1:free`,
  `dots-studio/dots-3-note-preview:free`, `nvidia/nemotron-3-super-120b-a12b:free`.
- All LLM answers are cached in `labels/api_cache.jsonl`, keyed by the sha1 of the request, and costed in
  `labels/ledger.jsonl`. A rerun with these files present costs $0 and needs no key. Without them, the paid calls
  cost about $2.9.

## 4. Commands actually run, in order (seed 20260925 everywhere)

| # | command | what it does | time |
|---|---|---|---|
| 1 | `.venv/bin/python src/smoke.py` | input check and exp14/exp15 smoke tests (must pass) | <1 min |
| 2 | `.venv/bin/python src/cost_projection.py` | live-price projection | <1 min |
| 3 | `.venv/bin/python src/api_work.py frame` | frozen adjudication frame | <1 min |
| 4 | `git commit protocol.yaml ...` | freeze (see `git log`; amendments in `results/amendments.jsonl`) | |
| 5 | `.venv/bin/python src/api_work.py pilot x 24` | paid pilot. Stopped by the platform budget after the 60 sonnet-4.5 labels (AM1) | ~1 min |
| 6 | `.venv/bin/python src/gpu_work.py translate srft` | GPU: NLLB translations, then SR_ft on 26,740 texts (bs 8 after OOM) | ~65 min on the L4 |
| 7 | `.venv/bin/python src/free_sched.py <minutes>` | free-model panel, 19 req/min limiter, priority queue. Run several times (AM2, AM4, AM6, AM10, AM11); resumable | ~95 min in total |
| 8 | `AII_HARD_STOP=2.82 .venv/bin/python src/paid_round5.py bake sonnet` | gemini full-vs-compact bake-off (full chosen) and sonnet reference on the 200 hi rows | ~3 min |
| 9 | `AII_HARD_STOP=2.82 .venv/bin/python src/paid_round5.py sr` | gemini StrongREJECT: Gemma EN->SL/EN->EN hi, lo, GaMS hi, then Gemma zero (AM7) | ~5 min |
| 10 | `AII_HARD_STOP=3.05 .venv/bin/python src/paid_round5.py trunc` | gemini on 300 truncation-matched EN->EN hi replies (AM9) | ~1 min |
| 11 | `./finalize.sh` | P1 labels, `eval.py`, `src/rederive.py`, `pytest`, schema validation and mini/preview (validation runs only if `AII_JSON_SKILL_DIR` is set) | ~3 min |
| 12 | `.venv/bin/python src/audit_headlines.py` | independent headline audit plus shuffled-input test | <1 min |

Steps 1-4 and 11-12 alone reproduce every number from the saved labels in `labels/`.

A delayed duplicate of step 6 ran in parallel from 00:45 to 01:38 (AM8). Its SR_ft rows are identical duplicates;
for translations, the last-written row per key is canonical, and every reader resolves duplicates that way.

## 5. What you should get

- `RESULTS.md`, generated from `results/*.json`. `README.md` "Headline" quotes it.
- `results/verdicts.json`, V1 at hi: **HARMFUL CONTENT SEPARATES (reserve = safety)**, with OUT_U (Gemma,
  EN->SL minus EN->EN, log-odds of the safe outcome):

  | readout | OUT_U [95% CI] |
  |---|---|
  | gemini original | 2.61 [2.20, 3.07] |
  | gemini translation | 2.41 [2.01, 2.88] |
  | gemini truncation-matched | 2.39 [1.97, 2.86] |
  | claude-sonnet-4.5 | 2.75 [1.95, 3.95] |
  | SR_ft | 1.37 [0.77, 2.35] |
  | SR_ft truncation-matched | 0.35 [-0.50, 1.32] |

  V3: dOUT_U (gemini) = -2.45 [-2.99, -1.99]. SDT R-BASE-OUT DiD_c(hi) - DiD_c(zero) = -0.80 [-1.23, -0.46].
- `results/rederive.json`: 49/49 checks pass. `results/audit_headlines.json`: the four headline OUT_U values match
  to 1e-6 from the raw label files, and the within-item shuffled-language null centres on 0 (95% range
  [-0.44, 0.39]), so the test fails on placebo input as it should.
- `eval_out.json` / `full_eval_out.json` (exp_eval_sol_out, 16,723 examples), plus `mini_*` and `preview_*`.
- Bootstrap CIs use numpy's default_rng(20260925 + offset), so they reproduce exactly with the pinned numpy.

All adjudication is by LLMs, **NOT humans**. The native-speaker audit is an unmet item (`human_input_requests.json`).
