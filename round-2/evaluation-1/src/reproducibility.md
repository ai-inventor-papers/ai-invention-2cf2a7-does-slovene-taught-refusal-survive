# Reproducibility: re-scoring all iter-1 screens on one refusal readout (`gen_art_evaluation_1`)

This artifact runs no model and uses no GPU. It re-reads the saved per-item outputs of four iter-1 experiment artifacts
and one dataset artifact, re-derives their statistics, and writes verdicts. All numbers below are read from the files
in this folder. The workspace does not record the exact CPU model, RAM, or per-step wall-clock beyond what is quoted here.

## 1. Get the artifact

```bash
git clone <URL of the public repository that publishes this workspace>   # URL not recorded in the workspace
cd <repo>/<folder of gen_art_evaluation_1>
```

## 2. Required inputs from other artifacts (not part of this folder)

The scripts read the saved outputs of these sibling artifacts, read-only:

| artifact id | used for |
|---|---|
| `gen_art_experiment_1` | judge_gemini.jsonl, judge_idname.jsonl, `results/analysis_results.json` |
| `gen_art_experiment_2` | Slovene judge rows |
| `gen_art_experiment_3` | SYS_REF judged rows |
| `gen_art_experiment_4` | Heretic-screen / prefill responses, `analysis.json` |
| `gen_art_dataset_1` | prompt sets, audited `frozen_groups.json` |

**Portability caveat (not fixed, because the code was not to be edited here):** the location of these inputs is a
single absolute constant, `ITER1 = Path("../../../round-1")`
in `src/common.py:16`. `vendor/exp4_analyze.py:20` has the same absolute path (`_E4`). To run elsewhere, point both
at the folder that holds the sibling artifact folders above (the repository publishes them as sibling folders of
the iter-1 generation step). No other absolute path appears in the code. The four `labels/` and `work/` files already
committed here (`work/registry.jsonl.gz`, `labels/harmonised_P1.jsonl.gz`, ...) hold the derived rows, so the
evaluation-side steps can be inspected without the inputs, but the pipeline as written rebuilds them from the inputs.

## 3. Environment

- OS: Ubuntu (Linux 6.17 kernel on the run host). System packages: none beyond `uv` and Python 3.12
  (`python3 --version` on the host gave 3.12.14). No apt packages are recorded as needed.
- Hardware: CPU only, 4 cores (`nproc` = 4). GPU: none. RAM: not recorded.
- Venv (as in `run_all.sh`, which creates it if `.venv` is missing):

```bash
uv venv .venv --python=3.12
uv pip install --python .venv/bin/python -r requirements.txt
```

`requirements.txt` and `pyproject.toml` carry the same 38 exact pins, including numpy==2.5.3, scipy==1.18.1,
pandas==2.3.3, scikit-learn==1.9.1, statsmodels==0.15.0, matplotlib==3.11.2, lingua-language-detector==2.2.0,
loguru==0.7.3, aiohttp==3.14.3, pyyaml==6.0.3 (see the files for the rest).

## 4. Keys, downloads

- No models, checkpoints or datasets are downloaded.
- Env var `OPENROUTER_API_KEY` (name only) is read **only** by `src/judge_p1.py` (paid tiers). It was exhausted
  (`limit_remaining 0`) during the run, so no paid call was made and $0 was spent. Without budget the script prints
  "key exhausted" and exits 3; `run_all.sh` tolerates that and continues.

## 5. Commands (exactly what `run_all.sh` runs, in order)

```bash
./run_all.sh
```

which executes:

```bash
(cd src && ../.venv/bin/python build_registry.py)     # registry of 33,623 responses + exact-P1 propagation
(cd src && ../.venv/bin/python surrogate.py)          # P1-only surrogate
(cd src && ../.venv/bin/python surrogate_pooled.py)   # pooled surrogate anchored to P1
(cd src && ../.venv/bin/python judge_p1.py --tier ALL) || echo "paid tiers not run"   # exit 3 in this run
.venv/bin/python eval.py                              # -> work/eval_full.json
.venv/bin/python src/report.py                        # -> eval_out.json, RECONCILIATION.md, work/verdict_table.json
.venv/bin/python src/figures.py                       # -> figures/
(cd src && ../.venv/bin/python spotcheck.py)          # score readouts vs the 48-item adjudication
(cd src && ../.venv/bin/python audit.py)              # 46 second-path checks; non-zero exit on failure
(cd src && ../.venv/bin/python placebo_check.py)      # shuffled-input tests must FAIL
```

Optional: `cd src && ../.venv/bin/python spotcheck.py --print` re-draws the same 48 items with no readout attached.
`judge_p1.py --tier {A,B,C,ALL}` is the paid pipeline (gemini-2.5-flash, openai/gpt-4.1); it is implemented and
dry-run tested (Tier A 20,037 jobs, B 7,088, C 6,975) but **was not run**. It is resumable from
`labels/ledger.jsonl`, which does not exist. Rerunning it later would change the readout (real labels replace the
surrogate wherever the ledger supplies them), so numbers below would then differ.

**Seeds:** global `SEED = 20260924` and bootstrap `B = 2000` in `src/common.py`; `rng_seed=20260923` in
`src/rederive.py`; adjudication draw seed 20260924 (12 items per model x language). Runtime: the $0 chain took
about 4 minutes on 4 cores (README); `eval.py` itself logged 79-81 s. Per-step timings otherwise not recorded.

**Protocol freeze:** `eval_protocol.json` with sha256 `8b240ee8...` in `eval_protocol.sha256` (includes amendments
A1, $0 readouts, and A2, kappa >= 0.4 guard; the original hash `d79adbc2...` is noted there).

## 6. Outputs and numbers to expect (from `logs/run_all_full.txt`, `README.md`, `RECONCILIATION.md`)

The logged full run ended with 44 metrics, 10 verdict rows, 38 reconciled numbers, and `46/46 checks pass`, EXIT 0.

| file | content |
|---|---|
| `eval_out.json` (+ `full_`, `mini_`, `preview_` variants) | 44 headline metrics, 33,623 per-response rows |
| `work/eval_full.json`, `work/reconciliation.json`, `work/verdict_table.json` | full result tree, reconciliation, verdicts |
| `RECONCILIATION.md` | verdict table (10 claims) + 38-number map |
| `work/audit.json`, `work/placebo_check.json` | audit and placebo results |
| `work/paraphrase_deflection_*.json` | GaMS-SL paraphrase deflection counts |
| `figures/fig1..fig6` (pdf + png) | forest/meta, agreement heatmap, prefill depth, C3 lambda curves, readout sensitivity, verdict table |

Numbers a reader should get:
- Real gemini P1 labels on 13,586 of 33,623 rows (10,852 exp1 + exact propagation); pooled surrogate trained on 26,912 labels.
- Cell validity: 33 VALID, 17 FAIL, 22 UNVALIDATED (all GaMS exp4 cells).
- 48-item adjudication (43 scorable for the logged kappas): pooled-P1 kappa 0.392, lexicon 0.211, real gemini JP2 0.167 (n=20), pooled-JP2 0.097.
- exp1 DiD -0.377 [-0.706, -0.051]; GaMS-SL deficit re-read: E1 -0.38, E3 -0.69, E4 -0.95, E6 -1.25; GLS pooled -0.50 [-0.82, -0.21]; REML + modified HKSJ -0.71 [-1.43, 0.00], I^2 0.40, PI [-2.30, +0.87].
- C1 DiD_id +3.22 [+2.38, +4.38]; D = -0.70 [-1.57, +0.08] under `frozen_groups.json`; C5a excess 0.298 (Gemma) and 0.574 (GaMS); Pareto hv ratio 2.292.
- Deflection: 34.6% (115/332) of GaMS Slovene prefill continuations paraphrase the request; Sig_SL 1.54 -> 1.16 after removal.
- Reconciliation: 15 SURVIVES, 1 SHRINKS, 0 REVERSES, 20 UNCITABLE, 2 NEW.

The adjudication is by the author model, not a human or a native Slovene speaker. The mapping from these files to paper
sections or table numbers is **not recorded** in the workspace (no paper source is in this folder).
