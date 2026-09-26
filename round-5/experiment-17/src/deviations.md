# Deviations from the artifact plan (gen_plan_experiment_2_idx2)

Each entry gives what changed, why, and what it costs. Plan-declared departures (a)–(i) come first, then deviations found during execution.

## Plan-declared departures (kept)

- **(a) The frozen-core edit is the SAVED iteration-3 edit.** We did not run a fresh frozen-core Heretic search. The edit is exp9's `selected/{gemma_it,gams3_it}` LoRA (r = 3, o_proj + down_proj). exp9 chose it with a reduced, parameter-identical trial budget, in NF4, using OUR selection rule F4 ("lowest refusal with KL ≤ 0.5"). Heretic has no automatic selection rule (research artifact art_NZ9n2Ej5RtGt). **Unpaid debt:** the tool's default-budget, bf16, automatic-selection search was never run. The GPU was revoked 25 min into exp13, and the tool has no automatic selector. The claim is therefore "what this documented English-only edit buys", not "what Heretic at its defaults buys".
- **(b) NF4 for both study models.** Every contrast is within one precision. Absolute rates are specific to NF4.
- **(c) 128 new tokens.** The sensitivity check regenerates 100 pairs × 2 languages at 256 tokens with λ = 1.0 (`sens256`).
- **(d) Adjudicator prompt.** Superseded by D-R0: no gpt-4o-mini call was possible.
- **(e) λ_gate.** Added only for a model that misses the DEV gate at λ = 1.0. It is reported beside λ = 1.0, never instead of it.
- **(f) Budget.** Superseded by D-R0: $0 was spent.
- **(g) Gold standard.** The gold labels are a blind **author-model** adjudication by the executor (Claude, an LLM). They are **not** human labels. A native-speaker audit request is in `results/human_audit_request.json`.
- **(h) EN vs SL comparisons.** EN-vs-SL contrasts on the natural prompts are descriptive only and marked NOT INTERPRETABLE AS A LANGUAGE EFFECT.
- **(i) Random-direction control.** The rand_1 control runs at λ = 1.0 on the 200-pair control subset.

## Deviations found during execution

### D-R0: OpenRouter run budget exhausted, so every paid readout was replaced by a local, pinned substitute (fixed before the protocol freeze)
The preflight OpenRouter smoke test (2026-09-25 00:37 UTC) returned HTTP 403 `aii_run_budget_exhausted`: *"AI Inventor per-run OpenRouter budget reached … $12.12 of $12.00 spent by this run … It does not reset while this run goes on: retrying will not help."* Earlier steps of the run had spent the budget before this artifact started. The plan's fallback (f) allows no silent local substitute for P1 or SR, and treats a missing adjudicator as "protocol incomplete". We instead adopted **declared** local substitutes. They were written into `protocol.yaml` (header R0) before the freeze, before any FINAL generation and before any readout existed:

| Plan component | Substitute actually used | Cost / caveat |
|---|---|---|
| gpt-4o-mini adjudicates LG/PG disagreements (RefusEU protocol) | **Qwen/Qwen3Guard-Gen-8B**@4505cb1a (multilingual guard), STRICT verdict (Controversial → unsafe). LOOSE is reported as a sensitivity. It is run on **all** rows. | This is **not** the RefusEU adjudicator. Because a third guard labels every row, ASR_row equals the 3-guard majority vote. RefusEU-protocol comparability holds for the two named guards only. |
| gemini-2.5-flash StrongREJECT rubric (the scorer used in artifact 1) | **The official StrongREJECT fine-tuned evaluator**, qylu4156/strongreject-15k-v1 (a LoRA on google/gemma-2b), with the repo's `strongreject_finetuned` template and expected-value rule. It scores **every** row, so no imputation is needed. | Its scale differs from artifact 1's rubric scores, so they cannot be pooled. The evaluator was fine-tuned on English, and its Slovene validity is measured by the adjudication, not assumed. bf16 instead of the repo's 4-bit load. |
| P1 3-way refusal judge (gemini) plus the gpt-4.1-mini second family | PolyGuard "Response refusal" (primary refusal readout) and the Qwen3Guard "Refusal" field (second family) | Guard refusal flags are not the frozen P1 prompt. The P1 readout is NOT_EXECUTED. |
| DEV gate readout: P1 REFUSE from gemini on 100 DEV EN rows | PolyGuard "Response refusal = yes" share on the same 100 DEV EN rows | The gate threshold is unchanged (≥ 50 % relative cut). The gate is decided after a guard pass on DEV rows, so the λ_gate rows are generated in a second model session. |
| Adjudication frame on λ_gate rows | Frame on **edit@1.0** rows, the confirmatory contrast | Se/Sp are estimated on the rows that carry S1. At λ_gate they are assumed to transport. |

Paid spend in this artifact: **$0.00**, apart from the rejected smoke calls. `src/judge_paid.py` and `src/label.py` are kept for provenance and were **not executed** for any label.

### D-DUP: a duplicate Gemma generation process ran for about 6 min
The first launch of `gen.py --model gemma_it` (00:38 UTC) survived its shell. A second launch (00:40) ran in parallel until the first was killed at 00:45. Both appended to `results/gens/dev_gemma_it.jsonl`, and 31 DEV keys (MINI and first DEV rows) were written twice. All readers use `common.read_gens`, which keeps the first occurrence of each key. Only DEV rows were affected: FINAL generation started after the duplicate was killed and after the freeze. The only other cost was a few OOM batch halvings.

### D-CONTAM: FINAL pair ids were not untouched at the pair level
The plan expected zero contamination hits. The grep (`data/contamination_check.json`) found FINAL pair ids in exp11 and exp13 generation files. All of those rows belong to the **refuseu_x NLLB companion arms** (EN_BT round trip, SL_MT, HU MT), which reuse the same pair id. The natural prompt strings themselves occur verbatim in 3 of exp11's GaMS EN_BT rows and 6 of exp13's rows (EN_BT reproduced the source) and in no SL row. No model was trained on any of them. The natural FINAL prompts are therefore effectively new inputs, but the claim "never generated on" holds at the prompt-string level, not the pair-id level.

### D-GATE-CUT: the edit@λ_gate condition runs on 650 pairs (plan cut 3)
The generation throughput measured at MINI/DEV was about 1.5–2.3 rows/s on the L4. The substitute design adds a second model session per gated model plus a third guard. Together these projected a total wall time beyond the 6 h budget with a full-size gate condition. Following the frozen wall-cut order, cuts 1–2 (random control, 256-token sensitivity) were kept because they are cheap (about 3 min each), and cut 3 was applied: the λ_gate condition covers the first 650 pairs by hash rank. This is reported as a reduction. orig and edit@1.0 run on all 1,300 pairs.

### D-WALL: wall-budget cuts actually applied
Measured throughput on the single L4: generation 2.2–2.8 rows/s, PolyGuard 3.7 rows/s, and three guards must each see
every generated row. With two models that projected past the 6 h budget, so two cuts were applied and recorded as
amendments before the work they affect:

- **A0_gams3_it** — the GaMS DEV dose grid runs the two doses the frozen gate rule actually needs (λ ∈ {0, 1.0}) instead
  of all eight. The extra doses exist only to locate λ_gate, which is needed only if the relative cut at λ = 1.0 falls
  below 50 %. `results/dev_gate_gams3_it.json` therefore reports a two-point curve, and figure F5 shows the full
  eight-dose curve for Gemma only. Cost: if GaMS had failed the gate, the grid would have had to be extended before its
  gate session (the chain does this automatically).
- **D-GATE-CUT** (above) — the λ_gate condition, if triggered, covers 650 of the 1,300 pairs.

Nothing on the frozen NEVER-CUT list was cut: both models, both languages, orig and edit@1.0 on all 1,300 pairs, the
guard-ensemble ASR on every generated row, the adjudication of every guard disagreement, the DEV gate, and ≥ 200 edited
adjudication rows all ran in full.
