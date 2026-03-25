from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def test_smoke_regression_supports_flow_and_docker_overrides(tmp_path: Path) -> None:
    suffix = tmp_path.name
    fake_docker = tmp_path / "fake_docker"
    capture_path = tmp_path / "smoke_capture.json"
    fake_flow = tmp_path / "fake_smoke_flow.py"

    _write_executable(
        fake_docker,
        """#!/usr/bin/env python3
raise SystemExit(0)
""",
    )
    _write_executable(
        fake_flow,
        f"""#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
import yaml

req_path = Path(sys.argv[1])
mode = sys.argv[2]
suffix = os.environ["VULD_SMOKE_TEST_SUFFIX"]
sid = f"sid-smoke-{{mode}}-{{suffix}}"
root = Path.cwd()
req = yaml.safe_load(req_path.read_text(encoding="utf-8")) or {{}}
capture_path = Path({str(capture_path)!r})
captures = []
if capture_path.exists():
    captures = json.loads(capture_path.read_text(encoding="utf-8"))
captures.append({{
    "mode": mode,
    "requirement_id": req.get("requirement_id"),
    "variation_mode": ((req.get("variation_key") or {{}}).get("mode")),
}})
capture_path.write_text(json.dumps(captures, ensure_ascii=False), encoding="utf-8")

(root / "metadata" / sid).mkdir(parents=True, exist_ok=True)
(root / "artifacts" / sid / "reports").mkdir(parents=True, exist_ok=True)
(root / "metadata" / sid / "plan.json").write_text(
    json.dumps({{"variation_key": req.get("variation_key")}}, ensure_ascii=False),
    encoding="utf-8",
)
candidate_count = 1 if mode == "deterministic" else 3
(root / "artifacts" / sid / "reports" / "evals.json").write_text(
    json.dumps({{"verify_pass": True, "evidence": f"ok-{{mode}}"}}, ensure_ascii=False),
    encoding="utf-8",
)
(root / "artifacts" / sid / "reports" / "diversity.json").write_text(
    json.dumps({{"metrics": {{"candidate_count": candidate_count}}}}, ensure_ascii=False),
    encoding="utf-8",
)
(root / "metadata" / sid / "generator_candidates.json").write_text(
    json.dumps({{"candidates": [{{"index": i}} for i in range(candidate_count)]}}, ensure_ascii=False),
    encoding="utf-8",
)
print(sid)
""",
    )

    env = os.environ.copy()
    env["VULD_SMOKE_DOCKER_BIN"] = str(fake_docker)
    env["VULD_SMOKE_FLOW_SCRIPT"] = str(fake_flow)
    env["VULD_SMOKE_SNAPSHOT"] = "smoke-snapshot-override"
    env["VULD_SMOKE_TEST_SUFFIX"] = suffix
    sid_det = f"sid-smoke-deterministic-{suffix}"
    sid_div = f"sid-smoke-diverse-{suffix}"

    try:
        completed = subprocess.run(
            ["bash", str(REPO_ROOT / "ops/ci/smoke_regression.sh")],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
        )

        assert completed.returncode == 0, completed.stderr
        assert "[SMOKE] Using snapshot: smoke-snapshot-override" in completed.stdout
        assert "[SMOKE] deterministic candidate_count=1" in completed.stdout
        assert "[SMOKE] diverse candidate_count=3" in completed.stdout
        assert "[SMOKE] Regression suite passed" in completed.stdout
        captures = json.loads(capture_path.read_text(encoding="utf-8"))
        assert [entry["mode"] for entry in captures] == ["deterministic", "diverse"]
        assert [entry["variation_mode"] for entry in captures] == ["deterministic", "diverse"]
    finally:
        shutil.rmtree(REPO_ROOT / "metadata" / sid_det, ignore_errors=True)
        shutil.rmtree(REPO_ROOT / "metadata" / sid_div, ignore_errors=True)
        shutil.rmtree(REPO_ROOT / "artifacts" / sid_det, ignore_errors=True)
        shutil.rmtree(REPO_ROOT / "artifacts" / sid_div, ignore_errors=True)
