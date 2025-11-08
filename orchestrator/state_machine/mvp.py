"""PLAN→PACK state machine used by the MVP runbook."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

MVP_STATES: List[str] = [
    "PLAN",
    "DRAFT",
    "BUILD",
    "RUN",
    "VERIFY",
    "REVIEW",
    "PACK",
]

MVP_TRANSITIONS: Dict[str, List[str]] = {
    "PLAN": ["DRAFT"],
    "DRAFT": ["BUILD", "REVIEW"],
    "BUILD": ["RUN"],
    "RUN": ["VERIFY"],
    "VERIFY": ["PACK", "REVIEW"],
    "REVIEW": ["DRAFT", "PACK"],
    "PACK": [],
}


@dataclass
class StateMachine:
    """Minimal helper to validate state transitions."""

    current: str = "PLAN"

    def transition(self, target: str) -> str:
        target = target.upper()
        if target not in MVP_STATES:
            raise ValueError(f"Unknown target state: {target}")
        allowed = MVP_TRANSITIONS[self.current]
        if target not in allowed:
            raise ValueError(f"Illegal transition {self.current} -> {target}")
        self.current = target
        return self.current

    def reset(self) -> None:
        self.current = "PLAN"
