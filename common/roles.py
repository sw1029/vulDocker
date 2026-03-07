"""Canonical role helpers shared across generation and verification stages."""
from __future__ import annotations

import re

ROLE_ALIASES = {
    "server": "service_main",
    "verifier": "poc_entry",
}


def normalize_role(value: str | None) -> str:
    token = re.sub(r"[\s-]+", "_", str(value or "").strip().lower())
    if not token:
        return ""
    return ROLE_ALIASES.get(token, token)


def role_matches(value: str | None, target: str | None) -> bool:
    left = normalize_role(value)
    right = normalize_role(target)
    return bool(left and right and left == right)


__all__ = ["normalize_role", "role_matches", "ROLE_ALIASES"]
