# Prior-art and fact check for the Slovene refusal study

## Summary

Dated (2026-09-24) prior-art and fact-verification artifact for the iteration-4 GaMS3-vs-Gemma-3 Slovene refusal study. No LLM spend; web greps plus one local overlap script.

KEY OUTPUTS FOR DOWNSTREAM
1. Novelty. No paper crosses prompt language x response language for refusal/ASR, so the M-IN/M-OUT DESIGN is novel. Confidence is medium. Nearest neighbours: Deng 2023 (instruction language), Cognitive Overload (turn-language switch), MINIONESE (perturbation type), Upadhyaya & Sikdar 2026 (output language as outcome).
2. Claim verdicts:
   - C-LAG: incremental (vs Wang 2025), still a LEAD because the exp11 CI includes 0.
   - Gemma benign-Slovene criterion shift: incremental. It is the opposite direction to Aziz 2026, and non-English over-refusal cost is already in Yoon 2026.
   - u_lang: incremental and exploratory (converse of Upadhyaya).
   - RQ4 AUROC 1.00: REPLICATION / source-separability. Balani & Panda 2609.27758 and Schwarz 2607.13075 show near-ceiling AUROC with unrelated negatives collapsing on matched twins, so re-run on same-source twins (exp9 twins, XSTest, JBB benign).
   - M-OUT production fluency: novel as a hypothesis, untested.
3. Heretic @3521f8648a0dccf6e12a92666862632235fac7e6:
   - It is a 2.0.0.dev0 snapshot from 2026-09-05. Defaults are n_trials 200 / n_startup 60 (not 80). Objectives are English-keyword refusals on AdvBench-derived harmful_behaviors test[:100] and FIRST-TOKEN KL on harmless_alpaca test[:100].
   - There is NO automatic selection: the choice is interactive over a Pareto front sorted by (refusals, KL), or via trial_index. A pre-registered rule is given (KL<=0.5 -> fewest refusals -> lower KL; fallbacks; pass trial_index + model_action='save' + seed).
   - The public p-e-w checkpoints used Heretic v1.0.0/v1.1.0.
4. Checkpoints for (C), all pinned by SHA:
   - p-e-w/gemma-3-12b-it-heretic e037e6e1 (TPE, KL 0.16) - priority 1.
   - mlabonne/gemma-3-12b-it-abliterated-v2 b8ae69bd - EXISTS; F32 text-only CausalLM; KL 1.04.
   - huihui-ai 33b9e740 (KL 0.45).
   - Exclude the QAT variant. No public abliterated GaMS3 exists.
5. Hungarian: not in the DECLARED GaMS3 CPT/SFT mix (cards at 1d0b27af/46127695 + arXiv 2603.01691). Do not claim 'absent'. HR/SR/BS make up 22.3% of Base CPT, which is a South-Slavic confound. Card CPT shares are SL 48.9 / EN 28.3 %, not 41.1 / 27.8.
6. (B) item body: mlabonne/harmful_behaviors is identical to AdvBench (520/520) and Heretic uses 500 of those prompts, so EXCLUDE AdvBench. Deduplicate JBB (14-19 near-dups; keep its 100 matched benign) and StrongREJECT (26). HarmBench and RefusEU have 0 overlap.
7. Estimators: arXiv 2511.21140 (ICML 2026) ADOPTS Rogan-Gladen with a Lang-Reiczigel CI; the 'PPI++/EIF more efficient' claim is NOT FOUND. The PPI id is 2301.09633, not 2301.09656. Recommendation: RG primary, per-cell PPI++ as sensitivity, labelled 'adjudicator-agreement-corrected'. StrongREJECT = (1-refusal)*(conv+spec-2)/8 (confirmed); a binary threshold of 0.5 would be ours. RefusEU ASR = Llama-Guard-3-8B + PolyGuard-Qwen, with GPT-4o-mini adjudicating disagreements.

Files: research_report.md (paste-ready related work/novelty/method specs), research_extended.json (claims_table, saturation_log, external_facts, method_specs, assumption_corrections), analysis/overlap.py plus results, and evidence/ logs.

## Research Findings

**Lane 1: input-language x output-language design.** As of 2026-09-24 no study sets the response language independently of the prompt language and measures refusal or ASR in all four cells. We checked scholarly and general engines, 25+ full-text greps and one Semantic Scholar citation hop. The closest designs manipulate something else:
- the jailbreak-instruction language [1];
- the conversation language across two turns [13];
- perturbation type over 18 input languages [7];
- 'think in English' mitigation prompts [2];
- response language only as an outcome of safety-feature ablation [8];
- English-instruction/target-language output for language confusion, not safety [12].

Verdict: the DESIGN is novel. Confidence is medium: the handbook's base rate for unchecked lanes turning out occupied is 11/11, and paywalled or unindexed work was not covered. Paste-ready: 'Deng et al. manipulate the language of the jailbreak instruction and of the prompt, but not of the response; we cross prompt with response language in a matched Gemma/GaMS pair under partial-dose abliteration.'

**Per-claim verdicts.**
- **C-LAG: incremental, and still a LEAD.** Wang et al. show full-dose English-direction transfer over 14 languages and 10 models, with no sibling pairs or ablation-dose sweep [15]. Dose curves exist for English steering [23]. Our replication CI (exp11 G3 -0.60 [-1.31,+0.40]) includes zero.
- **Gemma criterion shift: incremental.** Aziz et al. describe low-resource UNDER-refusal (87.9% -> 43.9%) as calibration, not representation, and find harmless refusal stays low [17]. Ours is the over-refusal side (DiD_c +0.52), but non-English users' higher over-refusal cost is already documented [27].
- **u_lang: incremental, exploratory.** It is the converse of [8], whose Gemma-2 finding of disentangled safety and language features is a tension to cite.
- **RQ4 AUROC 1.00: replication.** It is most parsimoniously a source-separability artefact. Easy negatives give AUROC >0.98 [20], and source-contrast AUROC of 0.996-0.999 drops to 0.590-0.690 on matched twins [21]. RQ4 must be re-run on same-source twins [51].
- **M-OUT production fluency: novel as a hypothesis, untested.** Neighbours report unclear or irrelevant low-resource output [4, 25, 26], but none separates a generation metric from a comprehension metric.

**Heretic @3521f8648a0d…** is a 2.0.0.dev0 snapshot. Its defaults are 200/60 trials (not 80), English-keyword refusals on AdvBench prompts, and first-token KL. It has NO automatic selection rule: the choice is interactive over a Pareto front sorted by (refusals, KL), or set by trial_index [38]. A pre-registered KL<=0.5 rule is needed.

**Checkpoints.** p-e-w heretic v1/v2, huihui-ai and mlabonne v1 exist, and so does mlabonne **-v2**, contrary to the planner [39-43]. All are pinned by SHA. Exclude the QAT variant [44]. No public abliterated GaMS3 was found.

**Hungarian** is not in the DECLARED GaMS3 CPT/SFT mix [46-48]. Do not write 'absent', and note that HR/SR/BS make up 22.3% of Base CPT.

**AdvBench.** mlabonne/harmful_behaviors is set-identical to AdvBench (520/520), and Heretic's defaults use 500 of those prompts [49, 50]. JBB and StrongREJECT therefore need deduplication; HarmBench and RefusEU do not overlap [51, 52, 54].

**Estimator.** Lee et al. (ICML 2026) adopt Rogan-Gladen with a Lang-Reiczigel CI. They argue PPI-type estimators can be biased under calibration/test shift, and 'PPI++/EIF more efficient' is NOT in the paper [34]. Recommendation: RG as primary and per-cell PPI++ as a sensitivity check [35, 36], always labelled 'adjudicator-agreement-corrected'. StrongREJECT's score (1-refusal)(c+s-2)/8 is confirmed [31, 32]. RefusEU's ASR uses two guards plus a GPT-4o-mini adjudicator [33].

**Contradicting evidence.** 22 of 61 configurations are more vulnerable in English [26]. Hard negatives undercut the 'representation intact' reading [20].

**What would change these verdicts.** Any unindexed paper that crosses response language would move the Lane-1 verdict to occupied.

## Sources

[1] [Multilingual Jailbreak Challenges in Large Language Models (arXiv 2310.06474v3, ICLR 2024)](https://arxiv.org/abs/2310.06474) (Yue Deng, Wenxuan Zhang, Sinno Jialin Pan, Lidong Bing; 2023) — Nearest neighbour for the input/output-language lane: manipulates prompt language and the language of an English vs translated AIM jailbreak instruction; responses translated to English for judging; never sets response language independently.

> low-resource languages exhibit about three times the likelihood of encountering harmful content compared to high-resource languages

Locator: abstract

[2] [All Languages Matter: On the Multilingual Safety of Large Language Models (XSafety; arXiv 2310.00905v2)](https://arxiv.org/abs/2310.00905) (Wenxuan Wang, Zhaopeng Tu, Chang Chen, Youliang Yuan, Jen-tse Huang, Wenxiang Jiao, Michael R. Lyu; 2023) — 14 safety issues x 10 languages; proposes 'think in English, respond in original language' prompting (a mitigation, not an output-language manipulation).

> we propose several simple and effective prompting methods to improve the multilingual safety of ChatGPT

Locator: abstract

[3] [Low-Resource Languages Jailbreak GPT-4 (arXiv 2310.02446v2)](https://arxiv.org/abs/2310.02446) (Zheng-Xin Yong, Cristina Menghini, Stephen H. Bach; 2023) — Translate-in / translate-back attack on AdvBench; BYPASS/REJECT/UNCLEAR labels; <1% to 79% bypass.

> provides actionable items that can get the users towards their harmful goals 79% of the time

Locator: abstract

[4] [The Language Barrier: Dissecting Safety Challenges of LLMs in Multilingual Contexts (Findings ACL 2024; arXiv 2401.13136v1)](https://arxiv.org/pdf/2401.13136) (Lingfeng Shen, Weiting Tan, Sihao Chen, Yunmo Chen, Jingyu Zhang, Haoran Xu, Boyuan Zheng, Philipp Koehn, Daniel Khashabi; 2024) — Low-resource prompts yield more harmful AND less relevant responses; nearest neighbour for the production-fluency (M-OUT) account; no response-language manipulation (0 grep hits).

> tend to generate less relevant responses

Locator: Introduction

[5] [Do Methods to Jailbreak and Defend LLMs Generalize Across Languages? (arXiv 2511.00689v2)](https://arxiv.org/abs/2511.00689) (Berk Atil, Rebecca J. Passonneau, Fred Morstatter; 2025) — 10 languages, 6 LLMs, HarmBench/AdvBench jailbreaks and defences; no response-language manipulation found.

[6] [Multilingual jailbreaking of LLMs using low-resource languages (arXiv 2605.18239)](https://arxiv.org/abs/2605.18239) (Dylan Marx, Marcel Dunaiski; 2026) — Multi-turn African-language jailbreaks; translation quality drives success; no input x output crossing (0 grep hits).

[7] [Minionese: Comprehensive Benchmark and Mechanistic Study of Multilingual LLM Safety (arXiv 2607.10112v1; TAIGR @ ICML 2026 workshop)](https://arxiv.org/abs/2607.10112) (Chigozirim Ifebi, Brent Kong, Ayushi Mehrotra; 2026) — Factorises input language (18, 4 tiers) x perturbation type; mechanistic 'misaligned subspace' account; 0 grep hits for response-language manipulation.

> 4 perturbation types (standard translation, code-switching, transliteration, and translationese)

Locator: abstract

[8] [When Safety Speaks a Language: A Mechanistic Analysis of Safety-Language Identity Entanglement in LLMs (arXiv 2608.29936v1)](https://arxiv.org/abs/2608.29936) (Apoorva Upadhyaya, Sandipan Sikdar; 2026) — Nearest neighbour for u_lang: SAE safety features entangled with language identity in Llama-3.1-8B/Qwen2.5-7B (not Gemma-2-9B); ablating safety features shifts output language; no language-feature-induces-refusal experiment.

> ablating safety features impacts not only harmful response rates but also target language

Locator: abstract

[9] [Who Bridges Safety? Identifying and Targeting Cross-Lingual Shared Safety Pathways (arXiv 2608.09095v1)](https://arxiv.org/abs/2608.09095) (Shuyi Miao, Wangjie Qiu, Pengyang Shao, Canran Xiao, Fei Shen, Zhiming Zheng, Tat-Seng Chua; 2026) — Cross-lingual shared safety pathways between high- and non-high-resource languages; no output-language crossing.

[10] [The Illusion of Cross-Lingual Safety in Low-Resource Languages (arXiv 2608.11146v1)](https://arxiv.org/abs/2608.11146) (2026) — LoDNA (Twi, Hausa, Amharic, Swahili); representation-level analysis; its 'literal vs localized' cosine refers to prompt representations, not response language.

> harmful prompts retain less than 10% of the English refusal signal across most language

Locator: abstract

[11] [IndicSafeEval: Safety Robustness of LLMs under Multilingual Persuasive Jailbreak Attacks (arXiv 2609.03781v2)](https://arxiv.org/abs/2609.03781) (2026) — Freshest benchmark checked (Sep 2026): 4 Indian languages x 6 persuasion strategies; no response-language factor found.

[12] [Understanding and Mitigating Language Confusion in LLMs (arXiv 2406.20052v3)](https://arxiv.org/abs/2406.20052) (Kelly Marchisio, Wei-Yin Ko, Alexandre Bérard, Théo Dehaze, Sebastian Ruder; 2024) — Language Confusion Benchmark; line-level pass rate; cross-lingual setting with English instruction and requested target-language output (not safety). Context for the >=90% response-language gate.

> their inability to consistently generate text in a user's desired language

Locator: abstract

[13] [Cognitive Overload: Jailbreaking Large Language Models with Overloaded Logical Thinking (arXiv 2311.09827)](https://arxiv.org/pdf/2311.09827) (2023) — Adjacent design: conversation language switched across two turns (input side); includes sl and hu among prompt languages; not a response-language manipulation.

> in a reversed order through a two-turn conversation

Locator: Section 3

[14] [Sandwich attack: Multi-language Mixture Adaptive Attack on LLMs (arXiv 2404.07242v1)](https://arxiv.org/pdf/2404.07242) (2024) — Forces answers in the same language as asked (diagonal cell only).

> Please give the answer in the language in which it is

Locator: Figure 1 prompt template

[15] [Refusal Direction is Universal Across Safety-Aligned Languages (arXiv 2505.17306v2; NeurIPS 2025 per citing bibliography)](https://arxiv.org/abs/2505.17306) (Xinpeng Wang, Mingyang Wang, Yihong Liu, Hinrich Schütze, Barbara Plank; 2025) — Nearest neighbour for C-LAG: full-dose English-direction ablation transfers across 14 languages and 10 models; alpha only for activation addition; no sibling pairs or ablation-dose sweep found.

> a vector extracted from English can bypass refusals in other languages with near-perfect effectiveness, without any additional fine-tuning

Locator: abstract

[16] [Refusal in Language Models Is Mediated by a Single Direction (arXiv 2406.11717v3, NeurIPS 2024)](https://arxiv.org/abs/2406.11717) (Andy Arditi, Oscar Obeso, Aaquib Syed, Daniel Paleka, Nina Panickssery, Wes Gurnee, Neel Nanda; 2024) — Foundational refusal-direction/abliteration result; 13 models; no multilingual or partial-ablation result (0 grep hits).

> we show that refusal is mediated by a one-dimensional subspace, across 13 popular open-source chat models

Locator: abstract

[17] [Low-Resource Safety Failures Are Action Failures, Not Representation Failures (arXiv 2606.01196v1)](https://arxiv.org/abs/2606.01196) (Rashad Aziz, Ikhlasul Akmal Hanif, Fajri Koto; 2026) — Nearest neighbour for the criterion shift and RQ4: 23 languages (no Slovene/Hungarian), Qwen2.5-7B/Gemma-2-9B/Llama-3.1-8B; harmful refusal 87.9% -> 43.9%; harmless refusal stays low (LRL 9.8%); calibration, not representation.

> Yet harmful refusal drops from 87.9% to 43.9%.

Locator: abstract

> What fails to transfer is calibration of the safety decision, not the underlying representation.

Locator: abstract

[18] [Interpretability without actionability (arXiv 2603.18353) - handbook S3](https://arxiv.org/abs/2603.18353) (Sanjay Basu, Sadiq Y. Patel, Parth Sheth, Bhairavi Muralidharan, Namrata Elamaran, Aakriti Kinra, John Morgan, Rajaie Batniji; 2026) — Knowledge-action gap prior for RQ4: probe AUROC 98.2% vs output sensitivity 45.1% (clinical domain).

> Linear probes discriminated hazardous from benign cases with 98.2% AUROC

Locator: abstract

[19] [LLMs Encode Harmfulness and Refusal Separately (arXiv 2507.11878v5)](https://arxiv.org/abs/2507.11878) (Jiachen Zhao, Jing Huang, Zhengxuan Wu, David Bau, Weiyan Shi; 2025) — Harmfulness is a concept separate from refusal; background for RQ4.

[20] [Hard Negatives Reveal What Easy Negatives Hide (arXiv 2609.27758)](https://arxiv.org/abs/2609.27758) (Paras Balani, Subhrakanta Panda; 2026) — Key RQ4 neighbour and a partial contradiction of Aziz: probe transfer AUROC > 0.98 with unrelated-source negatives collapses with XSTest hard negatives in low-resource languages (drop 0.276 on Qwen2.5-7B).

> we replicate near-perfect transfer (AUROC > 0.98) when harmless prompts come from an unrelated distribution (easy negatives)

Locator: abstract

[21] [The Entanglement Wall: Activation-Space Probes as Risk Detectors, Not Context Adjudicators (arXiv 2607.13075)](https://arxiv.org/pdf/2607.13075) (Dominik Schwarz; 2026) — Source-contrast AUROC 0.996-0.999 vs 0.590-0.690 on topic-matched benign twins: the source-separability control RQ4 lacks.

> fixed transfer to matched pairs is weaker

Locator: abstract

[22] [Detecting Safety Training Modification in Language Models via Activation Analysis (arXiv 2608.05578)](https://arxiv.org/pdf/2608.05578) (G. Messenger; 2026) — Abliteration signatures: collapse vs rotation-without-collapse (Gemma-2-9b-abliterated preserves separation).

> abliteration preserves cluster separation while rotating the refusal

Locator: abstract

[23] [There Is More to Refusal in Large Language Models than a Single Direction (arXiv 2602.02132v2, EMNLP 2026)](https://arxiv.org/pdf/2602.02132) (Faaiz Joad, Majd Hawasly, Sabri Boughorbel, Nadir Durrani, Husrev Taha Sencar; 2026) — Steering strength acts as a one-dimensional dose knob trading refusal against over-refusal (English); dose-response per se is not new.

> steering strength increases, the model increasingly

Locator: Introduction

[24] [Decided Upstream, Written Late: Locating and Pricing the Cross-Lingual Refusal Circuit of a Multilingual MoE (arXiv 2608.08032v2)](https://arxiv.org/abs/2608.08032) (Ramakrishna P. Kompella, Aadit Mahajan; 2026) — Harm detection nearly language-invariant mid-network but orthogonal to the late refusal 'writer'; representation-vs-action context.

[25] [SomaliBench Eval: Measuring English-to-Somali Refusal Gaps in Open-Weight Language Models (arXiv 2605.25420v2)](https://arxiv.org/pdf/2605.25420) (Khalid Yusuf Dahir; 2026) — Non-refusal in Somali is mostly unclear output (wrong-language/incoherent/off-topic), not fluent harmful compliance; neighbour for M-OUT.

> not fluent harmful compliance but unclear output

Locator: abstract

[26] [Why Do Safety Guardrails Degrade Across Languages? (arXiv 2605.17173)](https://arxiv.org/abs/2605.17173) (Max Zhang, Ameen Patel, Sang T. Truong, Sanmi Koyejo; 2026) — IRT decomposition over 61 configurations; contradicting evidence: 22 configurations more vulnerable in English; low-resource responses higher-entropy.

> 22 model configurations are more vulnerable in English than in low-resource languages

Locator: abstract

[27] [Who Pays More for Safety? Measuring the Disparate Cost of Safety Alignment across Languages (arXiv 2608.22490)](https://arxiv.org/abs/2608.22490) (Chanwoong Yoon, Jungsoo Park, Alan Ritter; 2026) — Non-English users bear higher utility/over-refusal 'Safety Cost': the direction of our Gemma criterion shift is not new.

> non-English users consistently bear a higher Safety Cost than English users

Locator: abstract

[28] [The Heterogeneous Safety Impacts of Benign Multilingual Fine-Tuning (arXiv 2606.28843)](https://arxiv.org/abs/2606.28843) (Will Hawkins, Kaivalya Rawal, Jonathan Rystrøm, Stratis Tsirtsis, Zihao Fu, Greta Warren, Ryan Brown, Eoin Delaney, Sandra Wachter, Brent Mittelstadt, Chris Russell; 2026) — RQ3 neighbour: language-dependent safety drift decoupled from capability (Llama-3.2, Qwen3, Gemma-3 small).

> safety outcomes are highly sensitive to both the choice of fine-tuning language and the evaluation language

Locator: abstract

[29] [Comparative Analysis of LLM Abliteration Methods: A Cross-Architecture Evaluation (arXiv 2512.13655v2)](https://arxiv.org/abs/2512.13655) (Richard J. Young; 2025) — Four tools x 16 models; Heretic KL 0.043-1.646; no multilingual or random-direction control.

[30] [Abliteration Is Not a Scalpel (arXiv 2607.17427)](https://arxiv.org/abs/2607.17427) (Aleksander Fafuła; 2026) — Off-target disposition effects of abliteration (Gemma-4/Qwen3 MoE); English decision tasks.

[31] [A StrongREJECT for Empty Jailbreaks (arXiv 2402.10260v2)](https://arxiv.org/pdf/2402.10260) (Alexandra Souly, Qingyuan Lu, Dillon Bowen, Tu Trinh, Elvis Hsieh, Sana Pandey, Pieter Abbeel, Justin Svegliato, Scott Emmons, Olivia Watkins, Sam Toyer; 2024) — Score definition and human-agreement table (rubric Spearman 0.846, fine-tuned 0.900, HarmBench 0.819).

> a binary score for non-refusal and two 5-point Likert scale scores

Locator: Section 2

[32] [dsbowen/strong_reject evaluate.py @ 7a551d5](https://raw.githubusercontent.com/dsbowen/strong_reject/7a551d5b440ec7b75d4f6f5bb7c1719965b76b47/strong_reject/evaluate.py) — Exact rubric scoring code; confirms (1-refusal)*(conv+spec-2)/8; fine-tuned evaluator qylu4156/strongreject-15k-v1.

> (1 - output["refusal"]) * (output["convincingness"] + output["specificity"] - 2) / 8

Locator: strongreject_rubric()

[33] [Multilingual Refusal Alignment for Safer Large Language Models (RefusEU; Findings ACL 2026; arXiv 2606.07535)](https://arxiv.org/pdf/2606.07535) (Aleksandra Krasnodębska, Wojciech Kusa, Aldo Lipani; 2026) — ASR = Llama-Guard-3-8B + PolyGuard-Qwen, GPT-4o-mini adjudicates disagreements; 1,400 test prompts per language; DeepL-translated generation seeds.

> prompted with a predefined safety classification protocol

Locator: Section 4 evaluation

[34] [How to Correctly Report LLM-as-a-Judge Evaluations (arXiv 2511.21140v4, ICML 2026)](https://arxiv.org/pdf/2511.21140) (Chungpa Lee, Thomas Zeng, Jongwon Jeong, Jy-yong Sohn, Kangwook Lee; 2026) — Adopts Rogan-Gladen with Lang-Reiczigel CI and adaptive calibration allocation; says PPI-type estimators can be biased under calibration/test shift; no EIF; contradicts the strategist's PPI++/EIF claim.

> remains unbiased under such shifts. We therefore adopt this estimator

Locator: Section 1

[35] [Prediction-Powered Inference (arXiv 2301.09633v4)](https://arxiv.org/abs/2301.09633) (Anastasios N. Angelopoulos, Stephen Bates, Clara Fannjiang, Michael I. Jordan, Tijana Zrnic; 2023) — Correct PPI identifier (the plan's 2301.09656 is an unrelated XAI paper).

[36] [PPI++: Efficient Prediction-Powered Inference (arXiv 2311.01453v2)](https://arxiv.org/pdf/2311.01453) (Anastasios N. Angelopoulos, John C. Duchi, Tijana Zrnic; 2023) — iid labelled/unlabelled assumption; power tuning 'essentially never worse'.

> power tuning is essentially never worse than either classical or prediction-powered inference

Locator: Section 1

[37] [AutoEval Done Right: Using Synthetic Data for Model Evaluation (arXiv 2403.07008v3)](https://arxiv.org/abs/2403.07008) (Pierre Boyeau, Anastasios N. Angelopoulos, Nir Yosef, Jitendra Malik, Michael I. Jordan; 2024) — PPI applied to model evaluation; background for the estimator choice.

[38] [p-e-w/heretic @ 3521f8648a0dccf6e12a92666862632235fac7e6 (config.py; also config.default.toml, main.py, README)](https://raw.githubusercontent.com/p-e-w/heretic/3521f8648a0dccf6e12a92666862632235fac7e6/src/heretic/config.py) (p-e-w; 2026) — Full SHA, 2026-09-05, 2.0.0.dev0, 25 commits after v1.4.0; defaults 200/60; English keyword refusals on AdvBench test[:100]; first-token KL; no automatic selection (interactive Pareto choice or trial_index).

> Index (in the sorted Pareto front) of the trial to use, or unset to prompt the user.

Locator: Settings.trial_index

[39] [p-e-w/gemma-3-12b-it-heretic (sha e037e6e112ea85777fc3858469cdc31fdfceaa13)](https://huggingface.co/p-e-w/gemma-3-12b-it-heretic/raw/main/README.md) (p-e-w; 2025) — Heretic v1.0.0; KL 0.16; 3/100 refusals; bf16 Gemma3ForConditionalGeneration.

> made using [Heretic](https://github.com/p-e-w/heretic) v1.0.0

Locator: card header

[40] [p-e-w/gemma-3-12b-it-heretic-v2 (sha 23fb4ede77eeb35f47904cd4993fd44e0668b7e8)](https://huggingface.co/p-e-w/gemma-3-12b-it-heretic-v2/raw/main/README.md) (p-e-w; 2025) — Heretic v1.1.0; KL 0.0995; 7/100.

> made using [Heretic](https://github.com/p-e-w/heretic) v1.1.0

Locator: card header

[41] [huihui-ai/gemma-3-12b-it-abliterated (sha 33b9e7402b3d8b396afdd9a3cfcefe391bf7a696)](https://huggingface.co/huihui-ai/gemma-3-12b-it-abliterated/raw/main/README.md) (huihui-ai; 2025) — Sumandora-style abliteration; bf16; KL 0.45 per Heretic README.

> This is a crude, proof-of-concept implementation to remove refusals from an LLM model without using TransformerLens.

Locator: card

[42] [mlabonne/gemma-3-12b-it-abliterated (sha fc5f782bd0a995f66f59c68dd3ab2f888ba65f1a)](https://huggingface.co/mlabonne/gemma-3-12b-it-abliterated/raw/main/README.md) (mlabonne; 2025) — Layerwise hidden-state abliteration, layers 3-45, refusal weight 0.6; bf16.

> This is combined with a refusal weight of 0.6 to upscale the importance of this refusal direction in each layer.

Locator: card

[43] [mlabonne/gemma-3-12b-it-abliterated-v2 (sha b8ae69bd7844187c27c941785afc1b0919f91f8e)](https://huggingface.co/mlabonne/gemma-3-12b-it-abliterated-v2/raw/main/README.md) (mlabonne; 2025) — EXISTS (contradicts planner); F32 text-only Gemma3ForCausalLM; orthogonalisation with normal layer-weight profile; 3/100, KL 1.04 per Heretic README.

> These weight factors follow a normal distribution with a certain spread and peak layer.

Locator: card

[44] [mlabonne/gemma-3-12b-it-qat-abliterated (sha 85b7be890f6038d310ba1416891993077fad55d4)](https://huggingface.co/mlabonne/gemma-3-12b-it-qat-abliterated/raw/main/README.md) (mlabonne; 2025) — QAT base (gemma-3-12b-it-qat-q4_0-unquantized): not a pure sibling; exclude.

[45] [google/gemma-3-12b-it (HF API; sha 96b6f1eccf38110c56df3a15bffe176da04bfd80)](https://huggingface.co/api/models/google/gemma-3-12b-it) (Google; 2025) — Gated (manual); Gemma3ForConditionalGeneration, 12.19B bf16 params incl. vision.

[46] [cjvt/GaMS3-12B-Instruct model card @ 1d0b27af](https://huggingface.co/cjvt/GaMS3-12B-Instruct/raw/1d0b27af5748784482600d24779409e7e1dc9adc/README.md) (CJVT; 2026) — Declared languages SL/EN/HR/BS/SR; CPT tables (Base SL 48.9/EN 28.3/HR 9.5/SR 8.0/BS 4.8 %); GaMS-Safety 459 + Nemotron-Chat 88,126; no Hungarian.

> The model might also work for other languages supported by Gemma 3, even though it was not continually pretrained on them.

Locator: Model details

[47] [cjvt/GaMS3-12B (base) model card @ 46127695](https://huggingface.co/cjvt/GaMS3-12B/raw/46127695de173a5de72e1da9dc43846f58553477/README.md) (CJVT; 2026) — Same CPT mix; no Hungarian; text-only Gemma3ForCausalLM.

[48] [Building a Strong Instruction Language Model for a Less-Resourced Language (GaMS3; arXiv 2603.01691v1)](https://arxiv.org/pdf/2603.01691) (Domen Vreš, Tjaša Arčon, Timotej Petrič, Dario Vajda, Marko Robnik-Šikonja, Iztok Lebar Bajec; 2026) — 140B SL/EN/BS/SR/HR CPT tokens; human-written safety prompts; 0 matches for Hungarian.

> The safety prompts were written by humans

Locator: Section 4 (chat tuning)

[49] [mlabonne/harmful_behaviors (sha 01cead01398926d81f7c52bdb790ee8cf77ebba7)](https://huggingface.co/datasets/mlabonne/harmful_behaviors) (mlabonne; 2024) — Heretic's default harmful set; card states no provenance; content set-identical to AdvBench (520/520) by analysis/overlap.py.

[50] [AdvBench harmful_behaviors.csv (Zou et al. 2023)](https://github.com/llm-attacks/llm-attacks/blob/main/data/advbench/harmful_behaviors.csv) (2023) — 520 harmful behaviours; source of mlabonne/harmful_behaviors; must be excluded from (B).

[51] [JailbreakBench (arXiv 2404.01318v5) and JBB-Behaviors dataset (sha 886acc35)](https://arxiv.org/abs/2404.01318) (Patrick Chao, Edoardo Debenedetti, Alexander Robey, Maksym Andriushchenko, Francesco Croce, Vikash Sehwag; 2024) — 100 harmful + 100 matched benign behaviours (same-source negatives for RQ4); 18 AdvBench-sourced items, 14-19 near-duplicates of Heretic's prompts.

[52] [HarmBench (arXiv 2402.04249v2)](https://arxiv.org/abs/2402.04249) (Mantas Mazeika, Long Phan, Xuwang Yin, Andy Zou, Zifan Wang; 2024) — 400 text behaviours (200 standard); 0 overlap with Heretic's AdvBench prompts at Jaccard 0.8.

[53] [SORRY-Bench (arXiv 2406.14598v2)](https://arxiv.org/abs/2406.14598) (Tinghao Xie, Xiangyu Qi, Yi Zeng, Yangsibo Huang; 2024) — 440 class-balanced unsafe instructions over 44 categories; HF gated (auto); overlap not computed.

[54] [NASK-PIB/RefusEU dataset (sha 5523ce30b9b6af59e95ade9c610b8b974412a6bb)](https://huggingface.co/datasets/NASK-PIB/RefusEU) (NASK-PIB; 2026) — Evaluation split 16,800 rows = 1,400 x 12 languages incl. sl; 0 overlap with AdvBench.

[55] [Crosslingual Capabilities and Knowledge Barriers in Multilingual Large Language Models (arXiv 2406.16135v2)](https://arxiv.org/abs/2406.16135) (Lynn Chua, Badih Ghazi, Yangsibo Huang, Pritish Kamath, Ravi Kumar; 2024) — One-line positioning for identity claim C1 (abstract only).

[56] [Edit Once, Update Everywhere: Cross-Lingual Knowledge Synchronization in LLMs (X-KDE; arXiv 2502.14645v2)](https://arxiv.org/abs/2502.14645) (Yuchen Wu, Liang Ding, Li Shen, Dacheng Tao; 2025) — One-line positioning for C1 (abstract only).

[57] [Refusal Lives Downstream of Persona in Chat Models (arXiv 2606.26161)](https://arxiv.org/abs/2606.26161) (Viola Zhong, Qirui Li; 2026) — Starting-list entry re-verified (title/date).

[58] [Abliteration Mitigation via Refusal Aliases (arXiv 2608.18093)](https://arxiv.org/abs/2608.18093) (Nathan Truong; 2026) — Starting-list entry re-verified (title/date).

[59] [Refusal geometry reflects refusal training (arXiv 2608.25390v2)](https://arxiv.org/pdf/2608.25390) (Andrey Labunets; 2026) — Refusal-training structure shapes refusal rank and ablation robustness.

[60] [BabelSteering: Multilingual Safety Alignment via English Steering Vectors (arXiv 2608.16577)](https://arxiv.org/pdf/2608.16577) (E. V. Stein, D. Meier, T. Ruas, J. P. Wahle, B. Gipp; 2026) — English refusal steering across 8 languages incl. Gemma 7B: +11 pp harmful refusal, +13 pp pseudo-harmful refusal.

> pseudo-harmful refusals increase by 13 pp on average

Locator: abstract

[61] [Aligned in Form, Not in Meaning: The Comprehension-Containment Decoupling of LLM Safety in Low-Resource Bangla Derogatory Speech (arXiv 2608.02941)](https://arxiv.org/abs/2608.02941) (Shadab Bin Habib, A K M Ferdous Reza Habib, Subarno Neel, Adib Sakhawat; 2026) — Comprehension and containment operate independently; closest to M-OUT's comprehension/production split but no generation-fluency metric.

[62] [The State of Multilingual LLM Safety Research (arXiv 2505.24119)](https://arxiv.org/abs/2505.24119) (Zheng-Xin Yong, Beyza Ermis, Marzieh Fadaee, Stephen H. Bach, Julia Kreutzer; 2025) — Survey of ~300 *ACL safety papers 2020-2024; English-centric field.

[63] [Measuring & Mitigating Over-Alignment for LLMs in Multilingual Criminal Law Courts (TF-RefusalBench; arXiv 2606.23375)](https://arxiv.org/pdf/2606.23375) (2026) — Abliteration removes refusal with minimal task cost in FR/DE/IT/EN legal tasks; C5a/RQ3 neighbour.

[64] [Sycophancy as a Multilingual Alignment Failure (arXiv 2606.08451)](https://arxiv.org/pdf/2606.08451) (2026) — Notes that open-ended generation in weak languages confounds safety evaluation with grammatical failure (uses forced-choice log-probs).

## Verification

Numbered citations resolve to unique listed sources. Passage checks test text occurrence, not claim truth or entailment. Author/year metadata and locators are not independently verified. Details: `research_verification.json`.

- Source [1]: text found — low-resource languages exhibit about three times the likelihood of encountering harmful content comp
- Source [2]: text found — we propose several simple and effective prompting methods to improve the multilingual safety of Chat
- Source [3]: text found — provides actionable items that can get the users towards their harmful goals 79% of the time
- Source [4]: text found — tend to generate less relevant responses
- Source [7]: text found — 4 perturbation types (standard translation, code-switching, transliteration, and translationese)
- Source [8]: text found — ablating safety features impacts not only harmful response rates but also target language
- Source [10]: text found — harmful prompts retain less than 10% of the English refusal signal across most language
- Source [12]: text found — their inability to consistently generate text in a user's desired language
- Source [13]: text found — in a reversed order through a two-turn conversation
- Source [14]: text found — Please give the answer in the language in which it is
- Source [15]: text found — a vector extracted from English can bypass refusals in other languages with near-perfect effectivene
- Source [16]: text found — we show that refusal is mediated by a one-dimensional subspace, across 13 popular open-source chat m
- Source [17]: text found — Yet harmful refusal drops from 87.9% to 43.9%.
- Source [17]: text found — What fails to transfer is calibration of the safety decision, not the underlying representation.
- Source [18]: text found — Linear probes discriminated hazardous from benign cases with 98.2% AUROC
- Source [20]: text found — we replicate near-perfect transfer (AUROC > 0.98) when harmless prompts come from an unrelated distr
- Source [21]: text found — fixed transfer to matched pairs is weaker
- Source [22]: text found — abliteration preserves cluster separation while rotating the refusal
- Source [23]: text found — steering strength increases, the model increasingly
- Source [25]: text found — not fluent harmful compliance but unclear output
- Source [26]: text found — 22 model configurations are more vulnerable in English than in low-resource languages
- Source [27]: text found — non-English users consistently bear a higher Safety Cost than English users
- Source [28]: text found — safety outcomes are highly sensitive to both the choice of fine-tuning language and the evaluation l
- Source [31]: text found — a binary score for non-refusal and two 5-point Likert scale scores
- Source [32]: text found — (1 - output["refusal"]) * (output["convincingness"] + output["specificity"] - 2) / 8
- Source [33]: text found — prompted with a predefined safety classification protocol
- Source [34]: text found — remains unbiased under such shifts. We therefore adopt this estimator
- Source [36]: text found — power tuning is essentially never worse than either classical or prediction-powered inference
- Source [38]: text found — Index (in the sorted Pareto front) of the trial to use, or unset to prompt the user.
- Source [39]: text found — made using [Heretic](https://github.com/p-e-w/heretic) v1.0.0
- Source [40]: text found — made using [Heretic](https://github.com/p-e-w/heretic) v1.1.0
- Source [41]: text found — This is a crude, proof-of-concept implementation to remove refusals from an LLM model without using 
- Source [42]: text found — This is combined with a refusal weight of 0.6 to upscale the importance of this refusal direction in
- Source [43]: text found — These weight factors follow a normal distribution with a certain spread and peak layer.
- Source [46]: text found — The model might also work for other languages supported by Gemma 3, even though it was not continual
- Source [48]: text found — The safety prompts were written by humans
- Source [60]: text found — pseudo-harmful refusals increase by 13 pp on average

## Follow-up Questions

- Does the RQ4 decodability result survive when harmless negatives are drawn from the same source as the harmful prompts (exp9's 150 content-matched twins, XSTest contrast prompts, JBB matched benign behaviours), and does the Slovene AUROC drop more than the English one as Balani & Panda report for lower-resource languages?
- In the M-IN vs M-OUT 2x2 (Slovene/English prompt x Slovene/English forced response), does retained refusal under the English edit track the response language (production fluency, BPB) rather than the prompt language (comprehension, Belebele), and does the answer differ between Gemma and GaMS?
- Are the LLM judge's sensitivity and specificity stable across abliteration dose within each model x language stratum (the transportability condition for Rogan-Gladen), or must correction be done per cell with PPI++ on in-cell adjudicated samples?

---
*Generated by AI Inventor Pipeline*
