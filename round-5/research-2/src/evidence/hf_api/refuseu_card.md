---
language:
- pl
- en
- cs
- sk
- sl
- lt
- lv
- de
- it
- fr
- es
- pt
multilinguality: multilingual
pretty_name: Multilingual Red-Teaming Preference + Evaluation
size_categories:
- 100K<n<1M
task_categories:
- text-generation
- text-classification
tags:
- safety
- red-teaming
- multilingual
- preference-dataset
- evaluation
configs:
- config_name: evaluation
  data_files:
  - split: eval
    path: evaluation/eval-*
- config_name: lang_cs
  data_files:
  - split: train
    path: lang_cs/train-*
  - split: test
    path: lang_cs/test-*
- config_name: lang_de
  data_files:
  - split: train
    path: lang_de/train-*
  - split: test
    path: lang_de/test-*
- config_name: lang_en
  data_files:
  - split: train
    path: lang_en/train-*
  - split: test
    path: lang_en/test-*
- config_name: lang_es
  data_files:
  - split: train
    path: lang_es/train-*
  - split: test
    path: lang_es/test-*
- config_name: lang_fr
  data_files:
  - split: train
    path: lang_fr/train-*
  - split: test
    path: lang_fr/test-*
- config_name: lang_it
  data_files:
  - split: train
    path: lang_it/train-*
  - split: test
    path: lang_it/test-*
- config_name: lang_lt
  data_files:
  - split: train
    path: lang_lt/train-*
  - split: test
    path: lang_lt/test-*
- config_name: lang_lv
  data_files:
  - split: train
    path: lang_lv/train-*
  - split: test
    path: lang_lv/test-*
- config_name: lang_pl
  data_files:
  - split: train
    path: lang_pl/train-*
  - split: test
    path: lang_pl/test-*
- config_name: lang_pt
  data_files:
  - split: train
    path: lang_pt/train-*
  - split: test
    path: lang_pt/test-*
- config_name: lang_sk
  data_files:
  - split: train
    path: lang_sk/train-*
  - split: test
    path: lang_sk/test-*
- config_name: lang_sl
  data_files:
  - split: train
    path: lang_sl/train-*
  - split: test
    path: lang_sl/test-*
- config_name: multilingual
  data_files:
  - split: train
    path: multilingual/train-*
  - split: test
    path: multilingual/test-*
dataset_info:
- config_name: evaluation
  features:
  - name: row_id
    dtype: int64
  - name: lang
    dtype: string
  - name: prompt
    dtype: string
  splits:
  - name: eval
    num_bytes: 5805282
    num_examples: 16800
  download_size: 3416852
  dataset_size: 5805282
- config_name: lang_cs
  features:
  - name: chosen
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: rejected
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: lang
    dtype: string
  - name: id
    dtype: string
  - name: row_id
    dtype: int64
  - name: category
    dtype: string
  splits:
  - name: train
    num_bytes: 12671899
    num_examples: 2748
  - name: test
    num_bytes: 654759
    num_examples: 141
  download_size: 5880244
  dataset_size: 13326658
- config_name: lang_de
  features:
  - name: chosen
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: rejected
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: lang
    dtype: string
  - name: id
    dtype: string
  - name: row_id
    dtype: int64
  - name: category
    dtype: string
  splits:
  - name: train
    num_bytes: 12135732
    num_examples: 2748
  - name: test
    num_bytes: 630927
    num_examples: 141
  download_size: 5373693
  dataset_size: 12766659
- config_name: lang_en
  features:
  - name: chosen
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: rejected
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: lang
    dtype: string
  - name: id
    dtype: string
  - name: row_id
    dtype: int64
  - name: category
    dtype: string
  splits:
  - name: train
    num_bytes: 13198313
    num_examples: 2748
  - name: test
    num_bytes: 663494
    num_examples: 141
  download_size: 6325215
  dataset_size: 13861807
- config_name: lang_es
  features:
  - name: chosen
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: rejected
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: lang
    dtype: string
  - name: id
    dtype: string
  - name: row_id
    dtype: int64
  - name: category
    dtype: string
  splits:
  - name: train
    num_bytes: 14577097
    num_examples: 2748
  - name: test
    num_bytes: 731766
    num_examples: 141
  download_size: 6323679
  dataset_size: 15308863
- config_name: lang_fr
  features:
  - name: chosen
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: rejected
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: lang
    dtype: string
  - name: id
    dtype: string
  - name: row_id
    dtype: int64
  - name: category
    dtype: string
  splits:
  - name: train
    num_bytes: 14429903
    num_examples: 2748
  - name: test
    num_bytes: 742599
    num_examples: 141
  download_size: 6196775
  dataset_size: 15172502
- config_name: lang_it
  features:
  - name: chosen
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: rejected
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: lang
    dtype: string
  - name: id
    dtype: string
  - name: row_id
    dtype: int64
  - name: category
    dtype: string
  splits:
  - name: train
    num_bytes: 14361447
    num_examples: 2748
  - name: test
    num_bytes: 723617
    num_examples: 141
  download_size: 6390570
  dataset_size: 15085064
- config_name: lang_lt
  features:
  - name: chosen
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: rejected
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: lang
    dtype: string
  - name: id
    dtype: string
  - name: row_id
    dtype: int64
  - name: category
    dtype: string
  splits:
  - name: train
    num_bytes: 10120891
    num_examples: 2748
  - name: test
    num_bytes: 532227
    num_examples: 141
  download_size: 4593588
  dataset_size: 10653118
- config_name: lang_lv
  features:
  - name: chosen
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: rejected
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: lang
    dtype: string
  - name: id
    dtype: string
  - name: row_id
    dtype: int64
  - name: category
    dtype: string
  splits:
  - name: train
    num_bytes: 12361380
    num_examples: 2748
  - name: test
    num_bytes: 636505
    num_examples: 141
  download_size: 5017826
  dataset_size: 12997885
- config_name: lang_pl
  features:
  - name: chosen
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: rejected
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: lang
    dtype: string
  - name: id
    dtype: string
  - name: row_id
    dtype: int64
  - name: category
    dtype: string
  splits:
  - name: train
    num_bytes: 11914709
    num_examples: 2748
  - name: test
    num_bytes: 610815
    num_examples: 141
  download_size: 5537258
  dataset_size: 12525524
- config_name: lang_pt
  features:
  - name: chosen
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: rejected
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: lang
    dtype: string
  - name: id
    dtype: string
  - name: row_id
    dtype: int64
  - name: category
    dtype: string
  splits:
  - name: train
    num_bytes: 13758159
    num_examples: 2748
  - name: test
    num_bytes: 710808
    num_examples: 141
  download_size: 6030431
  dataset_size: 14468967
- config_name: lang_sk
  features:
  - name: chosen
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: rejected
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: lang
    dtype: string
  - name: id
    dtype: string
  - name: row_id
    dtype: int64
  - name: category
    dtype: string
  splits:
  - name: train
    num_bytes: 11692081
    num_examples: 2748
  - name: test
    num_bytes: 598680
    num_examples: 141
  download_size: 5256586
  dataset_size: 12290761
- config_name: lang_sl
  features:
  - name: chosen
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: rejected
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: lang
    dtype: string
  - name: id
    dtype: string
  - name: row_id
    dtype: int64
  - name: category
    dtype: string
  splits:
  - name: train
    num_bytes: 10083361
    num_examples: 2748
  - name: test
    num_bytes: 515802
    num_examples: 141
  download_size: 4622500
  dataset_size: 10599163
- config_name: multilingual
  features:
  - name: chosen
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: rejected
    list:
    - name: content
      dtype: string
    - name: role
      dtype: string
  - name: lang
    dtype: string
  - name: id
    dtype: string
  - name: row_id
    dtype: int64
  - name: category
    dtype: string
  splits:
  - name: train
    num_bytes: 151304972
    num_examples: 32976
  - name: test
    num_bytes: 7751999
    num_examples: 1692
  download_size: 87562356
  dataset_size: 159056971
license: llama3.1
---

# Multilingual Red-Teaming Preference + Evaluation

This dataset contains multilingual red-teaming prompts and preference pairs for safety research, plus a separate multilingual evaluation prompt set.

## Dataset Structure

The repository is organized into multiple dataset configs:

- multilingual
  - train: full preference training split
  - test: full preference test split
- lang_pl, lang_en, lang_cs, lang_sk, lang_sl, lang_lt, lang_lv, lang_de, lang_it, lang_fr, lang_es, lang_pt
  - train: language-specific preference training split
  - test: language-specific preference test split
- evaluation
  - eval: multilingual evaluation prompts



## Data Fields

### Config multilingual and lang_*

Each row is a preference sample with fields:

- chosen: list of chat turns (preferred response)
- rejected: list of chat turns (non-preferred response)
- lang: language code
- id: sample id
- row_id: original row id
- category: category label

### Config evaluation

Each row is one prompt instance with fields:

- row_id: source CSV row index
- lang: language code
- prompt: evaluation prompt text



## Intended Use

This dataset is intended for:

- safety alignment and preference learning research
- multilingual refusal and robustness benchmarking
- model evaluation under potentially harmful prompt distributions

## Safety Notice

The dataset contains harmful, abusive, and policy-violating user prompts, and some rejected assistant responses may include unsafe content patterns. Handle with care and use only in controlled research environments.

## Ethical Considerations

- Do not use this dataset to build systems that facilitate abuse.
- Apply strict filtering and governance for downstream usage.
- Ensure compliance with local legal and institutional requirements.

## License

Specify the license used for this dataset before public release.

If unsure, keep the repository private until licensing and data governance are fully validated.

## Quick Start

```python
from datasets import load_dataset

repo_id = "NASK-PIB/RefusEU"

# Full multilingual preference dataset
train_ds = load_dataset(repo_id, "multilingual", split="train")
test_ds = load_dataset(repo_id, "multilingual", split="test")

# Language-specific subset
pl_train = load_dataset(repo_id, "lang_pl", split="train")
en_test = load_dataset(repo_id, "lang_en", split="test")

# Evaluation prompts
eval_ds = load_dataset(repo_id, "evaluation", split="eval")
```



## 📚 Citation
If you use the dataset, please cite the following paper:

```
@inproceedings{krasnodebska2026refuseu,
  author    = {Krasnodębska, Aleksandra and Kusa, Wojciech and Lipani, Aldo},
  title     = {{Multilingual Refusal Alignment for Safer Large Language Models}},
  booktitle = {Findings of the Association for Computational Linguistics: ACL 2026},
  year      = {2026},
  address   = {San Diego, California, United States},
  publisher = {Association for Computational Linguistics}
}
```



