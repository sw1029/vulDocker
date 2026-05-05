from __future__ import annotations

import json
from pathlib import Path

from rag import static_loader


def test_load_static_context_includes_raw_cve_snapshot(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path
    (root / "rag" / "index" / "rag-snap-20251108").mkdir(parents=True)
    processed_dir = root / "rag" / "corpus" / "processed" / "mvp-sample"
    processed_dir.mkdir(parents=True)
    (processed_dir / "context.md").write_text("MVP fallback context", encoding="utf-8")
    raw_dir = root / "rag" / "corpus" / "raw" / "poc" / "smoke-empty" / "20251108"
    raw_dir.mkdir(parents=True)
    (raw_dir / "cve-2099-0001.json").write_text(
        """
{
  "cve_id": "CVE-2099-0001",
  "title": "Demo product path traversal",
  "description": "Path traversal allows reading arbitrary files.",
  "link": "https://nvd.nist.gov/vuln/detail/CVE-2099-0001",
  "published": "2099-01-01",
  "source": "nvd",
  "tags": ["path traversal"]
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(static_loader, "get_repo_root", lambda: root)

    context = static_loader.load_static_context("rag-snap-20251108")

    assert "# CVE Record: CVE-2099-0001" in context
    assert "- Title: Demo product path traversal" in context
    assert "- Description: Path traversal allows reading arbitrary files." in context
    assert "- Source: nvd" in context
    assert "MVP fallback context" in context


def test_load_static_context_falls_back_to_mvp_sample_when_snapshot_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    root = tmp_path
    processed_dir = root / "rag" / "corpus" / "processed" / "mvp-sample"
    processed_dir.mkdir(parents=True)
    (processed_dir / "context.md").write_text("MVP fallback context", encoding="utf-8")
    monkeypatch.setattr(static_loader, "get_repo_root", lambda: root)

    context = static_loader.load_static_context("rag-snap-20990101")

    assert "MVP fallback context" in context


def test_load_static_context_formats_nested_nvd_cve_records(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path
    raw_dir = root / "rag" / "corpus" / "raw" / "poc" / "20251109"
    raw_dir.mkdir(parents=True)
    (raw_dir / "cve-2099-0042.json").write_text(
        json.dumps(
            {
                "cve": {
                    "id": "CVE-2099-0042",
                    "descriptions": [
                        {"lang": "en", "value": "Reflected cross-site scripting in the demo search page."}
                    ],
                    "weaknesses": [
                        {"description": [{"lang": "en", "value": "CWE-79"}]}
                    ],
                    "references": {
                        "referenceData": [{"url": "https://vendor.example/advisory/CVE-2099-0042"}]
                    },
                    "published": "2099-02-03T00:00:00.000",
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(static_loader, "get_repo_root", lambda: root)

    context = static_loader.load_static_context("rag-snap-20251109")

    assert "# CVE Record: CVE-2099-0042" in context
    assert "- Description: Reflected cross-site scripting in the demo search page." in context
    assert "- Weaknesses: CWE-79" in context
    assert "- Link: https://vendor.example/advisory/CVE-2099-0042" in context
    assert "- Source: nvd" in context


def test_load_static_context_expands_nvd_vulnerabilities_array(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path
    raw_dir = root / "rag" / "corpus" / "raw" / "poc" / "20251110"
    raw_dir.mkdir(parents=True)
    (raw_dir / "nvd-response.json").write_text(
        json.dumps(
            {
                "vulnerabilities": [
                    {
                        "cve": {
                            "id": "CVE-2099-0001",
                            "descriptions": [{"lang": "en", "value": "SQL injection issue."}],
                            "weaknesses": [{"description": [{"lang": "en", "value": "CWE-89"}]}],
                        }
                    },
                    {
                        "cve": {
                            "id": "CVE-2099-0042",
                            "descriptions": [{"lang": "en", "value": "XSS issue."}],
                            "weaknesses": [{"description": [{"lang": "en", "value": "CWE-79"}]}],
                        }
                    },
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(static_loader, "get_repo_root", lambda: root)

    context = static_loader.load_static_context("rag-snap-20251110")

    assert "# CVE Record: CVE-2099-0001" in context
    assert "# CVE Record: CVE-2099-0042" in context
    assert "- Weaknesses: CWE-89" in context
    assert "- Weaknesses: CWE-79" in context
