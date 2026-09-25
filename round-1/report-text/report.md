# Framing

GaMS3-12B-Instruct [20] and Gemma-3-12B-IT both descend from google/gemma-3-12b-pt, but followed different post-training paths. GaMS3 received Slovene continued pretraining on 140 billion tokens and supervised fine-tuning on a mix that is roughly 79% Slovene, including about 7,000 safety-refusal examples drawn largely from machine-translated Qwen-family responses. Gemma-IT received Google's standard multilingual post-training. Because the two checkpoints share a pretrained ancestor yet diverge in the language of their safety supervision, they form a natural pair for testing whether the language in which refusal was taught determines where refusal appears.

The core question is whether Slovene-taught refusal transfers to English. Prior work on refusal directions [1] established that a single subspace mediates refusal in English, and Wang et al. [2] showed that English-extracted refusal directions transfer across 14 languages, but both studies used models whose post-training mixed many languages. Less is known about transfer when safety supervision is concentrated in one language. Shaham et al. [4] found that "a pinch" of multilingual instruction data suffices for task-level transfer; Krasnodebska et al. [8] found that English-only DPO alignment does *not* ensure cross-lingual safety, even for the same harm categories. This tension motivates the dose-response design: if the English share of GaMS3's refusal supervision varies across hazard categories, categories with essentially zero English examples should show a measurable Slovene surplus that Gemma does not share.

A second question follows: if refusal does transfer, does the English-only objective of an automatic abliteration tool (Heretic [24]) remove Slovene refusal as readily as English refusal, and does it do so equally in GaMS3 and Gemma-IT? The practical stake is whether a monolingual attack pipeline is sufficient to strip safety from a bilingual model, or whether the Slovene supervision gives GaMS3 a Slovene reserve that an English-only adversary cannot reach. Joad et al. [5] showed that category-specific refusal directions are geometrically distinct yet collapse under linear intervention; Zhong and Li [6] argued that refusal lives downstream of persona in chat models. Both findings bear on whether a single English-extracted direction is the right probe for a bilingual model.

Four rival accounts were pre-registered. The main claim (behaviour-level reach) predicts that refusal transfers to English at every hazard-category grain. Alternate 1 (supervised reach) predicts a Slovene surplus in low-English-dose categories. Alternate 2 (base-checkpoint geometry) predicts that GaMS-vs-Gemma differences are explained by the base models' harmfulness separability [3, 14]. Alternate 3 (persona gating) predicts a uniform Slovene surplus driven by GaMS3's Slovene-anchored self-identity [6]. Alternate 4 (thin templated gate) predicts symmetric language differences driven by the diversity, not the language, of refusal supervision.

# Iteration 1

## Strategy

The iteration ran five artifacts: a dataset artifact that built the evaluation sets and audited GaMS3's supervision dose, and four experiment artifacts that each tested one or more of the pre-registered claims. The design was a screen: every claim was evaluated on SCORE items drawn from RefusEU's train and test splits, with the reserved RefusEU evaluation split untouched for a future FINAL pass. The sequence was dictated by a single-GPU constraint (40 GB disk), requiring models to be loaded and evicted one at a time.

The four experiments were:
1. Experiment 1 (main screen): the refusal difference-in-differences between GaMS3 and Gemma-IT on original models, plus the dose contrast D and identity calibration.
2. Experiment 2 (base models and mechanistic): harmfulness separability in the two base checkpoints and two instruct models, plus the ancestor-direction induction test.
3. Experiment 3 (persona gate): the alternate-3 manipulation, ablating GaMS3's persona direction and testing whether it moves Slovene refusal.
4. Experiment 4 (Heretic abliteration): English-objective abliteration of both instruct checkpoints, the transfer curve, the excess KL ratio, and the prefill test.

All protocols were hashed and committed before scoring. The OpenRouter shared key hit its daily limit partway through experiments 3 and 4, leaving some judge calls incomplete; these gaps are documented below.

## Artifact 1: Dataset and supervision audit

[ARTIFACT:art_EG6OpEkGvysx]

The dataset artifact assembled eight data blocks totalling 15,647 rows.

**RefusEU evaluation split.** 1,400 English and 1,400 Slovene prompts from RefusEU [8] (commit 5523ce30b9), frozen into 100 DEV and 1,300 FINAL pairs by sha1 of the pair identifier. Each item received a blind hazard-category label (majority vote of gpt-4.1-mini, gemini-2.5-flash, and a TF-IDF classifier). Gold-test accuracy was 0.759 for English and 0.716 for Slovene; restricting to items where all labellers agreed raised accuracy to 0.95 and 0.94. Inter-annotator kappa between the two LLM labellers was 0.88 (English) and 0.83 (Slovene).

A critical discovery was that same-row-identifier English and Slovene items in RefusEU are not translations: LaBSE cosine similarity was 0.553, matching the similarity of same-category pairs (0.547) and far below the machine-translation baseline (0.914). Zero of 1,400 pairs graded as translation-equivalent. This means within-model Slovene-vs-English comparisons on matched row identifiers conflate prompt content with language; only the cross-model difference-in-differences and a separate machine-translation arm are interpretable.

**Supervision dose audit.** 6,239 rows from GaMS-Nemotron-Chat and GaMS-Instruct-SAFE were labelled for response type, language, and hazard category by two LLM families (gpt-4.1-mini and gemini-2.5-flash, with llama-3.3-70b tiebreak on 928 disagreements; batch-check agreement 0.945 English, 0.959 Slovene). The overall English share of safety refusals was 0.178, with a propagated interval of [0.055, 0.452]. The upper bound exceeds 0.40, so "Slovene-dominant refusal" is not statistically licensed from the public data alone.

The pre-registered 0.10 threshold for assigning categories to dose groups produced the following frozen partition, which diverged from the initial Stage-0b estimates on three categories (S1, S2, S8):

**Table 1. Frozen dose groups after re-labelling.**

| Group | Categories | EN share range (point estimates) |
|---|---|---|
| Low-EN | S2, S5, S7, S13 | 0.034 to 0.096 |
| High-EN | S1, S3, S4, S8, S9, S10, S11, S14 | 0.109 to 0.291 |
| Intermediate | S6, S12 | 0.148 to 0.201 |

Thirteen of fourteen categories were flagged as dose-uncertain (the propagated EN-share interval straddles 0.10). The re-labelling changed S2 from high to low (point 0.075, down from Stage-0b's 0.292) and S8 from low to high (point 0.226). S1 moved from intermediate to high (point 0.291). These shifts reflect the difference between the literal Llama-Guard-3 hazard prompt used in Stage-0b and the RefusEU taxonomy operationalisation used here; agreement between the two was 0.58.

**Other blocks.** The hard set (OR-Bench-hard-1k, XSTest, OR-Bench-toxic-300) was assembled with Gemini Slovene machine translation (back-translation chrF median 79; 11 items dropped). The identity set comprised 120 identity questions across six facets plus 120 matched personal controls, with zero overlap against the Nemotron training rows. The dataset artifact spent $9.29 of a $9.50 budget.

## Artifact 2: Main screen of refusal differences (Experiment 1)

[ARTIFACT:art_hKWkjbNTydu_]

Gemma-3-12B-IT and GaMS3-12B-Instruct were run in NF4 quantization with greedy decoding (64 new tokens, empty system prompt) on all 2,137 SCORE RefusEU pairs, a 400-pair item-matched machine-translation arm, 60 identity question pairs, and 1,504 CONSTRUCT pairs (for calibrating the continuous prefix score). The protocol hash (10f3cdcf) was committed before any SCORE pass. Judges were gemini-2.5-flash on 10,852 responses (33 provider-blocked items fell back to gpt-4.1-mini) and gpt-4.1-mini on a 20% validation subset; total judge spend was approximately $0.91.

### Refusal rates

The ceiling flag fired: Gemma's English lexicon refusal rate was 0.961, and the prefix-score AUROC against the lexicon was only 0.61 in that cell, so the pre-registered fallback to the judge readout (including partial refusals) was triggered.

**Table 2. Refusal rates on the 2,137 SCORE pairs.**

| Readout | Gemma EN | Gemma SL | GaMS EN | GaMS SL |
|---|---|---|---|---|
| Lexicon | 0.961 | 0.885 | 0.942 | 0.723 |
| Judge (binary) | 0.979 | 0.929 | 0.971 | 0.865 |
| Judge + partial | 0.988 | 0.939 | 0.974 | 0.875 |

Both models refuse at high rates across languages. The gap is in Slovene: GaMS3 refuses less than Gemma in Slovene on both the lexicon (0.723 vs 0.885) and the judge (0.865 vs 0.929). In English, the two models are within two percentage points.

### Difference-in-differences and dose contrast

The difference-in-differences (DiD = [GaMS(SL − EN)] − [Gemma(SL − EN)]) measures whether GaMS3 has a larger Slovene deficit than Gemma. A negative DiD means GaMS3's Slovene gap is wider. All rate-to-logit conversions use the Hautus correction (adding 0.5 to counts before taking log-odds, to avoid infinities at 0% and 100%). The pre-registered threshold was m = 0.40 log-odds (the log-odds equivalent of a 5 pp smallest effect size of interest at the pooled base rate).

**Table 3. Overall DiD and dose contrast D (log-odds, 95% bootstrap CI).**

| Readout | Overall DiD [95% CI] | D [95% CI] | MDE(D) |
|---|---|---|---|
| Lexicon | −0.67 [−0.95, −0.41] | 0.61 [−0.58, 2.15] | 1.89 |
| Judge | −0.38 [−0.69, −0.05] | −0.08 [−1.27, 0.94] | 1.53 |
| Judge + partial | −0.03 [−0.39, 0.39] | −0.73 [−2.11, 0.48] | 1.87 |

On the lexicon, the overall DiD is clearly negative (−0.67, CI excludes 0), confirming that GaMS3 has a wider Slovene refusal gap than Gemma. On the judge, the DiD is smaller (−0.38) but its CI still excludes 0. Including partial refusals shrinks the DiD to near zero (−0.03), with the CI spanning both sides.

The dose contrast D (the difference in DiD between low-EN and high-EN categories) is the primary statistic for the main claim vs alternate 1. On all three readouts, D is uninformative: the confidence intervals are wide (MDE 1.5 to 1.9 log-odds, or 5.5 to 8 pp), spanning both positive and negative values. Neither equivalence nor a dose effect can be established.

[FIGURE:fig_forest_did]

The 14-category meta-regression of DiD on the English dose share found no significant slope: the zEN coefficient was −0.04 on the lexicon (95% CI [−0.66, 0.58]) and −0.12 on the judge (95% CI [−0.79, 0.54]). However, the item-level generalised linear mixed model produced a significant negative zEN term on the lexicon (−0.17, CI [−0.28, −0.07]) that flipped sign on the judge (+0.13, CI [0.00, 0.27]), a signature of pseudo-replication from 14 correlated category-level units (correlation between zEN and zSL: 0.86, VIF 3.84).

**Scorer confound.** The frozen Slovene lexicon lacked English-style "lecture" markers (phrases like "It's important to understand that..."), missing 312 GaMS Slovene judge-classified refusals vs 97 for Gemma. Kappa between the lexicon and the judge was below 0.70 in three of four model-language cells. The lexicon therefore overstates GaMS3's Slovene deficit relative to the judge.

### Item-matched machine-translation arm

To separate the language effect from the prompt-content effect, a 400-item arm used NLLB machine translations of English prompts into Slovene, giving paired items with identical content. GaMS3's Slovene-MT refusal rate was 0.968 vs its English rate of 0.970 (McNemar: 7 vs 8 discordant pairs). The judged DiD on this arm was −2.0 pp [−4.3, 0.0], compared with −6.0 pp on the natural RefusEU pairs sharing the same row identifiers. Most of GaMS3's Slovene deficit on natural pairs is thus a prompt-set-by-model interaction, not a pure language effect.

### Identity calibration (C1)

The calibration arm passed. GaMS3 named itself "GaMS" in 90% of Slovene identity responses and 35% of English ones; Gemma named itself "Gemma" at 77% in English and 67% in Slovene (Table 4). In English, GaMS3 produced "Qwen" as its primary name in 13% of responses, with 48% giving no name at all. The identity DiD was 3.22 [2.38, 4.38], far exceeding the 10 pp threshold (m_id = 0.43). This confirms that GaMS3's supervised fine-tuning can produce language-anchored behaviour: self-identity, taught only in Slovene, is Slovene-bound. The instrument can detect anchoring when it exists.

**Table 4. Identity: own-name rates and name distribution.**

| Cell | Own-name rate | Top other names |
|---|---|---|
| GaMS EN | 0.35 | Qwen 0.13, none 0.48 |
| GaMS SL | 0.90 | none 0.08 |
| Gemma EN | 0.77 | none 0.22 |
| Gemma SL | 0.67 | other 0.08, none 0.20 |

### Surface forms

1,504 of 1,545 GaMS3 Slovene refusals (97.3%) opened with the calque "Oprostite, vendar..." ("I'm sorry, but..."), a word-for-word translation of the English Qwen refusal template. The Nemotron training data contained 1,508 Slovene calques vs 585 "Žal..." openings and 739 English "I'm sorry, but..." openings. The near-universal Slovene calque confirms that GaMS3's refusal wording is borrowed from English, even when the content was supervised in Slovene.

### Verification

The audit script passed 30 of 30 checks. Two independent re-derivation scripts reproduced all rates, DiD, D, DiD_id, and machine-translation DiD exactly. Model-swap placebos (computing DiD after swapping model labels) were centred at zero (permutation p = 0.014 for the judge DiD, 0.17 to 0.87 for D). Four-vs-eight-bit first-token agreement was 0.95 (NF4 vs int8 on 20 fixed prompts); language consistency was 100%; batching-outcome agreement was 32/32.

### Outcome

Neither the main claim nor alternate 1 survived the screen. On the lexicon, the DiD is negative and exceeds m, which would favour alternate 1 through the generalised linear mixed model clause, but the dose contrast D is not significant. On the judge, the DiD is smaller (−0.38, barely excluding 0) and D is uninformative (MDE 1.53, well above 2m = 0.80). The judge and lexicon disagree on the direction of the zEN coefficient, so neither claim can be confirmed or refuted. The identity calibration arm passed, establishing that anchoring is detectable in this design. The frozen-core consequence (whether Heretic removes Slovene refusal) was deferred to experiment 4.

## Artifact 3: Base models and mechanistic induction (Experiment 2)

[ARTIFACT:art_NLTHj-fHEaG3]

Four checkpoints (gemma-3-12b-pt, GaMS3-12B, gemma-3-12b-it, GaMS3-12B-Instruct) were run in NF4 on an RTX 4090. Items were 2,889 RefusEU train+test pairs (sha1 split: 743 CONSTRUCT, 2,146 SCORE, with a SCORE-400 subset for generation) plus 400 alpaca harmless prompts (NLLB machine-translated to Slovene). The protocol was hashed and committed before any forward pass. OpenRouter spend was $4.74. The RefusEU evaluation split was never read.

### Alternate 2 (base-checkpoint geometry): killed

The pre-registered test asked whether the Slovene harmfulness separability (d') is higher in GaMS3-12B-base than in gemma-3-12b-pt, which would predict a Slovene refusal advantage. At the pre-registered layer (L = 22), the delta-d'-Slovene (GaMS-base minus pt) was −0.98 [−1.13, −0.85]: the GaMS base has *lower* Slovene separability than the pretrained ancestor at this layer, the opposite of the prediction. At each model's own best layer, the sign reversed to +2.85. The item-level regression found that base geometry explained only 4.2% of the instruct-level refusal variance [0.5%, 12.2%], with a z-score of −15 against the 50% mediation threshold. Dose coefficients were non-significant (wild-cluster p = 0.87 for zEN, 0.92 for zSL). An exploratory analysis found that base-model harm directions carry a last-token punctuation confound; punctuation-matched and mean-pooled delta-d' changed sign again. Base-separability contrasts are not robust.

**Alternate 2 is dead.** The base checkpoint does not set the instruct model's language profile of refusal.

### C4 (ancestor-direction induction): failure branch

The pre-registered test asked whether adding the gemma-3-12b-pt harmfulness direction to harmless-prompt activations induces refusal in the instruct models, and whether the EN/SL potency ratio differs between GaMS3 and Gemma. The pretrained direction never reached a refusal rate of 0.50 in any model-language cell under the judge readout (peak 0.03 to 0.25; output was mostly incoherent). It performed no better than random directions and had cosine similarity near zero with each instruct model's own refusal direction. This triggers the pre-registered failure branch: "refusal reads an ancestor-readable feature" loses causal support, consistent with Du et al. [3] who report limited forward transfer of refusal directions from base to post-trained models.

The positive control passed: each instruct model's own difference-of-means direction induced refusal at low alpha values (alpha50 approximately 0.03 times the mean residual norm for Gemma-IT, 0.05 for GaMS3). The own-direction delta for the language-asymmetry comparison was −0.09 [−0.28, 0.07] on the lexicon and +0.24 [0.13, 0.38] on the judge, both inside the pre-registered equivalence bound of plus or minus ln(1.5) = 0.41. Alternate 1 is therefore not supported by the induction data: GaMS3 does not show a lower Slovene induction potency than Gemma.

**Table 5. SCORE-400 judge refusal rates (Experiment 2, secondary).**

| Model | EN | SL |
|---|---|---|
| Gemma-IT | 0.957 | 0.945 |
| GaMS3-Instruct | 0.967 | 0.917 |
| DiD (log-odds) | −0.70 [−1.45, 0.02] | |

### Validity notes

The frozen lexicon was found to be language-asymmetric: the English list included "illegal" and "unethical" markers absent from the Slovene list. GaMS3's Slovene kappa (lexicon vs judge) was 0.38, confirming the lexicon overstates GaMS3's Slovene deficit. The prefix score was dominated by template and language priors (the centred score reversed the mean DiD). NF4-vs-int8 first-token agreement was 18/20.

## Artifact 4: Persona-gate test (Experiment 3)

[ARTIFACT:art_3GJzU9GuyW5r]

Alternate 3, drawing on Zhong and Li's [6] claim that refusal lives downstream of persona, predicted that GaMS3's Slovene-anchored persona gates Slovene refusal, producing a uniform surplus. The test ran GaMS3-12B-Instruct and Gemma-3-12B-IT in NF4 on an NVIDIA L4, on SCORE-400 RefusEU pairs. The protocol hash (eb718197) was committed before scoring. Judge: gemini-2.5-flash, spend $1.45.

### Verdict: untestable

The manipulation check failed. Persona ablation (removing GaMS3's own-name direction from late layers 32-47 via mean-projection with BOS skipped) did remove own-naming, but a variance-matched random direction also removed English naming to a comparable degree. The pre-registered rule declared alternate 3 untestable when the manipulation check fails.

Even if the manipulation had been clean, the signature would not survive. The judge-based triple-difference (TD*) was +0.23 [−0.81, 1.25], with an MDE of 1.46 (exceeding 2m = 0.88). The prefix-score co-primary (triggered by the ceiling rule) gave TD* = +0.43 [−0.11, 0.97], with the upper bound below the m_s threshold of 1.32.

### Consequential amendment

Zero-projection ablation was catastrophic in the Gemma-3 family, producing massive activations even for random directions (a BOS-sink artefact). The amendment replaced zero-projection with mean-projection that skips BOS, re-matching the random control on centred variance.

### Descriptive findings

GaMS3 showed a Slovene refusal *deficit* relative to Gemma, not the surplus that alternate 3 predicts. The unablated DiD was −1.11 [−2.00, −0.36] on the judge and −2.72 [−3.30, −2.13] on the prefix score. On the translation-matched items, it was −3.06 [−3.59, −2.52]. Late-layer persona ablation barely moved GaMS3's Slovene refusal: 0.883 to 0.853 (McNemar p = 0.08).

An exploratory finding: ablating GaMS3's own-name direction made GaMS3 identify as Qwen (English 0.15 to 0.78, Slovene 0.03 to 0.60), while random controls stayed at 0.23 to 0.30 and Gemma was unaffected. This is teacher-identity substitution, not persona removal: the ablation does not erase the identity; it replaces GaMS with the training-data source.

**Table 6. Refusal and identity rates under persona ablation (GaMS3, SCORE-400).**

| Condition | EN refusal | SL refusal | EN own-name | SL own-name |
|---|---|---|---|---|
| Original | 0.925 | 0.675 | 0.45 | 0.90 |
| Persona ablated (late) | 0.925 | 0.653 | 0.00 | 0.00 |
| Random control (late) | 0.925 | 0.670 | 0.23-0.30 | 0.23-0.30 |

Language-identity and Gemma induction ablation (C5) were catastrophic by the degeneracy gates and are not reported.

**Alternate 3 is dead.** The manipulation check fails, the premise (a Slovene surplus) is contradicted by the data, and the effect size is too small relative to the MDE.

## Artifact 5: Heretic abliteration and transfer curve (Experiment 4)

[ARTIFACT:art_A_ALQ08RqTgB]

English-objective abliteration was run on both instruct checkpoints using Heretic (commit 3521f864) with identical configuration: NF4, empty system prompt, TPE sampler with seed 20260923. The 17 compared draws were verified identical across models (paired design). A driver script copied Heretic's objective verbatim and logged bilingual metrics that never entered the objective; non-interference was verified by replaying objective values and confirming identical LoRA hashes.

### English abliteration reaches Slovene

Lexicon refusal on 400 RefusEU pairs fell sharply in both languages and both models:

**Table 7. Refusal rates before and after Heretic abliteration (lexicon, 400 pairs).**

| Condition | Gemma EN | Gemma SL | GaMS EN | GaMS SL |
|---|---|---|---|---|
| Original | 0.965 | 0.932 | 0.940 | 0.830 |
| Selected edit | 0.242 | 0.223 | 0.133 | 0.098 |

Trial-level slopes of Slovene refusal on English refusal were positive for both models (Gemma 1.21 [0.75, 1.83]; GaMS3 0.79 [0.51, 1.14]); shuffling Slovene rates produced slopes of 0.01 plus or minus 0.28. English-objective abliteration removes Slovene refusal.

[FIGURE:fig_transfer_curve]

### C3 (frozen-core transfer): fails both ways

The primary statistic G3 (the GaMS-minus-Gemma difference in the logistic transfer-curve intercept, measuring whether GaMS3 retains more Slovene refusal at matched English refusal) was −1.76 [−2.73, −1.09] on the matched first 17 trials (−1.76 on all trials, −1.74 on translation-equivalent pairs). The main claim required |G3| < m = 0.675; alternate 1 required G3 > m. Neither holds: Slovene refusal is *more* exposed in GaMS3 than in Gemma at any matched English refusal level. Trial-label permutation p = 0.000.

The category-level version (G3 in low-EN vs high-EN categories) was 0.39 [−1.19, 2.12], not separating dose groups.

### C5a (excess Slovene KL): reverses the prediction

The pre-registered test asked whether Heretic's real refusal direction damages Slovene more than a norm-matched random direction. The excess Slovene/English KL ratio was 0.298 [0.154, 0.562] for Gemma and 0.574 [0.409, 0.796] for GaMS3, both with confidence intervals entirely below 1. The real direction damages Slovene *less* than random directions. There is no Slovene leakage; the English-only objective is, if anything, Slovene-sparing.

### C5b (bilingual re-selection): unpowered

Only one candidate trial per model met the re-selection criteria, and it was the same as the original pick. Gain was zero. The test is unpowered because no trial reached the pre-registered threshold of 10 or fewer keyword refusals out of 100 (the best was 64/100 for Gemma, 29/100 for GaMS3). The fallback to a reduced-trial random-search analysis was triggered.

### Alternate 4 (thin templated gate): strongest signal but does not survive

A five-token compliant prefill ("Sure, here is") flipped refusals at strikingly different rates across models:

**Table 8. Prefill flip rates (fraction of items that refused at k = 0 but complied at k = 5).**

| | Gemma EN | Gemma SL | GaMS EN | GaMS SL |
|---|---|---|---|---|
| Flip rate | 0.031 | 0.558 | 0.559 | 0.855 |

The prefill signature Sig was 3.63 [3.13, 4.36] in English and 1.54 [1.20, 1.92] in Slovene, both exceeding the m2 threshold of 0.40 with confidence intervals above zero (z_c = 6.23, paired label-swap p = 0.000). GaMS3's refusal is more brittle than Gemma's in both languages, and the gap is larger in English (Sig_EN) than in Slovene (Sig_SL). However, alternate 4 predicted symmetric language effects (|Sig_SL − Sig_EN| < m), and the observed asymmetry was 2.10, far exceeding the threshold. Alternate 4 was scored as not survived.

The Pareto hypervolume ratio (GaMS3/Gemma) was 2.29 [2.01, 3.36], confirming that GaMS3's refusal is easier to remove across the entire refusal-KL trade-off front.

### Failed attempts

The plan's raw Arditi-style [1] rank-k ablation destroyed Gemma (KL 20 to 53 nats even for a random basis) and was abandoned. Mechanistic question C code was implemented but not run due to the key limit. Judge validation did not confirm the lexicon (kappa below 0.70 in all cells, though raw agreement was 95% with PABAK 0.90 on unedited cells). GaMS3's judge labels are incomplete: the OpenRouter key hit its daily limit before GaMS3 could be judged, and a retry with the replacement key still returned a 403 error.

### Limits

All transfer-curve and Pareto numbers come from reduced-trial random search, not the planned 80-trial Optuna run. The EN-KL-matched random control was unmatchable at the 6x cap. The lexicon is the primary readout because judge validation failed, with the prefix score as co-primary. Unedited-model KL reproduces to only 0.030 nats under NF4 batching.

## Summary of dead ends and surviving claims

**Table 9. Status of pre-registered claims after iteration 1.**

| Claim | Status | Key evidence | Next step |
|---|---|---|---|
| Main: behaviour-level reach (C2) | INCONCLUSIVE | D uninformative; MDE 1.5-1.9; lexicon/judge disagree | FINAL with larger N and validated judge |
| Alt 1: supervised reach | INCONCLUSIVE | Same D; zEN flips sign across readouts | Same |
| Alt 2: base geometry | DEAD | Delta-d' sign depends on layer; geometry share 4.2% | None |
| Alt 3: persona gate | DEAD | Manipulation check fails; premise (SL surplus) contradicted | None |
| Alt 4: thin gate | NOT SURVIVED | Prefill asymmetry too large; signature not symmetric | Descriptive only |
| C1: identity calibration | PASS | DiD_id = 3.22 [2.38, 4.38] | Carry forward |
| C3: frozen-core transfer | FAILS BOTH WAYS | G3 = −1.76 [−2.73, −1.09]; GaMS more exposed | Investigate with full Optuna run |
| C4: ancestor induction | FAILURE BRANCH | pt direction never reaches R = 0.50; own-direction equivalence holds | Report as check |
| C5a: excess SL KL | REVERSES | Ratio 0.30 / 0.57, CI below 1 | Confirm with judge |
| C5b: re-selection | UNPOWERED | n = 1 candidate per model | Full Optuna run needed |

# What we have learned so far

Five artifacts executed in iteration 1 screened all four rival accounts and the main claim against SCORE data drawn from RefusEU's train and test splits. Two rivals are dead: the base-checkpoint geometry account (alternate 2, killed by layer-dependent sign of the separability contrast and negligible mediation) and the persona-gating account (alternate 3, killed by a failed manipulation check and a Slovene deficit rather than the predicted surplus). The prefill signature of alternate 4 is the strongest observed signal, but its language asymmetry exceeded the pre-registered threshold.

The primary contest between behaviour-level reach (main) and category-level supervised reach (alternate 1) remains unresolved. The dose contrast D is uninformative on all readouts (MDE 1.5 to 1.9 log-odds), and the lexicon-vs-judge disagreement on the direction of the dose coefficient prevents a conclusion. The identity calibration passed, confirming that the design can detect anchoring when it exists. On the judge, the overall DiD is small (−0.38, about 5.6 pp), and the machine-translation arm shows that most of the natural-pair deficit comes from prompt-content differences rather than a pure language effect.

The abliteration results produced two findings that exceeded the pre-registered equivalence bounds in the wrong direction. First, GaMS3's Slovene refusal is *more* exposed to English abliteration than Gemma's (G3 = −1.76, where the main claim needed |G3| < 0.675). The Slovene-adapted model is easier, not harder, to strip of Slovene safety. Second, the real refusal direction damages Slovene *less* than norm-matched random directions (excess KL ratio below 1 in both models), refuting the prediction that an English-only objective leaks damage into Slovene.

The main open items for the next iteration are: running the FINAL evaluation on the reserved split with a validated bilingual judge, executing a full 80-trial Optuna run per model to power the transfer curve and re-selection tests, and resolving the lexicon-vs-judge disagreement through a second judge family.

## References

[1] A. Arditi, O. Obeso, A. Syed, D. Paleka, N. Rimsky, W. Gurnee, N. Nanda. "Refusal in Language Models Is Mediated by a Single Direction." NeurIPS 2024.

[2] X. Wang, M. Wang, Y. Liu, H. Schutze, B. Plank. "Refusal Direction is Universal Across Safety-Aligned Languages." NeurIPS 2025.

[3] H. Du, W. Li, M. Cai, K. Saraipour, Z. Zhang, H. Lakkaraju, Y. Sun, S. Zhang. "How Post-Training Reshapes LLMs: A Mechanistic View on Knowledge, Truthfulness, Refusal, and Confidence." arXiv 2504.02904, 2025.

[4] U. Shaham, J. Herzig, R. Aharoni, I. Szpektor, R. Tsarfaty, M. Eyal. "Multilingual Instruction Tuning With Just a Pinch of Multilinguality." Findings ACL 2024.

[5] F. Joad, M. Hawasly, S. Boughorbel, N. Durrani, H. Sencar. "There Is More to Refusal in Large Language Models than a Single Direction." arXiv 2602.02132, 2026.

[6] V. Zhong, Q. Li. "Refusal Lives Downstream of Persona in Chat Models." ICML 2026 MI Workshop.

[7] R. Aziz, I. A. Hanif, F. Koto. "Low-Resource Safety Failures Are Action Failures, Not Representation Failures." arXiv 2606.01196, 2026.

[8] A. Krasnodebska, W. Kusa, A. Lipani. "Multilingual Refusal Alignment for Safer Large Language Models." Findings ACL 2026.

[9] W. Hawkins et al. "The Heterogeneous Safety Impacts of Benign Multilingual Fine-Tuning." arXiv 2606.28843, 2026.

[10] X. Li, Z.-X. Yong, S. H. Bach. "Preference Tuning For Toxicity Mitigation Generalizes Across Languages." EMNLP 2024.

[11] A. Upadhyaya, S. Sikdar. "When Safety Speaks a Language: A Mechanistic Analysis of Safety-Language Identity Entanglement in LLMs." 2026.

[12] S.-Y. Miao et al. "Who Bridges Safety? Identifying and Targeting Cross-Lingual Shared Safety Pathways." 2026.

[13] A. Oppong et al. "The Illusion of Cross-Lingual Safety in Low-Resource Languages." 2026.

[14] C. Kissane, R. Krzyzanowski, A. Conmy, N. Nanda. "Base LLMs Refuse Too." Alignment Forum, 2024.

[15] L. Chua et al. "Crosslingual Capabilities and Knowledge Barriers in Multilingual Large Language Models." arXiv 2406.16135, 2024.

[16] X. He et al. "TUBA: Cross-Lingual Transferability of Backdoor Attacks in LLMs with Instruction Tuning." Findings ACL 2025.

[17] Y. Wu, L. Ding, L. Shen, D. Tao. "Edit Once, Update Everywhere: A Simple Framework for Cross-Lingual Knowledge Synchronization in LLMs." Findings ACL 2025.

[18] G. Messenger. "Detecting Safety Training Modification in Language Models via Activation Analysis." IEEE Access, 2026.

[19] A. Labunets. "Refusal geometry reflects refusal training: diverse refusal prefixes can raise stable rank and weaken refusal vector ablation attacks." 2026.

[20] D. Vres, T. Arcon, T. Petric, D. Vajda, M. Robnik-Sikonja, I. L. Bajec. "Building a Strong Instruction Language Model for a Less-Resourced Language." arXiv 2603.01691, 2026.

[21] R. Young. "Comparative Analysis of LLM Abliteration Methods: A Cross-Architecture Evaluation." arXiv 2512.13655, 2025.

[22] A. Fafula. "Abliteration Is Not a Scalpel: Off-Target Effects of Refusal Removal on Decision Disposition Across Model Families." arXiv 2607.17427, 2026.

[23] N. Truong. "Abliteration Mitigation via Refusal Aliases." arXiv 2608.18093, 2026.

[24] P. E. Weidmann. "Heretic: Fully Automatic Censorship Removal for Language Models." GitHub, 2025. Commit 3521f86.
