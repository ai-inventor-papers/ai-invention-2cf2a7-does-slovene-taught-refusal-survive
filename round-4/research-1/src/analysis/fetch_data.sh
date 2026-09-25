#!/bin/bash
# Re-download the benchmark files used by overlap.py (pinned revisions where the host supports it).
set -e; D="$(cd "$(dirname "$0")" && pwd)/data"; mkdir -p "$D"
M=01cead01398926d81f7c52bdb790ee8cf77ebba7   # mlabonne/harmful_behaviors
for s in train test; do curl -sfL -o "$D/mlab_harmful_$s.parquet" "https://huggingface.co/datasets/mlabonne/harmful_behaviors/resolve/$M/data/$s-00000-of-00001.parquet"; done
curl -sfL -o "$D/advbench.csv" https://raw.githubusercontent.com/llm-attacks/llm-attacks/main/data/advbench/harmful_behaviors.csv
J=886acc352a31533ffbcf4ef22c744658688086fc     # JailbreakBench/JBB-Behaviors
curl -sfL -o "$D/jbb_harmful.csv" "https://huggingface.co/datasets/JailbreakBench/JBB-Behaviors/resolve/$J/data/harmful-behaviors.csv"
curl -sfL -o "$D/jbb_benign.csv" "https://huggingface.co/datasets/JailbreakBench/JBB-Behaviors/resolve/$J/data/benign-behaviors.csv"
curl -sfL -o "$D/strongreject.csv" https://raw.githubusercontent.com/alexandrasouly/strongreject/main/strongreject_dataset/strongreject_dataset.csv
curl -sfL -o "$D/harmbench_all.csv" https://raw.githubusercontent.com/centerforaisafety/HarmBench/main/data/behavior_datasets/harmbench_behaviors_text_all.csv
R=5523ce30b9b6af59e95ade9c610b8b974412a6bb     # NASK-PIB/RefusEU
curl -sfL -o "$D/refuseu_eval.parquet" "https://huggingface.co/datasets/NASK-PIB/RefusEU/resolve/$R/evaluation/eval-00000-of-00001.parquet"
echo done
