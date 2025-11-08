"""Helpers for iterating plan.run_matrix bundles."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .paths import ensure_dir
from .schema import slugify_vuln_id


@dataclass(frozen=True)
class VulnBundle:
    vuln_id: str
    slug: str
    workspace_subdir: str


def is_multi_vuln(plan: Dict[str, Any]) -> bool:
    features = plan.get("features") or {}
    return bool(features.get("multi_vuln"))


def load_vuln_bundles(plan: Dict[str, Any]) -> List[VulnBundle]:
    matrix = plan.get("run_matrix") or {}
    entries = matrix.get("vuln_bundles") or []
    if not entries:
        requirement = plan.get("requirement") or {}
        vuln_id = requirement.get("vuln_id") or "CWE-UNKNOWN"
        entries = [
            {
                "vuln_id": vuln_id,
                "slug": slugify_vuln_id(vuln_id),
                "workspace_subdir": "app",
            }
        ]
    bundles: List[VulnBundle] = []
    for entry in entries:
        bundles.append(
            VulnBundle(
                vuln_id=str(entry.get("vuln_id")),
                slug=entry.get("slug") or slugify_vuln_id(entry.get("vuln_id", "")),
                workspace_subdir=entry.get("workspace_subdir") or "app",
            )
        )
    return bundles


def bundle_requirement(requirement: Dict[str, Any], bundle: VulnBundle) -> Dict[str, Any]:
    scoped = deepcopy(requirement)
    scoped["vuln_id"] = bundle.vuln_id
    scoped["vuln_ids"] = [bundle.vuln_id]
    return scoped


def workspace_dir_for_bundle(plan: Dict[str, Any], bundle: VulnBundle) -> Path:
    base = Path(plan["paths"]["workspace"]).parent
    target = base / bundle.workspace_subdir
    return ensure_dir(target)


def metadata_dir_for_bundle(plan: Dict[str, Any], bundle: VulnBundle) -> Path:
    base = Path(plan["paths"]["metadata"])
    if is_multi_vuln(plan):
        return ensure_dir(base / "bundles" / bundle.slug)
    return ensure_dir(base)


def artifacts_dir_for_bundle(plan: Dict[str, Any], bundle: VulnBundle, kind: str) -> Path:
    base = Path(plan["paths"]["artifacts"])
    if is_multi_vuln(plan):
        return ensure_dir(base / kind / bundle.slug)
    return ensure_dir(base / kind)


__all__ = [
    "VulnBundle",
    "bundle_requirement",
    "load_vuln_bundles",
    "workspace_dir_for_bundle",
    "metadata_dir_for_bundle",
    "artifacts_dir_for_bundle",
    "is_multi_vuln",
]
