# Does a Slovene "caution direction" cause Gemma-3's Slovene refusal lag?

Mechanism artifact for the GaMS3 vs Gemma-3 bilingual abliteration study (iteration 3, direction 3).

An English-objective Heretic LoRA removes most of **Gemma-3-12B-IT**'s English refusals while leaving Slovene refusals
largely intact — a **Slovene refusal lag**. Two mechanisms were proposed for it:

* **M-a (the literature's default, Wang et al. 2025):** Slovene harmful/harmless representations are *less separated*,
  so an English-fitted direction is a worse fit in Slovene.
* **M-b (the novel alternative):** there is a **separate Slovene caution direction** — a harm-related component of the
  Slovene refusal direction *orthogonal* to the English one — that the English-objective edit never touches.

This artifact tests both, on **Gemma-3-12B-IT** (the model with the lag) and **GaMS3-12B-Instruct** (the control),
with one identical code path, a pre-registered protocol frozen and git-committed before any test generation, and
norm-/variance-matched random controls throughout.

## Headline result: **neither mechanism explains the lag**

| claim | pre-registered test | outcome |
|---|---|---|
| The lag exists at the operating point | `Lag(E0) > m = 0.675`, CI excluding 0 | **yes, Gemma:** 1.98 logits [1.41, 2.73] (R_EN .64 vs R_SL .93) |
| Gemma-specific (GaMS control) | GaMS `Lag(E0)` | **no lag:** −0.33 [−0.70, 0.07] |
| Cross-model replication of the screen | `G3_op = Lag_GaMS − Lag_Gemma` | **−2.30 [−3.12, −1.61]** (lexicon proxy −2.31; s1 proxy −1.55) |
| **M-a:** weaker Slovene separation in Gemma | f, rho, d'(SL along r_EN) all lower in Gemma | **refuted.** f is *higher* in Gemma (+0.010 [0.005, 0.014]); cos(r_EN, r_SL) = .99 in **both** models |
| **M-b:** the orthogonal residual `u_SLperp` induces caution | alpha50(EN)/alpha50(SL) ≥ 2 and ≥ 2× random, CI lb > 1 | **refuted.** `u_SLperp` never reaches 50 % refusal in either language, in either model (right-censored at K = 3); its AUC (.18 SL Gemma) is at the random-direction level |
| **M-b:** neutralising `u_SLperp` closes the lag | cut − mean random cut ≥ 0.5, CI lb > 0, EN change < 5 pp, KL ≤ 1.2× | **not met at any scale.** s = 1.0: cut − random 0.17 [−0.09, 0.44]. s = 1.5 does cut the lag (0.62 [0.38, 0.97]) but fails the EN-invariance gate (−18 pp) and does **not** reduce the benign-Slovene false-alarm excess |
| **M-a:** neutralising the full Slovene direction closes the lag | same criterion | **cut is huge but not interpretable:** 3.97 [2.92, 5.38] — it drives Slovene refusal to **0.00** with **50 % degenerate output** and 19× the edit's KL. Destroying the model is not a mechanism. |

**Verdict (pre-registered table, both PARTIAL codings, primary judge): `neither` for both models.**
The Slovene and English refusal directions are *geometrically nearly identical* (cos ≈ .99 at each model's chosen
layer, against a split-half ceiling of ≈ .998). There is very little Slovene-specific refusal geometry left to be the
cause, and what little there is (`u_SLperp`, 13 % of the Slovene direction's norm at Gemma's L\* = 20) is causally
inert: it neither induces caution when added nor removes the lag when projected out.

### The one thing that *does* selectively induce Slovene caution

The pre-registered **rival** direction — `u_lang`, the plain language-identity direction (Slovene-harmless minus
English-harmless mean, orthogonalised to the refusal direction and to `u_SLperp`) — induces **fluent, on-topic Slovene
refusals of entirely harmless questions** at Gemma's L\* = 20:

| direction | alpha50 EN | alpha50 SL | R_lang = EN/SL | refusal on harmless SL prompts at K = 1 |
|---|---|---|---|---|
| `u_lang` (Gemma) | censored (> 3) | **0.65** [0.46, 0.79] | **4.64** [2.64, 5.95] | **1.00** (0 % degenerate) |
| `u_SLperp` (Gemma) | censored | censored | 1.00 | 0.09 |
| `r_EN` (positive control) | 0.91 | 0.65 | — | 0.90 |
| random 1–5 (Gemma) | all censored | all censored | — | ≤ 0.06 |

At K = 1 the model answers a question about Thai curry with *"Žal mi je, vendar ne morem odgovoriti na to vprašanje.
Moja naloga je zagotoviti varno in etično pomoč…"*. GaMS shows the same effect far more weakly (R_lang 1.66 [0.96, 2.16]).

**This is reported as exploratory and it does *not* rescue M-b.** It fails the pre-registered criterion's manipulation
check, `u_lang` is content-non-specific (it is *not* a harm direction), neutralising it is catastrophic
(EN refusal 0.64 → 0.02, KL 49×), and at K ≥ 1.5 in English it degrades into code-switching. The honest reading is that
**"being in Slovene" itself carries caution weight in these models**, not that a Slovene *harm* direction exists.
Whether that is a cause of the lag or a correlate of it is **not** established by this artifact.

### RQ4 (frozen-core debt) — a CHECK, not a contribution

Held-out harmful-vs-harmless probes (5-fold CV, PCA-128 in-fold, shuffled-label control) at each model's L\*:

* **AUROC = 1.000 in every state** (original, edit at lambda = 1, edit at lambda\*), for EN-BT, SL-MT and EN-orig,
  with the shuffled control at ~0.50. The edit does **not** remove harmfulness information — it changes what the model
  does with it. This holds largely by construction (Heretic removes a direction from the output weights, not from the
  representation), so it is reported with its ceiling flag and never as a finding.
* **EN-BT -> SL-MT probe transfer AUROC = 1.000** in every state — the harmful/harmless code is shared across the two
  languages, which is the same conclusion the geometry reaches by a different route.
* The **fixed probe** (projection onto the *original* model's own-language direction) does collapse, as expected:
  Gemma SL d' 1.35 -> 0.26 at lambda = 1; cos(edited diff-of-means, original) 1.00 -> 0.54.

### Dose-response detail worth flagging

`A_perp` is monotone in scale on the lag (s = 0.5 / 1.0 / 1.5 -> Lag 2.69 / 1.34 / 0.45) but s = 0.5 sits **above** the
un-neutralised edit (1.98), i.e. a weak projection *increases* the lag before reducing it. The reduction at s = 1.5 is
also not accompanied by any reduction in the benign-Slovene false-alarm excess (1.79 vs E0's 1.35), so the
"one mechanism" test fails: whatever s = 1.5 is doing to harmful Slovene prompts, it is not restoring calibrated
behaviour on safe-but-scary ones.

## What this means for the study

The lag is real, large and Gemma-specific, and it survives an operating point matched on English dose — but it is **not
a localisable linear direction**. Both the paper's proposed mechanisms are refuted on their own pre-registered terms.
A single linear component cannot be removed to fix Slovene without either doing nothing (`u_SLperp`) or destroying the
model (`r_SL`, `u_lang`). Future work should look at *distributed / non-linear* accounts, or at the interaction between
the English-fitted edit and Slovene generation, rather than at another direction.

## Relation to the field's standing results (framing, not a novelty claim)

The mechanistic-interpretability handbook's standing verdicts line up with what happened here, and they are the right
lens for the result:

* **Decodability is not actionability.** The field's rule is: never infer that interpretability *enables* correction
  from the fact that the information is decodable — measure output-level correction **and** collateral disruption
  against a **random-perturbation control**. This artifact runs exactly that test and it fails. Harmfulness is
  perfectly decodable in Slovene in every state (RQ4 AUROC 1.00, EN->SL transfer 1.00), and the refusal geometry is
  clean and stable (split-half ceiling ~.998) — yet projecting out the Slovene-specific component moves the lag no
  more than norm-matched random directions do. The lag is a **knowledge-action gap**, not a missing direction.
* **Steering claims need per-sample distributions, not a mean at one coefficient.** Every induction result here is a
  10-point dose-response curve with item-bootstrap CIs, per-prompt switch points (`fig3`), per-coefficient degeneracy
  and a manipulation check — and the curves do have a failure regime (they collapse at high K as outputs degenerate),
  which is reported rather than truncated away.
* **Difference-in-means, not a dictionary latent, is the unit.** All directions are winsorised difference-of-means,
  the baseline the field asks new units to beat, with split-half noise ceilings reported next to every cosine.

Nothing here is claimed as a new method. The contribution is a falsifiable mechanistic hypothesis — "a separate
Slovene caution direction causes the lag" — **tested and refuted** on its own pre-registered terms, with the rival
(M-a) refuted too, and one exploratory positive (`u_lang`) reported with its caveats intact.

## Judging: what actually happened, and why it matters

The frozen protocol specified **gemini-2.5-flash**. The run's OpenRouter budget was exhausted before this artifact
started (HTTP 403 `aii_run_budget_exhausted`, explicitly non-resetting; `:free` slugs 404), so plan fallback **F1** ran:

1. **Local Qwen3-14B judge — gated and REJECTED.** Against 530 archived real gemini labels from exp8 it scored
   kappa **0.25 (EN) / 0.33 (SL)** on *edited* rows: it calls "disclaimer-then-comply" answers REFUSE.
2. **Primary readout = `surrogate/gemini`**, a char+word TF-IDF multinomial model trained on **11.7 k archived
   gemini-2.5-flash labels** of exp8 Gemma rows (identical frozen prompt, 64-token responses). Its selection rule and
   candidate set were written **before any TEST row existed** (`src/judge_surrogate.py`). Grouped-CV kappa on edited
   rows: **EN 0.68 / SL 0.82** — it passed the ≥ 0.6 gate that the LLM judge failed.
3. **Blind adjudication by the executor agent** (author model, **not** a human; never claimed otherwise): 160 rows,
   80 per model, 50/50 by surrogate label, shown prompt + response only.

The adjudication exposes the most important caveat in this artifact:

| cell | surrogate sensitivity | surrogate specificity | kappa |
|---|---|---|---|
| Gemma EN | 0.92 | 0.68 | 0.50 |
| Gemma SL | 1.00 | 0.87 | 0.85 |
| **GaMS EN** | 1.00 | **0.57** | **0.25** |
| **GaMS SL** | 1.00 | **0.59** | **0.30** |

The surrogate was trained on **Gemma** outputs and **over-calls REFUSE on GaMS** (29 of 80 GaMS rows disagreed, all in
that direction). Every headline is therefore reported **raw and Rogan-Gladen corrected** with these per-model ×
per-language error matrices (`corrected_headlines_j1_R` in `results/analysis.json`), and **cross-model** statistics
such as `G3_op` are additionally reported under the judge-free lexicon and first-token-log-odds proxies, where they
replicate (−2.31 and −1.55). Within-Gemma conclusions rest on the better-validated Gemma cells.

## Verification

* `results/audit.json` — an **independent second code path** (pandas/scipy, does not import `analysis.py`)
  recomputes every rate, Lag, cut, alpha50 (scipy NLL vs the IRLS fit), f/cos/rho and an RQ4 AUROC:
  **125 / 125 checks pass**, including placebos (model-label swap, language-label swap, direction-label swap) that all
  centre on 0.
* `tests/test_units.py` — 10 unit tests (Hautus/logit, Gram-Schmidt orthogonality, alpha50 recovery and censoring,
  Rogan-Gladen, the label parser, degeneracy/language helpers).
* `results/dev/<M>/smoke.json`, `multi_check.json` — hook correctness: zero-strength hooks change logits by 0.0;
  mean-projection leaves the centred projection at ~4e-4; BOS untouched; lambda = 0 reproduces the base model exactly;
  the batched multi-condition runner matches the single-condition hook path.
* `protocol.yaml` (+ `.sha256`) and `protocol_amendments.yaml` were git-committed **before** the first TEST row of each
  model; `git log` shows the order.

### Deviations from the plan (all recorded in `protocol.yaml`)

* 64 new tokens for add-on rows too (the frozen judge prompt states "truncated at 64 tokens"), applied identically everywhere.
* Judge substitution as above (the single largest deviation).
* GaMS's alpha-grid ×2 rule fired on a **degeneration artefact** (`r_EN` at K = 3 is 62 % degenerate, and the surrogate
  reads degenerate text as non-refusal) and was overridden to ×1 — matching Gemma — in a pre-TEST amendment
  (commit `dd17feb`, written before any GaMS TEST row).
* The strict manipulation check (monotone t_post projection at L\*+4) fails even for the working positive control
  `r_EN`, because the direction rotates across layers; the analysis therefore also accepts a monotone dose→first-token-KL
  relation, and reports both.
* RQ4 uses 7 representative layers rather than every 4th, and 200–300 bootstrap draws; it is a CHECK, never a headline.
* No 4-vs-8-bit agreement check (a bf16/8-bit 12B does not fit beside NF4 on a 23 GB L4); all contrasts are within-precision.

## Reduced scope / not executed

* **Second judge family** is Qwen3-14B on a stratified 10 % sample (3.2 k rows) rather than gpt-4.1-mini at 20 % — no
  paid API was reachable. Since Qwen failed the gate it is reported as a *sensitivity* readout, not a co-primary.
* **dir2 adapter pick-up** for RQ4: no compatible sibling selection existed at start-up (logged in `results/<M>/checks.json`).
* Everything is on NF4, so absolute KL values and direction norms are not comparable to bf16 papers.
* Harmful items are exp8's RefusEU-TRAIN **screen** items (P200), so the add-on test sits on the screen lead; the paper
  must say so. The fresh 300-item probe belongs to the sibling artifact.

## Layout

| path | what |
|---|---|
| `method.py` | pipeline entry point (stages: data, gemma, gams, judge, analysis); documents the order of operations |
| `run_chain.sh` | the sequential single-GPU chain actually used (resumable; skips finished steps) |
| `src/common.py` | paths, model ids, frozen judge prompt (verbatim exp8), lexicon, helpers, row keys |
| `src/prep_data.py` | S0 input check (`logs/inputs_check.json`) + S1 data: Dolly harmless sets, NLLB SL-MT / EN-BT, P200 DEV40/TEST160, hard-benign 30/100, overlap checks, `data/split_manifest.json` |
| `src/gpu_block.py` | per-model GPU block: NF4 load, T1 smoke asserts, construct activations, directions + geometry (split-half + bootstrap), DEV generations, add-on band rule, protocol freeze, TEST induction / add-on / collateral, RQ4 activations |
| `src/probe.py` | verbatim copy of exp8 batching / greedy-generation / first-token helpers |
| `src/geomlib.py` | Gram-Schmidt helpers (unit-tested) |
| `src/judge_local.py` | local LLM judges (Qwen3-14B, Mistral-Small-24B): logit-restricted 3-way label, calibration vs archived gemini |
| `src/judge_surrogate.py` | gemini-2.5-flash surrogate (primary readout): fit + grouped CV + leave-one-curve-out + selection rule; apply |
| `src/judge.py` | OpenRouter client (unusable in this run: budget exhausted), request map, stratified second-family sample |
| `src/dev_decide.py` | DEV decisions (L*, alpha-grid multiplier, lambda*) from DEV rows + judge labels |
| `src/freeze.py` | writes / hashes / commits `protocol.yaml` and `protocol_amendments.yaml` |
| `src/adjudicate.py` | blind adjudication sample (author-model adjudicator, NOT human) |
| `src/rq4.py` | RQ4 probes (CV AUROC + shuffled control, fixed-probe d', transfer, diff-of-means cosine) |
| `src/analysis.py`, `src/stats.py` | S9 analysis -> `results/analysis.json` |
| `src/audit.py` | S10 independent recomputation (pandas/scipy, does not import `analysis.py`) + placebos -> `results/audit.json` |
| `src/rederive_headline.py` | THIRD re-derivation of the headline lag from `method_out.json` in pure Python (no numpy/pandas/scipy), with the language-swap placebo -> `results/rederive_headline.json` |
| `src/reconcile_readme.py` | recomputes every number quoted in this README from `results/analysis.json` -> `results/reconcile_readme.json` |
| `src/make_figs.py`, `src/make_outputs.py` | figures, `method_out.json` |
| `pyproject.toml`, `requirements.lock.txt` | 164 exactly-pinned dependencies (`uv pip freeze` of the venv that produced these results) |
| `tests/test_units.py` | T0 unit tests (`.venv/bin/python -m pytest -q`) |
| `data/` | all item sets (jsonl) + `split_manifest.json` (sha256, gates, overlap) |
| `protocol.yaml` (+ `.sha256`), `protocol_amendments.yaml` | pre-registration frozen before TEST (git history shows commit times) |
| `results/<M>/` | `geometry_{post,inst}.json`, `geometry_boot_post.npz`, `directions_{post,inst}.npz`, `random_controls.*`, `addon_collateral.json`, `checks.json`, `timing.json` |
| `results/dev/<M>/` | DEV rows, `dev_decisions.json`, `smoke.json`, `multi_check.json` |
| `results/test/<M>/` | TEST rows: `induce.jsonl`, `addon.jsonl` (one row per generation, all per-row diagnostics) |
| `results/judge_labels.jsonl` | every label (surrogate/gemini, surrogate/tfidf, local/qwen3-14b) keyed by row key |
| `results/judge_calib_*.json`, `results/judge_surrogate_selection.json` | judge validation |
| `results/adjudication_*.jsonl` | blind adjudication items, key and labels |
| `results/analysis.json`, `results/audit.json`, `results/rq4.json` | headline statistics |
| `figures/` | fig1-fig5 (PNG + PDF) |
| `results/acts_Lstar/` | 14 MB of L\*-layer activation slices kept so `src/audit.py` stays runnable; the bulk `acts/` (17 GB float32 residuals) was **removed** — regenerate with `src/gpu_block.py --phases acts` / `--phases rq4` |

## Which dependency data was used, and what was deliberately held back

Dependency `art_EG6OpEkGvysx` (`round-1/dataset-1/src/full_data_out.json`, 8 blocks) is used under the
study's **data-separation rule**, which the shared protocol fixes and this artifact must not break:

| block | use here | why |
|---|---|---|
| `hard_xstest`, `hard_orbench_hard1k` | **used** — `hard_DEV`, `is_harmful = 0` only: 30 dev + 100 test benign items, English re-translated with NLLB | the benign / over-refusal arm (`BenignExcess`). The dataset's own Slovene MT is gemini-made, which the protocol forbids for arms, so it is re-translated here |
| `refuseu_eval` | **text read for the overlap check only**, never generated on | RESERVED for the sibling/`dir4` evaluation artifact; generating on it here would burn the held-out set |
| `hard_FINAL` split, `identity_confirm` | **not opened** | RESERVED, same reason |
| `hard_orbench_toxic300`, `refuseu_gold_calib`, `gams_dose_rows`, `refuseu_x_mt` | **not used** | out of scope for a mechanism artifact: these are hazard-labelling / dose-estimation and natural-EN-SL blocks, and `refuseu_x_mt` duplicates the MT arm this artifact builds itself from exp8 items with a pinned NLLB config |

Harmful items come from exp8's `probe_P200` / `construct_A2` (RefusEU-TRAIN) with their sha256s checked at start-up;
harmless items are freshly drawn from Dolly-15k (deliberately *outside* Heretic's Alpaca-based KL objective data, so
the directions are not circular with the edit). `data/split_manifest.json` records every sha256, the chrF/langid gates
and the full cross-set overlap report.

## How to run

```bash
uv venv .venv --python=3.12 && uv pip install --python .venv/bin/python -r pyproject.toml
.venv/bin/python -m pytest -q                       # T0 unit tests
.venv/bin/python method.py --stage data             # inputs check + data (NLLB on GPU, ~10 min)
./run_chain.sh                                      # GPU chain (after the DEV judge/decision steps, see method.py)
.venv/bin/python method.py --stage analysis         # rq4, analysis, audit, figures, method_out.json
```

## Restoring removed files

Every `delete:` entry in `.aii/manifest.yaml`, and how to bring it back. **None of them is needed to read the
results, rerun the analysis, or reproduce any number in this README** — all derived artifacts are kept.

| removed path | why it is safe to remove | restore with |
|---|---|---|
| `.venv/` (11 GB) | regenerable; 164 exactly-pinned deps | `uv venv .venv --python=3.12 && uv pip install --python .venv/bin/python -r pyproject.toml` |
| `src/__pycache__/` | Python bytecode cache | recreated automatically on the next run of any `src/` script |
| `tests/__pycache__/` | Python bytecode cache | recreated automatically by `.venv/bin/python -m pytest -q` |
| `.pytest_cache/` | pytest run cache | recreated automatically by `.venv/bin/python -m pytest -q` |

Two further things are **not in this directory** and are restored the same way:

| path | restore with |
|---|---|
| `acts/` — 17 GB of float32 residual activations, deleted after the analysis for the 100 MB per-file publishing limit | `.venv/bin/python src/gpu_block.py --model <M> --phases acts` rebuilds the construct activations (~2-3 min/model); `--phases rq4` rebuilds the RQ4 activations (~3-7 min/model). Both regenerate **identically**, because `results/dev/<M>/dev_decisions.json` and `results/<M>/frozen.json` are kept. Everything derived from them — `results/<M>/directions_*.npz`, `geometry_*.json`, `results/rq4.json`, and the 14 MB of L\*-layer slices in `results/acts_Lstar/` — is kept, so **no analysis, figure or audit needs the rebuild** (`src/audit.py` reaches 127/127 with `acts/` absent). |
| model weights (in the shared HF cache, never in this directory) | `hf download google/gemma-3-12b-it --revision 96b6f1eccf38110c56df3a15bffe176da04bfd80`; `hf download cjvt/GaMS3-12B-Instruct --revision 1d0b27af5748784482600d24779409e7e1dc9adc`; `hf download facebook/nllb-200-distilled-1.3B --revision 7be3e24664b38ce1cac29b8aeed6911aa0cf0576`; `hf download Qwen/Qwen3-14B --revision 40c069824f4251a91eefaf281ebe4c544efd3e18` |
