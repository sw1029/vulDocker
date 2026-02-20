from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.rules import list_rules, load_rule


def test_load_rule_from_runtime_dir(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime_rules"
    runtime_dir.mkdir()
    rule_path = runtime_dir / "cwe-999.yaml"
    rule_path.write_text(
        "cwe: CWE-999\nsuccess_signature: AUTO SUCCESS\nflag_token: FLAG-auto\n", encoding="utf-8"
    )
    env_key = "VULD_RUNTIME_RULE_DIRS"
    original = os.environ.get(env_key)
    os.environ[env_key] = str(runtime_dir)
    try:
        load_rule.cache_clear()
        rule = load_rule("CWE-999")
        assert rule["success_signature"] == "AUTO SUCCESS"
        assert any(entry["id"].lower() == "cwe-999" for entry in list_rules())
    finally:
        load_rule.cache_clear()
        if original is None:
            os.environ.pop(env_key, None)
        else:
            os.environ[env_key] = original


def test_runtime_rule_does_not_override_static_rule_by_default(tmp_path: Path) -> None:
    """Known CWE must keep static contract unless explicit policy enables full override."""
    runtime_dir = tmp_path / "runtime_rules"
    runtime_dir.mkdir()
    # Override a known static rule (cwe-89.yaml exists under docs/evals/rules).
    (runtime_dir / "cwe-89.yaml").write_text(
        (
            "cwe: CWE-89\n"
            "origin: runtime\n"
            "override_scope: full\n"
            "success_signature: OVERRIDE SIG\n"
            "flag_token: OVERRIDE FLAG\n"
        ),
        encoding="utf-8",
    )
    env_key = "VULD_RUNTIME_RULE_DIRS"
    allow_key = "VULD_ALLOW_RUNTIME_RULE_OVERRIDE_STATIC"
    original = os.environ.get(env_key)
    original_allow = os.environ.get(allow_key)
    try:
        os.environ.pop(env_key, None)
        os.environ[allow_key] = "false"
        load_rule.cache_clear()
        baseline = load_rule("CWE-89")
        assert baseline.get("success_signature") != "OVERRIDE SIG"

        # Apply runtime override and re-load without clearing caches. The
        # implementation should key caches by runtime signature.
        os.environ[env_key] = str(runtime_dir)
        overridden = load_rule("CWE-89")
        assert overridden.get("success_signature") == baseline.get("success_signature")
        assert overridden.get("flag_token") == baseline.get("flag_token")
        assert overridden.get("override_scope") == "assertions_only" or overridden.get("override_scope") == "none"
    finally:
        load_rule.cache_clear()
        if original is None:
            os.environ.pop(env_key, None)
        else:
            os.environ[env_key] = original
        if original_allow is None:
            os.environ.pop(allow_key, None)
        else:
            os.environ[allow_key] = original_allow


def test_runtime_rule_full_override_applies_when_policy_enabled(tmp_path: Path) -> None:
    runtime_dir = tmp_path / "runtime_rules"
    runtime_dir.mkdir()
    (runtime_dir / "cwe-89.yaml").write_text(
        (
            "cwe: CWE-89\n"
            "origin: runtime\n"
            "override_scope: full\n"
            "success_signature: OVERRIDE SIG\n"
            "flag_token: OVERRIDE FLAG\n"
        ),
        encoding="utf-8",
    )
    env_key = "VULD_RUNTIME_RULE_DIRS"
    allow_key = "VULD_ALLOW_RUNTIME_RULE_OVERRIDE_STATIC"
    original = os.environ.get(env_key)
    original_allow = os.environ.get(allow_key)
    try:
        os.environ[env_key] = str(runtime_dir)
        os.environ[allow_key] = "true"
        load_rule.cache_clear()
        overridden = load_rule("CWE-89")
        assert overridden.get("success_signature") == "OVERRIDE SIG"
        assert overridden.get("flag_token") == "OVERRIDE FLAG"
        assert overridden.get("override_scope") == "full"
    finally:
        load_rule.cache_clear()
        if original is None:
            os.environ.pop(env_key, None)
        else:
            os.environ[env_key] = original
        if original_allow is None:
            os.environ.pop(allow_key, None)
        else:
            os.environ[allow_key] = original_allow
