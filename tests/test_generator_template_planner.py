from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.generator.service import GeneratorContext, GeneratorService
from common.contracts import write_generator_contract


def _context(*, failure: str = "") -> GeneratorContext:
    return GeneratorContext(
        rag="",
        failure=failure,
        hints="",
        researcher_report="",
        guard_spec="",
        guard_spec_dict={},
    )


def test_template_planner_is_skipped_for_clean_template_runs() -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.requirement = {}  # type: ignore[attr-defined]

    assert service._should_generate_template_plan(_context()) is False  # type: ignore[attr-defined]


def test_dynamic_eval_status_for_outcome_marks_fallback_as_degraded_success() -> None:
    outcome = SimpleNamespace(selected=SimpleNamespace(fallback_used=True))

    assert GeneratorService._dynamic_eval_status_for_outcome(outcome) == "degraded_success"


def test_dynamic_eval_status_for_outcome_marks_non_fallback_as_dynamic_success() -> None:
    outcome = SimpleNamespace(selected=SimpleNamespace(fallback_used=False))

    assert GeneratorService._dynamic_eval_status_for_outcome(outcome) == "dynamic_success"


def test_synthesis_action_trace_family_helpers_use_selection_and_materializer_family() -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "CVE-2099-0042",
        "request_ir": {
            "selection_decision": {
                "family": {
                    "selected": True,
                    "selected_family": "xss",
                }
            }
        },
    }
    outcome = SimpleNamespace(
        selected=SimpleNamespace(
            manifest={
                "metadata": {
                    "semantic_guided_family": "xss",
                    "semantic_guided_selection_source": "request_ir_selection",
                }
            }
        )
    )

    assert service._selected_family_for_trace() == "xss"  # type: ignore[attr-defined]
    assert service._materialized_family_for_synthesis_outcome(outcome) == "xss"  # type: ignore[attr-defined]


def test_template_planner_runs_when_failure_context_exists() -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.requirement = {}  # type: ignore[attr-defined]

    assert service._should_generate_template_plan(_context(failure="retry with fixes")) is True  # type: ignore[attr-defined]


def test_template_planner_can_be_force_enabled_from_requirement() -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.requirement = {"template_plan_enabled": True}  # type: ignore[attr-defined]

    assert service._should_generate_template_plan(_context()) is True  # type: ignore[attr-defined]


def test_requirement_for_synthesis_injects_resolved_runtime_recipe(tmp_path: Path) -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.sid = "sid-runtime-recipe"  # type: ignore[attr-defined]
    service.generator_mode = "synthesis"  # type: ignore[attr-defined]
    service.bundle = None  # type: ignore[attr-defined]
    service.workspace = tmp_path / "workspace"  # type: ignore[attr-defined]
    service.requirement = {"vuln_id": "NAME-OPEN-REDIRECT", "language": "python", "framework": "flask"}  # type: ignore[attr-defined]
    service.metadata_dir = tmp_path  # type: ignore[attr-defined]
    write_generator_contract(
        tmp_path,
        {
            "schema_version": "resolved_contract@1.0",
            "sid": "sid-runtime-recipe",
            "slug": "name-open-redirect",
            "vuln_id": "NAME-OPEN-REDIRECT",
            "runtime_recipe": {
                "language": "python",
                "framework": "fastapi",
                "topology": "service_plus_sidecar",
                "network_mode": "bridge",
            },
            "executor_plan": {
                "schema_version": "executor_plan@0.1",
                "service_port": 8000,
                "health_path": "/health",
                "topology": "service_plus_sidecar",
            },
            "staged_synthesis": {
                "schema_version": "staged_synthesis@0.1",
                "stage_order": ["candidate_resolution", "design_brief", "runtime_plan", "oracle_contract"],
                "candidate_resolution": {"selected_topology": "service_plus_sidecar"},
            },
        },
    )

    enriched = service._requirement_for_synthesis()  # type: ignore[attr-defined]

    assert enriched["runtime_recipe"]["framework"] == "fastapi"
    assert enriched["executor_plan"]["health_path"] == "/health"
    assert enriched["staged_synthesis"]["candidate_resolution"]["selected_topology"] == "service_plus_sidecar"
    assert "runtime_recipe" not in service.requirement  # type: ignore[operator]


def test_requirement_for_synthesis_builds_preflight_contract_for_name_only_when_missing(tmp_path: Path) -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.sid = "sid-preflight"  # type: ignore[attr-defined]
    service.generator_mode = "synthesis"  # type: ignore[attr-defined]
    service.bundle = None  # type: ignore[attr-defined]
    service.workspace = tmp_path / "workspace"  # type: ignore[attr-defined]
    service.metadata_dir = tmp_path  # type: ignore[attr-defined]
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "NAME-OPEN-REDIRECT",
        "vuln_name": "Open Redirect",
        "policy": {"name_only_mode": "dynamic"},
        "request_ir": {
            "request_label": "Open Redirect",
            "resolved_vuln_id": "NAME-OPEN-REDIRECT",
            "resolution_state": "catalog_alias",
            "resolution_match_class": "catalog_alias",
            "resolution_confidence": "high",
            "name_driven": True,
            "family_candidates": [
                {"family": "open_redirect", "source": "catalog_resolution", "confidence": "high"},
            ],
        },
        "request_identity": {
            "request_label": "Open Redirect",
            "resolved_vuln_id": "NAME-OPEN-REDIRECT",
            "match_class": "catalog_alias",
            "confidence": "high",
            "name_driven": True,
        },
        "name_resolution": {
            "resolved_vuln_id": "NAME-OPEN-REDIRECT",
            "match_class": "catalog_alias",
            "confidence": "high",
        },
        "stack_hypotheses": [
            {"language": "python", "framework": "flask", "source": "profile_prior", "confidence": "low"},
            {"language": "python", "framework": "fastapi", "source": "available_skeleton", "confidence": "low"},
        ],
    }
    (tmp_path / "researcher_report.json").write_text(
        json.dumps(
            {
                "quality": "sufficient",
                "tech_stack_candidates": [
                    {
                        "language": "python",
                        "framework": "flask",
                        "stack_id": "python/flask",
                        "confidence": "high",
                        "score": 0.9,
                        "sources": ["search_hit_text", "stack_anchor_query"],
                    },
                    {
                        "language": "python",
                        "framework": "fastapi",
                        "stack_id": "python/fastapi",
                        "confidence": "low",
                        "score": 0.2,
                        "sources": ["stack_anchor_query"],
                    },
                ],
                "family_hypothesis_summary": {
                    "top_family": "open_redirect",
                    "top_confidence": "high",
                    "contradiction_count": 0,
                    "contradictory_families": [],
                },
                "verification_spec": {
                    "success_mode": "text",
                    "success_text_markers": ["Exploit SUCCESS"],
                    "negative_controls": [{"name": "benign-next", "expect_success": False}],
                    "metamorphic": {"total": 1, "passed": 1},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    enriched = service._requirement_for_synthesis()  # type: ignore[attr-defined]

    assert enriched["request_ir"]["selection_decision"]["stack"]["selected"] is True
    assert enriched["request_ir"]["selection_decision"]["ready_for_materialization"] is True
    assert "name_only_generation_spec" in enriched
    assert "executor_plan" in enriched
    assert "staged_synthesis" in enriched
    assert enriched["staged_synthesis"]["runtime_plan"]["topology"] == "single_service"
    assert enriched["staged_synthesis"]["design_brief"]["selected_topology"] == "single_service"
    assert enriched["staged_synthesis"]["design_brief"]["selected_oracle_mode"] == "stateful_text"
    assert "negative_control_cases" in enriched["staged_synthesis"]["design_brief"]["required_roles"]


def test_researcher_report_for_prompt_preserves_family_hypothesis_summary(tmp_path: Path) -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.metadata_dir = tmp_path  # type: ignore[attr-defined]
    service.requirement = {"vuln_id": "NAME-OPEN-REDIRECT"}  # type: ignore[attr-defined]
    (tmp_path / "researcher_report.json").write_text(
        json.dumps(
            {
                "vuln_id": "NAME-OPEN-REDIRECT",
                "intent": "name-only dynamic lane",
                "tech_stack_candidates": [{"stack_id": "python/flask"}],
                "family_hypothesis_summary": {
                    "top_family": "open_redirect",
                    "top_confidence": "low",
                    "ambiguous": True,
                    "contradiction_count": 2,
                },
                "evidence_relevance": {"score": 0.41, "confidence": "medium"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    trimmed = json.loads(service._researcher_report_for_prompt())  # type: ignore[attr-defined]

    assert trimmed["family_hypothesis_summary"]["top_family"] == "open_redirect"
    assert trimmed["family_hypothesis_summary"]["ambiguous"] is True
    assert trimmed["evidence_relevance"]["confidence"] == "medium"


def test_researcher_report_for_prompt_preserves_compact_evidence_for_rag_injection(tmp_path: Path) -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.metadata_dir = tmp_path  # type: ignore[attr-defined]
    service.requirement = {"vuln_id": "CVE-2099-0001"}  # type: ignore[attr-defined]
    long_snippet = " ".join(["NVD advisory CVE-2099-0001 affected Flask endpoint"] * 30)
    (tmp_path / "researcher_report.json").write_text(
        json.dumps(
            {
                "vuln_id": "CVE-2099-0001",
                "evidence": [
                    {
                        "query": "CVE-2099-0001 NVD advisory affected versions weakness details",
                        "query_target": "advisory",
                        "evidence_type": "advisory",
                        "source_authority": "high",
                        "source": "local",
                        "provider": "local",
                        "title": "NVD - CVE-2099-0001",
                        "url": "file:///tmp/rag/corpus/raw/poc/20250101/CVE-2099-0001.json",
                        "snippet": long_snippet,
                        "raw_content": "should not be forwarded into the generator prompt",
                    }
                ],
                "evidence_type_summary": {
                    "hit_count": 1,
                    "matched_target_count": 1,
                    "by_type": {"advisory": 1},
                    "by_source_authority": {"high": 1},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    trimmed = json.loads(service._researcher_report_for_prompt())  # type: ignore[attr-defined]

    evidence = trimmed["evidence"][0]
    assert evidence["evidence_type"] == "advisory"
    assert evidence["source_authority"] == "high"
    assert evidence["title"] == "NVD - CVE-2099-0001"
    assert "raw_content" not in evidence
    assert len(evidence["snippet"]) <= 800
    assert trimmed["evidence_type_summary"]["by_type"]["advisory"] == 1


def test_hybrid_template_fallback_requires_compatible_template() -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.requirement = {"vuln_id": "NAME-CUSTOM-WEIRD-VULN", "pattern_id": "generic-web-vuln"}  # type: ignore[attr-defined]
    service._allow_external_db = lambda: False  # type: ignore[attr-defined]

    class _Template:
        def __init__(self, tags: list[str], pattern_id: str, requires_external_db: bool = False) -> None:
            self.tags = tags
            self.pattern_id = pattern_id
            self.requires_external_db = requires_external_db
            self.metadata = {}
            self.service_env = {}

    class _Registry:
        templates = [
            _Template(["cwe-89", "sqlite"], "sqli-sqlite-raw"),
            _Template(["cwe-352", "csrf"], "csrf-missing-token"),
        ]

    service._get_registry = lambda: _Registry()  # type: ignore[attr-defined]
    assert service._has_compatible_template() is False  # type: ignore[attr-defined]

    service.requirement = {"vuln_id": "NAME-TEMPLATE-INJECTION", "pattern_id": "template-injection"}  # type: ignore[attr-defined]

    class _CompatibleRegistry:
        templates = [
            _Template(["name-template-injection", "flask"], "template-injection"),
        ]

    service._get_registry = lambda: _CompatibleRegistry()  # type: ignore[attr-defined]
    assert service._has_compatible_template() is True  # type: ignore[attr-defined]


def test_hybrid_template_fallback_respects_runtime_db_surface() -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.requirement = {
        "vuln_id": "CWE-89",
        "pattern_id": "sqli-union-mysql",
        "runtime": {"db": "mysql", "allow_external_db": True},
    }  # type: ignore[attr-defined]
    service._allow_external_db = lambda: True  # type: ignore[attr-defined]
    service._runtime_db = lambda: "mysql"  # type: ignore[attr-defined]

    class _Template:
        def __init__(self, tags: list[str], pattern_id: str, db: str, requires_external_db: bool = False) -> None:
            self.tags = tags
            self.pattern_id = pattern_id
            self.db = db
            self.requires_external_db = requires_external_db
            self.metadata = {}
            self.service_env = {}

    class _Registry:
        templates = [
            _Template(["cwe-89", "flask"], "sqli-union-mysql", "sqlite", True),
            _Template(["cwe-89", "flask"], "sqli-union-mysql", "mysql", True),
        ]

    service._get_registry = lambda: _Registry()  # type: ignore[attr-defined]
    service.requirement["executor"] = {  # type: ignore[index]
        "allow_network": True,
        "network_mode": "bridge",
        "sidecars": [
            {
                "name": "mysql",
                "type": "mysql",
                "aliases": ["sqli-db"],
                "env": {
                    "MYSQL_USER": "sqli",
                    "MYSQL_PASSWORD": "sqli_pw",
                    "MYSQL_DATABASE": "sqliapp",
                },
            }
        ],
    }

    assert service._template_runtime_surface_matches(_Registry.templates[0]) is False  # type: ignore[attr-defined]
    assert service._template_runtime_surface_matches(_Registry.templates[1]) is True  # type: ignore[attr-defined]
    assert service._has_compatible_template() is True  # type: ignore[attr-defined]


def test_hybrid_template_fallback_rejects_external_db_template_without_executor_surface() -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.requirement = {
        "vuln_id": "CWE-89",
        "pattern_id": "sqli-union-mysql",
        "runtime": {"db": "mysql", "allow_external_db": True},
        "executor": {
            "allow_network": False,
            "network_mode": "none",
            "sidecars": [],
        },
    }  # type: ignore[attr-defined]
    service._allow_external_db = lambda: True  # type: ignore[attr-defined]
    service._runtime_db = lambda: "mysql"  # type: ignore[attr-defined]

    class _Template:
        def __init__(self) -> None:
            self.tags = ["cwe-89", "flask"]
            self.pattern_id = "sqli-union-mysql"
            self.db = "mysql"
            self.requires_external_db = True
            self.service_env = {
                "DB_HOST": "sqli-db",
                "DB_PORT": "3306",
                "DB_USER": "sqli",
                "DB_PASSWORD": "sqli_pw",
                "DB_NAME": "sqliapp",
                "APP_PORT": "5000",
            }
            self.metadata = {"ports": {"app": 5000}}

    class _Registry:
        templates = [_Template()]

    service._get_registry = lambda: _Registry()  # type: ignore[attr-defined]

    assert service._template_runtime_surface_matches(_Registry.templates[0]) is False  # type: ignore[attr-defined]
    assert service._has_compatible_template() is False  # type: ignore[attr-defined]


def test_hybrid_template_fallback_rejects_external_db_template_with_wrong_sidecar_type() -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.requirement = {
        "vuln_id": "CWE-89",
        "pattern_id": "sqli-union-mysql",
        "runtime": {"db": "mysql", "allow_external_db": True},
        "executor": {
            "allow_network": True,
            "network_mode": "bridge",
            "sidecars": [{"name": "postgres-main", "type": "postgres", "aliases": ["db-internal"]}],
        },
    }  # type: ignore[attr-defined]
    service._allow_external_db = lambda: True  # type: ignore[attr-defined]
    service._runtime_db = lambda: "mysql"  # type: ignore[attr-defined]

    class _Template:
        def __init__(self) -> None:
            self.tags = ["cwe-89", "flask"]
            self.pattern_id = "sqli-union-mysql"
            self.db = "mysql"
            self.requires_external_db = True
            self.service_env = {
                "DB_HOST": "sqli-db",
                "DB_PORT": "3306",
                "DB_USER": "sqli",
                "DB_PASSWORD": "sqli_pw",
                "DB_NAME": "sqliapp",
                "APP_PORT": "5000",
            }
            self.metadata = {"ports": {"app": 5000}, "stack_id": "python/flask"}

        @property
        def stack_id(self) -> str:
            return "python/flask"

        @property
        def language(self) -> str:
            return "python"

        @property
        def framework(self) -> str:
            return "flask"

    template = _Template()

    diagnostics = service._template_runtime_diagnostics(template)  # type: ignore[attr-defined]

    assert diagnostics["matches"] is False
    assert diagnostics["status"] == "executor_misconfigured"
    assert service._template_runtime_surface_matches(template) is False  # type: ignore[attr-defined]


def test_hybrid_template_fallback_rejects_template_when_sidecar_env_values_do_not_match() -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.requirement = {
        "vuln_id": "CWE-89",
        "pattern_id": "sqli-union-mysql",
        "runtime": {"db": "mysql", "allow_external_db": True, "db_name": "runtime_db_custom"},
        "executor": {
            "allow_network": True,
            "network_mode": "bridge",
            "sidecars": [
                {
                    "name": "mysql-main",
                    "type": "mysql",
                    "aliases": ["db-internal"],
                    "env": {
                        "MYSQL_USER": "custom_user",
                        "MYSQL_PASSWORD": "custom_pw",
                        "MYSQL_DATABASE": "custom_db",
                    },
                }
            ],
        },
    }  # type: ignore[attr-defined]
    service._allow_external_db = lambda: True  # type: ignore[attr-defined]
    service._runtime_db = lambda: "mysql"  # type: ignore[attr-defined]

    class _Template:
        def __init__(self) -> None:
            self.tags = ["cwe-89", "flask"]
            self.pattern_id = "sqli-union-mysql"
            self.db = "mysql"
            self.requires_external_db = True
            self.service_env = {
                "DB_HOST": "sqli-db",
                "DB_PORT": "3306",
                "DB_USER": "sqli",
                "DB_PASSWORD": "sqli_pw",
                "DB_NAME": "sqliapp",
                "APP_PORT": "5000",
            }
            self.metadata = {"ports": {"app": 5000}, "stack_id": "python/flask"}

        @property
        def stack_id(self) -> str:
            return "python/flask"

        @property
        def language(self) -> str:
            return "python"

        @property
        def framework(self) -> str:
            return "flask"

    diagnostics = service._template_runtime_diagnostics(_Template())  # type: ignore[attr-defined]

    assert diagnostics["matches"] is False
    assert diagnostics["status"] == "env_value_mismatch"
    assert diagnostics["env_value_mismatches"]["DB_HOST"]["expected"] == "db-internal"


def test_hybrid_template_fallback_rejects_stack_mismatched_template() -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.requirement = {
        "vuln_id": "CWE-89",
        "pattern_id": "sqli-sqlite-raw",
        "language": "python",
        "framework": "fastapi",
        "runtime": {"db": "sqlite", "allow_external_db": False},
    }  # type: ignore[attr-defined]
    service._allow_external_db = lambda: False  # type: ignore[attr-defined]
    service._runtime_db = lambda: "sqlite"  # type: ignore[attr-defined]

    class _Template:
        def __init__(self) -> None:
            self.tags = ["cwe-89", "sqlite", "flask"]
            self.pattern_id = "sqli-sqlite-raw"
            self.db = "sqlite"
            self.requires_external_db = False
            self.metadata = {"stack_id": "python/flask", "language": "python", "framework": "flask"}
            self.service_env = {}

        @property
        def stack_id(self) -> str:
            return "python/flask"

        @property
        def language(self) -> str:
            return "python"

        @property
        def framework(self) -> str:
            return "flask"

    class _Registry:
        templates = [_Template()]

    service._get_registry = lambda: _Registry()  # type: ignore[attr-defined]

    assert service._template_runtime_surface_matches(_Registry.templates[0]) is False  # type: ignore[attr-defined]
    assert service._has_compatible_template() is False  # type: ignore[attr-defined]


def test_viable_template_allows_internal_db_template_when_runtime_db_unspecified() -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.requirement = {"vuln_id": "CWE-89", "runtime": {}}  # type: ignore[attr-defined]
    service._allow_external_db = lambda: False  # type: ignore[attr-defined]

    class _Template:
        def __init__(self, *, db: str, requires_external_db: bool) -> None:
            self.tags = ["cwe-89", db]
            self.pattern_id = f"sqli-{db}"
            self.db = db
            self.requires_external_db = requires_external_db
            self.metadata = {"stack_id": "python/flask"}
            self.service_env = {}

        @property
        def stack_id(self) -> str:
            return "python/flask"

        @property
        def language(self) -> str:
            return "python"

        @property
        def framework(self) -> str:
            return "flask"

    class _Registry:
        templates = [
            _Template(db="mysql", requires_external_db=True),
            _Template(db="sqlite", requires_external_db=False),
        ]

    service._get_registry = lambda: _Registry()  # type: ignore[attr-defined]

    assert service._has_viable_template() is True  # type: ignore[attr-defined]


def test_template_mode_prefers_viable_template_over_compiler() -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.generator_mode = "template"  # type: ignore[attr-defined]
    service.sid = "sid-template-prefer-template"  # type: ignore[attr-defined]
    service.requirement = {"vuln_id": "CWE-89", "runtime": {"db": "mysql", "allow_external_db": True}}  # type: ignore[attr-defined]
    calls: list[tuple[str, str]] = []

    service._build_context = lambda: _context()  # type: ignore[attr-defined]
    service._ensure_loop_started = lambda: None  # type: ignore[attr-defined]
    service._has_viable_template = lambda: True  # type: ignore[attr-defined]
    service._run_compiler_if_supported = lambda: (_ for _ in ()).throw(AssertionError("compiler should not run"))  # type: ignore[attr-defined]
    service._run_synthesis_with_loops = lambda context: calls.append(("synthesis", "fallback"))  # type: ignore[attr-defined]
    service._run_template = lambda context, *, mode_label: calls.append(("template", mode_label))  # type: ignore[attr-defined]
    service.loop_controller = SimpleNamespace(record_success=lambda **kwargs: None)  # type: ignore[attr-defined]

    service.run()  # type: ignore[attr-defined]

    assert calls == [("template", "template")]


def test_template_mode_without_viable_template_can_fallback_to_compiler() -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.generator_mode = "template"  # type: ignore[attr-defined]
    service.sid = "sid-template-fallback-compiler"  # type: ignore[attr-defined]
    service.requirement = {"vuln_id": "CWE-89", "runtime": {"db": "mysql", "allow_external_db": True}}  # type: ignore[attr-defined]
    calls: list[tuple[str, str]] = []

    service._build_context = lambda: _context()  # type: ignore[attr-defined]
    service._ensure_loop_started = lambda: None  # type: ignore[attr-defined]
    service._has_viable_template = lambda: False  # type: ignore[attr-defined]
    service._run_compiler_if_supported = lambda: SimpleNamespace(strategy="sqli_string_concat")  # type: ignore[attr-defined]
    service._run_synthesis_with_loops = lambda context: calls.append(("synthesis", "fallback"))  # type: ignore[attr-defined]
    service._run_template = lambda context, *, mode_label: calls.append(("template", mode_label))  # type: ignore[attr-defined]
    service.loop_controller = SimpleNamespace(
        record_success=lambda **kwargs: calls.append(("compiler", str(kwargs.get("note") or "")))
    )  # type: ignore[attr-defined]

    service.run()  # type: ignore[attr-defined]

    assert calls == [("compiler", "compiler path: sqli_string_concat")]


def test_name_only_mode_dynamic_enables_dynamic_eval_for_name_driven_request() -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "NAME-OPEN-REDIRECT",
        "policy": {"name_only_mode": "dynamic"},
        "request_identity": {"name_driven": True},
    }

    assert service._dynamic_eval_enabled() is True  # type: ignore[attr-defined]


def test_name_only_mode_dynamic_enables_dynamic_eval_from_request_ir_only() -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "CWE-79",
        "policy": {"name_only_mode": "dynamic"},
        "request_ir": {
            "request_label": "Reflected XSS",
            "resolved_vuln_id": "CWE-79",
            "name_driven": True,
            "resolution_state": "token_match",
        },
    }

    assert service._dynamic_eval_enabled() is True  # type: ignore[attr-defined]


def test_name_only_mode_strict_dynamic_disables_lower_bound_fallback() -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "NAME-OPEN-REDIRECT",
        "policy": {
            "name_only_mode": "strict_dynamic",
            "dynamic_eval_allow_lower_bound_fallback": True,
        },
        "request_identity": {"name_driven": True},
    }

    assert service._dynamic_eval_enabled() is True  # type: ignore[attr-defined]
    assert service._dynamic_eval_allow_lower_bound_fallback() is False  # type: ignore[attr-defined]


def test_name_only_mode_strict_dynamic_disables_lower_bound_fallback_from_request_ir_only() -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.requirement = {  # type: ignore[attr-defined]
        "vuln_id": "CWE-79",
        "policy": {
            "name_only_mode": "strict_dynamic",
            "dynamic_eval_allow_lower_bound_fallback": True,
        },
        "request_ir": {
            "request_label": "Reflected XSS",
            "resolved_vuln_id": "CWE-79",
            "name_driven": True,
            "resolution_state": "token_match",
        },
    }

    assert service._dynamic_eval_enabled() is True  # type: ignore[attr-defined]
    assert service._dynamic_eval_allow_lower_bound_fallback() is False  # type: ignore[attr-defined]


def test_write_metadata_records_unified_retry_budget_for_template_plan(tmp_path: Path) -> None:
    service = GeneratorService.__new__(GeneratorService)
    service.sid = "sid-template-meta"  # type: ignore[attr-defined]
    service.metadata_dir = tmp_path  # type: ignore[attr-defined]
    service.runtime_templates_dir = tmp_path / "runtime_templates"  # type: ignore[attr-defined]
    service.variation = {"mode": "deterministic"}  # type: ignore[attr-defined]
    service.loop_index = 1  # type: ignore[attr-defined]
    service.user_deps = []  # type: ignore[attr-defined]
    service.single_attempt = True  # type: ignore[attr-defined]
    service.loop_controller = SimpleNamespace(current_loop=2, max_loops=4)  # type: ignore[attr-defined]
    service._candidate_k = lambda: 3  # type: ignore[attr-defined]
    service._llm_prompt_invocations = {"generator_plan": 1}  # type: ignore[attr-defined]
    service._template_runtime_diagnostics = lambda selection: {  # type: ignore[attr-defined]
        "requested_stack_id": "python/flask",
        "stack_match": True,
        "status": "not_required",
        "reason": "template runtime requirements are satisfied",
    }

    class _LLM:
        def execution_summary(self, observed=False, metadata=None):  # noqa: ANN001
            payload = {
                "attempt_scope": "observed" if observed else "last_call",
                "provider_attempted": False,
                "provider_succeeded": False,
                "stub_fallback": False,
                "fixture_used": False,
                "path_class": "not_executed",
                "cache_mode": "none",
            }
            if isinstance(metadata, dict):
                payload.update(metadata)
            return payload

    service.llm = _LLM()  # type: ignore[attr-defined]

    selection = SimpleNamespace(
        id="flask_sqlite_raw",
        path=tmp_path / "templates" / "flask_sqlite_raw" / "app",
        pattern_id="flask_sqlite_raw",
        stack_id="python/flask",
        language="python",
        framework="flask",
        scenario_type="web-poc",
        requires_external_db=False,
        metadata={"ports": {"app": 5000}},
        service_entry="app.py",
        poc_entry="poc.py",
        service_env={},
    )

    service._write_metadata(  # type: ignore[attr-defined]
        selection,
        [],
        ["app.py", "poc.py"],
        "",
        mode_label="template",
        user_deps_added=[],
    )

    payload = json.loads((tmp_path / "generator_template.json").read_text(encoding="utf-8"))
    llm_execution = payload["llm_execution"]
    assert llm_execution["prompt_contracts"][0]["name"] == "generator_plan"
    assert llm_execution["retry_budget"]["controller_loop_current"] == 2
    assert llm_execution["retry_budget"]["controller_loop_max"] == 4
    assert llm_execution["retry_budget"]["single_attempt_mode"] is True
    assert llm_execution["retry_budget"]["template_plan_actual_runs"] == 1
    assert llm_execution["retry_budget"]["template_selection_candidate_budget"] == 3
