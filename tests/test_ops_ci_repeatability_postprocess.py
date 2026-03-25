from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_repeatability_postprocess_runs_loads_dirs_collects_cases_and_writes_summary(tmp_path: Path) -> None:
    run_a = tmp_path / "repeat_alpha_case"
    run_b = tmp_path / "repeat_beta_case"
    run_a.mkdir(parents=True, exist_ok=True)
    run_b.mkdir(parents=True, exist_ok=True)
    (run_a / "docker_permission_artifact.txt").write_text("case_slug=alpha-case\n", encoding="utf-8")
    run_dirs_file = tmp_path / "run_dirs.txt"
    run_dirs_file.write_text(f"{run_a}\n{run_b}\n", encoding="utf-8")
    summary_path = tmp_path / "permission_artifact_summary.json"
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_postprocess.sh")!r}
repeatability_postprocess_runs RUN_DIRS CASES {str(run_dirs_file)!r} docker_permission_artifact.txt {str(summary_path)!r} TEST
python - <<'PY' {str(capture)!r} "${{RUN_DIRS[@]}}" __CASES__ "${{CASES[@]}}"
import json, sys
marker = sys.argv.index("__CASES__")
payload = {{
    "run_dirs": sys.argv[2:marker],
    "cases": sys.argv[marker + 1:],
}}
with open(sys.argv[1], "w", encoding="utf-8") as fh:
    json.dump(payload, fh)
PY
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
        "[TEST] note: docker permission artifact detected for alpha-case; unrestricted Docker-enabled rerun is recommended for runtime-equivalent helper truth"
    ]
    payload = json.loads(capture.read_text(encoding="utf-8"))
    assert payload == {
        "run_dirs": [str(run_a), str(run_b)],
        "cases": ["alpha-case"],
    }
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary == {
        "schema_version": "permission_artifact_summary@0.1",
        "permission_artifact_name": "docker_permission_artifact.txt",
        "permission_artifact_count": 1,
        "runtime_equivalent_helper_truth_available": False,
        "recommended_action": "unrestricted_docker_rerun",
        "permission_artifact_cases": ["alpha-case"],
    }


def test_repeatability_postprocess_runs_supports_empty_permission_case_set(tmp_path: Path) -> None:
    run_a = tmp_path / "repeat_alpha_case"
    run_a.mkdir(parents=True, exist_ok=True)
    run_dirs_file = tmp_path / "run_dirs.txt"
    run_dirs_file.write_text(f"{run_a}\n", encoding="utf-8")
    summary_path = tmp_path / "permission_artifact_summary.json"
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_postprocess.sh")!r}
repeatability_postprocess_runs RUN_DIRS CASES {str(run_dirs_file)!r} docker_permission_artifact.txt {str(summary_path)!r} TEST
python - <<'PY' {str(capture)!r} "${{CASES[@]}}"
import json, sys
with open(sys.argv[1], "w", encoding="utf-8") as fh:
    json.dump({{"cases": sys.argv[2:]}}, fh)
PY
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""
    payload = json.loads(capture.read_text(encoding="utf-8"))
    assert payload == {"cases": []}
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary == {
        "schema_version": "permission_artifact_summary@0.1",
        "permission_artifact_name": "docker_permission_artifact.txt",
        "permission_artifact_count": 0,
        "runtime_equivalent_helper_truth_available": True,
        "recommended_action": "none",
        "permission_artifact_cases": [],
    }


def test_repeatability_postprocess_runs_reuses_run_dir_validation_failures(tmp_path: Path) -> None:
    missing_file = tmp_path / "missing_run_dirs.txt"
    summary_path = tmp_path / "permission_artifact_summary.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_postprocess.sh")!r}
repeatability_postprocess_runs RUN_DIRS CASES {str(missing_file)!r} docker_permission_artifact.txt {str(summary_path)!r} TEST
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == f"[TEST] run dirs file not found: {missing_file}\n"
