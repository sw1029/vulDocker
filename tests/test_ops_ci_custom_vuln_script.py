from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _write_base_requirement(path: Path) -> None:
    payload = {
        "requirement_id": "TEST-CUSTOM-BASE",
        "vuln_id": "CWE-89",
        "language": "python",
        "framework": "flask",
        "seed": 1000,
        "retriever_commit": "stub",
        "corpus_snapshot": "rag-snap-mvp",
        "pattern_id": "sqli-string-concat",
        "deps_digest": "sha256:placeholder",
        "base_image_digest": "sha256:python311",
        "runtime": {"base_image": "python:3.11-slim", "package_manager": "pip"},
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _prepare_fake_runner(tmp_path: Path) -> Path:
    capture_path = tmp_path / "runner_capture.json"
    runner_path = tmp_path / "fake_run_case.sh"
    _write_executable(
        runner_path,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path
import yaml

req_path = Path(sys.argv[1])
mode = sys.argv[2] if len(sys.argv) > 2 else "deterministic"
payload = yaml.safe_load(req_path.read_text(encoding="utf-8")) or {{}}
capture = {{
    "req_path": str(req_path),
    "mode": mode,
    "payload": payload,
}}
Path({str(capture_path)!r}).write_text(json.dumps(capture, ensure_ascii=False), encoding="utf-8")
raise SystemExit(0)
""",
    )
    return capture_path


def _run_custom_script(tmp_path: Path, *args: str) -> dict:
    capture_path = _prepare_fake_runner(tmp_path)
    base_req = tmp_path / "base_requirement.yml"
    _write_base_requirement(base_req)
    env = os.environ.copy()
    env["VULD_CUSTOM_RUN_CASE_SCRIPT"] = str(tmp_path / "fake_run_case.sh")
    env["VULD_CUSTOM_BASE_REQUIREMENT_FILE"] = str(base_req)
    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_custom_vuln_example.sh"), *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(capture_path.read_text(encoding="utf-8"))


def test_run_custom_vuln_example_supports_csv_shorthand_mode(tmp_path: Path) -> None:
    captured = _run_custom_script(tmp_path, "CWE-22,CWE-94", "diverse")
    payload = captured["payload"]

    assert captured["mode"] == "diverse"
    assert payload["vuln_ids"] == ["CWE-22", "CWE-94"]
    assert payload["multi_vuln"] is True
    assert payload["intent"] == "Custom multi vulnerability run for CWE-22, CWE-94"
    assert payload["requirement_id"].startswith("CUSTOM-MULTI-CWE-22-CWE-94-")
    assert "vuln_id" not in payload


def test_run_custom_vuln_example_supports_multiple_args_and_mode_flag(tmp_path: Path) -> None:
    captured = _run_custom_script(tmp_path, "CWE-22", "CWE-79", "--mode", "deterministic")
    payload = captured["payload"]

    assert captured["mode"] == "deterministic"
    assert payload["vuln_ids"] == ["CWE-22", "CWE-79"]
    assert payload["multi_vuln"] is True
    assert payload["intent"] == "Custom multi vulnerability run for CWE-22, CWE-79"


def test_run_custom_vuln_example_supports_single_vuln_default_mode(tmp_path: Path) -> None:
    captured = _run_custom_script(tmp_path, "CWE-22")
    payload = captured["payload"]

    assert captured["mode"] == "deterministic"
    assert payload["vuln_id"] == "CWE-22"
    assert "vuln_ids" not in payload
    assert payload["intent"] == "Custom single vulnerability run for CWE-22"
    assert payload["requirement_id"].startswith("CUSTOM-CWE-22-")


def test_run_custom_vuln_example_supports_base_requirement_override(tmp_path: Path) -> None:
    capture_path = _prepare_fake_runner(tmp_path)
    base_req = tmp_path / "custom_base_requirement.yml"
    _write_base_requirement(base_req)
    env = os.environ.copy()
    env["VULD_CUSTOM_RUN_CASE_SCRIPT"] = str(tmp_path / "fake_run_case.sh")
    env["VULD_CUSTOM_BASE_REQUIREMENT_FILE"] = str(base_req)
    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_custom_vuln_example.sh"), "CWE-352"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    captured = json.loads(capture_path.read_text(encoding="utf-8"))
    payload = captured["payload"]
    assert payload["vuln_id"] == "CWE-352"
    assert payload["language"] == "python"
    assert payload["runtime"]["base_image"] == "python:3.11-slim"
