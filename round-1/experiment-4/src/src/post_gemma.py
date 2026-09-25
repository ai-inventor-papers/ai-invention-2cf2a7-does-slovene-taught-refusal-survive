#!/usr/bin/env python3
"""Post-chain GPU step for Gemma-3-12B-IT only (one model load). Gemma's main run (src/run_model.py) was launched before
two amendments were coded, so this re-creates, with the SAME functions GaMS runs in-process:
  (1) ALT-4 rank-k ablation, variant 'projected' (the plan's raw Arditi variant destroyed Gemma: KL 20-53 nats;
      kept as results/gemma_it/rank_k_raw*),
  (2) Mechanistic Question C (run_model.run_mech_c).
Usage: .venv/bin/python src/post_gemma.py
"""
import sys
from pathlib import Path

sys.argv = [str(Path(__file__).parent / "run_model.py"), "--model", "gemma_it"]
import run_model as RM  # noqa: E402
from common import SPLITS, read_jsonl  # noqa: E402
import probe as P  # noqa: E402


@RM.logger.catch(reraise=True)
def main():
    settings = RM.load_settings(RM.write_config_toml())
    model = RM.Model(settings)
    tok = model.tokenizer
    settings.response_prefix = ""  # Gemma main run found no common response prefix (checks.json)
    lex = RM.Lexicon(settings.model_extra["scorer"]["KeywordRate"]["keyword_markers"])
    s400 = read_jsonl(SPLITS / "score400.jsonl")
    construct = read_jsonl(SPLITS / "construct.jsonl")
    spare = read_jsonl(SPLITS / "kl_spare.jsonl")
    o1 = read_jsonl(RM.OUT / "orig_score400.jsonl")
    rp = lambda users: P.render(tok, users, settings.response_prefix)  # noqa: E731
    RM.run_rank_k(model, tok, settings, lex, s400, o1, construct, spare, rp, variant="projected")
    RM.run_mech_c(model, settings, construct)
    RM.logger.info("post_gemma done")


if __name__ == "__main__":
    main()
