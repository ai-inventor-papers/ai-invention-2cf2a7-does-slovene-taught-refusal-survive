# Does de-censoring hurt Slovene skills more? — RQ3 capability control (iter-3, exp 12)

This repository measures what an **English-objective Heretic abliteration edit** costs in *capability*, in English
vs Slovene (and Hungarian as a third language), for two sibling 12B models run through the same code path:
**GaMS3-12B-Instruct** (Slovene continued pre-training of Gemma 3) and **Gemma-3-12B-IT**, both in NF4.

The edit is compared with two controls on identical items: the **original** model, and a **norm-matched
random-direction edit**. The random edit is built through Heretic's own `abliterate()` with the *same* parameters
(rank, per-layer weights, modules); only the directions are random. It is the control that separates
"the refusal direction hurts X" from "any perturbation of this size hurts X".

**Headline numbers, gate verdicts and all tables are in [`results/RESULTS.md`](results/RESULTS.md).** It opens with
the findings summary (`results/findings.md`). Everything else in it is generated from `results/analysis.json`, which
`src/audit.py` re-derives independently (path B). Downstream artifacts should cite `results/gates.json`, which gives the
verdict per model × condition together with the adapter path and sha256 actually scored.

## Headline (details, CIs and caveats in `results/RESULTS.md`)

* **Gate:** no edit is catastrophic. On E_iter1 and E_art2 in both models and both languages, the macro
  headroom-normalised loss is ≤ 0.02 (95% upper bound ≤ 0.045). All λ ≤ 1.5 are OK. Gemma λ=2.0 is formally
  POSSIBLY_CATASTROPHIC because of one Slovene Winogrande cell sitting exactly on the 0.10 headroom floor (raw-pp change +0.25 pp).
* **Slovene is not hurt more than English.** A = H_SL − H_EN is positive (SL hurt less) for both edits in both models.
  The GaMS−Gemma interaction is I = +0.010 [−0.065, 0.074] (E_iter1). The resolution limit is ~0.10 of headroom.
* **The only localised cost is English ARC-C/BoolQ in GaMS**, −2 to −4 pp. It replicates across both edits and is absent in Gemma.
* **KL footprint:** the edit moves English next-token distributions more than Slovene or Hungarian ones. The multi-token
  EXCESS over random is 0.57 (GaMS) and 0.29 (Gemma), reproducing iter-1's C5a negative (0.574/0.298).
* **Fluency** (BPB on human text, language consistency, degeneracy) is essentially unchanged.
* Utility deltas of this size sit at the random-perturbation noise floor, and flips concentrate on near-tie items.
* Manipulation check: GaMS reproduces the logged Heretic KLs (−2.5%/−3%). Gemma's two structured edits both read +39–40%
  high, so Gemma E_iter1 is labelled UNVERIFIED. Batching and empty-system rendering were ruled out; the cause is unresolved.
  The adapter sha256 matches iter-1.

## What was done

| step | script | what |
|---|---|---|
| 1 | `src/prep_data.py` | 300 (+100 reserve) **row-paired EN/SL** items per task for ARC-C, BoolQ, HellaSwag, OBQA, PIQA and Winogrande. SL = `cjvt/slovenian-llm-eval@ca2f68d373`; EN = the HF originals rendered into the same `{query, choices, gold}` schema. Gold agreement is 1.000 in all 6 tasks; Winogrande is paired by `SL id − 23743 = EN row`, because row order gives only 0.50 agreement. Also: Belebele EN/SL/HU (200 items, paired by `(link, question_number)`); a fresh Dolly-15k harmless set (260; 8-gram/exact-deduplicated against harmless_alpaca, alpaca, and the iter-1/iter-2 sets); 150 FLORES passages per language; a zero-overlap audit against all 8 blocks of the dataset dependency `art_EG6OpEkGvysx`. |
| 1c | `src/prep_mt.py` | NLLB-200-distilled-1.3B (beam 4): EN→SL (SL-MT), SL→EN (EN-BT), EN→HU (HU-MT). Back-translation chrF medians are 71.9 (SL) and 73.6 (HU), passing the ≥60 gate. |
| 2 | `src/write_protocol.py` | `protocol.yaml` frozen (sha256 in `protocol.sha256`) and git-committed **before** any edited-condition forward pass. |
| 3–4 | `src/gpu_block.py` | Per model: ONE NF4 load through Heretic's `Model` class (iter-1's config verbatim). Every condition is a LoRA state swapped into the single adapter slot. Conditions: `orig`, `E_iter1` (iter-1 selected adapter), `E_iter1_l{0.5,1.5,2.0}` (lora_B × λ), `rand_nm_j1..5`, `rand_c6_j1`. A **manipulation check** reproduces iter-1's logged KLs. Utility runs through **lm-evaluation-harness 0.4.13** with custom local-subset YAMLs (`tasks/`). KL is computed at batch size 1. Also BPB, 128-token harmless generations, a second-path torch scorer, and a chat-template sensitivity check. |
| 6 | `src/analyze.py` | Headroom-normalised `H = (acc_cond − chance)/(acc_orig − chance) − 1`; macro over tasks with headroom ≥ 0.10; paired bootstrap (2,000 draws, same pair indices across conditions, languages and models); `A = H_SL − H_EN`; `I = A_GaMS − A_Gemma`; random-adjusted H; McNemar + Holm; **catastrophe gate**; λ gate curve; KL ratios + EXCESS vs random; BPB; language consistency and degeneracy (lingua). |
| 9 | `src/audit.py` | Independent recomputation (plain numpy) of every acc/H/macro/A/I/gate/KL/ratio. Three label-permutation placebos (model swap, language swap, condition swap), 1,000 permutations each. |
| 8 | `src/assemble_p0.py` | P0 table: RQ1 reused from iter-2 exp5 (cited); RQ2 from this round's artifact 4 if present (else PENDING); RQ3 from here. |
| 10 | `src/build_outputs.py`, `src/make_figs.py` | `method_out.json` (exp_gen_sol_out; per-item predictions for every model × condition), `results/gates.json`, `results/RESULTS.md`, figures. |

`method.py` runs all steps in order (`.venv/bin/python method.py`). How it actually ran on this pod (one L4, 6 h budget):
GaMS block 06:45–08:32 UTC, Gemma block 08:32–10:30, then two short resume passes (`logs/chain_after_gemma.sh`). Each
pass reloads the model, re-verifies the saved adapters by sha256, and skips every condition whose output file exists.

**E_art2** is artifact 2's B′ selection (`round-3/experiment-9/src/selected/<model>/adapter`). It was
written at 06:58 UTC, after the GaMS build and before the Gemma build. Gemma scores it inside its block. GaMS scores
its utility gate and KL in the first resume pass. Its own random controls (Heretic with artifact 2's parameters) were
not built for lack of time; the iter-1-parameter random edits serve as its random reference. `run_late_edits.sh`
re-scores anything still missing. Every deviation and cut is logged in `results/cuts.json`.

## Layout

```
method.py                 entry point (orchestrates src/*)
protocol.yaml / .sha256   frozen protocol (conditions, item sha256s, metrics, gate rule, cut order)
src/                      all code (see table above); tests/test_units.py = T0 unit tests (pytest -c pytest.ini)
tasks/                    lm-eval task YAMLs generated for the local item files (+ utils.py for Winogrande partial scoring)
data/util/                {task}_{en,sl}.jsonl  paired utility items (first 300 used; 'reserve' = next 100 in cut order)
data/belebele/            belebele_{en,sl,hu}.jsonl
data/harmless/            dolly_en.jsonl, harmless_mt.jsonl (+ mt_report.json)
data/fluency/             passages_{en,sl,hu}.jsonl (FLORES, human translations)
data/prep_report.json     pairing / gold-agreement / overlap audit;  data/manifest.json = sha256 of every item file
adapters/<model>/<cond>/  LoRA adapters actually scored (peft format + construction.json); E_iter1 is read in place from iter-1
results/items/            per-item raw outputs: util_*, utillam_*, bele_*, chat_*, scorer2_*, kl_*, bpb_*, gen_*
results/models/<model>/   conditions.json (adapter paths + sha256), manipulation_check.json, timing.json, KL continuations
results/screen/           original-model pilot (SCREEN, not confirmatory): timing, BOS, batch-vs-single check
results/analysis.json     every number;  utility_table.json, gates.json, kl_footprint.json, competence_covariates.json
results/audit.json        path-B recomputation + placebos;  p0_table.{json,md};  cuts.json;  RESULTS.md;  figs/
env/requirements.lock.txt exact package versions (uv pip freeze);  method_out.json (+ full_/mini_/preview_)
```

## How to run

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r env/requirements.lock.txt
export HF_TOKEN=...            # gated google/gemma-3-12b-it
.venv/bin/python method.py     # ~4 h on one 24 GB L4 GPU (NF4)
.venv/bin/python -m pytest -q -c pytest.ini tests/
```
Pod traps handled in code: there is no C compiler, so torch-native Triton ops are deregistered and `TORCHDYNAMO_DISABLE=1`
is set; `RLIMIT_AS` is never set; VRAM is capped with `set_per_process_memory_fraction(0.92)`.

## Kept artifacts (workspace paths)

* Adapters scored here: `./adapters/{gams3_it,gemma_it}/{E_iter1_l0.5,E_iter1_l1.5,E_iter1_l2.0,rand_nm_j1..5,rand_c6_j1}/`. Their sha256 values are in `results/gates.json` and `results/models/*/conditions.json`.
* E_iter1 (read-only, not copied): `../../../round-1/experiment-4/src/results/{gams3_it,gemma_it}/selected_adapter/`.

## Restoring removed files

`.aii/manifest.yaml` marks these as deletable after the round:

* `.venv/` (regenerable): `uv venv .venv --python 3.12 && uv pip install --python .venv/bin/python -r env/requirements.lock.txt`
* `.pytest_cache/` (regenerable): recreated by `.venv/bin/python -m pytest -q -c pytest.ini tests/`.

Model weights and datasets live in the shared HF cache outside this repo. They are re-downloaded on first use:
`huggingface-cli download cjvt/GaMS3-12B-Instruct --revision 1d0b27af5748784482600d24779409e7e1dc9adc`,
`huggingface-cli download google/gemma-3-12b-it --revision 96b6f1eccf38110c56df3a15bffe176da04bfd80`,
`huggingface-cli download facebook/nllb-200-distilled-1.3B` (or run `src/download_models.py`). The datasets (`cjvt/slovenian-llm-eval`,
`allenai/ai2_arc`, `aps/super_glue`, `Rowan/hellaswag`, `allenai/openbookqa`, `baber/piqa`, `allenai/winogrande`,
`facebook/belebele`, `databricks/databricks-dolly-15k`, `mlabonne/harmless_alpaca`, `tatsu-lab/alpaca`) are
fetched by `datasets.load_dataset`. The item files built from them are in `data/` with sha256 values in `data/manifest.json`.
