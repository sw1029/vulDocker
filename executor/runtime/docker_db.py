"""Docker executor that provisions an application + DB pair inside an isolated network."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.logging import get_logger
from common.paths import ensure_dir, get_artifacts_dir, get_workspace_dir

LOGGER = get_logger(__name__)
DOCKER_BIN = shutil.which("docker")
SYFT_BIN = shutil.which("syft")


class ExecutorError(RuntimeError):
    """Raised on runtime failures."""


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
    _write_image_metadata(image_tag, build_dir)


def _write_image_metadata(image_tag: str, build_dir: Path) -> None:
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
        _generate_sbom(image_tag, build_dir / "sbom.spdx.json")
    else:
        LOGGER.warning("Syft not found; skipping SBOM generation")


def _generate_sbom(image_tag: str, destination: Path) -> None:
    """Run syft with both the new (scan) and legacy CLI styles for compatibility."""

    commands = [
        {
            "cmd": [SYFT_BIN, "scan", f"docker:{image_tag}", "--output", f"spdx-json={destination}"],
            "writes_to_file": True,
        },
        {
            "cmd": [SYFT_BIN, "packages", f"docker:{image_tag}", "-o", "spdx-json"],
            "writes_to_file": False,
        },
        {
            "cmd": [SYFT_BIN, f"docker:{image_tag}", "-o", "spdx-json"],
            "writes_to_file": False,
        },
    ]
    for idx, item in enumerate(commands, start=1):
        cmd = item["cmd"]
        LOGGER.info("Generating SBOM via syft (attempt %s): %s", idx, " ".join(cmd))
        if item["writes_to_file"]:
            proc = subprocess.run(cmd, text=True, check=False)
            stdout, stderr = "", ""
        else:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            stdout, stderr = proc.stdout, proc.stderr
        if proc.returncode == 0:
            if not item["writes_to_file"]:
                destination.write_text(stdout, encoding="utf-8")
            return
        LOGGER.warning(
            "Syft attempt %s failed (exit %s): %s",
            idx,
            proc.returncode,
            (stderr or "").strip(),
        )
    LOGGER.error("All syft attempts failed; SBOM was not generated for %s", image_tag)


def create_network(network_name: str, log_path: Path) -> None:
    subprocess.run(
        [DOCKER_BIN, "network", "rm", network_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    cmd = [DOCKER_BIN, "network", "create", "--internal", network_name]
    run_command(cmd, log_path)


def remove_network(network_name: str) -> None:
    subprocess.run([DOCKER_BIN, "network", "rm", network_name], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def start_db_container(sid: str, network: str, db_config: Dict[str, str], log_path: Path) -> str:
    name = f"{sid}-db"
    env_args = []
    for key, value in db_config.items():
        if key == "IMAGE":
            continue
        env_args.extend(["-e", f"{key}={value}"])
    cmd = [
        DOCKER_BIN,
        "run",
        "-d",
        "--rm",
        "--name",
        name,
        "--network",
        network,
        "--health-cmd",
        "mysqladmin ping -h 127.0.0.1 -psqli_root_pw || exit 1",
        "--health-interval",
        "5s",
        "--health-retries",
        "20",
        *env_args,
        db_config.get("IMAGE", "mysql:8.0"),
    ]
    run_command(cmd, log_path)
    return name


def wait_for_db(container_name: str, timeout: int, log_path: Path) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        proc = subprocess.run(
            [
                DOCKER_BIN,
                "exec",
                container_name,
                "mysqladmin",
                "ping",
                "-h",
                "127.0.0.1",
                "-psqli_root_pw",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            return
        time.sleep(2)
    run_command(
        [DOCKER_BIN, "logs", container_name],
        log_path,
        check=False,
    )
    raise ExecutorError("Database did not become healthy within timeout")


def start_app_container(sid: str, network: str, image_tag: str, env: Dict[str, str], log_path: Path) -> str:
    name = f"{sid}-app"
    env_args = []
    for key, value in env.items():
        env_args.extend(["-e", f"{key}={value}"])
    cmd = [
        DOCKER_BIN,
        "run",
        "-d",
        "--rm",
        "--name",
        name,
        "--network",
        network,
        *env_args,
        image_tag,
    ]
    run_command(cmd, log_path)
    return name


def stop_container(name: str) -> None:
    subprocess.run([DOCKER_BIN, "stop", name], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def execute_poc(container_name: str, log_path: Path, port: int) -> None:
    exec_cmd = [
        DOCKER_BIN,
        "exec",
        container_name,
        "python",
        "poc.py",
        "--base-url",
        f"http://127.0.0.1:{port}",
    ]
    run_command(exec_cmd, log_path)


def collect_logs(container_name: str, destination: Path) -> None:
    with destination.open("w", encoding="utf-8") as handle:
        subprocess.run([DOCKER_BIN, "logs", container_name], stdout=handle, stderr=subprocess.STDOUT, text=True, check=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Docker executor with dedicated DB container")
    parser.add_argument("--sid", required=True)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--db-image", default="mysql:8.0")
    parser.add_argument("--db-user", default="sqli")
    parser.add_argument("--db-password", default="sqli_pw")
    parser.add_argument("--db-name", default="sqliapp")
    parser.add_argument("--app-port", type=int, default=5000)
    return parser.parse_args()


def main() -> None:
    if DOCKER_BIN is None:
        raise ExecutorError("Docker binary not available")
    args = parse_args()
    sid = args.sid
    workspace = get_workspace_dir(sid)
    build_dir = ensure_dir(get_artifacts_dir(sid) / "build")
    run_dir = ensure_dir(get_artifacts_dir(sid) / "run")
    image_tag = f"{sid}-app"
    network_name = f"{sid}-net"

    do_build = args.build or not (args.build or args.run)
    do_run = args.run or not (args.build or args.run)

    if do_build:
        build_image(sid, workspace, build_dir, image_tag)
    if not do_run:
        return

    run_log = run_dir / "run.log"
    run_log.write_text("", encoding="utf-8")
    db_log = run_dir / "db.log"
    db_log.write_text("", encoding="utf-8")

    db_config = {
        "IMAGE": args.db_image,
        "MYSQL_ROOT_PASSWORD": "sqli_root_pw",
        "MYSQL_DATABASE": args.db_name,
        "MYSQL_USER": args.db_user,
        "MYSQL_PASSWORD": args.db_password,
    }
    app_env = {
        "DB_HOST": f"{sid}-db",
        "DB_PORT": "3306",
        "DB_USER": args.db_user,
        "DB_PASSWORD": args.db_password,
        "DB_NAME": args.db_name,
        "APP_PORT": str(args.app_port),
    }

    db_container = None
    app_container = None
    try:
        create_network(network_name, run_log)
        db_container = start_db_container(sid, network_name, db_config, db_log)
        wait_for_db(db_container, timeout=120, log_path=db_log)
        app_container = start_app_container(sid, network_name, image_tag, app_env, run_log)
        # Allow app to warm up before executing PoC.
        time.sleep(5)
        execute_poc(app_container, run_log, args.app_port)
        collect_logs(app_container, run_dir / "app_container.log")
        collect_logs(db_container, run_dir / "db_container.log")
    finally:
        if app_container:
            stop_container(app_container)
        if db_container:
            stop_container(db_container)
        remove_network(network_name)

    summary = {
        "sid": sid,
        "image_tag": image_tag,
        "network": network_name,
        "db_image": args.db_image,
        "run_log": str(run_log),
        "db_log": str(db_log),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    LOGGER.info("Executor completed with summary: %s", summary)


if __name__ == "__main__":
    main()
