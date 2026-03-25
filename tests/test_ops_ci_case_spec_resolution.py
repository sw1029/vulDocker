from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_case_spec_resolution_supports_split_and_path_resolution(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    case_dir = tmp_path / "cases" / "alpha-case"
    case_dir.mkdir(parents=True, exist_ok=True)

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_spec_resolution.sh")!r}
mapfile -t PARTS < <(case_spec_split "alpha-case=alias_alpha")
CASE_DIR="$(case_spec_resolve_case_dir {str(tmp_path / "cases")!r} "${{PARTS[0]}}")"
case_spec_require_existing_dir TEST "${{CASE_DIR}}"
case_spec_require_safe_alias TEST "${{PARTS[1]}}"
export CASE_REF="${{PARTS[0]}}"
export CASE_ALIAS="${{PARTS[1]}}"
export CASE_DIR
python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "case_ref": os.environ["CASE_REF"],
  "case_alias": os.environ["CASE_ALIAS"],
  "case_dir": os.environ["CASE_DIR"],
}}))
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
    assert json.loads(capture.read_text(encoding="utf-8")) == {
        "case_ref": "alpha-case",
        "case_alias": "alias_alpha",
        "case_dir": str(case_dir),
    }


def test_case_spec_resolution_supports_absolute_case_dir(tmp_path: Path) -> None:
    capture = tmp_path / "capture.txt"
    probe = tmp_path / "probe.sh"

    case_dir = tmp_path / "absolute-case"
    case_dir.mkdir(parents=True, exist_ok=True)

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_spec_resolution.sh")!r}
printf '%s' "$(case_spec_resolve_case_dir /tmp/unused {str(case_dir)!r})" > {str(capture)!r}
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert capture.read_text(encoding="utf-8") == str(case_dir)


def test_case_spec_resolution_supports_context_and_output_helpers(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    case_dir = tmp_path / "cases" / "alpha-case"
    case_dir.mkdir(parents=True, exist_ok=True)

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_spec_resolution.sh")!r}
CASE_CONTEXT=()
case_spec_resolve_case_context CASE_CONTEXT TEST {str(tmp_path / "cases")!r} "alpha-case=alias-output"
case_spec_resolve_output_name OUTPUT_NAME TEST "${{CASE_CONTEXT[2]}}" "run_alpha_case"
case_spec_safe_slug SAFE_SLUG "${{OUTPUT_NAME}}"
export CASE_DIR="${{CASE_CONTEXT[0]}}"
export CASE_SLUG="${{CASE_CONTEXT[1]}}"
export CASE_ALIAS="${{CASE_CONTEXT[2]}}"
export OUTPUT_NAME
export SAFE_SLUG
python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "case_dir": os.environ["CASE_DIR"],
  "case_slug": os.environ["CASE_SLUG"],
  "case_alias": os.environ["CASE_ALIAS"],
  "output_name": os.environ["OUTPUT_NAME"],
  "safe_slug": os.environ["SAFE_SLUG"],
}}))
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
    assert json.loads(capture.read_text(encoding="utf-8")) == {
        "case_dir": str(case_dir),
        "case_slug": "alpha-case",
        "case_alias": "alias-output",
        "output_name": "alias-output",
        "safe_slug": "alias_output",
    }


def test_case_spec_resolution_supports_direct_output_context(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    case_dir = tmp_path / "cases" / "alpha-case"
    case_dir.mkdir(parents=True, exist_ok=True)

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_spec_resolution.sh")!r}
CASE_OUTPUT_CONTEXT=()
case_spec_resolve_direct_output_context CASE_OUTPUT_CONTEXT TEST {str(tmp_path / "cases")!r} "alpha-case=alias-output" {str(tmp_path / "outputs")!r}
export CASE_DIR="${{CASE_OUTPUT_CONTEXT[0]}}"
export CASE_SLUG="${{CASE_OUTPUT_CONTEXT[1]}}"
export CASE_ALIAS="${{CASE_OUTPUT_CONTEXT[2]}}"
export OUTPUT_NAME="${{CASE_OUTPUT_CONTEXT[3]}}"
export OUTPUT_DIR="${{CASE_OUTPUT_CONTEXT[4]}}"
python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "case_dir": os.environ["CASE_DIR"],
  "case_slug": os.environ["CASE_SLUG"],
  "case_alias": os.environ["CASE_ALIAS"],
  "output_name": os.environ["OUTPUT_NAME"],
  "output_dir": os.environ["OUTPUT_DIR"],
}}))
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
    assert json.loads(capture.read_text(encoding="utf-8")) == {
        "case_dir": str(case_dir),
        "case_slug": "alpha-case",
        "case_alias": "alias-output",
        "output_name": "alias-output",
        "output_dir": str(tmp_path / "outputs" / "alias-output"),
    }


def test_case_spec_resolution_supports_repeat_output_context(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    case_dir = tmp_path / "cases" / "alpha-case"
    case_dir.mkdir(parents=True, exist_ok=True)

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_spec_resolution.sh")!r}
CASE_OUTPUT_CONTEXT=()
case_spec_resolve_repeat_output_context CASE_OUTPUT_CONTEXT TEST {str(tmp_path / "cases")!r} "alpha-case=alias-output" {str(tmp_path / "outputs")!r} repeat
export CASE_DIR="${{CASE_OUTPUT_CONTEXT[0]}}"
export CASE_SLUG="${{CASE_OUTPUT_CONTEXT[1]}}"
export CASE_ALIAS="${{CASE_OUTPUT_CONTEXT[2]}}"
export OUTPUT_NAME="${{CASE_OUTPUT_CONTEXT[3]}}"
export SAFE_SLUG="${{CASE_OUTPUT_CONTEXT[4]}}"
export OUTPUT_DIR="${{CASE_OUTPUT_CONTEXT[5]}}"
python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "case_dir": os.environ["CASE_DIR"],
  "case_slug": os.environ["CASE_SLUG"],
  "case_alias": os.environ["CASE_ALIAS"],
  "output_name": os.environ["OUTPUT_NAME"],
  "safe_slug": os.environ["SAFE_SLUG"],
  "output_dir": os.environ["OUTPUT_DIR"],
}}))
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
    assert json.loads(capture.read_text(encoding="utf-8")) == {
        "case_dir": str(case_dir),
        "case_slug": "alpha-case",
        "case_alias": "alias-output",
        "output_name": "alias-output",
        "safe_slug": "alias_output",
        "output_dir": str(tmp_path / "outputs" / "repeat_alias_output"),
    }


def test_case_spec_resolution_exports_direct_output_context(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    case_dir = tmp_path / "cases" / "alpha-case"
    case_dir.mkdir(parents=True, exist_ok=True)

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_spec_resolution.sh")!r}
case_spec_export_direct_output_context DIRECT TEST {str(tmp_path / "cases")!r} "alpha-case=alias-output" {str(tmp_path / "outputs")!r}
export CASE_DIR="${{DIRECT_CASE_DIR}}"
export CASE_SLUG="${{DIRECT_CASE_SLUG}}"
export CASE_ALIAS="${{DIRECT_CASE_ALIAS}}"
export OUTPUT_NAME="${{DIRECT_OUTPUT_NAME}}"
export OUTPUT_DIR="${{DIRECT_OUTPUT_DIR}}"
python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "case_dir": os.environ["CASE_DIR"],
  "case_slug": os.environ["CASE_SLUG"],
  "case_alias": os.environ["CASE_ALIAS"],
  "output_name": os.environ["OUTPUT_NAME"],
  "output_dir": os.environ["OUTPUT_DIR"],
}}))
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
    assert json.loads(capture.read_text(encoding="utf-8")) == {
        "case_dir": str(case_dir),
        "case_slug": "alpha-case",
        "case_alias": "alias-output",
        "output_name": "alias-output",
        "output_dir": str(tmp_path / "outputs" / "alias-output"),
    }


def test_case_spec_resolution_exports_repeat_output_context(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    case_dir = tmp_path / "cases" / "alpha-case"
    case_dir.mkdir(parents=True, exist_ok=True)

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_spec_resolution.sh")!r}
case_spec_export_repeat_output_context REPEAT TEST {str(tmp_path / "cases")!r} "alpha-case=alias-output" {str(tmp_path / "outputs")!r} repeat
export CASE_DIR="${{REPEAT_CASE_DIR}}"
export CASE_SLUG="${{REPEAT_CASE_SLUG}}"
export CASE_ALIAS="${{REPEAT_CASE_ALIAS}}"
export OUTPUT_NAME="${{REPEAT_OUTPUT_NAME}}"
export SAFE_SLUG="${{REPEAT_SAFE_SLUG}}"
export OUTPUT_DIR="${{REPEAT_OUTPUT_DIR}}"
python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "case_dir": os.environ["CASE_DIR"],
  "case_slug": os.environ["CASE_SLUG"],
  "case_alias": os.environ["CASE_ALIAS"],
  "output_name": os.environ["OUTPUT_NAME"],
  "safe_slug": os.environ["SAFE_SLUG"],
  "output_dir": os.environ["OUTPUT_DIR"],
}}))
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
    assert json.loads(capture.read_text(encoding="utf-8")) == {
        "case_dir": str(case_dir),
        "case_slug": "alpha-case",
        "case_alias": "alias-output",
        "output_name": "alias-output",
        "safe_slug": "alias_output",
        "output_dir": str(tmp_path / "outputs" / "repeat_alias_output"),
    }


def test_case_spec_resolution_rejects_alias_with_path_separator(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_spec_resolution.sh")!r}
case_spec_require_safe_alias TEST "bad/alias"
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert completed.stderr == "[TEST] alias must not contain '/': bad/alias\n"
