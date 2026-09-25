#!/usr/bin/env python3
"""Step 1: download every source dataset at a pinned revision into temp/datasets/ and write provenance.json.
All sources are public HF dataset repos (no gated ones); GaMS-Instruct-SAFE 0.5 is copied read-only from Stage-0."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download
from loguru import logger

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "temp/datasets"
RUN = ROOT.parents[3]  # .../run_FVi3e3O9CH5I
S0 = RUN / "iter_2/gen_hypo/claude_agent/stage0"
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add(ROOT / "logs/s1_download.log", rotation="30 MB", level="DEBUG")

# repo -> (pinned revision, [files], licence note)
SOURCES = {
    "NASK-PIB/RefusEU": ("5523ce30b9b6af59e95ade9c610b8b974412a6bb",
                         ["evaluation/eval-00000-of-00001.parquet", "lang_en/train-00000-of-00001.parquet",
                          "lang_en/test-00000-of-00001.parquet", "lang_sl/train-00000-of-00001.parquet",
                          "lang_sl/test-00000-of-00001.parquet", "README.md"],
                         "card tag llama3.1; licence text 'to be specified' on the card -> FLAG (research use only)"),
    "cjvt/GaMS-Nemotron-Chat": ("0eab0b3cfcaaedf3958fe08ab1a7cd09302d65d7",
                                ["data/train-00000-of-00001.parquet", "README.md"], "see card (recorded in provenance.json)"),
    "Paul/XSTest": ("f600c994b256f12867dfa5b3eb3d545a3e62f8b5", ["xstest_prompts.csv", "README.md"], "CC-BY-4.0"),
    "natolambert/xstest-v2-copy": ("b71afe2a6d10e5a6254ea8bcb006c48b095a15d5",
                                   ["data/prompts-00000-of-00001.parquet"], "CC-BY-4.0 (fallback copy of XSTest v2)"),
    "bench-llm/or-bench": ("e36d8b80e81837c8a8f264bbb2a49f1b32c7e272",
                           ["or-bench-hard-1k.csv", "or-bench-toxic.csv", "README.md"], "CC-BY-4.0"),
    "OpenAssistant/oasst2": ("179dd21fc55192153d94adb0e0ce8f69e222bf75",
                             ["data/train-00000-of-00001-88ba0162028a73fc.parquet",
                              "data/validation-00000-of-00001-1deeef95c3248fe0.parquet", "README.md"], "Apache-2.0"),
    # extra reference sets (context / possible future use; not in data_out)
    "DAMO-NLP-SG/MultiJail": ("93d65c778925d55973b9ff30c7bccc8545494eb6", ["MultiJail.csv"], "MIT"),
    "LibrAI/do-not-answer": ("74e74f2e4507ef256fe536f78a776f4a1ff67955",
                             ["data/train-00000-of-00001-6ba0076b818accff.parquet"], "Apache-2.0"),
    "JailbreakBench/JBB-Behaviors": ("886acc352a31533ffbcf4ef22c744658688086fc",
                                     ["data/harmful-behaviors.csv", "data/benign-behaviors.csv"], "MIT"),
    "nvidia/Aegis-AI-Content-Safety-Dataset-2.0": ("d86bb8bedff51d25ac834ab7838f1cc61acb7a2c", ["test.json"], "CC-BY-4.0"),
    "CohereLabs/aya_redteaming": ("5a16fee03c19d681b4f3527b6a750e1ed4d434c7",
                                  ["aya_eng.jsonl", "aya_srp.jsonl"], "Apache-2.0"),
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


@logger.catch(reraise=True)
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    api = HfApi()
    prov = {}
    for repo, (rev, files, lic) in SOURCES.items():
        info = api.dataset_info(repo)
        head = info.sha
        card_lic = [t for t in (info.tags or []) if t.startswith("license:")]
        ent = {"revision_pinned": rev, "head_at_download": head, "head_matches_pin": head == rev,
               "card_license_tags": card_lic, "license_note": lic, "downloads_30d": info.downloads, "files": {}}
        for fn in files:
            p = Path(hf_hub_download(repo, fn, repo_type="dataset", revision=rev,
                                     local_dir=str(OUT / repo.replace("/", "__"))))
            ent["files"][fn] = {"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size, "sha256": sha256(p)}
            logger.info(f"{repo}:{fn} -> {p.stat().st_size/1e6:.1f} MB")
        prov[repo] = ent
    # GaMS-Instruct-SAFE 0.5 (CLARIN.SI 11356/2218, CC BY-SA 4.0) from the Stage-0 copy
    src = S0 / "safe05/GaMS-Instruct-SAFE_0.5/GaMS-Instruct-SAFE_0.5.json"
    dst = OUT / "GaMS-Instruct-SAFE_0.5.json"
    shutil.copy(src, dst)
    prov["CLARIN.SI/GaMS-Instruct-SAFE_0.5"] = {"source": "http://hdl.handle.net/11356/2218", "copied_from": str(src),
                                                "license_note": "CC BY-SA 4.0", "sha256": sha256(dst),
                                                "n_rows": len(json.loads(dst.read_text()))}
    (ROOT / "outputs").mkdir(exist_ok=True)
    (ROOT / "outputs/provenance.json").write_text(json.dumps(prov, indent=1))
    logger.info("provenance written")


if __name__ == "__main__":
    main()
