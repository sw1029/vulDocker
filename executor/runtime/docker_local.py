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
    bundle_requirement,
    is_multi_vuln,
    load_vuln_bundles,
    metadata_dir_for_bundle,
    workspace_dir_for_bundle,
)

LOGGER = get_logger(__name__)
DOCKER_BIN = shutil.which("docker")
SYFT_BIN = shutil.which("syft")


class ExecutorError(RuntimeError):
    def __init__(self, message: str, returncode: int | None = None):
        super().__init__(message)
        self.returncode = returncode


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
        raise ExecutorError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}",
            returncode=proc.returncode,
        )
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
    workspace: Path,
    run_dir: Path,
    executor_policy: Dict[str, Any],
    network_alias: "NetworkHandle",
    payloads: List[str] | None = None,
) -> int:
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
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=64m",
        "--security-opt",
        "no-new-privileges:true",
        "--cap-drop",
        "ALL",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "--network",
        network_mode,
        image_tag,
    ]
    last_exit_code = None
    try:
        run_command(start_cmd, run_log)
        time.sleep(1)
        logs_cmd = [DOCKER_BIN, "logs", container_name]
        _push_poc_script(workspace, container_name, run_log)
        try:
            _wait_for_app_ready(container_name, run_log)
        except ExecutorError:
            run_command(logs_cmd, run_log, check=False)
            raise
        payload_list = payloads or [None]
        for index, payload in enumerate(payload_list, start=1):
            exec_cmd = [
                DOCKER_BIN,
                "exec",
                container_name,
                "python",
                "/tmp/poc.py",
                "--base-url",
                "http://127.0.0.1:5000",
            ]
            if payload:
                exec_cmd.extend(["--payload", payload])
            if len(payload_list) > 1:
                with run_log.open("a", encoding="utf-8") as handle:
                    handle.write(f"\n# Payload {index}: {payload or 'default'}\n")
            try:
                proc = run_command(exec_cmd, run_log)
                last_exit_code = proc.returncode
            except ExecutorError as exc:
                if last_exit_code is None and getattr(exc, "returncode", None) is not None:
                    last_exit_code = exc.returncode
                run_command(logs_cmd, run_log, check=False)
                raise
        run_command(logs_cmd, run_log, check=False)
        return last_exit_code if last_exit_code is not None else 0
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
    bundle_requirement_view = bundle_requirement(plan["requirement"], bundle)
    payloads_raw = bundle_requirement_view.get("poc_payloads")
    poc_payloads: List[str] = []
    if isinstance(payloads_raw, list):
        for entry in payloads_raw:
            if isinstance(entry, str) and entry.strip():
                poc_payloads.append(entry)
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
        "invocation": None,
        "build_attempted": False,
        "run_attempted": False,
        "exit_code": None,
    }

    current_stage: Optional[str] = None
    sidecars: List[Dict[str, str]] = []
    network_handle = network_pool.acquire(bundle)
    summary["network_mode"] = network_handle.mode
    needs_sidecars = _bundle_requires_external_db(plan, bundle)
    if do_build and do_run:
        summary["invocation"] = "build+run"
    elif do_build:
        summary["invocation"] = "build"
    elif do_run:
        summary["invocation"] = "run"
    else:
        summary["invocation"] = "noop"
    try:
        if do_build:
            current_stage = "build"
            summary["build_attempted"] = True
            build_image(sid, workspace, build_dir, image_tag)
            summary["build_passed"] = True
        if do_run:
            current_stage = "run"
            summary["run_attempted"] = True
            if needs_sidecars:
                sidecars = _start_sidecars(sid, bundle, executor_policy, run_dir, network_handle)
            else:
                sidecars = []
            summary["sidecars"] = sidecars
            exit_code = run_container_with_poc(
                sid,
                bundle,
                image_tag,
                workspace,
                run_dir,
                executor_policy,
                network_handle,
                payloads=poc_payloads,
            )
            summary["run_passed"] = True
            summary["executed"] = True
            summary["exit_code"] = exit_code
    except ExecutorError as exc:
        summary["error"] = str(exc)
        summary["failed_stage"] = current_stage
        if summary.get("exit_code") is None and getattr(exc, "returncode", None) is not None:
            summary["exit_code"] = exc.returncode
    finally:
        _stop_sidecars(sidecars)
        network_pool.release(network_handle)
        summary_path = run_dir / "summary.json"
        previous: Dict[str, Any] = {}
        if summary_path.exists():
            try:
                previous = json.loads(summary_path.read_text(encoding="utf-8"))
            except Exception:
                previous = {}
        merged = dict(previous)
        merged.update(summary)
        merged["build_passed"] = _merge_stage_flag(previous, summary, "build_passed", "build_attempted")
        merged["run_passed"] = _merge_stage_flag(previous, summary, "run_passed", "run_attempted")
        merged["executed"] = _merge_stage_flag(previous, summary, "executed", "run_attempted")
        if not merged.get("invocation") and previous.get("invocation"):
            merged["invocation"] = previous.get("invocation")
        if summary.get("exit_code") is None and previous.get("exit_code") is not None:
            merged.setdefault("exit_code", previous.get("exit_code"))
        summary_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        summary = merged
    LOGGER.info("Executor bundle completed: %s", summary)
    return summary


def _write_index(sid: str, summaries: List[Dict[str, str]]) -> None:
    run_root = ensure_dir(get_artifacts_dir(sid) / "run")
    index_path = run_root / "index.json"

    # Merge with existing index to preserve build/run states across separate invocations
    existing: Dict[str, Any] = {}
    if index_path.exists():
        try:
            old = json.loads(index_path.read_text(encoding="utf-8"))
            for entry in (old.get("runs") or []):
                slug = entry.get("slug") or entry.get("vuln_id")
                if slug:
                    existing[slug] = entry
        except Exception:
            existing = {}

    merged: Dict[str, Dict[str, Any]] = dict(existing)
    for entry in summaries:
        slug = entry.get("slug") or entry.get("vuln_id")
        if not slug:
            continue
        prev = merged.get(slug, {})
        # Boolean fields: preserve any prior True
        build_passed = _merge_stage_flag(prev, entry, "build_passed", "build_attempted")
        run_passed = _merge_stage_flag(prev, entry, "run_passed", "run_attempted")
        executed = _merge_stage_flag(prev, entry, "executed", "run_attempted")
        exit_code = entry.get("exit_code")
        if exit_code is None:
            exit_code = prev.get("exit_code")

        merged[slug] = {
            **prev,
            **entry,
            "build_passed": build_passed,
            "run_passed": run_passed,
            "executed": executed,
            "exit_code": exit_code,
        }

    payload = {"sid": sid, "runs": list(merged.values())}
    index_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    LOGGER.info("Executor index written to %s", index_path)


def _merge_stage_flag(
    previous: Optional[Dict[str, Any]],
    current: Dict[str, Any],
    field: str,
    attempted_field: str,
) -> bool:
    if current.get(attempted_field):
        return bool(current.get(field))
    if previous:
        return bool(previous.get(field))
    return bool(current.get(field))


def _bundle_requires_external_db(plan: Dict[str, Any], bundle: VulnBundle) -> bool:
    metadata_dir = metadata_dir_for_bundle(plan, bundle)
    template_summary = metadata_dir / "generator_template.json"
    manifest_path = metadata_dir / "generator_manifest.json"
    for path in (manifest_path, template_summary):
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            value = data.get("requires_external_db")
            if value is not None:
                return bool(value)
    requirement = bundle_requirement(plan["requirement"], bundle)
    runtime = requirement.get("runtime") or {}
    db = str(runtime.get("db") or "").strip().lower()
    return db in {"mysql", "postgres", "postgresql", "mariadb"}


def _push_poc_script(workspace: Path, container_name: str, log_path: Path) -> None:
    if DOCKER_BIN is None:
        raise ExecutorError("Docker binary not available for copying PoC script")
    poc_path = workspace / "poc.py"
    if not poc_path.exists():
        raise ExecutorError(f"PoC script missing at {poc_path}")
    data = poc_path.read_bytes()
    cmd = [
        DOCKER_BIN,
        "exec",
        "-i",
        container_name,
        "sh",
        "-c",
        "cat > /tmp/poc.py && chmod 0644 /tmp/poc.py",
    ]
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("$ " + " ".join(cmd) + "\n")
        proc = subprocess.run(cmd, input=data, stdout=handle, stderr=subprocess.STDOUT, check=False)
    if proc.returncode != 0:
        raise ExecutorError(f"Command failed ({proc.returncode}): {' '.join(cmd)}")


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
        _wait_for_sidecar(entry, container_name, run_log)
        records.append({"name": name, "container": container_name, "image": image})
    return records


def _wait_for_sidecar(entry: Dict[str, Any], container_name: str, log_path: Path) -> None:
    probe = entry.get("ready_probe") or {}
    probe_type = (probe.get("type") or "").strip().lower()
    if probe_type == "mysql":
        _probe_mysql_sidecar(entry, container_name, log_path, probe)
        return
    delay = int(probe.get("wait_seconds", 5))
    if delay > 0:
        time.sleep(delay)


def _probe_mysql_sidecar(
    entry: Dict[str, Any], container_name: str, log_path: Path, probe: Dict[str, Any]
) -> None:
    if DOCKER_BIN is None:
        raise ExecutorError("Docker binary not available for mysql probes")
    env = entry.get("env") or {}
    user = probe.get("user") or env.get("MYSQL_USER") or env.get("MYSQL_ROOT_USER") or "root"
    password = probe.get("password") or env.get("MYSQL_PASSWORD") or env.get("MYSQL_ROOT_PASSWORD") or ""
    host = probe.get("host") or "127.0.0.1"
    retries = int(probe.get("retries", 10))
    interval = float(probe.get("interval", 2.0))
    command = [
        DOCKER_BIN,
        "exec",
        container_name,
        "mysqladmin",
        "-h",
        host,
        "-u",
        user,
    ]
    if password:
        command.append(f"-p{password}")
    command.append("ping")
    for attempt in range(1, retries + 1):
        proc = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if proc.returncode == 0:
            return
        time.sleep(interval)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"mysql readiness probe failed for {container_name}\n")
    raise ExecutorError(f"mysql sidecar did not become ready: {container_name}")


def _wait_for_app_ready(container_name: str, log_path: Path, port: int = 5000, retries: int = 10, delay: float = 1.5) -> None:
    if DOCKER_BIN is None:
        raise ExecutorError("Docker binary not available for app readiness probe")
    script = "import socket,sys;s=socket.socket();s.settimeout(1);s.connect(('127.0.0.1', int(sys.argv[1])));s.close()"
    for attempt in range(1, retries + 1):
        proc = subprocess.run(
            [DOCKER_BIN, "exec", container_name, "python", "-c", script, str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if proc.returncode == 0:
            return
        time.sleep(delay)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"application readiness probe failed for {container_name}\n")
    raise ExecutorError(f"application in {container_name} did not become ready on port {port}")


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
