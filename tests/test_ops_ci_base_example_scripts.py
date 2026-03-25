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


def _write_requirement(path: Path) -> None:
    payload = {
        "requirement_id": "TEST-BASE-REQ",
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


def test_run_base_example_supports_default_mode_and_overrides(tmp_path: Path) -> None:
    capture_path = tmp_path / "base_capture.json"
    runner_path = tmp_path / "fake_run_case.py"
    req_path = tmp_path / "base_requirement.yml"
    _write_requirement(req_path)
    _write_executable(
        runner_path,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path
import yaml

req_path = Path(sys.argv[1])
mode = sys.argv[2] if len(sys.argv) > 2 else ""
payload = yaml.safe_load(req_path.read_text(encoding="utf-8")) or {{}}
Path({str(capture_path)!r}).write_text(
    json.dumps({{"req_path": str(req_path), "mode": mode, "payload": payload}}, ensure_ascii=False),
    encoding="utf-8",
)
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_BASE_REQUIREMENT_FILE"] = str(req_path)
    env["VULD_BASE_RUN_CASE_SCRIPT"] = str(runner_path)
    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_base_example.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    captured = json.loads(capture_path.read_text(encoding="utf-8"))
    assert captured["req_path"] == str(req_path)
    assert captured["mode"] == "deterministic"
    assert captured["payload"]["requirement_id"] == "TEST-BASE-REQ"


def test_run_base_example_supports_explicit_mode(tmp_path: Path) -> None:
    capture_path = tmp_path / "base_capture.json"
    runner_path = tmp_path / "fake_run_case.py"
    req_path = tmp_path / "base_requirement.yml"
    _write_requirement(req_path)
    _write_executable(
        runner_path,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path

Path({str(capture_path)!r}).write_text(
    json.dumps({{"mode": sys.argv[2]}}, ensure_ascii=False),
    encoding="utf-8",
)
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_BASE_REQUIREMENT_FILE"] = str(req_path)
    env["VULD_BASE_RUN_CASE_SCRIPT"] = str(runner_path)
    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_base_example.sh"), "diverse"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    captured = json.loads(capture_path.read_text(encoding="utf-8"))
    assert captured["mode"] == "diverse"


def test_run_base_examples_forwards_args_to_override_script(tmp_path: Path) -> None:
    capture_path = tmp_path / "base_examples_capture.json"
    wrapper_path = tmp_path / "fake_base_example.py"
    _write_executable(
        wrapper_path,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path

Path({str(capture_path)!r}).write_text(
    json.dumps({{"argv": sys.argv[1:]}}, ensure_ascii=False),
    encoding="utf-8",
)
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_BASE_EXAMPLE_SCRIPT"] = str(wrapper_path)
    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_base_examples.sh"), "diverse"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    captured = json.loads(capture_path.read_text(encoding="utf-8"))
    assert captured["argv"] == ["diverse"]
