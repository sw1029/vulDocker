from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator.plugins.react_loop import ReactLoop


def test_react_loop_queries_include_raw_vuln_name(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-react-name-only"
    monkeypatch.setattr("orchestrator.plugins.react_loop.get_metadata_dir", lambda incoming_sid: tmp_path / incoming_sid)
    monkeypatch.setattr("orchestrator.plugins.react_loop.latest_failure_context", lambda incoming_sid: "")
    loop = ReactLoop(sid)

    queries = loop.queries_from_requirement(
        {
            "vuln_id": "NAME-TEMPLATE-INJECTION",
            "vuln_name": "Template Injection",
            "language": "python",
            "framework": "flask",
        }
    )

    assert any("Template Injection exploit writeup python flask" in query for query in queries)
