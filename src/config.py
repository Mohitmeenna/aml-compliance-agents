from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
import os

from src.paths import CONFIG_DIR, ROOT


load_dotenv(ROOT / ".env")


@lru_cache(maxsize=1)
def load_roles() -> dict[str, Any]:
    with open(CONFIG_DIR / "roles.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def load_settings() -> dict[str, Any]:
    with open(CONFIG_DIR / "settings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_user(user_id: str) -> dict[str, Any]:
    roles_cfg = load_roles()
    for user in roles_cfg["users"]:
        if user["id"] == user_id:
            role = roles_cfg["roles"][user["role"]]
            return {**user, "role_def": role, "permissions": set(role["permissions"])}
    raise KeyError(f"Unknown user_id: {user_id}")


def list_users() -> list[dict[str, Any]]:
    return list(load_roles()["users"])


def openai_config() -> dict[str, str | None]:
    """Any OpenAI-compatible chat API works (OpenAI, Groq, xAI, local gateways, etc.)."""
    settings = load_settings()
    api_key = (
        os.getenv("GROQ_API_KEY")
        or os.getenv("XAI_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )
    provider = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    if provider == "groq" or (os.getenv("GROQ_API_KEY") and not os.getenv("OPENAI_BASE_URL")):
        default_base = "https://api.groq.com/openai/v1"
        default_model = "llama-3.3-70b-versatile"
    elif provider == "xai" or (os.getenv("XAI_API_KEY") and not os.getenv("OPENAI_BASE_URL")):
        default_base = "https://api.x.ai/v1"
        default_model = "grok-3-mini"
    else:
        default_base = None
        default_model = settings["llm"]["model"]
    return {
        "api_key": api_key,
        "model": os.getenv("OPENAI_MODEL") or os.getenv("XAI_MODEL") or os.getenv("GROQ_MODEL") or default_model,
        "base_url": os.getenv("OPENAI_BASE_URL") or default_base,
    }