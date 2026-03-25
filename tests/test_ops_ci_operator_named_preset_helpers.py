from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_operator_named_preset_helpers_accepts_full_executable_chain(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    preset = tmp_path / "preset.sh"
    named = tmp_path / "named.sh"
    leaf = tmp_path / "leaf.sh"
    probe = tmp_path / "probe.sh"

    for helper in (preset, named, leaf):
        _write_executable(helper, "#!/usr/bin/env bash\nexit 0\n")

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_operator_named_preset_helpers.sh")!r}
operator_validate_named_preset_chain {str(preset)!r} {str(named)!r} {str(leaf)!r} '' '' TEST 'named helper' 'leaf helper'
python - <<'PY' > {str(capture)!r}
import json
print(json.dumps({{"ok": True}}))
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
    assert json.loads(capture.read_text(encoding="utf-8")) == {"ok": True}


def test_operator_named_preset_helpers_allows_preset_override_without_named_or_leaf(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    preset = tmp_path / "preset.sh"
    probe = tmp_path / "probe.sh"

    _write_executable(preset, "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_operator_named_preset_helpers.sh")!r}
operator_validate_named_preset_chain {str(preset)!r} /tmp/missing-named /tmp/missing-leaf override '' TEST 'named helper' 'leaf helper'
python - <<'PY' > {str(capture)!r}
import json
print(json.dumps({{"preset_override": True}}))
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
    assert json.loads(capture.read_text(encoding="utf-8")) == {"preset_override": True}


def test_operator_named_preset_helpers_allows_named_override_without_leaf(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    preset = tmp_path / "preset.sh"
    named = tmp_path / "named.sh"
    probe = tmp_path / "probe.sh"

    _write_executable(preset, "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(named, "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_operator_named_preset_helpers.sh")!r}
operator_validate_named_preset_chain {str(preset)!r} {str(named)!r} /tmp/missing-leaf '' override TEST 'named helper' 'leaf helper'
python - <<'PY' > {str(capture)!r}
import json
print(json.dumps({{"named_override": True}}))
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
    assert json.loads(capture.read_text(encoding="utf-8")) == {"named_override": True}


def test_operator_named_preset_helpers_rejects_missing_preset_helper(tmp_path: Path) -> None:
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_operator_named_preset_helpers.sh")!r}
operator_validate_named_preset_chain /tmp/missing-preset /tmp/missing-named /tmp/missing-leaf '' '' TEST 'named helper' 'leaf helper'
""",
    )

    completed = subprocess.run(
        ["bash", str(probe)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "[TEST] preset helper not found or not executable: /tmp/missing-preset" in completed.stderr
