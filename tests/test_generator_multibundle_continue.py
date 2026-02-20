from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import agents.generator.main as generator_main


def test_generator_continues_across_bundles_when_stop_on_first_failure_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sid = "sid-multi"
    bundles = [
        SimpleNamespace(vuln_id="CWE-89", slug="cwe-89"),
        SimpleNamespace(vuln_id="CWE-352", slug="cwe-352"),
    ]
    captured: dict = {}

    class DummyService:
        def __init__(self, sid: str, **kwargs) -> None:
            bundle = kwargs["bundle"]
            self.bundle = bundle
            self.workspace = tmp_path / "workspaces" / bundle.slug
            self.workspace.mkdir(parents=True, exist_ok=True)
            self.metadata_dir = tmp_path / "metadata" / sid / "bundles" / bundle.slug
            self.metadata_dir.mkdir(parents=True, exist_ok=True)

        def run(self) -> None:
            if self.bundle.slug == "cwe-89":
                raise RuntimeError("intentional failure")

    monkeypatch.setattr(
        generator_main,
        "parse_args",
        lambda: argparse.Namespace(
            sid=sid,
            mode="deterministic",
            template_root=None,
            single_attempt=True,
        ),
    )
    monkeypatch.setattr(generator_main, "load_plan", lambda _sid: {"policy": {"stop_on_first_failure": False}})
    monkeypatch.setattr(generator_main, "load_vuln_bundles", lambda _plan: bundles)
    monkeypatch.setattr(generator_main, "GeneratorService", DummyService)
    monkeypatch.setattr(
        generator_main,
        "_write_index",
        lambda _sid, runs: captured.update({"sid": _sid, "runs": runs}),
    )

    with pytest.raises(SystemExit) as exc:
        generator_main.main()

    assert exc.value.code == 1
    assert captured["sid"] == sid
    assert len(captured["runs"]) == 2
    assert captured["runs"][0]["status"] == "failed"
    assert captured["runs"][1]["status"] == "success"
