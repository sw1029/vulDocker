"""Lightweight assertion runner for LLM-assisted verification."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple


@dataclass
class AssertionOutcome:
    success: bool
    op: str
    details: str


def run_assertions(log_text: str, program: Sequence[Dict[str, object]] | None) -> Tuple[bool, List[AssertionOutcome]]:
    if not program:
        return True, []
    outcomes: List[AssertionOutcome] = []
    overall = True
    for entry in program:
        if not isinstance(entry, dict):
            continue
        op = str(entry.get("op") or "").lower()
        handler = _ASSERTION_HANDLERS.get(op)
        if handler is None:
            outcomes.append(AssertionOutcome(False, op or "unknown", "unsupported assertion"))
            overall = False
            continue
        success, detail = handler(log_text, entry)
        outcomes.append(AssertionOutcome(success, op, detail))
        if not success:
            overall = False
    return overall, outcomes


def _regex_flags(raw_flags: Sequence[str] | str | None) -> int:
    if raw_flags is None:
        return 0
    flags = 0
    values = raw_flags
    if isinstance(raw_flags, str):
        values = list(raw_flags)
    for flag in values:  # type: ignore[assignment]
        if flag == "i":
            flags |= re.IGNORECASE
        elif flag == "m":
            flags |= re.MULTILINE
        elif flag == "s":
            flags |= re.DOTALL
    return flags


def _assert_regex_contains(log_text: str, entry: Dict[str, object]) -> Tuple[bool, str]:
    pattern = entry.get("pattern")
    if not isinstance(pattern, str) or not pattern:
        return False, "missing regex pattern"
    flags = _regex_flags(entry.get("flags"))
    match = re.search(pattern, log_text, flags)
    return (match is not None, f"pattern={'found' if match else 'missing'}: {pattern}")


def _assert_contains(log_text: str, entry: Dict[str, object]) -> Tuple[bool, str]:
    needle = entry.get("string") or entry.get("pattern")
    if not isinstance(needle, str) or not needle:
        return False, "missing substring"
    success = needle in log_text
    return success, f"substring={'found' if success else 'missing'}"


def _assert_not_contains(log_text: str, entry: Dict[str, object]) -> Tuple[bool, str]:
    needle = entry.get("string") or entry.get("pattern")
    if not isinstance(needle, str) or not needle:
        return False, "missing substring"
    success = needle not in log_text
    return success, f"substring={'absent' if success else 'present'}"


def _extract_numeric(match: re.Match[str] | None) -> float | None:
    if not match:
        return None
    if match.lastindex:
        for idx in range(1, match.lastindex + 1):
            value = match.group(idx)
            if value and _NUMERIC_RE.search(value):
                try:
                    return float(value)
                except ValueError:  # pragma: no cover - defensive
                    continue
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _assert_number_delta(log_text: str, entry: Dict[str, object]) -> Tuple[bool, str]:
    before_pattern = entry.get("pattern_before")
    after_pattern = entry.get("pattern_after")
    if not isinstance(before_pattern, str) or not isinstance(after_pattern, str):
        return False, "number_delta requires pattern_before/pattern_after"
    flags = _regex_flags(entry.get("flags"))
    before = _extract_numeric(re.search(before_pattern, log_text, flags))
    after = _extract_numeric(re.search(after_pattern, log_text, flags))
    if before is None or after is None:
        return False, "unable to parse numeric values"
    delta = after - before
    comparator = str(entry.get("comparator") or "eq").lower()
    target = float(entry.get("delta") or 0.0)
    if comparator == "lt":
        success = delta < target
    elif comparator == "gt":
        success = delta > target
    else:
        success = delta == target
    return success, f"delta={delta} comparator={comparator} target={target}"


_ASSERTION_HANDLERS = {
    "regex_contains": _assert_regex_contains,
    "contains": _assert_contains,
    "not_contains": _assert_not_contains,
    "number_delta": _assert_number_delta,
}


_NUMERIC_RE = re.compile(r"[-+]?[0-9]*\.?[0-9]+")

