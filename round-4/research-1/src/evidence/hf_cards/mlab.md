---
license: gemma
library_name: transformers
pipeline_tag: image-text-to-text
base_model: google/gemma-3-12b-it
---

# 💎 Gemma 3 12B IT Abliterated

![image/png](https://cdn-uploads.huggingface.co/production/uploads/61b8e2ba285851687028d395/WjFfc8hhj20r5XK07Yny9.png)
<center><a href="https://huggingface.co/mlabonne/gemma-3-1b-it-abliterated">Gemma 3 1B Abliterated</a> • <a href="https://huggingface.co/mlabonne/gemma-3-4b-it-abliterated">Gemma 3 4B Abliterated</a> • <a href="https://huggingface.co/mlabonne/gemma-3-27b-it-abliterated">Gemma 3 27B Abliterated</a></center>

This is an uncensored version of [google/gemma-3-12b-it](https://huggingface.co/google/gemma-3-12b-it) created with a new abliteration technique.
See [this article](https://huggingface.co/blog/mlabonne/abliteration) to know more about abliteration.

I was playing with model weights and noticed that Gemma 3 was much more resilient to abliteration than other models like Qwen 2.5. 
I experimented with a few recipes to remove refusals while preserving most of the model capabilities.

Note that this is fairly experimental, so it might not turn out as well as expected. I saw some garbled text from time to time (e.g., "It' my" instead of "It's my").

I recommend using these generation parameters: `temperature=1.0`, `top_k=64`, `top_p=0.95`.

## ⚡️ Quantization

* **GGUF**: https://huggingface.co/mlabonne/gemma-3-12b-it-abliterated-GGUF

## ✂️ Layerwise abliteration

![image/png](https://cdn-uploads.huggingface.co/production/uploads/61b8e2ba285851687028d395/gXI5pTMfoX7uPUL-YJBXa.png)

In the original technique, a refusal direction is computed by comparing the residual streams between target (harmful) and baseline (harmless) samples.

Here, the model was abliterated by computing a refusal direction based on hidden states (inspired by [Sumandora's repo](https://github.com/Sumandora/remove-refusals-with-transformers/)) for most layers (layer 3 to 45), independently.
This is combined with a refusal weight of 0.6 to upscale the importance of this refusal direction in each layer.

This created a very high acceptance rate (>90%) and still produced coherent outputs.