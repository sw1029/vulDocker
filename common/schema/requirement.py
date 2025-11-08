"""Requirement schema helpers for vuln_id/vuln_ids normalization."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "on"}
    return bool(value)


def _coerce_identifier(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = value.strip()
    if not cleaned:
        return ""
    normalized = cleaned.replace(" ", "").upper()
    return normalized


def slugify_vuln_id(value: str) -> str:
    """Return workspace-safe slug for a vuln identifier."""

    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "vuln"


class RequirementValidationError(ValueError):
    """Raised when the requirement payload is missing mandatory fields."""


@dataclass
class RequirementNormalization:
    """Result of requirement normalization."""

    requirement: Dict[str, Any]
    requested_vuln_ids: List[str]
    effective_vuln_ids: List[str]
    multi_vuln: bool
    vuln_ids_digest: Optional[str]
    warnings: List[str]
    ignored_vuln_ids: List[str]
    bundles: List[Dict[str, str]]
    executor_policy: Dict[str, Any]


def normalize_requirement(
    requirement: Dict[str, Any],
    *,
    multi_vuln_opt_in: bool = False,
) -> RequirementNormalization:
    """Normalize vuln_id/vuln_ids fields and derive helper metadata."""

    normalized_req = deepcopy(requirement)
    requested = _extract_vuln_ids(normalized_req)
    if not requested:
        raise RequirementValidationError("At least one vuln_id or vuln_ids entry is required.")

    raw_multi = _as_bool(normalized_req.get("multi_vuln"))
    multi_vuln = bool((raw_multi or multi_vuln_opt_in) and len(requested) > 1)
    warnings: List[str] = []
    ignored: List[str] = []
    if not multi_vuln and len(requested) > 1:
        ignored = requested[1:]
        warnings.append(
            "multi_vuln disabled; ignoring additional vuln_ids: " + ", ".join(ignored)
        )
    effective = requested if multi_vuln else [requested[0]]
    normalized_req["vuln_id"] = effective[0]
    normalized_req["vuln_ids"] = effective
    normalized_req["multi_vuln"] = multi_vuln

    vuln_ids_digest: Optional[str] = None
    if multi_vuln:
        serialized = "\n".join(sorted(effective))
        vuln_ids_digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    bundles: List[Dict[str, str]] = []
    single_bundle = len(effective) == 1
    for vid in effective:
        slug = slugify_vuln_id(vid)
        workspace_subdir = "app" if single_bundle else f"app/{slug}"
        bundles.append(
            {
                "vuln_id": vid,
                "slug": slug,
                "workspace_subdir": workspace_subdir,
            }
        )

    return RequirementNormalization(
        requirement=normalized_req,
        requested_vuln_ids=requested,
        effective_vuln_ids=effective,
        multi_vuln=multi_vuln,
        vuln_ids_digest=vuln_ids_digest,
        warnings=warnings,
        ignored_vuln_ids=ignored,
        bundles=bundles,
        executor_policy=_normalize_executor_policy(normalized_req),
    )


def _extract_vuln_ids(requirement: Dict[str, Any]) -> List[str]:
    declared: List[str] = []
    seq = requirement.get("vuln_ids")
    if isinstance(seq, list):
        for entry in seq:
            identifier = _coerce_identifier(entry)
            if identifier and identifier not in declared:
                declared.append(identifier)
    primary = _coerce_identifier(
        requirement.get("vuln_id")
        or requirement.get("cwe_id")
        or requirement.get("cve_id")
    )
    if primary:
        if primary in declared:
            declared.remove(primary)
        declared.insert(0, primary)
    if not declared:
        return []
    return declared


def _normalize_executor_policy(requirement: Dict[str, Any]) -> Dict[str, Any]:
    policy = requirement.get("executor") or {}
    if not isinstance(policy, dict):
        policy = {}
    defaults = {
        "allow_network": False,
        "network_mode": "none",
        "sidecars": [],
    }
    result = {
        "allow_network": bool(policy.get("allow_network", False)),
        "network_mode": str(policy.get("network_mode") or ("bridge" if policy.get("allow_network") else "none")),
        "network_name": str(policy.get("network_name") or "").strip() or None,
        "sidecars": [],
    }
    sidecars = policy.get("sidecars") or []
    if isinstance(sidecars, list):
        for entry in sidecars:
            if not isinstance(entry, dict):
                continue
        aliases: List[str] = []
        raw_aliases = entry.get("aliases") or []
        if isinstance(raw_aliases, list):
            for alias in raw_aliases:
                if isinstance(alias, str) and alias.strip():
                    aliases.append(alias.strip())
        result["sidecars"].append(
            {
                "name": entry.get("name", "sidecar"),
                "image": entry.get("image"),
                "env": entry.get("env") or {},
                "ready_probe": entry.get("ready_probe") or {},
                "network_mode": entry.get("network_mode") or result["network_mode"],
                "aliases": aliases,
            }
        )
    if not result["sidecars"]:
        result["sidecars"] = []
    return result


__all__ = [
    "RequirementNormalization",
    "RequirementValidationError",
    "normalize_requirement",
    "slugify_vuln_id",
]
