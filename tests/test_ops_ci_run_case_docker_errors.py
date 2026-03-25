from __future__ import annotations

import subprocess

import pytest

from tests.e2e import run_case


def test_ensure_docker_ready_classifies_permission_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_case.shutil, "which", lambda _: "/usr/bin/docker")

    def _raise_permission_denied(*_args, **_kwargs):
        raise subprocess.CalledProcessError(
            1,
            ["docker", "info"],
            stderr=(
                b"ERROR: permission denied while trying to connect to the Docker daemon socket at "
                b"unix:///var/run/docker.sock: connect: operation not permitted"
            ),
        )

    monkeypatch.setattr(run_case.subprocess, "run", _raise_permission_denied)

    with pytest.raises(run_case.CaseError, match="docker daemon permission denied"):
        run_case._ensure_docker_ready({})


def test_ensure_docker_ready_keeps_generic_unreachable_class(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_case.shutil, "which", lambda _: "/usr/bin/docker")

    def _raise_unreachable(*_args, **_kwargs):
        raise subprocess.CalledProcessError(
            1,
            ["docker", "info"],
            stderr=b"ERROR: cannot connect to the Docker daemon at unix:///var/run/docker.sock",
        )

    monkeypatch.setattr(run_case.subprocess, "run", _raise_unreachable)

    with pytest.raises(run_case.CaseError, match="docker daemon is not reachable"):
        run_case._ensure_docker_ready({})
