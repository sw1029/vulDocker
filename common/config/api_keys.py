"""API key loader used by LLM and search clients."""
from __future__ import annotations

import configparser
from pathlib import Path
from typing import Optional


def _config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "api_keys.ini"


def _read_api_key(section: str) -> Optional[str]:
    path = _config_path()
    if not path.exists():
        return None
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    value = parser.get(section, "api_key", fallback=None)
    if not isinstance(value, str):
        return None
    return value.strip() or None


def get_openai_api_key() -> Optional[str]:
    """Read OpenAI API key from config/api_keys.ini if present."""

    return _read_api_key("openai")


def get_tavily_api_key() -> Optional[str]:
    """Read Tavily API key from config/api_keys.ini if present."""

    return _read_api_key("tavily")
