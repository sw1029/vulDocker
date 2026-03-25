from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_operator_matrix_baseline_sequence_exports_matrix_env_and_runtime_surface(
    tmp_path: Path,
) -> None:
    capture = tmp_path / "capture.json"
    sequence_helper = tmp_path / "sequence.py"

    _write_executable(
        sequence_helper,
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
Path({str(capture)!r}).write_text(json.dumps({{
  "argv": sys.argv[1:],
  "matrix_helper": os.environ.get("VULD_NAMED_MATRIX_HELPER"),
  "preset_target_helper": os.environ.get("VULD_NAMED_PRESET_TARGET_HELPER"),
  "retry_count": os.environ.get("VULD_SAMPLE_TARGET_DOCKER_RETRY_COUNT"),
  "retry_delay": os.environ.get("VULD_SAMPLE_TARGET_DOCKER_RETRY_DELAY_SEC"),
  "permission_artifact_name": os.environ.get("VULD_SAMPLE_TARGET_PERMISSION_ARTIFACT_NAME"),
  "permission_summary_name": os.environ.get("VULD_SAMPLE_TARGET_PERMISSION_SUMMARY_NAME"),
}}), encoding="utf-8")
raise SystemExit(0)
""",
    )

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_operator_matrix_baseline_sequence.sh')!r}\n"
                "test_matrix_export() {\n"
                "  export VULD_NAMED_MATRIX_HELPER=\"$1\"\n"
                "  export VULD_NAMED_PRESET_TARGET_HELPER=\"$2\"\n"
                "}\n"
                f"operator_run_matrix_baseline_sequence test_matrix_export /tmp/matrix_helper /tmp/named_matrix_helper 4 0 sample_permission_marker.txt sample_permission_summary.json VULD_SAMPLE_TARGET {str(sequence_helper)!r} TEST-MATRIX 'matrix preview' /tmp/preset_helper build_matrix_pair_case_specs alpha beta"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(capture.read_text(encoding="utf-8")) == {
        "argv": [
            "TEST-MATRIX",
            "matrix preview",
            "/tmp/preset_helper",
            "build_matrix_pair_case_specs",
            "alpha",
            "beta",
        ],
        "matrix_helper": "/tmp/matrix_helper",
        "preset_target_helper": "/tmp/named_matrix_helper",
        "retry_count": "4",
        "retry_delay": "0",
        "permission_artifact_name": "sample_permission_marker.txt",
        "permission_summary_name": "sample_permission_summary.json",
    }


def test_operator_matrix_baseline_sequence_rejects_missing_export_helper() -> None:
    tmp_root = Path("/tmp")
    sequence_helper = tmp_root / "vuldr_matrix_sequence_helper.sh"
    _write_executable(sequence_helper, "#!/usr/bin/env bash\nexit 0\n")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_operator_matrix_baseline_sequence.sh')!r}\n"
                f"operator_run_matrix_baseline_sequence missing_matrix_export /tmp/matrix_helper /tmp/named_matrix_helper 4 0 sample_permission_marker.txt sample_permission_summary.json VULD_SAMPLE_TARGET {str(sequence_helper)!r} TEST-MATRIX 'matrix preview' /tmp/preset_helper build_matrix_pair_case_specs alpha beta"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == "[TEST-MATRIX] matrix export helper not found: missing_matrix_export\n"
