from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_collect_permission_artifact_cases_prefers_case_slug_and_falls_back_to_basename(tmp_path: Path) -> None:
    run_a = tmp_path / "repeat_alpha_case"
    run_b = tmp_path / "repeat_beta_case"
    run_a.mkdir(parents=True, exist_ok=True)
    run_b.mkdir(parents=True, exist_ok=True)
    (run_a / "docker_permission_artifact.txt").write_text("case_slug=alpha-case\n", encoding="utf-8")
    (run_b / "docker_permission_artifact.txt").write_text("reason=docker daemon permission denied\n", encoding="utf-8")

    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"
    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_permission_artifacts.sh")!r}
mapfile -t cases < <(collect_permission_artifact_cases docker_permission_artifact.txt {str(run_a)!r} {str(run_b)!r})
python - <<'PY' > {str(capture)!r}
import json
print(json.dumps({{"cases": {{"values": []}}}}))
PY
python - <<'PY' {str(capture)!r} "${{cases[@]}}"
import json, sys
path = sys.argv[1]
payload = {{"cases": sys.argv[2:]}}
with open(path, "w", encoding="utf-8") as fh:
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
    payload = json.loads(capture.read_text(encoding="utf-8"))
    assert payload == {"cases": ["alpha-case", "repeat_beta_case"]}


def test_emit_permission_artifact_note_is_quiet_for_empty_and_formats_prefix(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"
    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_repeatability_permission_artifacts.sh")!r}
emit_permission_artifact_note SUPPORT
emit_permission_artifact_note MATRIX alpha-case beta-case
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    assert completed.stdout.splitlines() == [
        "[MATRIX] note: docker permission artifact detected for alpha-case beta-case; unrestricted Docker-enabled rerun is recommended for runtime-equivalent helper truth"
    ]
