from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_repeatability_report_failures_detect_transient_docker_failure(tmp_path: Path) -> None:
    report_root = tmp_path / "report"
    report_root.mkdir(parents=True, exist_ok=True)
    (report_root / "repeatability_report.json").write_text(
        '{"attempts":[{"error":"CaseError: docker daemon is not reachable"}]}',
        encoding="utf-8",
    )
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_report_failures.sh")!r}
repeatability_report_has_transient_docker_failure {str(report_root)!r}
echo ok
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "ok\n"


def test_repeatability_report_failures_detect_permission_denied_docker_failure(tmp_path: Path) -> None:
    report_root = tmp_path / "report"
    report_root.mkdir(parents=True, exist_ok=True)
    (report_root / "repeatability_report.json").write_text(
        '{"attempts":[{"error":"CaseError: docker daemon permission denied"}]}',
        encoding="utf-8",
    )
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_report_failures.sh")!r}
repeatability_report_has_permission_denied_docker_failure {str(report_root)!r}
echo ok
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "ok\n"


def test_repeatability_report_failures_write_permission_marker(tmp_path: Path) -> None:
    marker_path = tmp_path / "docker_permission_artifact.txt"
    report_path = tmp_path / "repeatability_report.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_report_failures.sh")!r}
repeatability_write_permission_artifact_marker \
  {str(marker_path)!r} \
  alpha-case \
  {str(report_path)!r}
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert marker_path.read_text(encoding="utf-8") == (
        f"case_slug=alpha-case\nreport_path={report_path}\nreason=docker daemon permission denied\n"
    )
