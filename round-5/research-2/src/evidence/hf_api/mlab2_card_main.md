---
license: gemma
library_name: transformers
pipeline_tag: image-text-to-text
base_model: google/gemma-3-12b-it
---

# 💎 Gemma 3 12B IT Abliterated

![image/png](https://cdn-uploads.huggingface.co/production/uploads/61b8e2ba285851687028d395/NjwzenHhKsuPRMPYxyN4p.png)
<center>Gemma 3 Abliterated <a href="https://huggingface.co/mlabonne/gemma-3-1b-it-abliterated-v2">1B</a> • <a href="https://huggingface.co/mlabonne/gemma-3-4b-it-abliterated-v2">4B</a> • <a href="https://huggingface.co/mlabonne/gemma-3-12b-it-abliterated-v2">12B</a> • <a href="https://huggingface.co/mlabonne/gemma-3-27b-it-abliterated-v2">27B</a></center>

This is an uncensored version of [google/gemma-3-12b-it](https://huggingface.co/google/gemma-3-12b-it) created with a new abliteration technique.
See [this article](https://huggingface.co/blog/mlabonne/abliteration) to know more about abliteration.

This is a new, improved version that targets refusals with enhanced accuracy.

I recommend using these generation parameters: `temperature=1.0`, `top_k=64`, `top_p=0.95`.

## ⚡️ Quantization

* **QAT**: https://huggingface.co/mlabonne/gemma-3-12b-it-qat-abliterated
* **GGUF**: https://huggingface.co/mlabonne/gemma-3-12b-it-abliterated-v2-GGUF

## ✂️ Abliteration

![image/png](https://cdn-uploads.huggingface.co/production/uploads/61b8e2ba285851687028d395/v78FqzqE-LMBIRSRJXegf.png)

The refusal direction is computed by comparing the residual streams between target (harmful) and baseline (harmless) samples. 
The hidden states of target modules (e.g., o_proj) are orthogonalized to subtract this refusal direction with a given weight factor. 
These weight factors follow a normal distribution with a certain spread and peak layer. 
Modules can be iteratively orthogonalized in batches, or the refusal direction can be accumulated to save memory.

Finally, I used a hybrid evaluation with a dedicated test set to calculate the acceptance rate. This uses both a dictionary approach and [NousResearch/Minos-v1](https://huggingface.co/NousResearch/Minos-v1). 
The goal is to obtain an acceptance rate >90% and still produce coherent outputs.