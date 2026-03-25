from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def _write_case(case_dir: Path, *, with_expectations: bool = False) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "requirement.yml").write_text("requirement_id: TEST\n", encoding="utf-8")
    if with_expectations:
        (case_dir / "expectations.json").write_text("{}", encoding="utf-8")


def test_support_workflow_chain_supports_case_root_output_and_python_override(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    _write_case(cases_root / "alpha-case", with_expectations=True)
    _write_case(cases_root / "beta-case")
    output_root = tmp_path / "outputs"
    capture_path = tmp_path / "python_calls.json"
    fake_python = tmp_path / "fake_python.py"

    _write_executable(
        fake_python,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path

capture_path = Path({str(capture_path)!r})
calls = []
if capture_path.exists():
    calls = json.loads(capture_path.read_text(encoding="utf-8"))
calls.append(sys.argv[1:])
capture_path.write_text(json.dumps(calls, ensure_ascii=False), encoding="utf-8")

argv = sys.argv[1:]
if argv and argv[0] == "tests/e2e/repeat_case.py":
    out_dir = Path(argv[argv.index("--output-dir") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "support_candidate.json").write_text(
        json.dumps({{"schema_version": "support_candidate@0.1", "case_name": out_dir.name}}, ensure_ascii=False),
        encoding="utf-8",
    )
    raise SystemExit(0)
if argv and argv[0] == "tests/e2e/support_review.py":
    out_path = Path(argv[argv.index("--output") + 1])
    out_path.write_text(
        json.dumps({{"authority_ready_bundle_count": 2, "reviewable_bundle_count": 0}}, ensure_ascii=False),
        encoding="utf-8",
    )
    raise SystemExit(0)
if argv and argv[0] == "tests/e2e/support_decide.py":
    out_path = Path(argv[argv.index("--output") + 1])
    out_path.write_text(
        json.dumps({{"schema_version": "support_registry_update@0.1", "accepted_count": 0}}, ensure_ascii=False),
        encoding="utf-8",
    )
    raise SystemExit(0)
if argv and argv[0] == "tests/e2e/support_apply.py":
    out_path = Path(argv[argv.index("--output") + 1])
    out_path.write_text(
        json.dumps({{"registry_item_count": 0, "schema_status": "normalized"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    raise SystemExit(0)
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_SUPPORT_WORKFLOW_PYTHON_BIN"] = str(fake_python)
    env["VULD_SUPPORT_WORKFLOW_CASES_ROOT"] = str(cases_root)
    env["VULD_SUPPORT_WORKFLOW_OUTPUT_ROOT"] = str(output_root)

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_support_workflow_chain.sh"),
            "alpha-case",
            "beta-case",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "[SUPPORT] completed" in completed.stdout
    assert (output_root / "repeat_alpha_case" / "support_candidate.json").exists()
    assert (output_root / "repeat_beta_case" / "support_candidate.json").exists()
    assert (output_root / "support_review.json").exists()
    assert (output_root / "support_decisions.json").exists()
    assert (output_root / "support_update.json").exists()
    assert (output_root / "support_registry.json").exists()
    summary = json.loads((output_root / "permission_artifact_summary.json").read_text(encoding="utf-8"))
    assert summary == {
        "schema_version": "permission_artifact_summary@0.1",
        "permission_artifact_name": "docker_permission_artifact.txt",
        "permission_artifact_count": 0,
        "runtime_equivalent_helper_truth_available": True,
        "recommended_action": "none",
        "permission_artifact_cases": [],
    }

    calls = json.loads(capture_path.read_text(encoding="utf-8"))
    assert calls[0][0] == "tests/e2e/repeat_case.py"
    assert calls[0][calls[0].index("--case") + 1] == str(cases_root / "alpha-case")
    assert "--expectations" in calls[0]
    assert calls[1][0] == "tests/e2e/repeat_case.py"
    assert calls[1][calls[1].index("--case") + 1] == str(cases_root / "beta-case")
    assert "--expectations" not in calls[1]
    assert calls[2][0] == "tests/e2e/support_review.py"
    assert calls[3][0] == "tests/e2e/support_decide.py"
    assert calls[4][0] == "tests/e2e/support_apply.py"


def test_support_workflow_chain_supports_review_only(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    _write_case(cases_root / "gamma-case", with_expectations=True)
    output_root = tmp_path / "outputs"
    capture_path = tmp_path / "python_calls.json"
    fake_python = tmp_path / "fake_python.py"

    _write_executable(
        fake_python,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path

capture_path = Path({str(capture_path)!r})
calls = []
if capture_path.exists():
    calls = json.loads(capture_path.read_text(encoding="utf-8"))
calls.append(sys.argv[1:])
capture_path.write_text(json.dumps(calls, ensure_ascii=False), encoding="utf-8")

argv = sys.argv[1:]
if argv and argv[0] == "tests/e2e/repeat_case.py":
    out_dir = Path(argv[argv.index("--output-dir") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "support_candidate.json").write_text(
        json.dumps({{"schema_version": "support_candidate@0.1", "case_name": out_dir.name}}, ensure_ascii=False),
        encoding="utf-8",
    )
    raise SystemExit(0)
if argv and argv[0] == "tests/e2e/support_review.py":
    out_path = Path(argv[argv.index("--output") + 1])
    out_path.write_text(
        json.dumps({{"authority_ready_bundle_count": 1, "reviewable_bundle_count": 0}}, ensure_ascii=False),
        encoding="utf-8",
    )
    raise SystemExit(0)
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_SUPPORT_WORKFLOW_PYTHON_BIN"] = str(fake_python)
    env["VULD_SUPPORT_WORKFLOW_CASES_ROOT"] = str(cases_root)
    env["VULD_SUPPORT_WORKFLOW_OUTPUT_ROOT"] = str(output_root)
    env["VULD_SUPPORT_WORKFLOW_REVIEW_ONLY"] = "1"

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_support_workflow_chain.sh"),
            "gamma-case",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "[SUPPORT] review-only completed" in completed.stdout
    assert (output_root / "repeat_gamma_case" / "support_candidate.json").exists()
    assert (output_root / "support_review.json").exists()
    summary = json.loads((output_root / "permission_artifact_summary.json").read_text(encoding="utf-8"))
    assert summary["permission_artifact_count"] == 0
    assert not (output_root / "support_decisions.json").exists()
    assert not (output_root / "support_update.json").exists()
    assert not (output_root / "support_registry.json").exists()

    calls = json.loads(capture_path.read_text(encoding="utf-8"))
    assert calls[0][0] == "tests/e2e/repeat_case.py"
    assert calls[1][0] == "tests/e2e/support_review.py"
    assert len(calls) == 2


def test_support_workflow_chain_supports_aliases_and_custom_review_output_name(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    _write_case(cases_root / "alpha-case", with_expectations=True)
    _write_case(cases_root / "beta-case", with_expectations=True)
    output_root = tmp_path / "outputs"
    capture_path = tmp_path / "python_calls.json"
    fake_python = tmp_path / "fake_python.py"

    _write_executable(
        fake_python,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path

capture_path = Path({str(capture_path)!r})
calls = []
if capture_path.exists():
    calls = json.loads(capture_path.read_text(encoding="utf-8"))
calls.append(sys.argv[1:])
capture_path.write_text(json.dumps(calls, ensure_ascii=False), encoding="utf-8")

argv = sys.argv[1:]
if argv and argv[0] == "tests/e2e/repeat_case.py":
    out_dir = Path(argv[argv.index("--output-dir") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "support_candidate.json").write_text("{{}}", encoding="utf-8")
    raise SystemExit(0)
if argv and argv[0] == "tests/e2e/support_review.py":
    out_path = Path(argv[argv.index("--output") + 1])
    out_path.write_text("{{}}", encoding="utf-8")
    raise SystemExit(0)
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_SUPPORT_WORKFLOW_PYTHON_BIN"] = str(fake_python)
    env["VULD_SUPPORT_WORKFLOW_CASES_ROOT"] = str(cases_root)
    env["VULD_SUPPORT_WORKFLOW_OUTPUT_ROOT"] = str(output_root)
    env["VULD_SUPPORT_WORKFLOW_REVIEW_ONLY"] = "1"
    env["VULD_SUPPORT_WORKFLOW_REVIEW_OUTPUT_NAME"] = "custom_review.json"
    env["VULD_SUPPORT_WORKFLOW_NO_SNAPSHOT"] = "1"

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_support_workflow_chain.sh"),
            "alpha-case=trusted_dynamic",
            "beta-case=open_redirect_dynamic",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert (output_root / "repeat_trusted_dynamic" / "support_candidate.json").exists()
    assert (output_root / "repeat_open_redirect_dynamic" / "support_candidate.json").exists()
    assert (output_root / "custom_review.json").exists()

    calls = json.loads(capture_path.read_text(encoding="utf-8"))
    assert calls[0][calls[0].index("--output-dir") + 1] == str(output_root / "repeat_trusted_dynamic")
    assert calls[1][calls[1].index("--output-dir") + 1] == str(output_root / "repeat_open_redirect_dynamic")
    assert "--no-snapshot" in calls[0]
    assert "--no-snapshot" in calls[1]
    assert calls[2][-2:] == ["--output", str(output_root / "custom_review.json")]
    assert "review_out=" + str(output_root / "custom_review.json") in completed.stdout


def test_support_workflow_chain_rejects_missing_repeat_run_dir(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    _write_case(cases_root / "alpha-case")
    output_root = tmp_path / "outputs"
    repeat_helper = tmp_path / "repeat_helper.py"

    _write_executable(
        repeat_helper,
        """#!/usr/bin/env python3
import os
from pathlib import Path

run_dirs_file = Path(os.environ["VULD_REPEAT_CHAIN_RUN_DIRS_FILE"])
run_dirs_file.parent.mkdir(parents=True, exist_ok=True)
run_dirs_file.write_text("/tmp/definitely-missing-repeat-run\\n", encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_SUPPORT_WORKFLOW_CASES_ROOT"] = str(cases_root)
    env["VULD_SUPPORT_WORKFLOW_OUTPUT_ROOT"] = str(output_root)
    env["VULD_SUPPORT_WORKFLOW_REPEAT_HELPER"] = str(repeat_helper)
    env["VULD_SUPPORT_WORKFLOW_REVIEW_HELPER"] = "/bin/echo"

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_support_workflow_chain.sh"),
            "alpha-case",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "[SUPPORT] run directory not found: /tmp/definitely-missing-repeat-run" in completed.stderr


def test_support_workflow_chain_rejects_missing_repeat_helper(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    _write_case(cases_root / "alpha-case")
    output_root = tmp_path / "outputs"
    missing_helper = tmp_path / "missing_repeat_helper.sh"

    env = os.environ.copy()
    env["VULD_SUPPORT_WORKFLOW_CASES_ROOT"] = str(cases_root)
    env["VULD_SUPPORT_WORKFLOW_OUTPUT_ROOT"] = str(output_root)
    env["VULD_SUPPORT_WORKFLOW_REPEAT_HELPER"] = str(missing_helper)
    env["VULD_SUPPORT_WORKFLOW_REVIEW_HELPER"] = "/bin/echo"

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_support_workflow_chain.sh"),
            "alpha-case",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == f"[SUPPORT] repeat helper not found or not executable: {missing_helper}\n"


def test_support_workflow_chain_supports_review_helper_override(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    _write_case(cases_root / "alpha-case", with_expectations=True)
    output_root = tmp_path / "outputs"
    capture_path = tmp_path / "review_helper_capture.json"
    fake_python = tmp_path / "fake_python.py"
    fake_review_helper = tmp_path / "review_helper.py"

    _write_executable(
        fake_python,
        """#!/usr/bin/env python3
from pathlib import Path
import sys
argv = sys.argv[1:]
if argv and argv[0] == "tests/e2e/repeat_case.py":
    out_dir = Path(argv[argv.index("--output-dir") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "support_candidate.json").write_text("{}", encoding="utf-8")
raise SystemExit(0)
""",
    )
    _write_executable(
        fake_review_helper,
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
capture = Path({str(capture_path)!r})
capture.write_text(json.dumps({{
    "argv": sys.argv[1:],
    "env": {{
        "VULD_SUPPORT_REVIEW_PYTHON_BIN": os.environ.get("VULD_SUPPORT_REVIEW_PYTHON_BIN"),
        "VULD_SUPPORT_REVIEW_OUTPUT_ROOT": os.environ.get("VULD_SUPPORT_REVIEW_OUTPUT_ROOT"),
        "VULD_SUPPORT_REVIEW_REVIEW_ONLY": os.environ.get("VULD_SUPPORT_REVIEW_REVIEW_ONLY"),
        "VULD_SUPPORT_REVIEW_DECISIONS_FILE": os.environ.get("VULD_SUPPORT_REVIEW_DECISIONS_FILE"),
        "VULD_SUPPORT_REVIEW_REVIEW_OUTPUT_NAME": os.environ.get("VULD_SUPPORT_REVIEW_REVIEW_OUTPUT_NAME"),
        "VULD_SUPPORT_REVIEW_DECISIONS_OUTPUT_NAME": os.environ.get("VULD_SUPPORT_REVIEW_DECISIONS_OUTPUT_NAME"),
        "VULD_SUPPORT_REVIEW_UPDATE_OUTPUT_NAME": os.environ.get("VULD_SUPPORT_REVIEW_UPDATE_OUTPUT_NAME"),
        "VULD_SUPPORT_REVIEW_REGISTRY_OUTPUT_NAME": os.environ.get("VULD_SUPPORT_REVIEW_REGISTRY_OUTPUT_NAME"),
    }},
}}, ensure_ascii=False), encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_SUPPORT_WORKFLOW_PYTHON_BIN"] = str(fake_python)
    env["VULD_SUPPORT_WORKFLOW_CASES_ROOT"] = str(cases_root)
    env["VULD_SUPPORT_WORKFLOW_OUTPUT_ROOT"] = str(output_root)
    env["VULD_SUPPORT_WORKFLOW_REVIEW_ONLY"] = "1"
    env["VULD_SUPPORT_WORKFLOW_REVIEW_OUTPUT_NAME"] = "custom_review.json"
    env["VULD_SUPPORT_WORKFLOW_REVIEW_HELPER"] = str(fake_review_helper)

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_support_workflow_chain.sh"),
            "alpha-case=alias_alpha",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(capture_path.read_text(encoding="utf-8"))
    assert payload["argv"] == [str(output_root / "repeat_alias_alpha")]
    assert payload["env"] == {
        "VULD_SUPPORT_REVIEW_PYTHON_BIN": str(fake_python),
        "VULD_SUPPORT_REVIEW_OUTPUT_ROOT": str(output_root),
        "VULD_SUPPORT_REVIEW_REVIEW_ONLY": "1",
        "VULD_SUPPORT_REVIEW_DECISIONS_FILE": "",
        "VULD_SUPPORT_REVIEW_REVIEW_OUTPUT_NAME": "custom_review.json",
        "VULD_SUPPORT_REVIEW_DECISIONS_OUTPUT_NAME": "support_decisions.json",
        "VULD_SUPPORT_REVIEW_UPDATE_OUTPUT_NAME": "support_update.json",
        "VULD_SUPPORT_REVIEW_REGISTRY_OUTPUT_NAME": "support_registry.json",
    }
    assert "review_out=" + str(output_root / "custom_review.json") in completed.stdout


def test_support_workflow_chain_supports_repeat_helper_override(tmp_path: Path) -> None:
    output_root = tmp_path / "outputs"
    repeat_capture_path = tmp_path / "repeat_helper_capture.json"
    review_capture_path = tmp_path / "review_helper_capture.json"
    fake_repeat_helper = tmp_path / "repeat_helper.py"
    fake_review_helper = tmp_path / "review_helper.py"

    _write_executable(
        fake_repeat_helper,
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
capture = Path({str(repeat_capture_path)!r})
run_dirs_file = Path(os.environ["VULD_REPEAT_CHAIN_RUN_DIRS_FILE"])
output_root = Path(os.environ["VULD_REPEAT_CHAIN_OUTPUT_ROOT"])
repeat_dir = output_root / "repeat_alias_alpha"
repeat_dir.mkdir(parents=True, exist_ok=True)
run_dirs_file.write_text(str(repeat_dir) + "\\n", encoding="utf-8")
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
        "VULD_REPEAT_CHAIN_LOG_PREFIX": os.environ.get("VULD_REPEAT_CHAIN_LOG_PREFIX"),
    }},
}}, ensure_ascii=False), encoding="utf-8")
raise SystemExit(0)
""",
    )
    _write_executable(
        fake_review_helper,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path
Path({str(review_capture_path)!r}).write_text(json.dumps(sys.argv[1:]), encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_SUPPORT_WORKFLOW_REPEAT_HELPER"] = str(fake_repeat_helper)
    env["VULD_SUPPORT_WORKFLOW_REVIEW_HELPER"] = str(fake_review_helper)
    env["VULD_SUPPORT_WORKFLOW_PYTHON_BIN"] = "/tmp/fake_python"
    env["VULD_SUPPORT_WORKFLOW_CASES_ROOT"] = "/tmp/fake_cases"
    env["VULD_SUPPORT_WORKFLOW_OUTPUT_ROOT"] = str(output_root)
    env["VULD_SUPPORT_WORKFLOW_MODE"] = "diverse"
    env["VULD_SUPPORT_WORKFLOW_ATTEMPTS"] = "5"
    env["VULD_SUPPORT_WORKFLOW_NO_SNAPSHOT"] = "1"
    env["VULD_SUPPORT_WORKFLOW_REVIEW_ONLY"] = "1"
    env["VULD_SUPPORT_WORKFLOW_PERMISSION_ARTIFACT_NAME"] = "custom_permission_marker.txt"
    env["VULD_SUPPORT_WORKFLOW_DOCKER_RETRY_COUNT"] = "4"
    env["VULD_SUPPORT_WORKFLOW_DOCKER_RETRY_DELAY_SEC"] = "0"

    completed = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / "ops/ci/run_support_workflow_chain.sh"),
            "alpha-case=alias_alpha",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    repeat_payload = json.loads(repeat_capture_path.read_text(encoding="utf-8"))
    assert repeat_payload["argv"] == ["alpha-case=alias_alpha"]
    assert repeat_payload["env"] == {
        "VULD_REPEAT_CHAIN_PYTHON_BIN": "/tmp/fake_python",
        "VULD_REPEAT_CHAIN_CASES_ROOT": "/tmp/fake_cases",
        "VULD_REPEAT_CHAIN_OUTPUT_ROOT": str(output_root),
        "VULD_REPEAT_CHAIN_MODE": "diverse",
        "VULD_REPEAT_CHAIN_ATTEMPTS": "5",
        "VULD_REPEAT_CHAIN_NO_SNAPSHOT": "1",
        "VULD_REPEAT_CHAIN_ALLOW_FAILURE_WITH_REPORT": "1",
        "VULD_REPEAT_CHAIN_PERMISSION_ARTIFACT_NAME": "custom_permission_marker.txt",
        "VULD_REPEAT_CHAIN_DOCKER_RETRY_COUNT": "4",
        "VULD_REPEAT_CHAIN_DOCKER_RETRY_DELAY_SEC": "0",
        "VULD_REPEAT_CHAIN_LOG_PREFIX": "SUPPORT",
    }
    assert json.loads(review_capture_path.read_text(encoding="utf-8")) == [str(output_root / "repeat_alias_alpha")]


def test_support_workflow_chain_continues_when_repeat_case_writes_report_and_exits_nonzero(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    _write_case(cases_root / "alpha-case", with_expectations=True)
    output_root = tmp_path / "outputs"
    capture_path = tmp_path / "python_calls.json"
    fake_python = tmp_path / "fake_python.py"

    _write_executable(
        fake_python,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path

capture_path = Path({str(capture_path)!r})
calls = json.loads(capture_path.read_text(encoding="utf-8")) if capture_path.exists() else []
calls.append(sys.argv[1:])
capture_path.write_text(json.dumps(calls, ensure_ascii=False), encoding="utf-8")

argv = sys.argv[1:]
if argv and argv[0] == "tests/e2e/repeat_case.py":
    out_dir = Path(argv[argv.index("--output-dir") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "support_candidate.json").write_text("{{}}", encoding="utf-8")
    (out_dir / "repeatability_report.json").write_text('{{"passed": false}}', encoding="utf-8")
    raise SystemExit(1)
if argv and argv[0] == "tests/e2e/support_review.py":
    out_path = Path(argv[argv.index("--output") + 1])
    out_path.write_text("{{}}", encoding="utf-8")
    raise SystemExit(0)
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_SUPPORT_WORKFLOW_PYTHON_BIN"] = str(fake_python)
    env["VULD_SUPPORT_WORKFLOW_CASES_ROOT"] = str(cases_root)
    env["VULD_SUPPORT_WORKFLOW_OUTPUT_ROOT"] = str(output_root)
    env["VULD_SUPPORT_WORKFLOW_REVIEW_ONLY"] = "1"

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_support_workflow_chain.sh"), "alpha-case"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "continuing with recorded report" in completed.stdout
    assert (output_root / "support_review.json").exists()
    calls = json.loads(capture_path.read_text(encoding="utf-8"))
    assert calls[0][0] == "tests/e2e/repeat_case.py"
    assert calls[1][0] == "tests/e2e/support_review.py"


def test_support_workflow_chain_fails_when_repeat_case_exits_nonzero_without_report(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    _write_case(cases_root / "alpha-case", with_expectations=True)
    fake_python = tmp_path / "fake_python.py"

    _write_executable(
        fake_python,
        """#!/usr/bin/env python3
import sys
argv = sys.argv[1:]
if argv and argv[0] == "tests/e2e/repeat_case.py":
    raise SystemExit(1)
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_SUPPORT_WORKFLOW_PYTHON_BIN"] = str(fake_python)
    env["VULD_SUPPORT_WORKFLOW_CASES_ROOT"] = str(cases_root)
    env["VULD_SUPPORT_WORKFLOW_OUTPUT_ROOT"] = str(tmp_path / "outputs")

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_support_workflow_chain.sh"), "alpha-case"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1


def test_support_workflow_chain_surfaces_permission_artifact_note(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    _write_case(cases_root / "alpha-case", with_expectations=True)
    output_root = tmp_path / "outputs"
    capture_path = tmp_path / "python_calls.json"
    fake_python = tmp_path / "fake_python.py"

    _write_executable(
        fake_python,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path

capture_path = Path({str(capture_path)!r})
calls = json.loads(capture_path.read_text(encoding="utf-8")) if capture_path.exists() else []
calls.append(sys.argv[1:])
capture_path.write_text(json.dumps(calls, ensure_ascii=False), encoding="utf-8")

argv = sys.argv[1:]
if argv and argv[0] == "tests/e2e/repeat_case.py":
    out_dir = Path(argv[argv.index("--output-dir") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "support_candidate.json").write_text("{{}}", encoding="utf-8")
    (out_dir / "repeatability_report.json").write_text(
        json.dumps({{
            "passed": False,
            "attempts": [{{"error": "CaseError: docker daemon permission denied"}}],
        }}, ensure_ascii=False),
        encoding="utf-8",
    )
    raise SystemExit(1)
if argv and argv[0] == "tests/e2e/support_review.py":
    out_path = Path(argv[argv.index("--output") + 1])
    out_path.write_text("{{}}", encoding="utf-8")
    raise SystemExit(0)
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_SUPPORT_WORKFLOW_PYTHON_BIN"] = str(fake_python)
    env["VULD_SUPPORT_WORKFLOW_CASES_ROOT"] = str(cases_root)
    env["VULD_SUPPORT_WORKFLOW_OUTPUT_ROOT"] = str(output_root)
    env["VULD_SUPPORT_WORKFLOW_REVIEW_ONLY"] = "1"

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_support_workflow_chain.sh"), "alpha-case"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "docker permission artifact detected for alpha-case" in completed.stdout
    assert (output_root / "repeat_alpha_case" / "docker_permission_artifact.txt").exists()
    assert (output_root / "support_review.json").exists()
    summary = json.loads((output_root / "permission_artifact_summary.json").read_text(encoding="utf-8"))
    assert summary == {
        "schema_version": "permission_artifact_summary@0.1",
        "permission_artifact_name": "docker_permission_artifact.txt",
        "permission_artifact_count": 1,
        "runtime_equivalent_helper_truth_available": False,
        "recommended_action": "unrestricted_docker_rerun",
        "permission_artifact_cases": ["alpha-case"],
    }
    calls = json.loads(capture_path.read_text(encoding="utf-8"))
    assert calls[0][0] == "tests/e2e/repeat_case.py"
    assert calls[1][0] == "tests/e2e/support_review.py"


def test_support_workflow_chain_supports_custom_permission_summary_name(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    _write_case(cases_root / "alpha-case", with_expectations=True)
    output_root = tmp_path / "outputs"
    fake_python = tmp_path / "fake_python.py"

    _write_executable(
        fake_python,
        """#!/usr/bin/env python3
import json
import sys
from pathlib import Path

argv = sys.argv[1:]
if argv and argv[0] == "tests/e2e/repeat_case.py":
    out_dir = Path(argv[argv.index("--output-dir") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "repeatability_report.json").write_text(
        json.dumps({
            "passed": False,
            "attempts": [{"error": "CaseError: docker daemon permission denied"}],
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    raise SystemExit(1)
if argv and argv[0] == "tests/e2e/support_review.py":
    out_path = Path(argv[argv.index("--output") + 1])
    out_path.write_text("{}", encoding="utf-8")
    raise SystemExit(0)
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_SUPPORT_WORKFLOW_PYTHON_BIN"] = str(fake_python)
    env["VULD_SUPPORT_WORKFLOW_CASES_ROOT"] = str(cases_root)
    env["VULD_SUPPORT_WORKFLOW_OUTPUT_ROOT"] = str(output_root)
    env["VULD_SUPPORT_WORKFLOW_REVIEW_ONLY"] = "1"
    env["VULD_SUPPORT_WORKFLOW_PERMISSION_SUMMARY_NAME"] = "custom_permission_summary.json"

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_support_workflow_chain.sh"), "alpha-case"],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "permission_summary_out=" + str(output_root / "custom_permission_summary.json") in completed.stdout
    summary = json.loads((output_root / "custom_permission_summary.json").read_text(encoding="utf-8"))
    assert summary["permission_artifact_count"] == 1
    assert summary["permission_artifact_cases"] == ["alpha-case"]
