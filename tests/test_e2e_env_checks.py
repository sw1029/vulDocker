from __future__ import annotations

from types import SimpleNamespace

from tests.e2e import test_cases


def test_e2e_skip_reason_reports_unreachable_docker_daemon(monkeypatch) -> None:
    monkeypatch.setenv("VULD_RUN_E2E", "1")
    monkeypatch.setattr(test_cases.shutil, "which", lambda name: "/usr/bin/docker")
    monkeypatch.setattr(
        test_cases.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="daemon down"),
    )
    test_cases._docker_ready_reason.cache_clear()

    assert test_cases._skip_reason() == "Docker daemon is not reachable"

    test_cases._docker_ready_reason.cache_clear()
