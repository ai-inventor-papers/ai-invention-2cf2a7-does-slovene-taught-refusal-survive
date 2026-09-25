#!/usr/bin/env bash
# Restore the files this repository does not ship (see .aii/manifest.yaml and README "Restoring removed files").
# Nothing here is needed to read the results: every number lives in results/, READOUT_v2.md and labels/.
# These are only needed to RE-RUN the pipeline.
set -euo pipefail
cd "$(dirname "$0")"

echo "== 1/3 python environment =="
if [ ! -x .venv/bin/python ]; then
  uv venv .venv --python=3.12
  uv pip install --python .venv/bin/python \
    pandas==3.0.6 pyarrow==25.0.1 numpy==2.5.3 scipy==1.18.1 statsmodels==0.15.0 scikit-learn==1.9.1 \
    aiohttp==3.14.3 sacrebleu==2.6.0 transformers==4.57.6 torch==2.14.0 sentencepiece==0.2.2 \
    loguru==0.7.3 PyYAML==6.0.3 protobuf==7.36.2 matplotlib==3.11.2 tenacity==9.1.4 psutil==7.2.2
else
  echo "   .venv already present, skipping"
fi

echo "== 2/3 exp9's distilled J1 judge (work/j1_model/, ~1.1 GB) =="
# Reassembled from the exp9 artifact's judge_model/mdeberta_gemini_distill/model_parts/ shards, which are published
# with that artifact. The reassembled checkpoint's sha256 is checked against exp9's own manifest.
# Only needed to REGENERATE work/ttj_j1_labels.jsonl; that file is shipped, so the translate-then-judge arm
# reproduces without this step.
if [ -f work/j1_model/model.safetensors ]; then
  echo "   already present, skipping"
else
  (cd src && ../.venv/bin/python -c "import ttj_judge_j1 as t; print(t.ensure_model())")
fi

echo "== 3/3 NLLB translation weights (only needed to redo src/nllb_ttj.py) =="
# They live in the shared HuggingFace cache pointed at by HF_HOME / HF_HUB_CACHE, outside this folder.
# The translations themselves are shipped in work/ttj_translations.jsonl, so this is optional.
echo "   run: huggingface-cli download facebook/nllb-200-distilled-1.3B"

echo "done."
