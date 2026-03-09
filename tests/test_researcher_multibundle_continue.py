from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import agents.researcher.main as researcher_main


def test_researcher_skips_supported_bundle_and_continues(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-research-skip"
    bundles = [
        SimpleNamespace(vuln_id="NAME-OPEN-REDIRECT", slug="name-open-redirect"),
        SimpleNamespace(vuln_id="NAME-CUSTOM-WEIRD-VULN", slug="name-custom-weird-vuln"),
    ]
    captured: dict = {}

    class DummyService:
        def __init__(self, sid: str, **kwargs) -> None:
            self.bundle = kwargs["bundle"]
            self.metadata_dir = tmp_path / "metadata" / sid / "bundles" / self.bundle.slug
            self.metadata_dir.mkdir(parents=True, exist_ok=True)

        def write_skip_report(self, reason: str) -> Path:
            path = self.metadata_dir / "researcher_report.json"
            path.write_text(reason, encoding="utf-8")
            return path

        def write_fail_closed_report(self, *, reason: str, terminal_failure_class: str, fix_hint: str = "") -> Path:
            path = self.metadata_dir / "researcher_report.json"
            path.write_text(f"{terminal_failure_class}:{reason}:{fix_hint}", encoding="utf-8")
            return path

        def run(self) -> Path:
            path = self.metadata_dir / "researcher_report.json"
            path.write_text("ok", encoding="utf-8")
            return path

    monkeypatch.setattr(
        researcher_main,
        "parse_args",
        lambda: argparse.Namespace(
            sid=sid,
            mode="deterministic",
            search_limit=3,
        ),
    )
    monkeypatch.setattr(
        researcher_main,
        "load_plan",
        lambda _sid: {"requirement": {"researcher": {}}, "policy": {}, "paths": {"metadata": str(tmp_path)}},
    )
    monkeypatch.setattr(researcher_main, "load_vuln_bundles", lambda _plan: bundles)
    monkeypatch.setattr(researcher_main, "ResearcherService", DummyService)
    monkeypatch.setattr(
        researcher_main,
        "can_resolve_without_remote_research_for_requirement",
        lambda vuln_id, requirement: vuln_id == "NAME-OPEN-REDIRECT",
    )
    monkeypatch.setattr(
        researcher_main,
        "_write_index",
        lambda _sid, reports: captured.update({"sid": _sid, "reports": reports}),
    )

    researcher_main.main()

    assert captured["sid"] == sid
    assert captured["reports"][0]["status"] == "skipped"
    assert captured["reports"][1]["status"] == "success"


def test_researcher_fail_closes_preseeded_unsupported_bundle_and_continues(tmp_path: Path, monkeypatch) -> None:
    sid = "sid-research-fail-closed"
    bundles = [
        SimpleNamespace(vuln_id="NAME-CUSTOM-WEIRD-VULN", slug="name-custom-weird-vuln"),
        SimpleNamespace(vuln_id="NAME-OPEN-REDIRECT", slug="name-open-redirect"),
    ]
    captured: dict = {}

    class DummyService:
        def __init__(self, sid: str, **kwargs) -> None:
            self.bundle = kwargs["bundle"]
            self.metadata_dir = tmp_path / "metadata" / sid / "bundles" / self.bundle.slug
            self.metadata_dir.mkdir(parents=True, exist_ok=True)

        def write_skip_report(self, reason: str) -> Path:
            path = self.metadata_dir / "researcher_report.json"
            path.write_text(reason, encoding="utf-8")
            return path

        def write_fail_closed_report(self, *, reason: str, terminal_failure_class: str, fix_hint: str = "") -> Path:
            path = self.metadata_dir / "researcher_report.json"
            path.write_text(f"{terminal_failure_class}:{reason}:{fix_hint}", encoding="utf-8")
            return path

        def run(self) -> Path:
            path = self.metadata_dir / "researcher_report.json"
            path.write_text("ok", encoding="utf-8")
            return path

    monkeypatch.setattr(
        researcher_main,
        "parse_args",
        lambda: argparse.Namespace(
            sid=sid,
            mode="deterministic",
            search_limit=3,
        ),
    )
    monkeypatch.setattr(
        researcher_main,
        "load_plan",
        lambda _sid: {"requirement": {"researcher": {}}, "policy": {}, "paths": {"metadata": str(tmp_path)}},
    )
    monkeypatch.setattr(researcher_main, "load_vuln_bundles", lambda _plan: bundles)
    monkeypatch.setattr(researcher_main, "ResearcherService", DummyService)
    monkeypatch.setattr(
        researcher_main,
        "can_resolve_without_remote_research_for_requirement",
        lambda vuln_id, requirement: vuln_id == "NAME-OPEN-REDIRECT",
    )
    monkeypatch.setattr(
        researcher_main,
        "load_semantic_profile",
        lambda metadata_dir: (
            {"support_level": "unsupported", "compiler_supported": False, "compiler_reason": "unsupported"}
            if metadata_dir.name == "name-custom-weird-vuln"
            else {"support_level": "compiler_supported", "compiler_supported": True}
        ),
    )
    monkeypatch.setattr(
        researcher_main,
        "_write_index",
        lambda _sid, reports: captured.update({"sid": _sid, "reports": reports}),
    )

    try:
        researcher_main.main()
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("researcher_main.main() should exit non-zero for fail-closed bundle")

    assert captured["sid"] == sid
    assert captured["reports"][0]["status"] == "failed"
    assert "Semantic profile marks unsupported free-form family before generation" in captured["reports"][0]["error"]
    assert captured["reports"][1]["status"] == "skipped"
