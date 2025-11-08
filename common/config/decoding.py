"""Decoding profile definitions used by LLM calls.

The values mirror docs/decoding/model_and_decoding_strategy.md so that
scripts can import a single helper and stay in sync with the documentation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class DecodingProfile:
    """Simple container for decoding parameters."""

    mode: str
    temperature: float
    top_p: float
    self_consistency_k: int = 1

    def to_kwargs(self) -> Dict[str, float]:
        """Return kwargs that can be passed directly to LLM SDKs."""

        return {
            "temperature": self.temperature,
            "top_p": self.top_p,
        }


_DETERMINISTIC = DecodingProfile(mode="deterministic", temperature=0.0, top_p=1.0)
_DIVERSE = DecodingProfile(mode="diverse", temperature=0.7, top_p=0.95, self_consistency_k=5)


def get_decoding_profile(mode: str) -> DecodingProfile:
    """Return the decoding profile for the requested mode.

    Parameters
    ----------
    mode: str
        Either ``"deterministic"`` or ``"diverse"``. Defaults to deterministic
        for any unknown value to keep the MVP reproducible.
    """

    normalized = (mode or "deterministic").lower()
    if normalized == "diverse":
        return _DIVERSE
    return _DETERMINISTIC
