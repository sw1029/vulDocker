"""Shared logging configuration."""
from __future__ import annotations

import logging
import os
from typing import Optional


_ENV_LEVEL = os.environ.get("VUL_LOG_LEVEL")


def _resolve_level(value: int | str | None) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        candidate = logging.getLevelName(value.strip().upper())
        if isinstance(candidate, int):
            return candidate
    if isinstance(_ENV_LEVEL, str):
        candidate = logging.getLevelName(_ENV_LEVEL.strip().upper())
        if isinstance(candidate, int):
            return candidate
    return logging.INFO


def configure_logging(level: int | str | None = None) -> None:
    resolved = _resolve_level(level)
    root = logging.getLogger()
    if not root.hasHandlers():
        logging.basicConfig(
            level=resolved,
            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        )
    else:
        root.setLevel(resolved)
    logging.getLogger("LiteLLM").setLevel(resolved)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name or "vul")
