from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_mysql_union_template_flag_token_matches_template_metadata() -> None:
    template_root = REPO_ROOT / "workspaces" / "templates" / "sqli" / "flask_mysql_union"
    metadata = json.loads((template_root / "template.json").read_text(encoding="utf-8"))
    expected = str(metadata.get("flag_token") or "").strip()

    app_text = (template_root / "app" / "app.py").read_text(encoding="utf-8")
    schema_text = (template_root / "app" / "schema.sql").read_text(encoding="utf-8")

    assert expected
    assert expected in app_text
    assert expected in schema_text
