from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def _write_case(case_dir: Path) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "requirement.yml").write_text("requirement_id: TEST\n", encoding="utf-8")
    (case_dir / "expectations.json").write_text("{}", encoding="utf-8")


def test_positive_direct_validation_supports_case_root_output_and_python_override(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    _write_case(cases_root / "trusted-dynamic-sqli")
    _write_case(cases_root / "open-redirect-dynamic-name-only")
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
if argv and argv[0] == "tests/e2e/run_case.py":
    out_dir = Path(argv[argv.index("--output-dir") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps({{"ok": True}}, ensure_ascii=False), encoding="utf-8")
    raise SystemExit(0)
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_POSITIVE_DIRECT_PYTHON_BIN"] = str(fake_python)
    env["VULD_POSITIVE_DIRECT_CASES_ROOT"] = str(cases_root)
    env["VULD_POSITIVE_DIRECT_OUTPUT_ROOT"] = str(output_root)

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_positive_direct_validation.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "[POSITIVE-DIRECT] completed" in completed.stdout
    assert f"[POSITIVE-DIRECT] trusted_out={output_root / 'trusted_dynamic'}" in completed.stdout
    assert f"[POSITIVE-DIRECT] open_redirect_out={output_root / 'open_redirect_dynamic'}" in completed.stdout
    assert (output_root / "trusted_dynamic" / "summary.json").exists()
    assert (output_root / "open_redirect_dynamic" / "summary.json").exists()

    calls = json.loads(capture_path.read_text(encoding="utf-8"))
    assert calls[0][0] == "tests/e2e/run_case.py"
    assert calls[0][calls[0].index("--case") + 1] == str(cases_root / "trusted-dynamic-sqli")
    assert calls[0][calls[0].index("--output-dir") + 1] == str(output_root / "trusted_dynamic")
    assert calls[1][0] == "tests/e2e/run_case.py"
    assert calls[1][calls[1].index("--case") + 1] == str(cases_root / "open-redirect-dynamic-name-only")
    assert calls[1][calls[1].index("--output-dir") + 1] == str(output_root / "open_redirect_dynamic")


def test_positive_direct_validation_supports_direct_helper_override(tmp_path: Path) -> None:
    capture_path = tmp_path / "helper_calls.json"
    fake_helper = tmp_path / "fake_helper.py"
    _write_executable(
        fake_helper,
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
payload = {{
    "argv": sys.argv[1:],
    "python_bin": os.environ.get("VULD_DIRECT_CHAIN_PYTHON_BIN"),
    "cases_root": os.environ.get("VULD_DIRECT_CHAIN_CASES_ROOT"),
    "output_root": os.environ.get("VULD_DIRECT_CHAIN_OUTPUT_ROOT"),
    "mode": os.environ.get("VULD_DIRECT_CHAIN_MODE"),
    "no_snapshot": os.environ.get("VULD_DIRECT_CHAIN_NO_SNAPSHOT"),
}}
Path({str(capture_path)!r}).write_text(json.dumps(payload), encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_POSITIVE_DIRECT_HELPER"] = str(fake_helper)
    env["VULD_POSITIVE_DIRECT_PYTHON_BIN"] = "/tmp/fake-python"
    env["VULD_POSITIVE_DIRECT_CASES_ROOT"] = "/tmp/fake-cases"
    env["VULD_POSITIVE_DIRECT_OUTPUT_ROOT"] = "/tmp/fake-output"
    env["VULD_POSITIVE_DIRECT_MODE"] = "diverse"
    env["VULD_POSITIVE_DIRECT_NO_SNAPSHOT"] = "0"

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_positive_direct_validation.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(capture_path.read_text(encoding="utf-8"))
    assert payload["argv"] == [
        "trusted-dynamic-sqli=trusted_dynamic",
        "open-redirect-dynamic-name-only=open_redirect_dynamic",
    ]
    assert payload["python_bin"] == "/tmp/fake-python"
    assert payload["cases_root"] == "/tmp/fake-cases"
    assert payload["output_root"] == "/tmp/fake-output"
    assert payload["mode"] == "diverse"
    assert payload["no_snapshot"] == "0"


def test_positive_direct_validation_supports_named_direct_helper_override(tmp_path: Path) -> None:
    capture_path = tmp_path / "helper_capture.json"
    fake_helper = tmp_path / "named_direct_helper.py"
    _write_executable(
        fake_helper,
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
payload = {{
    "argv": sys.argv[1:],
    "env": {{
        "VULD_NAMED_DIRECT_HELPER": os.environ.get("VULD_NAMED_DIRECT_HELPER"),
        "VULD_NAMED_DIRECT_PYTHON_BIN": os.environ.get("VULD_NAMED_DIRECT_PYTHON_BIN"),
        "VULD_NAMED_DIRECT_CASES_ROOT": os.environ.get("VULD_NAMED_DIRECT_CASES_ROOT"),
        "VULD_NAMED_DIRECT_OUTPUT_ROOT": os.environ.get("VULD_NAMED_DIRECT_OUTPUT_ROOT"),
        "VULD_NAMED_DIRECT_MODE": os.environ.get("VULD_NAMED_DIRECT_MODE"),
        "VULD_NAMED_DIRECT_NO_SNAPSHOT": os.environ.get("VULD_NAMED_DIRECT_NO_SNAPSHOT"),
    }},
}}
Path({str(capture_path)!r}).write_text(json.dumps(payload), encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_POSITIVE_DIRECT_NAMED_HELPER"] = str(fake_helper)
    env["VULD_POSITIVE_DIRECT_HELPER"] = "/tmp/direct_helper"
    env["VULD_POSITIVE_DIRECT_PYTHON_BIN"] = "/tmp/fake-python"
    env["VULD_POSITIVE_DIRECT_CASES_ROOT"] = "/tmp/fake-cases"
    env["VULD_POSITIVE_DIRECT_OUTPUT_ROOT"] = "/tmp/fake-output"
    env["VULD_POSITIVE_DIRECT_MODE"] = "diverse"
    env["VULD_POSITIVE_DIRECT_NO_SNAPSHOT"] = "0"
    env["VULD_POSITIVE_DIRECT_TRUSTED_CASE"] = "trusted-case"
    env["VULD_POSITIVE_DIRECT_OPEN_REDIRECT_CASE"] = "open-redirect-case"

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_positive_direct_validation.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(capture_path.read_text(encoding="utf-8"))
    assert payload["argv"] == ["trusted-case=trusted_dynamic", "open-redirect-case=open_redirect_dynamic"]
    assert payload["env"] == {
        "VULD_NAMED_DIRECT_HELPER": "/tmp/direct_helper",
        "VULD_NAMED_DIRECT_PYTHON_BIN": "/tmp/fake-python",
        "VULD_NAMED_DIRECT_CASES_ROOT": "/tmp/fake-cases",
        "VULD_NAMED_DIRECT_OUTPUT_ROOT": "/tmp/fake-output",
        "VULD_NAMED_DIRECT_MODE": "diverse",
        "VULD_NAMED_DIRECT_NO_SNAPSHOT": "0",
    }


def test_positive_direct_validation_supports_preset_helper_override(tmp_path: Path) -> None:
    capture_path = tmp_path / "preset_capture.json"
    fake_helper = tmp_path / "preset_helper.py"
    _write_executable(
        fake_helper,
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
payload = {{
    "argv": sys.argv[1:],
    "env": {{
        "VULD_NAMED_PRESET_TARGET_HELPER": os.environ.get("VULD_NAMED_PRESET_TARGET_HELPER"),
        "VULD_NAMED_PRESET_LOG_PREFIX": os.environ.get("VULD_NAMED_PRESET_LOG_PREFIX"),
    }},
}}
Path({str(capture_path)!r}).write_text(json.dumps(payload), encoding="utf-8")
raise SystemExit(0)
""",
    )

    env = os.environ.copy()
    env["VULD_POSITIVE_DIRECT_PRESET_HELPER"] = str(fake_helper)
    env["VULD_POSITIVE_DIRECT_NAMED_HELPER"] = "/tmp/named-direct"
    env["VULD_POSITIVE_DIRECT_TRUSTED_CASE"] = "trusted-case"
    env["VULD_POSITIVE_DIRECT_OPEN_REDIRECT_CASE"] = "open-redirect-case"

    completed = subprocess.run(
        ["bash", str(REPO_ROOT / "ops/ci/run_positive_direct_validation.sh")],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(capture_path.read_text(encoding="utf-8"))
    assert payload["argv"] == [
        "build_positive_pair_case_specs",
        "trusted-case",
        "open-redirect-case",
    ]
    assert payload["env"] == {
        "VULD_NAMED_PRESET_TARGET_HELPER": "/tmp/named-direct",
        "VULD_NAMED_PRESET_LOG_PREFIX": "POSITIVE-DIRECT",
    }
