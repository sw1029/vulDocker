from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_case_spec_presets_emit_expected_alias_sets(tmp_path: Path) -> None:
    capture = tmp_path / "capture.json"
    probe = tmp_path / "probe.sh"

    _write_executable(
        probe,
        f"""#!/usr/bin/env bash
set -euo pipefail
source {str(REPO_ROOT / "ops/ci/lib_case_spec_presets.sh")!r}
mapfile -t positive < <(build_positive_pair_case_specs trusted-case open-redirect-case)
mapfile -t blocked < <(build_blocked_noop_case_specs foobar-case strict-case)
mapfile -t low_cost < <(build_low_cost_case_specs strict-no-remote strict-stub negative-case)
mapfile -t matrix < <(build_matrix_pair_case_specs alpha-case beta-case)
export POSITIVE="$(printf '%s\\n' "${{positive[@]}}")"
export BLOCKED="$(printf '%s\\n' "${{blocked[@]}}")"
export LOW_COST="$(printf '%s\\n' "${{low_cost[@]}}")"
export MATRIX="$(printf '%s\\n' "${{matrix[@]}}")"
python - <<'PY' > {str(capture)!r}
import json
import os
print(json.dumps({{
  "positive": os.environ["POSITIVE"].splitlines(),
  "blocked": os.environ["BLOCKED"].splitlines(),
  "low_cost": os.environ["LOW_COST"].splitlines(),
  "matrix": os.environ["MATRIX"].splitlines(),
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
    payload = json.loads(capture.read_text(encoding="utf-8"))
    assert payload == {
        "positive": ["trusted-case=trusted_dynamic", "open-redirect-case=open_redirect_dynamic"],
        "blocked": ["foobar-case=foobar", "strict-case=strict"],
        "low_cost": ["strict-no-remote=strict_no_remote", "strict-stub=strict_stub", "negative-case=negative"],
        "matrix": ["alpha-case", "beta-case"],
    }
