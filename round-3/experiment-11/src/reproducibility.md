# Reproducibility

Environment: `uv sync` (Python 3.12; pins in `pyproject.toml` / `uv.lock`). Seed 20260925. One NVIDIA L4 (23 GB).

Full pipeline (resumable; every stage skips work already on disk):
```bash
uv run method.py --stages all      # preflight -> items -> calibrate -> freeze -> GPU gen -> judges -> analysis
uv run method.py --stages analysis # rebuild table -> analysis -> audit -> report -> figures -> method_out.json
.venv/bin/python -m pytest -c pytest.ini tests/   # 10/10 T0 unit checks
```

Provenance & pins:
- Models: `google/gemma-3-12b-it@96b6f1ec`, `cjvt/GaMS3-12B-Instruct@1d0b27af`, `facebook/nllb-200-distilled-1.3B`,
  judges `Qwen/Qwen3-14B@40c06982`, `mistralai/Mistral-Small-24B-Instruct-2501@9527884b`; public checkpoint
  `p-e-w/gemma-3-12b-it-heretic@e037e6e1`. Edit adapter read read-only from iter-1 exp4 `selected_adapter/`.
- Data provenance and seeded subset ids with sha256: `data/split_manifest_iter3.json`, `data/data_hashes.json`.
- Frozen protocol: `protocol.yaml` + `protocol.sha256`, git-committed (68f3f73) BEFORE the first FINAL row.
  Amendments: `results/protocol_amendments.json` (AM1-AM4), each committed before the generation it affects.

Recomputation: every headline number is re-derived by an independent pandas path in `src/rederive.py`
(`results/audit.json`: 25/25 checks < 1e-6; model-swap / language-swap / shuffled-judge placebos null).

Restoring removed files: see README.md "Restoring removed files" (`.venv` -> `uv sync`; `public_ckpts/` -> `hf download`).
