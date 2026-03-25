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
        "requirement_id": "TEST-RUN-CASE",
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


def _write_fake_docker(path: Path) -> None:
    _write_executable(
        path,
        """#!/usr/bin/env python3
import sys
raise SystemExit(0 if len(sys.argv) > 1 and sys.argv[1] == "info" else 0)
""",
    )


def _write_fake_python(path: Path) -> None:
    _write_executable(
        path,
        """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path


def append_capture(entry):
    capture_path = os.environ.get("VULD_RUN_CASE_CAPTURE")
    if not capture_path:
        return
    path = Path(capture_path)
    payload = []
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    payload.append(entry)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


argv = sys.argv[1:]
if argv and argv[0] == "orchestrator/plan.py":
    append_capture({"kind": "plan", "argv": argv})
    raise SystemExit(0)

if argv and argv[0] == "orchestrator/run_pipeline.py":
    sid = argv[argv.index("--sid") + 1]
    mode = argv[argv.index("--mode") + 1]
    append_capture({"kind": "pipeline", "sid": sid, "mode": mode})
    metadata_dir = Path.cwd() / "metadata" / sid
    metadata_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "policy": {"mode": mode},
        "bundles": [
            {
                "vuln_id": "CWE-89",
                "slug": "cwe-89",
                "artifacts": {
                    "eval_result": {"verify_pass": True},
                    "run_summary": {"run_passed": True, "error": None, "network_mode": "bridge", "sidecars": []},
                },
            }
        ],
        "reports": {"evals": {"overall_pass": True}},
    }
    (metadata_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    raise SystemExit(int(os.environ.get("VULD_RUN_CASE_PIPE_RC", "0")))

if argv and argv[0] == "-":
    script = sys.stdin.read()
    if "plan_module.build_plan(norm)" in script:
        append_capture({"kind": "sid-script", "argv": argv})
        sys.stdout.write(os.environ.get("VULD_RUN_CASE_TEST_SID", "sid-test") + "\\n")
        raise SystemExit(0)
    if 'manifest_path = root / f"metadata/{sid}/manifest.json"' in script:
        append_capture({"kind": "summary-script", "argv": argv})
        sid = os.environ["SID"]
        root = Path.cwd()
        manifest = json.loads((root / "metadata" / sid / "manifest.json").read_text(encoding="utf-8"))
        bundles = manifest.get("bundles", [])
        summary = {"sid": sid, "overall_pass": manifest.get("reports", {}).get("evals", {}).get("overall_pass"), "bundle_count": len(bundles)}
        print("[CASE] Summary:", json.dumps(summary, ensure_ascii=False))
        raise SystemExit(0)
    raise SystemExit("unexpected inline python script")

raise SystemExit(f"unexpected python argv: {argv}")
""",
    )


def _run_case_script(tmp_path: Path, *, mode: str = "deterministic", pipe_rc: int = 0) -> subprocess.CompletedProcess[str]:
    req_path = tmp_path / "requirement.yml"
    capture_path = tmp_path / "capture.json"
    docker_path = tmp_path / "fake_docker"
    python_path = tmp_path / "fake_python"
    _write_requirement(req_path)
    _write_fake_docker(docker_path)
    _write_fake_python(python_path)

    env = os.environ.copy()
    env["VULD_RUN_CASE_DOCKER_BIN"] = str(docker_path)
    env["VULD_RUN_CASE_PYTHON_BIN"] = str(python_path)
    env["VULD_RUN_CASE_TEST_SID"] = "sid-run-case"
    env["VULD_RUN_CASE_CAPTURE"] = str(capture_path)
    env["VULD_RUN_CASE_PIPE_RC"] = str(pipe_rc)
    return subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_case.sh"), str(req_path), mode],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )


def test_run_case_supports_override_python_and_docker_bins(tmp_path: Path) -> None:
    completed = _run_case_script(tmp_path, mode="diverse", pipe_rc=0)

    assert completed.returncode == 0, completed.stderr
    assert "[CASE] SID=sid-run-case" in completed.stdout
    assert "[CASE] Artifacts -> artifacts/sid-run-case" in completed.stdout
    capture = json.loads((tmp_path / "capture.json").read_text(encoding="utf-8"))
    assert [entry["kind"] for entry in capture] == ["plan", "sid-script", "pipeline", "summary-script"]
    assert capture[2]["mode"] == "diverse"


def test_run_case_propagates_pipeline_return_code_with_override_bins(tmp_path: Path) -> None:
    completed = _run_case_script(tmp_path, mode="deterministic", pipe_rc=7)

    assert completed.returncode == 7
    assert "[CASE] SID=sid-run-case" in completed.stdout
