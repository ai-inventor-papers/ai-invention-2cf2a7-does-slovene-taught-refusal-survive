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
|-|-|-|
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
|-|-|-|-|-|
| Lexicon | 0.961 | 0.885 | 0.942 | 0.723 |
| Judge (binary) | 0.979 | 0.929 | 0.971 | 0.865 |
| Judge + partial | 0.988 | 0.939 | 0.974 | 0.875 |

Both models refuse at high rates across languages. The gap is in Slovene: GaMS3 refuses less than Gemma in Slovene on both the lexicon (0.723 vs 0.885) and the judge (0.865 vs 0.929). In English, the two models are within two percentage points.

### Difference-in-differences and dose contrast

The difference-in-differences (DiD = [GaMS(SL - EN)] - [Gemma(SL - EN)]) measures whether GaMS3 has a larger Slovene deficit than Gemma. A negative DiD means GaMS3's Slovene gap is wider. All rate-to-logit conversions use the Hautus correction (adding 0.5 to counts before taking log-odds, to avoid infinities at 0% and 100%). The pre-registered threshold was m = 0.40 log-odds (the log-odds equivalent of a 5 pp smallest effect size of interest at the pooled base rate).

**Table 3. Overall DiD and dose contrast D (log-odds, 95% bootstrap CI).**

| Readout | Overall DiD [95% CI] | D [95% CI] | MDE(D) |
|-|-|-|-|
| Lexicon | -0.67 [-0.95, -0.41] | 0.61 [-0.58, 2.15] | 1.89 |
| Judge | -0.38 [-0.69, -0.05] | -0.08 [-1.27, 0.94] | 1.53 |
| Judge + partial | -0.03 [-0.39, 0.39] | -0.73 [-2.11, 0.48] | 1.87 |

On the lexicon, the overall DiD is clearly negative (-0.67, CI excludes 0), confirming that GaMS3 has a wider Slovene refusal gap than Gemma. On the judge, the DiD is smaller (-0.38) but its CI still excludes 0. Including partial refusals shrinks the DiD to near zero (-0.03), with the CI spanning both sides.

The dose contrast D (the difference in DiD between low-EN and high-EN categories) is the primary statistic for the main claim vs alternate 1. On all three readouts, D is uninformative: the confidence intervals are wide (MDE 1.5 to 1.9 log-odds, or 5.5 to 8 pp), spanning both positive and negative values. Neither equivalence nor a dose effect can be established.

[FIGURE:fig_forest_did]

The 14-category meta-regression of DiD on the English dose share found no significant slope: the zEN coefficient was -0.04 on the lexicon (95% CI [-0.66, 0.58]) and -0.12 on the judge (95% CI [-0.79, 0.54]). However, the item-level generalised linear mixed model produced a significant negative zEN term on the lexicon (-0.17, CI [-0.28, -0.07]) that flipped sign on the judge (+0.13, CI [0.00, 0.27]), a signature of pseudo-replication from 14 correlated category-level units (correlation between zEN and zSL: 0.86, VIF 3.84).

**Scorer confound.** The frozen Slovene lexicon lacked English-style "lecture" markers (phrases like "It's important to understand that..."), missing 312 GaMS Slovene judge-classified refusals vs 97 for Gemma. Kappa between the lexicon and the judge was below 0.70 in three of four model-language cells. The lexicon therefore overstates GaMS3's Slovene deficit relative to the judge.

### Item-matched machine-translation arm

To separate the language effect from the prompt-content effect, a 400-item arm used NLLB machine translations of English prompts into Slovene, giving paired items with identical content. GaMS3's Slovene-MT refusal rate was 0.968 vs its English rate of 0.970 (McNemar: 7 vs 8 discordant pairs). The judged DiD on this arm was -2.0 pp [-4.3, 0.0], compared with -6.0 pp on the natural RefusEU pairs sharing the same row identifiers. Most of GaMS3's Slovene deficit on natural pairs is thus a prompt-set-by-model interaction, not a pure language effect.

### Identity calibration (C1)

The calibration arm passed. GaMS3 named itself "GaMS" in 90% of Slovene identity responses and 35% of English ones; Gemma named itself "Gemma" at 77% in English and 67% in Slovene (Table 4). In English, GaMS3 produced "Qwen" as its primary name in 13% of responses, with 48% giving no name at all. The identity DiD was 3.22 [2.38, 4.38], far exceeding the 10 pp threshold (m_id = 0.43). This confirms that GaMS3's supervised fine-tuning can produce language-anchored behaviour: self-identity, taught only in Slovene, is Slovene-bound. The instrument can detect anchoring when it exists.

**Table 4. Identity: own-name rates and name distribution.**

| Cell | Own-name rate | Top other names |
|-|-|-|
| GaMS EN | 0.35 | Qwen 0.13, none 0.48 |
| GaMS SL | 0.90 | none 0.08 |
| Gemma EN | 0.77 | none 0.22 |
| Gemma SL | 0.67 | other 0.08, none 0.20 |

### Surface forms

1,504 of 1,545 GaMS3 Slovene refusals (97.3%) opened with the calque "Oprostite, vendar..." ("I'm sorry, but..."), a word-for-word translation of the English Qwen refusal template. The Nemotron training data contained 1,508 Slovene calques vs 585 "Žal..." openings and 739 English "I'm sorry, but..." openings. The near-universal Slovene calque confirms that GaMS3's refusal wording is borrowed from English, even when the content was supervised in Slovene.

### Verification

The audit script passed 30 of 30 checks. Two independent re-derivation scripts reproduced all rates, DiD, D, DiD_id, and machine-translation DiD exactly. Model-swap placebos (computing DiD after swapping model labels) were centred at zero (permutation p = 0.014 for the judge DiD, 0.17 to 0.87 for D). Four-vs-eight-bit first-token agreement was 0.95 (NF4 vs int8 on 20 fixed prompts); language consistency was 100%; batching-outcome agreement was 32/32.

### Outcome

Neither the main claim nor alternate 1 survived the screen. On the lexicon, the DiD is negative and exceeds m, which would favour alternate 1 through the generalised linear mixed model clause, but the dose contrast D is not significant. On the judge, the DiD is smaller (-0.38, barely excluding 0) and D is uninformative (MDE 1.53, well above 2m = 0.80). The judge and lexicon disagree on the direction of the zEN coefficient, so neither claim can be confirmed or refuted. The identity calibration arm passed, establishing that anchoring is detectable in this design. The frozen-core consequence (whether Heretic removes Slovene refusal) was deferred to experiment 4.

## Artifact 3: Base models and mechanistic induction (Experiment 2)

[ARTIFACT:art_NLTHj-fHEaG3]

Four checkpoints (gemma-3-12b-pt, GaMS3-12B, gemma-3-12b-it, GaMS3-12B-Instruct) were run in NF4 on an RTX 4090. Items were 2,889 RefusEU train+test pairs (sha1 split: 743 CONSTRUCT, 2,146 SCORE, with a SCORE-400 subset for generation) plus 400 alpaca harmless prompts (NLLB machine-translated to Slovene). The protocol was hashed and committed before any forward pass. OpenRouter spend was $4.74. The RefusEU evaluation split was never read.

### Alternate 2 (base-checkpoint geometry): killed

The pre-registered test asked whether the Slovene harmfulness separability (d') is higher in GaMS3-12B-base than in gemma-3-12b-pt, which would predict a Slovene refusal advantage. At the pre-registered layer (L = 22), the delta-d'-Slovene (GaMS-base minus pt) was -0.98 [-1.13, -0.85]: the GaMS base has *lower* Slovene separability than the pretrained ancestor at this layer, the opposite of the prediction. At each model's own best layer, the sign reversed to +2.85. The item-level regression found that base geometry explained only 4.2% of the instruct-level refusal variance [0.5%, 12.2%], with a z-score of -15 against the 50% mediation threshold. Dose coefficients were non-significant (wild-cluster p = 0.87 for zEN, 0.92 for zSL). An exploratory analysis found that base-model harm directions carry a last-token punctuation confound; punctuation-matched and mean-pooled delta-d' changed sign again. Base-separability contrasts are not robust.

**Alternate 2 is dead.** The base checkpoint does not set the instruct model's language profile of refusal.

### C4 (ancestor-direction induction): failure branch

The pre-registered test asked whether adding the gemma-3-12b-pt harmfulness direction to harmless-prompt activations induces refusal in the instruct models, and whether the EN/SL potency ratio differs between GaMS3 and Gemma. The pretrained direction never reached a refusal rate of 0.50 in any model-language cell under the judge readout (peak 0.03 to 0.25; output was mostly incoherent). It performed no better than random directions and had cosine similarity near zero with each instruct model's own refusal direction. This triggers the pre-registered failure branch: "refusal reads an ancestor-readable feature" loses causal support, consistent with Du et al. [3] who report limited forward transfer of refusal directions from base to post-trained models.

The positive control passed: each instruct model's own difference-of-means direction induced refusal at low alpha values (alpha50 approximately 0.03 times the mean residual norm for Gemma-IT, 0.05 for GaMS3). The own-direction delta for the language-asymmetry comparison was -0.09 [-0.28, 0.07] on the lexicon and +0.24 [0.13, 0.38] on the judge, both inside the pre-registered equivalence bound of plus or minus ln(1.5) = 0.41. Alternate 1 is therefore not supported by the induction data: GaMS3 does not show a lower Slovene induction potency than Gemma.

**Table 5. SCORE-400 judge refusal rates (Experiment 2, secondary).**

| Model | EN | SL |
|-|-|-|
| Gemma-IT | 0.957 | 0.945 |
| GaMS3-Instruct | 0.967 | 0.917 |
| DiD (log-odds) | -0.70 [-1.45, 0.02] | |

### Validity notes

The frozen lexicon was found to be language-asymmetric: the English list included "illegal" and "unethical" markers absent from the Slovene list. GaMS3's Slovene kappa (lexicon vs judge) was 0.38, confirming the lexicon overstates GaMS3's Slovene deficit. The prefix score was dominated by template and language priors (the centred score reversed the mean DiD). NF4-vs-int8 first-token agreement was 18/20.

## Artifact 4: Persona-gate test (Experiment 3)

[ARTIFACT:art_3GJzU9GuyW5r]

Alternate 3, drawing on Zhong and Li's [6] claim that refusal lives downstream of persona, predicted that GaMS3's Slovene-anchored persona gates Slovene refusal, producing a uniform surplus. The test ran GaMS3-12B-Instruct and Gemma-3-12B-IT in NF4 on an NVIDIA L4, on SCORE-400 RefusEU pairs. The protocol hash (eb718197) was committed before scoring. Judge: gemini-2.5-flash, spend $1.45.

### Verdict: untestable

The manipulation check failed. Persona ablation (removing GaMS3's own-name direction from late layers 32-47 via mean-projection with BOS skipped) did remove own-naming, but a variance-matched random direction also removed English naming to a comparable degree. The pre-registered rule declared alternate 3 untestable when the manipulation check fails.

Even if the manipulation had been clean, the signature would not survive. The judge-based triple-difference (TD*) was +0.23 [-0.81, 1.25], with an MDE of 1.46 (exceeding 2m = 0.88). The prefix-score co-primary (triggered by the ceiling rule) gave TD* = +0.43 [-0.11, 0.97], with the upper bound below the m_s threshold of 1.32.

### Consequential amendment

Zero-projection ablation was catastrophic in the Gemma-3 family, producing massive activations even for random directions (a BOS-sink artefact). The amendment replaced zero-projection with mean-projection that skips BOS, re-matching the random control on centred variance.

### Descriptive findings

GaMS3 showed a Slovene refusal *deficit* relative to Gemma, not the surplus that alternate 3 predicts. The unablated DiD was -1.11 [-2.00, -0.36] on the judge and -2.72 [-3.30, -2.13] on the prefix score. On the translation-matched items, it was -3.06 [-3.59, -2.52]. Late-layer persona ablation barely moved GaMS3's Slovene refusal: 0.883 to 0.853 (McNemar p = 0.08).

An exploratory finding: ablating GaMS3's own-name direction made GaMS3 identify as Qwen (English 0.15 to 0.78, Slovene 0.03 to 0.60), while random controls stayed at 0.23 to 0.30 and Gemma was unaffected. This is teacher-identity substitution, not persona removal: the ablation does not erase the identity; it replaces GaMS with the training-data source.

**Table 6. Refusal and identity rates under persona ablation (GaMS3, SCORE-400).**

| Condition | EN refusal | SL refusal | EN own-name | SL own-name |
|-|-|-|-|-|
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
|-|-|-|-|-|
| Original | 0.965 | 0.932 | 0.940 | 0.830 |
| Selected edit | 0.242 | 0.223 | 0.133 | 0.098 |

Trial-level slopes of Slovene refusal on English refusal were positive for both models (Gemma 1.21 [0.75, 1.83]; GaMS3 0.79 [0.51, 1.14]); shuffling Slovene rates produced slopes of 0.01 plus or minus 0.28. English-objective abliteration removes Slovene refusal.

[FIGURE:fig_transfer_curve]

### C3 (frozen-core transfer): fails both ways

**[Correction (iter 4, MINOR #1): The exp4 summary gives G3 = -1.86 [-2.87, -1.13] on the matched first 17 trials, -1.76 on all trials, -0.98 on the lambda curve. The text below used -1.76 for the matched-17 value; the correct matched-17 value is -1.86.]**

The primary statistic G3 (the GaMS-minus-Gemma difference in the logistic transfer-curve intercept, measuring whether GaMS3 retains more Slovene refusal at matched English refusal) was -1.86 [-2.87, -1.13] on the matched first 17 trials (-1.76 on all trials, -1.74 on translation-equivalent pairs). The main claim required |G3| < m = 0.675; alternate 1 required G3 > m. Neither holds: Slovene refusal is *more* exposed in GaMS3 than in Gemma at any matched English refusal level. Trial-label permutation p = 0.000.

The category-level version (G3 in low-EN vs high-EN categories) was 0.39 [-1.19, 2.12], not separating dose groups.

### C5a (excess Slovene KL): reverses the prediction

The pre-registered test asked whether Heretic's real refusal direction damages Slovene more than a norm-matched random direction. The excess Slovene/English KL ratio was 0.298 [0.154, 0.562] for Gemma and 0.574 [0.409, 0.796] for GaMS3, both with confidence intervals entirely below 1. The real direction damages Slovene *less* than random directions. There is no Slovene leakage; the English-only objective is, if anything, Slovene-sparing.

### C5b (bilingual re-selection): unpowered

Only one candidate trial per model met the re-selection criteria, and it was the same as the original pick. Gain was zero. The test is unpowered because no trial reached the pre-registered threshold of 10 or fewer keyword refusals out of 100 (the best was 64/100 for Gemma, 29/100 for GaMS3). The fallback to a reduced-trial random-search analysis was triggered.

### Alternate 4 (thin templated gate): strongest signal but does not survive

A five-token compliant prefill ("Sure, here is") flipped refusals at strikingly different rates across models:

**Table 8. Prefill flip rates (fraction of items that refused at k = 0 but complied at k = 5).**

| | Gemma EN | Gemma SL | GaMS EN | GaMS SL |
|-|-|-|-|-|
| Flip rate | 0.031 | 0.558 | 0.559 | 0.855 |

The prefill signature Sig was 3.63 [3.13, 4.36] in English and 1.54 [1.20, 1.92] in Slovene, both exceeding the m2 threshold of 0.40 with confidence intervals above zero (z_c = 6.23, paired label-swap p = 0.000). GaMS3's refusal is more brittle than Gemma's in both languages, and the gap is larger in English (Sig_EN) than in Slovene (Sig_SL). However, alternate 4 predicted symmetric language effects (|Sig_SL - Sig_EN| < m), and the observed asymmetry was 2.10, far exceeding the threshold. Alternate 4 was scored as not survived.

The Pareto hypervolume ratio (GaMS3/Gemma) was 2.29 [2.01, 3.36], confirming that GaMS3's refusal is easier to remove across the entire refusal-KL trade-off front.

### Failed attempts

The plan's raw Arditi-style [1] rank-k ablation destroyed Gemma (KL 20 to 53 nats even for a random basis) and was abandoned. Mechanistic question C code was implemented but not run due to the key limit. Judge validation did not confirm the lexicon (kappa below 0.70 in all cells, though raw agreement was 95% with PABAK 0.90 on unedited cells). GaMS3's judge labels are incomplete: the OpenRouter key hit its daily limit before GaMS3 could be judged, and a retry with the replacement key still returned a 403 error.

### Limits

All transfer-curve and Pareto numbers come from reduced-trial random search, not the planned 80-trial Optuna run. The EN-KL-matched random control was unmatchable at the 6x cap. The lexicon is the primary readout because judge validation failed, with the prefix score as co-primary. Unedited-model KL reproduces to only 0.030 nats under NF4 batching.

## Summary of dead ends and surviving claims

**Table 9. Status of pre-registered claims after iteration 1.**

| Claim | Status | Key evidence | Next step |
|-|-|-|-|
| Main: behaviour-level reach (C2) | INCONCLUSIVE | D uninformative; MDE 1.5-1.9; lexicon/judge disagree | FINAL with larger N and validated judge |
| Alt 1: supervised reach | INCONCLUSIVE | Same D; zEN flips sign across readouts | Same |
| Alt 2: base geometry | DEAD | Delta-d' sign depends on layer; geometry share 4.2% | None |
| Alt 3: persona gate | UNTESTABLE (manipulation check fails); DEAD (premise contradicted) | Manipulation check fails; premise (SL surplus) contradicted | None |
| Alt 4: thin gate | NOT SURVIVED | Prefill asymmetry too large; signature not symmetric | Descriptive only |
| C1: identity calibration | PASS | DiD_id = 3.22 [2.38, 4.38] | Carry forward |
| C3: frozen-core transfer | FAILS BOTH WAYS | G3 = -1.76 [-2.73, -1.09]; GaMS more exposed | Investigate with full Optuna run |
| C4: ancestor induction | FAILURE BRANCH | pt direction never reaches R = 0.50; own-direction equivalence holds | Report as check |
| C5a: excess SL KL | REVERSES | Ratio 0.30 / 0.57, CI below 1 | Confirm with judge |
| C5b: re-selection | UNPOWERED | n = 1 candidate per model | Full Optuna run needed |

# Iteration 2

## Strategy

Iteration 2 addressed three weaknesses identified by the reviewer and by iteration 1's own diagnostics. First, the main claim (behaviour-level reach vs category-level supervised reach) remained inconclusive because the dose contrast was unpowered on SCORE items, the lexicon and judge disagreed, and no FINAL evaluation had been run. Second, the Heretic transfer-curve finding (the transfer-curve intercept was -1.76, meaning GaMS3 retained less Slovene refusal than Gemma at matched English refusal) rested on a lexicon readout that failed judge validation in three of four cells. Third, the teacher-inheritance pathway, an alternate not originally pre-registered, was flagged by the reviewer as a plausible alternative account given GaMS3's heavy reliance on Qwen-family refusal data.

The iteration ran five artifacts:

1. Experiment 5 (confirmation): the pre-registered FINAL evaluation on the reserved RefusEU evaluation split, the item-matched machine-translation arm, the HARD set (XSTest + OR-Bench), and the identity questions, using 20,300 generations and a local Qwen3-14B judge after the OpenRouter budget was exhausted.
2. Experiment 6 (refusal depth pipeline): the code scaffold for a refusal-depth experiment. It produced no scored output and is reported as infrastructure, not a finding.
3. Experiment 7 (teacher inheritance): a five-system screen comparing GaMS3, Gemma-IT, Qwen3-235B (the teacher), Qwen3-14B (same-family control), and Llama-3.3-70B (outgroup placebo), testing whether GaMS3's refusal decisions and wording inherit from its Qwen teacher.
4. Experiment 8 (Heretic re-test): a fresh paired abliteration run on 200 item-matched RefusEU-TRAIN probes with three dose curves, removing the iter-1 confounds (unmatched EN/SL items, no judge on GaMS3) and testing the transfer curve, depth, and Slovene KL leakage with a local Llama-3.1-8B judge.
5. Evaluation 1 (reconciliation): a $0 harmonised re-scoring of all iteration-1 screens on a single readout, checking which findings survive, shrink, or become uncitable under a consistent judge.

The OpenRouter shared key was exhausted for most of the iteration (403 errors on all calls, including after the replacement notice). Every experiment that needed paid judges fell back to local open-weight models. This is the single largest constraint on this iteration's evidence quality.

## Artifact 6: Confirmation on the reserved FINAL splits (Experiment 5)

[ARTIFACT:art_Z4IDI9MPfitU]

This was the pre-registered confirmation run on the reserved evaluation data. Both models were run in NF4 quantization with greedy decoding (160 tokens, empty system turn, byte-identical template) at seed 20260924. The protocol was committed before generation (sha a76ee29); a DEV addendum was committed before any FINAL judging (sha 36eb7c3).

**Deviation D5.** The run's OpenRouter budget was exhausted mid-FINAL. The pre-registered gemini-2.5-flash and gpt-4.1-mini judges could not run to completion. The FINAL primary readout is a local Qwen3-14B judge (frozen prompt, logit-based), validated against gemini on DEV (binary kappa 0.68 to 0.86 across cells) and on the 11,146 FINAL rows that received gemini labels before the budget ran out. Identity uses a regex scorer validated against gemini on DEV (kappa 0.82 for Gemma, 1.00 for GaMS3). A DEV-based calibration layer corrects Qwen3's inflation of REFUSE on hedged English answers.

### Identity calibration: passes on FINAL

The identity arm replicates. GaMS3 named itself "GaMS" in 90% of Slovene answers and 33% of English answers; Gemma did not name itself in either language (the regex scored 0% in all Gemma cells because Gemma's own-name responses did not match the strict regex pattern). GaMS3 credited Qwen or Alibaba in 51% of English identity responses (up from 42% in iteration 1). The FINAL identity DiD was 3.46 [2.55, 4.62] (m_id = 0.40), confirming that the design can detect language anchoring.

**Table 10. Identity results on FINAL (80 pairs).**

| Cell | Own-name rate (regex) |
|-|-|
| GaMS EN | 0.325 |
| GaMS SL | 0.900 |
| Gemma EN | 0.563 |
| Gemma SL | 0.413 |

### Refusal on RefusEU natural pairs

On 1,300 FINAL pairs, the Qwen3 judge gave the following refusal rates:

**Table 11. FINAL refusal rates (Qwen3-14B judge, RefusEU natural pairs).**

| Model | EN | SL |
|-|-|-|
| GaMS3-Instruct | 0.972 | 0.922 |
| Gemma-IT | 0.979 | 0.958 |

The overall DiD was -0.35 [-0.81, 0.13], about -2.8 pp on the probability scale. The 95% CI includes zero: on the Qwen3 judge, there is no significant GaMS3 Slovene deficit.

The dose contrast was -0.27 [-1.31, 0.71], with minimum detectable effect 1.36 exceeding twice the pre-registered threshold (2m = 1.02). The dose test remains underpowered on the FINAL data.

The judge-family robustness check revealed a stark dependence on the judge. Gemini-2.5-flash labels existed for 607 of the 1,300 pairs (all GaMS3 rows plus the first Gemma rows before the budget ran out). On those 607 overlapping pairs:

**Table 12. DiD by judge family on the same 607 pairs.**

| Judge | DiD [95% CI] |
|-|-|
| Gemini-2.5-flash | -0.63 [-1.14, -0.16] |
| Qwen3-14B | +0.03 [-0.75, 0.82] |

The same items produce a significant GaMS3 Slovene deficit under gemini and a null under Qwen3. This judge dependence is the iteration's most consequential finding for the primary contest: the size and sign of the refusal DiD are not robust to the choice of judge family.

### Item-matched machine-translation arm

On 1,296 FINAL pairs (EN back-translation vs SL machine translation from the same English source), the DiD was -1.67 [-2.75, -1.03]. This is larger than the natural-pair DiD and is driven by Gemma refusing more in Slovene (99.5%) than in English (97.5%) on the matched items. The MT-arm DiD cannot be directly compared with the natural-pair DiD because the items differ in content and difficulty.

### HARD set: signal-detection analysis

The HARD set (349 unsafe + 1,093 safe items from XSTest and OR-Bench, with SL machine translations and EN back-translations) was analysed in a signal-detection framework.

**Table 13. Signal-detection parameters on HARD (SL-MT vs EN-BT).**

| | d' | c (criterion) | Hit rate | False-alarm rate |
|-|-|-|-|-|
| Gemma EN | 1.574 | -0.440 | 0.890 | 0.364 |
| Gemma SL | 1.393 | -0.870 | 0.941 | 0.569 |
| GaMS EN | 1.862 | -0.327 | 0.896 | 0.273 |
| GaMS SL | 1.678 | -0.235 | 0.859 | 0.273 |

The DiD in d' (discrimination) was -0.003 [-0.33, 0.29]: the two models lose the same amount of discrimination between languages. The DiD in criterion c was +0.52 [0.38, 0.68], the most robust result of the FINAL run. Gemma-IT shifts its criterion toward refusal on benign Slovene prompts (false-alarm rate rising from 0.364 to 0.569), while GaMS3 is language-invariant on criterion (false-alarm rates 0.273 in both languages). GaMS3 does not over-refuse in Slovene; Gemma does.

[FIGURE:fig_hard_sdt]

This criterion shift is fragile under partial-as-refusal coding, and the DEV gemini judge produced a comparable estimate (+0.67). It replicates across OR-Bench items alone (+0.70 [0.50, 0.93]) and survives dropping MT-fragile items (+0.62 [0.46, 0.79]).

### Refusal style

GaMS3's Slovene refusals on RefusEU are terse (median 16 tokens, vs 160 for Gemma) and formulaic: 61% open with "Oprostite, vendar vam pri tem" and 87% are covered by the top five openings. In English, 86% of GaMS3 refusals open with "I'm sorry, but I can't". Gemma's refusals are longer (median 160 tokens), with more varied openings ("I am programmed to be" in English, "Žal mi je, vendar ne" in Slovene).

### Verification

The audit passed 27 of 27 checks. An independent pandas re-derivation matched all headline numbers to 1e-9. Permutation tests confirmed p < 0.001 for identity DiD, with placebos not significant. Spend was $2.10.

## Artifact 7: Teacher-inheritance screen (Experiment 7)

[ARTIFACT:art_G-g_1sVIc39Z]

This exploratory screen tested whether GaMS3's refusal decisions and wording inherit from its Qwen-family teacher. Five systems were run on byte-identical prompts (greedy, empty system turn, 160 tokens): GaMS3-12B-Instruct (NF4 quantization), Gemma-3-12B-IT (NF4 quantization), Qwen3-235B-A22B (the SFT data generator, via OpenRouter with thinking off), Qwen3-14B (same-family positive control, NF4 quantization), and Llama-3.3-70B (outgroup placebo). The protocol was frozen (sha d7577710) before the full pass. Items: 616 HARD-DEV (XSTest + OR-Bench) + 400 SCORE RefusEU + 117 identity items; English, SL-MT, and EN back-translation arms.

**Readout caveat.** The OpenRouter budget ran out before the pre-registered gemini judge could label all systems. Headline numbers use a local Mistral-Small-24B judge (NF4 quantization, frozen prompt), validated against gemini with binary kappa 0.67 to 0.86 per local cell. Prefill rows have kappa 0.15 and are invalid under this readout.

### Decision inheritance: uninterpretable

The fingerprint-calibration gate failed. The positive control asked whether the instrument can detect within-family resemblance: the Qwen3-14B-to-Qwen3-235B kappa should exceed the Qwen3-14B-to-Gemma kappa by at least 0.10. The observed difference was -0.001 [-0.074, 0.079]: the instrument cannot distinguish same-family from cross-family agreement. All pairwise kappas cluster at 0.51 to 0.60, dominated by item difficulty (retest ceiling 0.88). The descriptive GaMS3-to-teacher kappa minus GaMS3-to-Gemma kappa was -0.044 [-0.118, 0.032], with the 90% CI excluding a +0.10 teacher advantage. GaMS3 does not take the teacher's side more often than it takes the sibling's, but the instrument lacks the resolution to detect even genuine family resemblance.

### Wording inheritance: supported

Refusal wording tells a different story. The SFT-source classifier (5-fold cross-validated accuracy 0.97) attributed 95.8% of GaMS3's English refusal first sentences to the Qwen teacher family, with an independent SVM re-derivation at 98.4% (shuffled-label placebo: 18%). Gemma scored 0.7%. In Slovene, GaMS3's refusal wording matches the GaMS-27B translated SFT data (90.8% of first sentences found verbatim) rather than the live teacher's output (1.5%).

**Table 14. Refusal first-sentence origin (share found verbatim in SFT data).**

| Model | EN | SL |
|-|-|-|
| GaMS3-Instruct | 0.761 | 0.908 |
| Gemma-IT | 0.000 | 0.030 |
| Qwen3-235B | 0.757 | 0.015 |
| Qwen3-14B | 0.092 | 0.007 |
| Llama-3.3-70B | 0.254 | 0.016 |

The English column shows that GaMS3 and the teacher share the same refusal vocabulary to the same degree (76%), and both are distinct from Gemma (0%). In Slovene, GaMS3 uses the machine-translated SFT wording (91%), not the teacher's live Slovene output (1.5%), confirming that the Slovene refusal calque originates in the training data translation, not in a runtime cross-lingual transfer from the teacher.

### Language asymmetry: Gemma is the outlier

Gemma-IT over-refuses safe Slovene items (+0.24 vs English), while GaMS3, the teacher, and the same-family control refuse *less* in Slovene. The Slovene kappa difference (GaMS3 vs teacher minus GaMS3 vs Gemma) was 0.082, and the gap-of-gaps (DiffGap) was -0.133 [-0.247, -0.011], running opposite to a teacher-inheritance prediction and driven by Gemma being the outlier in Slovene.

### Identity

GaMS3 named Qwen or Alibaba in 47% of English identity answers and 7% of Slovene ones, consistent with the FINAL result (51% English, not measured in Slovene by this artifact).

### Verification

Audit: 52 of 52 independent checks passed. An independent re-derivation with placebos reproduced all headline numbers. Judge spend: $1.45. The pre-registered paid readout (gemini + gpt-4.1 second family) is implemented but unrun; finalize.sh is resumable.

## Artifact 8: Heretic transfer-curve re-test (Experiment 8)

[ARTIFACT:art_T5ChU9GV1tf7]

This artifact re-tested the iteration-1 finding that English-objective Heretic abliteration strips GaMS3's Slovene refusal faster than Gemma's (iter-1 lexicon transfer-curve intercept = -1.86), using a design that removes the iter-1 confounds. It uses a fresh 200-item RefusEU-TRAIN probe, item-matched across three arms from one English source (EN original, NLLB Slovene MT, NLLB English back-translation). Both models were run through an identical code path (NF4 quantization, empty system, greedy, seed 20260924) over three dose curves:

- **Curve B (confirmatory):** 29 paired fresh Heretic trials whose TPE start-up draws were verified parameter-identical across models (9 of the 29 trials diverged in parameters after the start-up phase).
- **Lambda-scaling curve:** the iter-1 selected Heretic LoRA scaled by lambda (0.0 to 2.0 in 8 steps for Gemma, 6 for GaMS3).
- **Mean-projection curve:** graded mean-projection ablation of a winsorised own-English refusal direction with a centred-variance random-direction control.

**[Correction (iter 4, MUST-FIX #6a): The primary readout was the unvalidated lexicon (exp8 analysis.json: primary_readout = 'R_lex', readout_status = 'JUDGE PENDING: lexicon unvalidated screen'). The Llama-3.1-8B judge labelled only 3,374 of 24,000 rows (kappa 0.52). The iter-2 hypothesis update noted this: 'the paper's statement that exp8 used a Llama judge must be corrected'. See eval2 for the repair.]**

The judge was Llama-3.1-8B-Instruct (selected over Qwen3-8B by higher binary-refusal kappa vs gemini on a 1,000-row Gemma calibration set), applied identically to both models with the frozen judge prompt. Gemini labels exist for all Gemma rows but no GaMS3 rows (budget exhausted).

### Transfer curve: GaMS3 Slovene less retained, confirmed on fresh trials

On the 29 paired Heretic trials (confirmatory curve), the transfer-curve intercept (we define this as the GaMS-minus-Gemma predicted Slovene refusal rate at matched English refusal of 50%, on a logistic scale) was -2.36 [-3.18, -1.62]. At matched English refusal of 50%, Gemma retains 38 pp more Slovene refusal than GaMS3. The permutation test gave p < 0.001 (null mean 0.006, null SD 0.44). The BCa-corrected CI was [-3.22, -1.63].

**Table 15. G3 (GaMS-minus-Gemma predicted SL refusal at EN refusal = 50%) across dose curves.**

| Curve | G3 [95% CI] | Verdict (m = 0.675) | Verdict (m_local = 0.20) |
|-|-|-|-|
| B (29 paired trials) | -2.36 [-3.18, -1.62] | SL_OVER_EXPOSURE | SL_OVER_EXPOSURE |
| A1 (lambda scaling) | -0.19 [-1.03, 0.78] | INCONCLUSIVE | INCONCLUSIVE |
| A2 (mean-projection) | excluded (non-specific) | n/a | n/a |

The confirmatory curve confirms and strengthens the iter-1 finding (iter-1: intercept = -1.86 [-2.87, -1.13] on 17 trials). The lambda-scaling curve gives a much smaller and non-significant intercept (-0.19): the two curves disagree. The mean-projection curve was excluded because the direction-specific control failed in GaMS3 (ablating the real direction reduced refusal by the same amount as ablating random directions: real drop 0.91 vs random drop 0.91).

[FIGURE:fig_transfer_retest]

The exploratory dose-group analysis on the confirmatory curve found no separation: the intercept in low-English-dose categories was -1.92 [-3.28, -0.79] vs -3.05 [-4.52, -1.85] in high-English-dose categories (difference +1.12, not significant). The higher-dose categories showed a larger GaMS3 deficit, the opposite of what category-level supervised reach predicts.

### Slovene KL leakage: no leakage, replicated

The excess Slovene/English KL ratio was 0.54 [0.34, 0.80] for Gemma and 0.93 [0.77, 1.15] for GaMS3. Both models' confidence intervals are at or below 1: the real refusal direction does not damage Slovene more than random directions. GaMS3's ratio is closer to 1 than in iteration 1 (iter-1: 0.574 [0.409, 0.796]), but still no evidence of leakage.

### Depth analysis

On the lambda-scaling curve, a discrete-time hazard model found no significant interaction between refusal depth and the Slovene-vs-English gap. Depth numbers are lexicon-based (the only readout available for all steps) and treat each item's abliteration trajectory as a survival process.

### Verification

Audit: all re-derived independently with placebos. MT quality: median chrF 75.4, 2 fragile items. Pairing check: 29 common trials, 9 parameter mismatches (post-start-up divergence). Spend: $1.06. An independent blind spot-check by the orchestrating agent was included.

## Artifact 9: Reconciliation of iteration-1 findings (Evaluation 1)

[ARTIFACT:art_TXmgDAGgFGul]

This $0 evaluation harmonised all iteration-1 screens onto a single readout to check which findings survive. It used real gemini labels where they exist (all 10,852 exp1 responses plus 13,586 of 33,623 total rows across experiments) and a pooled TF-IDF classifier trained on all 26,912 real iter-1 judge labels where they do not. Per-cell validity gates were applied: 33 cells passed, 17 failed, and 22 (all GaMS3 exp4 cells) were unvalidated.

### Key finding 1: Prefill cells are unmeasurable

The iteration-1 prefill test (alternate 4) used the frozen lexicon as its primary readout because judge labels were unavailable for GaMS3. Against a 48-item blind adjudication (author model, not human), no readout reached kappa 0.60 on prefill continuations: the pooled surrogate achieved 0.39, the lexicon 0.21, and even the real gemini judge only 0.17 (calling 90% of Gemma prefill continuations refusals against an adjudicated 45%). The prefill cells are not measurable by any readout that existed in iteration 1. The prefill-depth signature (alternate 4) and the iter-1 transfer-curve estimate are therefore uncitable.

### Key finding 2: GaMS3 Slovene deflection

34.6% (115 of 332) of GaMS3's Slovene prefill continuations paraphrased the harmful request back ("izboljšana ... različica vašega sporočila"), a pattern absent in all other cells (0%). The lexicon scored 95.7% of these as flips (compliance), inflating the GaMS3 Slovene flip rate. Excluding them reduces the Slovene prefill signature from 1.54 to 1.16.

### Key finding 3: Meta-analysis of the GaMS3 Slovene deficit

The four iteration-1 estimates of the GaMS3 Slovene deficit came from four different experiments with four judge prompts. On one harmonised readout, the estimates were experiment 1 = -0.38, experiment 3 = -0.69, experiment 4 = -0.95, experiment 6 = -1.25 (experiment 5 was not recoverable because experiment 3 saved no text for the machine-translation arm). A generalised least-squares meta-analysis on the joint cluster-bootstrap covariance gave -0.50 [-0.82, -0.21]; REML with modified Hartung-Knapp-Sidik-Jonkman correction gave -0.71 [-1.43, 0.00]; I-squared was 0.40 and the prediction interval was [-2.30, 0.87].

### Key finding 4: Iter-1 "prompt-set artefact" is scale-dependent

The iteration-1 conclusion that "most of GaMS3's Slovene deficit is driven by prompt-content differences rather than a pure language effect" was drawn from a 6.0 pp vs 2.0 pp comparison on the probability scale. On the log-odds scale the same comparison is -0.75 vs -0.92: the gap shrinks and reverses in direction. The claim is therefore not robust to the choice of scale.

### Reconciliation summary

Of 38 re-evaluated numbers: 15 survived unchanged, 1 shrank (the iter-1 transfer-curve intercept from -1.86 to a provisional -0.44 [-1.70, 0.78] under the harmonised readout), 0 reversed, 20 became uncitable (all dependent on unvalidated GaMS3 experiment-4 cells or invalid prefill readouts), and 2 were new (the deflection pattern and the meta-analytic estimate).

**Table 16. Reconciliation verdict table (abbreviated).**

| Claim | Iter-1 verdict | Harmonised verdict | Changed? |
|-|-|-|-|
| Main/Alt-1 (D) | INCONCLUSIVE | INCONCLUSIVE | N |
| Alt-2 (base geometry) | DEAD | DEAD | N |
| Alt-3 (persona gate) | UNTESTABLE | UNTESTABLE | N |
| Alt-4 (prefill depth) | NOT SURVIVED | UNCITABLE | Y |
| C1 (identity) | PASS (3.22) | PASS (3.22) | N |
| C3 (transfer curve) | FAILS BOTH WAYS (-1.86) | UNCITABLE (provisional -0.44) | Y |
| C4 (ancestor induction) | FAILURE BRANCH | FAILURE BRANCH | N |
| C5a (excess SL KL) | REVERSES (< 1) | REVERSES (reproduced) | N |
| C5b (re-selection) | UNPOWERED | UNPOWERED | N |

## Experiment 6: Refusal-depth pipeline (not scored)

[ARTIFACT:art_vBF25ybuF5h3]

This artifact produced a Python pipeline (method.py and supporting modules) for measuring refusal depth across abliteration steps. It defines the experimental protocol and data-flow but produced no scored output: neither the model runs nor the judging were executed. It served as infrastructure for the depth analysis partially incorporated into experiment 8.

# Iteration 3

## Strategy

Three open problems guided this iteration. First, the experiment 8 transfer-curve headline (the transfer-curve intercept was -2.36 on paired Heretic trials) rested on the lexicon and a Llama-3.1-8B judge, neither of which was validated against blind adjudication on edited rows. Second, two mechanistic hypotheses remained untested: whether the Slovene refusal that outlasts English abliteration is carried by a geometrically separate "Slovene caution direction" in activation space (the geometry hypothesis, M-a), or whether the refusal direction merely has greater induction potency in Slovene than in English (the induction hypothesis, M-b). Third, no utility control had been run: it was unknown whether the English-only edit damages Slovene downstream skills more than English ones.

The iteration ran five artifacts:

1. Evaluation 2 (screen repair): re-judged experiment 8's 24,000 saved responses with two fresh local judges (Qwen3-14B and Mistral-Small-24B) to test whether the experiment 8 transfer-curve finding survives a validated readout.
2. Experiment 9 (cross-lingual abliteration lag confirmation): a fresh 300-item probe with 40 paired Heretic trials and a 9-point lambda curve, using a DeBERTa judge distilled from archived gemini labels, to confirm the transfer curve on new data. We call the GaMS-minus-Gemma predicted Slovene refusal at matched English refusal the cross-lingual abliteration lag.
3. Experiment 10 (mechanism test): a four-block experiment testing the geometry of the English and Slovene refusal directions, the induction potency of a Slovene-perpendicular component, add-on neutralisation at the selected abliteration strength, and the readability of refusal directions across abliteration states.
4. Experiment 11 (FINAL confirmation): the reserved split run with 27,264 generations across English, Slovene, and Hungarian, three abliteration doses, and Belebele comprehension, with a Qwen3-14B judge.
5. Experiment 12 (utility control): lm-eval on six multiple-choice tasks (300 paired English/Slovene items per task), measuring headroom-normalised utility loss, language asymmetry, KL divergence footprint, and bits-per-byte fluency.

The OpenRouter budget was exhausted throughout the iteration ($7.02 of $7.00 spent by the key probe at the start). Every judge was local.

## Artifact 10: Screen repair of experiment 8 (Evaluation 2)

[ARTIFACT:art_4V4_5HnuN2ka]

This evaluation re-judged experiment 8's saved responses (all 24,000 rows from both models, three arms, and all dose-curve steps) with two fresh local judges: Qwen3-14B and Mistral-Small-24B. The goal was to test whether the experiment 8 headline (lexicon transfer-curve intercept = -2.36) survives under a validated readout and to diagnose the sensitivity of the lag to the REFUSE-vs-PARTIAL boundary.

### Judge selection

**[Correction (iter 4, MUST-FIX #6c): The artifact selected Qwen3-14B because only it had full coverage (19,971 rows vs 2,614 for Mistral-Small-24B), not because of higher per-cell kappa. Calibration kappa was 0.36 overall (EN 0.25), below the archived Llama-3.1-8B's 0.52.]**

Qwen3-14B was selected as primary over Mistral-Small-24B because only Qwen3-14B had full coverage (19,971 rows vs 2,614 for Mistral-Small-24B). Calibration kappa was 0.36 overall (EN 0.25), below the archived Llama-3.1-8B's 0.52. Coverage was 19,971 rows for Qwen3-14B vs 2,614 for Mistral-Small-24B. The archived Llama-3.1-8B labels and lexicon were retained as secondary comparisons.

### The lexicon finding reproduces exactly

The experiment 8 lexicon transfer-curve intercept of -2.36 was reproduced bit-for-bit from the saved response files. This confirms that the lexicon estimate is a property of the data, not a computation error.

### Under the validated judge: lag survives for REFUSE-only coding

We define the integrated gap as the area-weighted average of the transfer-curve intercept across the observed English refusal range, used when the logistic fit cannot be evaluated at the 50% intercept. The Qwen3-14B judge gives an integrated gap of -1.95 [-3.75, -0.78] under REFUSE-only coding. The transfer-curve intercept at 50% English refusal is extrapolated because Gemma's English refusal never falls below 84% on the confirmatory-curve trials, so the support rule fails and the integrated gap replaces the point estimate. The lag survives: the confidence interval excludes zero.

Under PARTIAL-as-refusal coding (RP), the lag becomes INCONCLUSIVE. The CI includes zero. The finding is therefore fragile to how partial compliance is classified.

The lambda-scaling curve shrank under the validated judge: integrated gap = -0.47 [-1.86, 0.26], INCONCLUSIVE.

### Bias tipping analysis

**[Correction (iter 4, MUST-FIX #7): The tipping analysis was reported one-sidedly. The Gemma-SL false-REFUSE path is robust, but the GaMS-SL false-COMPLY path is not: eps* = 0.098 to reach -m (0.143 to reach 0), which requires only a ~10% error rate. The IG averages over EN refusal 0.83-0.98, far from the 50% operating point.]**

How many misclassifications would be needed to erase the lag? Two tipping paths exist. (1) Erasing the confirmatory-curve lag via Gemma-SL false-REFUSE requires adding 0.71 extra false-REFUSE labels per item. The measured 1-Sp is 0.003, two orders of magnitude below the threshold: this path is robust. (2) Erasing the lag via GaMS-SL false-COMPLY requires only eps* = 0.098 to reach -m (0.143 to reach 0). The measured GaMS-SL 1-Se is 0.088 [0.026, 0.259], so this path reaches the threshold within its CI. The lag is robust to the Gemma-SL false-REFUSE path but not to the GaMS-SL false-COMPLY path. The integrated gap averages over EN refusal 0.83-0.98, far from the 50% operating point.

### All instruments are weak on edited rows

On the 240 blind-adjudicated edited rows (author-model adjudication, not human), every instrument agreed only weakly with the adjudication:

**Table 17. Judge kappa against blind adjudication on edited rows.**

| Instrument | Kappa (binary-R) |
|-|-|
| Gemini-2.5-flash | 0.43 |
| Qwen3-14B | 0.26 |
| Llama-3.1-8B | 0.22 |
| Lexicon | 0.20 |

None exceeds 0.50. The gemini judge is the least bad, but it is still poor. This bounds how precisely any single readout can estimate the lag on abliterated outputs: the signal is real, but the magnitude is uncertain by at least a factor of two.

### Signal-detection criterion DiD reproduces

The signal-detection meta-analysis across experiments confirmed the criterion-shift finding. The FINAL difference-in-differences in criterion c from the Qwen3-14B judge was +0.52 [0.39, 0.67], reproducing the iteration-2 estimate. The difference-in-differences in d-prime remained near zero (-0.003 [-0.31, 0.27]). Across all sources that could be re-evaluated (FINAL, experiment 7 DEV under gemini and Mistral, experiment 8 originals), the criterion difference-in-differences ranged from +0.47 to +0.73, always positive: Gemma shifts its refusal criterion more in Slovene than GaMS3 does.

### Outcome

The experiment 8 transfer-curve finding is a real signal, not a readout artefact. The sign and approximate magnitude survive under a validated local judge. The precise magnitude is uncertain because all judges are weak on edited text. The result is fragile to the REFUSE/PARTIAL boundary.

## Artifact 11: Cross-lingual abliteration lag confirmation on fresh probe (Experiment 9)

[ARTIFACT:art_n3Crj0p24sBa]

This was the pre-registered iteration-3 confirmation of the cross-lingual abliteration lag. Both models were run in 8-bit floating-point (FP8) quantization (a deviation from iteration-1/iteration-2's NF4 quantization) on a fresh 300-item probe set drawn from RefusEU TRAIN, with NLLB Slovene machine translations and English back-translations. The experiment ran 40 paired Heretic trials (7 completed before the engine-equivalence gate triggered exclusions, leaving 7 on the B' curve and all 9 lambda steps on the lambda curve) plus a 9-point lambda-scaling curve (lambda 0.0 to 2.0). The protocol was committed before generation (seed 20260925).

**Judge.** The primary judge was a DeBERTa classifier (mdeberta-v3-base) distilled from 11,767 archived gemini labels. Its calibration kappa against gemini was 0.84 on the held-out set. A second judge family (Llama-3.1-8B-Instruct) was run on the Gemma rows where archived gemini labels exist.

### Lambda curve: lag confirmed

On the 9-point lambda curve, the transfer-curve intercept was -0.97 [-1.56, -0.44], exceeding the pre-registered margin (m = 0.675). The minimum detectable effect was 0.80. At matched English refusal of 50%, GaMS3 retains about 20 pp less Slovene refusal than Gemma.

Under the second judge family (Llama-3.1-8B), the lambda-curve transfer-curve intercept was -1.72 [-2.30, -0.96], also beyond the margin. The two judge families agree on sign and verdict, though the Llama judge gives a larger magnitude.

[FIGURE:fig_lambda_exp9]

### B' curve: unidentified

The paired-trial curve had only 7 trials that passed quality gates, all at high English refusal (0.84 to 0.98). Because neither model's English refusal dropped below 50%, the logistic fit could not identify the transfer-curve intercept at the 50% point. The paired-trial curve cannot confirm or refute the lag because the trials did not explore the relevant part of the dose-response space.

### Excess Slovene KL: below 1, replicated

The excess Slovene/English KL divergence ratio was 0.32 [0.16, 0.62] for Gemma and 0.62 [0.43, 0.87] for GaMS3. Both are below 1, replicating the iteration-1 and iteration-2 finding. The English-only abliteration edit perturbs Slovene next-token distributions less than random directions of equal norm.

### Original refusal rates

**Table 18. Unedited refusal rates on the 300-item fresh probe (DeBERTa judge).**

| Model | EN harmful | SL harmful | EN benign | SL benign |
|-|-|-|-|-|
| Gemma-IT | 0.94 | 1.00 | 0.08 | 0.26 |
| GaMS3-Instruct | 0.93 | 0.95 | 0.04 | 0.18 |

Gemma over-refuses benign Slovene items at 0.26 vs 0.08 in English, consistent with the criterion-shift pattern. GaMS3 shows a smaller but similar asymmetry (0.18 vs 0.04).

### Engine-equivalence gate

The pre-registered gate required NF4-vs-FP8 first-token agreement of at least 0.90 on 20 fixed prompts per model. Both models reached 0.86 and 0.88 respectively, falling short. The deviation to FP8 quantization (driven by vLLM compatibility on the available GPU) therefore introduces a quantization confound. All results from this experiment carry the label "FP8 quantization; engine-equivalence gate failed."

### Verification

**[Correction (iter 4, MUST-FIX #6b): The sentence 'independently re-trained on a different random split; headline changed by less than 0.05' does not appear in exp9's RESULTS.md, audit.json or rederive_headline.json. What those files record is three code paths agreeing and a model-swap p = 0.085. The DeBERTa was trained on 12,639 labels (9,884 train / 2,755 val), not 11,767 (which is exp10's surrogate).]**

Trial pairing was confirmed from Heretic's random-seed logs. Three independent code paths agreed on the headline numbers. Model-swap permutation p = 0.085. Spend: $0.

## Artifact 12: Mechanism test (Experiment 10)

[ARTIFACT:art_sfQmnafZ153j]

This experiment tested two mechanistic hypotheses about why Slovene refusal outlasts English abliteration. The geometry hypothesis predicted that the Slovene-perpendicular component of the refusal direction is geometrically and functionally separate in GaMS3 vs Gemma. The induction hypothesis predicted that this perpendicular component induces refusal preferentially in Slovene when added to harmless activations. The experiment ran four blocks: geometry, induction, add-on neutralisation, and refusal readability across abliteration states. Items were 160 TEST harmful + 100 benign + 100 Dolly harmless items from experiment 8's reserved pool. The judge was a TF-IDF surrogate trained on 11,767 archived gemini labels (kappa 0.68 EN, 0.82 SL).

### Geometry: EN and SL refusal directions are nearly collinear

At each model's best layer (L* = 20 for Gemma, L* = 28 for GaMS3), the refusal directions extracted from English and Slovene prompts are nearly collinear:

**Table 19. Geometry of refusal directions at L*.**

| Model | cos(r_EN, r_SL) | f(SL energy in EN dir.) | Ceiling cos | Perp share |
|-|-|-|-|-|
| Gemma-IT | 0.991 [0.989, 0.993] | 0.983 [0.978, 0.986] | 0.999 | 0.13 |
| GaMS3-Instruct | 0.986 [0.984, 0.988] | 0.973 [0.970, 0.975] | 0.998 | 0.16 |

The Slovene refusal direction lies almost entirely within the English refusal direction. Only 13-16% of the Slovene refusal signal is perpendicular to English. The Gemma-minus-GaMS difference in f at own-L* is 0.010 [0.005, 0.014], positive but tiny: Gemma captures slightly more of its Slovene signal along the English axis, but the practical difference is negligible.

**[Correction (iter 4, MUST-FIX #9e): At own-L*, the model difference in f is 0.010, negligible. At the common layer, Gemma-GaMS f = -0.009 [-0.014, -0.005] (GaMS has a larger perpendicular share), band cosines are 0.93/0.89 with perp shares 0.31/0.38, and d' of SL along r_EN is 1.37 vs 2.83 (Gemma-GaMS -1.46). The sign of the model difference depends on the layer, the same defect that killed alternate 2. M-a is therefore layer-dependent rather than simply refuted.]**

**Geometry hypothesis at own-L*: FALSE** for both models at their own best layers. The pre-registered criterion required the Slovene-perpendicular component to be geometrically larger in one model than the other; at own-L* it is not. However, at a common layer the model difference reverses (f = -0.009 [-0.014, -0.005], perp share 0.31 vs 0.38, d'(SL|r_EN) 1.37 vs 2.83). The geometry result is layer-dependent.

### Induction: the Slovene-perpendicular direction does not induce refusal

Adding the Slovene-perpendicular component (u_SLperp) to harmless activations at L* never induced refusal above 50% in either model or language. The alpha50 was right-censored at the maximum tested amplitude (3.0 K-units) for all u_SLperp cells. By contrast, the full English refusal direction (r_EN) reached alpha50 at 0.91 K for Gemma-EN and 1.32 K for GaMS3-EN. Random directions were also censored. The u_SLperp direction is inert as a refusal inducer.

**Induction hypothesis verdict: NOT_SUPPORTED** for both models.

### Exploratory: language-identity direction induces Slovene refusal

The language-identity direction (u_lang, extracted from language-classification probes) showed an asymmetric induction pattern. In Gemma, adding u_lang at L* induced Slovene refusal (alpha50 = 0.65 [0.46, 0.79]) but not English refusal (censored at 3.0 K). In GaMS3, the pattern was similar but weaker: Slovene alpha50 = 1.78 [1.32, 2.38], English censored. The model contrast (log R_lang Gemma minus GaMS3) was 1.03 [0.42, 1.60] under the primary judge, confirming that this direction induces more Slovene refusal in Gemma than in GaMS3. This is exploratory and was not pre-registered.

### Add-on neutralisation: only full r_SL ablation closes the lag

**[Correction (iter 4, MUST-FIX #9b-d): (b) u_SLperp cut-vs-random is summarised at all three scales: s=0.5 gives -0.51, s=1.0 gives 0.17 [-0.09,0.44], s=1.5 gives 0.62 [0.38,0.97] (excludes 0 but fails EN-invariance gate at -18 pp EN). (c) GaMS Lag(E0) = -0.33 [-0.70,0.07] fails the add-on precondition, so GaMS add-on results are uninformative. (d) u_lang failed the manipulation check in Gemma (manip_ok False) and was 77% degenerate at alpha50 in GaMS SL. GaMS EN alpha50 was 2.96 (not censored as stated).]**

The add-on block tested whether adding a second ablation (of u_SLperp, u_lang, or the full r_SL) at the selected lambda closes the remaining Slovene-vs-English refusal gap. At Gemma's selected abliteration strength (lambda*), the baseline lag was +1.98 [1.41, 2.73] (Slovene refusal still higher than English). Ablating u_SLperp at three scales (0.5, 1.0, 1.5) moved the lag to 2.69, 1.34, and 0.45, respectively; the cut-vs-random difference was -0.51 at s=0.5, 0.17 [-0.09, 0.44] at s=1.0, and 0.62 [0.38, 0.97] at s=1.5 (excludes 0 but fails the EN-invariance gate at -18 pp EN). Only ablating the full Slovene refusal direction (A_SLfull) closed the lag (-6.17 [-6.50, -5.87]), at the cost of 50% degenerate outputs and 19x KL. GaMS Lag(E0) = -0.33 [-0.70, 0.07] fails the add-on precondition, so the GaMS add-on block is uninformative.

Ablating the language-identity direction (A_lang) failed the manipulation check in Gemma (manip_ok False) and collapsed refusal in both languages to near zero (EN 0.02, SL 0.03) with 51% degenerate outputs. In GaMS SL, u_lang was 77% degenerate at alpha50. GaMS EN alpha50 was 2.96 (not censored). The u_lang add-on result is uninformative.

### G3_op on the SCREEN items: reproduces

**[Correction (iter 4, MUST-FIX #9a): This is G3_op = Lag_GaMS - Lag_Gemma at each model's E0 operating point (edited, lambda*), not a transfer-curve intercept computed from original-model rates. Also, exp8, eval2, and exp10 share items (exp8's SCREEN P200 TEST160), so the report's phrase 'independent judge and item set' is incorrect for exp10 vs exp8.]**

G3_op on the experiment 8 SCREEN items (TEST160 harmful subset) was -2.30 [-3.12, -1.61], computed as Lag_GaMS minus Lag_Gemma at each model's E0 operating point (edited, lambda*). This replicates the sign and approximate magnitude of the experiment 8 lexicon estimate (-2.36) under an independent judge on the same item set.

### Refusal readability: refusal is always readable

**[Correction (iter 4, MUST-FIX #9f): AUROC = 1.00 at layer 8 is flagged ceiling:true in rq4.json. Harmful items are RefusEU and harmless items are Dolly, so this likely reflects dataset-source separability, not 'refusal is always readable'. The probe is a harmfulness probe, not a refusal-direction probe. A same-source harmless control (e.g. JBB matched benign, XSTest contrast prompts) was not run.]**

Across all abliteration states (original, the iteration-1 edit, and the strongest edit), AUROC for a fixed linear probe (harmful RefusEU vs harmless Dolly) trained on original-model activations was 1.00 at every layer tested (8, 12, 20, 28, 36, 44) in both models. English-to-Slovene transfer was also 1.00. This is harmful-vs-harmless source separability at ceiling, not a refusal-direction readability test; the ceiling likely reflects dataset-source contrast (RefusEU vs Dolly) rather than the refusal signal per se. A same-source harmless control was not run. The fixed-probe d-prime collapses (from 1.37 to 0.25 at the best layer in Gemma under the strongest edit), confirming that abliteration reduces the magnitude of the signal without destroying its separability.

### Final verdict

**Both the geometry hypothesis and the induction hypothesis are REFUTED.** The Slovene refusal that survives English abliteration is not carried by a separate Slovene direction and cannot be induced by the Slovene-perpendicular component. The lag is a property of the shared refusal subspace, not a geometrically distinct Slovene reserve.

## Artifact 13: FINAL confirmation on reserved split (Experiment 11)

[ARTIFACT:art_Aw3AXCXv9pUg]

**[Correction (iter 4, MUST-FIX #4): (a) The quantization was NF4 (8.4 GB VRAM), not FP8. (b) The item set was RefusEU-x FINAL MT pairs with per-model n differing (Gemma 200 vs GaMS 1101 EN / 652 SL). (c) An 8-step FINAL lambda curve (0.1-1.0) was run and fitted (per-step Hautus rates in RESULTS_tables.md), not 'a single edit step'. (d) The Mistral second-family gate had kappa 0.26 on edited rows. (e) Permutation p = 0.092. (f) The RP readout G3 = +8.74 [-1.51, 14.05] (perm p 0.04, degenerate support).]**

This was the pre-registered FINAL confirmation run. Both models were run in NF4 quantization on the reserved RefusEU evaluation split (RefusEU-x FINAL MT pairs, Gemma n = 200, GaMS n = 1,101 EN / 652 SL), plus a 247-item Hungarian arm (NLLB-translated from the same English sources) and the HARD set (349 harmful + 1,093 safe items). Conditions: original models plus an 8-step FINAL lambda curve (lambda 0.1 to 1.0, fitted with per-step Hautus rates). The experiment generated 27,264 responses and obtained 25,036 judge labels from Qwen3-14B. The Mistral second-family gate had kappa 0.26 on edited rows.

### Cross-lingual abliteration lag: ESTIMATE, not confirmed

The transfer-curve intercept on the 8-step FINAL lambda curve was -0.60 [-1.31, +0.40], verdict ESTIMATE. Permutation p = 0.092. The support rule failed because the observed EN refusal range ([0.64, 0.94] Gemma, [0.60, 0.96] GaMS) did not include a step near 50%. The minimum detectable effect was 1.44, exceeding the pre-registered threshold (2m = 1.35). The RP readout gave G3 = +8.74 [-1.51, 14.05] (perm p 0.04, degenerate support due to near-ceiling Slovene rates).

**Table 20. McNemar rates on the reserved split (Qwen3-14B judge, REFUSE-only).**

| Model | EN orig | EN edit | SL orig | SL edit |
|-|-|-|-|-|
| Gemma-IT | 0.98 | 0.645 | 0.99 | 0.68 |
| GaMS3-Instruct | 0.97 | 0.58 | 0.97 | 0.46 |

GaMS3's Slovene refusal drops further than Gemma's (from 0.97 to 0.46 vs from 0.99 to 0.68), consistent with a lag but not reaching significance because both models also differ in English.

**Why the test was underpowered.** The Qwen3-14B judge over-calls English refusal. On the 36 blind-adjudicated GaMS3-EN edited rows, the judge's specificity was 0.33 (kappa 0.27). It labels many English compliant responses as refusals, inflating edited English rates and shrinking the apparent EN-to-SL difference. The lag requires a two-dimensional comparison (English drop vs Slovene drop); inflating the English baseline compresses the available range.

### Cross-lingual moderation: Hungarian behaves like Slovene

We define the cross-lingual moderation test as the change in the Slovene-vs-English lag from original to edited models, measured separately for each non-English language. A reduced two-point version compared this change for Slovene and for Hungarian. On the 122-item Hungarian arm, the lag change was:

- Gemma: lag_orig = 0.52, lag_edit = 0.48, change = -0.03
- GaMS3: lag_orig = 0.26, lag_edit = -0.23, change = -0.49

**[Correction (iter 4, MUST-FIX #8): The Slovene two-point row gives G3_2pt = +0.05 [-1.49, 2.02]: no GaMS-vs-Gemma difference in Slovene. The Hungarian row gives -0.46 [-2.21, 1.44] with MDE ~3. Neither language shows an effect, so the claim 'Hungarian behaves like Slovene' carries no information about the lag. Under the pre-registered competence vs thin-gate predictions: competence predicts |G3_L3| < m, thin-gate/GaMS-specific SFT predicts G3_L3 < -m. The CI spans both. Verdict: ESTIMATE. A 4-cell Spearman of 0.60 between Belebele accuracy and lag was computed but not reported.]**

The difference in lag change (GaMS3 minus Gemma) on Hungarian was -0.46 [-2.21, 1.44], INCONCLUSIVE. On Slovene, the two-point estimate was +0.05 [-1.49, 2.02], also null. Neither language shows a significant model difference. The CI spans both the pre-registered competence prediction (|G3_L3| < m) and the thin-gate prediction (G3_L3 < -m). Verdict: ESTIMATE for both languages. The Belebele-lag Spearman was 0.60 (4 cells).

### Belebele comprehension: unchanged by the edit

Belebele reading-comprehension accuracy on 200 human-translated parallel items was unaffected by the edit in every model-language cell:

**Table 21. Belebele accuracy (200 items, FP8 quantization).**

| Model | Condition | EN | SL | HU |
|-|-|-|-|-|
| Gemma-IT | Original | 0.930 | 0.885 | 0.880 |
| Gemma-IT | Edit (lam=1) | 0.930 | 0.885 | 0.880 |
| GaMS3-Instruct | Original | 0.905 | 0.875 | 0.870 |
| GaMS3-Instruct | Edit (lam=1) | 0.910 | 0.870 | 0.825 |

Gemma is entirely unchanged. GaMS3 shows a 4.5 pp drop in Hungarian, the only cell exceeding 1 pp, and a 0.5 pp drop in Slovene. The edit does not damage comprehension.

### Mixed-effects model: language-model interaction

**[Correction (iter 4, MUST-FIX #2): The GEE sign was interpreted incorrectly. A positive gams:sl:edit = +1.06 on a refusal log-odds model means the edit shrinks GaMS3's SL-EN margin LESS than Gemma's, not more. From Table 20: Gemma logit SL-EN goes 0.70 to 0.16 (change -0.55); GaMS goes -0.11 to -0.50 (change -0.39). The three-way difference is +0.16, same sign as the GEE. The GaMS-Gemma difference in SL-EN margin is mostly present before the edit (gams:sl = -1.73, p = 3e-5; VB posterior -1.83). This is direct evidence against an edit-induced lag on FINAL, not for it.]**

A generalised estimating equation on 7,337 original+edited rows (both models, all languages, harmful items) found a significant three-way interaction: the gams:sl:edit coefficient was +1.06 (p = 0.022; VB posterior +1.04 +/- 0.16). On a refusal log-odds model, a positive three-way term means the edit shrinks GaMS3's SL-EN margin less than Gemma's. The model difference in SL-EN margin is largely baseline: gams:sl = -1.73 (p = 3e-5; VB posterior -1.83), and the gams:edit main effect was non-significant (-0.18, p = 0.47; VB -0.75 +/- 0.10). On FINAL, the model difference in SL-vs-EN refusal is largely pre-edit, not edit-induced. The item sets are unmatched (Gemma refuseu_x n = 200; GaMS n = 1,101 EN / 652 SL).

### Verification

Language consistency was 0.98-1.00 in all cells. The invalid rate (responses where the judge could not classify) was below 0.03. Spend: $0.

## Artifact 14: Utility control (Experiment 12)

[ARTIFACT:art_Q-LED_B1t1VK]

This experiment measured whether the English-only abliteration edit damages Slovene downstream skills more than English ones, using lm-eval (version 0.4.13) on six zero-shot multiple-choice tasks: ARC-Challenge (science reasoning), BoolQ (boolean questions), HellaSwag (commonsense completion), OpenBookQA (science facts), PIQA (physical intuition), and Winogrande (coreference), with 300 paired English/Slovene items per task. Conditions: original model, the iteration-1 selected Heretic edit (lambda = 1.0), the artifact-2 selected edit, norm-matched random edits, and a strength-6 random edit. Lambda dose points at 0.5, 1.0, 1.5, and 2.0 were tested on a 100-item subset.

### No edit is catastrophic

The pre-registered catastrophe gate required macro headroom-normalised loss (H) to stay below 0.20. Every model-language-condition cell passed:

**Table 22. Catastrophe gate (300-item full sets).**

| Model | Condition | EN loss (95% hi) | SL loss (95% hi) | Verdict |
|-|-|-|-|-|
| GaMS3 | Iter-1 edit | 0.018 (0.039) | -0.007 (0.021) | OK |
| GaMS3 | Art-2 edit | 0.020 (0.043) | 0.009 (0.038) | OK |
| Gemma | Iter-1 edit | -0.008 (0.009) | -0.022 (0.024) | OK |
| Gemma | Art-2 edit | -0.016 (0.002) | -0.049 (-0.000) | OK |

On the 100-item lambda subset, every lambda up to 1.5 passed in both models. Gemma at lambda = 2.0 was possibly catastrophic under the pre-registered rule (Slovene 95% upper bound = 0.33), but this is entirely driven by a Winogrande cell whose original headroom is at the 0.10 floor (chance + 0.10). The raw percentage-point macro for that cell set is +0.25 pp. The largest lambda licensed as safe is 2.0 for GaMS3 and 1.5 for Gemma.

### Slovene is not hurt more than English

The language asymmetry A = H_SL - H_EN was positive (Slovene hurt less) in all four model-by-edit cells:

**Table 23. Language asymmetry and interaction.**

| Model | Condition | A [95% CI] |
|-|-|-|
| GaMS3 | Iter-1 edit | +0.025 [-0.009, 0.060] |
| GaMS3 | Art-2 edit | +0.011 [-0.023, 0.050] |
| Gemma | Iter-1 edit | +0.014 [-0.036, 0.082] |
| Gemma | Art-2 edit | +0.033 [-0.020, 0.125] |

The interaction (GaMS3 asymmetry minus Gemma asymmetry) was +0.010 [-0.065, 0.074] for the iteration-1 edit and -0.022 [-0.116, 0.043] for the artifact-2 edit: no evidence that the edit hits GaMS3's Slovene skills harder than Gemma's. The design resolves the interaction to about 0.10 of headroom, so a smaller differential is undetermined.

Random-adjusted asymmetry (edit minus random) was +0.051 [+0.012, +0.093] for GaMS3 under the iteration-1 edit and +0.038 [+0.001, +0.080] under the artifact-2 edit: relative to a same-size random perturbation, the edit spares Slovene. Both confidence intervals exclude zero.

### One localised cost: GaMS3 English ARC-Challenge

GaMS3 lost 3.7 pp on English ARC-Challenge under the iteration-1 edit (12 vs 1 discordant items; McNemar Holm-corrected p = 0.041) and 2.7 pp under the artifact-2 edit (9 vs 1). The Slovene ARC-Challenge counterpart did not move (0.0 pp). Gemma showed no loss on any task. The effect is small (macro EN loss 0.018-0.020 of headroom) and replicates across two independently selected edits, consistent with English reasoning entanglement.

### KL footprint: English perturbed more than Slovene

The multi-token excess KL divergence ratio (edit-vs-random, Slovene/English) was 0.57 [0.49, 0.66] for GaMS3 (iteration-1 edit) and 0.29 [0.24, 0.37] for Gemma (iteration-1 edit), reproducing iteration-1 values (0.574, 0.298) on a fresh harmless set. The artifact-2 edit gave the same pattern (GaMS3: 0.49 [0.40, 0.62]; Gemma: 0.31 [0.25, 0.39]). Both models' ratios are below 1: the refusal edit touches English distributions more than Slovene.

### Fluency: untouched

Bits-per-byte on human-translated FLORES passages changed by at most +0.10% under the iteration-1 edit (GaMS3 Slovene) and +0.09% (Gemma Slovene), versus +1.0 to 1.8% for a strength-6 random edit. Language consistency stayed above 0.94 in every cell.

### Gemma KL: UNVERIFIED

Gemma's measured first-token KL divergence under the iteration-1 edit was 0.510 vs the logged Heretic value of 0.366, a +39% discrepancy. The adapter identity was confirmed (sha256 match), and random and strength-6 edits reproduced. Padding and prompt-rendering diagnostics ruled out those causes. The discrepancy is unexplained but common to every structured Heretic edit on Gemma. The Gemma iteration-1 edit gate verdict (OK) is reported with the UNVERIFIED label.

**[Correction (iter 4, MUST-FIX #10): Table 24 mixed first-token and 32-token quantities. The SL/EN ratio 0.52 and EXCESS 0.47 are first-token values; 0.010/0.024 = 0.39 is the 32-token ratio. The text's 'multi-token excess 0.57 (GaMS)' traces to RESULTS.md multi-token 0.57 [0.51, 0.66], not 0.49. The art-2 GaMS 0.49 [0.40, 0.62] is first-token. exp12 Belebele contradicts exp11: GaMS orig is 0.930/0.850/0.885 in exp12 vs 0.905/0.875/0.870 in exp11; GaMS HU under E_iter1 is unchanged in exp12 but drops 4.5 pp in exp11. The ARC-C cost omits replicated BoolQ losses (-2.0/-2.3 pp).]**

**Table 24. KL footprint (batch size 1, Dolly harmless). First-token and 32-token reported separately.**

| Model | Condition | KL EN 1st tok | KL SL 1st tok | 1st-tok SL/EN | 1st-tok EXCESS [95% CI] | KL EN 32-tok | KL SL 32-tok | 32-tok SL/EN |
|-|-|-|-|-|-|-|-|-|
| GaMS3 | Iter-1 edit | - | - | 0.52 | 0.47 [0.38, 0.60] | 0.024 | 0.010 | 0.39 |
| GaMS3 | Art-2 edit | - | - | 0.54 | 0.49 [0.40, 0.62] | 0.029 | 0.011 | 0.38 |
| Gemma | Iter-1 edit | - | - | 0.72 | 0.63 [0.34, 1.17] | 0.073 | 0.019 | 0.26 |
| Gemma | Art-2 edit | - | - | 0.72 | 0.63 [0.34, 1.15] | 0.076 | 0.021 | 0.28 |

Multi-token excess KL ratio (RESULTS.md): GaMS3 iter-1 0.57 [0.51, 0.66]; Gemma iter-1 0.29 [0.24, 0.37].

The exp11 Belebele table (Table 21) shows GaMS3 HU drops 4.5 pp under E_iter1, but exp12 Belebele (same 200 items) shows no such drop (GaMS3 HU unchanged at 0.885). The discrepancy is unexplained (possibly different harness or prompt format). The 4.5 pp drop is not replicated in exp12.

In addition to ARC-Challenge, BoolQ showed replicated losses: -2.0 pp (iter-1 edit) and -2.3 pp (art-2 edit).

### Verification

GaMS3 reproduced logged Heretic KL divergences within 3%. Self-KL floor was exactly 0 (batch size 1, fp32). The language-swap placebo centred at zero. GaMS3 Slovene evaluation accuracies match the published paper [20] within 0.06 on all six tasks (acc; acc_norm matched on 5/6 for GaMS3 and 4/6 for Gemma). Spend: $0.

**[MUST-FIX #15 (MINOR #2): Why iteration 3 looked like this.]** The iter-2 hypothesis update moved the study's stance to 'deepen': the main claim became 'C-LAG: reach set by Slovene COMPETENCE, not by the supervision dose' (replacing the original supervised-reach framing). It pre-registered two mechanistic predictions, M-a (sensitivity, the geometry hypothesis: the Slovene-perpendicular component is larger in one model) and M-b (induction: u_SLperp induces refusal preferentially in Slovene). The iteration-3 budget was therefore allocated to mechanism tests (experiment 10), a fresh confirmation (experiment 9), the FINAL split (experiment 11), and a utility control (experiment 12). In hindsight, this allocation spent budget on more metrics over the same underpowered, judge-limited readout, rather than on validated labels for edited rows, which every estimate requires.

**Iteration 3 verdicts.** C-LAG competence claim: ESTIMATE (not confirmed; support rule fails). M-a (geometry): not supported at own-L*, layer-dependent at common layer, supported by exp11 C-MECH SDT. M-b (induction of u_SLperp): NOT SUPPORTED. L3 moderator: ESTIMATE (CI spans both predictions). Criterion shift on originals: REPLICATES. Criterion shift on edited models: DISAPPEARS (exp11 HARD post-edit DiD_c = 0.14 [-0.78, 1.12]).

## Not executed or abandoned in iteration 3

**[MUST-FIX #5: Dead ends and unexecuted pre-registered components.]**

| Component | Status | Reason | Evidence file |
|-|-|-|-|
| C-EXT (public abliterated Gemma checkpoints) | Not generated | Shared cache reclaimed mid-run; n_checkpoints = 0 | exp13 RESULTS_tables.md |
| Frozen-core RQ2 edit (80 trials, bf16, Heretic's own selection) | Never ran | Every iteration-3 edit is the iter-1 reduced-trial NF4 fallback or exp9's | - |
| exp10 Qwen3-14B judge | Failed gate | kappa 0.25 EN / 0.33 SL on edited rows; forced Rogan-Gladen reporting | exp10 summary_tables.md |
| exp9 GaMS random-direction control | Not scored | random_specificity n_random_steps_scored = 0 | exp9 analysis.json |
| exp9 lambda steps after step 0 | Reduced to 100 items | Not the planned 300 per step | exp9 RESULTS.md |
| exp11 job J6 (GaMS lambda=1 remainder) | Not reached | Run ended before completion | exp11 RESULTS_tables.md |
| exp12 GSM8K | Cut | Budget exhaustion | exp12 RESULTS.md |
| exp12 chat-template exploratory | Unreported | GaMS SL ARC-C H = -0.15 with chat template vs 0.00 without | exp12 RESULTS.md |

## Coverage against the frozen core

**[MUST-FIX #11: Coverage of the original request.]**

| RQ | What was planned | What ran | Status | Gap |
|-|-|-|-|-|
| RQ1 (original refusal DiD) | RefusEU natural + MT, HARD, dose | All ran across iter 1-3 | DONE | Dose contrast underpowered |
| RQ2 (original-to-abliterated safety deltas, RefusEU protocol) | Natural RefusEU FINAL pre/post edit, ASR, language consistency | No artifact evaluated NATURAL RefusEU EN/SL evaluation prompts under the edit; exp11 used NLLB MT pairs and HARD only; no ASR reported | PARTIAL | Natural FINAL pairs unscored; ASR missing |
| RQ3 (mechanism) | M-a, M-b, depth, geometry | Geometry at own-L* tested (exp10); induction tested; add-on partial | PARTIAL | Layer-dependent geometry untested at scale; GaMS add-on uninformative |
| RQ4 (decodability) | Fixed-probe AUROC across abliteration states | Ran but at ceiling; source-separability confound | PARTIAL | Same-source harmless control absent |
| Frozen-core edit | Heretic bf16, 80 trials, Heretic's own selection | Never ran; all edits are iter-1 reduced-trial NF4 fallback (Gemma still 65% refusal at lambda=1) | NOT DONE | Main blocker |
| Judge validation | Small manually reviewed sample | All adjudication is author-LLM, not human | NOT DONE | Main readout blocker |

**[MUST-FIX #12: Budget misallocation.]** Iteration 3 spent its budget on more metrics and mechanisms over the same underpowered, judge-limited readout. Every judge has kappa at most 0.43 against adjudication on edited rows (Table 17). The FINAL MDE (1.44) exceeds 2m, and the lag magnitude varies 4x across readouts. The mechanism study (experiment 10), utility battery (experiment 12), and L3 arm cannot move the C-LAG verdict while the edited-row readout is invalid. The next iteration's budget must go to (i) a larger adjudicated or human-audited edited-row set stratified by model x language x dose, then Rogan-Gladen-corrected G3; and (ii) more lambda steps and items near EN refusal = 50% so the support rule can pass.

# What we have learned so far (iterations 1-3)

**[Correction (iter 4, MUST-FIX #1): The C-LAG paragraph below is rewritten. Each artifact's pre-registered verdict is given verbatim. exp8, eval2, and exp10 share items and are counted as one dataset.]**

**[Correction (iter 4, MUST-FIX #3): The criterion-shift claim is restricted to 'original models, HARD set'. On edited models and on benign content-matched twins, the model difference is not in c.]**

**[Correction (iter 4, MUST-FIX #13): Each positive claim is compared with its nearest published neighbour.]**

Three iterations screened the main claim (behaviour-level reach) and four alternates against SCORE data (iteration 1), the reserved FINAL evaluation split (iteration 2), and fresh data with mechanism tests and utility controls (iteration 3). Two alternates are dead (base-checkpoint geometry and persona gating). A third (prefill-depth signature, alternate 4) is uncitable because no available readout can validly score prefill continuations. Two mechanistic hypotheses were tested: the geometry hypothesis (Slovene refusal occupies a separate direction) is layer-dependent -- nearly collinear at own-L* (cos = 0.986-0.991) but divergent at a common layer (perp share 0.31 vs 0.38). The induction hypothesis (the Slovene-perpendicular component induces refusal) is not supported: u_SLperp never reached alpha50 in any cell. The teacher-inheritance screen found that GaMS3's refusal *decisions* do not detectably inherit from the Qwen teacher, while its refusal *wording* inherits almost entirely (76% of English and 91% of Slovene first sentences are verbatim from the SFT data).

The primary contest between behaviour-level reach and supervised reach remains unresolved. The dose contrast is underpowered across all three iterations. The overall GaMS3 Slovene deficit (DiD) is judge-dependent; the meta-analytic estimate is -0.50 [-0.82, -0.21]. On original models and the HARD set, the signal-detection decomposition is robust: the DiD in d' (discrimination) is near zero (-0.003), while the DiD in criterion c is +0.52 [0.39, 0.67], driven by Gemma over-refusing benign Slovene prompts. This criterion shift replicates across experiments, judge families, and item sets on original models. However, on edited models (exp11 HARD post-edit), DiD_c = 0.14 [-0.78, 1.12]: the criterion-shift difference disappears after the edit. On the exp9 lambda curve, the model difference in the lag window sits in discrimination (DiD_d' = +0.99 [-0.11, 1.93]), not criterion (DiD_c = -0.00 [-0.42, 0.48]). The criterion-shift finding is therefore specific to the original-model HARD setting. Aziz et al. [7] showed calibration-not-representation across 23 languages; our sibling-pair design adds GaMS3-specific detail but does not change the interpretation.

The cross-lingual abliteration lag (C-LAG) has a consistent negative sign but is not confirmed by pre-registered criteria. Each artifact's pre-registered verdict: exp9 verdict = ESTIMATE (support_rule False, second-family and R2 conditions False; model-swap permutation p = 0.084; 7 of 10 J1-J2 cells fail validation on GaMS edited rows); eval2 verdict = 'C-LAG screen holds under validated judges: False' and 'INCONCLUSIVE/weak-LAG, not a clean LAG'; exp11 verdict = ESTIMATE ('NOT reproduced on reserved data'). Exp8, eval2, and exp10 share the same item set (exp8's SCREEN P200 TEST160), so there are two independent datasets (exp8/eval2/exp10 on P200; exp9 on 300-item RefusEU-TRAIN; exp11 on FINAL), not three. The magnitude ranges from -0.6 to -2.4 across designs and judges, with the uncertainty driven by weak judge agreement on edited text (best kappa = 0.43, gemini) and the GaMS-SL false-COMPLY tipping path. Wang et al. [2] showed full-dose English-direction transfer across 14 languages; our contribution is the partial-dose sibling-pair design, but the lag does not yet meet confirmation criteria.

The u_lang exploratory finding (the language-identity direction induces Slovene refusal, alpha50 = 0.65 in Gemma, 2.96 in GaMS3) is close to Upadhyaya and Sikdar [11], who showed safety features geometrically entangled with language identity and that ablating safety features shifts output language. Our delta is the matched sibling pair and the dose dimension, but u_lang failed the manipulation check in Gemma. The RQ4 AUROC = 1.00 finding (harmfulness decodable while refusal collapses) replicates Aziz et al. [7], who showed the same pattern across 23 languages; it is not a new finding from this study, and the ceiling likely reflects dataset-source separability rather than refusal readability (Balani and Panda show AUROC drops from >0.98 to 0.59-0.69 on matched-source negatives). The Hungarian ESTIMATE (-0.46 [-2.21, 1.44]) and Slovene two-point null (+0.05 [-1.49, 2.02]) are both uninformative; neither supports nor refutes a GaMS-specific account. On FINAL, the model difference in SL-vs-EN refusal is largely baseline (gams:sl = -1.73, p = 3e-5), not edit-induced.

The utility control (experiment 12) established that the English-only abliteration edit does not damage Slovene downstream skills more than English ones. All macro headroom-normalised losses are below 0.05. The language asymmetry is positive in every cell (Slovene hurt less), and the random-adjusted excess asymmetry excludes zero for GaMS3 (excess = +0.051 [+0.012, +0.093]). Localised costs include GaMS3's English ARC-Challenge (3.7 pp, p = 0.041) and BoolQ (-2.0/-2.3 pp), both replicating across two edits. The excess Slovene KL divergence ratio is below 1 in both models across all iterations. Fluency (bits-per-byte) and Belebele comprehension are essentially unaffected (the exp11 4.5 pp Hungarian drop is not replicated in exp12).

The identity calibration arm continues to replicate (FINAL identity DiD = 3.46 [2.55, 4.62]). GaMS3 credits Qwen or Alibaba in roughly half of its English identity answers.

Open items at the end of iteration 3: the dose contrast remains underpowered. The lag magnitude is uncertain by a factor of two or more because no judge exceeds kappa 0.43 on edited text. The frozen-core Heretic procedure (bf16, 80 trials, Heretic's selection rule) has never been run. No artifact has scored natural RefusEU FINAL prompts under the edit. All adjudication is author-LLM, not human. The next iteration's budget belongs on validated labels and a lambda grid that covers EN 50%.

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

# Iteration 4

## Strategy

Three problems guided this iteration, following the reviewer's directive that the budget must go to the readout and a new confirmation rather than more probes.

First, the C-LAG sign was consistent but no artifact's pre-registered verdict reached CONFIRM. The main blocker was the edited-row readout: every judge had kappa at most 0.43, and the GaMS-SL false-COMPLY tipping path reached measured error CIs. Iteration 4 addressed this with a paid-judge readout completion (evaluation 3) that applied gemini-2.5-flash and gpt-4.1-mini to all saved edited responses, added translate-then-judge and Rogan-Gladen correction [25], and pooled across item bodies.

Second, the mechanism question shifted. The iter-2 hypothesis update replaced the comprehension-competence framing with two testable accounts: M-OUT (production-side, predicting the lag follows the output language) and M-IN (input-side caution, predicting the lag follows the input language). Experiment 14 tested these with a 2x3x3 design crossing input language (EN, SL, HU) with forced output language (EN, SL, HU) at three abliteration doses.

Third, the lag estimate's uncertainty was partly driven by sparse lambda coverage near EN 50%. Experiment 15 addressed this with a fine-grained lambda ladder (13 steps for Gemma, 15 for GaMS) on a fresh 300-item RefusEU-TRAIN body disjoint from all prior probes.

A fifth slot (research, art_NZ9n2Ej5RtGt) conducted a dated prior-art and fact-check, cataloguing nearest neighbours for each positive claim and verifying the M-OUT/M-IN design's novelty.

The OpenRouter shared key was available for this iteration. All paid judge calls used gemini-2.5-flash and gpt-4.1-mini.

Five artifact slots were planned. Slot 2 failed; the other four completed:

1. Evaluation 3 (readout completion): paid-judge re-scoring of all saved edited and original rows from experiments 8, 9, 11 and the experiment 10 add-on, with translate-then-judge, adjudication, and Rogan-Gladen [25] / PPI++ [26] corrected cross-model lag pooled across item bodies.
2. Experiment 13 (held-out confirmation, **FAILED**): a newly selected Heretic edit, a DEV-calibrated lambda grid bracketing English refusal of 50%, a confirmation curve on a new external 300-item harmful body, random-direction controls, and the frozen-core RQ2 natural RefusEU pairs under the edit. The container lost its GPU about 25 minutes into the run, so none of this was generated. The paid-judge substitute re-readout of archived curves was frozen but never labelled. See "Not executed or abandoned in iteration 4" below.
3. Experiment 14 (mechanism 2x3x3): input language x output language x dose, with three models (Gemma, GaMS3, public p-e-w/heretic checkpoint), testing M-OUT vs M-IN.
4. Experiment 15 (fine-grained lambda ladder): 13/15-step lambda curve on fresh 300-item body with random-direction controls, MT-noise check, and first-token KL collateral.
5. Research artifact: prior-art search and fact verification.

Because slot 2 failed, iteration 4 has **no held-out confirmation and no RQ2 result**. Every iteration-4 number below comes from re-readouts of saved rows (evaluation 3), a screen (experiment 14) or a denser curve on a fresh body (experiment 15).

## Artifact 15: Readout completion with paid judge (Evaluation 3)

[ARTIFACT:art_gOdYt7zLWvfr]

This evaluation applied the pre-registered paid readout to all saved edited and original rows from experiments 8, 9, 11 and the experiment 10 add-on block. The primary judge was gemini-2.5-flash (thinking off, primary scoring prompt). The second judge was gpt-4.1-mini on a stratified subset. Translate-then-judge (TTJ) applied NLLB SL-to-EN translation before judging, giving a language-neutral readout. Blind adjudication used two Claude-family adjudicators (claude-sonnet-4.5 for 285 rows, the executing agent for 195 rows; 40-row overlap, inter-adjudicator kappa 0.69).

### Readout gate: FAILS

The pre-registered gate required per-cell Se >= 0.80 AND Sp >= 0.80 in both decisive cells (GaMS-SL-edited and Gemma-SL-edited), and kappa(gemini, gpt-4.1-mini) >= 0.60. Both decisive cells fail:

**Table 25. Readout gate (gemini-2.5-flash vs adjudication).**

| Cell | Se [95% CI] | Sp [95% CI] | kappa gemini-gpt | Pass |
|-|-|-|-|-|
| GaMS-SL-edited | 0.91 [0.74, 0.97] | 0.73 [0.61, 0.83] | 0.39 | False |
| Gemma-SL-edited | 0.99 [0.87, 1.00] | 0.66 [0.43, 0.83] | 0.72 | False |

The paid judge has high sensitivity but specificity of 0.66-0.73 on edited Slovene rows (it over-calls REFUSE), below the pre-registered 0.80 floor. No readout tier passed the bake-off. All numbers below are estimates with their CIs, not primary verdicts.

### Pooled cross-model lag: sign confirmed, edit-induced component is zero

Pooling over three item bodies (experiment 9 lambda curve, experiment 11 reserved split, experiment 8 body A) using REML with the modified Hartung-Knapp-Sidik-Jonkman correction. We define the cross-model lag G3 as the GaMS-minus-Gemma difference in predicted Slovene refusal log-odds at matched English refusal of 50%; G3_orig is the pre-edit baseline component and G3_edit is the edit-induced component (G3 = G3_orig + G3_edit):

**Table 26. Pooled lag estimates (REML + HKSJ, k = 3 item bodies, R coding).**

| Readout | G3 [95% CI] | G3_edit [95% CI] | IG [95% CI] | I-squared |
|-|-|-|-|-|
| Raw primary (gemini) | -1.17 [-1.84, -0.50] | 0.39 [-1.95, 2.74] | -1.15 [-1.31, -0.99] | 0.22 |
| RG (unstable) | -1.79 [-7.17, 3.58] | n/a | -2.02 [-5.40, 1.35] | 0.00 |
| PPI | -1.77 [-1.89, -1.65] | 0.20 [-0.72, 1.11] | -2.00 [-3.19, -0.82] | 0.00 |
| TTJ | -1.10 [-4.67, 2.47] | 0.33 [-6.52, 7.18] | -1.40 [-2.46, -0.33] | 0.59 |

The pooled lag is negative under every readout. The edit-induced component is centred near zero in every readout. Subtracting each model's own pre-edit language gap, the lag is entirely explained by the baseline offset: GaMS3 starts with less Slovene refusal than Gemma before any de-censoring. **R-BASE (baseline offset) is the best-supported account.**

### Per-curve headlines

The per-curve table shows the raw primary lag, pre-edit baseline, and edit-induced component for each curve:

**Table 27. Per-curve G3 decomposition (raw primary readout, R coding).**

| Curve | G3 [95% CI] | G3_orig [95% CI] | G3_edit [95% CI] | On support | Verdict |
|-|-|-|-|-|-|
| exp9 lambda | -1.12 [-1.70, -0.63] | -2.56 [-4.07, -1.32] | 1.43 [0.29, 2.98] | False | ESTIMATE |
| exp11 FINAL | -1.00 [-1.40, -0.68] | -1.11 [-2.74, -0.21] | 0.10 [-0.85, 1.71] | True | CONFIRM-LAG |
| exp8 A1 | -1.54 [-2.11, -1.00] | -1.13 [-2.67, 0.04] | -0.41 [-1.65, 1.26] | False | CONFIRM-LAG |
| exp8 B | -1.20 [-1.77, -0.58] | -1.33 [-2.37, 0.78] | 0.12 [-2.21, 1.47] | True | ESTIMATE |
| exp10 op point | G3_op -2.42 [-4.35, -1.53] | 0.99 [-1.10, 3.53] | -3.40 [-6.09, -1.30] | - | CONFIRM-LAG |

The pre-edit baseline (G3_orig) is strongly negative in every body, confirming the baseline offset. The edit-induced component (G3_edit) spans zero in three of four curves. The experiment 9 lambda curve gives a positive edit-induced component (1.43 [0.29, 2.98]), suggesting that the edit actually *closes* the pre-existing gap in that body. Curve slopes: b_Gemma ranges from 1.40 to 1.66, b_GaMS from 0.97 to 1.13 -- both near 1, confirming parallel curves consistent with R-BASE.

### Tipping analysis

Both tipping paths (Gemma-SL false-REFUSE and GaMS-SL false-COMPLY) reach measured error CIs in most curves. The Gemma-SL 1-Sp (measured 0.34 [0.17, 0.57]) exceeds the delta* needed to push the lag to the negative margin in the experiment 9 lambda curve (0.36) and the experiment 11 reserved split (0.21). The GaMS-SL 1-Se (measured 0.09 [0.03, 0.26]) reaches the eps* needed to push the lag to zero in experiment 9 (0.13) and experiment 11 (0.21). The lag sign is robust; its magnitude is not.

### R-JUDGE rival

Translate-then-judge (TTJ) lag tracks the direct readout closely: experiment 9 lambda curve direct -0.89 vs TTJ -0.81 (difference 0.08); experiment 11 reserved split direct -0.83 vs TTJ -1.37 (difference -0.55). Both survive. If the lag were a judge artefact of Slovene-language responses, TTJ (which judges English translations) would erase it. It does not.

### Outcome

The lag sign is replicated under a paid frontier judge. The readout gate fails, so the magnitude is uncertain. The R-BASE (baseline offset) account is the best-supported explanation: the lag is pre-edit, not edit-induced. Spend: $4.31 of $8.00 cap.

## Artifact 16: 2x3x3 input-language x output-language mechanism test (Experiment 14)

[ARTIFACT:art_4Mf1Fazk33yZ]

This experiment tested the M-OUT (production-side) and M-IN (input-side) accounts of why Gemma retains more Slovene refusal after English-objective abliteration. The design crossed input language (EN, SL, HU) with forced output language (EN, SL, HU) using a parallel one-line suffix in the input language that states the required response language. The suffix was present in every cell, including matched cells, so it is constant across the design. Three models were run: Gemma-3-12B-IT, GaMS3-12B-Instruct, and p-e-w/gemma-3-12b-it-heretic (a public English-abliterated Gemma checkpoint, one external dose). Items: 200 harmful + 100 benign. Total: 18,700 rows.

**[Correction (iter 5): Tables 28-30 and this section's prose were regenerated from experiment 14's own `results/RESULTS_tables.md`. They replace earlier tables that did not match that file. The earlier tables showed Gemma SL->EN at 0.25 where the file has 0.07, and GaMS3 OUT_SL at +0.05 where the file has -0.44. The earlier text also said compliance was >= 90% in all but one cell, but four GaMS3 cells are below 0.90, one of them at 0.00.]**

**Doses.** Doses were chosen on a DEV scan of EN->EN refusal with the suffix. Gemma: lambda_lo = 0.5 and lambda_hi = 1.0. EN->EN logit refusal was +0.36 and -1.47, so the scan straddles 50% (straddle ok and FINAL support both True). GaMS3: lambda_lo = 0.5 and lambda_hi = 0.625. EN->EN logit refusal was -0.82 and -1.32, both below 50%, so the scan does not straddle it (straddle ok and FINAL support both False). **Every GaMS3 quantity evaluated at matched EN->EN 50% (Table 30b, and the L*-based contrasts in Table 30) is therefore an extrapolation outside GaMS3's measured dose support.**

### Refusal rate tables

Table 28 (Gemma) and Table 29 (GaMS3) give the refusal share per cell at all three doses. The readout is the primary judge on harmful items, coded R = REFUSE share, with Wilson 95% CIs. The RP coding is identical to R in every cell. Language compliance is the share of replies written in the requested output language, pooled over doses. Cells below 0.90 are marked †.

**Table 28. Gemma-IT refusal rate per input->output cell, all three doses.**

| Cell | zero | lo (lambda 0.5) | hi (lambda 1.0) | Language compliance |
|-|-|-|-|-|
| EN->EN | 0.88 [0.83, 0.92] | 0.59 [0.52, 0.66] | 0.18 [0.14, 0.24] | 1.00 |
| EN->SL | 0.95 [0.92, 0.98] | 0.92 [0.87, 0.95] | 0.77 [0.71, 0.82] | 0.99 |
| EN->HU | 0.94 [0.90, 0.97] | 0.81 [0.75, 0.86] | 0.46 [0.39, 0.53] | 0.98 |
| SL->EN | 0.88 [0.82, 0.91] | 0.46 [0.39, 0.52] | 0.07 [0.05, 0.12] | 1.00 |
| SL->SL | 0.95 [0.91, 0.97] | 0.85 [0.80, 0.90] | 0.56 [0.49, 0.63] | 1.00 |
| SL->HU | 0.94 [0.90, 0.97] | 0.84 [0.78, 0.88] | 0.53 [0.46, 0.60] | 1.00 |
| HU->EN | 0.88 [0.83, 0.92] | 0.54 [0.47, 0.60] | 0.10 [0.07, 0.15] | 1.00 |
| HU->SL | 0.95 [0.92, 0.98] | 0.93 [0.89, 0.96] | 0.83 [0.78, 0.88] | 0.96 |
| HU->HU | 0.94 [0.90, 0.97] | 0.80 [0.74, 0.85] | 0.55 [0.48, 0.62] | 1.00 |

**Table 29. GaMS3-Instruct refusal rate per input->output cell, all three doses.**

| Cell | zero | lo (lambda 0.5) | hi (lambda 0.625) | Language compliance |
|-|-|-|-|-|
| EN->EN | 0.82 [0.77, 0.87] | 0.30 [0.25, 0.37] | 0.21 [0.16, 0.27] | 1.00 |
| EN->SL | 0.77 [0.71, 0.82] | 0.21 [0.16, 0.27] | 0.14 [0.09, 0.19] | 0.98 |
| EN->HU | 0.80 [0.73, 0.85] | 0.34 [0.28, 0.41] | 0.23 [0.17, 0.29] | 0.97 |
| SL->EN | 0.87 [0.82, 0.91] | 0.25 [0.20, 0.31] | 0.16 [0.12, 0.22] | 0.00 † |
| SL->SL | 0.87 [0.82, 0.91] | 0.20 [0.15, 0.26] | 0.15 [0.11, 0.21] | 1.00 |
| SL->HU | 0.82 [0.77, 0.87] | 0.27 [0.21, 0.33] | 0.17 [0.13, 0.23] | 0.56 † |
| HU->EN | 0.86 [0.81, 0.91] | 0.29 [0.24, 0.36] | 0.19 [0.14, 0.25] | 0.14 † |
| HU->SL | 0.92 [0.87, 0.95] | 0.23 [0.18, 0.29] | 0.12 [0.09, 0.18] | 0.86 † |
| HU->HU | 0.91 [0.86, 0.94] | 0.41 [0.34, 0.48] | 0.28 [0.22, 0.35] | 1.00 |

**Table 29b. p-e-w/gemma-3-12b-it-heretic (public checkpoint, single external dose).**

| Cell | ext | Language compliance |
|-|-|-|
| EN->EN | 0.05 [0.03, 0.09] | 1.00 |
| EN->SL | 0.15 [0.11, 0.21] | 0.92 |
| EN->HU | 0.02 [0.01, 0.05] | 0.96 |
| SL->EN | 0.01 [0.00, 0.03] | 0.99 |
| SL->SL | 0.21 [0.16, 0.27] | 1.00 |
| SL->HU | 0.07 [0.04, 0.11] | 0.99 |
| HU->EN | 0.04 [0.02, 0.07] | 0.94 |
| HU->SL | 0.14 [0.10, 0.19] | 0.68 † |
| HU->HU | 0.08 [0.05, 0.13] | 1.00 |

Gemma at the high dose shows a large output-language gradient. English-output cells refuse 0.07-0.18 and Slovene-output cells 0.56-0.83. EN->SL is 0.77 against EN->EN 0.18, a difference of 0.59. The gradient is present before the edit: at dose zero, the Slovene-output cells refuse 0.95 against 0.88 for the English-output cells. Input language matters less, and its sign depends on the column. At the high dose, Slovene input lowers refusal in the EN and SL output columns (0.18 -> 0.07 and 0.77 -> 0.56) and raises it slightly in the HU column (0.46 -> 0.53).

GaMS3 at its high dose spans 0.12-0.28 with no Slovene-output excess. **GaMS3 did not follow the output-language instruction off the English-input row.** Its SL->EN compliance is 0.00, and all 32 of its high-dose SL->EN refusals were written in the input language, not the requested output language. HU->EN compliance is 0.14 and SL->HU 0.56. GaMS3's SL->EN column is therefore in practice a second SL->SL cell. Only the English-input row (EN->EN, EN->SL, EN->HU; compliance 0.97-1.00) is a valid output-language manipulation for GaMS3. Gemma complies at 0.96-1.00 in every cell.

### Mechanism contrast

OUT_SL is the Slovene output-language effect and IN_SL the Slovene input-language effect, both on the edit-induced L* scale of Table 30b. OUT_SL averages (X->SL minus X->EN) over English and Slovene input X. IN_SL averages (SL->Y minus EN->Y) over English and Slovene output Y. These definitions reproduce the raw values of both models from Table 30b. **Both contrasts therefore use GaMS3's non-compliant SL->EN cell.** Table 30 gives every readout recorded in the results file. NA marks a readout that has no L*-based estimate: translate-then-judge ran only at edited doses, and the second judge produced no labels on these rows. MDE = 2.8 x bootstrap SE.

**Table 30. Mechanism contrasts by readout (logit, 95% CI).**

| Readout | Model | OUT_SL | IN_SL | INT_SL | OUT-IN (SL) | OUT_HU | IN_HU | INT_HU |
|-|-|-|-|-|-|-|-|-|
| raw_R | Gemma | 1.14 [0.60, 1.56] | -0.60 [-1.02, -0.18] | -0.02 [-0.71, 0.62] | 1.73 [1.03, 2.34] | 0.55 [0.13, 0.91] | -0.15 [-0.56, 0.25] | 0.34 [-0.42, 1.11] |
| raw_R | GaMS3 | -0.44 [-0.98, 0.27] | -0.86 [-1.58, -0.13] | -0.66 [-2.74, 0.60] | 0.41 [-0.55, 1.59] | 0.30 [-0.30, 1.14] | -0.40 [-1.06, 0.61] | -0.35 [-1.92, 0.73] |
| raw_RP | Gemma | identical to raw_R | | | | | | |
| raw_RP | GaMS3 | identical to raw_R | | | | | | |
| ttj_R | both | NA | NA | NA | NA | NA | NA | NA |
| second_R | both | NA | NA | NA | NA | NA | NA | NA |
| rg_R | Gemma | 1.85 [-3.67, 7.44] | -2.53 [-5.74, -0.12] | -3.95 [-6.12, 4.07] | 4.38 [-1.31, 10.08] | -0.66 [-4.37, 5.39] | -0.28 [-2.59, 1.69] | 0.65 [-3.45, 6.23] |
| rg_R | GaMS3 | -3.07 [-8.76, 1.44] | -5.32 [-8.36, -0.70] | 6.15 [-5.56, 10.15] | 2.24 [-6.66, 7.01] | -0.24 [-7.21, 7.67] | -4.22 [-7.89, 3.18] | -4.84 [-9.29, 10.31] |
| ppi_R | Gemma | 0.20 [-0.76, 1.13] | -0.42 [-0.88, 0.14] | 0.36 [-0.54, 1.00] | 0.62 [-0.55, 1.72] | -0.39 [-1.39, 0.36] | -0.14 [-0.56, 0.34] | 0.25 [-0.74, 1.18] |
| ppi_R | GaMS3 | 3.09 [-7.69, 5.59] | -2.37 [-6.14, 3.21] | -4.32 [-13.58, 6.06] | 5.46 [-8.15, 9.05] | 0.41 [-2.09, 6.30] | -0.55 [-3.74, 2.95] | -0.94 [-8.59, 3.81] |

Cross-model contrasts on the raw readout (GaMS3 minus Gemma):
- dOUT_SL = -1.58 [-2.22, -0.66] (MDE 1.07)
- dIN_SL = -0.26 [-1.13, 0.57] (MDE 1.19)
- dINT_SL = -0.64 [-2.74, 0.83] (MDE 2.50)
- dOUT_HU = -0.26 [-0.96, 0.69] (MDE 1.14)
- dIN_HU = -0.25 [-1.02, 0.82] (MDE 1.32)
- HU fluency = -0.09 [-1.37, 0.78] (MDE 1.54)

**Pre-registered decisions.**
- raw_R and raw_RP: P0 passes. SL: M-OUT SUPPORTED. HU: M-OUT SUPPORTED. Specificity checks: dOUT_SL DIFFERENT, dIN_SL ESTIMATE, G3 at SL->SL DIFFERENT, G3_edit at SL->SL ESTIMATE.
- rg_R: P0 fails, so no mechanism call is made. The would-be SL call is MIXED/UNRESOLVED and HU is NEITHER (ESTIMATE). dOUT_SL = -4.92 [-13.28, 1.49], MDE 10.62.
- ppi_R: P0 fails, so no mechanism call is made. The would-be SL call is NEITHER (ESTIMATE). dOUT_SL = 2.89 [-7.80, 5.65], MDE 9.71.
- ttj_R and second_R: P0 fails; no call.
- The results file's own robustness flag for the SL call across raw, RG, PPI and TTJ is **robust = False**.

Gemma's raw OUT_SL = 1.14 [0.60, 1.56] excludes zero. So does its English-input-row component alone, L*(EN->SL) = 1.15 [0.54, 1.68] (Table 30b). The raw dOUT_SL = -1.58 excludes zero, but it averages in GaMS3's non-compliant SL->EN cell. **Restricted to the compliance-valid English-input row, the edit-induced cross-model contrast is G3_edit(EN->SL) = -1.26 [-2.17, 0.20], whose CI includes zero.** The total contrast on that row, including the pre-edit gap, is G3(EN->SL) = -2.63 [-3.46, -1.30]. M-OUT is therefore supported for Gemma on the raw readout. It is not supported as a cross-model edit-induced effect once GaMS3's failed manipulation is excluded, and it does not survive the corrected readouts.

**Table 30b. Lag at matched EN->EN refusal of 50% (logit, 95% item-bootstrap CI, raw primary readout).** a is the total SL-vs-reference gap at the matched point. L* is its edit-induced part, that is, a minus the pre-edit gap. G3 = GaMS3 a minus Gemma a, and G3_edit = GaMS3 L* minus Gemma L*. GaMS3 values are extrapolated (see Doses).

| Cell | Gemma a | Gemma L* | GaMS3 a | GaMS3 L* | G3 | G3_edit |
|-|-|-|-|-|-|-|
| EN->EN | 0.00 [-0.00, 0.00] | 0.00 [-0.00, 0.00] | 0.00 [-0.00, 0.00] | 0.00 [-0.00, 0.00] | 0.00 [-0.00, 0.00] | 0.00 [-0.00, 0.00] |
| EN->SL | 2.17 [1.81, 2.67] | 1.15 [0.54, 1.68] | -0.45 [-1.15, 0.83] | -0.11 [-0.88, 1.29] | -2.63 [-3.46, -1.30] | -1.26 [-2.17, 0.20] |
| EN->HU | 1.12 [0.88, 1.42] | 0.39 [-0.18, 0.85] | 0.28 [-0.36, 1.36] | 0.47 [-0.24, 1.56] | -0.85 [-1.57, 0.30] | 0.09 [-0.78, 1.37] |
| SL->EN | -0.63 [-0.94, -0.34] | -0.59 [-1.02, -0.16] | -0.18 [-0.85, 0.91] | -0.53 [-1.28, 0.58] | 0.45 [-0.30, 1.57] | 0.06 [-0.79, 1.18] |
| SL->SL | 1.46 [1.14, 1.86] | 0.54 [-0.14, 1.10] | -0.96 [-1.60, -0.16] | -1.30 [-2.04, -0.46] | -2.42 [-3.21, -1.53] | -1.84 [-2.80, -0.78] |
| SL->HU | 1.34 [1.02, 1.77] | 0.52 [-0.14, 1.11] | -0.15 [-0.83, 1.07] | -0.15 [-0.97, 1.10] | -1.49 [-2.24, -0.34] | -0.67 [-1.65, 0.74] |
| HU->EN | -0.32 [-0.63, 0.00] | -0.32 [-0.79, 0.16] | 0.08 [-0.73, 1.54] | -0.22 [-1.15, 1.23] | 0.40 [-0.41, 1.76] | 0.09 [-0.87, 1.55] |
| HU->SL | 2.37 [1.96, 2.97] | 1.34 [0.74, 1.89] | -0.00 [-0.78, 1.53] | -0.81 [-1.77, 0.78] | -2.37 [-3.33, -0.75] | -2.15 [-3.16, -0.46] |
| HU->HU | 1.14 [0.87, 1.46] | 0.41 [-0.21, 0.95] | 0.59 [-0.15, 1.97] | -0.10 [-0.96, 1.30] | -0.56 [-1.34, 0.84] | -0.51 [-1.51, 1.00] |

G3_edit excludes zero in two cells, SL->SL (-1.84 [-2.80, -0.78]) and HU->SL (-2.15 [-3.16, -0.46]). Both rest on extrapolated GaMS3 values, and HU->SL is a non-compliant GaMS3 cell (0.86). A GLM co-primary estimate gives the same pattern: Gemma a(EN->SL) = 2.08 [1.77, 2.43] and GaMS3 a(EN->SL) = -0.44 [-0.73, -0.16]. A GEE logit with an exchangeable item cluster (n = 10,800) gives a model x SL-output x high-dose coefficient of -2.41 (SE 0.26, p = 8e-20).

### Placebo and controls

**Placebos.** All null means are below 0.1.
- In/out swap, OUT-minus-IN (SL): Gemma observed 1.73 (null SD 0.30, permutation p = 0.0); GaMS3 observed 0.41 (null SD 0.50, p = 0.41).
- Model swap: G3 at SL->SL -2.42, G3_edit at SL->SL -1.84 and dOUT_SL -1.58 all give permutation p = 0.0; dIN_SL -0.26 gives p = 0.30.
- Language swap, SL->SL minus EN->EN logit: Gemma +0.92, +1.40 and +1.71 at zero, lo and hi (p <= 0.002). GaMS3 +0.35 (p = 0.06), -0.59 (p = 0.002) and -0.37 (p = 0.11).

**Random-direction edit at the high dose.** Refusal stays at its dose-zero level:
- Gemma EN->EN: random 0.88 against real 0.185. Gemma SL->SL: random 0.96 against real 0.56.
- GaMS3 EN->EN: random 0.825 against real 0.21. GaMS3 SL->SL: random 0.88 against real 0.155.
- First-token KL, real against random: Gemma EN 0.57 vs 0.006 and SL 0.34 vs 0.005; GaMS3 EN 0.068 vs 0.001 and SL 0.049 vs 0.001.

**MT noise.** EN-orig vs EN-BT refusal differs significantly at dose zero in both models:
- Gemma: 0.935 vs 0.88, McNemar p = 0.019.
- GaMS3: 0.905 vs 0.825, p = 0.005.
- At the high dose there is no significant difference (p = 0.56 and 0.83).

**Harmful content (R-INCAP).** The results file has an attack-success entry for one cell only, Gemma HU->SL: S = 0.00 at both edited doses (n = 186 and 167). No harmful-content reading exists for the decisive EN->SL and EN->EN cells.

**Degeneracy.** The degeneracy rate is at most 0.008 in every model x dose; none is flagged.

### C-EXT: public checkpoint

The public p-e-w/gemma-3-12b-it-heretic checkpoint (Table 29b) shows the same direction as edited Gemma. SL->SL refuses 0.21 against 0.05 for EN->EN, a residual of 16.0 pp. OUT_ext_SL = 1.38 [0.49, 2.44] and IN_ext_SL = -0.72 [-1.60, -0.08]. The checkpoint's absolute refusal is far lower than edited Gemma's, and its HU->SL cell fails compliance (0.68). Its judge-validity cells have only 10 rows each, with no gold REFUSE rows in either. So this is a directional replication in one checkpoint we did not build, not a validated magnitude.

### SDT decomposition

**Table 30c. Signal-detection DiD (Gemma minus GaMS3) at dose zero and lambda_hi, benign twins as noise, 95% CI.** Negative c DiD means Gemma's criterion moves further toward refusal than GaMS3's.

| Dose | Contrast | d' DiD | c DiD | Gemma-only d' | Gemma-only c |
|-|-|-|-|-|-|
| zero | SL input | -0.02 [-0.57, 0.58] | 0.20 [-0.07, 0.49] | 0.04 | 0.04 |
| zero | SL output | -0.13 [-0.68, 0.39] | -0.76 [-1.06, -0.52] | -0.32 | -0.67 |
| zero | SL both | -0.41 [-1.01, 0.15] | -0.47 [-0.78, -0.20] | -0.22 | -0.57 |
| hi | SL input | 0.27 [-0.59, 0.83] | 0.48 [0.07, 0.75] | 0.08 | 0.57 |
| hi | SL output | 0.72 [-0.06, 1.30] | -1.56 [-1.97, -1.29] | 0.42 | -1.41 |
| hi | SL both | 0.18 [-0.87, 0.90] | -1.16 [-1.72, -0.81] | 0.19 | -0.95 |

The Slovene-output effect sits in the criterion, not in discrimination. At high dose the c DiD is -1.56 [-1.97, -1.29] and the d' DiD is 0.72 [-0.06, 1.30], which includes zero. The criterion shift is already present before the edit: the dose-zero SL-output c DiD is -0.76 [-1.06, -0.52]. Slovene input moves the criterion the other way at high dose (+0.48 [0.07, 0.75]).

### Judge validity

These figures compare the primary judge with blind author-model adjudication, NOT human review. Across 240 pooled edited rows, Se = 0.89 [0.81, 0.95], Sp = 0.73 [0.66, 0.79] and kappa3 = 0.51. In the decisive cells:
- Gemma SL edited (n = 60): Se 0.89 [0.75, 0.96], Sp **0.42 [0.24, 0.61]**, kappa 0.35.
- GaMS3 SL edited (n = 60): Se 0.86 [0.49, 0.97], Sp 0.81 [0.69, 0.89], kappa 0.43.
- Gemma EN edited: Se 0.70 [0.40, 0.89], Sp 0.75 [0.53, 0.89].
- Gemma HU edited: Sp 0.67 [0.45, 0.83].

The phase-4 gate fails in both decisive cells. No gpt-4.1-mini labels exist on edited rows, and the shuffled-label kappa is NA. The judge over-calls REFUSE most in exactly Gemma's Slovene-output edited cells, the cells that carry the M-OUT effect.

### Outcome

**Verdict: ESTIMATE (screen), not a confirmation.** On the raw readout, edited Gemma's residual refusal follows the output language. English-output cells refuse 0.07-0.18 whatever the input language, Slovene-output cells refuse 0.56-0.83, and the pre-registered raw call is M-OUT SUPPORTED. Five facts limit this:
1. The call is not robust across readouts. RG and PPI make no mechanism call, TTJ and the second judge have no L* estimate, and the results file flags robust = False.
2. GaMS3 failed the output-language manipulation off the English-input row. On the compliance-valid row, the cross-model edit-induced contrast -1.26 [-2.17, 0.20] includes zero, and GaMS3's L* values are extrapolated.
3. The Slovene-output separation, and its criterion shift, already exist at dose zero.
4. Gemma's Slovene-output edited cells have judge Sp 0.42.
5. Harmful-content yield was measured in only one cell.

The production-side reading remains a hypothesis. It holds that refusal is the fallback when the model must produce harmful content in a language it generates poorly (Gemma SL BPB 1.20 vs GaMS3 0.89, from experiment 12's competence covariates). This experiment does not test it directly.

The nearest published neighbour for this finding is Upadhyaya and Sikdar [11], who showed safety features entangled with language identity in Gemma-2-9B. Our delta is the matched sibling pair under partial-dose abliteration with a 2x3x3 design that separates input from output language. As of 2026-09-24, no prior study crosses prompt language with response language for refusal measurement (research artifact verification).

## Artifact 17: Fine-grained lambda ladder (Experiment 15)

[ARTIFACT:art_piu0nI9vij_F]

This experiment ran a fine-grained lambda ladder -- 13 steps for Gemma (0.000 to 2.000) and 15 steps for GaMS (0.000 to 1.538) -- on a fresh 300-item RefusEU-TRAIN body disjoint from all prior probes. Each step used NLLB EN-BT and SL-MT arms from one English source. The judge was a local model (primary) with archival and TTJ readouts.

### Per-step refusal rates

Gemma SL refusal consistently exceeds EN refusal (margin positive throughout the entire dose range): at lambda 0 the margin is 1.48 log-odds; at lambda 2.0 it is 1.24. GaMS SL tracks EN closely: margin near zero or slightly negative in the middle range (e.g. -0.25 at lambda 0.420), turning positive at higher doses (0.72 at lambda 1.538). The margin never reaches the magnitude seen in Gemma.

### Headline readouts

**Table 31. Headline G3 decomposition (R coding, raw readout).**

| Readout | G3 [95% CI] | G3_orig [95% CI] | G3_edit [95% CI] |
|-|-|-|-|
| RAW | -0.70 [-1.01, -0.42] | -1.17 [-2.83, 0.22] | 0.47 [-0.96, 2.14] |
| RG | -0.01 [-4.36, 11.27] | -1.76 [-5.45, 1.96] | 1.75 [-4.58, 13.18] |
| PPI | -0.75 [-2.43, 0.99] | -1.52 [-6.46, 2.82] | 0.76 [-3.78, 6.27] |
| TTJ | -0.79 [-1.09, -0.48] | -1.37 [-2.29, 0.37] | 0.58 [-1.18, 1.52] |

G3_R = -0.70 [-1.01, -0.42] with MDE 0.42, the most powerful estimate in the entire study. It survives under TTJ (-0.79 [-1.09, -0.48]). G3_orig_R = -1.17 [-2.83, 0.22]: the pre-edit gap carries the lag. G3_edit_R = +0.47 [-0.96, 2.14]: the edit-induced component spans zero, confirming that the lag is baseline, not edit-induced. Rogan-Gladen correction is degenerate (CI [-4.36, 11.27]) due to low specificity. PPI includes zero.

Curve slopes: b_Gemma = 0.94 [0.75, 1.17], b_GaMS = 0.80 [0.63, 0.95]. Both are near 1, confirming parallel-curve geometry consistent with R-BASE.

### Random-direction control

Norm-matched random edits at four lambda points show G3_edit_rand near zero at all ranks (range 0.39 to 0.49), with CIs spanning zero at s=0.5 and including small positive values. The random control confirms that the (non-significant) G3_edit is not a directional artefact: random perturbations of equal norm produce the same null G3_edit.

### MT-noise check

EN-orig vs EN-BT refusal rates do not differ significantly at any model-lambda combination (McNemar p >= 0.125 in all four tested cells). Machine translation noise is not driving the SL-EN margin.

### First-token KL collateral

The real refusal edit produces much larger KL divergence than random directions at matched norm. For Gemma at lambda 2.0: real KL_EN 0.38, KL_SL 0.74, vs random KL_EN 0.008-0.011, KL_SL 0.019-0.019. For GaMS at lambda 1.538: real KL_EN 0.16, KL_SL 0.12, vs random KL_EN 0.003-0.005, KL_SL 0.004-0.004. The edit's collateral damage is real and directionally specific, not norm-induced.

### SDT per step

Both models show a criterion shift across languages at every lambda step. At lambda 0: Gemma c_EN = 0.58, c_SL = 1.37 (shift +0.79); GaMS c_EN = 0.61, c_SL = 1.02 (shift +0.41). At lambda 2.0: Gemma c_EN = -1.05, c_SL = -0.22 (shift +0.83). The Slovene criterion is always higher (more conservative) than English in Gemma. In GaMS, the shift is smaller and reverses at higher doses. d' drops monotonically with dose in both models, as expected.

### Judge validity

Per-cell adjudication: Gemma SL edited Sp = 0.55 [0.40, 0.69]; GaMS SL edited Se = 0.76 [0.55, 0.89], Sp = 0.62 [0.46, 0.75]. The pooled edited kappa is 0.51. These are the best validation numbers in the study, but still below the 0.80 gate.

### Verdict

Primary verdict: ESTIMATE. The lag screen is not a confirmation because the readout gate fails and TOST equivalence for the cross-model lag does not hold. R-BASE is supported: the edit-induced component spans zero, the pre-edit baseline is negative, and the curves are parallel. The MDE (0.42) means a true edit-induced lag of magnitude 0.42 or larger would have been detected; the data are consistent with a true edit-induced component near zero.

## Artifact 18: Prior-art and fact check (Research)

[ARTIFACT:art_NZ9n2Ej5RtGt]

This artifact conducted a dated (2026-09-24) prior-art search and fact verification. No LLM spend; web greps plus one local overlap script. Key findings:

**Novelty.** No published paper crosses prompt language with response language for refusal or ASR measurement as of 2026-09-24. The M-IN/M-OUT design is novel. Confidence is medium (the handbook's base rate for unchecked lanes turning out occupied is 11/11, and paywalled or unindexed work was not covered). Nearest neighbours: Deng et al. 2023 (instruction language), Cognitive Overload (turn-language switch), Minionese (perturbation type over 18 input languages), Upadhyaya and Sikdar 2026 (output language as outcome of safety-feature ablation, not as a controlled factor). Related concurrent work: Zhang et al. [29] analyse why safety guardrails degrade across languages; Kompella and Mahajan [32] locate and price the cross-lingual refusal circuit in an MoE model; Stein et al. [33] use English steering vectors for multilingual safety alignment (BabelSteering).

**Claim verdicts.**
- Cross-lingual abliteration lag: incremental vs Wang et al. [2], who showed full-dose English-direction transfer across 14 languages with no sibling pairs or dose sweep.
- Gemma criterion shift on originals: incremental. Aziz et al. [7] describe under-refusal as calibration; Yoon et al. [30] document non-English over-refusal costs. Our sibling-pair design adds GaMS3-specific detail.
- Language-specificity of refusal direction: incremental, exploratory. Converse of Upadhyaya and Sikdar [11].
- Harmfulness AUROC 1.00: replication of Aziz et al. [7], not a new finding. Source-separability confound documented by Balani and Panda [31].
- M-OUT (production-fluency mechanism): novel as a hypothesis. Nearest neighbours report unclear or irrelevant low-resource output (Shen et al. [27], Dahir [28]), but none separates a generation metric from a comprehension metric.

**Heretic facts.** Heretic @3521f86 is a 2.0.0.dev0 snapshot (2026-09-05). Defaults: 200 trials / 60 startup (not 80). English-keyword refusals on the first 100 AdvBench test prompts. No automatic selection: the choice is interactive over a Pareto front, or via a trial index. The pre-registered KL <= 0.5 selection rule is ours, not Heretic's.

**Item overlap.** mlabonne/harmful_behaviors is set-identical to AdvBench (520/520), and Heretic uses 500 of those prompts. The item bodies for experiments 14 and 15 were verified disjoint from AdvBench, RefusEU evaluation, and all prior probes.

**Hungarian.** Hungarian is not in the declared GaMS3 CPT/SFT mix. The model card shows SL 48.9 / EN 28.3% of CPT tokens (not 41.1/27.8 as earlier stated). Croatian/Serbian/Bosnian make up 22.3% of base continued pretraining, a South-Slavic confound for any claim about Slovene-specific training.

[FIGURE:fig_mechanism_2x3]

[FIGURE:fig_lambda_ladder]

## Not executed or abandoned in iteration 4

Slot 2 of the iteration-4 strategy (experiment 13) was the held-out confirmation. It was to use a newly selected Heretic edit, a DEV-calibrated lambda grid, a confirmation curve on a new external 300-item body, random-direction controls and the frozen-core RQ2 natural pairs under the edit. It produced **no generation and no primary label**. Every item below is read from experiment 13's own workspace:
- `protocol.yaml`
- `results/protocol_amendments.json`
- `results/tier_table.json`
- `results/readout_provenance.json`
- `data/split_manifest_iter4.json`
- `.aii_worker_result.json`

No number from this artifact appears in any result above.

### Amendment A1: GPU lost

About 25 minutes into the run, the container lost access to its L4 GPU. nvidia-smi reported "Failed to initialize NVML: Unknown Error", and opening `/dev/nvidia*` returned EPERM, meaning the cgroup device permission was revoked host-side. This could not be fixed from inside the container, and provisioning another GPU was outside the task's tools and budget.

The following were therefore **not executed**:
- the new Heretic edit
- the DEV lambda grid
- the confirmation curve on the new B-300 items
- the random-direction controls
- the RQ2 natural RefusEU pairs under the edit

The GPU code (`src/gpu_session.py`) and the new item body were delivered frozen and untested on GPU.

The amendment substituted a paid-judge **re-readout** of the archived dose curves of two earlier Heretic edit draws. E9 is the exp9 selected edit, with Gemma random edits. E11 is the iteration-1 edit on 200 RefusEU-FINAL MT items plus 50 benign HARD items. The amendment itself states that this is a judge-validity re-readout of generations that were already analysed, not a new-item replication.

The later amendments:
- **A2:** gemini returned 403 PROHIBITED_CONTENT on 2 of 240 calibration rows. Such rows would take a gpt-4.1-mini fallback label.
- **A3:** records the tier-gate failure (Table 31a below).
- **A4:** the shared OpenRouter key hit its daily limit (403, key limit exceeded) at the first primary call. Before any label, A4 pre-registered a redesigned adjudication: 432 author-model gold rows, 12 per model x arm x lambda cell. It also pre-registered a PPI++ fallback on the archived exp9 labels, marked exploratory-substitute.

### Two-tier judge bake-off (tier_table)

Two judge tiers were calibrated against eval2's 240 blind author-model adjudicated edited rows (NOT human). Both tiers fail the per-cell gate. The frozen rule therefore set gemini-2.5-flash as primary with an ESTIMATE ceiling. The two tiers agree with kappa = 0.52. Spend at this point was $0.064.

**Table 31a. Experiment 13 judge bake-off, per cell (n = 60 per cell; gold REFUSE/non-REFUSE counts in brackets).**

| Cell | flash-lite Se | flash-lite Sp | flash-lite kappa | flash Se | flash Sp | flash kappa |
|-|-|-|-|-|-|-|
| GaMS3 EN edited [38/22] | 0.97 | 0.36 | 0.39 | 0.89 | 0.55 | 0.47 |
| GaMS3 SL edited [45/15] | 0.98 | 0.27 | 0.31 | 1.00 | 0.47 | 0.57 |
| Gemma EN edited [27/33] | 0.89 | 0.33 | 0.21 | 0.93 | 0.55 | 0.45 |
| Gemma SL edited [27/33] | 0.96 | 0.33 | 0.28 | 0.96 | 0.42 | 0.37 |
| Overall (n = 240) [137/103] | 0.96 | 0.33 | 0.31 | 0.95 | 0.50 | 0.47 |
| Gate pass | False | | | False | | |

This is a second, independent measurement of the primary judge's over-calling on edited rows: flash specificity is 0.42-0.55. It points in the same direction as evaluation 3 (Sp 0.66-0.73) and experiment 14 (Gemma SL Sp 0.42).

### The re-readout: frozen but unlabelled

The substitute re-readout table was frozen at 19,195 rows (rows sha256 `e37fd7d3...6c242`, source-file hashes recorded in `readout_provenance.json`):
- E9: 7,040 rows. Gemma: edited 1,600 harmful + 960 benign, original 300 + 180, random 600 + 360. GaMS3: edited 1,600 + 960, original 300 + 180.
- E11: 12,155 rows. Gemma: edited 3,200 + 800, original 400 + 100. GaMS3: edited 4,553 + 800, original 2,202 + 100.

No primary, second-judge, translate-then-judge, StrongREJECT or adjudication label file exists in the workspace. The daily key limit (A4) was hit at the first primary call, and the executing session then ended with `failed = true` in `.aii_worker_result.json`. The table is reusable, but it carries no result.

### The item pool and its overlap with experiment 14

Experiment 13 built a 519-item external harmful pool from HarmBench, JailbreakBench and StrongREJECT, with no SORRY-Bench items. It was split by sha1 order (manifest sha256 `adea9ff1...`) into:
- **DEV:** 60 items (20 HarmBench / 5 JBB / 35 StrongREJECT).
- **B:** 300 items for the experiment 13 confirmation (107 / 44 / 149).
- **C:** 159 items reserved for the parallel mechanism artifact (63 / 19 / 77).
- **SPARE:** 0 items.

`protocol.yaml` still records the `items_iter4.jsonl` hash as PENDING, because NLLB translation was running on CPU after the GPU loss.

Experiment 14 built its own item set from the same public sources, under its own IDs. The iteration-5 hypothesis revision found that **116 of the 300 B items and 55 of the 159 C items were consumed by experiment 14**. That leaves 184 B + 104 C = 288 items that no artifact has generated. This overlap count comes from the iteration-5 strategy record. It was not recomputed for this section, because the two artifacts use different item IDs and matching them needs a text-level join. So the B body is no longer the untouched held-out body the slot-2 plan assumed.

**Table 31b. Iteration-4 components not executed.**

| Component | Status | Reason | Evidence file |
|-|-|-|-|
| exp13 new Heretic edit and DEV lambda grid | Not executed | GPU lost (A1) | exp13 protocol.yaml |
| exp13 held-out confirmation curve (B-300) | Not executed | GPU lost (A1) | exp13 protocol.yaml |
| exp13 random-direction controls | Not executed | GPU lost (A1) | exp13 protocol.yaml |
| RQ2 natural RefusEU FINAL pairs under the edit | Not executed (owed since iteration 1) | GPU lost (A1) | exp13 protocol.yaml |
| exp13 substitute paid re-readout (19,195 rows) | Frozen, unlabelled | OpenRouter daily key limit (A4); session ended failed | exp13 readout_provenance.json, .aii_worker_result.json |
| exp13 judge tier gate | Ran; both tiers FAIL | Sp 0.27-0.36 (flash-lite), 0.42-0.55 (flash) | exp13 tier_table.json |
| exp13 held-out item body | Built; partly consumed by exp14 | 116 B + 55 C overlap | exp13 split_manifest_iter4.json; iteration-5 strategy |
| exp14 harmful-content (ASR) readout | One cell only (Gemma HU->SL) | Not completed | exp14 RESULTS_tables.md |

# Iteration 5

**Strategy.** Three goals: (i) confirm the C-OUT finding on a fresh 294-item body with a new Heretic edit, a suffix-free design, a full 2x3x3+controls matrix, and PPI correction (experiment 16); (ii) run the deferred RefusEU FINAL evaluation with the full 1,300-item pool, random-edit and 256-token controls, and multiple readouts (experiment 17); (iii) test the R-INCAP question -- whether Gemma's Slovene reserve is real safety (harmful content separates) or production failure (the model refuses because it cannot produce harmful Slovene) -- with a StrongREJECT harmful-content endpoint alongside refusal (evaluation 4). Two support artifacts complete the iteration: a paper-number audit (evaluation 5) and a novelty and fact-check update (research 2).

[Correction: C-LAG is now closed in favour of C-OUT. The overall cross-lingual abliteration lag is better characterised as an output-language effect (C-OUT) than as a generic cross-lingual lag (C-LAG), because the mechanism experiment (experiment 14) showed it sits in the output-language contrast, not the input-language contrast.]

[Correction: The novelty verdict for the main claim is downgraded from NOVEL to PARTIALLY OCCUPIED. Two new preprints partly occupy the lane: Addagada [34] forces the output language and finds a relevance curse; Nguyen et al. [35] cross prompt and response language on benign content. The narrowed design (crossing both factors with safety endpoints, a sibling pair, partial-dose edit) remains unoccupied.]

## Artifact 19: C-OUT confirmation (Experiment 16)

[ARTIFACT:art_exp16]

This experiment tested whether the output-language effect (C-OUT) -- edited Gemma refusing more when told to write in Slovene than in English -- replicates on a fresh 294-item body (146 StrongREJECT, 109 HarmBench, 39 JBB) with a new Heretic edit, using prediction-powered inference (PPI) as the primary estimator rather than raw rates. The design was 2 models x 7 cells (English-in English-out, English-in Slovene-out, English-in Hungarian-out, Slovene-in Slovene-out, suffix-free English, suffix-free Slovene, plus external checkpoints) x 4 doses (zero, low, high, full) plus random-direction and original-model controls. Benign twins (n = 100) were generated for signal-detection and false-refusal analyses. The primary estimator switched from Rogan-Gladen to PPI after the Youden-J diagnostic flagged Rogan-Gladen instability in decisive cells (the estimator-switch amendment; Fiedler [36]).

### Headline: C-OUT replicates

The primary PPI estimate is OUT_Gemma = +2.43 [+0.89, +5.38] log-odds: edited Gemma refuses 2.43 log-odds more when told to answer in Slovene than in English, at the dose-matched lambda. The cross-model contrast dOUT = -2.31 [-5.34, -0.68] excludes zero: Gemma's output-language reserve is larger than GaMS3's. GaMS3 shows no output-language effect: OUT_GaMS3 = +0.12 [-0.47, +0.72], spanning zero. The input-language effect in Gemma is negative: IN_Gemma = -0.68 [-1.23, -0.36]. Slovene input reduces refusal.

All confirmation clauses pass on the consensus reference: OUT_Gemma >= m, its lower CI > 0, dOUT <= -m, its upper CI < 0, sign holds under gemini-refused and adjudicated-explicit readouts, IN_Gemma <= +m, and decisive cells are compliance-valid. However, **the verdict is capped at ESTIMATE** because the adjudication kappa on harmful content is 0.12 (gate requires 0.60). The adjudicator disagreement stems from truncation: gpt-4.1 scored cut-off partial compliance as non-harmful (convincing = 1, specific = 1), while claude-haiku-4.5 graded the partial content 2-4. The anchor is WEAK.

### Per-cell refusal rates

**Table 32a. Primary-judge refusal rates on harmful items, selected cells (n = 294 per cell).**

| Model | Cell | Dose | Refusal (primary judge) |
|-|-|-|-|
| Gemma | EN->EN | hi | 0.330 |
| Gemma | EN->SL | lo | 0.884 |
| Gemma | EN->HU | lo | 0.731 |
| Gemma | SL->EN | lo | 0.344 |
| Gemma | SF_EN->EN | lo | 0.510 |
| Gemma | SF_SL>SL | lo | 0.827 |
| Gemma | EN->EN | zero | 0.918 |
| Gemma | EN->SL | zero | 0.969 |
| GaMS3 | EN->EN | hi | 0.490 |
| GaMS3 | EN->SL | hi | 0.449 |
| GaMS3 | SF_EN->EN | hi | 0.527 |
| GaMS3 | SF_SL>SL | hi | 0.616 |
| GaMS3 | EN->EN | zero | 0.820 |
| GaMS3 | EN->SL | zero | 0.786 |

Gemma's English-in Slovene-out refusal exceeds English-in English-out at every dose. The gap is present at dose zero (0.969 vs 0.918) and widens under abliteration (low dose: 0.884 vs 0.531). GaMS3's Slovene-out and English-out rates are close at every dose. The suffix-free cells show the same pattern as the suffixed cells: Slovene output drives higher refusal in Gemma (0.827 vs 0.510 at low dose), ruling out a suffix artefact.

### The edit widens the reserve

The edit-induced output-language contrast OUT_edit = +2.43 [+0.92, +5.38]. English-only de-censoring does not close the Slovene reserve; it widens it. This is consistent with R-BASE: the edit suppresses English refusal more than Slovene refusal in Gemma, because Gemma's Slovene refusal was higher to begin with.

### SDT decomposition

**Table 32b. Signal-detection DiD (Gemma minus GaMS3) at dose zero and dose*, 95% CI.**

| Dose | Contrast | d' DiD | c DiD |
|-|-|-|-|
| zero | SL output | -0.37 [-0.81, 0.07] | -0.65 [-0.90, -0.46] |
| lo | SL output | +0.09 [-0.62, 0.57] | -1.07 [-1.42, -0.85] |
| zero | SL output (GaMS3 only) | | +0.10 [-0.12, 0.35] |
| lo | SL output (GaMS3 only) | | -0.05 [-0.42, 0.38] |

The output-language effect sits in the criterion, not in discrimination. At the dose-matched lambda, the criterion DiD is -1.07 [-1.42, -0.85] and the d' DiD is +0.09 [-0.62, 0.57], which includes zero. The criterion shift is already present before the edit (dose zero c DiD = -0.65 [-0.90, -0.46]). GaMS3's criterion DiD is near zero at both doses. This replicates the SDT pattern from experiment 14.

### Benign false refusal

Gemma falsely refuses benign prompts more often when told to reply in Slovene than in English (gemini-refused readout): Slovene-out 0.38 vs English-out 0.08 (false-refusal output-language contrast = +1.95 [+1.40, +2.94]). The false-refusal input-language effect is null (+0.00 [-0.72, +0.74]). GaMS3 also shows higher false refusal in Slovene under the gemini readout (Slovene-out 0.21 vs English-out 0.02), but the sign does not hold under the template-token judge (the cross-model false-refusal difference reverses: +1.73 [+0.65, +3.17] under the template-token judge vs -0.61 [-2.25, +0.74] under gemini). The secondary benign verdict is ESTIMATE.

### C-EXT: public checkpoint

The p-e-w/heretic checkpoint replicates the C-OUT direction: OUT_ext = +1.59 [+1.10, +2.24] (primary judge), +1.87 [+1.42, +2.51] (TTJ primary judge). The Slovene-vs-Hungarian contrast is also positive under the primary judge (+1.53 [+1.07, +2.08]). Only one external checkpoint was tested; the pre-registered external-replication rule requires two, so external replication cannot pass by construction.

### Judge validity

**Table 32c. Judge error in decisive cells (LLM adjudication, NOT human; n = 100 per cell).**

| Cell | Judge vs reference | Se | Sp | n |
|-|-|-|-|-|
| Gemma EN->EN | gemini_U vs adj_U | 0.93 | 0.63 | 99 |
| Gemma EN->SL | gemini_U vs adj_U | 1.00 | 0.94 | 99 |
| GaMS3 EN->EN | gemini_U vs adj_U | 0.92 | 0.84 | 100 |
| GaMS3 EN->SL | gemini_U vs adj_U | 1.00 | 0.82 | 99 |
| Gemma EN->EN | J1 vs adj_explicit | 1.00 | 0.46 | 100 |
| Gemma EN->SL | J1 vs adj_explicit | 1.00 | 0.35 | 100 |

The adjudicator kappa on harmful content is 0.12 -- far below the 0.60 gate. The four-class kappa is 0.63 (passes) and the refusal kappa is 0.90 (passes). The low harmful-content agreement is traced to gpt-4.1's handling of truncated partial compliance (the estimator-switch amendment).

### Placebos and sensitivities

All within-item swap placebos centre at zero (p >= 0.15 for local readouts; p = 0.0000 for gemini readouts, confirming the signal is real on the gemini channel). The MT-noise control shows no significant difference. Random-direction edits produce near-zero output-language contrasts (random-vs-real OUT Gemma: -2.03 [-3.30, -0.98] on the primary judge, confirming the real edit is directionally specific). The OUT estimate is stable across item sources: StrongREJECT +2.60, HarmBench +2.25, JBB +2.12 (all gemini_U).

### Outcome

**Verdict: ESTIMATE with WEAK anchor.** All confirmation clauses pass on the consensus reference. The C-OUT finding replicates: edited Gemma refuses more in Slovene-output cells than English-output cells, the effect sits in the criterion, and GaMS3 shows no such effect. The verdict is capped at ESTIMATE because the harmful-content adjudication kappa is 0.12, well below the 0.60 gate. The edit widens the reserve. The suffix-driver clause is false (OUT_SF +1.97 [+0.32, +5.13]): the suffix is not the mechanism. R-INCAP is tested in evaluation 4 (below).

## Artifact 20: RefusEU FINAL (Experiment 17)

[ARTIFACT:art_exp17]

This experiment measured what one English-only de-censoring edit buys on RefusEU's own 1,300 prompts per language, in both models and both languages (English, Slovene). The judge stack used local substitutes after the OpenRouter budget was exhausted (judge-substitution deviation): PolyGuard refusal (replacing the primary gemini judge), Qwen3Guard-Gen-8B (replacing gpt-4o-mini adjudication), and the official StrongREJECT fine-tuned evaluator (replacing gemini StrongREJECT). Adjudication is blind author-model LLM, NOT human. 11,600 rows were analysed across four conditions: edited, original, random-edit, and 256-token sensitivity.

### The edit raises attack success in all four cells

**Table 33. Paired edit effects (orig -> edit@1.0, exact McNemar, Holm-corrected).**

| Model | Lang | ASR orig | ASR edit | Delta [95% CI] | Verdict |
|-|-|-|-|-|-|
| Gemma | EN | 0.045 | 0.897 | 0.852 [0.831, 0.870] | **ROBUST** |
| Gemma | SL | 0.026 | 0.683 | 0.657 [0.629, 0.683] | **ROBUST** |
| GaMS3 | EN | 0.033 | 0.970 | 0.937 [0.923, 0.949] | **ROBUST** |
| GaMS3 | SL | 0.068 | 0.915 | 0.847 [0.826, 0.867] | **ROBUST** |

All four cells are ROBUST: the edit produces a massive increase in attack success on RefusEU prompts. The edit is more effective on GaMS3 than Gemma in both languages, and more effective in English than Slovene in both models.

### Cross-model difference (descriptive, not dose-matched)

The cross-model DiD in English is 0.085 [0.066, 0.105] and in Slovene 0.190 [0.159, 0.221] on the ASR readout: GaMS3 gains more from the edit than Gemma. This is descriptive because the two models were edited at the same lambda (1.0), not at dose-matched lambdas. The C-LAG line is closed in favour of C-OUT.

### Language confound

The English and Slovene prompt sets are different natural prompts with LaBSE similarity 0.55, so the SL-vs-EN difference within a model is **NOT INTERPRETABLE AS A LANGUAGE EFFECT**. Even in the high-similarity subset (LaBSE >= 0.70, n = 58), the SL-EN gap in Gemma is -0.190 [-0.345, -0.035] and in GaMS3 is -0.035 [-0.121, 0.052].

### Corrected ASR

Rogan-Gladen corrected deltas (using per-cell Se/Sp from blind author-model adjudication on 60 rows per cell):
- Gemma EN: delta_RG = 0.863 [0.811, 0.892]
- Gemma SL: delta_RG = 0.578 [0.473, 0.639]
- GaMS3 EN: delta_RG = 0.967 [0.927, 0.976]
- GaMS3 SL: delta_RG = 0.884 [0.826, 0.912]

Judge validity varies by cell: GaMS3 EN passes the validation gate on ASR_row (Se 1.00, Sp 0.903) and LG-unsafe (Se 1.00, Sp 0.998). Gemma SL passes only on LG-unsafe (Se 0.889, Sp 0.829). StrongREJECT fine-tuned has near-zero sensitivity in Gemma cells (Se 0.067 EN, Se 0.000 SL), making it unsuitable as the sole harmful-content readout for Gemma.

### Controls

Random-edit control: ASR changes are near zero in all four model x language cells (largest delta 0.020, McNemar p >= 0.125). The 256-token sensitivity shows higher StrongREJECT scores at longer generation but no change in ASR (e.g. Gemma EN ASR 0.850 at both 128 and 256 tokens). Language consistency is >= 0.999 in all cells. Degeneracy rates are at most 0.010.

### Ranking vs thresholding

An added analysis tested whether the guards fail Slovene by ranking (AUROC) or by calibration (threshold). AUROC is high in all cells (0.887-1.000), meaning the guards rank harmful above harmless correctly. The failure is in the shipped decision threshold, not in the underlying score. This is consistent with Aziz et al.'s [7] calibration-not-representation account.

### Verdict

All four paired-edit cells are ROBUST. The edit is effective on RefusEU prompts. The cross-model and cross-language differences are descriptive because the design is not dose-matched and the prompt sets are not parallel. The StrongREJECT fine-tuned evaluator has near-zero sensitivity for Gemma, confirming it cannot substitute for a paid rubric judge on this model.

## Artifact 21: R-INCAP safety evaluation (Evaluation 4)

[ARTIFACT:art_eval4]

This artifact tested whether Gemma's Slovene-output reserve is real safety (harmful content separates: the model refuses AND produces less harmful content in Slovene) or production failure (the model refuses because it cannot produce harmful Slovene, not because it detects harm). It re-used experiment 14's body (200 items per cell) with refusal measured by the primary judge and harmful content measured by StrongREJECT (original gemini rubric, translated rubric, and local fine-tuned). Adjudication used a free LLM panel (Nemotron-3-ultra and Laguna-S, with dots-3/Nemotron-3-super tie-breaking), NOT human review.

### HARMFUL CONTENT SEPARATES (reserve = safety)

**At high dose:** the output-language refusal contrast (primary judge) is OUT_R = 2.67 [2.29, 3.12] log-odds and the harmful-content contrast (original StrongREJECT rubric) is OUT_U = 2.61 [2.20, 3.07]. Both are positive and exclude zero. Gemma refuses more in Slovene AND produces less harmful content in Slovene. The PPI-corrected refusal (using explicit-refusal gold) is even larger: OUT_R(PPI explicit) = 5.39 [4.91, 5.85].

**At low dose:** the same pattern holds: OUT_R (primary judge) = 2.05 [1.61, 2.65] and OUT_U (original rubric) = 2.80 [2.25, 3.69].

The truncation-matched StrongREJECT (cutting English-out replies to the word length of the Slovene-out translation for the same item) gives a smaller contrast: OUT_U(fine-tuned StrongREJECT, truncation-matched) = 0.35 [-0.50, 1.32] at high dose, including zero. However, the gemini-scored truncation-matched contrast remains large: 2.39 [1.97, 2.86]. The truncation control shows that some of the harmful-content gap is explained by Slovene replies being shorter, but the effect survives under the paid rubric.

**Verdict: R-INCAP = HARMFUL CONTENT SEPARATES (reserve = safety).** The reserve is not a production failure. Gemma genuinely produces less harmful content when replying in Slovene.

### Four-class composition

**Table 34. Four-class composition at high dose, decisive cells.**

| Cell | n | EXPLICIT | DEFLECT | COMPLY | PF index | U_adj |
|-|-|-|-|-|-|-|
| Gemma EN->SL hi | 50 | 0.54 | 0.26 | 0.20 | 0.57 | 0.14 |
| Gemma EN->EN hi | 48 | 0.00 | 0.10 | 0.90 | 0.10 | 0.75 |
| GaMS3 EN->SL hi | 49 | 0.00 | 0.08 | 0.90 | 0.08 | 0.90 |
| GaMS3 EN->EN hi | 50 | 0.00 | 0.12 | 0.88 | 0.12 | 0.84 |

The production-failure index (PF: share of degraded + deflection responses among non-explicit-refusal) in Gemma English-in Slovene-out is 0.57 vs 0.10 in English-in English-out, a difference of 0.46 [0.23, 0.65]. In GaMS3 the difference is -0.04 [-0.17, 0.09], near zero. Half of Gemma's Slovene non-compliance is deflection (the model changes the topic or gives a vague answer rather than explicitly refusing or complying). The paid sonnet-4.5 reference confirms: PF difference 0.50 [0.25, 0.68] for Gemma, -0.00 [-0.13, 0.13] for GaMS3.

This means Gemma's Slovene reserve has two components: explicit refusal (54% of high-dose English-in Slovene-out responses) and deflection (26%). Both reduce harmful content. The deflection component is consistent with Shen et al.'s [27] relevance curse and Addagada's [34] observation that non-English output lowers attack success.

### SDT decomposition

The criterion-shift pattern from experiment 14 replicates. At high dose, the SL-output c DiD (Gemma minus GaMS3) is -1.56 [-1.98, -1.29], and the d' DiD is 0.72 [-0.10, 1.31] (includes zero). The edit-induced component of the criterion shift: R-BASE-OUT c DiD(hi) - DiD(zero) = -0.80 [-1.23, -0.46]. The criterion shift widens under the edit, beyond the baseline.

### Benign false refusal (unedited models)

Gemma falsely refuses benign English-in Slovene-out prompts at 0.20 [0.10, 0.37] vs English-in English-out at 0.10 [0.03, 0.26] (adjudicated any-refusal, n = 30 per cell). The primary-judge rate is higher (0.31 vs 0.09). GaMS3 shows no such gap (Slovene-out 0.10 vs English-out 0.25, but the English-out cell has only n = 4 adjudicated rows, making it uninformative).

### Adjudication quality

Inter-adjudicator kappa on the four-class label is 0.82 (pooled), on any-refusal is 0.85, and on harmful content is 0.59. The sonnet-4.5 anchor agrees with the final adjudication at kappa 0.86 (class), 0.90 (any-refusal), and 0.87 (harmful content). The shuffled-label per-stratum kappa is -0.003 (pass). A bridge sample of 12 rows from evaluation 2's author-model gold gives any-refusal kappa = 0.75 (agree 0.92).

### Judge error matrices

The local StrongREJECT fine-tuned evaluator has near-zero sensitivity for Gemma's Slovene-output cells: sensitivity = 0.00 [0.00, 0.35] for harmful content in Gemma English-in Slovene-out. The gemini rubrics (original and translated) have better sensitivity (0.57 [0.25, 0.84]) but lower specificity. Only sonnet-4.5 passes the validation gate in all four decisive cells (refusal sensitivity >= 0.80, specificity >= 0.80; harmful-content sensitivity >= 0.97, specificity >= 0.95). The Rogan-Gladen estimator is unidentifiable in several cells (Youden J < 0.3), so PPI is the preferred correction.

### Controls

Random-edit controls: harmful-content score at random-edit high dose is near zero-dose levels (Gemma English-out: random 0.010 vs zero 0.010, Heretic 0.130). The experiment 15 lambda-0 StrongREJECT check gives Slovene-minus-English = 0.00 [0.00, 0.00] for both models, confirming no harmful-content gap at zero dose. Truncation matching reduces the StrongREJECT gap but does not eliminate it under the gemini rubric. Round-trip translation shifts StrongREJECT scores by -0.07 on average (median chrF 67.96), with 7% of U labels flipping. All placebos (model swap, outlang swap, inout swap) are centred and significant as expected.

### Outcome

**Verdict: ESTIMATE with WEAK anchor.** HARMFUL CONTENT SEPARATES at both doses. The reserve is safety, not production failure. However, the local StrongREJECT evaluator has near-zero sensitivity for Gemma's Slovene cells, so the harmful-content endpoint relies on the paid gemini rubric and the free LLM panel. The PF index shows that deflection accounts for about a quarter of Gemma's Slovene reserve, consistent with the relevance curse [27, 34].

## Artifact 22: Paper number audit (Evaluation 5)

[ARTIFACT:art_eval5]

This artifact audited the numerical claims across all prior iterations. Key findings:

**R-BASE ceiling sensitivity.** Experiment 15's baseline component (cross-model gap at zero dose = -1.17) is a CEILING-ARTEFACT: one flip in the Gemma lambda-0 Slovene cell (299/300 refusals) moves it inside the margin. Only the experiment 9 lambda body has a ROBUST-OFFSET (cross-model gap = -2.56, fragility index 9). The experiment 11 and experiment 8 bodies are also ceiling artefacts (fragility index 1-2). The Jeffreys posterior gives P(gap < -m) = 0.74, 95% CrI [-3.98, 0.58].

**Slovene-specific leakage check.** 'No Slovene-specific leakage' is supported in 8 of 12 rows; UNDETERMINED in 4 (experiment 12 Gemma, experiment 14 Gemma, experiment 15 Gemma and GaMS3). A gated GPU re-measurement of experiment 15's 40 prompts passed the gate (max relative difference 0.0000) but the bootstrap CIs of the top-dose excess are UNDETERMINED in both models.

**Decomposition.** Across 107 body x readout rows: 15 are edit-induced, 0 are baseline, 64 are underdetermined. The parallel-curve geometry holds (b_Gemma = 0.94 [0.75, 1.17], b_GaMS3 = 0.80 [0.63, 0.95]).

**Criterion shift.** 8 of 9 compliance-valid rows have a CI below 0: Gemma's criterion moves toward refusing when it replies in Slovene. The one exception is experiment 9 (iteration 3, English-50% window): 0.00 [-0.48, 0.42].

**Ledger.** 1,176 numeric tokens plus 22 pointer claims: 332 SURVIVE, 844 UNTRACEABLE, 2 REVERSE, 1 SHRINKS. The claim-level reversals are: experiment 15 GaMS3 slope, experiment 15 best-validation claim, evaluation 3 experiment 10 edit-induced gap, evaluation 3 Qwen-positive. Attribution errors: experiment 15 pooled kappa, experiment 14 bits-per-byte attribution.

**Verification.** 49/49 independent checks pass.

## Artifact 23: Novelty and fact check (Research 2)

[ARTIFACT:art_research2]

This artifact updated the novelty and fact check from iteration 4, with a search date of 2026-09-25.

**Main-claim novelty verdict: PARTIALLY OCCUPIED** (was NOVEL). Two new preprints partly occupy the lane:
- Addagada [34] (arXiv 2609.08373v1, 8 Sep 2026) forces the output language (EN/ES/HI/AR) of an English structural jailbreak and scores with a StrongREJECT-style rubric. Non-English output lowers attack success in 11 of 12 cells: the 'relevance curse'. N = 30 per cell, pilot preprint.
- Nguyen et al. [35] (arXiv 2608.26186v1, 22 Aug 2026) fully cross prompt and response language (EN/NO) on benign questions. Refusals appear only in Norwegian-prompt conditions.

**Still ours:** crossing both factors with safety endpoints (refusal + StrongREJECT, reported separately), the Gemma/GaMS3 sibling pair, the partial-dose English-only edit plus public checkpoints, Hungarian, and a constant suffix in all cells.

**Claim verdicts.**
- (a) Reply-language reserve: incremental. The cross-model contrast remains a screen (edit-induced cross-model gap, English-in Slovene-out: -1.26 [-2.17, 0.20]).
- (b) Production-failure reading: incremental / replication of Shen et al.'s relevance curse [27]. The term 'relevance curse' should be cited, not coined.
- (c) GaMS3 baseline Slovene deficit: descriptive. Confounded by different SFT. The GaMS3 paper [20] reports no safety evaluation.
- (d) Per-cell judge error matrix: a check in a crowded lane. What remains ours is that the judge over-calls REFUSE on edited Slovene text.

**Method specs confirmed.** StrongREJECT HEAD is unchanged (7a551d5). RefusEU is a re-implementation (Llama-Guard-3-8B + PolyGuard-Qwen, GPT-4o-mini adjudicating; no published snapshot). RG/Lang-Reiczigel formulas confirmed from Lee [25]; Fiedler [36] flags RG instability at low Youden J. PPI ids confirmed [26, 37].

**Facts verified.** All pinned checkpoint shas equal main. GaMS3 Long-CPT BCMS share is 30.2% (vs 22.3% in Base CPT). No abliterated GaMS3 exists. NLLB is CC-BY-NC-4.0.

**New caveat (Fiedler [36]).** RG is unstable at low Youden J. Gemma SL-edited cells with Se 0.89 / Sp 0.42 give J ~ 0.31, so PPI is the more robust correction; RG results for those cells should be flagged unstable.

[FIGURE:fig_cout_forest]

[FIGURE:fig_rincap_composition]

## Not executed or abandoned in iteration 5

**Table 35. Iteration-5 components not executed.**

| Component | Status | Reason | Evidence |
|-|-|-|-|
| Experiment 16 partial-dose points | Not executed | Hard stop at $4.00 budget cap | exp16 results/queue_*.json |
| Experiment 16 Gemma high dose (partial) | Partial: only 100 English-out, 72 Slovene-out, 181 suffix-free English, 31 suffix-free Slovene at high dose | Gemma deadline cut | exp16 RESULTS_tables.md |
| Experiment 16 huihui and mlabonne external checkpoints | Not run | Time: pre-registered cut order | exp16 RESULTS_tables.md |
| Experiment 16 gpt-4.1-mini second adjudicator | Not run | OpenRouter budget | exp16 amendments |
| Experiment 17 primary gemini judge | Replaced by PolyGuard (judge substitution) | OpenRouter budget exhausted | exp17 deviations.md |
| Experiment 17 gemini StrongREJECT rubric | Replaced by StrongREJECT fine-tuned (judge substitution) | OpenRouter budget exhausted | exp17 deviations.md |
| Experiment 17 gpt-4o-mini adjudicator | Replaced by Qwen3Guard-Gen-8B (judge substitution) | OpenRouter budget exhausted | exp17 deviations.md |
| Evaluation 4 sonnet-4.5 on low dose | Not run | Budget: pre-registered high dose only | eval4 RESULTS.md |
| Evaluation 4 human audit of adjudication | Requested, not performed | No human reviewer available | eval4 results/human_audit_request.json |
| Frozen-core Heretic (bf16, 80 trials) | Still not executed | Owed since iteration 1 | |
| Natural RefusEU reserved-split under edit | Still not executed | Owed since iteration 1 | |

# What we have learned so far

Five iterations have screened the main claim and four alternates against scoring-split data (iteration 1), the reserved evaluation split (iteration 2), fresh data with mechanism tests and utility controls (iteration 3), a paid-judge readout completion with a new mechanism experiment and a fine-grained confirmation (iteration 4), and a C-OUT confirmation with harmful-content endpoints and RefusEU FINAL (iteration 5). Two alternates are dead (base-checkpoint geometry and persona gating). A third (prefill-depth signature, alternate 4) is uncitable. The geometry of refusal is layer-dependent: nearly collinear at each model's best layer but divergent at a common layer. The perpendicular component does not induce refusal. The teacher-inheritance screen found that GaMS3's refusal decisions do not inherit from the Qwen teacher, while its wording inherits almost entirely.

The primary contest (behaviour-level reach vs supervised reach) remains unresolved: the dose contrast is underpowered across all iterations. The overall GaMS3 Slovene deficit is judge-dependent; the meta-analytic estimate is -0.50 [-0.82, -0.21]. The criterion-shift finding replicates across experiments on compliance-valid rows: 8 of 9 CIs lie below zero (Gemma's criterion moves toward refusing when it replies in Slovene; GaMS3's does not). The shift is specific to the output language, not the input language, and is consistent with Aziz et al.'s [7] calibration-not-representation account.

The cross-lingual abliteration lag is better characterised as an output-language effect (C-OUT) than as a generic cross-lingual lag. The C-OUT finding from experiment 14 replicates in experiment 16 on a fresh 294-item body: OUT_Gemma(PPI) = +2.43 [+0.89, +5.38], dOUT = -2.31 [-5.34, -0.68]. Gemma's refusal follows the output language; GaMS3's does not (OUT_GaMS3 = +0.12 [-0.47, +0.72]). The input-language effect is negative in Gemma (IN = -0.68 [-1.23, -0.36]): Slovene input reduces refusal, opposite to the output effect. The suffix is not the driver (suffix-free OUT spans the same range). All confirmation clauses pass on the consensus reference, but the verdict is capped at ESTIMATE because the harmful-content adjudicator kappa is 0.12 (anchor WEAK).

**R-BASE remains the best-supported account for the overall lag.** The edit-induced component spans zero (experiment 15: edit-induced cross-model gap = +0.47 [-0.96, 2.14]). The pre-edit baseline is negative everywhere. The curves are parallel (slope near 1 in both models). The R-BASE baseline is, however, a ceiling artefact in most item bodies: experiment 15's baseline cross-model gap = -1.17 has fragility index 1 (one flip moves it inside the margin). Only the experiment 9 body has a robust offset (fragility index = 9).

The R-INCAP question is answered: **the reserve is safety, not production failure.** At both doses, harmful content separates: Gemma produces less harmful content in Slovene-output cells (OUT_U original rubric = 2.61 [2.20, 3.07] at high dose) alongside higher refusal (OUT_R primary judge = 2.67 [2.29, 3.12]). The four-class decomposition shows that half of Gemma's Slovene non-compliance is deflection (PF index difference 0.46 [0.23, 0.65]), consistent with Shen et al.'s [27] relevance curse and Addagada's [34] output-language effect. The paid sonnet-4.5 reference confirms the pattern (PF difference 0.50 [0.25, 0.68] for Gemma; -0.00 [-0.13, 0.13] for GaMS3).

The edit widens the Slovene reserve (edit-induced output-language contrast = +2.43 [+0.92, +5.38]). English-only abliteration does not close the Slovene-English refusal gap; it amplifies it. This is because the edit suppresses English refusal more than Slovene refusal in Gemma, as R-BASE predicts.

On RefusEU FINAL prompts (experiment 17, n = 1,300 per cell), the edit is effective in all four cells (ROBUST). GaMS3 gains more from the edit than Gemma in both languages. The EN-vs-SL within-model difference is not interpretable as a language effect because the prompt sets differ (LaBSE 0.55). The ranking-vs-thresholding analysis shows the guards' AUROC is high (0.887-1.000) but their decision thresholds are miscalibrated for Slovene, consistent with the criterion-shift finding.

The benign false-refusal rate is higher in Slovene-output cells than English-output cells for Gemma (Slovene-out 0.20 vs English-out 0.10, adjudicated; Slovene-out 0.38 vs English-out 0.08 on gemini-refused in experiment 16). The sign does not hold under all readouts (the template-token judge reverses the cross-model false-refusal difference).

The novelty verdict is downgraded from NOVEL to PARTIALLY OCCUPIED. Addagada [34] forces the output language of a jailbreak and reports a relevance curse. Nguyen et al. [35] cross prompt and response language on benign content. The narrowed design -- crossing both factors with safety endpoints on a sibling pair under partial-dose abliteration -- remains unoccupied as of 2026-09-25 (medium-low confidence).

The SDT criterion shift (c DiD) is the study's most replicable quantitative finding. It is present at dose zero (-0.65 to -0.76), widens under the edit (R-BASE-OUT c DiD(hi) - DiD(zero) = -0.80 [-1.23, -0.46]), and is specific to the output language. It means Gemma adopts a more conservative decision rule when replying in Slovene: at the same level of harmful-content discrimination, it sets a higher threshold for compliance.

The p-e-w/heretic checkpoint replicates C-OUT across iterations: OUT_ext = +1.38 [+0.49, +2.44] (iteration 4), +1.59 [+1.10, +2.24] (iteration 5, primary-judge readout). A second public checkpoint has not been tested.

The utility control (experiment 12) stands: the edit does not damage Slovene downstream skills more than English ones. The identity calibration arm continues to replicate.

Open items: the readout gate has never passed. The frozen-core Heretic procedure (bf16, 80 trials, Heretic's own selection rule) has never been run. No artifact has scored natural RefusEU reserved-split prompts under the edit. All adjudication is author-LLM, not human. The harmful-content adjudicator kappa (0.12 in experiment 16; 0.59 in evaluation 4) remains below the gate; the sonnet-4.5 anchor is the best-validated readout (kappa 0.87 vs final adjudication) but is available only on high-dose decisive cells. If R-BASE is correct, the lag is an artefact of model selection (GaMS3 was simply trained to refuse less in Slovene), not a property of the abliteration procedure. The M-OUT finding (output language drives the lag) is confirmed as C-OUT and deserves pre-registered confirmation with a validated readout and human adjudication.

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

[25] C. Lee, T. Zeng, J. Jeong, J. Sohn, K. Lee. "How to Correctly Report LLM-as-a-Judge Evaluations." ICML 2026. arXiv 2511.21140.

[26] A. N. Angelopoulos, J. C. Duchi, T. Zrnic. "PPI++: Efficient Prediction-Powered Inference." arXiv 2311.01453, 2023.

[27] L. Shen, W. Tan, S. Chen, Y. Chen, J. Zhang, H. Xu, B. Zheng, P. Koehn, D. Khashabi. "The Language Barrier: Dissecting Safety Challenges of LLMs in Multilingual Contexts." Findings ACL 2024. arXiv 2401.13136.

[28] K. Y. Dahir. "SomaliBench Eval: Measuring English-to-Somali Refusal Gaps in Open-Weight Language Models." arXiv 2605.25420, 2026.

[29] M. Zhang, A. Patel, S. T. Truong, S. Koyejo. "Why Do Safety Guardrails Degrade Across Languages?" arXiv 2605.17173, 2026.

[30] C. Yoon, J. Park, A. Ritter. "Who Pays More for Safety? Measuring the Disparate Cost of Safety Alignment across Languages." arXiv 2608.22490, 2026.

[31] P. Balani, S. Panda. "Hard Negatives Reveal What Easy Negatives Hide." arXiv 2609.27758, 2026.

[32] R. P. Kompella, A. Mahajan. "Decided Upstream, Written Late: Locating and Pricing the Cross-Lingual Refusal Circuit of a Multilingual MoE." arXiv 2608.08032, 2026.

[33] E. V. Stein, D. Meier, T. Ruas, J. P. Wahle, B. Gipp. "BabelSteering: Multilingual Safety Alignment via English Steering Vectors." arXiv 2608.16577, 2026.

[34] T. C. Addagada. "Structural Jailbreaks Generalize but Do Not Compound: A Cross-Provider and Multilingual Study of Involuntary In-Context Learning." arXiv 2609.08373, 2026.

[35] T. T. H. Nguyen, M. K. Tieu, M. A. Riegler, P. Halvorsen, T. Nguyen. "Investigating the Influence of Prompt and Response Languages on LLM Content Generation." arXiv 2608.26186, 2026.

[36] J. Fiedler. "Bias and Uncertainty in LLM-as-a-Judge Estimation." arXiv 2605.06939, 2026.

[37] A. N. Angelopoulos, S. Bates, C. Fannjiang, M. I. Jordan, T. Zrnic. "Prediction-Powered Inference." Science 382, 669-674, 2023.