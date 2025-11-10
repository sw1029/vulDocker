"""Tests for rule-based verifier logic."""
from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from evals.poc_verifier import rule_based

REPO_ROOT = Path(__file__).resolve().parents[3]


class RuleBasedVerifierTests(TestCase):
    def _write_log(self, text: str = "") -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        log_path = Path(tmp.name) / "run.log"
        log_path.write_text(text, encoding="utf-8")
        return log_path

    def test_summary_success_and_exit_code_gate(self) -> None:
        log_path = self._write_log("JSON output unused")
        run_summary = {"success": True, "flag": "FLAG-token", "exit_code": 0}
        rule = {
            "cwe": "CWE-999",
            "flag_token": "FLAG-token",
            "output": {
                "format": "json",
                "json": {"success_key": "success", "success_value": True, "flag_key": "flag"},
            },
        }
        with patch.object(rule_based, "load_rule", return_value=rule):
            result = rule_based.verify_with_rule(
                "CWE-999",
                log_path,
                run_summary=run_summary,
                policy={"require_exit_code_zero": True},
            )
        self.assertTrue(result["verify_pass"])
        self.assertIn("JSON success", result["evidence"])

    def test_exit_code_policy_failure(self) -> None:
        log_path = self._write_log("text ignored")
        run_summary = {"success": True, "flag": "FLAG-token", "exit_code": 137}
        rule = {
            "cwe": "CWE-999",
            "flag_token": "FLAG-token",
            "output": {
                "format": "json",
                "json": {"success_key": "success", "success_value": True, "flag_key": "flag"},
            },
        }
        with patch.object(rule_based, "load_rule", return_value=rule):
            result = rule_based.verify_with_rule(
                "CWE-999",
                log_path,
                run_summary=run_summary,
                policy={"require_exit_code_zero": True},
            )
        self.assertFalse(result["verify_pass"])
        self.assertIn("exit_code=137", result["evidence"])

    def test_text_signature_when_summary_missing(self) -> None:
        log_path = self._write_log("SIG PASS FLAG-token")
        rule = {
            "cwe": "CWE-999",
            "success_signature": "SIG",
            "flag_token": "FLAG-token",
            "strict_flag": False,
        }
        with patch.object(rule_based, "load_rule", return_value=rule):
            result = rule_based.verify_with_rule("CWE-999", log_path)
        self.assertTrue(result["verify_pass"])
        self.assertIn("Found signature", result["evidence"])

    def test_pattern_evidence_from_workspace(self) -> None:
        sid = f"sid-test-{uuid.uuid4().hex[:8]}"
        workspace_base = REPO_ROOT / "workspaces" / sid / "app"
        artifacts_run = REPO_ROOT / "artifacts" / sid / "run"
        workspace_base.mkdir(parents=True, exist_ok=True)
        artifacts_run.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(REPO_ROOT / "workspaces" / sid, ignore_errors=True))
        self.addCleanup(lambda: shutil.rmtree(REPO_ROOT / "artifacts" / sid, ignore_errors=True))

        (workspace_base / "app.py").write_text("def handler():\n    return 'SELECT * FROM users'\n", encoding="utf-8")
        (workspace_base / "poc.py").write_text("print('SQLi SUCCESS')\n", encoding="utf-8")
        log_path = artifacts_run / "run.log"
        log_path.write_text("LOG", encoding="utf-8")

        rule = {
            "cwe": "CWE-999",
            "success_signature": "SIG",
            "flag_token": "",
            "patterns": [
                {"type": "file_contains", "path": "app.py", "contains": "SELECT"},
                {"type": "poc_contains", "contains": "SQLi SUCCESS"},
            ],
        }
        with patch.object(rule_based, "load_rule", return_value=rule):
            result = rule_based.verify_with_rule(
                "CWE-999",
                log_path,
                run_summary={"sid": sid},
            )
        evidence = result["evidence"]
        self.assertIn("app.py contains 'SELECT'", evidence)
        self.assertIn("poc.py contains 'SQLi SUCCESS'", evidence)

    def test_pattern_lookup_uses_slug_subdirectory(self) -> None:
        sid = f"sid-test-{uuid.uuid4().hex[:8]}"
        slug = "cwe-demo"
        workspace_dir = REPO_ROOT / "workspaces" / sid / "app" / slug
        artifacts_run = REPO_ROOT / "artifacts" / sid / "run" / slug
        workspace_dir.mkdir(parents=True, exist_ok=True)
        artifacts_run.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(REPO_ROOT / "workspaces" / sid, ignore_errors=True))
        self.addCleanup(lambda: shutil.rmtree(REPO_ROOT / "artifacts" / sid, ignore_errors=True))

        (workspace_dir / "poc.py").write_text("print('Exploit SUCCESS')", encoding="utf-8")
        (artifacts_run / "run.log").write_text("LOG", encoding="utf-8")

        rule = {
            "cwe": "CWE-123",
            "success_signature": "",
            "flag_token": "",
            "patterns": [{"type": "poc_contains", "contains": "Exploit SUCCESS"}],
        }
        with patch.object(rule_based, "load_rule", return_value=rule):
            result = rule_based.verify_with_rule(
                "CWE-123",
                artifacts_run / "run.log",
                run_summary={"sid": sid, "slug": slug},
            )
        self.assertIn("poc.py contains 'Exploit SUCCESS'", result["evidence"])
