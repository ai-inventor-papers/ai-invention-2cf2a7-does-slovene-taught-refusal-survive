---
license: gemma
language:
- sl
- en
- sr
- hr
- bs
base_model:
- google/gemma-3-12b-pt
pipeline_tag: text-generation
---

# Model Card for GaMS3-12B-Instruct

GaMS3 represents the next generation of the GaMS (Generative Model for Slovene) model. The model is based on Google's Gemma 3 family and continually pretrained on Slovene, English, and some portion of Croatian, Serbian, and Bosnian corpora. The supervised fine-tuning phase was done on a combination of Slovene and English datasets.

![image/png](https://cdn-uploads.huggingface.co/production/uploads/652d40a78fa1fbb0aae165bb/94gX0PG8zRB_Zg31K2y_i.png)

**NOTE:** This is a pretrained version of the model and is not instruction/chat tuned. For the instruct version, check [cjvt/GaMS3-12B-Instruct](https://huggingface.co/cjvt/GaMS3-12B-Instruct).

## Acknowledgment

The model was developed within the [PoVeJMo](https://www.cjvt.si/povejmo/en/project/) research program (Adaptive Natural Language Processing with Large Language Models), particularly within the research project titled SloLLaMai -- Open-access computationally efficient models for Slovenian. The program is funded within the Recovery and Resilience Plan by the Slovenian Research and Innovation Agency (ARIS) and NextGenerationEU. The authors also acknowledge the financial support from the Slovenian Research and Innovation Agency (research core funding No. P6-0411 -- Language Resources and Technologies for Slovene).

This project is also funded by the European Union under Horizon Europe (101186647 – AI4DH).

We thank everyone who contributed to data collection and preparation, which enabled us to train our model. Special thanks go to Nikola Ljubešić, Taja Kuzman, Tjaša Arčon, Jaka Čibej, Simon Krek, Tomaž Erjavec, Iztok Kosem and Tomaž Savodnik.

The model's development was supported by NVIDIA as a part of their Sovereign AI initiative. We are thankful for the access to [NVIDIA DGX Cloud Lepton](https://developer.nvidia.com/blog/introducing-nvidia-dgx-cloud-lepton-a-unified-ai-platform-built-for-developers/). We are also extremely grateful for all the support and help we received from a group of exceptional people at NVIDIA: Anna Louise Ollerenshaw, Meriem Bendris, Oleg Sudakov, Benedetta Delfino, Rita Fernandes Neves, Andrea Pilzer, Miguel Martinez, Noel Osagie, Adam Henryk Grzywaczewski and Aleks Polak.

## Basic information

- **Developed by:** team of researchers at the University of Ljubljana, Faculty for Computer and Information Science. Team members: Domen Vreš, Iztok Lebar Bajec, Tjaša Arčon, Timotej Petrič, Dario Vajda and Marko Robnik-Šikonja.
- **Languages:** Slovene, English (primary), Croatian, Bosnian and Serbian (secondary). The model might also work for other languages supported by Gemma 3, even though it was not continually pretrained on them.
- **Base model:** [google/gemma-3-12b-pt](https://huggingface.co/google/gemma-3-12b-pt)
- **License:** [Gemma](https://ai.google.dev/gemma/terms)

## Usage

### Transformers library

The model can be run through `pipeline` API using the following code:

```python
from transformers import pipeline

model_id = "cjvt/GaMS3-12B"

model = pipeline(
    "text-generation",
    model=model_id,
    device_map="cuda" # replace with "mps" to run on a Mac device
)

prompts = [
    "The examples of antonyms are:\nhigh => low\nwide => narrow\nbig =>",
    "Pristanek je bil prvi nadzorovani spust ameriškega vesoljskega plovila na površje Lune po Apollu 17 leta 1972, ko je na Luni pristala zadnja Nasina misija s posadko.\nDoslej so na Luni pristala vesoljska plovila le iz štirih drugih držav –",
    "U četvrtak je bila prva polufinalna večer Dore, a komentari na društvenim mrežama ne prestaju. U nedjeljno finale prošli su:"
]

sequences = model(
    prompts,
    max_new_tokens=512,
    num_return_sequences=1
)

for seq in sequences:
    print("--------------------------")
    print(f"Result: {seq[0]['generated_text']}")
    print("--------------------------\n")
```

For multi GPU inference, set the `device_map` to `auto` (accelerate library required):

## Training

The training was performed in 3 CPT stages<<<<<<<.
- **Parallel alignment**: the model was pretrained on parallel English and Slovene texts using a context window of 65536 tokens;
- **Base CPT**: the model was pretrained on a combination of Slovene, English, Croatian, Bosnian and Serbian corpora with a context window of 65536 tokens;
- **Long CPT**: the model was pretrained on a combination of high-quality Slovene, English, Croatian, Bosnian, and Serbian corpora with a context window of 131072 tokens.

### Infrastructure

The model was trained on the following HPC infrastructure:
- EuroHPC supercomputer [LEONARDO](https://www.hpc.cineca.it/systems/hardware/leonardo/): We managed to scale the training across 128 nodes on LEONARDO's booster partition. We used approximately **150k GPU** hours on LEONARDO for development of this model (including data preparation such as translation and web rewrite, and model training).
- Faculty's B200 node: With 8 B200 GPUs, our faculty's node represents a modern infrastructure for AI development. However, as we have only a single such node, the majority of the training was done elsewhere. In total, around **1000 GPU hours** were used on the B200 node.
- [NVIDIA DGX Cloud Lepton](https://developer.nvidia.com/blog/introducing-nvidia-dgx-cloud-lepton-a-unified-ai-platform-built-for-developers/): A unified AI platform that connects developers to tens of thousands of GPUs from a global network of cloud providers. It addresses a critical need: accelerating AI developer productivity by providing access to GPU capacity and AI services across the NVIDIA compute ecosystem. It integrates seamlessly with the NVIDIA software stack, enabling developers to build, train, and deploy AI applications quickly and Scale. We spent approximately **40k Lepton GPU hours**.

### Software

[NVIDIA NeMo Framework 2.0](https://github.com/NVIDIA-NeMo/NeMo) (container version [25.07](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/nemo?version=25.07));

### Training hyperparameters

In line with our commitment to transparency, open science, and the sharing of knowledge, we openly disclose all training hyperparameters used in developing this model. All training stages were performed with **bfloat16** precision and **Adam** optimizer.

| Stage | Model Parallelism | Data Parallelism | Batch Size | Micro Batch Size | LR Scheduler | Min LR | Max LR | Warmup Steps | Constant Steps | Epochs |
|-------|--------------------|------------------|------------|-------------------|--------------|--------|--------|---------------|----------------|--------|
|   Parallel alignment    | TP 8 | 64 | 128 | 1 | Cosine with warmup | 5e-7 | 5e-6 | 150 | 200 | 1 |
|   Base CPT    | TP 8  | 64 | Rampup: 128 (961 steps) -> 192 (600 steps) -> 256 | 1 | Cosine with warmup | 5e-7 | 5e-6 | 1000 | 1000 | 1 |
|   Long CPT    | TP 8  | 16 | 64 | 1 | Constant with warmup | / | 5e-6 | 500 | / | 1 |

## Data and benchmark information

We provide a mixture of datasets used during each of the training stages. **99 %** of the data was used as a training set, while the remaining percent was used as a validation set. The stats were computed after the initial documents were tokenized, split into units that fit into the context window, merged together using sequence packing and padded to full context window.

### Parallel alignment

| Corpus            | Number of tokens | Number of documents | Total percentage | Short description |
|-------------------|----------|-------------|------------------|------------------|
| DGT		| 804847616		| 12281	| 6.3 % | English, Slovene and Croatian texts extracted from [DGT corpus](https://joint-research-centre.ec.europa.eu/language-technology-resources/dgt-translation-memory_en). Cutoff date: 2025 Vol 5. |
| MaCoCu	| 430374912		| 6567	| 3.4 % | https://www.clarin.si/repository/xmlui/handle/11356/1813 |
| KAS		| 31391744		| 479	| 0.2 % | https://www.clarin.si/repository/xmlui/handle/11356/1449 |
| Wikipedia	| 11529093120	| 175920 | 90.1 % | English Wikipedia retrieved using [wikipedia_markdown](https://huggingface.co/datasets/zidsi/wikipedia_markdown). Translated into Slovene using [GaMS-9B-Translator](https://huggingface.co/GaMS-Beta/GaMS-9B-SFT-Translator-DPO) to create a parallel corpus. |
| **Total** | **12795707392** | **195247** | | |

### Base CPT

| Corpus            | Language   | Number of tokens | Number of documents | Total percentage | Short description |
|-------------------|------------|----------|-------------|------------------|------------------|
| nemotron_pretraining_code | English   | 1952120832 | 29787 | 1.9 % | Subsample of [Nemotron-Pretraining-Code-v1](https://huggingface.co/datasets/nvidia/Nemotron-Pretraining-Code-v1). Downloaded git-repositories from Nemotron-Code-Metadata |
| nemotron_math_4_plus | English | 2526937088 | 38558 | 2.5 % | Subsample of 4plus split from [Nemotron-CC-Math-v1](https://huggingface.co/datasets/nvidia/Nemotron-CC-Math-v1) |
| nemotron_math_3 | English | 1210908672 | 18477 | 1.2 % | Subsample of 3 split from [Nemotron-CC-Math-v1](https://huggingface.co/datasets/nvidia/Nemotron-CC-Math-v1) |
| nemotron_pretraining_sft | English | 3718316032 | 56737 | 3.7 % | Subsample of Nemotron-SFT-General split from [Nemotron-Pretraining-SFT-v1](https://huggingface.co/datasets/nvidia/Nemotron-Pretraining-SFT-v1) |
| nemotron_high_quality | English | 10479403008 | 159903 | 10.4 % | Subsample of High-Quality-Synthetic split from [Nemotron-CC-v2](https://huggingface.co/datasets/nvidia/Nemotron-CC-v2). Only the examples generated with Qwen3-30B-A3B were considered for selection. |
| nemotron_diverse_qa | English | 8631353344 | 131704 | 8.6 % | Subsample of DiverseQA split from [Nemotron-CC-v2](https://huggingface.co/datasets/nvidia/Nemotron-CC-v2). |
| finepdfs_bos | Bosnian | 4815912960 | 73485 | 4.8 % | Subsample of Bosnian corpus from [FinePDFS](https://huggingface.co/datasets/HuggingFaceFW/finepdfs ). |
| finepdfs_hrv | Croatian | 9541124096 | 145586 | 9.5 % | Subsample of Croatian corpus from [FinePDFS](https://huggingface.co/datasets/HuggingFaceFW/finepdfs ). |
| finepdfs_srp | Serbian | 8119844864 | 123899 | 8.0 % | Subsample of Serbian corpus from [FinePDFS](https://huggingface.co/datasets/HuggingFaceFW/finepdfs ). |
| finepdfs_slv | Slovenian | 5925044224 | 90409 | 5.9 % | Subsample of Slovene corpus from [FinePDFS](https://huggingface.co/datasets/HuggingFaceFW/finepdfs ). |
| trendi | Slovenian | 1737687040 | 26515 | 1.7 % | https://www.clarin.si/repository/xmlui/handle/11356/2064, Cutoff date: December 2023 |
| classla | Slovenian | 4256432128 | 64948 | 4.2 % | https://www.clarin.si/repository/xmlui/handle/11356/1882, 1 million randomly selected documents were rewritten using 27B Gemma 3 |
| sl_legal | Slovenian | 1697710080 | 25905 | 1.7 % | Combination of various Slovene legal data (Legal-Information system of Slovenia, Court practice, Uradni List RS) |
| sl_med | Slovenian | 1598095360 | 24385 | 1.6 % | Combination of crawled data, academic works and journals connected to medicine |
| metafida | Slovenian | 4591910912 | 70067 | 4.6 % | https://www.clarin.si/repository/xmlui/handle/11356/1775 The following subcorpora were removed: janes_tweet, janes_forum, janes_news, dgt15_sl, classlawiki_sl and tweet_sl |
| fineweb2 | Slovenian | 13890289664 | 211949 | 13.8 % | Slovene corpus from [FineWeb-2](https://huggingface.co/datasets/HuggingFaceFW/fineweb-2) |
| kas | Slovenian | 2726035456 | 41596 | 2.7 % | https://www.clarin.si/repository/xmlui/handle/11356/1448 |
| nuk_combined | Slovenian | 1213267968 | 18513 | 1.2 % | OCR-ed data (Marker, Nanonets, Llama 4 Maverick) from the national library of Slovenia. Mostly old newspapers, some books and scientific journals |
| nuk_doc | Slovenian | 11570774016 | 176556 | 11.5 % | OCR-ed data (Marker, Nanonets, Llama 4 Maverick) from the national library of Slovenia. Mostly old newspapers, some books and scientific journals |
| wikipedia_yugo | Slovenian, Croatian, Bosnian, Serbian | 673775616 | 10281 | 0.7 % | Combination of Slovene, Bosnian, Croatian and Serbian (converted to Latin) wikipedia. Retrieved using [wikipedia_markdown](https://huggingface.co/datasets/zidsi/wikipedia_markdown). Cutoff date: January 2025 |
| **Total** | | **100876943360** | **1539260** | | |

### Long 

| Corpus            | Language   | Number of tokens | Number of documents | Total percentage | Short description |
|-------------------|------------|----------|-------------|------------------|------------------|
| nemotron_math_4_plus | English | 1087373312 | 8296 | 5.4 % | Subsample of 4plus split from [Nemotron-CC-Math-v1](https://huggingface.co/datasets/nvidia/Nemotron-CC-Math-v1) |
| nemotron_pretraining_sft | English | 1231945728 | 9399 | 6.1 % | Subsample of Nemotron-SFT-General split from [Nemotron-Pretraining-SFT-v1](https://huggingface.co/datasets/nvidia/Nemotron-Pretraining-SFT-v1) |
| nemotron_high_quality | English | 2634285056 | 20098 | 13.1 % | https://huggingface.co/datasets/nvidia/Nemotron-CC-v2 | Subsample of High-Quality-Synthetic split from [Nemotron-CC-v2](https://huggingface.co/datasets/nvidia/Nemotron-CC-v2). Only the examples generated with Qwen3-30B-A3B were considered for selection. |
| nemotron_diverse_qa | English | 1237975040 | 9445 | 6.2 % | https://huggingface.co/datasets/nvidia/Nemotron-CC-v2 | Subsample of DiverseQA split from [Nemotron-CC-v2](https://huggingface.co/datasets/nvidia/Nemotron-CC-v2). |
| finepdfs_bos | Bosnian | 1614282752 | 12316 | 8.0 % | https://huggingface.co/datasets/HuggingFaceFW/finepdfs | Subsample of Bosnian corpus from [FinePDFS](https://huggingface.co/datasets/HuggingFaceFW/finepdfs ). |
| finepdfs_hrv | Croatian | 2385248256 | 18198 | 11.9 % | https://huggingface.co/datasets/HuggingFaceFW/finepdfs | Subsample of Croatian corpus from [FinePDFS](https://huggingface.co/datasets/HuggingFaceFW/finepdfs ). |
| finepdfs_srp | Serbian | 2074345472 | 15826 | 10.3 % | https://huggingface.co/datasets/HuggingFaceFW/finepdfs | Subsample of Serbian corpus from [FinePDFS](https://huggingface.co/datasets/HuggingFaceFW/finepdfs ). |
| finepdfs_slv | Slovenian | 1969618944 | 15027 | 9.8 % | https://huggingface.co/datasets/HuggingFaceFW/finepdfs | Subsample of Slovene corpus from [FinePDFS](https://huggingface.co/datasets/HuggingFaceFW/finepdfs ). |
| trendi | Slovenian | 610533376 | 4658 | 3.0 % | https://www.clarin.si/repository/xmlui/handle/11356/2064, Time window: January 2024 - July 2025 |
| kas_extension | Slovenian | 2256404480 | 17215 | 11.2 % | Final theses from the three Slovene Universities for years 2019-2024. The theses were crawled from University repositories and OCR-ed with LLama 4 Maverick. |
| math_sl | Slovenian | 1456078848 | 11109 | 7.2 % | Combination of 3 sources: translation of nemotron_math_4_plus (using [GaMS-9B-Translator](https://huggingface.co/GaMS-Beta/GaMS-9B-SFT-Translator-DPO)) and LLama 4 Maverick OCRs of 2 Slovene math/physics journals: Presek and Obzornik za matematiko in fiziko |
| nemotron_pretraining_sft_translated | Slovenian | 1553858560 | 11855 | 7.7 % | Translations of nemotron_pretraining_sft using [GaMS-9B-Translator](https://huggingface.co/GaMS-Beta/GaMS-9B-SFT-Translator-DPO) |
| **Total** | | **20111949824** | **1539260** | | |


## Usage and Limitations

These models have certain limitations that users should be aware of.

### Intended Usage

Open Large Language Models (LLMs) have a wide range of applications across
various industries and domains. The following list of potential uses is not
comprehensive. The purpose of this list is to provide contextual information
about the possible use-cases that the model creators considered as part of model
training and development.

* Content Creation and Communication
  * Text Generation: These models can be used to generate creative text formats
    such as poems, scripts, code, marketing copy, and email drafts.
  * Chatbots and Conversational AI: Power conversational interfaces for customer
    service, virtual assistants, or interactive applications.
  * Text Summarization: Generate concise summaries of a text corpus, research
    papers, or reports.
* Research and Education
  * Natural Language Processing (NLP) Research: These models can serve as a
    foundation for researchers to experiment with NLP techniques, develop
    algorithms, and contribute to the advancement of the field.
  * Language Learning Tools: Support interactive language learning experiences,
    aiding in grammar correction or providing writing practice.
  * Knowledge Exploration: Assist researchers in exploring large bodies of text
    by generating summaries or answering questions about specific topics.

### Limitations

* Training Data
  * The quality and diversity of the training data significantly influence the
    model's capabilities. Biases or gaps in the training data can lead to
    limitations in the model's responses.
  * The scope of the training dataset determines the subject areas the model can
    handle effectively.
* Context and Task Complexity
  * LLMs are better at tasks that can be framed with clear prompts and
    instructions. Open-ended or highly complex tasks might be challenging.
  * A model's performance can be influenced by the amount of context provided
    (longer context generally leads to better outputs, up to a certain point).
* Language Ambiguity and Nuance
  * Natural language is inherently complex. LLMs might struggle to grasp subtle
    nuances, sarcasm, or figurative language.
* Factual Accuracy
  * LLMs generate responses based on information they learned from their
    training datasets, but they are not knowledge bases. They may generate
    incorrect or outdated factual statements.
* Common Sense
  * LLMs rely on statistical patterns in language. They might lack the ability
    to apply common sense reasoning in certain situations.

### Ethical Considerations and Risks

The development of large language models (LLMs) raises several ethical concerns.
In creating an open model, we have carefully considered the following:

* Bias and Fairness
  * LLMs trained on large-scale, real-world text data can reflect socio-cultural
    biases embedded in the training material. These models underwent careful
    scrutiny, input data pre-processing described and posterior evaluations
    reported in this card.
* Misinformation and Misuse
  * LLMs can be misused to generate text that is false, misleading, or harmful.
  * Guidelines are provided for responsible use with the model, see the
    [Responsible Generative AI Toolkit][rai-toolkit].
* Transparency and Accountability:
  * This model card summarizes details on the models' architecture,
    capabilities, limitations, and evaluation processes.
  * A responsibly developed open model offers the opportunity to share
    innovation by making LLM technology accessible to developers and researchers
    across the AI ecosystem.

Risks identified and mitigations:

* Perpetuation of biases: It's encouraged to perform continuous monitoring
  (using evaluation metrics, human review) and the exploration of de-biasing
  techniques during model training, fine-tuning, and other use cases.
* Generation of harmful content: Mechanisms and guidelines for content safety
  are essential. Developers are encouraged to exercise caution and implement
  appropriate content safety safeguards based on their specific product policies
  and application use cases.
* Misuse for malicious purposes: Technical limitations and developer and
  end-user education can help mitigate against malicious applications of LLMs.
  Educational resources and reporting mechanisms for users to flag misuse are
  provided. Prohibited uses of Gemma models are outlined in the
  [Gemma Prohibited Use Policy][prohibited-use].
* Privacy violations: Models were trained on data filtered for removal of PII
  (Personally Identifiable Information). Developers are encouraged to adhere to
  privacy regulations with privacy-preserving techniques.

