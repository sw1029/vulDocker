"""Scenario ID helper aligned with docs/handbook.md (메타스토어/아티팩트 섹션)."""
from __future__ import annotations

import hashlib
import json
from typing import Dict


SID_FIELDS = [
    "model_version",
    "prompt_hash",
    "seed",
    "retriever_commit",
    "corpus_snapshot",
    "pattern_id",
    "deps_digest",
    "base_image_digest",
]
OPTIONAL_FIELDS = ["vuln_ids_digest"]


def compute_sid(components: Dict[str, str]) -> str:
    """Return the deterministic SID hash."""

    payload = {key: components.get(key, "") for key in SID_FIELDS}
    for field in OPTIONAL_FIELDS:
        value = components.get(field)
        if value:
            payload[field] = value
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"sid-{digest[:12]}"
