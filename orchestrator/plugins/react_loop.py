"""Helpers that wire Researcher ReAct loops into the orchestrator."""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from common.logging import get_logger
from common.paths import ensure_dir, get_metadata_dir
from rag import latest_failure_context

LOGGER = get_logger(__name__)


_FAMILY_HINTS: Dict[str, Dict[str, Any]] = {
    "open_redirect": {
        "aliases": ["open redirect", "unvalidated redirect", "open redirection", "redirection"],
        "anchors": ["redirect target", "next parameter", "location header"],
        "query_focus": "open redirect",
        "exploit_hypothesis": "user-controlled redirect target reaches redirect sink",
    },
    "template_injection": {
        "aliases": [
            "template injection",
            "server-side template injection",
            "server side template injection",
            "ssti",
        ],
        "anchors": ["render_template_string", "jinja2", "{{7*7}}"],
        "query_focus": "server-side template injection",
        "exploit_hypothesis": "attacker-controlled template source reaches a template sink",
    },
    "path_traversal": {
        "aliases": ["path traversal", "directory traversal", "file traversal"],
        "anchors": ["../", "/etc/passwd", "send_file"],
        "query_focus": "path traversal",
        "exploit_hypothesis": "path input reaches filesystem read sink without normalization",
    },
    "xss": {
        "aliases": ["cross-site scripting", "xss", "reflected xss"],
        "anchors": ["<script>", "reflection", "template response"],
        "query_focus": "cross-site scripting",
        "exploit_hypothesis": "request input is reflected without escaping",
    },
    "ssrf": {
        "aliases": ["ssrf", "server-side request forgery", "server side request forgery"],
        "anchors": ["requests.get", "169.254.169.254", "user-controlled url"],
        "query_focus": "server-side request forgery",
        "exploit_hypothesis": "user-controlled URL reaches an outbound HTTP client sink",
    },
    "sqli": {
        "aliases": ["sql injection", "sqli"],
        "anchors": ["or 1=1", "union select", "cursor.execute"],
        "query_focus": "sql injection",
        "exploit_hypothesis": "request input is concatenated into a SQL execution sink",
    },
    "csrf": {
        "aliases": ["csrf", "cross-site request forgery"],
        "anchors": ["state-changing endpoint", "csrf token", "same-site"],
        "query_focus": "cross-site request forgery",
        "exploit_hypothesis": "cross-site request reaches a state-changing endpoint without CSRF validation",
    },
    "deserialization": {
        "aliases": ["insecure deserialization", "deserialization"],
        "anchors": ["pickle.loads", "yaml.load", "jsonpickle.decode"],
        "query_focus": "insecure deserialization",
        "exploit_hypothesis": "attacker-controlled serialized input reaches a deserialization sink",
    },
    "command_injection": {
        "aliases": ["command injection", "shell injection"],
        "anchors": ["subprocess", "os.system", "shell=true"],
        "query_focus": "command injection",
        "exploit_hypothesis": "user input reaches command execution without isolation",
    },
    "code_injection": {
        "aliases": ["code injection", "eval injection", "exec injection"],
        "anchors": ["eval(", "exec(", "user-controlled code"],
        "query_focus": "code injection",
        "exploit_hypothesis": "user-controlled code reaches an eval/exec sink",
    },
    "ldap_injection": {
        "aliases": ["ldap injection", "ldap filter injection"],
        "anchors": ["ldap filter", "directory search", "filter bypass"],
        "query_focus": "ldap injection",
        "exploit_hypothesis": "user-controlled directory lookup input reaches an LDAP filter sink",
    },
    "xxe": {
        "aliases": ["xxe", "xml external entity", "xml external entity injection"],
        "anchors": ["resolve_entities", "load_dtd", "external entity"],
        "query_focus": "xml external entity",
        "exploit_hypothesis": "attacker-controlled XML reaches a parser with entity resolution enabled",
    },
}

_VULN_ID_FAMILY_MAP = {
    "cwe-89": "sqli",
    "cwe_89": "sqli",
    "cwe-352": "csrf",
    "cwe_352": "csrf",
    "cwe-22": "path_traversal",
    "cwe_22": "path_traversal",
    "cwe-79": "xss",
    "cwe_79": "xss",
    "cwe-918": "ssrf",
    "cwe_918": "ssrf",
    "cwe-502": "deserialization",
    "cwe_502": "deserialization",
    "cwe-78": "command_injection",
    "cwe_78": "command_injection",
    "cwe-94": "code_injection",
    "cwe_94": "code_injection",
    "name-open-redirect": "open_redirect",
    "name-template-injection": "template_injection",
    "name-ldap-injection": "ldap_injection",
    "name-xxe": "xxe",
}


@dataclass
class ReactSpan:
    """Context manager that records researcher.react span metadata."""

    loop: "ReactLoop"
    name: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    _events: List[Dict[str, Any]] = field(default_factory=list)
    _start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def event(self, name: str, **attrs: Any) -> None:
        self._events.append(
            {
                "name": name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "attributes": attrs,
            }
        )

    def close(self) -> None:
        if self.loop is None:
            return
        payload = {
            "trace_id": self.loop.trace_id,
            "span_id": self.span_id,
            "span_name": self.name,
            "started_at": self._start.isoformat(),
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "attributes": self.attributes,
            "events": self._events,
        }
        self.loop._append_span(payload)
        self.loop = None

    def __enter__(self) -> "ReactSpan":
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        self.close()


class ReactLoop:
    """Light-weight plugin that captures Researcher queries and spans."""

    def __init__(self, sid: str) -> None:
        self.sid = sid
        self.metadata_dir = ensure_dir(get_metadata_dir(sid))
        self.trace_id = f"{sid}-react-{uuid.uuid4().hex[:8]}"
        self.failure_context = latest_failure_context(sid)
        self._span_path = self.metadata_dir / "react_trace.jsonl"
        self._history_path = self.metadata_dir / "researcher_history.jsonl"

    def span(self, name: str = "researcher.react", **attrs: Any) -> ReactSpan:
        """Return a context manager capturing a Researcher span."""

        return ReactSpan(loop=self, name=name, attributes=attrs)

    def queries_from_requirement(self, requirement: Dict[str, Any], *, limit: int = 3) -> List[str]:
        """Generate deterministic ReAct-style seed queries."""

        plan = self.query_plan_from_requirement(requirement, limit=limit)
        return [str(entry.get("query") or "").strip() for entry in plan.get("queries") or [] if str(entry.get("query") or "").strip()]

    def query_plan_from_requirement(self, requirement: Dict[str, Any], *, limit: int = 3) -> Dict[str, Any]:
        """Build a lightweight staged query plan for Researcher retrieval."""

        vuln_ids = _vuln_ids_from_requirement(requirement)
        vuln_names = _vuln_names_from_requirement(requirement)
        request_label = _request_label_from_requirement(requirement)
        stack_hypotheses = _stack_hypotheses_from_requirement(requirement)
        explicit_stack = _explicit_stack_from_requirement(requirement)
        tech_stack = " ".join(
            token
            for token in (explicit_stack.get("language"), explicit_stack.get("framework"))
            if isinstance(token, str) and token.strip()
        ).strip()
        intent = requirement.get("intent") or requirement.get("goal") or ""
        pattern_id = str(requirement.get("pattern_id") or "").strip()
        runtime = requirement.get("runtime") or {}
        db = ""
        if isinstance(runtime, dict):
            db = str(runtime.get("db") or runtime.get("database") or requirement.get("database") or "").strip()
        focus_label = request_label or (vuln_names[0] if vuln_names else (vuln_ids[0] if vuln_ids else "vulnerability"))
        family_hypotheses = _infer_family_hypotheses(requirement)
        exploit_hypotheses = _exploit_hypotheses(family_hypotheses)
        queries: List[Dict[str, Any]] = []

        def add_query(
            query: str,
            *,
            evidence_type: str,
            rationale: str,
            priority: int,
            family: str = "",
        ) -> None:
            normalized = str(query or "").strip()
            if not normalized:
                return
            queries.append(
                {
                    "query": normalized,
                    "evidence_type": evidence_type,
                    "rationale": rationale,
                    "priority": priority,
                    "family": family,
                }
            )

        if request_label:
            add_query(
                f"{request_label} vulnerability writeup exploit poc {tech_stack}".strip(),
                evidence_type="writeup",
                rationale="request_label-first exploit writeup seed",
                priority=10,
            )
            add_query(
                f"{request_label} vulnerable example github {tech_stack}".strip(),
                evidence_type="reference_impl",
                rationale="request_label-first vulnerable reference implementation seed",
                priority=9,
            )
        for vuln_name in vuln_names:
            add_query(
                f"{vuln_name} exploit writeup {tech_stack}".strip(),
                evidence_type="writeup",
                rationale="raw vulnerability name exploit seed",
                priority=8,
            )
        for vuln_id in vuln_ids:
            add_query(
                f"{vuln_id} weakness details exploit {tech_stack}".strip(),
                evidence_type="advisory",
                rationale="identifier-level weakness/advisory seed",
                priority=7,
            )
            add_query(
                f"{vuln_id} vulnerability exploit analysis {tech_stack}".strip(),
                evidence_type="writeup",
                rationale="identifier-level exploit analysis seed",
                priority=6,
            )
        if pattern_id and pattern_id.lower() != "generic-web-vuln":
            add_query(
                f"{pattern_id} vulnerable example poc {tech_stack}".strip(),
                evidence_type="reference_impl",
                rationale="pattern-guided vulnerable example seed",
                priority=7,
            )
        for hypothesis in family_hypotheses[:2]:
            family = str(hypothesis.get("family") or "").strip()
            config = _FAMILY_HINTS.get(family) or {}
            focus = str(config.get("query_focus") or family.replace("_", " ")).strip()
            anchors = " ".join(config.get("anchors") or []) if isinstance(config.get("anchors"), list) else ""
            add_query(
                f"{focus} exploit writeup poc {tech_stack}".strip(),
                evidence_type="writeup",
                rationale=f"family hypothesis seed via {hypothesis.get('basis') or 'heuristic'}",
                priority=10 if hypothesis.get("confidence") == "high" else 7,
                family=family,
            )
            if anchors:
                add_query(
                    f"{focus} {anchors} vulnerable example {tech_stack}".strip(),
                    evidence_type="oracle_hint",
                    rationale="family semantic anchor seed",
                    priority=8,
                    family=family,
                )
        curated_intent = _curated_intent_query_seed(intent)
        if curated_intent:
            add_query(
                f"{curated_intent} poc tutorial {tech_stack}".strip(),
                evidence_type="writeup",
                rationale="curated non-regression intent seed",
                priority=5,
            )
        if db:
            add_query(
                f"{focus_label} {db} {tech_stack} vulnerable example".strip(),
                evidence_type="reference_impl",
                rationale="runtime database anchor seed",
                priority=6,
            )
        if not explicit_stack and stack_hypotheses:
            for index, hypothesis in enumerate(stack_hypotheses[:2], start=1):
                stack_id = str(hypothesis.get("stack_id") or "").strip()
                if not stack_id:
                    continue
                add_query(
                    f"{focus_label} vulnerable example {stack_id}".strip(),
                    evidence_type="stack_anchor",
                    rationale=f"stack hypothesis #{index} anchor seed",
                    priority=9,
                )

        if not queries:
            add_query(
                "autonomous vulnerability lab research report",
                evidence_type="reference",
                rationale="generic fallback query",
                priority=1,
            )

        augmented = self._augment_with_failures(queries)
        unique: List[Dict[str, Any]] = []
        seen_queries: set[str] = set()
        ordered_entries = sorted(augmented, key=lambda item: int(item.get("priority") or 0), reverse=True)
        for entry in ordered_entries:
            normalized = str(entry.get("query") or "").strip()
            if not normalized or normalized in seen_queries:
                continue
            seen_queries.add(normalized)
            unique.append(entry)
            if len(unique) >= limit:
                break
        if not explicit_stack and stack_hypotheses:
            desired_stack_anchors = 1
            if limit >= 4 and len(stack_hypotheses) > 1:
                desired_stack_anchors = 2
            unique = self._ensure_stack_anchor_queries(
                unique,
                ordered_entries=ordered_entries,
                limit=limit,
                desired_count=desired_stack_anchors,
            )

        return {
            "request_label": focus_label,
            "tech_stack": explicit_stack.get("stack_id") if explicit_stack else None,
            "stack_hypotheses": stack_hypotheses,
            "stack_locked": bool(explicit_stack),
            "runtime_db": db or None,
            "pattern_id": pattern_id or None,
            "family_hypotheses": family_hypotheses,
            "exploit_hypotheses": exploit_hypotheses,
            "queries": unique,
        }

    def record_researcher_report(
        self,
        *,
        queries: Iterable[str],
        search_results: Iterable[Dict[str, Any]],
        report_path: Path,
        query_plan: Dict[str, Any] | None = None,
    ) -> None:
        """Append a JSON line summarizing the Researcher output."""

        payload = {
            "trace_id": self.trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "queries": list(queries),
            "query_plan": query_plan or {},
            "search_results": list(search_results),
            "report_path": str(report_path),
        }
        with self._history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    @staticmethod
    def _ensure_stack_anchor_queries(
        selected: List[Dict[str, Any]],
        *,
        ordered_entries: List[Dict[str, Any]],
        limit: int,
        desired_count: int,
    ) -> List[Dict[str, Any]]:
        desired = max(0, int(desired_count or 0))
        if desired == 0:
            return selected
        selected_queries = {
            str(item.get("query") or "").strip()
            for item in selected
            if isinstance(item, dict) and str(item.get("query") or "").strip()
        }
        stack_selected = [
            item
            for item in selected
            if str(item.get("evidence_type") or "").strip() == "stack_anchor"
        ]
        if len(stack_selected) >= desired:
            return selected
        stack_candidates = [
            entry
            for entry in ordered_entries
            if str(entry.get("evidence_type") or "").strip() == "stack_anchor"
            and str(entry.get("query") or "").strip()
            and str(entry.get("query") or "").strip() not in selected_queries
        ]
        if not stack_candidates:
            return selected
        updated = list(selected)
        counts: Dict[str, int] = {}
        for entry in updated:
            evidence_type = str(entry.get("evidence_type") or "").strip()
            counts[evidence_type] = counts.get(evidence_type, 0) + 1

        while len(
            [item for item in updated if str(item.get("evidence_type") or "").strip() == "stack_anchor"]
        ) < desired and stack_candidates:
            candidate = stack_candidates.pop(0)
            if len(updated) < limit:
                updated.append(candidate)
                continue
            replacement_index = -1
            for index in range(len(updated) - 1, -1, -1):
                evidence_type = str(updated[index].get("evidence_type") or "").strip()
                if counts.get(evidence_type, 0) > 1 and evidence_type != "stack_anchor":
                    replacement_index = index
                    break
            if replacement_index == -1:
                replacement_index = len(updated) - 1
            removed_type = str(updated[replacement_index].get("evidence_type") or "").strip()
            counts[removed_type] = max(0, counts.get(removed_type, 0) - 1)
            updated[replacement_index] = candidate
            counts["stack_anchor"] = counts.get("stack_anchor", 0) + 1
        return updated

    def rank_family_hypotheses(
        self,
        search_results: Iterable[Any],
        *,
        base_hypotheses: List[Dict[str, Any]] | None = None,
        limit: int = 4,
    ) -> Dict[str, Any]:
        """Rank candidate semantic families from retrieval evidence."""

        hypotheses: Dict[str, Dict[str, Any]] = {}

        def _ensure_family(family: str) -> Dict[str, Any]:
            entry = hypotheses.get(family)
            if entry is None:
                entry = {
                    "family": family,
                    "score": 0.0,
                    "signals": 0,
                    "matched_aliases": [],
                    "matched_anchors": [],
                    "bases": [],
                }
                hypotheses[family] = entry
            return entry

        for item in base_hypotheses or []:
            family = str((item or {}).get("family") or "").strip()
            if not family:
                continue
            entry = _ensure_family(family)
            confidence = str((item or {}).get("confidence") or "low").strip().lower()
            basis = str((item or {}).get("basis") or "heuristic").strip().lower() or "heuristic"
            entry["score"] += {"high": 0.35, "medium": 0.22, "low": 0.12}.get(confidence, 0.12)
            entry["bases"].append({"basis": basis, "confidence": confidence})

        for raw in search_results:
            if hasattr(raw, "title") and hasattr(raw, "snippet"):
                text = " ".join(
                    str(part or "").strip().lower()
                    for part in (getattr(raw, "title", ""), getattr(raw, "url", ""), getattr(raw, "snippet", ""), getattr(raw, "raw_content", ""))
                    if str(part or "").strip()
                )
            elif isinstance(raw, dict):
                text = " ".join(
                    str(part or "").strip().lower()
                    for part in (raw.get("title"), raw.get("url"), raw.get("snippet"), raw.get("raw_content"))
                    if str(part or "").strip()
                )
            else:
                text = str(raw or "").strip().lower()
            if not text:
                continue
            for family, config in _FAMILY_HINTS.items():
                aliases = [token for token in config.get("aliases") or [] if isinstance(token, str) and token.strip()]
                anchors = [token for token in config.get("anchors") or [] if isinstance(token, str) and token.strip()]
                matched_aliases = [token for token in aliases if token.lower() in text]
                matched_anchors = [token for token in anchors if token.lower() in text]
                if not matched_aliases and not matched_anchors:
                    continue
                entry = _ensure_family(family)
                entry["score"] += min(0.65, (0.18 * len(matched_aliases)) + (0.12 * len(matched_anchors)))
                entry["signals"] += 1
                for token in matched_aliases:
                    if token not in entry["matched_aliases"]:
                        entry["matched_aliases"].append(token)
                for token in matched_anchors:
                    if token not in entry["matched_anchors"]:
                        entry["matched_anchors"].append(token)

        ranked: List[Dict[str, Any]] = []
        for family, entry in hypotheses.items():
            score = round(min(1.0, float(entry.get("score") or 0.0)), 3)
            ranked.append(
                {
                    "family": family,
                    "score": score,
                    "signal_hits": int(entry.get("signals") or 0),
                    "matched_aliases": list(entry.get("matched_aliases") or []),
                    "matched_anchors": list(entry.get("matched_anchors") or []),
                    "bases": list(entry.get("bases") or []),
                }
            )
        ranked.sort(key=lambda item: (float(item.get("score") or 0.0), int(item.get("signal_hits") or 0)), reverse=True)
        ranked = ranked[: max(1, limit)]

        top_family = ranked[0]["family"] if ranked else ""
        top_score = float(ranked[0].get("score") or 0.0) if ranked else 0.0
        second_score = float(ranked[1].get("score") or 0.0) if len(ranked) > 1 else 0.0
        top_margin = round(max(0.0, top_score - second_score), 3)
        contradictory_families = [
            item["family"]
            for item in ranked[1:]
            if float(item.get("score") or 0.0) >= 0.40
        ]
        raw_top_confidence = _score_to_confidence(top_score) if ranked else None
        ambiguous = bool(
            ranked and (len(contradictory_families) >= 2 or (bool(contradictory_families) and top_margin < 0.2))
        )
        top_has_base = bool((ranked[0].get("bases") or [])) if ranked else False
        top_confidence = (
            _calibrate_family_confidence(
                raw_top_confidence or "low",
                ambiguous=ambiguous,
                top_margin=top_margin,
                has_base=top_has_base,
            )
            if ranked
            else None
        )
        for item in ranked:
            item["confidence"] = (
                top_confidence
                if item is ranked[0]
                else _score_to_confidence(float(item.get("score") or 0.0))
            )
        return {
            "ranked_families": ranked,
            "top_family": top_family or None,
            "top_confidence": top_confidence,
            "raw_top_confidence": raw_top_confidence,
            "top_margin": top_margin,
            "ambiguous": ambiguous,
            "contradiction_count": len(contradictory_families),
            "contradictory_families": contradictory_families,
        }

    # Internal helpers -----------------------------------------------------

    def _augment_with_failures(self, queries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self.failure_context:
            return queries
        hints = []
        for line in self.failure_context.splitlines():
            tokens = [token.strip() for token in line.split(":") if token.strip()]
            if len(tokens) >= 2:
                hints.append(tokens[-1])
        if hints:
            queries.append(
                {
                    "query": f"{' '.join(hints[:2])} mitigation guidance".strip(),
                    "evidence_type": "oracle_hint",
                    "rationale": "recent failure context mitigation seed",
                    "priority": 4,
                    "family": "",
                }
            )
        return queries

    def _append_span(self, payload: Dict[str, Any]) -> None:
        with self._span_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _vuln_ids_from_requirement(requirement: Dict[str, Any]) -> List[str]:
    values = requirement.get("vuln_ids")
    if isinstance(values, list):
        normalized = [str(item).strip() for item in values if isinstance(item, str) and item.strip()]
        if normalized:
            return normalized
    fallback = requirement.get("vuln_id") or requirement.get("cwe_id") or requirement.get("cve_id")
    if isinstance(fallback, str) and fallback.strip():
        return [fallback.strip()]
    return []


def _vuln_names_from_requirement(requirement: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    for key in ("vuln_name", "vulnerability_name", "weakness_name", "cwe_name", "vuln_label"):
        value = requirement.get(key)
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if cleaned and cleaned not in names:
            names.append(cleaned)
    return names


def _request_label_from_requirement(requirement: Dict[str, Any]) -> str:
    request_identity = requirement.get("request_identity")
    if isinstance(request_identity, dict):
        value = request_identity.get("request_label")
        if isinstance(value, str) and value.strip():
            return value.strip()
    names = _vuln_names_from_requirement(requirement)
    return names[0] if names else ""


def _explicit_stack_from_requirement(requirement: Dict[str, Any]) -> Dict[str, str]:
    language = str(requirement.get("language") or "").strip().lower()
    framework = str(requirement.get("framework") or "").strip().lower()
    if not language or not framework:
        return {}
    return {
        "language": language,
        "framework": framework,
        "stack_id": f"{language}/{framework}",
        "source": "explicit_requirement",
        "confidence": "high",
    }


def _stack_hypotheses_from_requirement(requirement: Dict[str, Any]) -> List[Dict[str, str]]:
    explicit = _explicit_stack_from_requirement(requirement)
    hypotheses: List[Dict[str, str]] = [explicit] if explicit else []
    seen = {(explicit.get("language"), explicit.get("framework"))} if explicit else set()
    raw = requirement.get("stack_hypotheses")
    if not isinstance(raw, list):
        return hypotheses
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        language = str(entry.get("language") or "").strip().lower()
        framework = str(entry.get("framework") or "").strip().lower()
        if not language or not framework:
            continue
        key = (language, framework)
        if key in seen:
            continue
        seen.add(key)
        hypotheses.append(
            {
                "language": language,
                "framework": framework,
                "stack_id": str(entry.get("stack_id") or f"{language}/{framework}").strip().lower(),
                "source": str(entry.get("source") or "unknown").strip().lower() or "unknown",
                "confidence": str(entry.get("confidence") or "unknown").strip().lower() or "unknown",
            }
        )
    return hypotheses


def _curated_intent_query_seed(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = re.sub(r"\s+", " ", value).strip()
    if not text:
        return ""
    lowered = text.lower()
    noisy_markers = (
        "e2e",
        "regression",
        "회귀",
        "검증",
        "smoke",
        "baseline",
        "테스트",
    )
    if any(marker in lowered for marker in noisy_markers):
        return ""
    return text


def _infer_family_hypotheses(requirement: Dict[str, Any]) -> List[Dict[str, str]]:
    candidates: List[Dict[str, str]] = []
    text_parts = [
        _request_label_from_requirement(requirement),
        * _vuln_names_from_requirement(requirement),
        str(requirement.get("pattern_id") or ""),
    ]
    normalized_text = " ".join(part.strip().lower() for part in text_parts if isinstance(part, str) and part.strip())
    vuln_ids = [str(item).strip().lower() for item in _vuln_ids_from_requirement(requirement)]

    def add_candidate(family: str, confidence: str, basis: str) -> None:
        if not family:
            return
        for existing in candidates:
            if existing.get("family") != family:
                continue
            rank = {"low": 1, "medium": 2, "high": 3}
            if rank.get(confidence, 0) > rank.get(str(existing.get("confidence") or "low"), 0):
                existing["confidence"] = confidence
                existing["basis"] = basis
            return
        candidates.append({"family": family, "confidence": confidence, "basis": basis})

    for vuln_id in vuln_ids:
        family = _VULN_ID_FAMILY_MAP.get(vuln_id)
        if family:
            add_candidate(family, "high", "vuln_id")

    pattern_id = str(requirement.get("pattern_id") or "").strip().lower()
    for family, config in _FAMILY_HINTS.items():
        aliases = [str(item).strip().lower() for item in config.get("aliases") or [] if str(item).strip()]
        if pattern_id and any(alias.replace(" ", "-") in pattern_id for alias in aliases):
            add_candidate(family, "high", "pattern_id")
        if normalized_text and any(alias in normalized_text for alias in aliases):
            add_candidate(family, "high", "request_label")

    return candidates


def _exploit_hypotheses(family_hypotheses: List[Dict[str, str]]) -> List[str]:
    values: List[str] = []
    for hypothesis in family_hypotheses:
        family = str(hypothesis.get("family") or "").strip()
        config = _FAMILY_HINTS.get(family) or {}
        text = str(config.get("exploit_hypothesis") or "").strip()
        if text and text not in values:
            values.append(text)
    return values


def _score_to_confidence(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.40:
        return "medium"
    return "low"


def _downgrade_confidence(confidence: str, steps: int = 1) -> str:
    ordered = ["low", "medium", "high"]
    if confidence not in ordered:
        confidence = "low"
    index = ordered.index(confidence)
    return ordered[max(0, index - max(0, steps))]


def _calibrate_family_confidence(
    confidence: str,
    *,
    ambiguous: bool,
    top_margin: float,
    has_base: bool,
) -> str:
    calibrated = str(confidence or "low").strip().lower() or "low"
    if ambiguous:
        calibrated = _downgrade_confidence(calibrated, 2 if top_margin < 0.1 else 1)
    elif top_margin < 0.2:
        calibrated = _downgrade_confidence(calibrated, 1)
    if not has_base and calibrated == "high":
        calibrated = "medium"
    return calibrated


__all__ = ["ReactLoop", "ReactSpan"]
