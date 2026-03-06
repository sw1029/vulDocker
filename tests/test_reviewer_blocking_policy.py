from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.reviewer.service import ReviewerContext, ReviewerService
from common.run_matrix import VulnBundle


class _LoopStub:
    current_loop = 1

    def start_loop(self) -> None:
        return None

    def record_failure(self, **kwargs) -> None:
        self.last_failure = kwargs

    def record_success(self, **kwargs) -> None:
        self.last_success = kwargs


class _LLMStub:
    def generate(self, prompt):  # noqa: ANN001
        return "{}"


def test_reviewer_non_blocking_quality_issue_does_not_block_successful_bundle(tmp_path: Path) -> None:
    service = ReviewerService.__new__(ReviewerService)
    service.sid = "sid-review"
    service.plan = {"requirement": {}, "paths": {"metadata": str(tmp_path)}}  # type: ignore[attr-defined]
    service.metadata_root = tmp_path  # type: ignore[attr-defined]
    service.loop_controller = _LoopStub()  # type: ignore[attr-defined]
    service.llm = _LLMStub()  # type: ignore[attr-defined]
    service.bundles = [VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")]  # type: ignore[attr-defined]
    service._evaluate_bundle = lambda bundle: ReviewerContext(  # type: ignore[attr-defined]
        sid="sid-review",
        bundle=bundle,
        log_path=tmp_path / "run.log",
        log_excerpt="ok",
        success=True,
        issues=[],
        blocking=False,
        reason="",
        fix_hint="",
    )
    service._scan_workspace = lambda bundle, exploit_success=False: [  # type: ignore[attr-defined]
        {
            "sid": "sid-review",
            "bundle_slug": bundle.slug,
            "file": "app.py",
            "line": 1,
            "issue": "Dynamic guard mismatch: semantic drift",
            "fix_hint": "realign semantics",
            "severity": "medium",
            "blocking": False,
            "created_at": "2026-03-06T00:00:00+00:00",
        }
    ]

    service.run()

    summary = json.loads((tmp_path / "reviewer_report.json").read_text(encoding="utf-8"))
    assert summary["blocking_bundles"] == []
