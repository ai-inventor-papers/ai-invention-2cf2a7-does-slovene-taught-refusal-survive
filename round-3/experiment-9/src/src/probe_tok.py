"""Torch-free rendering/tokenisation identical to probe.render + probe.encode (used by the vLLM env)."""
from __future__ import annotations


def render(tok, users: list[str]) -> list[str]:
    return tok.apply_chat_template([[{"role": "user", "content": u}] for u in users], add_generation_prompt=True,
                                   tokenize=False)


def encode_users(tok, users: list[str]) -> list[list[int]]:
    return [tok(t, return_token_type_ids=False)["input_ids"] for t in render(tok, users)]
