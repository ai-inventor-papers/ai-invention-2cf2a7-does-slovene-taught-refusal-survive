# Reproducing this audit

This is what was actually run for this artifact (iteration-5 evaluation "Tracing every paper number to saved
results"). It is an analysis-only audit of saved outputs of earlier artifacts. It makes **no paid API calls**
(OpenRouter spend $0) and no new generations. The one exception is an optional, gated GPU re-measurement of exp15's
first-token KL, using the saved adapters.

## 1. Get the artifact

The workspace is published as one folder of a public GitHub repository. Clone the repository and `cd` into this
artifact's folder:

```bash
git clone <repository-url> && cd <repository>/<this-artifact-folder>   # e.g. iter_5/gen_art/gen_art_evaluation_5
```

All paths below are relative to this folder. The code reads upstream artifacts through **one** constant,
`AII_RUN_ROOT`, defined in `src/common.py` and repeated in `verify/verify.py` and `gpu/kl_recompute.py`. Its
default is three directories above this folder (`Path(__file__)`-anchored), i.e. the invention-loop root whose
`iter_*/gen_art/<artifact>/` sub-folders hold the upstream artifacts. If your clone lays the artifacts out
differently, set `export AII_RUN_ROOT=<path to the folder that contains iter_1 ... iter_5>`.

Upstream artifacts read (read-only; listed with their files in `inputs.yaml`; existence, size and sha256 are
recorded in `results/inputs_manifest.json`):

| artifact id | folder (relative to `AII_RUN_ROOT`) |
|---|---|
| art_piu0nI9vij_F (exp15) | `iter_4/gen_art/gen_art_experiment_15` |
| art_4Mf1Fazk33yZ (exp14) | `iter_4/gen_art/gen_art_experiment_14` |
| exp13 | `iter_4/gen_art/gen_art_experiment_13` |
| eval3 | `iter_4/gen_art/gen_art_evaluation_3` |
| research_1 | `iter_4/gen_art/gen_art_research_1` |
| art_n3Crj0p24sBa (exp9) | `iter_3/gen_art/gen_art_experiment_9` |
| art_Aw3AXCXv9pUg (exp11) | `iter_3/gen_art/gen_art_experiment_11` |
| exp10, exp12, eval2 | `iter_3/gen_art/gen_art_experiment_10`, `..._12`, `gen_art_evaluation_2` |
| exp5 / exp4 | `iter_2/gen_art/gen_art_experiment_5`, `iter_1/gen_art/gen_art_experiment_4` |
| iteration-4 paper draft and review | `iter_4/gen_report_text/gen_report_text/paper_draft.md`, `iter_4/review_report/review_report/.terminal_claude_agent_struct_out.json` |

Caveats on these inputs:

- Some upstream files are large and may not be in the public repository. The publish step skips files of 100 MB or
  more, and a few inputs (e.g. eval3 `work/frame.parquet`, exp15 `results/rows_final.jsonl`) are git-ignored by their
  own artifacts. If one is missing, `src/check_inputs.py` records it, and only the cells that depend on it become
  UNTRACEABLE.
- The user's uploaded research-plan document is private and is **not** published. Nothing in this artifact reads it.

## 2. System, Python and libraries

- Ubuntu (Linux 6.8), Python **3.12.14**, `uv` for environments. No system packages beyond a C runtime are needed for
  the CPU path.
- CPU analysis environment: exact pins are in `pyproject.toml` and `requirements.lock.txt`: numpy 2.5.3, scipy 1.18.1,
  pandas 3.0.6, pyarrow 25.0.1, matplotlib 3.11.2, loguru 0.7.3, pyyaml, pytest 9.1.1. Create it with:

```bash
uv venv .venv --python=3.12
uv pip install --python .venv/bin/python -r requirements.lock.txt
```

- Optional GPU environment: `gpu/pyproject.toml` and `gpu/uv.lock` are copied unchanged from exp15 (torch 2.14.0+cu130,
  transformers 4.57.6, bitsandbytes 0.50.2, accelerate 1.15.0). Install with `cd gpu && uv sync --frozen`. It takes
  about 9 GB and 10-15 minutes.

## 3. Downloads, environment variables, keys

- The CPU path needs no downloads and no keys.
- The GPU path needs:
  - the pinned weights `google/gemma-3-12b-it@96b6f1eccf38110c56df3a15bffe176da04bfd80` (gated) and
    `cjvt/GaMS3-12B-Instruct@1d0b27af5748784482600d24779409e7e1dc9adc`, in the Hugging Face cache named by `HF_HOME` /
    `HF_HUB_CACHE`. The script runs with `HF_HUB_OFFLINE=1`, so fetch the weights first with
    `huggingface-cli download <repo> --revision <sha>`;
  - `HF_TOKEN` (gated Gemma);
  - exp9's saved adapters `selected/<model>/adapter` and `adapters/<model>/rand_{1,2}`, read via `AII_RUN_ROOT`.
- `OPENROUTER_API_KEY` is **not** used.

## 4. Commands actually run (in order)

Hardware: 48-CPU host, 503 GB RAM, 1x NVIDIA L4 (23 GB VRAM; about 8.4 GB used per NF4 12B model).
Seeds: 20260927 (audit), 20260926 (GPU forward pass; greedy and deterministic). B = 2000 bootstrap draws, 5000
permutations, 200,000 posterior draws.

```bash
git add protocol_eval.yaml && git commit -m "freeze"    # decision rules frozen BEFORE Steps 1-2 (commit c82f748; sha256 in git)
.venv/bin/python eval.py                                 # Steps 0-7: inputs manifest, ceiling, KL, decomposition, exp14 tables,
                                                         # ledger, owed tables / criterion shift / exp13 / coverage / verdicts,
                                                         # verify/verify.py, make_tables.py -> eval_out.json   (~75 s CPU)
(cd gpu && uv sync --frozen && .venv/bin/python kl_recompute.py)   # optional GPU step, ~6 min incl. model loads
                                                                   # -> results/kl_items_exp15_recomputed.jsonl
.venv/bin/python eval.py                                 # rerun so the gated GPU result enters kl_excess.json and every table
.venv/bin/python -m pytest -q                            # 7 unit tests
.venv/bin/python verify/verify.py                        # independent second code path (never imports src/)
# schema check + variants (aii-json skill):
#   aii_json_validate_schema.py --format exp_eval_sol_out --file eval_out.json
#   aii_json_format_mini_preview.py --input eval_out.json   -> full_/mini_/preview_eval_out.json
```

`.venv/bin/python eval.py --skip-steps` only rebuilds `eval_out.json` from `results/*.json`.
`src/make_tables.py` re-renders every markdown file, the figures and `PAPER_INSERTS.md` from JSON. Once the
iteration-5 experiments write `results/analysis.json`, `src/owed.py` fills the PENDING rows (RQ2 / C-OUT) by glob.

## 5. What you should get

All numbers are rendered from JSON. See `PAPER_INSERTS.md` for paste-ready text, and `eval_out.json` `metrics_agg` for
the machine-readable headline values.

- **Ceiling sensitivity** (`results/ceiling_sensitivity.{json,md}`, `figures/fig_fragility.pdf`):
  - exp15 lambda-0 counts: Gemma 294/300 EN and 299/300 SL; GaMS3 289 and 292;
  - G3_orig -1.171; FI_m = 1; FI_0 = 4;
  - probability-scale DiD -0.67 pp, 95% CI [-3.3, 1.7];
  - verdict CEILING-ARTEFACT.

  Across eval3 bodies (paid gemini readout), only exp9's baseline offset is ROBUST-OFFSET (FI_m 9). exp8_A1, exp8_B and
  exp11 are CEILING-ARTEFACT.
- **C5a** (`results/kl_excess.{json,md}`, `figures/fig_kl_excess_forest.pdf`):
  - exp15 excess 0.959 (Gemma) and 0.796 (GaMS3), reproduced exactly;
  - the gated GPU re-measurement reproduced the saved means (relative difference 0.0000). The item-bootstrap CIs
    [0.41, 2.89] and [0.51, 1.28] give UNDETERMINED;
  - overall, 8 of 12 body rows are NO-LEAKAGE and 4 are UNDETERMINED.
- **Decomposition** (`results/decomposition_table.{json,md}`, `figures/fig_decomposition_forest.pdf`): 107 body x
  readout rows with frozen statuses, split by direction; slopes replace the "parallel curves" claim.
- **exp14 tables** (`results/exp14_tables_regenerated.md`):
  - the independent rows_final cross-check finds 0 mismatches;
  - paper Tables 28-29 differ from exp14 in 0 of 180 values.
- **Ledger** (`results/correction_ledger.{json,csv}`, `results/ledger_summary.md`):
  - 1,176 tokens plus 22 pointer claims;
  - 4 claim-level reversals and 2 attribution errors;
  - the placebo auto-match rate is reported, so auto-SURVIVES counts as weak evidence.
- **Criterion shift** (`results/criterion_shift.{json,md}`): among compliance-valid rows, 8 have a CI below 0 and none
  above. exp14's SLinput rows are INVALID-MANIPULATION (GaMS3 SL->EN compliance 0.00). The frozen all-rows rule
  outcome is also reported.
- **exp13 record** (`results/not_executed_exp13.{json,md}`): B/C overlap with exp14 is 116 and 55 items, and 288 were
  never generated, reproduced exactly.
- **Verification** (`results/verify.json`): 49/49 independent checks pass, including shuffled-label and
  shuffled-language placebos that behave as nulls.

These results feed the iteration-5 paper's audit / reconciliation section: the R-BASE paragraph, the C5a paragraph,
the decomposition table, the criterion-shift paragraph, the exp13 not-executed box and the correction boxes.
