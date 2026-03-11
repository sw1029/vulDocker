from __future__ import annotations

from pathlib import Path

from evals.poc_verifier import rule_based


def test_rule_based_patterns_support_file_regex_contains_on_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "app"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "app.py").write_text(
        "from fastapi.responses import RedirectResponse\n"
        "def go(next: str):\n"
        "    return RedirectResponse(url=next, status_code=302)\n",
        encoding="utf-8",
    )
    rule = {
        "patterns": [
            {"type": "file_regex_contains", "path": "app.py", "pattern": r"RedirectResponse\("},
            {"type": "file_regex_contains", "path": "app.py", "pattern": r"url\s*=\s*next"},
        ]
    }

    evidence = rule_based._evaluate_patterns(rule, [workspace])  # type: ignore[attr-defined]

    assert evidence == [
        "app.py matches /RedirectResponse\\(/",
        "app.py matches /url\\s*=\\s*next/",
    ]
