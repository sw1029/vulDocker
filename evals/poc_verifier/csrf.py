"""CSRF verifier plugin."""
from __future__ import annotations

from pathlib import Path

from .registry import register_verifier


def _evaluate_csrf_log(log_path: Path) -> dict:
    if not log_path.exists():
        raise FileNotFoundError(f"Log file not found: {log_path}")
    content = log_path.read_text(encoding="utf-8")
    has_marker = "CSRF SUCCESS" in content
    has_flag = "FLAG" in content
    evidence = []
    if has_marker:
        evidence.append("CSRF SUCCESS")
    if has_flag:
        evidence.append("FLAG present")
    return {
        "verify_pass": bool(has_marker and has_flag),
        "evidence": ", ".join(evidence) if evidence else "Signature missing",
        "log_path": str(log_path),
        "status": "evaluated",
    }


register_verifier(["CWE-352", "csrf"], _evaluate_csrf_log)
