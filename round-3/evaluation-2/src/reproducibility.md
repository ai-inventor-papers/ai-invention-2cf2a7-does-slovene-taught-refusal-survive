# Reproducibility — exp8 readout repair (iter-3 evaluation_2)

This describes **what was actually run**, in order, on Ubuntu with one NVIDIA L4 GPU.

## 0. What this evaluation does
Re-judges the 24,000 responses that experiment 8 (`art_T5ChU9GV1tf7`) saved, with characterised open-weight judges and a
blind author-model adjudication, and recomputes the "de-censoring hits Slovene harder" lag (G3) that exp8 read off a keyword
lexicon. It generates **no new model outputs**. It ran in **MODE L** (local judges primary) because the shared OpenRouter
run budget was exhausted; **$0 of API spend**.

## 1. Copy the artifact folder
```bash
cp -r <this folder> ~/readout_repair && cd ~/readout_repair
```
All read-only inputs live at absolute paths under
`../../../round-2/` (exp5, exp7, exp8, evaluation_1) and
`.../iter_1/gen_art/gen_art_dataset_1`; `src/common.py` hard-codes them. On a fresh machine, place those dependency
workspaces at the same paths (or edit the constants in `src/common.py`).

## 2. System + Python
- Ubuntu (Linux 6.8), NVIDIA L4 (23 GB VRAM), CUDA driver 580.x, 48 vCPU, ~500 GB RAM.
- Python 3.12 via `uv`. Do **not** use `pip` directly; `uv` only.
```bash
uv venv .venv --python=3.12
uv pip install --python .venv/bin/python -r pyproject.toml
```
Exact versions actually installed (also pinned in `pyproject.toml`): torch==2.14.0, transformers==5.17.0,
tokenizers==0.23.2, safetensors==0.8.0, huggingface-hub==1.32.0, bitsandbytes==0.50.2, accelerate==1.15.0, numpy==2.5.3,
scipy==1.18.1, pandas==3.0.6, pyarrow==25.0.1, statsmodels==0.15.0, scikit-learn==1.9.1, aiohttp==3.14.3, loguru==0.7.3,
matplotlib==3.11.2, PyYAML==6.0.3, tenacity==9.1.4, sentencepiece==0.2.2, protobuf==7.36.2.

## 3. Models / downloads / env vars (names only)
Judges are downloaded from HuggingFace into the run's shared cache (env vars **already set**; do not override):
`HF_HOME`, `HF_HUB_CACHE`, `HF_DATASETS_CACHE`, `HF_TOKEN`. Weights:
```bash
hf download Qwen/Qwen3-14B --revision 40c069824f4251a91eefaf281ebe4c544efd3e18
hf download mistralai/Mistral-Small-24B-Instruct-2501 --revision 9527884be6e5616bdd54de542f9ae13384489724
hf download cjvt/GaMS3-12B-Instruct --revision 1d0b27af5748784482600d24779409e7e1dc9adc   # tokenizer only (shared Gemma-3 tokenizer)
```
`OPENROUTER_BASE_URL` / `OPENROUTER_API_KEY` are read only for the start-up key probe (which returned budget-exhausted →
MODE L); no paid call is made. No secret values appear in any file.

## 4. Exact commands, in order
Seed 20260925 throughout. Protocol frozen (`protocol.yaml` + `protocol.sha256`) and git-committed **before** the first label.
```bash
# STEP 0 — master table (request text, resp64/resp128 under the Gemma-3 tokenizer, all archived labels), frozen frames,
#          blind adjudication file. ~4 min. Verifies GaMS/Gemma tokenizers identical on 20/20 strings.
.venv/bin/python src/build_master.py

# STEP 1 — local judges (NF4, first-token argmax; resumable append-only labels/<judge>.jsonl). One L4, ~90 min total.
.venv/bin/python src/judge_local.py --judge qwen3_14b  --sets calib,adjudication,B_all,A1_native,origharm_native,A1_64,orig_64,e7H
.venv/bin/python src/judge_local.py --judge mistral24b --sets calib,adjudication,sample25
# Coverage actually obtained (time-boxed on one GPU): Qwen3-14B judged calib(973)+adjudication(237)+B(11263)+A1(5700)
#   +orig/harmless(1798)+A1@64(3648 of 5486); Mistral-24B judged calib(973)+adjudication(237)+sample25(1355 of 4155).

# BLIND ADJUDICATION (done by the executing LLM agent, NOT a human): read adjudication/blind_items.jsonl (uid, request,
#   response, language only) and write adjudication/author_labels.json BEFORE opening any label file for those rows.

# STEPS 2-7 — characterise readout, recompute lag, B-vs-A1 decomposition, tipping point, cross-artifact SDT meta,
#             placebos, outputs. EVAL_NBOOT bootstrap draws (1000 in the committed run; the protocol specifies 2000). ~4 min.
EVAL_NBOOT=1000 .venv/bin/python eval.py

# READOUT_REPAIR.md + independent second code path
.venv/bin/python src/gen_readout_repair.py
.venv/bin/python src/rederive.py

# validate + mini/preview
SKILL=/ai-inventor/.claude/skills/aii-json
$SKILL/../.ability_client_venv/bin/python $SKILL/scripts/aii_json_validate_schema.py --format exp_eval_sol_out --file "$PWD/eval_out.json"
$SKILL/../.ability_client_venv/bin/python $SKILL/scripts/aii_json_format_mini_preview.py --input "$PWD/eval_out.json"
```
`finalize.sh` bundles the STEP 2-7 → validation block.

## 5. Outputs a reader should get, and where they appear
- `results/eval_results.json` — all numbers. Headline block `headline_summary`; per-curve lag in `step3_lag`.
- `READOUT_REPAIR.md` — every iter-1/2 number → validated replacement + status.
- `judge_error_matrices.json` — per judge×model×language Se/Sp (reusable by other iter-3 artifacts).
- `eval_out.json` (+ `full_`/`mini_`/`preview_`) — exp_eval_sol_out; per-row labels as `predict_*`, headlines in `metrics_agg`.
- `work/items_relabelled.jsonl.gz` — every row × truncation with all labels. `work/rederive.json` — second code path.
- `figures/` — transfer curves per readout, forest of G3, tipping-point contour, meta forest.

### Numbers to expect (committed run, EVAL_NBOOT=1000)
- **B lexicon G3 = −2.36 [−3.16, −1.64]** — reproduces exp8 exactly (unit test `exp8_lexicon_B_reproduced`).
- **B under Qwen3-14B (primary), REFUSE coding**: integrated gap IG = **−1.95 [−3.75, −0.78]** (LAG). Support rule fails
  (Gemma B English refusal rarely <50%), so IG/x*_joint are the pre-registered support-robust co-primaries; G3@50% is extrapolated.
- **B under PARTIAL-as-refusal**: INCONCLUSIVE (CI includes 0) → the lag is fragile to the REFUSE/PARTIAL boundary.
- **A1 under Qwen3-14B**: IG = **−0.47 [−1.86, 0.26]** INCONCLUSIVE (shrinks toward 0).
- **C-LAG screen holds = False** (requires negativity, CI excluding 0, under both codings and after RG correction).
- **Bias tipping point (B)**: ~0.71 extra Gemma-SL false-REFUSE needed to reach −m (0.85 to reach 0) vs measured
  differential ~0.003 → the lag is not explained by judge SL→REFUSE bias.
- **exp5 HARD DiD_c = +0.52 [0.39, 0.67]** — criterion-shift replicated (Step 6 S1); pooled RE-HKSJ DiD_c ≈ +0.52.

### Independent re-derivation / placebos (audit)
- `src/rederive.py` recomputes B and A1 G3 via a **separate numpy Newton-Raphson GLM** reading only `labels/*.jsonl` +
  `work/master.parquet`: point estimates match the main (imported-estimator) path to **<2e-9** (`work/rederive.json →
  comparison_to_main`). CI endpoints differ because rederive uses an item-only bootstrap for A1 vs item+step in the main path.
- Placebos (`step7_placebos`): model-label swap within trial index → mean −0.008 (centred); language-label swap within
  item×step → 0.07 / 0.03 (small). Paired permutation p is in `step3_lag.B.primary_R.permutation`.
- Unit tests (`unit_tests`): Hautus, Rogan-Gladen, kappa-vs-sklearn, and G3=0 on a synthetic lockstep curve all pass.

## 6. Notes / limits
- Reference labels are **author-model adjudication (an LLM agent), not human**; every error table says so.
- No native-speaker Slovene check (carried as a limit). NF4 judges are reduced precision.
- On torch≥2.14 without a C compiler, `src/judge_local.py` applies the `deregister_op_overrides` trap from iter-2.
- Process control is PID-based only; never kill/monitor judges by name (other runs share the box).
