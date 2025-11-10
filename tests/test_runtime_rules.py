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
