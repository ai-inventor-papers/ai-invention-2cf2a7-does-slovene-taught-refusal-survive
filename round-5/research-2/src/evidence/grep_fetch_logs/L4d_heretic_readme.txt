# 2026-09-25T00:43:42Z https://raw.githubusercontent.com/p-e-w/heretic/master/README.md :: gemma-3-12b|KL divergence|mlabonne|huihui
warning: The `fitz` API is deprecated and will be removed in future. Use `import pymupdf` instead.
URL: https://raw.githubusercontent.com/p-e-w/heretic/master/README.md
Type: HTML
Pattern: gemma-3-12b|KL divergence|mlabonne|huihui (22 matches in 17147 chars)

--- Content ---

1519:...)), with a TPE-based parameter optimizer powered by [Optuna](https://optuna.org/). This approach enables Heretic to work **completely automatically.** Heretic finds high-quality abliteration parameters by co-minimizing the number of refusals and the KL divergence from the original model. This results in a decensored model that retains as much of the original model's intelligence as possible. Using Heretic does not require an understanding of transformer internals. In fact, anyone who knows how to run a comma...
--
2307:...are not yet supported out of the box.    Running unsupervised with the default configuration, Heretic can produce decensored models that rival the quality of abliterations created manually by human experts: | Model | Refusals for "harmful" prompts | KL divergence from original model for "harmless" prompts | | :--- | ---: | ---: | | [google/gemma-3-12b-it](https://huggingface.co/google/gemma-3-12b-it) (original) | 97/100 | 0 *(by definition)* | | [mlabonne/gemma-3-12b-it-abliterated-v2](https://huggingface.co/mlabonne/gemma-3-12b-it-abliterated-v2) | 3/100 | 1.04 | | [huihui-ai/gemma-3-12b-it-abliterated](https://huggingface.co/huihui-ai/gemma-3-12b-it-abliterated) | 3/100 | 0.45 | | **[p-e-w/gemma-3-12b-it-heretic](https://huggingface.co/p-e-w/gemma-3-12b-it-heretic) (ours)** | **3/100** | **0.16** | The Heretic version, generated without any human effort, achieves the same level of refusal su...
--
[10 more matches not shown]
