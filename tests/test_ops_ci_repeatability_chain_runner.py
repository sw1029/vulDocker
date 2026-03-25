from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_repeatability_chain_runner_exports_env_invokes_helper_and_postprocesses(
    tmp_path: Path,
) -> None:
    repeat_helper = tmp_path / "repeat_helper.py"
    helper_capture = tmp_path / "helper_capture.json"
    runner_capture = tmp_path / "runner_capture.json"
    output_root = tmp_path / "outputs"

    _write_executable(
        repeat_helper,
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

capture = Path({str(helper_capture)!r})
output_root = Path(os.environ["VULD_REPEAT_CHAIN_OUTPUT_ROOT"])
run_a = output_root / "repeat_alpha"
run_b = output_root / "repeat_beta"
run_a.mkdir(parents=True, exist_ok=True)
run_b.mkdir(parents=True, exist_ok=True)
(run_a / os.environ["VULD_REPEAT_CHAIN_PERMISSION_ARTIFACT_NAME"]).write_text("case_slug=alpha-case\\n", encoding="utf-8")
Path(os.environ["VULD_REPEAT_CHAIN_RUN_DIRS_FILE"]).write_text(f"{{run_a}}\\n{{run_b}}\\n", encoding="utf-8")
capture.write_text(json.dumps({{
    "argv": sys.argv[1:],
    "env": {{
        "VULD_REPEAT_CHAIN_PYTHON_BIN": os.environ.get("VULD_REPEAT_CHAIN_PYTHON_BIN"),
        "VULD_REPEAT_CHAIN_CASES_ROOT": os.environ.get("VULD_REPEAT_CHAIN_CASES_ROOT"),
        "VULD_REPEAT_CHAIN_OUTPUT_ROOT": os.environ.get("VULD_REPEAT_CHAIN_OUTPUT_ROOT"),
        "VULD_REPEAT_CHAIN_MODE": os.environ.get("VULD_REPEAT_CHAIN_MODE"),
        "VULD_REPEAT_CHAIN_ATTEMPTS": os.environ.get("VULD_REPEAT_CHAIN_ATTEMPTS"),
        "VULD_REPEAT_CHAIN_NO_SNAPSHOT": os.environ.get("VULD_REPEAT_CHAIN_NO_SNAPSHOT"),
        "VULD_REPEAT_CHAIN_ALLOW_FAILURE_WITH_REPORT": os.environ.get("VULD_REPEAT_CHAIN_ALLOW_FAILURE_WITH_REPORT"),
        "VULD_REPEAT_CHAIN_PERMISSION_ARTIFACT_NAME": os.environ.get("VULD_REPEAT_CHAIN_PERMISSION_ARTIFACT_NAME"),
        "VULD_REPEAT_CHAIN_DOCKER_RETRY_COUNT": os.environ.get("VULD_REPEAT_CHAIN_DOCKER_RETRY_COUNT"),
        "VULD_REPEAT_CHAIN_DOCKER_RETRY_DELAY_SEC": os.environ.get("VULD_REPEAT_CHAIN_DOCKER_RETRY_DELAY_SEC"),
        "VULD_REPEAT_CHAIN_RUN_DIRS_FILE": os.environ.get("VULD_REPEAT_CHAIN_RUN_DIRS_FILE"),
        "VULD_REPEAT_CHAIN_LOG_PREFIX": os.environ.get("VULD_REPEAT_CHAIN_LOG_PREFIX"),
    }},
}}, ensure_ascii=False), encoding="utf-8")
raise SystemExit(0)
""",
    )

    capture_probe = tmp_path / "capture_probe.sh"
    _write_executable(
        capture_probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_chain_runner.sh")!r}
repeatability_run_helper_and_postprocess RUN_DIRS CASES SUMMARY_OUT {str(repeat_helper)!r} python /tmp/cases {str(output_root)!r} diverse 4 1 1 docker_permission_artifact.txt custom_permission_summary.json 3 0 TEST alpha-case=alpha beta-case=beta
python - <<'PY' {str(runner_capture)!r} "${{RUN_DIRS[@]}}" __CASES__ "${{CASES[@]}}" __SUMMARY__ "${{SUMMARY_OUT}}"
import json
import sys

cases_marker = sys.argv.index("__CASES__")
summary_marker = sys.argv.index("__SUMMARY__")
payload = {{
    "run_dirs": sys.argv[2:cases_marker],
    "cases": sys.argv[cases_marker + 1:summary_marker],
    "summary_out": sys.argv[summary_marker + 1],
}}
with open(sys.argv[1], "w", encoding="utf-8") as fh:
    json.dump(payload, fh)
PY
""",
    )

    completed = subprocess.run(
        ["bash", str(capture_probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == [
        "[TEST] note: docker permission artifact detected for alpha-case; unrestricted Docker-enabled rerun is recommended for runtime-equivalent helper truth"
    ]
    helper_payload = json.loads(helper_capture.read_text(encoding="utf-8"))
    assert helper_payload == {
        "argv": ["alpha-case=alpha", "beta-case=beta"],
        "env": {
            "VULD_REPEAT_CHAIN_PYTHON_BIN": "python",
            "VULD_REPEAT_CHAIN_CASES_ROOT": "/tmp/cases",
            "VULD_REPEAT_CHAIN_OUTPUT_ROOT": str(output_root),
            "VULD_REPEAT_CHAIN_MODE": "diverse",
            "VULD_REPEAT_CHAIN_ATTEMPTS": "4",
            "VULD_REPEAT_CHAIN_NO_SNAPSHOT": "1",
            "VULD_REPEAT_CHAIN_ALLOW_FAILURE_WITH_REPORT": "1",
            "VULD_REPEAT_CHAIN_PERMISSION_ARTIFACT_NAME": "docker_permission_artifact.txt",
            "VULD_REPEAT_CHAIN_DOCKER_RETRY_COUNT": "3",
            "VULD_REPEAT_CHAIN_DOCKER_RETRY_DELAY_SEC": "0",
            "VULD_REPEAT_CHAIN_RUN_DIRS_FILE": str(output_root / "repeat_run_dirs.txt"),
            "VULD_REPEAT_CHAIN_LOG_PREFIX": "TEST",
        },
    }
    runner_payload = json.loads(runner_capture.read_text(encoding="utf-8"))
    assert runner_payload == {
        "run_dirs": [str(output_root / "repeat_alpha"), str(output_root / "repeat_beta")],
        "cases": ["alpha-case"],
        "summary_out": str(output_root / "custom_permission_summary.json"),
    }
    summary = json.loads((output_root / "custom_permission_summary.json").read_text(encoding="utf-8"))
    assert summary == {
        "schema_version": "permission_artifact_summary@0.1",
        "permission_artifact_name": "docker_permission_artifact.txt",
        "permission_artifact_count": 1,
        "runtime_equivalent_helper_truth_available": False,
        "recommended_action": "unrestricted_docker_rerun",
        "permission_artifact_cases": ["alpha-case"],
    }


def test_repeatability_chain_runner_rejects_missing_helper() -> None:
    missing_helper = Path("/tmp/vuld_missing_repeatability_chain_runner_helper.sh")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {str(REPO_ROOT / 'ops/ci/lib_repeatability_chain_runner.sh')!r}\n"
                f"repeatability_run_helper_and_postprocess RUN_DIRS CASES SUMMARY_OUT {str(missing_helper)!r} python /tmp/cases /tmp/out deterministic 2 0 0 docker_permission_artifact.txt permission_artifact_summary.json '' '' TEST alpha-case"
            ),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == f"[TEST] repeat helper not found or not executable: {missing_helper}\n"
