# Reproducibility

This folder is **one directory of a public GitHub repository** (the AI-Inventor run `run_FVi3e3O9CH5I`). A reader has
only that repository — never this server — so every path below and in the code is **relative to this folder**, and the
few inputs produced by other artifacts are read from **sibling directories of the same repository**, named by artifact id.

## 1. Get the artifact
```bash
git clone <this-repository-url>
cd <repo>/round-4/experiment-14/src   # this folder
```
Sibling artifacts this code reads (read-only), by id — each is a sibling folder in the same clone:
* `gen_art_experiment_9` (iter-3): the Heretic edit adapters (`selected/{gemma_it,gams3_it}/adapter`), the norm-matched
  random-direction control (`adapters/{model}/rand_1`), and the J1 judge (`judge_model/mdeberta_gemini_distill/`).
* `gen_art_experiment_11` (iter-3): source of the copied hook / NLLB / `stats_core` code (provenance in
  `results/provenance_code.json`).
* `gen_art_experiment_8` (iter-2): the verbatim P1 judge prompt.
* `gen_art_evaluation_2`, `gen_art_experiment_10`, `gen_art_experiment_11` (iter-3): the 562 previously-adjudicated
  calibration rows.
* `gen_art_dataset_1` (iter-1, id `art_EG6OpEkGvysx`): RefusEU eval prompts used only as a dedup target.
The code resolves these through the single constant `RUN` in `src/common.py` (currently an absolute run path). To run
from a clone, set `RUN` to the repository's `3_invention_loop` directory (or export `AII_RUN_ROOT` and point `common.RUN`
at it). No file the user uploaded is used; nothing here depends on private uploads.

## 2. Environment (Ubuntu, exactly what was installed)
* Python 3.12; `uv` (no pip). `uv sync` builds `.venv` from `pyproject.toml` + `uv.lock` (full freeze in
  `requirements.lock.txt`). Key pins: torch 2.14.0+cu130, transformers 4.57.6, bitsandbytes 0.50.2, peft 0.21.0,
  accelerate 1.15.0, sentencepiece, sacrebleu, lingua-language-detector 2.2.0, statsmodels 0.15.0, scikit-learn 1.9.1,
  openai 3.19.2.
```bash
uv sync            # or: uv venv .venv --python 3.12 && uv pip install -r requirements.lock.txt
```

## 3. Model / data downloads and secrets (by NAME only)
* HuggingFace weights (into `$HF_HOME`, NOT this folder), pinned revisions in `results/inputs_check.json`:
  `google/gemma-3-12b-it@96b6f1ec`, `cjvt/GaMS3-12B-Instruct@1d0b27af`, `p-e-w/gemma-3-12b-it-heretic@e037e6e1`,
  `facebook/nllb-200-distilled-1.3B`. `restore.sh` downloads all four.
* J1 judge: reassembled from the sibling artifact's `model_parts/` (sha256-verified) into `judge_model/j1/` on first use.
* External pools fetched at build time: HarmBench / StrongREJECT / AdvBench canonical CSVs (the HF mirrors are gated;
  `src/build_pool.py` logs the GitHub sources + sha256 into `data/pool_manifest.json`), JBB-Behaviors from HF.
* API: OpenRouter via env vars `OPENROUTER_BASE_URL` and `OPENROUTER_API_KEY` (names only; never commit values). Used
  only for judge calibration and the benign-twin writer. **During this run the shared platform key hit its daily cap**
  (`403 aii_openrouter_key_limit`); the pipeline fell back to the local J1 judge (amendment A4) and still completes.

## 4. Commands actually run, in order (seed 20260926; one NVIDIA L4, 23 GB)
```bash
export HF_HUB_OFFLINE=1 AII_DEV_JUDGE=j1
cd src
../.venv/bin/python preflight.py            # dependency + sha + HF-pin + OpenRouter smoke
../.venv/bin/python build_pool.py           # external harmful pool + dedup  (~1 min)
../.venv/bin/python twins.py                # 60 benign twins (paid, before the key cap)  (<$0.02)
../.venv/bin/python build_items.py --mode items,aux   # NLLB SL/HU MT + chrF + DEV/KL/suffix  (GPU, ~3 min)
../.venv/bin/python calib.py                # paid judge-tier calibration (562 rows)  (~$0.12)
../.venv/bin/python freeze.py               # write+hash+commit protocol.yaml  (BEFORE any grid row)
../.venv/bin/python gen.py --model gemma_it --phases mini,dev,kl,grid   # ~1.5 h GPU
../.venv/bin/python judge_j1.py --mode label --models gemma_it          # J1 labels (~80 s)
../.venv/bin/python gen.py --model gams3_it --phases mini,dev,kl,grid   # ~0.7 h GPU
../.venv/bin/python gen.py --model pew_heretic --phases ext             # C-EXT, ~15 min GPU
../.venv/bin/python build_items.py --mode ttj --models gemma_it,gams3_it,pew_heretic --only_edited  # NLLB reply->EN
../.venv/bin/python judge_j1.py --mode label,ttj --models gemma_it,gams3_it,pew_heretic
# blind adjudication frames (executor model, NOT human):
../.venv/bin/python adjudicate_frame.py --mode draw --models gemma_it --tag g
../.venv/bin/python adjudicate_frame.py --mode draw --models gams3_it --tag s
../.venv/bin/python adjudicate_frame.py --mode draw --models pew_heretic --ext pew_heretic --tag x
#   -> read adjudication/blind_items_<tag>.jsonl, write adjudication/author_labels_<tag>.json
../.venv/bin/python build_table.py && ../.venv/bin/python analysis.py
../.venv/bin/python rederive.py && ../.venv/bin/python figures.py
../.venv/bin/python make_report.py && ../.venv/bin/python make_outputs.py
../../.venv/bin/python -m pytest -c ../pytest.ini ../tests/
```
`run_chain.sh` bundles the GaMS→C-EXT→TTJ GPU steps (used because they run unattended after the Gemma grid). Every
generation and label job is append-only and resumable by row key; total wall time ~3 h GPU + analysis.

## 5. What a reader should get
* **Headline (Gemma-3-12B-IT): the residual Slovene refusal follows the REPLY language, not the prompt (M-OUT).**
  `results/analysis.json` → `readouts.raw_R`: `OUT_SL|gemma_it` ≈ +1.14 [0.60, 1.56], `IN_SL|gemma_it` ≈ −0.60
  [−1.02, −0.18] (logit, 95% item-bootstrap CI). Confirmed judge-independently by the blind adjudication
  (`gold_out_vs_in.gemma_it`: non-English reply ≈ 0.50 vs English reply ≈ 0.33 refusal). Not "robust" under the
  degenerate Rogan-Gladen correction (paid judges were blocked); PPI++ keeps the sign. These are the abstract/headline.
* `results/RESULTS_tables.md` and `RESULTS.md` are generated from `results/analysis.json` (no hand-typed numbers);
  `results/audit.json` re-derives every headline independently (checks < 1e-6) and shows the placebos centre at 0.
* Figures F1–F6 in `figures/`; per-example generations + labels in `method_out.json` (schema `exp_gen_sol_out`).
