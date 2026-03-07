from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

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


class _FailIfCalledLLM:
    def generate(self, prompt):  # noqa: ANN001
        raise AssertionError("LLM should not have been called")


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


def test_reviewer_surfaces_low_confidence_unknown_issue_without_blocking(tmp_path: Path) -> None:
    bundle = VulnBundle(vuln_id="CWE-9999", slug="cwe-9999", workspace_subdir="app")
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "resolved_contract.json").write_text(
        json.dumps(
            {
                "semantic_contract": {
                    "evidence_relevance": {
                        "confidence": "low",
                        "negative_hit_ratio": 0.10,
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    service = ReviewerService.__new__(ReviewerService)
    service.sid = "sid-review"
    service.plan = {  # type: ignore[attr-defined]
        "requirement": {},
        "paths": {"metadata": str(tmp_path)},
        "policy": {"guard": {"low_confidence_unknown_policy": "warn"}},
    }
    service.metadata_root = tmp_path  # type: ignore[attr-defined]
    service.loop_controller = _LoopStub()  # type: ignore[attr-defined]
    service.llm = _LLMStub()  # type: ignore[attr-defined]
    service.bundles = [bundle]  # type: ignore[attr-defined]
    service._evaluate_bundle = lambda incoming_bundle: ReviewerContext(  # type: ignore[attr-defined]
        sid="sid-review",
        bundle=incoming_bundle,
        log_path=tmp_path / "run.log",
        log_excerpt="ok",
        success=True,
        issues=[],
        blocking=False,
        reason="",
        fix_hint="",
    )
    service._scan_workspace = lambda incoming_bundle, exploit_success=False: []  # type: ignore[attr-defined]

    service.run()

    summary = json.loads((tmp_path / "reviewer_report.json").read_text(encoding="utf-8"))
    assert summary["blocking_bundles"] == []
    assert any("confidence is low" in issue.get("issue", "").lower() for issue in summary["issues_sample"])


def test_reviewer_skips_llm_feedback_for_clean_runs_by_default(tmp_path: Path) -> None:
    service = ReviewerService.__new__(ReviewerService)
    service.sid = "sid-review"
    service.plan = {"requirement": {}, "paths": {"metadata": str(tmp_path)}}  # type: ignore[attr-defined]
    service.metadata_root = tmp_path  # type: ignore[attr-defined]
    service.loop_controller = _LoopStub()  # type: ignore[attr-defined]
    service.llm = _FailIfCalledLLM()  # type: ignore[attr-defined]
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
    service._scan_workspace = lambda bundle, exploit_success=False: []  # type: ignore[attr-defined]

    service.run()

    bundle_report = json.loads((tmp_path / "reviewer_report.json").read_text(encoding="utf-8"))
    assert bundle_report["blocking_bundles"] == []


def test_reviewer_blocks_on_semantic_contract_contradiction(tmp_path: Path) -> None:
    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "resolved_contract.json").write_text(
        json.dumps(
            {
                "semantic_contract": {
                    "contradictions": [
                        "semantic_contract sink conflicts with baseline CWE-89 semantics"
                    ]
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    service = ReviewerService.__new__(ReviewerService)
    service.sid = "sid-review"
    service.plan = {"requirement": {}, "paths": {"metadata": str(tmp_path)}}  # type: ignore[attr-defined]
    service.metadata_root = tmp_path  # type: ignore[attr-defined]
    service.loop_controller = _LoopStub()  # type: ignore[attr-defined]
    service.llm = _LLMStub()  # type: ignore[attr-defined]
    service.bundles = [bundle]  # type: ignore[attr-defined]
    service._evaluate_bundle = lambda incoming_bundle: ReviewerContext(  # type: ignore[attr-defined]
        sid="sid-review",
        bundle=incoming_bundle,
        log_path=tmp_path / "run.log",
        log_excerpt="ok",
        success=True,
        issues=[],
        blocking=False,
        reason="",
        fix_hint="",
    )
    service._scan_workspace = lambda incoming_bundle, exploit_success=False: []  # type: ignore[attr-defined]

    service.run()

    summary = json.loads((tmp_path / "reviewer_report.json").read_text(encoding="utf-8"))
    assert summary["blocking_bundles"] == ["cwe-89"]
    assert any("semantic contract contradiction" in issue.get("issue", "").lower() for issue in summary["issues_sample"])


def test_evaluate_bundle_blocks_on_nested_verifier_guard_failure(tmp_path: Path, monkeypatch) -> None:
    metadata_dir = tmp_path / "metadata"
    artifacts_dir = tmp_path / "artifacts"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "run").mkdir(parents=True, exist_ok=True)
    run_log = artifacts_dir / "run" / "run.log"
    run_log.write_text("Exploit SUCCESS\n", encoding="utf-8")
    (artifacts_dir / "run" / "summary.json").write_text(
        json.dumps({"exit_code": 0, "run_attempted": True, "sid": "sid-review", "slug": "cwe-89"}, ensure_ascii=False),
        encoding="utf-8",
    )

    service = ReviewerService.__new__(ReviewerService)
    service.sid = "sid-review"
    service.plan = {  # type: ignore[attr-defined]
        "requirement": {},
        "paths": {"metadata": str(metadata_dir), "artifacts": str(artifacts_dir)},
    }
    service.metadata_root = metadata_dir  # type: ignore[attr-defined]

    bundle = VulnBundle(vuln_id="CWE-89", slug="cwe-89", workspace_subdir="app")

    def _fake_evaluate_with_vuln(*args, **kwargs) -> Dict[str, Any]:
        return {
            "verify_pass": True,
            "status": "evaluated",
            "evidence": "Exploit SUCCESS",
            "guard_consistency": {
                "available": True,
                "required_but_missing": False,
                "verifier": {
                    "passed": False,
                    "blocking": True,
                    "violations": ["verifier assertion failed (contains): substring=missing: expected marker"],
                },
                "workspace": {"passed": True, "blocking": False, "violations": []},
            },
        }

    monkeypatch.setattr("agents.reviewer.service.evaluate_with_vuln", _fake_evaluate_with_vuln)

    context = service._evaluate_bundle(bundle)  # type: ignore[attr-defined]

    assert context.success is False
    assert context.blocking is True
    assert any("verifier guard mismatch" in issue.get("issue", "").lower() for issue in context.issues)
