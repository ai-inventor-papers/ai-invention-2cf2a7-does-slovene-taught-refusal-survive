# Reproducibility

This describes what was **actually run** on 2026-09-24, including the two places where the platform's API key limit forced
a substitution. Every path below is **relative to this artifact's folder**; no absolute server path is needed or usable.

## 1. Getting this artifact

This folder is published as one directory of a public GitHub repository, alongside the other artifacts of the same run.

```bash
git clone <the run's repository URL>
cd <repo>/3_invention_loop/iter_4/gen_art/gen_art_evaluation_3
```

The sibling folders this artifact **reads** (read-only, never written) are, by artifact id:

| id | published sibling folder | what is read |
|---|---|---|
| `art_T5ChU9GV1tf7` (exp8) | `../../../iter_2/gen_art/gen_art_experiment_8` | `results/items_final.jsonl`, `results/judge_labels.jsonl`, `data/probe_P200.jsonl`, `src/common.py`, `src/analysis.py`, spot-check files |
| `art_n3Crj0p24sBa` (exp9) | `../../../iter_3/gen_art/gen_art_experiment_9` | `results/items_final.jsonl`, `data/probe_P300.jsonl`, `data/twins_T150.jsonl`, `results/adjudication_rubric.md`, `src/stats_core.py`, `judge_model/mdeberta_gemini_distill/` |
| `art_sfQmnafZ153j` (exp10) | `../../../iter_3/gen_art/gen_art_experiment_10` | `results/test/*/addon.jsonl`, `results/adjudication_*`, `src/analysis.py` |
| `art_Aw3AXCXv9pUg` (exp11) | `../../../iter_3/gen_art/gen_art_experiment_11` | `results/rows_final.parquet`, `results/adjudication/*`, `data/items.jsonl`, `src/analysis.py` |
| iter-3 evaluation 2 | `../../../iter_3/gen_art/gen_art_evaluation_2` | `work/master.parquet`, `work/items_relabelled.jsonl.gz`, `adjudication/*`, `labels/*`, `src/stats_core.py` |
| exp12 | `../../../iter_3/gen_art/gen_art_experiment_12` | `results/gates.json` (catastrophe gate, cited only) |

`src/common.py` resolves all of these from **one constant**, `RUNS`, anchored on `Path(__file__)`:
`RUNS = Path(__file__).resolve().parents[4]` would point at the published `3_invention_loop/` directory. In the version
that ran on the server `RUNS` is the absolute run directory; **a reader must set `RUNS` to their clone's
`3_invention_loop/` directory** (or export `AII_RUNS=/path/to/clone/3_invention_loop`) before running `src/build_frame.py`.
Nothing else in the code refers to a machine-specific path.

There is **no private user-uploaded input** in this artifact: everything it reads is either a published sibling folder or
a public model/prompt. (The run's `user_uploads/` planning document is not read by this code.)

## 2. Environment

Ubuntu 22.04, Python 3.12, one NVIDIA L4 (23 GB VRAM), 48 CPU cores, 503 GB RAM. GPU is needed only for the two local
model steps (NLLB translation and the J1 judge); everything else is CPU-only.

```bash
uv venv .venv --python=3.12
uv pip install --python .venv/bin/python \
  pandas==3.0.6 pyarrow==25.0.1 numpy==2.5.3 scipy==1.18.1 statsmodels==0.15.0 scikit-learn==1.9.1 \
  aiohttp==3.14.3 sacrebleu==2.6.0 transformers==4.57.6 torch==2.14.0 sentencepiece==0.2.2 \
  loguru==0.7.3 PyYAML==6.0.3 protobuf==7.36.2 matplotlib==3.11.2 tenacity==9.1.4 psutil==7.2.2
```

`protobuf` is required by the mdeberta tokenizer used in step 7; it was installed mid-run after that step first failed.

## 3. Downloads, environment variables and keys

- **Environment variables (names only, never values):** `OPENROUTER_BASE_URL` and `OPENROUTER_API_KEY` for every paid
  call. Requests **must** carry a `User-Agent` header — the proxy in front of the base URL rejects UA-less requests with
  an HTML 403 from Cloudflare, which looks like an auth failure but is not.
- **Models downloaded:** `facebook/nllb-200-distilled-1.3B` (`huggingface-cli download facebook/nllb-200-distilled-1.3B`),
  cached in the run's shared HF cache via the pre-set `HF_HOME`/`HF_HUB_CACHE`; never override these.
- **Judge models called through OpenRouter:** `google/gemini-2.5-flash-lite`, `google/gemini-2.5-flash`,
  `openai/gpt-4.1-mini`, `anthropic/claude-sonnet-4.5`.
- **No checkpoint is downloaded for the J1 judge:** it is reassembled from the exp9 sibling folder's
  `judge_model/mdeberta_gemini_distill/model_parts/` and its sha256 is checked against that manifest.

## 4. Commands, in the order they were run

Seed `20260926` everywhere; `B = 2000` for raw curves and `1000` for corrected ones.

```bash
# 0. freeze (before any paid call)
sha256sum protocol.yaml > protocol.sha256 && git add protocol.yaml protocol.sha256 src vendor && git commit -m "Freeze protocol"

cd src
# 1. row frame over the four artifacts + the C1 verification   (~30 s)
../.venv/bin/python build_frame.py
# 2. judge-tier bake-off + archived-label drift check          (~40 s, $0.14)
../.venv/bin/python bakeoff.py
# 3. cost projection -> triggers the pre-registered cut ladder (AM1)
../.venv/bin/python label_passes.py project
# 4. primary pass, priorities 1-2                              (~5 min, $2.18, 25,025 calls)
../.venv/bin/python label_passes.py primary 2
# 5. second family                                             (~4 min, $1.12, 9,888 calls)
../.venv/bin/python label_passes.py second
# 6. NLLB translation + round-trip control                     (~27 min on the L4)
../.venv/bin/python nllb_ttj.py
# 7. translate-then-judge labels with exp9's J1 (AM2)          (~10 min on the L4)
../.venv/bin/python ttj_judge_j1.py
# 8. StrongREJECT ASR                                          ($0.30; stopped at 1,108/5,800 by the platform key limit)
../.venv/bin/python label_passes.py asr
# 9. blind adjudication                                        ($0.61; 285/480 by API, the rest by the executing agent, AM2)
../.venv/bin/python adjudicate.py sample
../.venv/bin/python adjudicate.py run
cd ..
# 10. analysis, figures, outputs                               (~5 min, no spend)
.venv/bin/python eval.py
# 11. independent audit path
.venv/bin/python src/rederive.py
```

Total paid spend **$4.31**, against this artifact's own $8.00 hard stop. The run ended early because the *platform's*
shared key reached its daily limit (`GET /key` reported `limit 12.0, usage 11.80`), which returns HTTP 403
`aii_openrouter_key_limit`. Reproducing steps 8-9 in full needs roughly **$1.9 more** than was spent here.

### What changed mid-run (all in `amendments.jsonl`, each committed before the affected work)

- **AM0** — no judge tier passed the pre-registered Se/Sp ≥ 0.80 gate against the *prior* adjudications (specificity
  0.43-0.66 on edited rows). `gemini-2.5-flash` was chosen by the frozen fallback rule (higher `min(Se, Sp)`), and every
  headline carries the flag *"primary tier failed bake-off"*. Its drift kappa against the archived exp8 gemini labels was
  0.97 (3-way), which cleared the ≥ 0.90 reuse rule, so ~11.9k archived Gemma labels were reused rather than repaid.
- **AM1** — the cost projection came to $8.30 > $7.50, so the pre-registered cut ladder was applied in order (exp8 B GaMS
  rows to a 30 % item sample; Hungarian rows dropped; TTJ restricted to bracket steps plus λ = 0).
- **AM2** — the platform key limit. ASR stopped at 1,108 rows, the paid TTJ pass never ran (replaced by exp9's J1 judge on
  the same NLLB translations, with J1 also applied to the direct rows so R-JUDGE compares one instrument with itself),
  195 adjudication rows were labelled by the executing agent instead of the API adjudicator, and the pre-registered
  temperature-0.7 intra-rater retest was replaced by a 40-row **inter**-adjudicator overlap.

## 5. Outputs a reader should get, and where they appear

| file | what it holds |
|---|---|
| `results/tier_bakeoff.json` | per-tier Se/Sp against prior adjudications, drift kappa, the chosen tier and its flag |
| `results/judge_error_matrices_v2.{json,md}` | per-cell Se/Sp with Wilson CIs for **every** instrument (paid gemini, gpt-4.1-mini, TTJ, J1, J2, Qwen3-14B, Mistral, lexicon), prevalence, OFF_TASK share, the kappa gate and the gate verdict |
| `results/recompute.json` | G3, G3_orig, G3_edit, IG, slopes, MDE and verdicts per curve × readout × coding, plus rivals, tipping, HKSJ pooling, placebos, blocked-row bounds and sanity |
| `results/rederive.json` | the independent audit: each headline recomputed through a different code path, with pass/fail per check |
| `results/smoke_tests.json` | reproduction of each artifact's archived headline from its archived label column |
| `READOUT_v2.md` | the table the paper quotes from: every old number → its validated replacement, CI, gate status and SURVIVES/SHRINKS/REVERSES/UNCITABLE |
| `labels/readout_rows.jsonl.gz` | one row per generation: response, every judge's label, the TTJ translation and label, ASR fields, adjudication and weights |
| `eval_out.json` (+ `full_`/`mini_`/`preview_`) | the `exp_eval_sol_out` schema view of the same numbers |
| `figures/fig1…fig4` | curves under each readout, the G3/G3_edit forest plot, the Se/Sp table, the tipping plot |

The paper's headline claims come from `READOUT_v2.md` (the status column), the gate table in
`results/judge_error_matrices_v2.md`, and the pooled HKSJ rows of `results/recompute.json → pooling`.

### Determinism

The label passes are cached by `sha1(judge | prompt_sha | content)` in `labels/ledger.jsonl`, so re-running them re-reads
the ledger and spends nothing. `eval.py` is fully deterministic given the ledger and the adjudication files (seed
20260926). Two things are **not** bit-reproducible: the paid judges themselves (a re-run against the live API may return
different labels — this is exactly what the drift check measures), and the 195 agent-adjudicated rows, which are a
recorded human-in-the-loop-shaped artifact of this session and are shipped as data in `adjudication/labels.jsonl`
rather than regenerated.
