# Reproducibility

## Environment
* Python 3.12, dependencies pinned in `pyproject.toml` + `uv.lock` (`uv sync` restores the exact set).
* Key versions: torch 2.14.0+cu130, transformers 4.57.6, bitsandbytes 0.50.2, peft 0.21.0, numpy 2.5.3,
  scikit-learn 1.9.1, scipy 1.18.1, statsmodels 0.15.0. Recorded live in `results/preflight.json`.
* Hardware used: 1× NVIDIA L4 (23.7 GB). NF4 4-bit weights, bf16 compute. No host C compiler (the triton eager-op
  overrides are de-registered at import; see `src/common.py:disable_torch_native_triton`).
* Seed 20260926 everywhere (generation step order, item hashing, bootstrap, permutations).

## Models and edits (read-only inputs; not copied into this repo)
* `google/gemma-3-12b-it@96b6f1eccf38110c56df3a15bffe176da04bfd80`
* `cjvt/GaMS3-12B-Instruct@1d0b27af5748784482600d24779409e7e1dc9adc`
* `facebook/nllb-200-distilled-1.3B` (EN↔SL translation)
* Heretic edit `E_exp9`, random edits `rand_1..2`, and the J1 distilled judge: iter-3 exp9, read in place from the
  run volume. sha256 of every adapter is recorded in `results/preflight.json` and in each generation run's
  `results/check_{model}.json` (λ = 0 identity: max|Δlogit| = 0; hook vs saved λ = 1.0 / 0.5 adapters: 20/20 argmax,
  Δlogit 0).

## Determinism and resumability
* Generation is greedy; every row is keyed by `row_id = sha1(item_id|model|edit|arm|lambda)` and appended to
  `results/gens/{model}.jsonl`, so re-running resumes without duplicates.
* Paid calls are cached in `results/ledger.jsonl` by `sha1(request||response)`; no row is paid twice.
* NF4 batch-composition can make token-level outputs vary at the margin; iter-3 exp11 measured this as 64/64 stable
  outcomes at the label level, so a single greedy sample per prompt is used (standard for refusal audits).

## What was actually run (vs the pre-registered plan)
* The pre-registered **paid** readout (gemini-2.5-flash primary + gpt-4.1-mini second family + StrongREJECT ASR) was
  **not** run: the run's shared OpenRouter key reached its $12.00 limit at 19:05 UTC (amendment A4), after $0.28 of
  this artifact's calls (tier selection + Gemma DEV labels + twin build). The full-coverage readout is therefore the
  **J1 fallback** (exp9's mdeberta classifier distilled from archived real gemini-2.5-flash labels), which under F3 is
  **not** promoted to a validated primary. `finalize.sh` re-runs the paid readout on the saved generations when budget
  is available; nothing needs regenerating.
* `results/protocol_amendments.json` lists A0 (64 tokens), A1 (ladder + tier + cut order), A2 (fill-in), A4 (key
  limit → J1). `protocol.yaml` (+ `protocol.sha256`) was git-committed before any BODY row.

## Reproduce
```bash
uv sync
uv run pytest -q tests                 # 10 statistics unit tests
uv run method.py --stage all           # build items -> tier -> generate (GPU) -> label -> ttj -> adjudicate -> analyse
# OR, from saved generations only:
uv run method.py --stage analysis      # analysis.py -> rederive.py (independent audit) -> figures.py -> make_outputs.py
```
`results/audit.json` re-derives every headline number on an independent numpy/statsmodels path (`src/rederive.py`,
which never imports `analysis.py`) to a tolerance of 1e-6 (closed-form) / 1e-4 (GLM optimiser). Every number in
`README.md` / `RESULTS.md` is rendered from `results/analysis.json`; none is hand-typed.

## Kept artifacts (on the run volume, by path relative to this repo)
`results/` (generations, labels, analysis, audit, ledger, adjudication), `data/` (items + provenance), `figures/`,
`logs/`. These are all text/PDF and small; nothing is marked for deletion except `.venv/` (regenerable by `uv sync`).
The model weights and the exp9 edits/J1 checkpoint are **not** stored here — they are read in place from the shared HF
cache and the exp9 workspace on the run volume.
