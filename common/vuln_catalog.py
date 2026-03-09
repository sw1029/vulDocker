"""Shared vuln family catalog for name-only normalization and compiler routing."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ASSETS_ROOT = Path(__file__).resolve().parent / "assets"
VULN_CATALOG_PATH = ASSETS_ROOT / "vuln-family-catalog.json"
TOKEN_MATCH_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "attack",
        "bug",
        "by",
        "for",
        "from",
        "in",
        "issue",
        "of",
        "on",
        "or",
        "the",
        "through",
        "to",
        "using",
        "via",
        "vulnerability",
        "weakness",
        "with",
    }
)


def normalize_vuln_label(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = re.sub(r"[^a-z0-9]+", " ", value.strip().lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _content_tokens(value: Any) -> Tuple[str, ...]:
    label = normalize_vuln_label(value)
    tokens = [
        token
        for token in label.split(" ")
        if token and token not in TOKEN_MATCH_STOPWORDS
    ]
    return tuple(sorted(set(tokens)))


def _normalize_identifier(value: Any) -> str:
    token = str(value or "").strip()
    if not token:
        return ""
    normalized = token.upper().replace("_", "-").replace(" ", "")
    if normalized.startswith("NAME-"):
        return normalized
    if normalized.startswith("CWE-"):
        return normalized
    if normalized.startswith("CWE") and normalized[3:].isdigit():
        return f"CWE-{normalized[3:]}"
    return normalized


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "on"}
    return bool(value)


@lru_cache(maxsize=1)
def _catalog_payload() -> Dict[str, Dict[str, Any]]:
    raw = json.loads(VULN_CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    payload: Dict[str, Dict[str, Any]] = {}
    for raw_vuln_id, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        vuln_id = _normalize_identifier(raw_vuln_id)
        if not vuln_id:
            continue
        normalized_entry = dict(entry)
        normalized_entry["vuln_id"] = vuln_id
        normalized_entry["family"] = str(entry.get("family") or vuln_id.lower()).strip()
        normalized_entry["support_level"] = str(entry.get("support_level") or "unsupported").strip().lower()
        normalized_entry["display_name"] = str(entry.get("display_name") or vuln_id).strip()
        normalized_entry["pattern_id"] = str(entry.get("pattern_id") or "generic-web-vuln").strip()
        normalized_entry["fragment_strategy"] = str(entry.get("fragment_strategy") or "").strip()
        runtime = entry.get("runtime")
        normalized_entry["runtime"] = dict(runtime) if isinstance(runtime, dict) else {}
        runtime_surface = entry.get("runtime_surface")
        normalized_entry["runtime_surface"] = dict(runtime_surface) if isinstance(runtime_surface, dict) else {}
        user_deps = entry.get("user_deps")
        normalized_entry["user_deps"] = [
            str(item).strip() for item in user_deps or [] if isinstance(item, str) and str(item).strip()
        ]
        normalized_entry["label_aliases"] = [
            normalize_vuln_label(item)
            for item in entry.get("label_aliases") or []
            if normalize_vuln_label(item)
        ]
        normalized_entry["pattern_aliases"] = [
            normalize_vuln_label(item)
            for item in entry.get("pattern_aliases") or []
            if normalize_vuln_label(item)
        ]
        normalized_entry["identifier_aliases"] = [
            _normalize_identifier(item)
            for item in entry.get("identifier_aliases") or []
            if _normalize_identifier(item)
        ]
        token_sets: List[Tuple[str, ...]] = []
        for raw_set in entry.get("token_sets") or []:
            if not isinstance(raw_set, list):
                continue
            tokens = tuple(
                token
                for token in (normalize_vuln_label(item) for item in raw_set)
                if token and " " not in token
            )
            if tokens:
                token_sets.append(tokens)
        normalized_entry["token_sets"] = token_sets
        variants: List[Dict[str, Any]] = []
        for raw_variant in entry.get("strategy_variants") or []:
            if not isinstance(raw_variant, dict):
                continue
            fragment_strategy = str(raw_variant.get("fragment_strategy") or "").strip()
            if not fragment_strategy:
                continue
            runtime_db = [
                normalize_vuln_label(item)
                for item in raw_variant.get("runtime_db") or []
                if normalize_vuln_label(item)
            ]
            pattern_aliases = [
                normalize_vuln_label(item)
                for item in raw_variant.get("pattern_aliases") or []
                if normalize_vuln_label(item)
            ]
            runtime_surface = raw_variant.get("runtime_surface")
            variants.append(
                {
                    "fragment_strategy": fragment_strategy,
                    "runtime_db": runtime_db,
                    "pattern_aliases": pattern_aliases,
                    "require_allow_external_db": _as_bool(raw_variant.get("require_allow_external_db")),
                    "runtime_surface": dict(runtime_surface) if isinstance(runtime_surface, dict) else {},
                }
            )
        normalized_entry["strategy_variants"] = variants
        payload[vuln_id] = normalized_entry
    return payload


@lru_cache(maxsize=1)
def _catalog_indexes() -> Dict[str, Dict[str, str]]:
    label_aliases: Dict[str, str] = {}
    pattern_aliases: Dict[str, str] = {}
    identifier_aliases: Dict[str, str] = {}
    for vuln_id, entry in _catalog_payload().items():
        identifier_aliases[vuln_id] = vuln_id
        for alias in entry.get("identifier_aliases") or []:
            identifier_aliases[alias] = vuln_id
        for alias in entry.get("label_aliases") or []:
            label_aliases[alias] = vuln_id
        for alias in entry.get("pattern_aliases") or []:
            pattern_aliases[alias] = vuln_id
        for variant in entry.get("strategy_variants") or []:
            if not isinstance(variant, dict):
                continue
            for alias in variant.get("pattern_aliases") or []:
                if isinstance(alias, str) and alias:
                    pattern_aliases[alias] = vuln_id
    return {
        "label_aliases": label_aliases,
        "pattern_aliases": pattern_aliases,
        "identifier_aliases": identifier_aliases,
    }


def vuln_catalog_entries() -> List[Dict[str, Any]]:
    return [dict(entry) for entry in _catalog_payload().values()]


def vuln_catalog_entry(vuln_id: str) -> Optional[Dict[str, Any]]:
    canonical = _catalog_indexes()["identifier_aliases"].get(_normalize_identifier(vuln_id) or "")
    if not canonical:
        return None
    entry = _catalog_payload().get(canonical)
    return dict(entry) if isinstance(entry, dict) else None


def resolve_vuln_catalog_entry(
    *,
    vuln_id: Any = "",
    pattern_id: Any = "",
    raw_label: Any = "",
) -> Optional[Dict[str, Any]]:
    indexes = _catalog_indexes()
    identifier = _normalize_identifier(vuln_id)
    canonical = indexes["identifier_aliases"].get(identifier or "")
    if canonical:
        entry = dict(_catalog_payload()[canonical])
        entry["_match_source"] = "identifier_alias"
        return entry

    pattern = normalize_vuln_label(pattern_id)
    canonical = indexes["pattern_aliases"].get(pattern or "")
    if canonical:
        entry = dict(_catalog_payload()[canonical])
        entry["_match_source"] = "pattern_alias"
        return entry

    label = normalize_vuln_label(raw_label)
    canonical = indexes["label_aliases"].get(label or "")
    if canonical:
        entry = dict(_catalog_payload()[canonical])
        entry["_match_source"] = "label_alias"
        return entry

    content_tokens = _content_tokens(raw_label)
    if content_tokens:
        matches: List[Tuple[int, str, Dict[str, Any]]] = []
        for canonical, entry in _catalog_payload().items():
            for token_set in entry.get("token_sets") or []:
                candidate_tokens = tuple(
                    sorted(
                        {
                            token
                            for token in token_set
                            if isinstance(token, str)
                            and token
                            and token not in TOKEN_MATCH_STOPWORDS
                        }
                    )
                )
                if not candidate_tokens:
                    continue
                if candidate_tokens != content_tokens:
                    continue
                matches.append((len(candidate_tokens), canonical, entry))
                break
        if matches:
            matches.sort(key=lambda item: item[0], reverse=True)
            top_score = matches[0][0]
            top_matches = [item for item in matches if item[0] == top_score]
            unique_canonicals = {canonical for _score, canonical, _entry in top_matches}
            if len(unique_canonicals) == 1:
                matched = dict(top_matches[0][2])
                matched["_match_source"] = "token_match"
                return matched
    return None


def mapped_vuln_id_with_source(value: Any) -> Tuple[str, str]:
    entry = resolve_vuln_catalog_entry(vuln_id=value, pattern_id=value, raw_label=value)
    if not isinstance(entry, dict):
        return "", ""
    match_source = str(entry.get("_match_source") or "").strip().lower()
    if match_source in {"identifier_alias", "pattern_alias", "label_alias"}:
        return str(entry.get("vuln_id") or ""), "alias"
    if match_source == "token_match":
        return str(entry.get("vuln_id") or ""), "fragment_strategy_fallback"
    return str(entry.get("vuln_id") or ""), "unknown"


def resolve_compiler_strategy(vuln_id: str, requirement: Optional[Dict[str, Any]] = None) -> str:
    entry = vuln_catalog_entry(vuln_id)
    if not isinstance(entry, dict):
        return ""
    req = requirement if isinstance(requirement, dict) else {}
    runtime = req.get("runtime") if isinstance(req.get("runtime"), dict) else {}
    runtime_db = normalize_vuln_label(runtime.get("db"))
    pattern_id = normalize_vuln_label(req.get("pattern_id"))
    allow_external_db = _as_bool(runtime.get("allow_external_db") or req.get("allow_external_db"))
    for variant in entry.get("strategy_variants") or []:
        if not isinstance(variant, dict):
            continue
        variant_dbs = {token for token in variant.get("runtime_db") or [] if isinstance(token, str) and token}
        variant_patterns = {
            token for token in variant.get("pattern_aliases") or [] if isinstance(token, str) and token
        }
        explicit_pattern_match = bool(pattern_id and pattern_id in variant_patterns)
        runtime_match = not variant_dbs or bool(runtime_db and runtime_db in variant_dbs)
        if not explicit_pattern_match and not runtime_match:
            continue
        if variant.get("require_allow_external_db") and not allow_external_db and not explicit_pattern_match:
            continue
        strategy = str(variant.get("fragment_strategy") or "").strip()
        if strategy:
            return strategy
    return str(entry.get("fragment_strategy") or "").strip()


def resolve_runtime_surface_spec(strategy: str, requirement: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    token = str(strategy or "").strip()
    if not token:
        return {}
    for entry in _catalog_payload().values():
        if not isinstance(entry, dict):
            continue
        for variant in entry.get("strategy_variants") or []:
            if not isinstance(variant, dict):
                continue
            if str(variant.get("fragment_strategy") or "").strip() != token:
                continue
            runtime_surface = variant.get("runtime_surface")
            return dict(runtime_surface) if isinstance(runtime_surface, dict) else {}
        if str(entry.get("fragment_strategy") or "").strip() == token:
            runtime_surface = entry.get("runtime_surface")
            if isinstance(runtime_surface, dict):
                return dict(runtime_surface)
    return {}


def catalog_profile_defaults() -> Dict[str, Dict[str, Any]]:
    defaults: Dict[str, Dict[str, Any]] = {}
    for entry in vuln_catalog_entries():
        defaults[str(entry.get("vuln_id") or "")] = {
            "display_name": str(entry.get("display_name") or "").strip(),
            "pattern_id": str(entry.get("pattern_id") or "").strip(),
            "runtime": dict(entry.get("runtime") or {}),
            "user_deps": list(entry.get("user_deps") or []),
        }
    return defaults


def catalog_semantic_support_defaults() -> Dict[str, Dict[str, str]]:
    defaults: Dict[str, Dict[str, str]] = {}
    for entry in vuln_catalog_entries():
        defaults[str(entry.get("vuln_id") or "")] = {
            "family": str(entry.get("family") or "").strip(),
            "support_level": str(entry.get("support_level") or "unsupported").strip().lower(),
            "compiler_strategy": str(entry.get("fragment_strategy") or "").strip(),
        }
    return defaults


__all__ = [
    "catalog_profile_defaults",
    "catalog_semantic_support_defaults",
    "mapped_vuln_id_with_source",
    "normalize_vuln_label",
    "resolve_compiler_strategy",
    "resolve_runtime_surface_spec",
    "resolve_vuln_catalog_entry",
    "vuln_catalog_entries",
    "vuln_catalog_entry",
]
