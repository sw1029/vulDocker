from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CASE_MATRIX_PATH = REPO_ROOT / "tests/e2e/case_matrix.json"

ALLOWED_AXIS_VALUES = {
    "family_known": {"known", "unknown"},
    "phrase_shape": {"canonical", "alias", "paraphrase", "broad"},
    "stack_evidence": {"explicit", "researcher", "defaulted", "conflicting"},
    "topology_class": {"single_service", "service_plus_sidecar"},
    "evidence_authority": {"high", "mixed", "low"},
    "conflict_level": {"low", "family_conflict", "stack_conflict"},
    "oracle_difficulty": {"simple", "payload_replay", "stateful"},
    "remote_mode": {"remote_ok", "strict_no_remote"},
}


def load_case_matrix() -> Dict[str, Dict[str, Any]]:
    cases = raw_case_matrix_entries()
    return {
        str(entry.get("case") or "").strip(): entry
        for entry in cases
        if isinstance(entry, dict) and str(entry.get("case") or "").strip()
    }


def raw_case_matrix_entries() -> List[Dict[str, Any]]:
    payload = json.loads(CASE_MATRIX_PATH.read_text(encoding="utf-8"))
    cases = payload.get("cases") if isinstance(payload, dict) else []
    if not isinstance(cases, list):
        return []
    return [entry for entry in cases if isinstance(entry, dict)]


def case_matrix_entry(case_name: str) -> Dict[str, Any]:
    return dict(load_case_matrix().get(case_name) or {})


def case_matrix_axes(case_name: str) -> Dict[str, str]:
    entry = case_matrix_entry(case_name)
    axes = entry.get("axes") if isinstance(entry.get("axes"), dict) else {}
    return {
        str(key): str(value)
        for key, value in axes.items()
        if isinstance(key, str) and str(key).strip() and isinstance(value, str) and str(value).strip()
    }


def active_case_names() -> List[str]:
    return sorted(
        path.parent.name
        for path in (REPO_ROOT / "tests/e2e/cases").glob("*/requirement.yml")
    )
