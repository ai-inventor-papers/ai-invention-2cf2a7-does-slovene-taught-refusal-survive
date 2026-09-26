Style note: These papers mix short declarative sentences (8-12 words) with one longer sentence carrying a qualification or comparison (20-30 words). Hedging is sparse and tied to genuine uncertainty ("may not generalize", "likely not optimal"). First person is rare in Arditi and Joad, more common in Wang and Krasnodebska ("we show", "we uncover"). Citation density is moderate: 2-4 per paragraph in the introduction, clustered at the related-work boundary. Numbers appear in results paragraphs alongside the condition that produced them, never free-floating.

---

## Arditi et al. 2024 — "Refusal in Language Models Is Mediated by a Single Direction" (NeurIPS 2024)
URL: https://arxiv.org/abs/2406.11717

### Abstract
"Conversational large language models are fine-tuned for both instruction-following and safety, resulting in models that obey benign requests but refuse harmful ones. While this refusal behavior is widespread across chat models, its underlying mechanisms remain poorly understood. In this work, we show that refusal is mediated by a one-dimensional subspace, across 13 popular open-source chat models up to 72B parameters in size."

### Introduction (first paragraph)
"Deployed large language models (LLMs) undergo multiple rounds of fine-tuning to become both helpful and harmless: to provide helpful responses to innocuous user requests, but to refuse harmful or inappropriate ones. Naturally, large numbers of users and researchers alike have attempted to circumvent these defenses using a wide array of jailbreak attacks to uncensor model outputs, including fine-tuning techniques."

### Results paragraph
"Under no intervention, chat models refuse nearly all harmful requests, yielding high refusal and safety scores. Ablating the refusal direction from the model's residual stream activations, labeled as directional ablation, reduces refusal rates and elicits unsafe completions."

### Limitations
"Our study has several limitations. While we evaluate a broad range of open-source models, our findings may not generalize to untested models, especially those at greater scale, including current state-of-the-art proprietary models and those developed in the future. Additionally, the methodology we used to extract the 'refusal direction' is likely not optimal and relies on several heuristics."

---

## Wang et al. 2025 — "Refusal Direction is Universal Across Safety-Aligned Languages" (NeurIPS 2025)
URL: https://arxiv.org/abs/2505.17306

### Abstract
"Refusal mechanisms in large language models (LLMs) are essential for ensuring safety. Recent research has revealed that refusal behavior can be mediated by a single direction in activation space, enabling targeted interventions to bypass refusals. While this is primarily demonstrated in an English-centric context, appropriate refusal behavior is important for any language, but poorly understood. In this paper, we investigate the refusal behavior in LLMs across 14 languages using PolyRefuse, a multilingual safety dataset created by translating malicious and benign English prompts into these languages. We uncover the surprising cross-lingual universality of the refusal direction: a vector extracted from English can bypass refusals in other languages with near-perfect effectiveness, without any additional fine-tuning. Even more remarkably, refusal directions derived from any safety-aligned language transfer seamlessly to others."

### Introduction (first paragraph)
"LLMs are increasingly deployed across a wide range of real-world applications. To ensure their safe use, LLMs are expected to exhibit a refusal mechanism, the ability to obey to non-harmful request but refuse harmful, unethical, or policy-violating requests. This capability is typically instilled via reinforcement learning from human feedback (RLHF) and other alignment strategies."

### Results paragraph
"English-derived refusal vectors lead to a substantial increase in harmful compliance across all evaluated models and safety-aligned languages. Even models that initially demonstrate strong multilingual safety, such as gemma-2-9B-it and Qwen2.5-14B-Instruct, can be successfully jailbroken post-ablation... Yet, the ablation further increases compliance rates (e.g., gemma-2-9B-it increases from 0.57 to 0.87), confirming that English-derived refusal directions contribute notably to refusal behavior even in languages where safety is already suboptimal."

### Limitations
"While our work provides new insights into the multilingual refusal mechanisms of LLMs, it has several limitations. First, our analysis is based on a selected set of 14 typologically diverse languages. The observed transferability may be influenced by the amount of representation each language has in the model's pretraining corpus. As a result, our findings may not extend to languages with extremely limited data."

---

## Joad et al. 2026 — "There Is More to Refusal in Large Language Models than a Single Direction"
URL: https://arxiv.org/abs/2602.02132

### Abstract
"Prior work argues that refusal in large language models is mediated by a single direction, enabling steering and abliteration. We show that this account is incomplete: across diverse refusal and non-compliance categories, refusal behaviors correspond to geometrically distinct directions in activation space. Yet activation steering along any refusal-related direction produces nearly identical refusal–over-refusal trade-offs, acting as a shared one-dimensional control knob. Thus, different directions primarily affect not whether the model refuses, but how it refuses. Using sparse autoencoders, we uncover a structured internal representation of refusal: a reusable core of shared refusal latents supplemented by style- and domain-specific latents. Linear interventions collapse this structure into uniform behavioral control, flattening mechanistic differences across refusal types. Our results reconcile the apparent simplicity of refusal steering with the diversity of refusal behaviors, and clarify the limits of linear interpretability for aligned model behavior."

### Introduction (first paragraph)
"A central objective in training large language models (LLMs) is to align them with values such as helpfulness and harmlessness while preserving sensitivity to user intent. Refusal training supports this goal by enabling models to decline inappropriate or unsupported requests rather than comply indiscriminately. Such refusals are typically expressed through a characteristic tone and stance."

### Results paragraph
"Typical cosine similarities are 0.4–0.6, with several pairs close to orthogonal. This indicates that different refusal categories correspond to distinct activation-space directions rather than a single universal refusal vector. The directions are nevertheless structured rather than arbitrary. Hierarchical agglomerative clustering over the cosine-similarity matrix reveals clusters that broadly align with the refusal categories: safety- and content-policy-oriented refusals group more closely with one another than with capability-limitation or underspecification refusals."

### Limitations
"Our analysis is conducted on three instruction-tuned language models. While these models span different architectures and training pipelines, fine-tuning can substantially reorganize models' internal representation spaces. We therefore do not assume that the observed refusal mechanisms persist in larger models, base (non–instruction-tuned) models, or systems trained with substantially different alignment procedures. Our findings should thus be interpreted as characterizing refusal behavior within this model regime rather than establishing universality across all large language models."

---

## Krasnodebska et al. 2026 — "Multilingual Refusal Alignment for Safer Large Language Models" (Findings ACL 2026)
URL: https://arxiv.org/abs/2606.07535

### Abstract
"As Large Language Models (LLMs) are deployed globally, ensuring their safety and alignment across multiple languages becomes paramount. However, safety behaviors often vary unpredictably between languages, posing significant challenges for consistent and ethical AI. In this work, we systematically investigate the dynamics of multilingual alignment, exploring whether single-language alignment transfers cross-lingually, how language consistency is preserved during training, and the resulting trade-offs with general knowledge capabilities. We introduce RefusEU, a novel refusal alignment dataset covering 12 European languages, including a dedicated test set for evaluating current state-of-the-art models. Our controlled Direct Preference Optimization (DPO) experiments provide two key insights: aligning models exclusively in English is insufficient to ensure cross-lingual safety, even for the same harm categories, whereas training on multilingual datasets can improve safety without degrading general performance, as measured by the Global MMLU benchmark."

### Introduction (first paragraph)
"Advances in pretrained Large Language Models (LLMs) have significantly improved language understanding and generation, enabling their rapid adoption in real-world applications. At the same time, these models raise safety challenges such as harmful outputs, biased behavior, and ethical risk - that are amplified in multilingual settings."

### Results paragraph
"Overall, ASR scores on RefuseEU-test were the lowest on the balanced dataset for both LLaMA 8B and LLaMA 70B trainings. The second most interesting configuration was the dataset based on high-resource languages. In this scenario only Slovenian exceeded 10% ASR for LLaMA 70B. For LLaMA 8B, all scores were below 5%, except for Latvian."

---

## Vres et al. 2026 — "Building a Strong Instruction Language Model for a Less-Resourced Language"
URL: https://arxiv.org/abs/2603.01691

### Abstract
"Large language models (LLMs) have become an essential tool for natural language processing and artificial intelligence in general. Current open-source models are primarily trained on English texts, resulting in poorer performance on less-resourced languages and cultures. We present a set of methodological approaches necessary for the successful adaptation of an LLM to a less-resourced language, and demonstrate them using the Slovene language. We present GaMS3-12B, a generative model for Slovene with 12 billion parameters, and demonstrate that it is the best-performing open-source model for Slovene within its parameter range."

### Introduction (first paragraph)
"Large language models (LLMs), particularly generative LLMs like GPT models, have dramatically transformed natural language processing (NLP), advancing our understanding and ability to generate human language. As a result of this rapid development, new open-source decoder-type transformer LLMs such as Gemma, Llama, Nemotron, and many others are released on a regular basis. These models are trained predominantly on high-resource languages (primarily English) while their attention and performance on less-resourced languages, such as Slovene, is limited."

### Results paragraph
"GaMS3 ranks only behind the two times larger GaMS-27B-Nemotron and Gemma 3 27B. It beats Gemma 3 12B significantly, showing a clear benefit of Slovene adaptation. GaMS3 also outperforms GaMS-9B-Nemotron and Zlatorog, which are the Slovene specialized models of similar size."

### Limitations
"The main drawback of our approach appears to be its reliance on machine-translated data, particularly during the SFT stage. As a result, the model's Slovene is not as natural as it could be. We plan to address this problem in the future by reducing the amount of machine-translation data and improving its quality."

---

## Section outlines

### Arditi et al. 2024
1. Introduction
2. Methodology
3. Refusal is mediated by a single direction
4. A white-box jailbreak via weight orthogonalization
5. Mechanistic analysis of adversarial suffixes
6. Related work
7. Discussion
- Method organised by: pipeline (extract direction, ablate, orthogonalise)
- Results organised by: claim then evidence, main result then extensions

### Wang et al. 2025
1. Introduction
2. Related Work (2.1 LLM Safety and Refusal Mechanism, 2.2 Multilingual Alignment)
3. Background (3.1 Refusal Direction Extraction, 3.2 Removing or Adding Refusal Behavior)
4. Not All Languages are Safety-Aligned
5. Assessing Refusal Directions Across Languages (5.1 PolyRefuse, 5.2 Cross-lingual Transfer of English Refusal Vectors, 5.3 Refusal Vectors from Non-English Languages, 5.4 Reducing Compliance Rate)
6. Exploring the Geometry of Refusal in LLMs
7. Discussion (incl. Limitations)
8. Conclusion
- Method organised by: component (dataset, extraction, transfer, geometry)
- Results organised by: research question, each with its own subsection

### Joad et al. 2026
1. Introduction
2. Methods (2.1 Identifying Refusal in Activation Space, 2.2 Identifying Refusal in SAE Space)
3. Experimental Setup
4. Findings (4.1 Geometry of Refusal Directions, 4.2 Interventions: Steering and Ablation, 4.3 Refusal Directions in SAE Space)
5. Related Work
6. Conclusion
7. Limitations
- Method organised by: technique (mean-difference directions, SAE-based directions)
- Results organised by: level of analysis (geometry, behavioural interventions, SAE decomposition)

### Krasnodebska et al. 2026
1. Introduction
2. Related work
3. Dataset construction
4. Methodology (4.1 Abliteration, 4.2 Alignment datasets, 4.3 Training setup, 4.4 Baselines, 4.5 Evaluation)
5. Results (5.1 Attack success rate, 5.2 Language consistency)
- Method organised by: pipeline stage (data, abliteration, training, evaluation)
- Results organised by: metric (ASR, then language consistency)

### Vres et al. 2026
1. Introduction
2. Related work
3. Continual pretraining (3.1-3.5 substages)
4. Supervised fine-tuning (4.1 GaMS-Instruct, 4.2 GaMS-Nemotron-Chat)
5. Training setup
6. Evaluation (6.1 Slovenian-LLM-Eval, 6.2 Translation, 6.3 Arena)
7. Conclusion
- Method organised by: training stage (CPT stages, then SFT stages)
- Results organised by: benchmark
