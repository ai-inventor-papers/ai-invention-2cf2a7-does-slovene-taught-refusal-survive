---
license: gemma
library_name: transformers
pipeline_tag: image-text-to-text
base_model: google/gemma-3-12b-it-qat-q4_0-unquantized
---

# 💎 Gemma 3 12B IT QAT Abliterated

![image/png](https://cdn-uploads.huggingface.co/production/uploads/61b8e2ba285851687028d395/NjwzenHhKsuPRMPYxyN4p.png)
<center>Gemma 3 QAT Abliterated <a href="https://huggingface.co/mlabonne/gemma-3-1b-it-qat-abliterated">1B</a> • <a href="https://huggingface.co/mlabonne/gemma-3-4b-it-qat-abliterated">4B</a> • <a href="https://huggingface.co/mlabonne/gemma-3-12b-it-qat-abliterated">12B</a> • <a href="https://huggingface.co/mlabonne/gemma-3-27b-it-qat-abliterated">27B</a></center>

This is an uncensored version of [google/gemma-3-12b-it-qat-q4_0-unquantized](https://huggingface.co/google/gemma-3-12b-it-qat-q4_0-unquantized) created with a new abliteration technique.
See [this article](https://huggingface.co/blog/mlabonne/abliteration) to know more about abliteration.

This is a new, improved version that targets refusals with enhanced accuracy.

I recommend using these generation parameters: `temperature=1.0`, `top_k=64`, `top_p=0.95`.

## ✂️ Abliteration

![image/png](https://cdn-uploads.huggingface.co/production/uploads/61b8e2ba285851687028d395/WgrnFKv6HM2CiOxgklv3R.png)

The refusal direction is computed by comparing the residual streams between target (harmful) and baseline (harmless) samples. 
The hidden states of target modules (e.g., o_proj) are orthogonalized to subtract this refusal direction with a given weight factor. 
These weight factors follow a normal distribution with a certain spread and peak layer. 
Modules can be iteratively orthogonalized in batches, or the refusal direction can be accumulated to save memory.

Finally, I used a hybrid evaluation with a dedicated test set to calculate the acceptance rate. This uses both a dictionary approach and [NousResearch/Minos-v1](https://huggingface.co/NousResearch/Minos-v1). 
The goal is to obtain an acceptance rate >90% and still produce coherent outputs.