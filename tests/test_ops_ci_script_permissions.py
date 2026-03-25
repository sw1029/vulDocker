from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_ops_ci_shell_entrypoints_are_executable() -> None:
    scripts = sorted((REPO_ROOT / "ops/ci").glob("run_*.sh"))
    scripts.append(REPO_ROOT / "ops/ci" / "smoke_regression.sh")

    missing = [str(path.relative_to(REPO_ROOT)) for path in scripts if not os.access(path, os.X_OK)]
    assert missing == []
