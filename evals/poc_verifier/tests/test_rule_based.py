"""Tests for rule-based verifier logic."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from evals.poc_verifier import rule_based


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
