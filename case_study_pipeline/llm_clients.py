"""
Thin wrappers around the Anthropic and OpenAI APIs for the case study pipeline.

API keys are loaded from `.env` (ANTHROPIC_API_KEY, OPENAI_API_KEY) via
python-dotenv, matching the pattern already used in rag/pipeline.py.

"No memory" note (Check 2):
The OpenAI Chat Completions API is stateless by default — each call only sees the
messages you pass in that request. `query_openai()` here only ever sends a single
system + user message and never passes prior assistant turns, a
`previous_response_id`, or any stored profile/preferences. So as long as Check 2 is
made as its own call (not appending to the Check 1 conversation), it is naturally
"memory off". There is nothing to disable in the API itself — see
https://help.openai.com/en/articles/8590148-memory-faq for how this maps to the
ChatGPT web app's per-chat Memory toggle (which only applies to the consumer app,
not the API).
"""

from __future__ import annotations

import os

import anthropic
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DEFAULT_CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
DEFAULT_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")

DEFAULT_MAX_TOKENS = 8000


def _anthropic_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Add it to rfr-rag/.env"
        )
    return anthropic.Anthropic(api_key=api_key)


def _openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY not set. Add it to rfr-rag/.env"
        )
    return OpenAI(api_key=api_key)


def query_claude(
    prompt: str,
    model: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    system: str | None = None,
) -> str:
    """Send a single-turn prompt to Claude and return the text response.

    Uses streaming so that long generations (large max_tokens) don't trip the
    SDK's non-streaming 10-minute guard, and so full-length case-study documents
    are not truncated.
    """
    client = _anthropic_client()
    kwargs = {
        "model": model or DEFAULT_CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system

    parts: list[str] = []
    with client.messages.stream(**kwargs) as stream:
        for text in stream.text_stream:
            parts.append(text)
    return "".join(parts).strip()


def query_openai(
    prompt: str,
    model: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    system: str | None = None,
) -> str:
    """
    Send a single, standalone (no conversation history) prompt to ChatGPT and
    return the text response. Each call is independent -> "memory off" by
    construction (see module docstring).
    """
    client = _openai_client()
    model = model or DEFAULT_OPENAI_MODEL

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
        )
    except Exception as exc:  # some newer models reject `max_tokens`
        if "max_tokens" in str(exc) and "max_completion_tokens" in str(exc):
            response = client.chat.completions.create(
                model=model,
                max_completion_tokens=max_tokens,
                messages=messages,
            )
        else:
            raise

    return response.choices[0].message.content.strip()
