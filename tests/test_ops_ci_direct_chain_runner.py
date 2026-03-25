from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_direct_chain_runner_executes_multiple_case_specs_and_emits_completed(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    cases_root = tmp_path / "cases"
    alpha = cases_root / "alpha-case"
    beta = cases_root / "beta-case"
    alpha.mkdir(parents=True, exist_ok=True)
    beta.mkdir(parents=True, exist_ok=True)
    (alpha / "expectations.json").write_text("{}", encoding="utf-8")
    fake_python = tmp_path / "fake_python.py"
    capture = tmp_path / "calls.json"

    _write_executable(
        fake_python,
        f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path

capture_path = Path({str(capture)!r})
calls = json.loads(capture_path.read_text(encoding="utf-8")) if capture_path.exists() else []
calls.append(sys.argv[1:])
capture_path.write_text(json.dumps(calls), encoding="utf-8")

argv = sys.argv[1:]
if argv and argv[0] == "tests/e2e/run_case.py":
    out_dir = Path(argv[argv.index("--output-dir") + 1])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text('{{"ok": true}}', encoding="utf-8")
raise SystemExit(0)
""",
    )

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_direct_chain_runner.sh")!r}
direct_run_case_specs \
  TEST \
  {str(fake_python)!r} \
  {str(cases_root)!r} \
  {str(tmp_path / "outputs")!r} \
  deterministic \
  1 \
  alpha-case \
  beta-case=custom_beta
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "[TEST] alpha-case -> " in completed.stdout
    assert "[TEST] beta-case -> " in completed.stdout
    assert "[TEST] completed" in completed.stdout
    assert (tmp_path / "outputs" / "run_alpha_case" / "summary.json").exists()
    assert (tmp_path / "outputs" / "custom_beta" / "summary.json").exists()
    calls = json.loads(capture.read_text(encoding="utf-8"))
    assert len(calls) == 2
    assert "--expectations" in calls[0]
    assert "--expectations" not in calls[1]


def test_direct_chain_runner_propagates_invalid_alias_failure(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    cases_root = tmp_path / "cases"
    case_dir = cases_root / "gamma-case"
    case_dir.mkdir(parents=True, exist_ok=True)
    fake_python = tmp_path / "fake_python.py"

    _write_executable(fake_python, "#!/usr/bin/env python3\nraise SystemExit(0)\n")
    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_direct_chain_runner.sh")!r}
direct_run_case_specs \
  TEST \
  {str(fake_python)!r} \
  {str(cases_root)!r} \
  {str(tmp_path / "outputs")!r} \
  deterministic \
  0 \
  gamma-case=bad/alias
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
