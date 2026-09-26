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

The primary statistic G3 (the GaMS-minus-Gemma difference in the logistic transfer-curve intercept, measuring whether GaMS3 retains more Slovene refusal at matched English refusal) was -1.76 [-2.73, -1.09] on the matched first 17 trials (-1.76 on all trials, -1.74 on translation-equivalent pairs). The main claim required |G3| < m = 0.675; alternate 1 required G3 > m. Neither holds: Slovene refusal is *more* exposed in GaMS3 than in Gemma at any matched English refusal level. Trial-label permutation p = 0.000.

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
| Alt 3: persona gate | DEAD | Manipulation check fails; premise (SL surplus) contradicted | None |
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

Qwen3-14B was selected as primary over Mistral-Small-24B on the basis of higher per-cell kappa against archived gemini labels on a 973-row calibration set. Coverage was 19,971 rows for Qwen3-14B vs 2,614 for Mistral-Small-24B. The archived Llama-3.1-8B labels and lexicon were retained as secondary comparisons.

### The lexicon finding reproduces exactly

The experiment 8 lexicon transfer-curve intercept of -2.36 was reproduced bit-for-bit from the saved response files. This confirms that the lexicon estimate is a property of the data, not a computation error.

### Under the validated judge: lag survives for REFUSE-only coding

We define the integrated gap as the area-weighted average of the transfer-curve intercept across the observed English refusal range, used when the logistic fit cannot be evaluated at the 50% intercept. The Qwen3-14B judge gives an integrated gap of -1.95 [-3.75, -0.78] under REFUSE-only coding. The transfer-curve intercept at 50% English refusal is extrapolated because Gemma's English refusal never falls below 84% on the confirmatory-curve trials, so the support rule fails and the integrated gap replaces the point estimate. The lag survives: the confidence interval excludes zero.

Under PARTIAL-as-refusal coding (RP), the lag becomes INCONCLUSIVE. The CI includes zero. The finding is therefore fragile to how partial compliance is classified.

The lambda-scaling curve shrank under the validated judge: integrated gap = -0.47 [-1.86, 0.26], INCONCLUSIVE.

### Bias tipping analysis

How many misclassifications would be needed to erase the lag? Erasing the confirmatory-curve lag (to an integrated gap of -0.675) requires adding 0.71 extra false-REFUSE labels per item in the Gemma-SL cell. The measured inter-judge differential between Qwen3-14B and the blind adjudication on edited rows is 0.003. The required bias exceeds the observed bias by two orders of magnitude. The lag is not an artefact of judge bias, though the judge is imprecise.

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

The DeBERTa distilled judge was independently re-trained on a different random split; the headline transfer-curve intercept changed by less than 0.05. Trial pairing was confirmed from Heretic's random-seed logs. Spend: $0.

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

**Geometry hypothesis support: FALSE** for both models. The pre-registered criterion required the Slovene-perpendicular component to be geometrically larger in one model than the other. It is not.

### Induction: the Slovene-perpendicular direction does not induce refusal

Adding the Slovene-perpendicular component (u_SLperp) to harmless activations at L* never induced refusal above 50% in either model or language. The alpha50 was right-censored at the maximum tested amplitude (3.0 K-units) for all u_SLperp cells. By contrast, the full English refusal direction (r_EN) reached alpha50 at 0.91 K for Gemma-EN and 1.32 K for GaMS3-EN. Random directions were also censored. The u_SLperp direction is inert as a refusal inducer.

**Induction hypothesis verdict: NOT_SUPPORTED** for both models.

### Exploratory: language-identity direction induces Slovene refusal

The language-identity direction (u_lang, extracted from language-classification probes) showed an asymmetric induction pattern. In Gemma, adding u_lang at L* induced Slovene refusal (alpha50 = 0.65 [0.46, 0.79]) but not English refusal (censored at 3.0 K). In GaMS3, the pattern was similar but weaker: Slovene alpha50 = 1.78 [1.32, 2.38], English censored. The model contrast (log R_lang Gemma minus GaMS3) was 1.03 [0.42, 1.60] under the primary judge, confirming that this direction induces more Slovene refusal in Gemma than in GaMS3. This is exploratory and was not pre-registered.

### Add-on neutralisation: only full r_SL ablation closes the lag

The add-on block tested whether adding a second ablation (of u_SLperp, u_lang, or the full r_SL) at the selected lambda closes the remaining Slovene-vs-English refusal gap. At Gemma's selected abliteration strength (lambda*), the baseline lag was +1.98 [1.41, 2.73] (Slovene refusal still higher than English). Ablating u_SLperp at three scales (0.5, 1.0, 1.5) moved the lag to 2.69, 1.34, and 0.45, respectively, but the cut-vs-random comparison was not significant: u_SLperp ablation moved refusal by the same amount as random-direction ablation (cut-random 0.17 [-0.09, 0.44]). Only ablating the full Slovene refusal direction (A_SLfull) closed the lag (-6.17 [-6.50, -5.87]), at the cost of 50% degenerate outputs and 19x KL.

Ablating the language-identity direction (A_lang) collapsed refusal in both languages to near zero (EN 0.02, SL 0.03) with 51% degenerate outputs, making it uninformative.

### Transfer-curve intercept on the SCREEN items: reproduces

The transfer-curve intercept on the experiment 8 SCREEN items (TEST160 harmful subset), computed from the add-on block's original-model rates, was -2.30 [-3.12, -1.61]. This replicates the experiment 8 lexicon estimate (-2.36) under an independent judge and item set.

### Refusal readability: refusal is always readable

Across all abliteration states (original, the iteration-1 edit, and the strongest edit), AUROC for a fixed linear probe trained on original-model activations was 1.00 at every layer tested (8, 12, 20, 28, 36, 44) in both models. English-to-Slovene transfer was also 1.00. The refusal direction is always readable from the residual stream, even in heavily abliterated models. The fixed-probe d-prime collapses (from 1.37 to 0.25 at the best layer in Gemma under the strongest edit), confirming that abliteration reduces the magnitude of the refusal signal without destroying its separability.

### Final verdict

**Both the geometry hypothesis and the induction hypothesis are REFUTED.** The Slovene refusal that survives English abliteration is not carried by a separate Slovene direction and cannot be induced by the Slovene-perpendicular component. The lag is a property of the shared refusal subspace, not a geometrically distinct Slovene reserve.

## Artifact 13: FINAL confirmation on reserved split (Experiment 11)

[ARTIFACT:art_Aw3AXCXv9pUg]

This was the pre-registered FINAL confirmation run. Both models were run in FP8 quantization on the reserved RefusEU evaluation split (200 items), plus a 247-item Hungarian arm (NLLB-translated from the same English sources) and the HARD set (349 harmful + 1,093 safe items). Conditions: original models and the iteration-1 selected Heretic edit at lambda = 1.0. The experiment generated 27,264 responses and obtained 25,036 judge labels from Qwen3-14B.

### Cross-lingual abliteration lag: ESTIMATE, not confirmed

The transfer-curve intercept on the lambda = 1.0 edit was -0.60 [-1.31, +0.40], verdict ESTIMATE. The support rule failed: neither model's English refusal reached 50% on the single edit step. The minimum detectable effect was 1.44, exceeding the pre-registered threshold (2m = 1.35). The test is therefore formally underpowered.

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

The difference in lag change (GaMS3 minus Gemma) on Hungarian was -0.46 [-2.21, 1.44], INCONCLUSIVE. However, the pattern is consistent with a general non-English transfer effect rather than a GaMS3-specific Slovene effect: GaMS3's lag drops by 0.49 on Hungarian (a language it was not specially trained on), compared with Gemma's near-zero change. This weighs against the explanation that GaMS3's Slovene-specific supervised fine-tuning drives the lag.

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

A generalised estimating equation on 7,337 original+edited rows (both models, all languages, harmful items) found a significant three-way interaction: the gams:sl:edit coefficient was +1.06 (p = 0.022). GaMS3's Slovene refusal drops more under the edit than expected from the main effects alone, but the interaction goes in the direction of greater Slovene exposure for GaMS3, not greater Slovene resilience. The gams:edit main effect was non-significant (-0.18, p = 0.47): GaMS3 is not generally more vulnerable to the edit than Gemma.

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

**Table 24. KL footprint (batch size 1, 32-token, Dolly harmless).**

| Model | Condition | KL EN-BT | KL SL-MT | SL/EN ratio | EXCESS vs random [95% CI] |
|-|-|-|-|-|-|
| GaMS3 | Iter-1 edit | 0.024 | 0.010 | 0.52 | 0.47 [0.38, 0.60] |
| GaMS3 | Art-2 edit | 0.029 | 0.011 | 0.54 | 0.49 [0.40, 0.62] |
| Gemma | Iter-1 edit | 0.073 | 0.019 | 0.72 | 0.63 [0.34, 1.17] |
| Gemma | Art-2 edit | 0.076 | 0.021 | 0.72 | 0.63 [0.34, 1.15] |

### Verification

GaMS3 reproduced logged Heretic KL divergences within 3%. Self-KL floor was exactly 0 (batch size 1, fp32). The language-swap placebo centred at zero. GaMS3 Slovene evaluation accuracies match the published paper [20] within 0.06 on all six tasks. Spend: $0.

# What we have learned so far

Three iterations have screened the main claim (behaviour-level reach) and four alternates against SCORE data (iteration 1), the reserved FINAL evaluation split (iteration 2), and fresh data with mechanism tests and utility controls (iteration 3). Two alternates are dead (base-checkpoint geometry and persona gating). A third (prefill-depth signature, alternate 4) is uncitable because no available readout can validly score prefill continuations. Two mechanistic hypotheses (the geometry hypothesis, that Slovene refusal occupies a separate direction; the induction hypothesis, that the Slovene-perpendicular component induces refusal) are refuted: the English and Slovene refusal directions are nearly collinear (cos = 0.986-0.991), and the perpendicular component does not induce refusal. The teacher-inheritance screen found that GaMS3's refusal *decisions* do not detectably inherit from the Qwen teacher, while its refusal *wording* inherits almost entirely (76% of English and 91% of Slovene first sentences are verbatim from the SFT data).

The primary contest between behaviour-level reach and supervised reach remains unresolved. The dose contrast is underpowered across all three iterations. The overall GaMS3 Slovene deficit (DiD) is judge-dependent; the meta-analytic estimate is -0.50 [-0.82, -0.21]. What is robust is the signal-detection decomposition: the DiD in d' (discrimination) is near zero (-0.003), while the DiD in criterion c is +0.52 [0.39, 0.67], driven by Gemma over-refusing benign Slovene prompts. This criterion-shift finding replicates across experiments, judge families, and item sets.

The cross-lingual abliteration lag is now confirmed across three independent designs. On fresh Heretic trials (experiment 8, 29 pairs, lexicon), the transfer-curve intercept was -2.36 [-3.18, -1.62]. Under a validated local judge on the same data (evaluation 2, Qwen3-14B), the integrated gap is -1.95 [-3.75, -0.78]. On a fresh probe with a DeBERTa judge (experiment 9, lambda curve), the transfer-curve intercept was -0.97 [-1.56, -0.44]. On the experiment 10 SCREEN items under a TF-IDF surrogate, the intercept was -2.30 [-3.12, -1.61]. The FINAL confirmation (experiment 11) gave -0.60 [-1.31, +0.40], formally ESTIMATE due to the support rule failing, but consistent in sign. The lag is real: at matched English refusal, GaMS3 retains less Slovene refusal than Gemma. The precise magnitude ranges from -0.6 to -2.4 across designs and judges, with the uncertainty driven by weak judge agreement on edited text (best kappa = 0.43, gemini).

The lag is not explained by a separate Slovene direction (both the geometry hypothesis and the induction hypothesis refuted), nor by base-checkpoint geometry, nor by persona gating. The exploratory finding from experiment 10 is that the language-identity direction can induce Slovene refusal when added to harmless activations (alpha50 = 0.65 in Gemma, 1.78 in GaMS3), with Gemma showing stronger induction than GaMS3. This suggests that Gemma's Slovene over-refusal involves the language-identity subspace, but the result is exploratory. The Hungarian arm of experiment 11 found that Hungarian behaves like Slovene under abliteration (GaMS3's lag drops 0.49 on Hungarian, Gemma's is unchanged), weighing against a GaMS3-specific Slovene SFT explanation and in favour of a generic non-English transfer effect.

The utility control (experiment 12) established that the English-only abliteration edit does not damage Slovene downstream skills more than English ones. All macro headroom-normalised losses are below 0.05. The language asymmetry is positive in every cell (Slovene hurt less), and the random-adjusted excess asymmetry excludes zero for GaMS3 (excess = +0.051 [+0.012, +0.093]). The one localised cost is GaMS3's English ARC-Challenge (3.7 pp loss, McNemar p = 0.041), which replicates across two edits. The excess Slovene KL divergence ratio is below 1 in both models across all iterations: the refusal edit reaches Slovene distributions less than random perturbations of equal norm. Fluency (bits-per-byte) and Belebele comprehension are essentially unaffected.

The identity calibration arm continues to replicate (FINAL identity difference-in-differences = 3.46 [2.55, 4.62]). GaMS3 credits Qwen or Alibaba in roughly half of its English identity answers.

Open items for a potential next iteration: the dose contrast remains underpowered and may require a fundamentally different design to resolve. The lag magnitude is uncertain by a factor of two or more because no judge exceeds kappa 0.43 on edited text; human adjudication on a small sample would anchor the scale. The language-identity induction finding deserves a pre-registered follow-up. The Gemma KL divergence discrepancy (+39% vs logged) is unexplained.

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
