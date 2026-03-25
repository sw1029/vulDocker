from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_repeatability_case_failure_returns_retry_for_transient_docker_report(tmp_path: Path) -> None:
    report_root = tmp_path / "report"
    report_root.mkdir(parents=True, exist_ok=True)
    report_path = report_root / "repeatability_report.json"
    report_path.write_text(
        '{"attempts":[{"error":"CaseError: docker daemon is not reachable"}]}',
        encoding="utf-8",
    )
    capture = tmp_path / "capture.txt"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_case_failure.sh")!r}
ACTION=""
repeatability_resolve_case_failure_action \
  ACTION \
  TEST \
  alpha-case \
  {str(report_root)!r} \
  {str(report_path)!r} \
  1 \
  0 \
  2 \
  0 \
  docker_permission_artifact.txt
printf '%s' "${{ACTION}}" > {str(capture)!r}
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert capture.read_text(encoding="utf-8") == "retry"


def test_repeatability_case_failure_continues_with_permission_denied_report_and_writes_marker(
    tmp_path: Path,
) -> None:
    report_root = tmp_path / "report"
    report_root.mkdir(parents=True, exist_ok=True)
    report_path = report_root / "repeatability_report.json"
    report_path.write_text(
        '{"attempts":[{"error":"CaseError: docker daemon permission denied"}]}',
        encoding="utf-8",
    )
    marker_name = "custom_permission_marker.txt"
    capture = tmp_path / "capture.txt"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_case_failure.sh")!r}
ACTION=""
repeatability_resolve_case_failure_action \
  ACTION \
  TEST \
  alpha-case \
  {str(report_root)!r} \
  {str(report_path)!r} \
  1 \
  1 \
  2 \
  0 \
  {marker_name!r}
printf '%s' "${{ACTION}}" > {str(capture)!r}
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert capture.read_text(encoding="utf-8") == "continue"
    assert "reported docker daemon permission denied; continuing with recorded report" in completed.stdout
    assert (report_root / marker_name).read_text(encoding="utf-8") == (
        f"case_slug=alpha-case\nreport_path={report_path}\nreason=docker daemon permission denied\n"
    )


def test_repeatability_case_failure_continues_with_generic_report_when_allowed(tmp_path: Path) -> None:
    report_root = tmp_path / "report"
    report_root.mkdir(parents=True, exist_ok=True)
    report_path = report_root / "repeatability_report.json"
    report_path.write_text('{"passed": false}', encoding="utf-8")
    capture = tmp_path / "capture.txt"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_case_failure.sh")!r}
ACTION=""
repeatability_resolve_case_failure_action \
  ACTION \
  TEST \
  alpha-case \
  {str(report_root)!r} \
  {str(report_path)!r} \
  7 \
  1 \
  2 \
  0 \
  docker_permission_artifact.txt
printf '%s' "${{ACTION}}" > {str(capture)!r}
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert capture.read_text(encoding="utf-8") == "continue"
    assert "repeat alpha-case returned 7, continuing with recorded report" in completed.stdout


def test_repeatability_case_failure_returns_fail_when_report_cannot_be_used(tmp_path: Path) -> None:
    report_root = tmp_path / "report"
    report_root.mkdir(parents=True, exist_ok=True)
    report_path = report_root / "missing_report.json"
    capture = tmp_path / "capture.txt"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_case_failure.sh")!r}
ACTION=""
repeatability_resolve_case_failure_action \
  ACTION \
  TEST \
  alpha-case \
  {str(report_root)!r} \
  {str(report_path)!r} \
  1 \
  0 \
  2 \
  2 \
  docker_permission_artifact.txt
printf '%s' "${{ACTION}}" > {str(capture)!r}
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert capture.read_text(encoding="utf-8") == "fail"
    assert completed.stdout == ""
