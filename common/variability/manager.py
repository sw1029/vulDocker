"""Variation Key normalization and decoding profile management.

The implementation mirrors docs/handbook.md (다변성/디코딩) so that PLAN, Generator,
Reviewer, and Researcher share the same normalization logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from common.config import DecodingProfile


_CORE_KEYS = {"mode", "temperature", "top_p", "self_consistency_k", "pattern_pool_seed"}


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


@dataclass(frozen=True)
class VariationSpec:
    """Container for normalized variation parameters."""

    mode: str
    temperature: float
    top_p: float
    self_consistency_k: int
    pattern_pool_seed: int
    extras: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def for_mode(cls, mode: str, *, seed: int | None = None) -> "VariationSpec":
        normalized = (mode or "deterministic").lower()
        if normalized == "diverse":
            defaults = {"temperature": 0.7, "top_p": 0.95, "self_consistency_k": 5}
        else:
            normalized = "deterministic"
            defaults = {"temperature": 0.0, "top_p": 1.0, "self_consistency_k": 1}
        return cls(
            mode=normalized,
            temperature=defaults["temperature"],
            top_p=defaults["top_p"],
            self_consistency_k=defaults["self_consistency_k"],
            pattern_pool_seed=_safe_int(seed, 0),
            extras={},
        )

    @classmethod
    def from_raw(cls, raw: Optional[Dict[str, Any]], *, seed: int | None = None) -> "VariationSpec":
        raw = raw or {}
        base = cls.for_mode(raw.get("mode"), seed=raw.get("pattern_pool_seed", seed))
        temperature = _safe_float(raw.get("temperature"), base.temperature)
        top_p = _safe_float(raw.get("top_p"), base.top_p)
        self_consistency_k = max(1, _safe_int(raw.get("self_consistency_k"), base.self_consistency_k))
        pattern_pool_seed = _safe_int(raw.get("pattern_pool_seed"), base.pattern_pool_seed)
        extras = {key: value for key, value in raw.items() if key not in _CORE_KEYS}
        return cls(
            mode=base.mode,
            temperature=temperature,
            top_p=top_p,
            self_consistency_k=self_consistency_k,
            pattern_pool_seed=pattern_pool_seed,
            extras=extras,
        )

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "mode": self.mode,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "self_consistency_k": self.self_consistency_k,
            "pattern_pool_seed": self.pattern_pool_seed,
        }
        payload.update(self.extras)
        return payload


class VariationManager:
    """Utility that exposes agent-specific decoding profiles and timers."""

    def __init__(self, variation_key: Optional[Dict[str, Any]], *, seed: int | None = None) -> None:
        self._spec = VariationSpec.from_raw(variation_key, seed=seed)

    @property
    def key(self) -> Dict[str, Any]:
        """Return a serializable dict copy of the normalized Variation Key."""

        return self._spec.to_dict()

    @property
    def mode(self) -> str:
        return self._spec.mode

    @property
    def is_diverse(self) -> bool:
        return self._spec.mode == "diverse"

    @property
    def pattern_seed(self) -> int:
        return self._spec.pattern_pool_seed

    def pattern_seed_with_offset(self, offset: int) -> int:
        return self._spec.pattern_pool_seed + int(offset)

    def self_consistency_k(self, agent: str = "generator") -> int:
        key = f"{agent}_self_consistency_k"
        if key in self._spec.extras:
            return max(1, _safe_int(self._spec.extras[key], 1))
        if agent == "generator":
            return self._spec.self_consistency_k
        return 1

    def profile_for(self, agent: str, override_mode: Optional[str] = None) -> DecodingProfile:
        """Return the decoding profile honoring variation + per-agent overrides."""

        target_mode = self._agent_mode(agent, override_mode)
        if target_mode == self._spec.mode:
            spec = self._spec
        else:
            spec = VariationSpec.for_mode(target_mode, seed=self._spec.pattern_pool_seed)
        return DecodingProfile(
            mode=spec.mode,
            temperature=spec.temperature,
            top_p=spec.top_p,
            self_consistency_k=spec.self_consistency_k,
        )

    def _agent_mode(self, agent: str, override_mode: Optional[str]) -> str:
        if override_mode:
            return override_mode.lower()
        agent_key = f"{agent}_mode"
        if agent_key in self._spec.extras:
            return str(self._spec.extras[agent_key]).lower()
        if agent == "reviewer":
            return str(self._spec.extras.get("reviewer_mode", "deterministic")).lower()
        return self._spec.mode

    @staticmethod
    def normalize(raw: Optional[Dict[str, Any]], *, seed: int | None = None) -> Dict[str, Any]:
        """Return a normalized Variation Key dictionary."""

        return VariationSpec.from_raw(raw, seed=seed).to_dict()


__all__ = ["VariationManager", "VariationSpec"]
