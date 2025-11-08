"""Docker-based executor for the MVP scenario."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.logging import get_logger
from common.paths import ensure_dir, get_artifacts_dir, get_workspace_dir

LOGGER = get_logger(__name__)
DOCKER_BIN = shutil.which("docker")
SYFT_BIN = shutil.which("syft")


class ExecutorError(RuntimeError):
    pass


def run_command(cmd: List[str], log_path: Path, check: bool = True, cwd: Path | None = None) -> subprocess.CompletedProcess:
    LOGGER.info("Running command: %s", " ".join(cmd))
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("$ " + " ".join(cmd) + "\n")
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    if check and proc.returncode != 0:
        raise ExecutorError(f"Command failed ({proc.returncode}): {' '.join(cmd)}")
    return proc


def build_image(sid: str, workspace: Path, build_dir: Path, image_tag: str) -> None:
    if DOCKER_BIN is None:
        raise ExecutorError("Docker binary not available")
    build_log = build_dir / "build.log"
    build_log.write_text("", encoding="utf-8")
    cmd = [
        DOCKER_BIN,
        "build",
        "-f",
        str(workspace / "Dockerfile"),
        "-t",
        image_tag,
        str(workspace),
    ]
    run_command(cmd, build_log, cwd=workspace)

    image_id_path = build_dir / "image_id.txt"
    inspect = subprocess.run(
        [DOCKER_BIN, "image", "inspect", image_tag, "--format", "{{.Id}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if inspect.returncode == 0:
        image_id_path.write_text(inspect.stdout.strip(), encoding="utf-8")

    if SYFT_BIN:
        sbom_path = build_dir / "sbom.spdx.json"
        with sbom_path.open("w", encoding="utf-8") as handle:
            LOGGER.info("Generating SBOM via syft")
            proc = subprocess.run(
                [SYFT_BIN, "packages", f"docker:{image_tag}", "-o", "json"],
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
            if proc.returncode != 0:
                LOGGER.warning("Syft exited with %s", proc.returncode)
    else:
        LOGGER.warning("Syft not found; skipping SBOM generation")


def run_container_with_poc(sid: str, image_tag: str, run_dir: Path) -> None:
    if DOCKER_BIN is None:
        raise ExecutorError("Docker binary not available")
    run_log = run_dir / "run.log"
    run_log.write_text("", encoding="utf-8")
    container_name = f"{sid}-runtime"
    start_cmd = [
        DOCKER_BIN,
        "run",
        "-d",
        "--rm",
        "--name",
        container_name,
        "--network",
        "none",
        image_tag,
    ]
    try:
        run_command(start_cmd, run_log)
        time.sleep(3)
        exec_cmd = [
            DOCKER_BIN,
            "exec",
            container_name,
            "python",
            "poc.py",
            "--base-url",
            "http://127.0.0.1:5000",
        ]
        run_command(exec_cmd, run_log)
        logs_cmd = [DOCKER_BIN, "logs", container_name]
        run_command(logs_cmd, run_log, check=False)
    finally:
        subprocess.run([DOCKER_BIN, "stop", container_name], check=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Docker executor")
    parser.add_argument("--sid", required=True)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sid = args.sid
    workspace = get_workspace_dir(sid)
    build_dir = ensure_dir(get_artifacts_dir(sid) / "build")
    run_dir = ensure_dir(get_artifacts_dir(sid) / "run")
    image_tag = sid

    do_build = args.build or not (args.build or args.run)
    do_run = args.run or not (args.build or args.run)

    if do_build:
        build_image(sid, workspace, build_dir, image_tag)
    if do_run:
        run_container_with_poc(sid, image_tag, run_dir)

    summary = {
        "sid": sid,
        "image_tag": image_tag,
        "build_log": str(build_dir / "build.log"),
        "run_log": str(run_dir / "run.log"),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    LOGGER.info("Executor completed: %s", summary)


if __name__ == "__main__":
    main()
