"""LLM client for the synthesis layer.

Defaults to a local Ollama model (no API key, no network egress) so the
pipeline runs out of the box. If ANTHROPIC_API_KEY is set in the environment,
uses the Claude API instead for higher-quality synthesis -- same call
signature either way, so callers don't need to know which backend answered.
"""

from __future__ import annotations

import os

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.2:latest"
ANTHROPIC_MODEL = "claude-opus-4-8"


def chat(system: str, user: str) -> str:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _chat_anthropic(system, user)
    return _chat_ollama(system, user)


def _chat_anthropic(system: str, user: str) -> str:
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return next(block.text for block in response.content if block.type == "text")


def _chat_ollama(system: str, user: str) -> str:
    import httpx

    response = httpx.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        },
        timeout=180.0,
    )
    response.raise_for_status()
    return response.json()["message"]["content"]
