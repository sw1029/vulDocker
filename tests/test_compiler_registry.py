from __future__ import annotations

from pathlib import Path

from agents.generator.compiler import compile_manifest
from agents.generator.service import GeneratorService
from common.contracts import compiler_support_summary

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


def _semantic_profile(
    strategy: str,
    *,
    requested_name: str,
    normalized_vuln_id: str,
    framework: str = "flask",
) -> dict:
    return {
        "requested_name": requested_name,
        "normalized_vuln_id": normalized_vuln_id,
        "compiler_strategy": strategy,
        "compiler_supported": True,
        "scenario_shape": {"service_port": 5000},
        "stack_profile": {"language": "python", "framework": framework},
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


def test_generator_writes_stack_aware_compiler_runtime_rule_for_fastapi_name_family(tmp_path: Path) -> None:
    if yaml is None:
        raise AssertionError("PyYAML is required for runtime rule serialization tests")

    result = compile_manifest(
        sid="sid-registry-open-redirect-fastapi",
        requirement={
            "vuln_id": "NAME-OPEN-REDIRECT",
            "vuln_name": "Open Redirect",
            "framework": "fastapi",
        },
        semantic_profile=_semantic_profile(
            "open_redirect_reflect",
            requested_name="Open Redirect",
            normalized_vuln_id="NAME-OPEN-REDIRECT",
            framework="fastapi",
        ),
    )
    assert result is not None

    service = GeneratorService.__new__(GeneratorService)
    service.runtime_rules_dir = tmp_path / "runtime_rules"  # type: ignore[attr-defined]
    service.requirement = {"vuln_id": "NAME-OPEN-REDIRECT"}  # type: ignore[attr-defined]
    service._write_compiler_runtime_rule(result)  # type: ignore[attr-defined]

    rule_path = service.runtime_rules_dir / "name-open-redirect.yaml"  # type: ignore[attr-defined]
    payload = yaml.safe_load(rule_path.read_text(encoding="utf-8"))
    patterns = payload.get("patterns") or []
    assert any(
        entry.get("type") == "file_contains" and entry.get("contains") == "RedirectResponse("
        for entry in patterns
    )
    assert any(
        entry.get("type") == "file_contains" and entry.get("contains") == "next: str = Query("
        for entry in patterns
    )
    assert not any(
        entry.get("type") == "file_contains" and entry.get("contains") == "request.args.get('next'"
        for entry in patterns
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
    assert result.manifest["build"]["command"] == "pip install --no-cache-dir -r requirements.txt"
    assert result.manifest["run"]["command"] == "python app.py"
    assert result.manifest["poc"]["cmd"] == "python poc.py --base-url {{base_url}}"
    assert result.manifest["poc"]["flag_token"] == "FLAG{OPEN_REDIRECT_OK}"
    service_main = next(item for item in result.manifest["files"] if item["role"] == "service_main")
    readme = next(item for item in result.manifest["files"] if item["path"] == "README.md")
    assert "next_url = request.args.get('next'" in service_main["content"]
    assert "python/flask" in readme["content"]
    assert "redirect_next_route" in readme["content"]
    assert "Service behavior: python/flask registry-backed open redirect service." in readme["content"]
    assert "Exploit contract: Registry-backed open redirect PoC." in readme["content"]


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


def test_code_injection_registry_manifest_records_scaffold_and_fragment_metadata() -> None:
    result = compile_manifest(
        sid="sid-registry-codei",
        requirement={"vuln_id": "CWE-94", "vuln_name": "Code Injection"},
        semantic_profile=_semantic_profile(
            "code_injection_eval",
            requested_name="Code Injection",
            normalized_vuln_id="CWE-94",
        ),
    )

    assert result is not None
    metadata = result.manifest["metadata"]
    assert metadata["stack_scaffold_id"] == "python/flask"
    assert metadata["stack_scaffold_version"] == "1.0"
    assert metadata["fragment_id"] == "eval_code_exec_route"
    assert metadata["compose_mode"] == "registry"
    service_main = next(item for item in result.manifest["files"] if item["role"] == "service_main")
    assert "code = request.args.get('code', '21 + 21')" in service_main["content"]
    assert "result = eval(code)" in service_main["content"]
    assert result.manifest["poc"]["flag_token"] == "FLAG{CODEI_OK}"


def test_ldap_injection_registry_manifest_records_scaffold_and_fragment_metadata() -> None:
    result = compile_manifest(
        sid="sid-registry-ldapi",
        requirement={"vuln_id": "NAME-LDAP-INJECTION", "vuln_name": "LDAP Injection"},
        semantic_profile=_semantic_profile(
            "ldap_injection_filter",
            requested_name="LDAP Injection",
            normalized_vuln_id="NAME-LDAP-INJECTION",
        ),
    )

    assert result is not None
    metadata = result.manifest["metadata"]
    assert metadata["stack_scaffold_id"] == "python/flask"
    assert metadata["stack_scaffold_version"] == "1.0"
    assert metadata["fragment_id"] == "ldap_filter_concat_route"
    assert metadata["compose_mode"] == "registry"
    service_main = next(item for item in result.manifest["files"] if item["role"] == "service_main")
    assert "ldap_filter = '(&(uid=' + user + ')(status=active))'" in service_main["content"]
    assert "search_directory(ldap_filter)" in service_main["content"]
    assert result.manifest["poc"]["flag_token"] == "FLAG{LDAPI_OK}"


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


def test_mysql_sqli_registry_manifest_records_external_db_metadata() -> None:
    result = compile_manifest(
        sid="sid-registry-sqli-mysql",
        requirement={
            "vuln_id": "CWE-89",
            "vuln_name": "SQL Injection",
            "pattern_id": "sqli-union-mysql",
            "runtime": {"db": "mysql", "allow_external_db": True},
        },
        semantic_profile=_semantic_profile(
            "sqli_string_concat_mysql",
            requested_name="SQL Injection",
            normalized_vuln_id="CWE-89",
        ),
    )

    assert result is not None
    metadata = result.manifest["metadata"]
    assert metadata["stack_scaffold_id"] == "python/flask"
    assert metadata["stack_scaffold_version"] == "1.0"
    assert metadata["fragment_id"] == "mysql_login_query_concat_route"
    assert metadata["compose_mode"] == "registry"
    assert metadata["requires_external_db"] is True
    assert result.manifest["requires_external_db"] is True
    assert result.manifest["run"]["env"]["DB_HOST"] == "sqli-db"
    assert result.manifest["run"]["env"]["DB_USER"] == "sqli"
    requirements_txt = next(item for item in result.manifest["files"] if item["path"] == "requirements.txt")
    readme = next(item for item in result.manifest["files"] if item["path"] == "README.md")
    assert "mysql-connector-python==8.1.0" in requirements_txt["content"]
    service_main = next(item for item in result.manifest["files"] if item["role"] == "service_main")
    assert "mysql.connector.connect" in service_main["content"]
    assert "missing-db-host" in service_main["content"]
    assert "Runtime assumptions: external service dependency with env contract" in readme["content"]
    assert "DB_HOST" in readme["content"]


def test_mysql_sqli_registry_manifest_uses_catalog_runtime_surface_with_custom_sidecar_values() -> None:
    result = compile_manifest(
        sid="sid-registry-sqli-mysql-custom",
        requirement={
            "vuln_id": "CWE-89",
            "vuln_name": "SQL Injection",
            "pattern_id": "sqli-union-mysql",
            "runtime": {"db": "mysql", "allow_external_db": True, "db_name": "runtime_db"},
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
        },
        semantic_profile=_semantic_profile(
            "sqli_string_concat_mysql",
            requested_name="SQL Injection",
            normalized_vuln_id="CWE-89",
        ),
    )

    assert result is not None
    assert result.manifest["run"]["env"] == {
        "APP_PORT": "5000",
        "DB_HOST": "db-internal",
        "DB_PORT": "3306",
        "DB_USER": "custom_user",
        "DB_PASSWORD": "custom_pw",
        "DB_NAME": "custom_db",
    }


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


def test_open_redirect_fastapi_registry_manifest_uses_second_scaffold() -> None:
    result = compile_manifest(
        sid="sid-registry-open-redirect-fastapi",
        requirement={
            "vuln_id": "NAME-OPEN-REDIRECT",
            "vuln_name": "Open Redirect",
            "language": "python",
            "framework": "fastapi",
        },
        semantic_profile={
            **_semantic_profile(
                "open_redirect_reflect",
                requested_name="Open Redirect",
                normalized_vuln_id="NAME-OPEN-REDIRECT",
            ),
            "stack_profile": {"language": "python", "framework": "fastapi"},
        },
    )

    assert result is not None
    metadata = result.manifest["metadata"]
    assert metadata["stack_scaffold_id"] == "python/fastapi"
    assert metadata["fragment_id"] == "redirect_next_route_fastapi"
    service_main = next(item for item in result.manifest["files"] if item["role"] == "service_main")
    poc = next(item for item in result.manifest["files"] if item["role"] == "poc_entry")
    assert "from fastapi import FastAPI, Query" in service_main["content"]
    assert "RedirectResponse(url=next, status_code=302)" in service_main["content"]
    assert "Open Redirect compiler PoC (FastAPI)" in poc["content"]
    assert "[open-redirect-fastapi-compiler]" in poc["content"]


def test_compiler_support_summary_is_framework_aware_for_second_scaffold() -> None:
    open_redirect_fastapi = compiler_support_summary(
        "NAME-OPEN-REDIRECT",
        {"language": "python", "framework": "fastapi"},
    )
    template_injection_fastapi = compiler_support_summary(
        "NAME-TEMPLATE-INJECTION",
        {"language": "python", "framework": "fastapi"},
    )
    sqli_fastapi = compiler_support_summary(
        "CWE-89",
        {"language": "python", "framework": "fastapi"},
    )
    xss_fastapi = compiler_support_summary(
        "CWE-79",
        {"language": "python", "framework": "fastapi"},
    )
    ssrf_fastapi = compiler_support_summary(
        "CWE-918",
        {"language": "python", "framework": "fastapi"},
    )

    assert open_redirect_fastapi["compiler_supported"] is True
    assert open_redirect_fastapi["compiler_strategy"] == "open_redirect_reflect"
    assert template_injection_fastapi["compiler_supported"] is True
    assert template_injection_fastapi["compiler_strategy"] == "template_injection_render"
    path_traversal_fastapi = compiler_support_summary(
        "CWE-22",
        {"language": "python", "framework": "fastapi"},
    )
    assert path_traversal_fastapi["compiler_supported"] is True
    assert path_traversal_fastapi["compiler_strategy"] == "path_traversal_file_read"
    assert xss_fastapi["compiler_supported"] is True
    assert xss_fastapi["compiler_strategy"] == "xss_reflected"
    assert ssrf_fastapi["compiler_supported"] is True
    assert ssrf_fastapi["compiler_strategy"] == "ssrf_loopback_fetch"
    assert sqli_fastapi["compiler_supported"] is False
    assert sqli_fastapi["compiler_reason"] == "compiler scaffold registry not implemented"


def test_path_traversal_fastapi_registry_manifest_uses_second_scaffold() -> None:
    result = compile_manifest(
        sid="sid-registry-path-traversal-fastapi",
        requirement={
            "vuln_id": "CWE-22",
            "vuln_name": "Path Traversal",
            "language": "python",
            "framework": "fastapi",
        },
        semantic_profile={
            **_semantic_profile(
                "path_traversal_file_read",
                requested_name="Path Traversal",
                normalized_vuln_id="CWE-22",
            ),
            "stack_profile": {"language": "python", "framework": "fastapi"},
        },
    )

    assert result is not None
    metadata = result.manifest["metadata"]
    assert metadata["stack_scaffold_id"] == "python/fastapi"
    assert metadata["fragment_id"] == "file_read_download_route_fastapi"
    service_main = next(item for item in result.manifest["files"] if item["role"] == "service_main")
    poc = next(item for item in result.manifest["files"] if item["role"] == "poc_entry")
    assert "from fastapi import FastAPI, Query" in service_main["content"]
    assert "target = BASE_DIR / path" in service_main["content"]
    assert "Path Traversal compiler PoC (FastAPI)" in poc["content"]
    assert "[path-traversal-fastapi-compiler]" in poc["content"]


def test_template_injection_fastapi_registry_manifest_uses_second_scaffold() -> None:
    result = compile_manifest(
        sid="sid-registry-template-fastapi",
        requirement={
            "vuln_id": "NAME-TEMPLATE-INJECTION",
            "vuln_name": "Template Injection",
            "language": "python",
            "framework": "fastapi",
        },
        semantic_profile={
            **_semantic_profile(
                "template_injection_render",
                requested_name="Template Injection",
                normalized_vuln_id="NAME-TEMPLATE-INJECTION",
            ),
            "stack_profile": {"language": "python", "framework": "fastapi"},
        },
    )

    assert result is not None
    metadata = result.manifest["metadata"]
    assert metadata["stack_scaffold_id"] == "python/fastapi"
    assert metadata["fragment_id"] == "render_jinja_template_fastapi"
    service_main = next(item for item in result.manifest["files"] if item["role"] == "service_main")
    poc = next(item for item in result.manifest["files"] if item["role"] == "poc_entry")
    assert "from fastapi import FastAPI, Query" in service_main["content"]
    assert "template = Template('<h1>Hello ' + name + '</h1>')" in service_main["content"]
    assert "return HTMLResponse(template.render())" in service_main["content"]
    assert "Template Injection compiler PoC (FastAPI)" in poc["content"]
    assert "[template-injection-fastapi-compiler]" in poc["content"]


def test_xss_fastapi_registry_manifest_uses_second_scaffold() -> None:
    result = compile_manifest(
        sid="sid-registry-xss-fastapi",
        requirement={
            "vuln_id": "CWE-79",
            "vuln_name": "Reflected XSS",
            "language": "python",
            "framework": "fastapi",
        },
        semantic_profile={
            **_semantic_profile(
                "xss_reflected",
                requested_name="Reflected XSS",
                normalized_vuln_id="CWE-79",
            ),
            "stack_profile": {"language": "python", "framework": "fastapi"},
        },
    )

    assert result is not None
    metadata = result.manifest["metadata"]
    assert metadata["stack_scaffold_id"] == "python/fastapi"
    assert metadata["fragment_id"] == "render_reflect_route_fastapi"
    service_main = next(item for item in result.manifest["files"] if item["role"] == "service_main")
    poc = next(item for item in result.manifest["files"] if item["role"] == "poc_entry")
    assert "from fastapi import FastAPI, Query" in service_main["content"]
    assert "return HTMLResponse(\"<div class='result'>\" + name + \"</div>\")" in service_main["content"]
    assert "Reflected XSS compiler PoC (FastAPI)" in poc["content"]
    assert "[xss-fastapi-compiler]" in poc["content"]


def test_ssrf_fastapi_registry_manifest_uses_second_scaffold() -> None:
    result = compile_manifest(
        sid="sid-registry-ssrf-fastapi",
        requirement={
            "vuln_id": "CWE-918",
            "vuln_name": "SSRF",
            "language": "python",
            "framework": "fastapi",
        },
        semantic_profile={
            **_semantic_profile(
                "ssrf_loopback_fetch",
                requested_name="SSRF",
                normalized_vuln_id="CWE-918",
            ),
            "stack_profile": {"language": "python", "framework": "fastapi"},
        },
    )

    assert result is not None
    metadata = result.manifest["metadata"]
    assert metadata["stack_scaffold_id"] == "python/fastapi"
    assert metadata["fragment_id"] == "loopback_fetch_route_fastapi"
    service_main = next(item for item in result.manifest["files"] if item["role"] == "service_main")
    poc = next(item for item in result.manifest["files"] if item["role"] == "poc_entry")
    assert "from fastapi import FastAPI, Query" in service_main["content"]
    assert "resp = requests.get(url, timeout=2)" in service_main["content"]
    assert "return Response(" in service_main["content"]
    assert "SSRF compiler PoC (FastAPI)" in poc["content"]
    assert "[ssrf-fastapi-compiler]" in poc["content"]


def test_xxe_registry_manifest_records_scaffold_fragment_and_extra_files() -> None:
    result = compile_manifest(
        sid="sid-registry-xxe",
        requirement={"vuln_id": "NAME-XXE", "vuln_name": "XML External Entity"},
        semantic_profile=_semantic_profile(
            "xxe_xml_entity_resolve",
            requested_name="XML External Entity",
            normalized_vuln_id="NAME-XXE",
        ),
    )

    assert result is not None
    metadata = result.manifest["metadata"]
    assert metadata["stack_scaffold_id"] == "python/flask"
    assert metadata["stack_scaffold_version"] == "1.0"
    assert metadata["fragment_id"] == "xxe_local_file_entity_route"
    assert metadata["compose_mode"] == "registry"
    assert result.manifest["poc"]["flag_token"] == "FLAG{XXE_OK}"
    service_main = next(item for item in result.manifest["files"] if item["role"] == "service_main")
    assert "etree.XMLParser(load_dtd=True, resolve_entities=True, no_network=False)" in service_main["content"]
    assert "root = etree.fromstring(xml_body, parser=parser)" in service_main["content"]
    requirements_txt = next(item for item in result.manifest["files"] if item["path"] == "requirements.txt")
    assert "lxml==5.2.1" in requirements_txt["content"]
    paths = {item["path"] for item in result.manifest["files"]}
    assert "secret.txt" in paths


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
