from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_support_review_output_notes_emit_completion_and_outputs(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_support_review_output_notes.sh")!r}
support_review_emit_completion_and_outputs \
  "SUPPORT-REVIEW" \
  "completed" \
  "review_out" "/tmp/review.json" \
  "update_out" "/tmp/update.json" \
  "registry_out" "/tmp/registry.json"
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == [
        "[SUPPORT-REVIEW] completed",
        "[SUPPORT-REVIEW] review_out=/tmp/review.json",
        "[SUPPORT-REVIEW] update_out=/tmp/update.json",
        "[SUPPORT-REVIEW] registry_out=/tmp/registry.json",
    ]


def test_support_review_output_notes_require_even_pairs(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_support_review_output_notes.sh")!r}
support_review_emit_output_pairs "SUPPORT-REVIEW" "review_out"
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr.strip() == "support review output note pairs are required"


def test_support_review_output_notes_emit_review_only_completion(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_support_review_output_notes.sh")!r}
support_review_emit_review_only_completion \
  "SUPPORT" \
  "/tmp/review.json" \
  "permission_summary_out" "/tmp/permission_summary.json"
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == [
        "[SUPPORT] review-only completed",
        "[SUPPORT] review_out=/tmp/review.json",
        "[SUPPORT] permission_summary_out=/tmp/permission_summary.json",
    ]


def test_support_review_output_notes_emit_standard_completion(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_support_review_output_notes.sh")!r}
support_review_emit_standard_completion \
  "SUPPORT" \
  "/tmp/review.json" \
  "/tmp/update.json" \
  "/tmp/registry.json" \
  "permission_summary_out" "/tmp/permission_summary.json"
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == [
        "[SUPPORT] completed",
        "[SUPPORT] review_out=/tmp/review.json",
        "[SUPPORT] update_out=/tmp/update.json",
        "[SUPPORT] registry_out=/tmp/registry.json",
        "[SUPPORT] permission_summary_out=/tmp/permission_summary.json",
    ]


def test_support_review_output_notes_emit_reviewable_accept_completion(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_support_review_output_notes.sh")!r}
support_review_emit_reviewable_accept_completion \
  "REVIEWABLE" \
  "/tmp/review_index.json" \
  "/tmp/registry_update.json" \
  "/tmp/registry.json"
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == [
        "[REVIEWABLE] completed",
        "[REVIEWABLE] review_index=/tmp/review_index.json",
        "[REVIEWABLE] registry_update=/tmp/registry_update.json",
        "[REVIEWABLE] registry=/tmp/registry.json",
    ]


def test_support_review_output_notes_emit_resolved_review_only_completion(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
export VULD_SUPPORT_REVIEW_RESOLVED_REVIEW_OUT=/tmp/review.json
source {str(REPO_ROOT / "ops/ci/lib_support_review_output_notes.sh")!r}
support_review_emit_resolved_review_only_completion \
  "SUPPORT" \
  "permission_summary_out" "/tmp/permission_summary.json"
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == [
        "[SUPPORT] review-only completed",
        "[SUPPORT] review_out=/tmp/review.json",
        "[SUPPORT] permission_summary_out=/tmp/permission_summary.json",
    ]


def test_support_review_output_notes_emit_resolved_standard_completion(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
export VULD_SUPPORT_REVIEW_RESOLVED_REVIEW_OUT=/tmp/review.json
export VULD_SUPPORT_REVIEW_RESOLVED_UPDATE_OUT=/tmp/update.json
export VULD_SUPPORT_REVIEW_RESOLVED_REGISTRY_OUT=/tmp/registry.json
source {str(REPO_ROOT / "ops/ci/lib_support_review_output_notes.sh")!r}
support_review_emit_resolved_standard_completion \
  "SUPPORT" \
  "permission_summary_out" "/tmp/permission_summary.json"
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == [
        "[SUPPORT] completed",
        "[SUPPORT] review_out=/tmp/review.json",
        "[SUPPORT] update_out=/tmp/update.json",
        "[SUPPORT] registry_out=/tmp/registry.json",
        "[SUPPORT] permission_summary_out=/tmp/permission_summary.json",
    ]


def test_support_review_output_notes_emit_resolved_reviewable_accept_completion(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
export VULD_SUPPORT_REVIEW_RESOLVED_REVIEW_OUT=/tmp/review_index.json
export VULD_SUPPORT_REVIEW_RESOLVED_UPDATE_OUT=/tmp/registry_update.json
export VULD_SUPPORT_REVIEW_RESOLVED_REGISTRY_OUT=/tmp/registry.json
source {str(REPO_ROOT / "ops/ci/lib_support_review_output_notes.sh")!r}
support_review_emit_resolved_reviewable_accept_completion "REVIEWABLE"
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == [
        "[REVIEWABLE] completed",
        "[REVIEWABLE] review_index=/tmp/review_index.json",
        "[REVIEWABLE] registry_update=/tmp/registry_update.json",
        "[REVIEWABLE] registry=/tmp/registry.json",
    ]


def test_support_review_output_notes_emit_prefixed_review_only_completion(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
export TEST_PREFIX_RESOLVED_REVIEW_OUT=/tmp/review.json
source {str(REPO_ROOT / "ops/ci/lib_support_review_output_notes.sh")!r}
support_review_emit_prefixed_review_only_completion \
  "SUPPORT" \
  "TEST_PREFIX" \
  "permission_summary_out" "/tmp/permission_summary.json"
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == [
        "[SUPPORT] review-only completed",
        "[SUPPORT] review_out=/tmp/review.json",
        "[SUPPORT] permission_summary_out=/tmp/permission_summary.json",
    ]


def test_support_review_output_notes_emit_prefixed_standard_completion(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
export TEST_PREFIX_RESOLVED_REVIEW_OUT=/tmp/review.json
export TEST_PREFIX_RESOLVED_UPDATE_OUT=/tmp/update.json
export TEST_PREFIX_RESOLVED_REGISTRY_OUT=/tmp/registry.json
source {str(REPO_ROOT / "ops/ci/lib_support_review_output_notes.sh")!r}
support_review_emit_prefixed_standard_completion \
  "SUPPORT" \
  "TEST_PREFIX" \
  "permission_summary_out" "/tmp/permission_summary.json"
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == [
        "[SUPPORT] completed",
        "[SUPPORT] review_out=/tmp/review.json",
        "[SUPPORT] update_out=/tmp/update.json",
        "[SUPPORT] registry_out=/tmp/registry.json",
        "[SUPPORT] permission_summary_out=/tmp/permission_summary.json",
    ]


def test_support_review_output_notes_emit_prefixed_reviewable_accept_completion(
    tmp_path: Path,
) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
export TEST_PREFIX_RESOLVED_REVIEW_OUT=/tmp/review_index.json
export TEST_PREFIX_RESOLVED_UPDATE_OUT=/tmp/registry_update.json
export TEST_PREFIX_RESOLVED_REGISTRY_OUT=/tmp/registry.json
source {str(REPO_ROOT / "ops/ci/lib_support_review_output_notes.sh")!r}
support_review_emit_prefixed_reviewable_accept_completion "REVIEWABLE" "TEST_PREFIX"
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == [
        "[REVIEWABLE] completed",
        "[REVIEWABLE] review_index=/tmp/review_index.json",
        "[REVIEWABLE] registry_update=/tmp/registry_update.json",
        "[REVIEWABLE] registry=/tmp/registry.json",
    ]
