"""Docker-based executor for the MVP scenario."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.logging import get_logger
from common.paths import ensure_dir, get_artifacts_dir
from common.plan import load_plan
from common.run_matrix import (
    VulnBundle,
    artifacts_dir_for_bundle,
    is_multi_vuln,
    load_vuln_bundles,
    workspace_dir_for_bundle,
)

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


def run_container_with_poc(
    sid: str,
    bundle: VulnBundle,
    image_tag: str,
    run_dir: Path,
    executor_policy: Dict[str, Any],
    network_alias: "NetworkHandle",
) -> None:
    if DOCKER_BIN is None:
        raise ExecutorError("Docker binary not available")
    run_log = run_dir / "run.log"
    run_log.write_text("", encoding="utf-8")
    container_name = f"{sid}-{bundle.slug}-runtime"
    network_mode = network_alias.mode
    start_cmd = [
        DOCKER_BIN,
        "run",
        "-d",
        "--rm",
        "--name",
        container_name,
        "--network",
        network_mode,
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
        logs_cmd = [DOCKER_BIN, "logs", container_name]
        try:
            run_command(exec_cmd, run_log)
        except ExecutorError:
            run_command(logs_cmd, run_log, check=False)
            raise
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
    plan = load_plan(args.sid)
    bundles = load_vuln_bundles(plan)
    multi = is_multi_vuln(plan)
    policy = plan.get("policy", {})
    executor_policy = (policy.get("executor") or {})
    stop_on_first_failure = bool(policy.get("stop_on_first_failure"))
    network_pool = NetworkPool(plan["sid"], executor_policy)
    summaries: List[Dict[str, str]] = []
    had_error = False
    for bundle in bundles:
        summary = _run_bundle(
            args,
            plan,
            bundle,
            multi,
            stop_on_first_failure,
            executor_policy,
            network_pool,
        )
        summaries.append(summary)
        if summary.get("error"):
            had_error = True
            LOGGER.error(
                "Executor recorded failure for %s (%s): %s",
                plan["sid"],
                bundle.vuln_id,
                summary["error"],
            )
            if stop_on_first_failure:
                LOGGER.info("stop_on_first_failure policy engaged; halting remaining bundles.")
                break
    _write_index(args.sid, summaries)
    if had_error:
        raise SystemExit(1)


def _run_bundle(
    args: argparse.Namespace,
    plan: Dict[str, Any],
    bundle: VulnBundle,
    multi: bool,
    stop_on_first_failure: bool,
    executor_policy: Dict[str, Any],
    network_pool: "NetworkPool",
) -> Dict[str, Any]:
    sid = args.sid
    workspace = workspace_dir_for_bundle(plan, bundle)
    build_dir = artifacts_dir_for_bundle(plan, bundle, "build")
    run_dir = artifacts_dir_for_bundle(plan, bundle, "run")
    image_tag = f"{sid}-{bundle.slug}" if multi else sid
    do_build = args.build or not (args.build or args.run)
    do_run = args.run or not (args.build or args.run)

    summary = {
        "sid": sid,
        "vuln_id": bundle.vuln_id,
        "slug": bundle.slug,
        "image_tag": image_tag,
        "build_log": str(build_dir / "build.log"),
        "run_log": str(run_dir / "run.log"),
        "build_passed": False,
        "run_passed": False,
        "executed": False,
        "error": None,
        "failed_stage": None,
        "stop_on_first_failure": stop_on_first_failure,
        "network_mode": None,
        "sidecars": [],
    }

    current_stage: Optional[str] = None
    sidecars: List[Dict[str, str]] = []
    network_handle = network_pool.acquire(bundle)
    summary["network_mode"] = network_handle.mode
    try:
        if do_build:
            current_stage = "build"
            build_image(sid, workspace, build_dir, image_tag)
            summary["build_passed"] = True
        if do_run:
            current_stage = "run"
            sidecars = _start_sidecars(sid, bundle, executor_policy, run_dir, network_handle)
            summary["sidecars"] = sidecars
            run_container_with_poc(sid, bundle, image_tag, run_dir, executor_policy, network_handle)
            summary["run_passed"] = True
            summary["executed"] = True
    except ExecutorError as exc:
        summary["error"] = str(exc)
        summary["failed_stage"] = current_stage
    finally:
        _stop_sidecars(sidecars)
        network_pool.release(network_handle)
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    LOGGER.info("Executor bundle completed: %s", summary)
    return summary


def _write_index(sid: str, summaries: List[Dict[str, str]]) -> None:
    run_root = ensure_dir(get_artifacts_dir(sid) / "run")
    index_path = run_root / "index.json"
    payload = {"sid": sid, "runs": summaries}
    index_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    LOGGER.info("Executor index written to %s", index_path)


def _start_sidecars(
    sid: str,
    bundle: VulnBundle,
    executor_policy: Dict[str, Any],
    run_dir: Path,
    network_alias: "NetworkHandle",
) -> List[Dict[str, str]]:
    sidecars_cfg = executor_policy.get("sidecars") or []
    if not sidecars_cfg:
        return []
    if DOCKER_BIN is None:
        raise ExecutorError("Docker binary not available for sidecars")
    if network_alias.mode in {"none"}:
        raise ExecutorError("Sidecars require an executor network but allow_network is false")
    run_log = run_dir / "run.log"
    records: List[Dict[str, str]] = []
    for entry in sidecars_cfg:
        image = entry.get("image")
        if not image:
            continue
        name = entry.get("name") or "sidecar"
        container_name = f"{sid}-{bundle.slug}-{name}"
        cmd = [
            DOCKER_BIN,
            "run",
            "-d",
            "--rm",
            "--name",
            container_name,
            "--network",
            network_alias.mode,
        ]
        env = entry.get("env") or {}
        for key, value in env.items():
            cmd.extend(["-e", f"{key}={value}"])
        aliases = entry.get("aliases") or []
        for alias in aliases:
            cmd.extend(["--network-alias", alias])
        cmd.append(image)
        run_command(cmd, run_log)
        _wait_for_sidecar(entry.get("ready_probe") or {}, container_name, run_log)
        records.append({"name": name, "container": container_name, "image": image})
    return records


def _wait_for_sidecar(probe: Dict[str, Any], container_name: str, log_path: Path) -> None:
    delay = int(probe.get("wait_seconds", 5))
    if delay > 0:
        time.sleep(delay)


def _stop_sidecars(sidecars: List[Dict[str, str]]) -> None:
    if not sidecars:
        return
    for entry in sidecars:
        container = entry.get("container")
        if container:
            subprocess.run([DOCKER_BIN, "stop", container], check=False)


class NetworkHandle:
    def __init__(self, mode: str) -> None:
        self.mode = mode


class NetworkPool:
    def __init__(self, sid: str, policy: Dict[str, Any]) -> None:
        self.sid = sid
        self.policy = policy
        self.allow_network = bool(policy.get("allow_network"))
        self.sidecars = policy.get("sidecars") or []
        self.explicit_name = (policy.get("network_name") or "").strip() or None
        self.mode = self._resolve_mode()

    def acquire(self, bundle: VulnBundle) -> NetworkHandle:
        return NetworkHandle(self.mode)

    def release(self, handle: NetworkHandle) -> None:
        pass

    def _resolve_mode(self) -> str:
        if not self.allow_network:
            return "none"
        if self.explicit_name:
            self._ensure_network(self.explicit_name)
            return self.explicit_name
        if any(entry.get("aliases") for entry in self.sidecars):
            name = f"{self.sid}-net"
            self._ensure_network(name)
            return name
        return self.policy.get("network_mode") or "bridge"

    def _ensure_network(self, name: str) -> None:
        inspect = subprocess.run(
            [DOCKER_BIN, "network", "inspect", name],
            capture_output=True,
            text=True,
            check=False,
        )
        if inspect.returncode == 0:
            return
        inspect = subprocess.run(
            [DOCKER_BIN, "network", "create", name],
            capture_output=True,
            text=True,
            check=False,
        )
        if inspect.returncode != 0:
            raise ExecutorError(f"Failed to create network {name}: {inspect.stderr.strip()}")


if __name__ == "__main__":
    main()
