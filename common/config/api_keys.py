"""API key loader used by LLM clients."""
from __future__ import annotations

import configparser
from pathlib import Path
from typing import Optional


def _config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "api_keys.ini"


def get_openai_api_key() -> Optional[str]:
    """Read OpenAI API key from config/api_keys.ini if present."""

    path = _config_path()
    if not path.exists():
        return None
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    return parser.get("openai", "api_key", fallback=None).strip() or None
