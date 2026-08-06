"""Thin OpenAI client with deterministic fallback for offline/eval."""

from __future__ import annotations

import json
from typing import Any

from src.config import openai_config
from src.rbac.sanitize import sanitize_untrusted_text


class LLMUnavailable(Exception):
    pass


def llm_available() -> bool:
    cfg = openai_config()
    key = cfg.get("api_key") or ""
    if not key:
        return False
    placeholders = ("sk-your-key", "xai-your-key", "gsk-your-key", "your-key-here")
    return not any(p in key for p in placeholders)


def chat(system: str, user: str, *, temperature: float | None = None) -> str:
    if not llm_available():
        raise LLMUnavailable(
            "No LLM API key set (XAI_API_KEY or OPENAI_API_KEY). "
            "Put it in .env — deterministic path will be used by callers."
        )
    from openai import OpenAI

    cfg = openai_config()
    kwargs = {"api_key": cfg["api_key"]}
    if cfg.get("base_url"):
        kwargs["base_url"] = cfg["base_url"]
    client = OpenAI(**kwargs)
    from src.config import load_settings

    settings = load_settings()["llm"]
    resp = client.chat.completions.create(
        model=cfg["model"],
        temperature=settings["temperature"] if temperature is None else temperature,
        max_tokens=settings["max_tokens"],
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


def safe_json_chat(system: str, user: str) -> dict[str, Any]:
    raw = chat(system + "\nRespond with valid JSON only.", user, temperature=0)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


def wrap_untrusted(label: str, text: str) -> str:
    return f"{label}: {sanitize_untrusted_text(text)}"