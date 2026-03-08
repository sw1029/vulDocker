from __future__ import annotations

from pathlib import Path

from agents.generator.compiler import compile_manifest
from agents.generator.service import GeneratorService

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


def _semantic_profile(strategy: str, *, requested_name: str, normalized_vuln_id: str) -> dict:
    return {
        "requested_name": requested_name,
        "normalized_vuln_id": normalized_vuln_id,
        "compiler_strategy": strategy,
        "compiler_supported": True,
        "scenario_shape": {"service_port": 5000},
        "stack_profile": {"language": "python", "framework": "flask"},
    }


def test_generator_writes_compiler_derived_runtime_rule_for_name_family(tmp_path: Path) -> None:
    if yaml is None:
        raise AssertionError("PyYAML is required for runtime rule serialization tests")

    result = compile_manifest(
        sid="sid-registry-open-redirect",
        requirement={"vuln_id": "NAME-OPEN-REDIRECT", "vuln_name": "Open Redirect"},
        semantic_profile=_semantic_profile(
            "open_redirect_reflect",
            requested_name="Open Redirect",
            normalized_vuln_id="NAME-OPEN-REDIRECT",
        ),
    )
    assert result is not None

    service = GeneratorService.__new__(GeneratorService)
    service.runtime_rules_dir = tmp_path / "runtime_rules"  # type: ignore[attr-defined]
    service.requirement = {"vuln_id": "NAME-OPEN-REDIRECT"}  # type: ignore[attr-defined]
    service._write_compiler_runtime_rule(result)  # type: ignore[attr-defined]

    rule_path = service.runtime_rules_dir / "name-open-redirect.yaml"  # type: ignore[attr-defined]
    payload = yaml.safe_load(rule_path.read_text(encoding="utf-8"))
    assert payload["cwe"] == "NAME-OPEN-REDIRECT"
    assert payload["success_signature"] == "Exploit SUCCESS"
    assert payload["flag_token"] == "FLAG{OPEN_REDIRECT_OK}"
    assert payload["service_entry"] == "app.py"
    assert payload["poc_entry"] == "poc.py"
    assert any(
        entry.get("type") == "file_contains" and entry.get("contains") == "redirect("
        for entry in (payload.get("patterns") or [])
    )
    assert any(
        entry.get("type") == "poc_contains" and entry.get("contains") == "FLAG{OPEN_REDIRECT_OK}"
        for entry in (payload.get("patterns") or [])
    )


def test_open_redirect_registry_manifest_records_scaffold_and_fragment_metadata() -> None:
    result = compile_manifest(
        sid="sid-registry-open-redirect",
        requirement={"vuln_id": "NAME-OPEN-REDIRECT", "vuln_name": "Open Redirect"},
        semantic_profile=_semantic_profile(
            "open_redirect_reflect",
            requested_name="Open Redirect",
            normalized_vuln_id="NAME-OPEN-REDIRECT",
        ),
    )

    assert result is not None
    metadata = result.manifest["metadata"]
    assert metadata["stack_scaffold_id"] == "python/flask"
    assert metadata["stack_scaffold_version"] == "1.0"
    assert metadata["fragment_id"] == "redirect_next_route"
    assert metadata["compose_mode"] == "registry"
    assert result.manifest["poc"]["flag_token"] == "FLAG{OPEN_REDIRECT_OK}"
    service_main = next(item for item in result.manifest["files"] if item["role"] == "service_main")
    assert "next_url = request.args.get('next'" in service_main["content"]


def test_csrf_registry_manifest_records_scaffold_and_fragment_metadata() -> None:
    result = compile_manifest(
        sid="sid-registry-csrf",
        requirement={"vuln_id": "CWE-352", "vuln_name": "CSRF"},
        semantic_profile=_semantic_profile(
            "csrf_missing_token",
            requested_name="CSRF",
            normalized_vuln_id="CWE-352",
        ),
    )

    assert result is not None
    metadata = result.manifest["metadata"]
    assert metadata["stack_scaffold_id"] == "python/flask"
    assert metadata["stack_scaffold_version"] == "1.0"
    assert metadata["fragment_id"] == "csrf_state_change_route"
    assert metadata["compose_mode"] == "registry"
    assert result.manifest["poc"]["flag_token"] == "FLAG-csrf-demo-token"


def test_command_injection_registry_manifest_records_scaffold_and_fragment_metadata() -> None:
    result = compile_manifest(
        sid="sid-registry-cmdi",
        requirement={"vuln_id": "CWE-78", "vuln_name": "Command Injection"},
        semantic_profile=_semantic_profile(
            "command_injection_shell",
            requested_name="Command Injection",
            normalized_vuln_id="CWE-78",
        ),
    )

    assert result is not None
    metadata = result.manifest["metadata"]
    assert metadata["stack_scaffold_id"] == "python/flask"
    assert metadata["stack_scaffold_version"] == "1.0"
    assert metadata["fragment_id"] == "shell_command_exec_route"
    assert metadata["compose_mode"] == "registry"
    service_main = next(item for item in result.manifest["files"] if item["role"] == "service_main")
    assert "subprocess.check_output(cmd, shell=True, text=True)" in service_main["content"]
    assert result.manifest["poc"]["flag_token"] == "FLAG{CMDI_OK}"


def test_sqli_registry_manifest_records_scaffold_and_fragment_metadata() -> None:
    result = compile_manifest(
        sid="sid-registry-sqli",
        requirement={"vuln_id": "CWE-89", "vuln_name": "SQL Injection"},
        semantic_profile=_semantic_profile(
            "sqli_string_concat",
            requested_name="SQL Injection",
            normalized_vuln_id="CWE-89",
        ),
    )

    assert result is not None
    metadata = result.manifest["metadata"]
    assert metadata["stack_scaffold_id"] == "python/flask"
    assert metadata["stack_scaffold_version"] == "1.0"
    assert metadata["fragment_id"] == "login_query_concat_route"
    assert metadata["compose_mode"] == "registry"
    service_main = next(item for item in result.manifest["files"] if item["role"] == "service_main")
    assert "init_db()" in service_main["content"]
    assert result.manifest["poc"]["flag_token"] == "FLAG-sqli-demo-token"


def test_template_injection_registry_manifest_records_scaffold_and_fragment_metadata() -> None:
    result = compile_manifest(
        sid="sid-registry-template",
        requirement={"vuln_id": "NAME-TEMPLATE-INJECTION", "vuln_name": "Template Injection"},
        semantic_profile=_semantic_profile(
            "template_injection_render",
            requested_name="Template Injection",
            normalized_vuln_id="NAME-TEMPLATE-INJECTION",
        ),
    )

    assert result is not None
    metadata = result.manifest["metadata"]
    assert metadata["stack_scaffold_id"] == "python/flask"
    assert metadata["stack_scaffold_version"] == "1.0"
    assert metadata["fragment_id"] == "render_template_string_concat"
    assert metadata["compose_mode"] == "registry"
    assert result.manifest["poc"]["flag_token"] == "FLAG{SSTI_OK}"
    service_main = next(item for item in result.manifest["files"] if item["role"] == "service_main")
    assert "render_template_string(template)" in service_main["content"]


def test_path_traversal_registry_manifest_records_scaffold_fragment_and_extra_files() -> None:
    result = compile_manifest(
        sid="sid-registry-path",
        requirement={"vuln_id": "CWE-22", "vuln_name": "Path Traversal"},
        semantic_profile=_semantic_profile(
            "path_traversal_file_read",
            requested_name="Path Traversal",
            normalized_vuln_id="CWE-22",
        ),
    )

    assert result is not None
    metadata = result.manifest["metadata"]
    assert metadata["stack_scaffold_id"] == "python/flask"
    assert metadata["stack_scaffold_version"] == "1.0"
    assert metadata["fragment_id"] == "file_read_download_route"
    assert metadata["compose_mode"] == "registry"
    paths = {item["path"] for item in result.manifest["files"]}
    assert "secret.txt" in paths
    assert "files/note.txt" in paths


def test_xss_registry_manifest_records_scaffold_and_fragment_metadata() -> None:
    result = compile_manifest(
        sid="sid-registry-xss",
        requirement={"vuln_id": "CWE-79", "vuln_name": "Reflected XSS"},
        semantic_profile=_semantic_profile(
            "xss_reflected",
            requested_name="Reflected XSS",
            normalized_vuln_id="CWE-79",
        ),
    )

    assert result is not None
    metadata = result.manifest["metadata"]
    assert metadata["stack_scaffold_id"] == "python/flask"
    assert metadata["stack_scaffold_version"] == "1.0"
    assert metadata["fragment_id"] == "render_reflect_route"
    assert metadata["compose_mode"] == "registry"
    assert result.manifest["poc"]["flag_token"] == "FLAG{XSS_OK}"
    poc_entry = next(item for item in result.manifest["files"] if item["role"] == "poc_entry")
    assert "<script>alert(1)</script>" in poc_entry["content"]


def test_ssrf_registry_manifest_records_scaffold_and_fragment_metadata() -> None:
    result = compile_manifest(
        sid="sid-registry-ssrf",
        requirement={"vuln_id": "CWE-918", "vuln_name": "SSRF"},
        semantic_profile=_semantic_profile(
            "ssrf_loopback_fetch",
            requested_name="SSRF",
            normalized_vuln_id="CWE-918",
        ),
    )

    assert result is not None
    metadata = result.manifest["metadata"]
    assert metadata["stack_scaffold_id"] == "python/flask"
    assert metadata["stack_scaffold_version"] == "1.0"
    assert metadata["fragment_id"] == "loopback_fetch_route"
    assert metadata["compose_mode"] == "registry"
    service_main = next(item for item in result.manifest["files"] if item["role"] == "service_main")
    assert "http://127.0.0.1:5000/metadata" in service_main["content"]


def test_deserialization_registry_manifest_records_scaffold_and_fragment_metadata() -> None:
    result = compile_manifest(
        sid="sid-registry-deser",
        requirement={"vuln_id": "CWE-502", "vuln_name": "Insecure Deserialization"},
        semantic_profile=_semantic_profile(
            "deserialization_pickle_body",
            requested_name="Insecure Deserialization",
            normalized_vuln_id="CWE-502",
        ),
    )

    assert result is not None
    metadata = result.manifest["metadata"]
    assert metadata["stack_scaffold_id"] == "python/flask"
    assert metadata["stack_scaffold_version"] == "1.0"
    assert metadata["fragment_id"] == "unsafe_pickle_body_route"
    assert metadata["compose_mode"] == "registry"
    service_main = next(item for item in result.manifest["files"] if item["role"] == "service_main")
    assert "init_runtime_state()" in service_main["content"]
    assert result.manifest["poc"]["flag_token"] == "FLAG{DESER_OK}"
