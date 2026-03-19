"""Docker-based executor for the MVP scenario."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import shlex
import subprocess
import sys
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.logging import get_logger
from common.bundle_state import bundle_research_blocker
from common.paths import ensure_dir, get_artifacts_dir
from common.plan import load_plan
from common.contracts import load_generator_contract as load_resolved_contract
from common.run_matrix import (
    VulnBundle,
    artifacts_dir_for_bundle,
    bundle_requirement,
    is_multi_vuln,
    load_vuln_bundles,
    metadata_dir_for_bundle,
    workspace_dir_for_bundle,
)
from evals.assertions import run_assertions

LOGGER = get_logger(__name__)
DOCKER_BIN = shutil.which("docker")
SYFT_BIN = shutil.which("syft")
DEFAULT_APP_PORT = 5000
ORACLE_EXECUTION_FILENAME = "oracle_execution.json"
DEFAULT_POC_ENTRY_SUFFIXES = {
    ".py",
    ".sh",
    ".js",
    ".ts",
    ".rb",
    ".php",
    ".pl",
}


class ExecutorError(RuntimeError):
    def __init__(self, message: str, returncode: int | None = None):
        super().__init__(message)
        self.returncode = returncode


def run_command(cmd: List[str], log_path: Path, check: bool = True, cwd: Path | None = None) -> subprocess.CompletedProcess:
    LOGGER.info("Running command: %s", " ".join(cmd))
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("$ " + " ".join(cmd) + "\n")
        handle.flush()
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
    metadata_dir: Path,
    run_dir: Path,
    network_alias: "NetworkHandle",
    *,
    service_port: int,
    base_url: str,
    service_env: Dict[str, str],
    poc_entry: str,
    poc_entry_source: str | None,
    poc_cmd: str | None,
    health_path: str | None,
    healthchecks: List[Dict[str, Any]] | None,
    executor_policy: Dict[str, Any] | None = None,
    payloads: List[str] | None = None,
) -> Dict[str, Any]:
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
    ]
    for key, value in service_env.items():
        start_cmd.extend(["-e", f"{key}={value}"])
    start_cmd.append(image_tag)
    last_exit_code = None
    try:
        run_command(start_cmd, run_log)
        time.sleep(1)
        logs_cmd = [DOCKER_BIN, "logs", container_name]
        try:
            _wait_for_app_ready(
                container_name,
                run_log,
                port=service_port,
                health_path=health_path,
                healthchecks=healthchecks,
            )
        except ExecutorError:
            run_command(logs_cmd, run_log, check=False)
            raise
        try:
            poc_container_path = _push_poc_script(
                workspace,
                container_name,
                run_log,
                poc_entry=poc_entry,
                poc_entry_source=poc_entry_source,
                executor_policy=executor_policy,
            )
        except ExecutorError:
            run_command(logs_cmd, run_log, check=False)
            raise
        payload_list = payloads or [None]
        for index, payload in enumerate(payload_list, start=1):
            exec_cmd = _build_poc_exec_cmd(
                container_name,
                metadata_dir,
                poc_container_path,
                base_url,
                poc_cmd=str(poc_cmd or "").strip() or None,
                payload=payload,
            )
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
        oracle_execution = _execute_oracle_replays(
            container_name=container_name,
            metadata_dir=metadata_dir,
            run_dir=run_dir,
            log_path=run_log,
            poc_path=poc_container_path,
            base_url=base_url,
            poc_cmd=str(poc_cmd or "").strip() or None,
            success_exit_code=last_exit_code if last_exit_code is not None else 0,
            success_payloads=payload_list,
        )
        run_command(logs_cmd, run_log, check=False)
        return {
            "exit_code": last_exit_code if last_exit_code is not None else 0,
            "oracle_execution": oracle_execution,
        }
    finally:
        subprocess.run([DOCKER_BIN, "rm", "-f", container_name], check=False)


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
    try:
        summaries: List[Dict[str, str]] = []
        had_error = False
        for bundle in bundles:
            research_blocker = bundle_research_blocker(plan, bundle)
            if research_blocker:
                summary = _skipped_bundle_summary(
                    args.sid,
                    bundle,
                    plan,
                    reason=str(research_blocker.get("reason") or "research blocked bundle"),
                )
                summaries.append(summary)
                continue
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
    finally:
        network_pool.close()


def _skipped_bundle_summary(
    sid: str,
    bundle: VulnBundle,
    plan: Dict[str, Any],
    *,
    reason: str,
) -> Dict[str, Any]:
    run_dir = artifacts_dir_for_bundle(plan, bundle, "run")
    build_dir = artifacts_dir_for_bundle(plan, bundle, "build")
    summary = {
        "sid": sid,
        "vuln_id": bundle.vuln_id,
        "slug": bundle.slug,
        "image_tag": f"{sid}-{bundle.slug}" if is_multi_vuln(plan) else sid,
        "build_log": str(build_dir / "build.log"),
        "run_log": str(run_dir / "run.log"),
        "build_passed": False,
        "run_passed": False,
        "executed": False,
        "error": reason,
        "failed_stage": "research_short_circuit",
        "stop_on_first_failure": bool((plan.get("policy") or {}).get("stop_on_first_failure")),
        "network_mode": None,
        "sidecars": [],
        "invocation": "skipped",
        "build_attempted": False,
        "run_attempted": False,
        "exit_code": None,
        "service_port": None,
        "service_base_url": None,
        "poc_entry": None,
        "poc_entry_source": None,
        "poc_cmd": None,
        "poc_cmd_source": None,
        "healthchecks": [],
        "healthchecks_source": None,
        "service_env_runtime": {},
        "service_env_source": None,
        "sidecars_source": None,
        "sidecar_start_order": [],
        "sidecar_start_order_source": None,
        "allow_network": None,
        "allow_network_source": None,
        "network_mode_source": None,
        "network_contract": [],
        "network_contract_source": None,
        "seed_strategy": None,
        "seed_strategy_source": None,
        "seed_files": [],
        "seed_files_source": None,
        "volume_contract": [],
        "volume_contract_source": None,
        "env_contract": [],
        "env_contract_source": None,
        "oracle_execution_path": None,
        "oracle_execution_parity": None,
        "oracle_execution": {},
        "poc_cmd": None,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    LOGGER.info("Executor bundle skipped: %s", summary)
    return summary


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
    metadata_dir = metadata_dir_for_bundle(plan, bundle)
    build_dir = artifacts_dir_for_bundle(plan, bundle, "build")
    run_dir = artifacts_dir_for_bundle(plan, bundle, "run")
    bundle_requirement_view = bundle_requirement(plan["requirement"], bundle)
    execution_surface = _resolve_execution_surface(
        metadata_dir,
        workspace,
        executor_policy,
        plan=plan,
        bundle=bundle,
    )
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
        "service_port": None,
        "service_base_url": None,
        "poc_entry": None,
        "poc_entry_source": None,
        "poc_cmd": None,
        "poc_cmd_source": None,
        "healthchecks": [],
        "healthchecks_source": None,
        "service_env_runtime": {},
        "service_env_source": None,
        "sidecars_source": None,
        "sidecar_start_order": [],
        "sidecar_start_order_source": None,
        "allow_network": None,
        "allow_network_source": None,
        "network_mode_source": None,
        "network_contract": [],
        "network_contract_source": None,
        "seed_strategy": None,
        "seed_strategy_source": None,
        "seed_apply_attempted": False,
        "seed_apply_completed": False,
        "seed_files_applied_total": 0,
        "seed_mount_targets": [],
        "seed_files": [],
        "seed_files_source": None,
        "volume_contract": [],
        "volume_contract_source": None,
        "env_contract": [],
        "env_contract_source": None,
        "oracle_execution_path": None,
        "oracle_execution_parity": None,
        "oracle_execution": {},
        "poc_cmd": None,
    }

    current_stage: Optional[str] = None
    sidecars: List[Dict[str, str]] = []
    network_handle = network_pool.acquire(bundle, execution_surface)
    _, _, _, runtime_graph = _load_contract_sections(metadata_dir)
    summary["network_mode"] = network_handle.mode
    summary["service_port_source"] = execution_surface.get("service_port_source")
    summary["service_entry_source"] = execution_surface.get("service_entry_source")
    summary["poc_entry"] = execution_surface.get("poc_entry")
    summary["poc_entry_source"] = execution_surface.get("poc_entry_source")
    summary["poc_cmd"] = execution_surface.get("poc_cmd")
    summary["poc_cmd_source"] = execution_surface.get("poc_cmd_source")
    summary["base_url_source"] = execution_surface.get("base_url_source")
    summary["health_path_source"] = execution_surface.get("health_path_source")
    summary["healthchecks"] = deepcopy(execution_surface.get("healthchecks") or [])
    summary["healthchecks_source"] = execution_surface.get("healthchecks_source")
    summary["service_env_runtime"] = deepcopy(execution_surface.get("service_env") or {})
    summary["service_env_source"] = execution_surface.get("service_env_source")
    summary["sidecars_source"] = execution_surface.get("sidecars_source")
    summary["sidecar_start_order"] = deepcopy(execution_surface.get("sidecar_start_order") or [])
    summary["sidecar_start_order_source"] = execution_surface.get("sidecar_start_order_source")
    summary["allow_network"] = bool(execution_surface.get("allow_network"))
    summary["allow_network_source"] = execution_surface.get("allow_network_source")
    summary["network_mode_source"] = execution_surface.get("network_mode_source")
    summary["network_contract"] = deepcopy(execution_surface.get("network_contract") or [])
    summary["network_contract_source"] = execution_surface.get("network_contract_source")
    summary["seed_strategy"] = execution_surface.get("seed_strategy")
    summary["seed_strategy_source"] = execution_surface.get("seed_strategy_source")
    summary["seed_files"] = deepcopy(execution_surface.get("seed_files") or [])
    summary["seed_files_source"] = execution_surface.get("seed_files_source")
    summary["volume_contract"] = deepcopy(execution_surface.get("volume_contract") or [])
    summary["volume_contract_source"] = execution_surface.get("volume_contract_source")
    summary["env_contract"] = deepcopy(execution_surface.get("env_contract") or [])
    summary["env_contract_source"] = execution_surface.get("env_contract_source")
    needs_sidecars = bool(execution_surface.get("requires_external_db"))
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
            summary["service_port"] = int(execution_surface.get("service_port") or DEFAULT_APP_PORT)
            summary["service_base_url"] = str(execution_surface.get("base_url") or "")
            _validate_service_entry_contract(workspace, execution_surface)
            _validate_poc_entry_contract(workspace, execution_surface)
            _validate_poc_cmd_contract(execution_surface)
            _validate_healthcheck_contract(execution_surface)
            _validate_service_endpoint_contract(execution_surface)
            _validate_sidecar_runtime_contract(execution_surface)
            _validate_sidecar_identity_contract(execution_surface)
            _validate_service_runtime_binding_contract(execution_surface)
            _validate_seed_files(workspace, execution_surface)
            _validate_seed_strategy_contract(execution_surface)
            _validate_volume_contract(execution_surface)
            _validate_network_contract(execution_surface)
            _validate_sidecar_dependency_contract(execution_surface, runtime_graph)
            _validate_seed_init_contract(workspace, execution_surface)
            _validate_env_contract_shape(execution_surface)
            _validate_service_env_contract(execution_surface)
            _validate_sidecar_env_contract(execution_surface)
            _validate_sidecar_probe_contract(execution_surface)
            if needs_sidecars:
                sidecars = _start_sidecars(
                    sid,
                    bundle,
                    execution_surface,
                    workspace,
                    run_dir,
                    network_handle,
                )
            else:
                sidecars = []
            summary["sidecars"] = sidecars
            summary.update(_seed_apply_observation(execution_surface, sidecars))
            run_result = run_container_with_poc(
                sid,
                bundle,
                image_tag,
                workspace,
                metadata_dir,
                run_dir,
                network_handle,
                service_port=summary["service_port"],
                base_url=summary["service_base_url"],
                service_env=deepcopy(execution_surface.get("service_env") or {}),
                poc_entry=str(execution_surface.get("poc_entry") or "poc.py"),
                poc_entry_source=execution_surface.get("poc_entry_source"),
                poc_cmd=str(execution_surface.get("poc_cmd") or "").strip() or None,
                health_path=execution_surface.get("health_path"),
                healthchecks=deepcopy(execution_surface.get("healthchecks") or []),
                executor_policy=executor_policy,
                payloads=poc_payloads,
            )
            summary["run_passed"] = True
            summary["executed"] = True
            summary["exit_code"] = run_result.get("exit_code")
            oracle_execution = run_result.get("oracle_execution") if isinstance(run_result.get("oracle_execution"), dict) else {}
            summary["oracle_execution"] = oracle_execution
            summary["oracle_execution_parity"] = str(oracle_execution.get("parity") or "").strip() or None
            oracle_path = run_dir / ORACLE_EXECUTION_FILENAME
            if oracle_path.exists():
                summary["oracle_execution_path"] = str(oracle_path)
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


def _load_contract_sections(metadata_dir: Path) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    contract = _load_generator_contract(metadata_dir)
    if not isinstance(contract, dict):
        return {}, {}, {}, {}
    executor_plan = contract.get("executor_plan") if isinstance(contract.get("executor_plan"), dict) else {}
    runtime_recipe = contract.get("runtime_recipe") if isinstance(contract.get("runtime_recipe"), dict) else {}
    runtime_graph = contract.get("runtime_graph") if isinstance(contract.get("runtime_graph"), dict) else {}
    return contract, executor_plan, runtime_recipe, runtime_graph


def _normalize_string_dict(raw: Any) -> Dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {
        str(key).strip(): str(value)
        for key, value in raw.items()
        if isinstance(key, str) and str(key).strip() and value not in (None, "")
    }


def _normalize_sidecars(raw_sidecars: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_sidecars, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for item in raw_sidecars:
        if not isinstance(item, dict):
            continue
        entry: Dict[str, Any] = {}
        for key in ("name", "type", "image", "network_mode"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                entry[key] = value.strip()
        aliases = item.get("aliases")
        if isinstance(aliases, list):
            normalized_aliases = [
                str(alias).strip()
                for alias in aliases
                if isinstance(alias, str) and str(alias).strip()
            ]
            if normalized_aliases:
                entry["aliases"] = normalized_aliases
        env = _normalize_string_dict(item.get("env"))
        if env:
            entry["env"] = env
        ready_probe = item.get("ready_probe")
        if isinstance(ready_probe, dict) and ready_probe:
            entry["ready_probe"] = deepcopy(ready_probe)
        if entry:
            normalized.append(entry)
    return normalized


def _normalize_healthchecks(raw_healthchecks: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_healthchecks, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for item in raw_healthchecks:
        if not isinstance(item, dict):
            continue
        entry: Dict[str, Any] = {}
        for key in ("node", "path", "transport"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                entry[key] = value.strip()
        port = item.get("port")
        if isinstance(port, int) and port > 0:
            entry["port"] = port
        if entry:
            normalized.append(entry)
    return normalized


def _normalize_env_contract(raw_env_contract: Any) -> List[Dict[str, str]]:
    if not isinstance(raw_env_contract, list):
        return []
    normalized: List[Dict[str, str]] = []
    for item in raw_env_contract:
        if not isinstance(item, dict):
            continue
        scope = str(item.get("scope") or "").strip().lower()
        name = str(item.get("name") or "").strip()
        if not scope or not name:
            continue
        entry: Dict[str, str] = {"scope": scope, "name": name}
        value = item.get("value")
        if isinstance(value, str) and value.strip():
            entry["value"] = value.strip()
        normalized.append(entry)
    return normalized


def _normalize_volume_contract(raw_volume_contract: Any) -> List[Dict[str, str]]:
    if not isinstance(raw_volume_contract, list):
        return []
    normalized: List[Dict[str, str]] = []
    for item in raw_volume_contract:
        if not isinstance(item, dict):
            continue
        scope = str(item.get("scope") or "").strip().lower()
        target = str(item.get("target") or "").strip()
        if not scope or not target:
            continue
        entry: Dict[str, str] = {"scope": scope, "target": target}
        source = str(item.get("source") or "").strip().lower()
        if source:
            entry["source"] = source
        mode = str(item.get("mode") or "").strip().lower()
        if mode:
            entry["mode"] = mode
        normalized.append(entry)
    return normalized


def _normalize_network_contract(raw_network_contract: Any) -> List[Dict[str, str]]:
    if not isinstance(raw_network_contract, list):
        return []
    normalized: List[Dict[str, str]] = []
    for item in raw_network_contract:
        if not isinstance(item, dict):
            continue
        scope = str(item.get("scope") or "").strip().lower()
        alias = str(item.get("alias") or "").strip()
        if not scope or not alias:
            continue
        entry: Dict[str, str] = {"scope": scope, "alias": alias}
        name = str(item.get("name") or "").strip()
        if name:
            entry["name"] = name
        normalized.append(entry)
    return normalized


def _normalize_seed_files(raw_seed_files: Any) -> List[str]:
    if not isinstance(raw_seed_files, list):
        return []
    normalized: List[str] = []
    for item in raw_seed_files:
        if not isinstance(item, str):
            continue
        token = item.strip().lstrip("./")
        if not token or token in normalized:
            continue
        normalized.append(token)
    return normalized


def _synthesized_sidecars_from_target_hints(
    *,
    target_db_hint: str | None,
    target_sidecars_hint: List[str],
    service_env: Dict[str, str],
) -> tuple[List[Dict[str, Any]], str | None]:
    hints = [
        str(item).strip().lower()
        for item in target_sidecars_hint
        if isinstance(item, str) and str(item).strip()
    ]
    target_db = str(target_db_hint or "").strip().lower()
    if target_db and target_db not in hints:
        hints.append(target_db)
    if not hints:
        return [], None
    db_host = str(service_env.get("DB_HOST") or "").strip() or "db-internal"
    db_name = str(service_env.get("DB_NAME") or "").strip() or "sqliapp"
    db_user = str(service_env.get("DB_USER") or "").strip() or "sqli"
    db_password = str(service_env.get("DB_PASSWORD") or "").strip() or "sqli_pw"

    for hint in hints:
        if hint in {"mysql", "mariadb"}:
            image = "mysql:8.0" if hint == "mysql" else "mariadb:11"
            sidecar = {
                "name": f"{hint}-main",
                "type": hint,
                "image": image,
                "aliases": [db_host],
                "env": {
                    "MYSQL_ROOT_PASSWORD": "sqli_root_pw",
                    "MYSQL_DATABASE": db_name,
                    "MYSQL_USER": db_user,
                    "MYSQL_PASSWORD": db_password,
                },
                "ready_probe": {"type": "mysql", "retries": 10},
            }
            return [sidecar], "generator_manifest.metadata.target_sidecars"
        if hint in {"postgres", "postgresql"}:
            sidecar = {
                "name": "postgres-main",
                "type": "postgres",
                "image": "postgres:16",
                "aliases": [db_host],
                "env": {
                    "POSTGRES_DB": db_name,
                    "POSTGRES_USER": db_user,
                    "POSTGRES_PASSWORD": db_password,
                },
                "ready_probe": {"type": "postgres", "retries": 10},
            }
            return [sidecar], "generator_manifest.metadata.target_sidecars"
    return [], None


def _synthesize_service_env_from_runtime_hints(
    *,
    service_env: Dict[str, str],
    service_port: int,
    sidecars: List[Dict[str, Any]],
    target_db_hint: str | None,
    target_sidecars_hint: List[str],
    source: str | None = None,
) -> tuple[Dict[str, str], str | None]:
    env = dict(service_env or {})
    sidecar_type = ""
    for entry in sidecars:
        if not isinstance(entry, dict):
            continue
        candidate = str(entry.get("type") or entry.get("name") or "").strip().lower()
        if candidate in {"mysql", "mariadb", "postgres", "postgresql"}:
            sidecar_type = candidate
            break
    if not sidecar_type:
        hints = [
            str(item).strip().lower()
            for item in target_sidecars_hint
            if isinstance(item, str) and str(item).strip()
        ]
        if isinstance(target_db_hint, str) and target_db_hint.strip():
            hints.append(target_db_hint.strip().lower())
        for candidate in hints:
            if candidate in {"mysql", "mariadb", "postgres", "postgresql"}:
                sidecar_type = candidate
                break
    if not sidecar_type:
        return env, None

    primary_sidecar = next((entry for entry in sidecars if isinstance(entry, dict)), {})
    aliases = primary_sidecar.get("aliases") if isinstance(primary_sidecar, dict) and isinstance(primary_sidecar.get("aliases"), list) else []
    host = env.get("DB_HOST") or (
        str(aliases[0]).strip() if aliases and isinstance(aliases[0], str) and str(aliases[0]).strip() else ""
    ) or str((primary_sidecar or {}).get("name") or "").strip() or "db-internal"
    if sidecar_type in {"mysql", "mariadb"}:
        defaults = {
            "APP_PORT": str(service_port),
            "DB_HOST": host,
            "DB_PORT": "3306",
            "DB_USER": env.get("DB_USER") or str(((primary_sidecar or {}).get("env") or {}).get("MYSQL_USER") or "").strip() or "sqli",
            "DB_PASSWORD": env.get("DB_PASSWORD") or str(((primary_sidecar or {}).get("env") or {}).get("MYSQL_PASSWORD") or "").strip() or "sqli_pw",
            "DB_NAME": env.get("DB_NAME") or str(((primary_sidecar or {}).get("env") or {}).get("MYSQL_DATABASE") or "").strip() or "sqliapp",
        }
    else:
        defaults = {
            "APP_PORT": str(service_port),
            "DB_HOST": host,
            "DB_PORT": "5432",
            "DB_USER": env.get("DB_USER") or str(((primary_sidecar or {}).get("env") or {}).get("POSTGRES_USER") or "").strip() or "sqli",
            "DB_PASSWORD": env.get("DB_PASSWORD") or str(((primary_sidecar or {}).get("env") or {}).get("POSTGRES_PASSWORD") or "").strip() or "sqli_pw",
            "DB_NAME": env.get("DB_NAME") or str(((primary_sidecar or {}).get("env") or {}).get("POSTGRES_DB") or "").strip() or "sqliapp",
        }
    changed = False
    for key, value in defaults.items():
        if not str(env.get(key) or "").strip() and str(value or "").strip():
            env[key] = str(value)
            changed = True
    if not changed:
        return env, None
    if isinstance(source, str) and source.strip():
        return env, f"{source}+runtime_hint_sidecar_defaults"
    return env, "runtime_hint_sidecar_defaults"


def _resolve_sidecars_from_sources(
    executor_plan: Dict[str, Any],
    runtime_graph: Dict[str, Any],
    runtime_recipe: Dict[str, Any],
    executor_policy: Dict[str, Any],
) -> tuple[List[Dict[str, Any]], str | None]:
    runtime_graph_sidecars, runtime_graph_sidecars_suffix = _sidecars_from_runtime_graph_nodes(runtime_graph)
    for source, source_field, raw in (
        ("executor_plan.sidecars", executor_plan.get("sidecars_source"), executor_plan.get("sidecars")),
        ("runtime_graph.nodes", runtime_graph.get("sidecars_source"), runtime_graph_sidecars),
        ("runtime_recipe.sidecars", runtime_recipe.get("sidecars_source"), runtime_recipe.get("sidecars")),
        (
            "policy.executor.sidecars",
            None,
            executor_policy.get("sidecars") if isinstance(executor_policy, dict) else None,
        ),
    ):
        sidecars = _normalize_sidecars(raw)
        if sidecars:
            resolved_source = str(source_field or "").strip() or source
            if source == "runtime_graph.nodes" and runtime_graph_sidecars_suffix:
                resolved_source = f"{resolved_source}+{runtime_graph_sidecars_suffix}"
            return sidecars, resolved_source
    return [], None


def _sidecars_from_runtime_graph_nodes(runtime_graph: Dict[str, Any]) -> tuple[List[Dict[str, Any]], str | None]:
    nodes = runtime_graph.get("nodes") if isinstance(runtime_graph.get("nodes"), list) else []
    if not nodes:
        return [], None
    graph_env_contract = runtime_graph.get("env_contract") if isinstance(runtime_graph.get("env_contract"), list) else []
    sidecar_env_by_scope: Dict[str, Dict[str, str]] = {}
    for contract_entry in graph_env_contract:
        if not isinstance(contract_entry, dict):
            continue
        scope = str(contract_entry.get("scope") or "").strip().lower()
        if not scope.startswith("sidecar:"):
            continue
        name = str(contract_entry.get("name") or "").strip()
        value = str(contract_entry.get("value") or "").strip()
        if not name or not value:
            continue
        bucket = sidecar_env_by_scope.setdefault(scope, {})
        bucket[name] = value
    sidecars: List[Tuple[int, Dict[str, Any]]] = []
    used_env_contract = False
    for index, node in enumerate(nodes, start=1):
        if not isinstance(node, dict):
            continue
        if str(node.get("kind") or "").strip().lower() != "sidecar":
            continue
        raw_id = str(node.get("id") or "").strip()
        raw_name = str(node.get("name") or "").strip()
        name = raw_name or (raw_id.split(":", 1)[1] if raw_id.startswith("sidecar:") else raw_id)
        name = str(name or "").strip()
        if not name:
            continue
        entry: Dict[str, Any] = {"name": name}
        sidecar_type = str(node.get("sidecar_type") or node.get("type") or "").strip()
        if sidecar_type:
            entry["type"] = sidecar_type
        image = str(node.get("image") or "").strip()
        if image:
            entry["image"] = image
        aliases = node.get("aliases") if isinstance(node.get("aliases"), list) else []
        normalized_aliases = [str(alias).strip() for alias in aliases if isinstance(alias, str) and str(alias).strip()]
        if normalized_aliases:
            entry["aliases"] = normalized_aliases
        ready_probe = node.get("ready_probe")
        if isinstance(ready_probe, dict) and ready_probe:
            entry["ready_probe"] = deepcopy(ready_probe)
        env = _normalize_string_dict(node.get("env"))
        contract_env = sidecar_env_by_scope.get(f"sidecar:{name.lower()}") or {}
        for key, value in contract_env.items():
            if key not in env:
                env[key] = value
                used_env_contract = True
        if env:
            entry["env"] = env
        startup_order_index = node.get("startup_order_index")
        sort_key = int(startup_order_index) if isinstance(startup_order_index, int) and startup_order_index > 0 else 10_000 + index
        sidecars.append((sort_key, entry))
    sidecars.sort(key=lambda item: item[0])
    return [entry for _, entry in sidecars], ("env_contract" if used_env_contract else None)


def _sidecar_start_order_from_runtime_graph(runtime_graph: Dict[str, Any]) -> tuple[List[str], str | None]:
    nodes = runtime_graph.get("nodes") if isinstance(runtime_graph.get("nodes"), list) else []
    ordered: List[Tuple[int, str]] = []
    sidecar_names: List[str] = []
    for index, node in enumerate(nodes, start=1):
        if not isinstance(node, dict):
            continue
        if str(node.get("kind") or "").strip().lower() != "sidecar":
            continue
        raw_id = str(node.get("id") or "").strip()
        raw_name = str(node.get("name") or "").strip()
        name = raw_name or (raw_id.split(":", 1)[1] if raw_id.startswith("sidecar:") else raw_id)
        name = str(name or "").strip()
        if not name:
            continue
        sidecar_names.append(name)
        startup_order_index = node.get("startup_order_index")
        sort_key = int(startup_order_index) if isinstance(startup_order_index, int) and startup_order_index > 0 else 10_000 + index
        ordered.append((sort_key, name))
    indexed = [item for item in ordered if item[0] < 10_000]
    if indexed:
        indexed.sort(key=lambda item: item[0])
        return [name for _, name in indexed], "runtime_graph.nodes.startup_order_index"
    edges = runtime_graph.get("edges") if isinstance(runtime_graph.get("edges"), list) else []
    dependency_by_name: Dict[str, str] = {}
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        target = str(edge.get("to") or "").strip()
        if not target.startswith("sidecar:"):
            continue
        sidecar_name = target.split(":", 1)[1].strip()
        if not sidecar_name:
            continue
        startup_after = str(edge.get("startup_after") or "").strip()
        if startup_after.startswith("sidecar:"):
            dependency_by_name[sidecar_name] = startup_after.split(":", 1)[1].strip()
    if dependency_by_name and sidecar_names:
        remaining = list(dict.fromkeys(sidecar_names))
        resolved: List[str] = []
        while remaining:
            progress = False
            for name in list(remaining):
                dependency = dependency_by_name.get(name, "")
                if not dependency or dependency in resolved or dependency not in sidecar_names:
                    resolved.append(name)
                    remaining.remove(name)
                    progress = True
            if not progress:
                resolved.extend(remaining)
                break
        return resolved, "runtime_graph.edges.startup_after"
    ordered.sort(key=lambda item: item[0])
    return [name for _, name in ordered], None


def _resolve_service_port_from_sources(
    metadata_dir: Path,
    workspace: Path | None,
    contract: Dict[str, Any],
    executor_plan: Dict[str, Any],
    runtime_recipe: Dict[str, Any],
    runtime_graph: Dict[str, Any],
) -> tuple[int, str | None]:
    def _service_port_from_healthchecks(raw_healthchecks: Any) -> int | None:
        healthchecks = _normalize_healthchecks(raw_healthchecks)
        for entry in healthchecks:
            if not isinstance(entry, dict):
                continue
            node = str(entry.get("node") or "").strip().lower()
            if node and node != "service":
                continue
            try:
                value = int(entry.get("port"))
            except Exception:
                value = None
            if value:
                return value
        return None

    for source, raw in (
        ("executor_plan.service_port", executor_plan.get("service_port")),
        ("runtime_recipe.service_port", runtime_recipe.get("service_port")),
        ("resolved_contract.service_port", contract.get("service_port")),
    ):
        try:
            value = int(raw)
        except Exception:
            value = None
        if value:
            return value, source
    for source, raw in (
        ("executor_plan.healthchecks[service].port", executor_plan.get("healthchecks")),
        ("runtime_graph.healthchecks[service].port", runtime_graph.get("healthchecks")),
        ("runtime_recipe.healthchecks[service].port", runtime_recipe.get("healthchecks")),
    ):
        value = _service_port_from_healthchecks(raw)
        if value:
            return value, source
    exploit_path = runtime_graph.get("exploit_path") if isinstance(runtime_graph.get("exploit_path"), dict) else {}
    for source, raw in (
        ("runtime_graph.exploit_path.port", exploit_path.get("port") if isinstance(exploit_path, dict) else None),
        (
            "runtime_graph.service_node.port",
            next(
                (
                    node.get("port")
                    for node in (runtime_graph.get("nodes") if isinstance(runtime_graph.get("nodes"), list) else [])
                    if isinstance(node, dict) and str(node.get("kind") or "").strip().lower() == "service"
                ),
                None,
            ),
        ),
    ):
        try:
            value = int(raw)
        except Exception:
            value = None
        if value:
            return value, source
    port = _port_from_generator_template(metadata_dir)
    if port:
        return port, "generator_template.port"
    port = _port_from_generator_manifest(metadata_dir)
    if port:
        return port, "generator_manifest.run.port"
    if workspace is not None:
        port = _port_from_dockerfile(workspace)
        if port:
            return port, "workspace.dockerfile.expose"
    return DEFAULT_APP_PORT, "default.app_port"


def _resolve_base_url_from_sources(
    executor_policy: Dict[str, Any],
    contract: Dict[str, Any],
    executor_plan: Dict[str, Any],
    runtime_graph: Dict[str, Any],
    service_port: int,
) -> tuple[str, str | None]:
    override = (executor_policy or {}).get("base_url")
    if isinstance(override, str) and override.strip():
        return override.strip(), "policy.executor.base_url"
    value = executor_plan.get("base_url")
    if isinstance(value, str) and value.strip():
        return value.strip(), "executor_plan.base_url"
    value = contract.get("base_url")
    if isinstance(value, str) and value.strip():
        return value.strip(), "resolved_contract.base_url"
    exploit_path = runtime_graph.get("exploit_path") if isinstance(runtime_graph.get("exploit_path"), dict) else {}
    value = exploit_path.get("base_url") if isinstance(exploit_path, dict) else None
    if isinstance(value, str) and value.strip():
        return value.strip(), "runtime_graph.exploit_path.base_url"
    return f"http://127.0.0.1:{service_port}", "default.localhost_service_port"


def _resolve_service_env_from_sources(
    metadata_dir: Path,
    contract: Dict[str, Any],
    executor_plan: Dict[str, Any],
    runtime_recipe: Dict[str, Any],
    runtime_graph: Dict[str, Any],
) -> tuple[Dict[str, str], str | None]:
    for source, source_field, raw in (
        ("executor_plan.service_env", executor_plan.get("service_env_source"), executor_plan.get("service_env")),
        ("runtime_recipe.service_env", runtime_recipe.get("service_env_source"), runtime_recipe.get("service_env")),
        ("resolved_contract.service_env", None, contract.get("service_env")),
    ):
        env = _normalize_string_dict(raw)
        if env:
            resolved_source = str(source_field or "").strip() or source
            return env, resolved_source
    graph_env_contract = runtime_graph.get("env_contract") if isinstance(runtime_graph.get("env_contract"), list) else []
    graph_env: Dict[str, str] = {}
    for entry in graph_env_contract:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("scope") or "").strip().lower() != "service":
            continue
        key = str(entry.get("name") or "").strip()
        value = str(entry.get("value") or "").strip()
        if key and value:
            graph_env[key] = value
    if graph_env:
        return graph_env, "runtime_graph.env_contract"
    manifest = _load_json(metadata_dir / "generator_manifest.json")
    if isinstance(manifest, dict):
        inner = manifest.get("manifest")
        if isinstance(inner, dict):
            run_section = inner.get("run")
            if isinstance(run_section, dict):
                env = _normalize_string_dict(run_section.get("env"))
                if env:
                    return env, "generator_manifest.manifest.run.env"
    template = _load_json(metadata_dir / "generator_template.json")
    env = _normalize_string_dict(template.get("service_env") if isinstance(template, dict) else None)
    return env, ("generator_template.service_env" if env else None)


def _resolve_generator_manifest_target_runtime_hints(
    metadata_dir: Path,
) -> tuple[str | None, List[str], str | None, str | None]:
    payload = _load_json(metadata_dir / "generator_manifest.json")
    if not isinstance(payload, dict):
        return None, [], None, None
    manifest = payload.get("manifest") if isinstance(payload.get("manifest"), dict) else payload
    if not isinstance(manifest, dict):
        return None, [], None, None
    metadata = manifest.get("metadata") if isinstance(manifest.get("metadata"), dict) else {}
    if not isinstance(metadata, dict):
        return None, [], None, None
    target_db = str(metadata.get("target_db") or "").strip().lower() or None
    target_sidecars = [
        str(item).strip().lower()
        for item in (metadata.get("target_sidecars") or [])
        if isinstance(item, str) and str(item).strip()
    ]
    target_topology = str(metadata.get("target_topology") or "").strip().lower() or None
    if not target_db and not target_sidecars and not target_topology:
        return None, [], None, None
    return target_db, target_sidecars, "generator_manifest.metadata", target_topology


def _resolve_health_path_from_sources(
    executor_plan: Dict[str, Any],
    runtime_graph: Dict[str, Any],
    runtime_recipe: Dict[str, Any],
) -> tuple[str | None, str | None]:
    for source, raw in (
        ("executor_plan.health_path", executor_plan.get("health_path")),
        ("runtime_recipe.health_path", runtime_recipe.get("health_path")),
    ):
        if isinstance(raw, str) and raw.strip():
            return raw.strip(), source
    for source, raw in (
        ("executor_plan.healthchecks[service]", executor_plan.get("healthchecks")),
        ("runtime_graph.healthchecks[service]", runtime_graph.get("healthchecks")),
        ("runtime_recipe.healthchecks[service]", runtime_recipe.get("healthchecks")),
    ):
        healthchecks = _normalize_healthchecks(raw)
        for entry in healthchecks:
            if str(entry.get("node") or "").strip().lower() != "service":
                continue
            path = str(entry.get("path") or "").strip()
            if path:
                return path, source
    return None, None


def _resolve_service_entry_from_sources(
    contract: Dict[str, Any],
    executor_plan: Dict[str, Any],
    runtime_recipe: Dict[str, Any],
    runtime_graph: Dict[str, Any],
) -> tuple[str, str | None]:
    for source, raw in (
        ("executor_plan.service_entry", executor_plan.get("service_entry")),
        ("runtime_recipe.service_entry", runtime_recipe.get("service_entry")),
        ("resolved_contract.service_entry", contract.get("service_entry")),
    ):
        if isinstance(raw, str) and raw.strip():
            return raw.strip(), source
    exploit_path = runtime_graph.get("exploit_path") if isinstance(runtime_graph.get("exploit_path"), dict) else {}
    for source, raw in (
        (
            "runtime_graph.exploit_path.service_entry",
            exploit_path.get("service_entry") if isinstance(exploit_path, dict) else None,
        ),
        (
            "runtime_graph.service_node.entry",
            next(
                (
                    node.get("entry")
                    for node in (runtime_graph.get("nodes") if isinstance(runtime_graph.get("nodes"), list) else [])
                    if isinstance(node, dict) and str(node.get("kind") or "").strip().lower() == "service"
                ),
                None,
            ),
        ),
    ):
        if isinstance(raw, str) and raw.strip():
            return raw.strip(), source
    return "app.py", "default.app.py"


def _resolve_poc_entry_from_metadata(metadata_dir: Path) -> tuple[str, str | None]:
    contract = _load_generator_contract(metadata_dir)
    if isinstance(contract, dict):
        poc_entry = contract.get("poc_entry")
        if isinstance(poc_entry, str) and poc_entry.strip():
            return poc_entry.strip(), "resolved_contract.poc_entry"
    manifest = _load_json(metadata_dir / "generator_manifest.json")
    if isinstance(manifest, dict):
        inner = manifest.get("manifest")
        if isinstance(inner, dict):
            files = inner.get("files") or []
            if isinstance(files, list):
                for entry in files:
                    if not isinstance(entry, dict):
                        continue
                    role = str(entry.get("role") or "").strip().lower()
                    path = entry.get("path")
                    if role == "poc_entry" and isinstance(path, str) and path.strip():
                        return path.strip(), "generator_manifest.manifest.files(role=poc_entry)"
    template = _load_json(metadata_dir / "generator_template.json")
    if isinstance(template, dict):
        poc_entry = template.get("poc_entry")
        if isinstance(poc_entry, str) and poc_entry.strip():
            return poc_entry.strip(), "generator_template.poc_entry"
    return "poc.py", "default.poc.py"


def _resolve_poc_entry_from_sources(
    metadata_dir: Path,
    contract: Dict[str, Any],
    executor_plan: Dict[str, Any],
    runtime_recipe: Dict[str, Any],
    runtime_graph: Dict[str, Any],
) -> tuple[str, str | None]:
    for source, raw in (
        ("executor_plan.poc_entry", executor_plan.get("poc_entry")),
        ("runtime_recipe.poc_entry", runtime_recipe.get("poc_entry")),
        ("resolved_contract.poc_entry", contract.get("poc_entry")),
    ):
        if isinstance(raw, str) and raw.strip():
            return raw.strip(), source
    exploit_path = runtime_graph.get("exploit_path") if isinstance(runtime_graph.get("exploit_path"), dict) else {}
    entrypoint = exploit_path.get("entrypoint") if isinstance(exploit_path, dict) else None
    if isinstance(entrypoint, str) and entrypoint.strip():
        return entrypoint.strip(), "runtime_graph.exploit_path.entrypoint"
    return _resolve_poc_entry_from_metadata(metadata_dir)


def _resolve_poc_cmd_from_metadata(metadata_dir: Path) -> tuple[str | None, str | None]:
    contract = _load_generator_contract(metadata_dir)
    if isinstance(contract, dict):
        cmd = contract.get("poc_cmd")
        if isinstance(cmd, str) and cmd.strip():
            return cmd.strip(), "resolved_contract.poc_cmd"
    payload = _load_json(metadata_dir / "generator_manifest.json")
    if isinstance(payload, dict):
        manifest = payload.get("manifest")
        if isinstance(manifest, dict):
            poc = manifest.get("poc")
            if isinstance(poc, dict):
                cmd = poc.get("cmd")
                if isinstance(cmd, str) and cmd.strip():
                    return cmd.strip(), "generator_manifest.manifest.poc.cmd"
    return None, None


def _resolve_poc_cmd_from_sources(
    metadata_dir: Path,
    contract: Dict[str, Any],
) -> tuple[str | None, str | None]:
    cmd = contract.get("poc_cmd")
    if isinstance(cmd, str) and cmd.strip():
        return cmd.strip(), "resolved_contract.poc_cmd"
    return _resolve_poc_cmd_from_metadata(metadata_dir)


def _resolve_healthchecks_from_sources(
    executor_plan: Dict[str, Any],
    runtime_graph: Dict[str, Any],
    runtime_recipe: Dict[str, Any],
) -> tuple[List[Dict[str, Any]], str | None]:
    for source, raw in (
        ("executor_plan.healthchecks", executor_plan.get("healthchecks")),
        ("runtime_graph.healthchecks", runtime_graph.get("healthchecks")),
        ("runtime_recipe.healthchecks", runtime_recipe.get("healthchecks")),
    ):
        healthchecks = _normalize_healthchecks(raw)
        if healthchecks:
            return healthchecks, source
    return [], None


def _resolve_env_contract_from_sources(
    executor_plan: Dict[str, Any],
    runtime_graph: Dict[str, Any],
) -> tuple[List[Dict[str, str]], str | None]:
    for source, raw in (
        ("executor_plan.env_contract", executor_plan.get("env_contract")),
        ("runtime_graph.env_contract", runtime_graph.get("env_contract")),
    ):
        env_contract = _normalize_env_contract(raw)
        if env_contract:
            return env_contract, source
    return [], None


def _resolve_volume_contract_from_sources(
    executor_plan: Dict[str, Any],
    runtime_graph: Dict[str, Any],
    runtime_recipe: Dict[str, Any],
) -> tuple[List[Dict[str, str]], str | None]:
    for source, raw in (
        ("executor_plan.volume_contract", executor_plan.get("volume_contract")),
        ("runtime_graph.volume_contract", runtime_graph.get("volume_contract")),
        ("runtime_recipe.volume_contract", runtime_recipe.get("volume_contract")),
    ):
        volume_contract = _normalize_volume_contract(raw)
        if volume_contract:
            source_field = str(
                executor_plan.get("volume_contract_source")
                if source.startswith("executor_plan")
                else runtime_graph.get("volume_contract_source")
                if source.startswith("runtime_graph")
                else runtime_recipe.get("volume_contract_source")
                or ""
            ).strip()
            return volume_contract, (source_field or source)
    return [], None


def _resolve_network_contract_from_sources(
    executor_plan: Dict[str, Any],
    runtime_graph: Dict[str, Any],
    runtime_recipe: Dict[str, Any],
) -> tuple[List[Dict[str, str]], str | None]:
    for source, raw in (
        ("executor_plan.network_contract", executor_plan.get("network_contract")),
        ("runtime_graph.network_contract", runtime_graph.get("network_contract")),
        ("runtime_recipe.network_contract", runtime_recipe.get("network_contract")),
    ):
        network_contract = _normalize_network_contract(raw)
        if network_contract:
            source_field = str(
                executor_plan.get("network_contract_source")
                if source.startswith("executor_plan")
                else runtime_graph.get("network_contract_source")
                if source.startswith("runtime_graph")
                else runtime_recipe.get("network_contract_source")
                or ""
            ).strip()
            return network_contract, (source_field or source)
    return [], None


def _apply_network_contract_to_sidecars(
    sidecars: List[Dict[str, Any]],
    network_contract: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    if not sidecars or not network_contract:
        return sidecars
    updated = deepcopy(sidecars)
    alias_by_scope: Dict[str, List[str]] = {}
    for entry in network_contract:
        if not isinstance(entry, dict):
            continue
        scope = str(entry.get("scope") or "").strip().lower()
        alias = str(entry.get("alias") or "").strip()
        if not scope.startswith("sidecar:") or not alias:
            continue
        bucket = alias_by_scope.setdefault(scope, [])
        if alias not in bucket:
            bucket.append(alias)
    if not alias_by_scope:
        return updated
    for entry in updated:
        if not isinstance(entry, dict):
            continue
        sidecar_name = str(entry.get("name") or "").strip().lower()
        if not sidecar_name:
            continue
        scope = f"sidecar:{sidecar_name}"
        aliases = alias_by_scope.get(scope)
        if not aliases:
            continue
        existing_aliases = (
            [
                str(alias).strip()
                for alias in entry.get("aliases")
                if isinstance(alias, str) and str(alias).strip()
            ]
            if isinstance(entry.get("aliases"), list)
            else []
        )
        for alias in aliases:
            if alias not in existing_aliases:
                existing_aliases.append(alias)
        if existing_aliases:
            entry["aliases"] = existing_aliases
    return updated


def _apply_network_contract_to_service_env(
    service_env: Dict[str, str],
    network_contract: List[Dict[str, str]],
    *,
    source: str | None,
) -> tuple[Dict[str, str], str | None]:
    env = dict(service_env or {})
    changed = False
    for entry in network_contract:
        if not isinstance(entry, dict):
            continue
        scope = str(entry.get("scope") or "").strip().lower()
        if scope != "service":
            continue
        name = str(entry.get("name") or "").strip()
        alias = str(entry.get("alias") or "").strip()
        if not name or not alias:
            continue
        if not str(env.get(name) or "").strip():
            env[name] = alias
            changed = True
    if not changed:
        return env, source
    if isinstance(source, str) and source.strip():
        return env, f"{source}+network_contract_aliases"
    return env, "network_contract.service_aliases"


def _resolve_seed_files_from_sources(
    executor_plan: Dict[str, Any],
    runtime_graph: Dict[str, Any],
    runtime_recipe: Dict[str, Any],
) -> tuple[List[str], str | None]:
    for source, raw in (
        ("executor_plan.seed_files", executor_plan.get("seed_files")),
        ("runtime_graph.seed_files", runtime_graph.get("seed_files")),
        ("runtime_recipe.seed_files", runtime_recipe.get("seed_files")),
    ):
        seed_files = _normalize_seed_files(raw)
        if seed_files:
            return seed_files, source
    return [], None


def _resolve_seed_strategy_from_sources(
    executor_plan: Dict[str, Any],
    runtime_graph: Dict[str, Any],
    runtime_recipe: Dict[str, Any],
) -> tuple[str | None, str | None]:
    for source, raw in (
        ("executor_plan.seed_strategy", executor_plan.get("seed_strategy")),
        ("runtime_graph.seed_strategy", runtime_graph.get("seed_strategy")),
        ("runtime_recipe.seed_strategy", runtime_recipe.get("seed_strategy")),
    ):
        strategy = str(raw or "").strip().lower()
        if strategy:
            source_field = str(
                executor_plan.get("seed_strategy_source")
                if source.startswith("executor_plan")
                else runtime_graph.get("seed_strategy_source")
                if source.startswith("runtime_graph")
                else runtime_recipe.get("seed_strategy_source")
                or ""
            ).strip()
            return strategy, (source_field or source)
    return None, None


def _resolve_requires_external_db_from_sources(
    *,
    plan: Dict[str, Any] | None,
    bundle: VulnBundle | None,
    metadata_dir: Path,
    executor_plan: Dict[str, Any],
    runtime_recipe: Dict[str, Any],
    runtime_graph: Dict[str, Any],
    target_topology_hint: str | None,
    sidecars: List[Dict[str, Any]],
) -> bool:
    def _db_value_requires_external_db(value: Any) -> bool:
        token = str(value or "").strip().lower()
        return token in {"mysql", "postgres", "postgresql", "mariadb"}

    def _dependency_hints_require_external_db(payload: Dict[str, Any]) -> bool:
        hypotheses = payload.get("runtime_dependency_hypotheses") if isinstance(payload.get("runtime_dependency_hypotheses"), list) else []
        for entry in hypotheses:
            if not isinstance(entry, dict):
                continue
            kind = str(entry.get("kind") or "").strip().lower()
            value = str(entry.get("value") or "").strip().lower()
            if kind == "db" and _db_value_requires_external_db(value):
                return True
        return False

    if executor_plan.get("requires_external_db") is True:
        return True
    if _db_value_requires_external_db(executor_plan.get("db")):
        return True
    if _dependency_hints_require_external_db(executor_plan):
        return True
    topology = str(executor_plan.get("topology") or "").strip().lower()
    if topology == "service_plus_sidecar" or _normalize_sidecars(executor_plan.get("sidecars")):
        return True
    if runtime_recipe.get("requires_external_db") is True:
        return True
    if _db_value_requires_external_db(runtime_recipe.get("db")):
        return True
    if _dependency_hints_require_external_db(runtime_recipe):
        return True
    topology = str(runtime_recipe.get("topology") or "").strip().lower()
    if topology == "service_plus_sidecar" or _normalize_sidecars(runtime_recipe.get("sidecars")):
        return True
    if _db_value_requires_external_db(runtime_graph.get("db")):
        return True
    topology = str(runtime_graph.get("topology") or "").strip().lower()
    if topology == "service_plus_sidecar":
        return True
    if str(target_topology_hint or "").strip().lower() == "service_plus_sidecar":
        return True
    nodes = runtime_graph.get("nodes")
    if isinstance(nodes, list) and any(
        isinstance(node, dict) and str(node.get("kind") or "").strip().lower() == "sidecar"
        for node in nodes
    ):
        return True
    if sidecars:
        return True
    target_db, target_sidecars, _, _ = _resolve_generator_manifest_target_runtime_hints(metadata_dir)
    if _db_value_requires_external_db(target_db):
        return True
    if target_sidecars:
        return True
    for path in (metadata_dir / "generator_manifest.json", metadata_dir / "generator_template.json"):
        data = _load_json(path)
        if isinstance(data, dict) and data.get("requires_external_db") is True:
            return True
    if plan is not None and bundle is not None:
        requirement = bundle_requirement(plan["requirement"], bundle)
        runtime = requirement.get("runtime") or {}
        db = str(runtime.get("db") or runtime.get("database") or "").strip().lower()
        return db in {"mysql", "postgres", "postgresql", "mariadb"}
    return False


def _resolve_allow_network_from_sources(
    executor_policy: Dict[str, Any],
    executor_plan: Dict[str, Any],
    runtime_graph: Dict[str, Any],
    runtime_recipe: Dict[str, Any],
    target_topology_hint: str | None,
    sidecars: List[Dict[str, Any]],
    requires_external_db: bool,
) -> tuple[bool, str | None]:
    if isinstance(executor_policy, dict) and executor_policy.get("allow_network") is False:
        return False, "policy.executor.allow_network"
    for label, source_field, raw in (
        ("executor_plan.network_enabled", executor_plan.get("network_enabled_source"), executor_plan.get("network_enabled")),
        ("runtime_graph.network_enabled", runtime_graph.get("network_enabled_source"), runtime_graph.get("network_enabled")),
        ("runtime_recipe.network_enabled", runtime_recipe.get("network_enabled_source"), runtime_recipe.get("network_enabled")),
    ):
        if isinstance(raw, bool):
            return raw, (str(source_field or "").strip() or label)
    graph_network = runtime_graph.get("network") if isinstance(runtime_graph.get("network"), dict) else {}
    if isinstance(graph_network.get("enabled"), bool):
        source = str(runtime_graph.get("network_enabled_source") or "runtime_graph.network.enabled").strip()
        return bool(graph_network.get("enabled")), source or "runtime_graph.network.enabled"
    explicit_network_mode = str((executor_policy or {}).get("network_mode") or "").strip().lower()
    if explicit_network_mode:
        return explicit_network_mode != "none", "policy.executor.network_mode"
    topology = str(executor_plan.get("topology") or runtime_recipe.get("topology") or target_topology_hint or "").strip().lower()
    if topology == "service_plus_sidecar":
        topology_source = str(
            executor_plan.get("topology_source")
            or runtime_recipe.get("topology_source")
            or ""
        ).strip()
        return True, (topology_source or "topology_requires_network")
    return bool(sidecars or requires_external_db), ("sidecar_or_db_requires_network" if sidecars or requires_external_db else None)


def _resolve_network_mode_from_sources(
    executor_policy: Dict[str, Any],
    executor_plan: Dict[str, Any],
    runtime_graph: Dict[str, Any],
    runtime_recipe: Dict[str, Any],
    target_topology_hint: str | None,
    *,
    allow_network: bool,
) -> tuple[str, str | None]:
    if not allow_network:
        return "none", "allow_network=false"
    explicit_network_mode = str((executor_policy or {}).get("network_mode") or "").strip()
    if explicit_network_mode:
        return explicit_network_mode, "policy.executor.network_mode"
    for label, source_field, raw in (
        ("executor_plan.network_mode", executor_plan.get("network_mode_source"), executor_plan.get("network_mode")),
        ("runtime_graph.network_mode", runtime_graph.get("network_mode_source"), runtime_graph.get("network_mode")),
        ("runtime_recipe.network_mode", runtime_recipe.get("network_mode_source"), runtime_recipe.get("network_mode")),
    ):
        network_mode = str(raw or "").strip()
        if network_mode:
            return network_mode, (str(source_field or "").strip() or label)
    graph_network = runtime_graph.get("network") if isinstance(runtime_graph.get("network"), dict) else {}
    graph_mode = str(graph_network.get("mode") or "").strip()
    if graph_mode:
        source = str(runtime_graph.get("network_mode_source") or "runtime_graph.network.mode").strip()
        return graph_mode, source or "runtime_graph.network.mode"
    if str(target_topology_hint or "").strip().lower() == "service_plus_sidecar":
        return "bridge", "generator_manifest.metadata.target_topology"
    return "bridge", "default(bridge)"


def _resolve_execution_surface(
    metadata_dir: Path,
    workspace: Path | None,
    executor_policy: Dict[str, Any] | None,
    *,
    plan: Dict[str, Any] | None = None,
    bundle: VulnBundle | None = None,
) -> Dict[str, Any]:
    policy = dict(executor_policy or {})
    contract, executor_plan, runtime_recipe, runtime_graph = _load_contract_sections(metadata_dir)
    target_db_hint, target_sidecars_hint, target_runtime_hint_source, target_topology_hint = _resolve_generator_manifest_target_runtime_hints(
        metadata_dir
    )
    service_env, base_service_env_source = _resolve_service_env_from_sources(
        metadata_dir,
        contract,
        executor_plan,
        runtime_recipe,
        runtime_graph,
    )
    service_port, service_port_source = _resolve_service_port_from_sources(
        metadata_dir,
        workspace,
        contract,
        executor_plan,
        runtime_recipe,
        runtime_graph,
    )
    sidecars, sidecars_source = _resolve_sidecars_from_sources(executor_plan, runtime_graph, runtime_recipe, policy)
    if not sidecars:
        synthesized_sidecars, synthesized_source = _synthesized_sidecars_from_target_hints(
            target_db_hint=target_db_hint,
            target_sidecars_hint=target_sidecars_hint,
            service_env=service_env,
        )
        if synthesized_sidecars:
            sidecars = synthesized_sidecars
            sidecars_source = synthesized_source
    network_contract, network_contract_source = _resolve_network_contract_from_sources(executor_plan, runtime_graph, runtime_recipe)
    sidecars = _apply_network_contract_to_sidecars(sidecars, network_contract)
    service_env, enriched_service_env_source = _apply_network_contract_to_service_env(
        service_env,
        network_contract,
        source=base_service_env_source,
    )
    service_env, service_env_source = _synthesize_service_env_from_runtime_hints(
        service_env=service_env,
        service_port=service_port,
        sidecars=sidecars,
        target_db_hint=target_db_hint,
        target_sidecars_hint=target_sidecars_hint,
        source=enriched_service_env_source or base_service_env_source,
    )
    if not service_env_source:
        service_env_source = enriched_service_env_source or base_service_env_source
    seed_files, seed_files_source = _resolve_seed_files_from_sources(executor_plan, runtime_graph, runtime_recipe)
    seed_strategy, seed_strategy_source = _resolve_seed_strategy_from_sources(executor_plan, runtime_graph, runtime_recipe)
    volume_contract, volume_contract_source = _resolve_volume_contract_from_sources(executor_plan, runtime_graph, runtime_recipe)
    env_contract, env_contract_source = _resolve_env_contract_from_sources(executor_plan, runtime_graph)
    sidecar_start_order = (
        deepcopy(executor_plan.get("sidecar_start_order"))
        if isinstance(executor_plan.get("sidecar_start_order"), list)
        else deepcopy(runtime_graph.get("sidecar_start_order"))
        if isinstance(runtime_graph.get("sidecar_start_order"), list)
        else deepcopy(runtime_recipe.get("sidecar_start_order"))
        if isinstance(runtime_recipe.get("sidecar_start_order"), list)
        else []
    )
    derived_sidecar_start_order_source = None
    if not sidecar_start_order:
        sidecar_start_order, derived_sidecar_start_order_source = _sidecar_start_order_from_runtime_graph(runtime_graph)
    sidecar_start_order_source = str(
        executor_plan.get("sidecar_start_order_source")
        or runtime_graph.get("sidecar_start_order_source")
        or runtime_recipe.get("sidecar_start_order_source")
        or ""
    ).strip() or None
    if sidecar_start_order and not sidecar_start_order_source:
        sidecar_start_order_source = derived_sidecar_start_order_source
    requires_external_db = _resolve_requires_external_db_from_sources(
        plan=plan,
        bundle=bundle,
        metadata_dir=metadata_dir,
        executor_plan=executor_plan,
        runtime_recipe=runtime_recipe,
        runtime_graph=runtime_graph,
        target_topology_hint=target_topology_hint,
        sidecars=sidecars,
    )
    allow_network, allow_network_source = _resolve_allow_network_from_sources(
        policy,
        executor_plan,
        runtime_graph,
        runtime_recipe,
        target_topology_hint,
        sidecars,
        requires_external_db,
    )
    network_mode, network_mode_source = _resolve_network_mode_from_sources(
        policy,
        executor_plan,
        runtime_graph,
        runtime_recipe,
        target_topology_hint,
        allow_network=allow_network,
    )
    surface: Dict[str, Any] = {
        "service_port": service_port,
        "service_port_source": service_port_source,
        "service_entry": None,
        "service_entry_source": None,
        "poc_entry": None,
        "poc_entry_source": None,
        "poc_cmd": None,
        "poc_cmd_source": None,
        "base_url": None,
        "base_url_source": None,
        "service_env": service_env,
        "service_env_source": service_env_source,
        "env_contract": env_contract,
        "env_contract_source": env_contract_source,
        "db": str(
            executor_plan.get("db")
            or runtime_recipe.get("db")
            or runtime_graph.get("db")
            or target_db_hint
            or ""
        ).strip().lower() or None,
        "db_source": str(
            executor_plan.get("db_source")
            or runtime_recipe.get("db_source")
            or runtime_graph.get("db_source")
            or (f"{target_runtime_hint_source}.target_db" if target_db_hint and target_runtime_hint_source else "")
            or ""
        ).strip() or None,
        "topology": str(
            executor_plan.get("topology")
            or runtime_recipe.get("topology")
            or runtime_graph.get("topology")
            or target_topology_hint
            or ""
        ).strip().lower() or None,
        "topology_source": str(
            executor_plan.get("topology_source")
            or runtime_recipe.get("topology_source")
            or runtime_graph.get("topology_source")
            or (f"{target_runtime_hint_source}.target_topology" if target_topology_hint and target_runtime_hint_source else "")
            or ""
        ).strip() or None,
        "requires_external_db": requires_external_db,
        "health_path": None,
        "health_path_source": None,
        "healthchecks": [],
        "healthchecks_source": None,
        "sidecars": sidecars,
        "sidecars_source": sidecars_source,
        "sidecar_start_order": sidecar_start_order,
        "sidecar_start_order_source": sidecar_start_order_source,
        "target_sidecars_hint": target_sidecars_hint,
        "target_runtime_hint_source": target_runtime_hint_source,
        "seed_files": seed_files,
        "seed_files_source": seed_files_source,
        "seed_strategy": seed_strategy,
        "seed_strategy_source": seed_strategy_source,
        "volume_contract": volume_contract,
        "volume_contract_source": volume_contract_source,
        "network_contract": network_contract,
        "network_contract_source": network_contract_source,
        "network_mode": network_mode,
        "network_mode_source": network_mode_source,
        "allow_network": allow_network,
        "allow_network_source": allow_network_source,
    }
    service_entry, service_entry_source = _resolve_service_entry_from_sources(contract, executor_plan, runtime_recipe, runtime_graph)
    poc_entry, poc_entry_source = _resolve_poc_entry_from_sources(
        metadata_dir,
        contract,
        executor_plan,
        runtime_recipe,
        runtime_graph,
    )
    poc_cmd, poc_cmd_source = _resolve_poc_cmd_from_sources(metadata_dir, contract)
    base_url, base_url_source = _resolve_base_url_from_sources(policy, contract, executor_plan, runtime_graph, service_port)
    health_path, health_path_source = _resolve_health_path_from_sources(executor_plan, runtime_graph, runtime_recipe)
    healthchecks, healthchecks_source = _resolve_healthchecks_from_sources(executor_plan, runtime_graph, runtime_recipe)
    surface["service_entry"] = service_entry
    surface["service_entry_source"] = service_entry_source
    surface["poc_entry"] = poc_entry
    surface["poc_entry_source"] = poc_entry_source
    surface["poc_cmd"] = poc_cmd
    surface["poc_cmd_source"] = poc_cmd_source
    surface["base_url"] = base_url
    surface["base_url_source"] = base_url_source
    surface["health_path"] = health_path
    surface["health_path_source"] = health_path_source
    surface["healthchecks"] = healthchecks
    surface["healthchecks_source"] = healthchecks_source
    network_name = str(policy.get("network_name") or "").strip()
    if network_name:
        surface["network_name"] = network_name
    return surface


def _bundle_requires_external_db(plan: Dict[str, Any], bundle: VulnBundle) -> bool:
    metadata_dir = metadata_dir_for_bundle(plan, bundle)
    workspace: Path | None = None
    paths = plan.get("paths") if isinstance(plan.get("paths"), dict) else {}
    if isinstance(paths, dict) and paths.get("workspace"):
        workspace = workspace_dir_for_bundle(plan, bundle)
    executor_policy = ((plan.get("policy") or {}).get("executor") or {})
    return bool(
        _resolve_execution_surface(
            metadata_dir,
            workspace,
            executor_policy,
            plan=plan,
            bundle=bundle,
        ).get("requires_external_db")
    )


def _effective_executor_policy(metadata_dir: Path, executor_policy: Dict[str, Any]) -> Dict[str, Any]:
    policy = dict(executor_policy or {})
    surface = _resolve_execution_surface(metadata_dir, None, policy)
    policy["allow_network"] = bool(surface.get("allow_network"))
    policy["network_mode"] = str(surface.get("network_mode") or "none")
    policy["sidecars"] = deepcopy(surface.get("sidecars") or [])
    if surface.get("network_name"):
        policy["network_name"] = surface.get("network_name")
    return policy


def _validate_workspace_relative_path(raw_path: str, *, source: str, label: str) -> str:
    value = str(raw_path or "").strip()
    rel_path = Path(value)
    if rel_path.is_absolute() or ".." in rel_path.parts:
        raise ExecutorError(f"Invalid {label} path (source={source or 'unknown'}): {value}")
    return str(rel_path).lstrip("./")


def _validate_seed_files(workspace: Path | None, execution_surface: Dict[str, Any]) -> None:
    seed_files = execution_surface.get("seed_files") if isinstance(execution_surface.get("seed_files"), list) else []
    normalized_seed_files = [
        _validate_workspace_relative_path(
            str(item),
            source=str(execution_surface.get("seed_files_source") or "unknown"),
            label="seed file",
        )
        for item in seed_files
        if isinstance(item, str) and str(item).strip()
    ]
    if not normalized_seed_files or workspace is None:
        return
    missing: List[str] = []
    for relative_path in normalized_seed_files:
        candidate = workspace / relative_path
        if not candidate.exists():
            missing.append(relative_path)
    if missing:
        raise ExecutorError(
            "Declared seed files missing from workspace "
            f"(source={execution_surface.get('seed_files_source') or 'unknown'}): {', '.join(missing)}"
        )


def _validate_service_entry_contract(workspace: Path | None, execution_surface: Dict[str, Any]) -> None:
    if workspace is None:
        return
    service_entry = _validate_workspace_relative_path(
        str(execution_surface.get("service_entry") or "app.py"),
        source=str(execution_surface.get("service_entry_source") or "unknown"),
        label="service entry",
    ) or "app.py"
    service_path = workspace / service_entry
    if not service_path.exists() or not service_path.is_file():
        raise ExecutorError(
            "Declared service entry missing from workspace "
            f"(source={execution_surface.get('service_entry_source') or 'unknown'}): {service_entry}"
        )


def _validate_poc_entry_contract(workspace: Path | None, execution_surface: Dict[str, Any]) -> None:
    if workspace is None:
        return
    poc_entry = _validate_workspace_relative_path(
        str(execution_surface.get("poc_entry") or "poc.py"),
        source=str(execution_surface.get("poc_entry_source") or "unknown"),
        label="poc entry",
    ) or "poc.py"
    poc_path = workspace / poc_entry
    if not poc_path.exists() or not poc_path.is_file():
        raise ExecutorError(
            "Declared poc entry missing from workspace "
            f"(source={execution_surface.get('poc_entry_source') or 'unknown'}): {poc_entry}"
        )


def _validate_poc_cmd_contract(execution_surface: Dict[str, Any]) -> None:
    poc_cmd = str(execution_surface.get("poc_cmd") or "").strip()
    if not poc_cmd:
        return
    if "{{poc_path}}" in poc_cmd:
        return
    poc_entry = str(execution_surface.get("poc_entry") or "").strip() or "poc.py"
    entry_path = Path(poc_entry)
    entry_name = entry_path.name
    allowed_refs = {
        poc_entry,
        str(entry_path).lstrip("./"),
        entry_name,
        f"./{entry_name}",
    }

    if _needs_shell(poc_cmd):
        candidates = re.findall(r"(?:\./)?[A-Za-z0-9_./-]+\.(?:py|sh|js|ts|rb|php|pl)\b", poc_cmd)
    else:
        try:
            tokens = shlex.split(poc_cmd)
        except Exception:
            tokens = poc_cmd.split()
        candidates = [
            token
            for token in tokens
            if Path(str(token)).suffix.lower() in DEFAULT_POC_ENTRY_SUFFIXES
            and not str(token).startswith("/")
        ]
    if not candidates:
        return
    mismatched = [
        candidate
        for candidate in candidates
        if str(candidate).strip() not in allowed_refs and Path(str(candidate)).name != entry_name
    ]
    if mismatched:
        raise ExecutorError(
            "Declared poc_cmd references a local script inconsistent with poc_entry "
            f"(poc_cmd_source={execution_surface.get('poc_cmd_source') or 'unknown'}, "
            f"poc_entry_source={execution_surface.get('poc_entry_source') or 'unknown'}): "
            f"{', '.join(mismatched)}"
        )


def _validate_healthcheck_contract(execution_surface: Dict[str, Any]) -> None:
    healthchecks = execution_surface.get("healthchecks") if isinstance(execution_surface.get("healthchecks"), list) else []
    if not healthchecks:
        return
    source = str(execution_surface.get("healthchecks_source") or "unknown").strip() or "unknown"
    malformed: List[str] = []
    unsupported_nodes: List[str] = []
    explicit_service_ports: List[int] = []
    explicit_service_paths: List[str] = []
    for entry in healthchecks:
        if not isinstance(entry, dict):
            continue
        node = str(entry.get("node") or "service").strip().lower() or "service"
        transport = str(entry.get("transport") or "http").strip().lower() or "http"
        path = str(entry.get("path") or "").strip()
        port = entry.get("port")
        if node != "service":
            unsupported_nodes.append(node)
            continue
        if isinstance(port, int) and port > 0:
            explicit_service_ports.append(int(port))
        if transport not in {"http", "https", "tcp"}:
            malformed.append(f"service transport={transport or '<missing>'}")
            continue
        if transport in {"http", "https"} and not path:
            malformed.append(f"service {transport} missing path")
            continue
        if transport in {"http", "https"} and path:
            explicit_service_paths.append(path if path.startswith("/") else f"/{path}")
        if transport == "tcp" and path:
            malformed.append(f"service tcp path={path}")
    if unsupported_nodes:
        raise ExecutorError(
            "Declared healthchecks contain unsupported non-service nodes "
            f"(source={source}): {', '.join(sorted(dict.fromkeys(unsupported_nodes)))}"
        )
    if malformed:
        raise ExecutorError(
            "Declared healthchecks contain malformed service probes "
            f"(source={source}): {', '.join(malformed)}"
        )
    unique_ports = sorted(set(explicit_service_ports))
    if len(unique_ports) > 1:
        raise ExecutorError(
            "Declared healthchecks contain conflicting service probe ports "
            f"(source={source}): {', '.join(str(port) for port in unique_ports)}"
        )
    service_port = execution_surface.get("service_port")
    if len(unique_ports) == 1 and isinstance(service_port, int) and service_port > 0:
        probe_port = unique_ports[0]
        if probe_port != service_port:
            raise ExecutorError(
                "Declared healthchecks are inconsistent with resolved service_port "
                f"(healthchecks_source={source}, service_port_source={execution_surface.get('service_port_source') or 'unknown'}): "
                f"healthcheck_port={probe_port}, service_port={service_port}"
            )
    unique_paths = sorted(set(explicit_service_paths))
    health_path = str(execution_surface.get("health_path") or "").strip()
    normalized_health_path = health_path if not health_path or health_path.startswith("/") else f"/{health_path}"
    if len(unique_paths) == 1 and normalized_health_path and unique_paths[0] != normalized_health_path:
        raise ExecutorError(
            "Declared healthchecks are inconsistent with resolved health_path "
            f"(healthchecks_source={source}, health_path_source={execution_surface.get('health_path_source') or 'unknown'}): "
            f"healthcheck_path={unique_paths[0]}, health_path={normalized_health_path}"
        )


def _validate_service_endpoint_contract(execution_surface: Dict[str, Any]) -> None:
    base_url = str(execution_surface.get("base_url") or "").strip()
    service_port = execution_surface.get("service_port")
    if not base_url or not isinstance(service_port, int) or service_port <= 0:
        return
    try:
        parsed = urlsplit(base_url)
    except Exception:
        return
    host = str(parsed.hostname or "").strip().lower()
    if host not in {"127.0.0.1", "localhost"}:
        return
    effective_port = parsed.port
    if effective_port is None:
        if parsed.scheme == "http":
            effective_port = 80
        elif parsed.scheme == "https":
            effective_port = 443
    if effective_port is None:
        return
    if int(effective_port) != int(service_port):
        raise ExecutorError(
            "Declared base_url is inconsistent with service_port for local executor runtime "
            f"(base_url_source={execution_surface.get('base_url_source') or 'unknown'}, "
            f"service_port_source={execution_surface.get('service_port_source') or 'unknown'}): "
            f"base_url={base_url}, service_port={service_port}"
        )


def _runtime_family_token(raw: Any) -> str | None:
    token = str(raw or "").strip().lower()
    if not token:
        return None
    token = token.split("/")[-1]
    token = token.split(":")[0]
    if token in {"mysql", "mariadb"} or token.startswith("mysql") or token.startswith("mariadb"):
        return "mysql"
    if token in {"postgres", "postgresql"} or token.startswith("postgres"):
        return "postgres"
    return None


def _validate_sidecar_runtime_contract(execution_surface: Dict[str, Any]) -> None:
    sidecars = execution_surface.get("sidecars") if isinstance(execution_surface.get("sidecars"), list) else []
    db_family = _runtime_family_token(execution_surface.get("db"))
    hint_conflicts: List[str] = []
    db_conflicts: List[str] = []
    for entry in sidecars:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip() or "sidecar"
        hint_pairs = []
        for field in ("type", "name", "image"):
            family = _runtime_family_token(entry.get(field))
            value = str(entry.get(field) or "").strip()
            if family and value:
                hint_pairs.append((field, family, value))
        families = sorted({family for _, family, _ in hint_pairs})
        if len(families) > 1:
            hint_conflicts.append(
                f"{name} (" + ", ".join(f"{field}={value}" for field, _, value in hint_pairs) + ")"
            )
            continue
        sidecar_family = families[0] if families else _runtime_family_token(_sidecar_runtime_kind(entry))
        if db_family and sidecar_family and db_family != sidecar_family:
            db_conflicts.append(f"{name} runtime={sidecar_family} db={db_family}")
    if hint_conflicts:
        raise ExecutorError(
            "Declared sidecar runtime hints are inconsistent "
            f"(sidecars_source={execution_surface.get('sidecars_source') or 'unknown'}): {', '.join(hint_conflicts)}"
        )
    if db_conflicts:
        raise ExecutorError(
            "Declared sidecar runtime is inconsistent with resolved db family "
            f"(sidecars_source={execution_surface.get('sidecars_source') or 'unknown'}, "
            f"db_source={execution_surface.get('db_source') or 'unknown'}): {', '.join(db_conflicts)}"
        )


def _validate_sidecar_identity_contract(execution_surface: Dict[str, Any]) -> None:
    sidecars = execution_surface.get("sidecars") if isinstance(execution_surface.get("sidecars"), list) else []
    if not sidecars:
        return
    source = str(execution_surface.get("sidecars_source") or "unknown").strip() or "unknown"
    name_owner: Dict[str, str] = {}
    duplicate_names: List[str] = []
    for entry in sidecars:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        normalized = name.lower()
        owner = name_owner.get(normalized)
        if owner and owner != name:
            duplicate_names.append(name)
            continue
        if owner and owner == name:
            duplicate_names.append(name)
            continue
        name_owner[normalized] = name
    if duplicate_names:
        raise ExecutorError(
            "Declared sidecars contain duplicate sidecar names "
            f"(sidecars_source={source}): {', '.join(sorted(dict.fromkeys(duplicate_names)))}"
        )

    identity_owner: Dict[str, str] = {normalized: f"name:{name}" for normalized, name in name_owner.items()}
    collisions: List[str] = []
    for entry in sidecars:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        aliases = entry.get("aliases") if isinstance(entry.get("aliases"), list) else []
        for alias in aliases:
            alias_value = str(alias).strip()
            if not alias_value:
                continue
            normalized_alias = alias_value.lower()
            existing = identity_owner.get(normalized_alias)
            current_owner = f"alias:{name}"
            if existing and existing not in {f"name:{name}", current_owner}:
                collisions.append(f"{alias_value} ({existing} vs alias:{name})")
                continue
            identity_owner[normalized_alias] = current_owner
    if collisions:
        raise ExecutorError(
            "Declared sidecar aliases collide with other sidecar identities "
            f"(sidecars_source={source}): {', '.join(sorted(dict.fromkeys(collisions)))}"
        )


def _validate_service_runtime_binding_contract(execution_surface: Dict[str, Any]) -> None:
    service_port = execution_surface.get("service_port")
    if not isinstance(service_port, int) or service_port <= 0:
        return
    service_env = execution_surface.get("service_env") if isinstance(execution_surface.get("service_env"), dict) else {}
    sidecars = execution_surface.get("sidecars") if isinstance(execution_surface.get("sidecars"), list) else []
    mismatched: List[str] = []
    for key in ("APP_PORT", "PORT"):
        value = str(service_env.get(key) or "").strip()
        if not value or not value.isdigit():
            continue
        if int(value) != int(service_port):
            mismatched.append(f"{key}={value}")
    if mismatched:
        raise ExecutorError(
            "Declared service env port bindings are inconsistent with resolved service_port "
            f"(service_env_source={execution_surface.get('service_env_source') or 'unknown'}, "
            f"service_port_source={execution_surface.get('service_port_source') or 'unknown'}): "
            f"{', '.join(mismatched)}, service_port={service_port}"
        )
    db_token = str(execution_surface.get("db") or "").strip().lower()
    expected_db_port: int | None = None
    if db_token in {"mysql", "mariadb"}:
        expected_db_port = 3306
    elif db_token in {"postgres", "postgresql"}:
        expected_db_port = 5432
    if expected_db_port is None:
        for entry in sidecars:
            if not isinstance(entry, dict):
                continue
            sidecar_kind = _sidecar_runtime_kind(entry)
            if sidecar_kind in {"mysql", "mariadb"}:
                expected_db_port = 3306
                break
            if sidecar_kind in {"postgres", "postgresql"}:
                expected_db_port = 5432
                break
    db_port = str(service_env.get("DB_PORT") or "").strip()
    if expected_db_port is not None and db_port.isdigit() and int(db_port) != expected_db_port:
        raise ExecutorError(
            "Declared service env DB_PORT is inconsistent with resolved database runtime "
            f"(service_env_source={execution_surface.get('service_env_source') or 'unknown'}, "
            f"db_source={execution_surface.get('db_source') or 'unknown'}): "
            f"DB_PORT={db_port}, expected={expected_db_port}"
        )
    db_sidecar_aliases: set[str] = set()
    for entry in sidecars:
        if not isinstance(entry, dict):
            continue
        if _sidecar_runtime_kind(entry) not in {"mysql", "mariadb", "postgres", "postgresql"}:
            continue
        name = str(entry.get("name") or "").strip()
        if name:
            db_sidecar_aliases.add(name)
        aliases = entry.get("aliases") if isinstance(entry.get("aliases"), list) else []
        for alias in aliases:
            if isinstance(alias, str) and alias.strip():
                db_sidecar_aliases.add(alias.strip())
    db_host = str(service_env.get("DB_HOST") or "").strip()
    if db_sidecar_aliases and db_host and db_host not in db_sidecar_aliases:
        raise ExecutorError(
            "Declared service env DB_HOST is inconsistent with resolved sidecar aliases "
            f"(service_env_source={execution_surface.get('service_env_source') or 'unknown'}, "
            f"sidecars_source={execution_surface.get('sidecars_source') or 'unknown'}): "
            f"DB_HOST={db_host}, expected_one_of={', '.join(sorted(db_sidecar_aliases))}"
        )
    db_credential_mismatches: List[str] = []
    for entry in sidecars:
        if not isinstance(entry, dict):
            continue
        sidecar_kind = _sidecar_runtime_kind(entry)
        sidecar_env = entry.get("env") if isinstance(entry.get("env"), dict) else {}
        if sidecar_kind in {"mysql", "mariadb"}:
            field_pairs = (
                ("DB_NAME", "MYSQL_DATABASE"),
                ("DB_USER", "MYSQL_USER"),
                ("DB_PASSWORD", "MYSQL_PASSWORD"),
            )
        elif sidecar_kind in {"postgres", "postgresql"}:
            field_pairs = (
                ("DB_NAME", "POSTGRES_DB"),
                ("DB_USER", "POSTGRES_USER"),
                ("DB_PASSWORD", "POSTGRES_PASSWORD"),
            )
        else:
            continue
        for service_key, sidecar_key in field_pairs:
            service_value = str(service_env.get(service_key) or "").strip()
            sidecar_value = str(sidecar_env.get(sidecar_key) or "").strip()
            if service_value and sidecar_value and service_value != sidecar_value:
                db_credential_mismatches.append(
                    f"{service_key}={service_value} vs {sidecar_key}={sidecar_value}"
                )
    if db_credential_mismatches:
        raise ExecutorError(
            "Declared service env DB credentials are inconsistent with resolved sidecar env "
            f"(service_env_source={execution_surface.get('service_env_source') or 'unknown'}, "
            f"sidecars_source={execution_surface.get('sidecars_source') or 'unknown'}): "
            f"{', '.join(db_credential_mismatches)}"
        )
    db_field_mismatches: List[str] = []
    for entry in sidecars:
        if not isinstance(entry, dict):
            continue
        sidecar_kind = _sidecar_runtime_kind(entry)
        sidecar_env = entry.get("env") if isinstance(entry.get("env"), dict) else {}
        if sidecar_kind in {"mysql", "mariadb"}:
            field_map = {
                "DB_NAME": "MYSQL_DATABASE",
                "DB_USER": "MYSQL_USER",
                "DB_PASSWORD": "MYSQL_PASSWORD",
            }
        elif sidecar_kind in {"postgres", "postgresql"}:
            field_map = {
                "DB_NAME": "POSTGRES_DB",
                "DB_USER": "POSTGRES_USER",
                "DB_PASSWORD": "POSTGRES_PASSWORD",
            }
        else:
            continue
        for service_key, sidecar_key in field_map.items():
            service_value = str(service_env.get(service_key) or "").strip()
            sidecar_value = str(sidecar_env.get(sidecar_key) or "").strip()
            if service_value and sidecar_value and service_value != sidecar_value:
                db_field_mismatches.append(
                    f"{service_key}={service_value} vs {sidecar_key}={sidecar_value}"
                )
    if db_field_mismatches:
        raise ExecutorError(
            "Declared service env DB credentials are inconsistent with resolved sidecar env "
            f"(service_env_source={execution_surface.get('service_env_source') or 'unknown'}, "
            f"sidecars_source={execution_surface.get('sidecars_source') or 'unknown'}): "
            f"{', '.join(db_field_mismatches)}"
        )


def _validate_seed_strategy_contract(execution_surface: Dict[str, Any]) -> None:
    seed_strategy = str(execution_surface.get("seed_strategy") or "").strip().lower()
    if not seed_strategy:
        return
    strategy_source = str(execution_surface.get("seed_strategy_source") or "unknown").strip() or "unknown"
    db = str(execution_surface.get("db") or "").strip().lower()
    sidecars = execution_surface.get("sidecars") if isinstance(execution_surface.get("sidecars"), list) else []
    requires_external_db = bool(execution_surface.get("requires_external_db"))
    sql_seed_files = _sql_seed_files(execution_surface)
    sql_sidecar_kinds = {
        kind
        for kind in (
            _sidecar_runtime_kind(entry)
            for entry in sidecars
            if isinstance(entry, dict)
        )
        if kind in {"mysql", "mariadb", "postgres", "postgresql"}
    }
    if seed_strategy == "sqlite_service_init":
        if db and db != "sqlite":
            raise ExecutorError(
                "Declared seed strategy sqlite_service_init is incompatible with non-sqlite runtime "
                f"(source={strategy_source}, db={db})"
            )
        if requires_external_db or sidecars:
            raise ExecutorError(
                "Declared seed strategy sqlite_service_init is incompatible with sidecar/external-db runtime "
                f"(source={strategy_source})"
            )
        return
    if seed_strategy == "sidecar_sql_apply":
        if db == "sqlite":
            raise ExecutorError(
                "Declared seed strategy sidecar_sql_apply is incompatible with sqlite runtime "
                f"(source={strategy_source})"
            )
        if not (requires_external_db or sidecars):
            raise ExecutorError(
                "Declared seed strategy sidecar_sql_apply requires external-db or sidecar runtime "
                f"(source={strategy_source})"
            )
        if not sql_seed_files:
            raise ExecutorError(
                "Declared seed strategy sidecar_sql_apply requires at least one .sql seed file "
                f"(source={strategy_source})"
            )
        if not sql_sidecar_kinds:
            raise ExecutorError(
                "Declared seed strategy sidecar_sql_apply requires a SQL-capable sidecar target "
                f"(source={strategy_source})"
            )
        if len(sql_sidecar_kinds) > 1:
            raise ExecutorError(
                "Declared seed strategy sidecar_sql_apply is ambiguous across multiple SQL sidecar runtimes "
                f"(source={strategy_source}): {', '.join(sorted(sql_sidecar_kinds))}"
            )


def _validate_env_contract_shape(execution_surface: Dict[str, Any]) -> None:
    env_contract = execution_surface.get("env_contract") if isinstance(execution_surface.get("env_contract"), list) else []
    if not env_contract:
        return
    unsupported_scopes: List[str] = []
    for entry in env_contract:
        if not isinstance(entry, dict):
            continue
        scope = str(entry.get("scope") or "").strip().lower()
        if not scope:
            continue
        if scope == "service" or scope.startswith("sidecar:"):
            continue
        unsupported_scopes.append(scope)
    if unsupported_scopes:
        raise ExecutorError(
            "Declared env contract contains unsupported scopes "
            f"(source={execution_surface.get('env_contract_source') or 'unknown'}): {', '.join(sorted(dict.fromkeys(unsupported_scopes)))}"
        )


def _validate_service_env_contract(execution_surface: Dict[str, Any]) -> None:
    env_contract = execution_surface.get("env_contract") if isinstance(execution_surface.get("env_contract"), list) else []
    service_env = execution_surface.get("service_env") if isinstance(execution_surface.get("service_env"), dict) else {}
    required_names: List[str] = []
    conflicting: List[str] = []
    expected_by_name: Dict[str, str] = {}
    mismatched: List[str] = []
    for entry in env_contract:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("scope") or "").strip().lower() != "service":
            continue
        name = str(entry.get("name") or "").strip()
        if name and name not in required_names:
            required_names.append(name)
        expected_value = str(entry.get("value") or "").strip()
        if name and expected_value:
            existing = expected_by_name.get(name)
            if existing and existing != expected_value:
                conflicting.append(f"{name} ({existing} vs {expected_value})")
            else:
                expected_by_name[name] = expected_value
        actual_value = str(service_env.get(name) or "").strip()
        if name and expected_value and actual_value and expected_value != actual_value:
            mismatched.append(f"{name} (expected={expected_value}, actual={actual_value})")
    if conflicting:
        raise ExecutorError(
            "Declared env contract contains conflicting service values "
            f"(source={execution_surface.get('env_contract_source') or 'unknown'}): {', '.join(sorted(dict.fromkeys(conflicting)))}"
        )
    missing = [name for name in required_names if not str(service_env.get(name) or "").strip()]
    if missing:
        raise ExecutorError(
            "Declared env contract missing service env values "
            f"(source={execution_surface.get('env_contract_source') or 'unknown'}): {', '.join(missing)}"
        )
    if mismatched:
        raise ExecutorError(
            "Declared env contract value mismatch "
            f"(source={execution_surface.get('env_contract_source') or 'unknown'}): {', '.join(mismatched)}"
        )


def _validate_sidecar_env_contract(execution_surface: Dict[str, Any]) -> None:
    env_contract = execution_surface.get("env_contract") if isinstance(execution_surface.get("env_contract"), list) else []
    sidecars = execution_surface.get("sidecars") if isinstance(execution_surface.get("sidecars"), list) else []
    if not env_contract:
        return
    sidecar_env_by_scope: Dict[str, Dict[str, str]] = {}
    for entry in sidecars:
        if not isinstance(entry, dict):
            continue
        sidecar_name = str(entry.get("name") or "").strip().lower()
        sidecar_env = entry.get("env") if isinstance(entry.get("env"), dict) else {}
        if not sidecar_name:
            continue
        sidecar_env_by_scope[f"sidecar:{sidecar_name}"] = {
            str(key): str(value)
            for key, value in sidecar_env.items()
            if isinstance(key, str) and key.strip() and value not in (None, "")
        }
    expected_by_scope_name: Dict[tuple[str, str], str] = {}
    conflicting: List[str] = []
    missing_targets: List[str] = []
    missing_values: List[str] = []
    mismatched: List[str] = []
    for entry in env_contract:
        if not isinstance(entry, dict):
            continue
        scope = str(entry.get("scope") or "").strip().lower()
        if not scope.startswith("sidecar:"):
            continue
        target_env = sidecar_env_by_scope.get(scope)
        if target_env is None:
            if scope not in missing_targets:
                missing_targets.append(scope)
            continue
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        expected_value = str(entry.get("value") or "").strip()
        if expected_value:
            key = (scope, name)
            existing = expected_by_scope_name.get(key)
            if existing and existing != expected_value:
                conflicting.append(f"{scope}.{name} ({existing} vs {expected_value})")
            else:
                expected_by_scope_name[key] = expected_value
        actual_value = str(target_env.get(name) or "").strip()
        if not actual_value:
            missing_values.append(f"{scope}.{name}")
            continue
        if expected_value and expected_value != actual_value:
            mismatched.append(f"{scope}.{name} (expected={expected_value}, actual={actual_value})")
    if conflicting:
        raise ExecutorError(
            "Declared env contract contains conflicting sidecar values "
            f"(source={execution_surface.get('env_contract_source') or 'unknown'}): {', '.join(sorted(dict.fromkeys(conflicting)))}"
        )
    if missing_targets:
        raise ExecutorError(
            "Declared env contract targets missing sidecar entries "
            f"(source={execution_surface.get('env_contract_source') or 'unknown'}): {', '.join(missing_targets)}"
        )
    if missing_values:
        raise ExecutorError(
            "Declared env contract missing sidecar env values "
            f"(source={execution_surface.get('env_contract_source') or 'unknown'}): {', '.join(missing_values)}"
        )
    if mismatched:
        raise ExecutorError(
            "Declared env contract sidecar value mismatch "
            f"(source={execution_surface.get('env_contract_source') or 'unknown'}): {', '.join(mismatched)}"
        )


def _validate_sidecar_probe_contract(execution_surface: Dict[str, Any]) -> None:
    sidecars = execution_surface.get("sidecars") if isinstance(execution_surface.get("sidecars"), list) else []
    mismatched: List[str] = []
    for entry in sidecars:
        if not isinstance(entry, dict):
            continue
        sidecar_kind = _sidecar_runtime_kind(entry)
        if sidecar_kind in {"mysql", "mariadb"}:
            expected_probe_type = "mysql"
        elif sidecar_kind in {"postgres", "postgresql"}:
            expected_probe_type = "postgres"
        else:
            continue
        probe = entry.get("ready_probe") if isinstance(entry.get("ready_probe"), dict) else {}
        probe_type = str(probe.get("type") or "").strip().lower()
        if probe_type and probe_type != expected_probe_type:
            mismatched.append(
                f"{str(entry.get('name') or sidecar_kind)} probe_type={probe_type} expected={expected_probe_type}"
            )
    if mismatched:
        raise ExecutorError(
            "Declared sidecar ready_probe is inconsistent with resolved sidecar runtime "
            f"(sidecars_source={execution_surface.get('sidecars_source') or 'unknown'}): {', '.join(mismatched)}"
        )


def _validate_volume_contract(execution_surface: Dict[str, Any]) -> None:
    volume_contract = execution_surface.get("volume_contract") if isinstance(execution_surface.get("volume_contract"), list) else []
    sidecars = execution_surface.get("sidecars") if isinstance(execution_surface.get("sidecars"), list) else []
    if not volume_contract:
        return
    sidecar_names = {
        str(entry.get("name") or "").strip().lower()
        for entry in sidecars
        if isinstance(entry, dict) and str(entry.get("name") or "").strip()
    }
    unsupported_scopes: List[str] = []
    unsupported_sources: List[str] = []
    seen_mounts: Dict[tuple[str, str], tuple[str, str]] = {}
    conflicting_mounts: List[str] = []
    malformed: List[str] = []
    missing_targets: List[str] = []
    for entry in volume_contract:
        if not isinstance(entry, dict):
            continue
        scope = str(entry.get("scope") or "").strip().lower()
        if not scope.startswith("sidecar:"):
            if scope:
                unsupported_scopes.append(scope)
            continue
        sidecar_name = scope.split(":", 1)[1].strip().lower()
        if sidecar_name not in sidecar_names:
            missing_targets.append(scope)
            continue
        target = str(entry.get("target") or "").strip()
        source = str(entry.get("source") or "").strip().lower() or "workspace"
        mode = str(entry.get("mode") or "").strip().lower() or "rw"
        if source not in {"workspace", "runtime"}:
            unsupported_sources.append(f"{scope} -> source={source}")
            continue
        if not target.startswith("/") or mode not in {"ro", "rw"}:
            malformed.append(f"{scope} -> target={target or '<missing>'}, mode={mode}")
            continue
        key = (scope, target)
        signature = (source, mode)
        existing = seen_mounts.get(key)
        if existing and existing != signature:
            conflicting_mounts.append(
                f"{scope} -> {target} ({existing[0]}/{existing[1]} vs {source}/{mode})"
            )
            continue
        seen_mounts[key] = signature
    if unsupported_scopes:
        raise ExecutorError(
            "Declared volume contract contains unsupported scopes "
            f"(source={execution_surface.get('volume_contract_source') or 'unknown'}): {', '.join(sorted(dict.fromkeys(unsupported_scopes)))}"
        )
    if unsupported_sources:
        raise ExecutorError(
            "Declared volume contract contains unsupported mount sources "
            f"(source={execution_surface.get('volume_contract_source') or 'unknown'}): {', '.join(sorted(dict.fromkeys(unsupported_sources)))}"
        )
    if missing_targets:
        raise ExecutorError(
            "Declared volume contract targets missing sidecar entries "
            f"(source={execution_surface.get('volume_contract_source') or 'unknown'}): {', '.join(missing_targets)}"
        )
    if conflicting_mounts:
        raise ExecutorError(
            "Declared volume contract contains conflicting sidecar mount definitions "
            f"(source={execution_surface.get('volume_contract_source') or 'unknown'}): {', '.join(sorted(dict.fromkeys(conflicting_mounts)))}"
        )
    if malformed:
        raise ExecutorError(
            "Declared volume contract contains malformed sidecar mounts "
            f"(source={execution_surface.get('volume_contract_source') or 'unknown'}): {', '.join(malformed)}"
        )
    seed_strategy = str(execution_surface.get("seed_strategy") or "").strip().lower()
    sql_seed_files = _sql_seed_files(execution_surface)
    if seed_strategy == "sidecar_sql_apply" and sql_seed_files:
        required_scopes = {
            f"sidecar:{str(entry.get('name') or '').strip().lower()}"
            for entry in sidecars
            if isinstance(entry, dict) and _sidecar_runtime_kind(entry) in {"mysql", "mariadb", "postgres", "postgresql"}
        }
        ambiguous_seed_mounts: List[str] = []
        for scope in sorted(required_scopes):
            matching_targets = sorted(
                {
                    str(contract_entry.get("target") or "").strip()
                    for contract_entry in volume_contract
                    if isinstance(contract_entry, dict)
                    and str(contract_entry.get("scope") or "").strip().lower() == scope
                    and str(contract_entry.get("source") or "").strip().lower() in {"", "workspace"}
                    and str(contract_entry.get("target") or "").strip().startswith("/")
                    and (str(contract_entry.get("mode") or "").strip().lower() or "rw") == "ro"
                }
            )
            if len(matching_targets) > 1:
                ambiguous_seed_mounts.append(f"{scope} -> {', '.join(matching_targets)}")
        if ambiguous_seed_mounts:
            raise ExecutorError(
                "Declared volume contract contains ambiguous workspace seed mount targets "
                f"(source={execution_surface.get('volume_contract_source') or 'unknown'}): {', '.join(ambiguous_seed_mounts)}"
            )
        missing_seed_mounts = [
            scope
            for scope in sorted(required_scopes)
            if not any(
                isinstance(contract_entry, dict)
                and str(contract_entry.get("scope") or "").strip().lower() == scope
                and str(contract_entry.get("source") or "").strip().lower() in {"", "workspace"}
                and str(contract_entry.get("target") or "").strip().startswith("/")
                and (str(contract_entry.get("mode") or "").strip().lower() or "rw") == "ro"
                for contract_entry in volume_contract
            )
        ]
        if missing_seed_mounts:
            raise ExecutorError(
                "Declared volume contract missing workspace seed mount entries "
                f"(source={execution_surface.get('volume_contract_source') or 'unknown'}): {', '.join(missing_seed_mounts)}"
            )


def _validate_network_contract(execution_surface: Dict[str, Any]) -> None:
    network_contract = execution_surface.get("network_contract") if isinstance(execution_surface.get("network_contract"), list) else []
    if not network_contract:
        return
    sidecars = execution_surface.get("sidecars") if isinstance(execution_surface.get("sidecars"), list) else []
    service_env = execution_surface.get("service_env") if isinstance(execution_surface.get("service_env"), dict) else {}
    sidecar_aliases: Dict[str, List[str]] = {}
    alias_catalog: set[str] = set()
    for entry in sidecars:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip().lower()
        aliases = entry.get("aliases") if isinstance(entry.get("aliases"), list) else []
        values = [
            str(alias).strip()
            for alias in aliases
            if isinstance(alias, str) and str(alias).strip()
        ]
        if name:
            values.append(name)
        if not name:
            continue
        deduped: List[str] = []
        for value in values:
            if value not in deduped:
                deduped.append(value)
                alias_catalog.add(value)
        sidecar_aliases[f"sidecar:{name}"] = deduped
    expected_service_alias_by_name: Dict[str, str] = {}
    conflicting_service_aliases: List[str] = []
    missing_targets: List[str] = []
    unresolved_service_aliases: List[str] = []
    unsupported_scopes: List[str] = []
    mismatched_service_aliases: List[str] = []
    mismatched_sidecar_aliases: List[str] = []
    for entry in network_contract:
        if not isinstance(entry, dict):
            continue
        scope = str(entry.get("scope") or "").strip().lower()
        alias = str(entry.get("alias") or "").strip()
        if not scope or not alias:
            continue
        if scope == "service":
            name = str(entry.get("name") or "").strip() or "DB_HOST"
            existing_alias = expected_service_alias_by_name.get(name)
            if existing_alias and existing_alias != alias:
                conflicting_service_aliases.append(f"{name} ({existing_alias} vs {alias})")
                continue
            expected_service_alias_by_name[name] = alias
            actual_value = str(service_env.get(name) or "").strip()
            if actual_value and actual_value != alias:
                mismatched_service_aliases.append(f"{name} (expected={alias}, actual={actual_value})")
            if not alias_catalog:
                unresolved_service_aliases.append(f"{name} alias unresolved ({alias})")
            elif alias not in alias_catalog:
                mismatched_service_aliases.append(f"{name} alias unresolved ({alias})")
            continue
        if scope.startswith("sidecar:"):
            aliases = sidecar_aliases.get(scope)
            if aliases is None:
                missing_targets.append(scope)
                continue
            if alias not in aliases:
                mismatched_sidecar_aliases.append(f"{scope} alias={alias}")
            continue
        unsupported_scopes.append(scope)
    if unsupported_scopes:
        raise ExecutorError(
            "Declared network contract contains unsupported scopes "
            f"(source={execution_surface.get('network_contract_source') or 'unknown'}): {', '.join(sorted(dict.fromkeys(unsupported_scopes)))}"
        )
    if missing_targets:
        raise ExecutorError(
            "Declared network contract targets missing sidecar entries "
            f"(source={execution_surface.get('network_contract_source') or 'unknown'}): {', '.join(missing_targets)}"
        )
    if conflicting_service_aliases:
        raise ExecutorError(
            "Declared network contract contains conflicting service aliases "
            f"(source={execution_surface.get('network_contract_source') or 'unknown'}): {', '.join(sorted(dict.fromkeys(conflicting_service_aliases)))}"
        )
    if unresolved_service_aliases:
        raise ExecutorError(
            "Declared network contract contains unresolved service aliases without sidecar targets "
            f"(source={execution_surface.get('network_contract_source') or 'unknown'}): {', '.join(sorted(dict.fromkeys(unresolved_service_aliases)))}"
        )
    if mismatched_sidecar_aliases:
        raise ExecutorError(
            "Declared network contract sidecar alias mismatch "
            f"(source={execution_surface.get('network_contract_source') or 'unknown'}): {', '.join(mismatched_sidecar_aliases)}"
        )
    if mismatched_service_aliases:
        raise ExecutorError(
            "Declared network contract service alias mismatch "
            f"(source={execution_surface.get('network_contract_source') or 'unknown'}): {', '.join(mismatched_service_aliases)}"
        )
    if sidecars and network_contract and execution_surface.get("allow_network") is False:
        raise ExecutorError(
            "Declared network contract requires enabled executor network "
            f"(source={execution_surface.get('network_contract_source') or 'unknown'})"
        )


def _validate_sidecar_dependency_contract(
    execution_surface: Dict[str, Any],
    runtime_graph: Dict[str, Any],
) -> None:
    sidecars = execution_surface.get("sidecars") if isinstance(execution_surface.get("sidecars"), list) else []
    if not sidecars:
        return
    sidecar_names = [
        str(entry.get("name") or "").strip()
        for entry in sidecars
        if isinstance(entry, dict) and str(entry.get("name") or "").strip()
    ]
    if not sidecar_names:
        return
    sidecar_name_set = set(sidecar_names)
    source = str(execution_surface.get("sidecar_start_order_source") or "unknown").strip() or "unknown"
    start_order = (
        execution_surface.get("sidecar_start_order")
        if isinstance(execution_surface.get("sidecar_start_order"), list)
        else []
    )
    normalized_order = [str(name).strip() for name in start_order if isinstance(name, str) and str(name).strip()]
    unknown_names = [name for name in normalized_order if name not in sidecar_name_set]
    if unknown_names:
        raise ExecutorError(
            "Declared sidecar start order references unknown sidecars "
            f"(source={source}): {', '.join(unknown_names)}"
        )
    duplicates: List[str] = []
    seen: set[str] = set()
    for name in normalized_order:
        if name in seen and name not in duplicates:
            duplicates.append(name)
        seen.add(name)
    if duplicates:
        raise ExecutorError(
            "Declared sidecar start order contains duplicate sidecars "
            f"(source={source}): {', '.join(duplicates)}"
        )

    edges = runtime_graph.get("edges") if isinstance(runtime_graph.get("edges"), list) else []
    if not edges:
        return
    dependency_by_name: Dict[str, str] = {}
    malformed: List[str] = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        target = str(edge.get("to") or "").strip()
        startup_after = str(edge.get("startup_after") or "").strip()
        if not target.startswith("sidecar:") or not startup_after:
            continue
        if not startup_after.startswith("sidecar:"):
            malformed.append(f"{target} -> {startup_after}")
            continue
        sidecar_name = target.split(":", 1)[1].strip()
        dependency_name = startup_after.split(":", 1)[1].strip()
        if not sidecar_name or not dependency_name:
            malformed.append(f"{target} -> {startup_after}")
            continue
        if sidecar_name not in sidecar_name_set or dependency_name not in sidecar_name_set:
            malformed.append(f"{sidecar_name} -> {dependency_name}")
            continue
        existing = dependency_by_name.get(sidecar_name)
        if existing and existing != dependency_name:
            malformed.append(f"{sidecar_name} -> {dependency_name}")
            continue
        dependency_by_name[sidecar_name] = dependency_name
    if malformed:
        raise ExecutorError(
            "runtime_graph startup_after references malformed or unknown sidecars "
            f"(source=runtime_graph.edges.startup_after): {', '.join(malformed)}"
        )
    if not dependency_by_name:
        return

    state_by_name: Dict[str, int] = {}
    cycle_path: List[str] = []

    def _visit(name: str) -> bool:
        state = state_by_name.get(name, 0)
        if state == 1:
            cycle_path.append(name)
            return True
        if state == 2:
            return False
        state_by_name[name] = 1
        dependency = dependency_by_name.get(name)
        if dependency and _visit(dependency):
            if name not in cycle_path:
                cycle_path.append(name)
            return True
        state_by_name[name] = 2
        return False

    for name in dependency_by_name:
        if _visit(name):
            ordered_cycle = list(dict.fromkeys(reversed(cycle_path)))
            raise ExecutorError(
                "runtime_graph startup_after contains cyclic sidecar dependency "
                f"(source=runtime_graph.edges.startup_after): {', '.join(ordered_cycle)}"
            )

    effective_order = [
        str(entry.get("name") or "").strip()
        for entry in _ordered_sidecars(sidecars, normalized_order)
        if isinstance(entry, dict) and str(entry.get("name") or "").strip()
    ]
    order_index = {name: idx for idx, name in enumerate(effective_order)}
    mismatched: List[str] = []
    for sidecar_name, dependency_name in dependency_by_name.items():
        sidecar_index = order_index.get(sidecar_name)
        dependency_index = order_index.get(dependency_name)
        if sidecar_index is None or dependency_index is None:
            continue
        if dependency_index > sidecar_index:
            mismatched.append(f"{sidecar_name} after {dependency_name}")
    if mismatched:
        raise ExecutorError(
            "sidecar start order violates runtime_graph startup_after dependency "
            f"(source={source}): {', '.join(mismatched)}"
        )


def _validate_seed_init_contract(workspace: Path | None, execution_surface: Dict[str, Any]) -> None:
    seed_files = execution_surface.get("seed_files") if isinstance(execution_surface.get("seed_files"), list) else []
    normalized_seed_files = [
        str(item).strip().lstrip("./")
        for item in seed_files
        if isinstance(item, str) and str(item).strip()
    ]
    if not normalized_seed_files or workspace is None:
        return
    seed_strategy = str(execution_surface.get("seed_strategy") or "").strip().lower()
    if seed_strategy and seed_strategy != "sqlite_service_init":
        return
    db = str(execution_surface.get("db") or "").strip().lower()
    if db != "sqlite":
        return
    service_entry = str(execution_surface.get("service_entry") or "").strip().lstrip("./") or "app.py"
    service_path = workspace / service_entry
    if not service_path.exists():
        return
    try:
        content = service_path.read_text(encoding="utf-8")
    except Exception:
        return
    lowered = content.lower()
    basename_hits = [
        Path(item).name.lower()
        for item in normalized_seed_files
        if Path(item).name.lower() in lowered
    ]
    init_markers = (
        "init_db(",
        "init_sqlite",
        "executescript(",
        "db.create_all(",
        "create table",
    )
    if basename_hits or any(marker in lowered for marker in init_markers):
        return
    raise ExecutorError(
        "Declared seed files require sqlite runtime init signals before run "
        f"(service_entry={service_entry}, seed_files={', '.join(normalized_seed_files)})"
    )


def _resolve_base_url(metadata_dir: Path, executor_policy: Dict[str, Any], port: int) -> str:
    """Resolve base URL for PoC scripts executed *inside* the container."""
    contract, executor_plan, _, runtime_graph = _load_contract_sections(metadata_dir)
    value, _ = _resolve_base_url_from_sources(executor_policy, contract, executor_plan, runtime_graph, port)
    return value


def _resolve_service_port(metadata_dir: Path, workspace: Path | None) -> int:
    """Resolve service port from generator metadata, manifest, or Dockerfile."""
    contract, executor_plan, runtime_recipe, runtime_graph = _load_contract_sections(metadata_dir)
    value, _ = _resolve_service_port_from_sources(
        metadata_dir,
        workspace,
        contract,
        executor_plan,
        runtime_recipe,
        runtime_graph,
    )
    return value


def _resolve_health_path(metadata_dir: Path) -> str | None:
    _, executor_plan, runtime_recipe, runtime_graph = _load_contract_sections(metadata_dir)
    value, _ = _resolve_health_path_from_sources(executor_plan, runtime_graph, runtime_recipe)
    return value


def _resolve_healthchecks(metadata_dir: Path) -> List[Dict[str, Any]]:
    _, executor_plan, runtime_recipe, runtime_graph = _load_contract_sections(metadata_dir)
    healthchecks, _ = _resolve_healthchecks_from_sources(executor_plan, runtime_graph, runtime_recipe)
    return healthchecks


def _resolve_service_env(metadata_dir: Path) -> Dict[str, str]:
    contract, executor_plan, runtime_recipe, runtime_graph = _load_contract_sections(metadata_dir)
    env, _ = _resolve_service_env_from_sources(metadata_dir, contract, executor_plan, runtime_recipe, runtime_graph)
    return env


def _port_from_generator_template(metadata_dir: Path) -> int | None:
    data = _load_json(metadata_dir / "generator_template.json")
    if not isinstance(data, dict):
        return None
    ports = data.get("ports")
    if isinstance(ports, dict):
        candidate = ports.get("app") or ports.get("service") or ports.get("web")
        try:
            value = int(candidate)
        except Exception:
            value = None
        if value:
            return value
    candidate = data.get("service_port") or data.get("port")
    try:
        value = int(candidate)
    except Exception:
        value = None
    return value or None


def _port_from_generator_manifest(metadata_dir: Path) -> int | None:
    payload = _load_json(metadata_dir / "generator_manifest.json")
    if not isinstance(payload, dict):
        return None
    manifest = payload.get("manifest")
    if not isinstance(manifest, dict):
        return None
    run_section = manifest.get("run")
    if isinstance(run_section, dict):
        port = run_section.get("port")
        try:
            value = int(port)
        except Exception:
            value = None
        if value:
            return value
        command = run_section.get("command")
        if isinstance(command, str):
            return _parse_port_from_run_command(command)
    if isinstance(run_section, str):
        return _parse_port_from_run_command(run_section)
    return None


def _parse_port_from_run_command(command: str) -> int | None:
    text = (command or "").strip()
    if not text:
        return None
    # docker run -p HOST:CONTAINER, or --publish HOST:CONTAINER
    pattern = re.compile(r"(?:-p|--publish)\s*(\d+)\s*:\s*(\d+)")
    match = pattern.search(text)
    if match:
        try:
            return int(match.group(2))
        except Exception:
            return None
    return None


def _port_from_dockerfile(workspace: Path) -> int | None:
    dockerfile = workspace / "Dockerfile"
    if not dockerfile.exists():
        return None
    try:
        lines = dockerfile.read_text(encoding="utf-8").splitlines()
    except Exception:
        return None
    for line in lines:
        stripped = line.strip()
        if not stripped.upper().startswith("EXPOSE"):
            continue
        parts = stripped.split()
        for token in parts[1:]:
            raw = token.split("/")[0].strip()
            if raw.isdigit():
                value = int(raw)
                if value > 0:
                    return value
    return None


def _resolve_poc_entry_relpath(metadata_dir: Path) -> str:
    """Resolve poc entry path relative to workspace."""
    relpath, _ = _resolve_poc_entry_from_metadata(metadata_dir)
    return relpath


def _push_poc_script(
    workspace: Path,
    container_name: str,
    log_path: Path,
    *,
    poc_entry: str,
    poc_entry_source: str | None,
    executor_policy: Dict[str, Any] | None = None,
) -> str:
    if DOCKER_BIN is None:
        raise ExecutorError("Docker binary not available for copying PoC script")
    rel = str(poc_entry or "").strip() or "poc.py"
    rel_path = Path(rel)
    if rel_path.is_absolute() or ".." in rel_path.parts:
        raise ExecutorError(f"Invalid poc_entry path (source={poc_entry_source or 'unknown'}): {rel}")
    source_path = workspace / rel_path
    if not source_path.exists():
        raise ExecutorError(
            f"PoC script missing from workspace (source={poc_entry_source or 'unknown'}): {source_path}"
        )
    entry_name = rel_path.name
    allowed_suffixes = list(DEFAULT_POC_ENTRY_SUFFIXES)
    policy_allow = (executor_policy or {}).get("poc_entry_suffixes")
    if isinstance(policy_allow, list) and policy_allow:
        allowed_suffixes = []
        for entry in policy_allow:
            if not isinstance(entry, str):
                continue
            suffix = entry.strip()
            if not suffix:
                continue
            if not suffix.startswith("."):
                suffix = f".{suffix}"
            allowed_suffixes.append(suffix.lower())
        if not allowed_suffixes:
            allowed_suffixes = list(DEFAULT_POC_ENTRY_SUFFIXES)
    if Path(entry_name).suffix.lower() not in set(allowed_suffixes):
        raise ExecutorError(
            f"Unsupported poc_entry filename: {entry_name} (allowed: {', '.join(sorted(set(allowed_suffixes)))})"
        )
    data = source_path.read_bytes()
    dest_path = f"/tmp/{entry_name}"
    quoted_dest = shlex.quote(dest_path)
    cmd = [
        DOCKER_BIN,
        "exec",
        "-i",
        container_name,
        "sh",
        "-c",
        f"cat > {quoted_dest} && chmod 0644 {quoted_dest}",
    ]
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("$ " + " ".join(cmd) + "\n")
        handle.flush()
        proc = subprocess.run(cmd, input=data, stdout=handle, stderr=subprocess.STDOUT, check=False)
    if proc.returncode != 0:
        raise ExecutorError(f"Command failed ({proc.returncode}): {' '.join(cmd)}")
    return dest_path


def _build_poc_exec_cmd(
    container_name: str,
    metadata_dir: Path,
    poc_path: str,
    base_url: str,
    *,
    poc_cmd: str | None = None,
    payload: str | None,
) -> List[str]:
    exec_prefix = [DOCKER_BIN, "exec", "-w", "/app", "-e", "PYTHONPATH=/app", container_name]
    cmd = str(poc_cmd or "").strip() or _resolve_poc_cmd(metadata_dir)
    if cmd is None:
        suffix = Path(poc_path).suffix.lower()
        interpreter = "python"
        if suffix == ".sh":
            interpreter = "sh"
        elif suffix == ".js":
            interpreter = "node"
        elif suffix == ".ts":
            interpreter = "ts-node"
        elif suffix == ".rb":
            interpreter = "ruby"
        elif suffix == ".php":
            interpreter = "php"
        elif suffix == ".pl":
            interpreter = "perl"
        args = [interpreter, poc_path, "--base-url", base_url]
        if payload:
            args.extend(["--payload", payload])
        return [*exec_prefix, *args]

    if _needs_shell(cmd):
        rendered = _render_poc_cmd_shell(cmd, poc_path=poc_path, base_url=base_url, payload=payload)
        return [*exec_prefix, "sh", "-lc", rendered]

    tokens = shlex.split(cmd)
    rendered_tokens: List[str] = []
    for token in tokens:
        token = _rewrite_poc_token(token, poc_path)
        token = token.replace("{{poc_path}}", poc_path).replace("{{base_url}}", base_url)
        if "{{payload}}" in token:
            if payload is None:
                if rendered_tokens and rendered_tokens[-1] == "--payload":
                    rendered_tokens.pop()
                continue
            token = token.replace("{{payload}}", payload)
        rendered_tokens.append(token)

    if payload and "--payload" in rendered_tokens:
        # If the template declared a --payload switch but didn't include a value,
        # append the payload as the next argument.
        try:
            idx = rendered_tokens.index("--payload")
        except ValueError:
            idx = -1
        if idx != -1 and idx == len(rendered_tokens) - 1:
            rendered_tokens.append(payload)

    return [*exec_prefix, *rendered_tokens]


def _resolve_poc_cmd(metadata_dir: Path) -> str | None:
    cmd, _ = _resolve_poc_cmd_from_metadata(metadata_dir)
    return cmd


def _render_poc_cmd_shell(
    cmd: str,
    *,
    poc_path: str,
    base_url: str,
    payload: str | None,
) -> str:
    raw = (cmd or "").strip()
    raw = raw.replace("{{poc_path}}", poc_path).replace("{{base_url}}", shlex.quote(base_url))
    # Backwards compat: map common relative poc paths to the injected path.
    raw = re.sub(r"(?:(?:\\./)?poc\\.py)\\b", poc_path, raw)
    if payload is not None and "{{payload}}" in raw:
        raw = raw.replace("{{payload}}", shlex.quote(payload))
    return raw


def _needs_shell(cmd: str) -> bool:
    tokens = ["&&", ";", "|", ">", "<", "$(", "`"]
    return any(token in cmd for token in tokens)


def _rewrite_poc_token(token: str, poc_path: str) -> str:
    entry_name = Path(poc_path).name
    if token in {entry_name, f"./{entry_name}"}:
        return poc_path
    if token.endswith(f"/{entry_name}") and not token.startswith("/tmp/"):
        return poc_path
    return token


def _load_json(path: Path) -> Dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _load_generator_contract(metadata_dir: Path) -> Dict[str, Any] | None:
    return load_resolved_contract(metadata_dir)


def _load_exploit_oracle(metadata_dir: Path) -> Dict[str, Any]:
    contract = _load_generator_contract(metadata_dir)
    oracle = contract.get("exploit_oracle") if isinstance(contract, dict) else {}
    return deepcopy(oracle) if isinstance(oracle, dict) else {}


def _normalize_oracle_negative_controls(exploit_oracle: Dict[str, Any]) -> List[Dict[str, Any]]:
    controls = exploit_oracle.get("negative_controls") if isinstance(exploit_oracle.get("negative_controls"), list) else []
    normalized: List[Dict[str, Any]] = []
    for index, entry in enumerate(controls, start=1):
        if not isinstance(entry, dict):
            continue
        payload = entry.get("payload")
        if not isinstance(payload, str) or not payload.strip():
            continue
        normalized.append(
            {
                "name": str(entry.get("name") or f"negative-{index}").strip() or f"negative-{index}",
                "payload": payload.strip(),
                "expect_success": False,
                "rationale": str(entry.get("rationale") or "").strip() or None,
            }
        )
    return normalized


def _normalize_oracle_metamorphic_cases(exploit_oracle: Dict[str, Any]) -> List[Dict[str, Any]]:
    metamorphic = exploit_oracle.get("metamorphic") if isinstance(exploit_oracle.get("metamorphic"), dict) else {}
    cases = metamorphic.get("cases") if isinstance(metamorphic.get("cases"), list) else []
    normalized: List[Dict[str, Any]] = []
    for index, entry in enumerate(cases, start=1):
        if not isinstance(entry, dict):
            continue
        payload = entry.get("payload")
        if not isinstance(payload, str) or not payload.strip():
            continue
        expect_success = entry.get("expect_success")
        normalized.append(
            {
                "name": str(entry.get("name") or f"metamorphic-{index}").strip() or f"metamorphic-{index}",
                "payload": payload.strip(),
                "expect_success": bool(expect_success) if isinstance(expect_success, bool) else True,
                "rationale": str(entry.get("rationale") or "").strip() or None,
            }
        )
    return normalized


def _oracle_positive_success(log_text: str, exit_code: int, exploit_oracle: Dict[str, Any]) -> Dict[str, Any]:
    success_signature = str(exploit_oracle.get("success_signature") or "").strip()
    flag_token = str(exploit_oracle.get("flag_token") or "").strip()
    negative_markers = [
        str(item).strip()
        for item in (exploit_oracle.get("negative_text_markers") or [])
        if isinstance(item, str) and str(item).strip()
    ]
    forbidden_markers = [
        str(item).strip()
        for item in (exploit_oracle.get("forbidden_success_markers") or [])
        if isinstance(item, str) and str(item).strip()
    ]
    assertion_program = (
        exploit_oracle.get("assertion_program")
        if isinstance(exploit_oracle.get("assertion_program"), list)
        else []
    )
    assertion_pass, assertion_outcomes = run_assertions(log_text, assertion_program)
    matched_negative_markers = [marker for marker in negative_markers if marker in log_text]
    matched_forbidden_markers = [marker for marker in forbidden_markers if marker in log_text]
    success_signature_hit = bool(success_signature and success_signature in log_text)
    flag_token_hit = bool(flag_token and flag_token in log_text)
    positive_hit = False
    if success_signature and flag_token:
        positive_hit = success_signature_hit and flag_token_hit
    elif success_signature:
        positive_hit = success_signature_hit
    elif flag_token:
        positive_hit = flag_token_hit
    elif assertion_program:
        positive_hit = assertion_pass
    positive_hit = bool(positive_hit and exit_code == 0 and not matched_forbidden_markers)
    return {
        "positive_hit": positive_hit,
        "success_signature_hit": success_signature_hit,
        "flag_token_hit": flag_token_hit,
        "assertion_program_pass": assertion_pass,
        "assertion_outcomes": [
            {
                "op": outcome.op,
                "success": outcome.success,
                "details": outcome.details,
            }
            for outcome in assertion_outcomes
        ],
        "matched_negative_markers": matched_negative_markers,
        "matched_forbidden_markers": matched_forbidden_markers,
    }


def _run_command_capture(cmd: List[str], log_path: Path) -> Dict[str, Any]:
    LOGGER.info("Running command with capture: %s", " ".join(cmd))
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    output = proc.stdout or ""
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("$ " + " ".join(cmd) + "\n")
        if output:
            handle.write(output)
            if not output.endswith("\n"):
                handle.write("\n")
    return {"returncode": proc.returncode, "output": output}


def _evaluate_oracle_case(
    *,
    name: str,
    payload: str,
    expect_success: bool,
    container_name: str,
    metadata_dir: Path,
    poc_path: str,
    base_url: str,
    poc_cmd: str | None,
    log_path: Path,
    exploit_oracle: Dict[str, Any],
) -> Dict[str, Any]:
    exec_cmd = _build_poc_exec_cmd(
        container_name,
        metadata_dir,
        poc_path,
        base_url,
        poc_cmd=poc_cmd,
        payload=payload,
    )
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n# Oracle Replay: {name} (payload={payload})\n")
    result = _run_command_capture(exec_cmd, log_path)
    analysis = _oracle_positive_success(str(result.get("output") or ""), int(result.get("returncode") or 0), exploit_oracle)
    passed = analysis["positive_hit"] if expect_success else not analysis["positive_hit"]
    return {
        "name": name,
        "payload": payload,
        "expect_success": expect_success,
        "passed": bool(passed),
        "exit_code": int(result.get("returncode") or 0),
        "success_signature_hit": bool(analysis["success_signature_hit"]),
        "flag_token_hit": bool(analysis["flag_token_hit"]),
        "assertion_program_pass": bool(analysis["assertion_program_pass"]),
        "matched_negative_markers": analysis["matched_negative_markers"],
        "matched_forbidden_markers": analysis["matched_forbidden_markers"],
        "output_excerpt": str(result.get("output") or "")[-4000:],
        "assertion_outcomes": analysis["assertion_outcomes"],
    }


def _oracle_execution_parity(negative_controls: Dict[str, Any], metamorphic: Dict[str, Any]) -> str:
    negative_attempted = bool(negative_controls.get("attempted"))
    negative_passed = negative_controls.get("passed") is True
    metamorphic_attempted = bool(metamorphic.get("attempted"))
    metamorphic_passed = metamorphic.get("passed") is True
    if negative_attempted and metamorphic_attempted and negative_passed and metamorphic_passed:
        return "high"
    if negative_attempted or metamorphic_attempted:
        return "partial"
    return "missing"


def _execute_oracle_replays(
    *,
    container_name: str,
    metadata_dir: Path,
    run_dir: Path,
    log_path: Path,
    poc_path: str,
    base_url: str,
    poc_cmd: str | None,
    success_exit_code: int,
    success_payloads: List[str | None],
) -> Dict[str, Any]:
    exploit_oracle = _load_exploit_oracle(metadata_dir)
    negative_controls = _normalize_oracle_negative_controls(exploit_oracle)
    metamorphic_cases = _normalize_oracle_metamorphic_cases(exploit_oracle)
    negative_results = [
        _evaluate_oracle_case(
            name=str(entry.get("name") or f"negative-{index}"),
            payload=str(entry.get("payload") or ""),
            expect_success=False,
            container_name=container_name,
            metadata_dir=metadata_dir,
            poc_path=poc_path,
            base_url=base_url,
            poc_cmd=poc_cmd,
            log_path=log_path,
            exploit_oracle=exploit_oracle,
        )
        for index, entry in enumerate(negative_controls, start=1)
    ]
    metamorphic_results = [
        _evaluate_oracle_case(
            name=str(entry.get("name") or f"metamorphic-{index}"),
            payload=str(entry.get("payload") or ""),
            expect_success=bool(entry.get("expect_success")),
            container_name=container_name,
            metadata_dir=metadata_dir,
            poc_path=poc_path,
            base_url=base_url,
            poc_cmd=poc_cmd,
            log_path=log_path,
            exploit_oracle=exploit_oracle,
        )
        for index, entry in enumerate(metamorphic_cases, start=1)
    ]
    forbidden_markers = [
        str(item).strip()
        for item in (exploit_oracle.get("forbidden_success_markers") or [])
        if isinstance(item, str) and str(item).strip()
    ]
    forbidden_pass = all(
        not result.get("matched_forbidden_markers")
        for result in [*negative_results, *metamorphic_results]
    )
    negative_payloads_declared = exploit_oracle.get("negative_controls") if isinstance(exploit_oracle.get("negative_controls"), list) else []
    metamorphic_payloads_declared = (
        (exploit_oracle.get("metamorphic") or {}).get("cases")
        if isinstance((exploit_oracle.get("metamorphic") or {}), dict)
        else []
    )
    payload: Dict[str, Any] = {
        "schema_version": "oracle_execution@0.1",
        "source": "executor_replay",
        "success_case": {
            "executed": True,
            "exit_code": success_exit_code,
            "payloads": [item for item in success_payloads],
        },
        "negative_controls": {
            "available": bool(negative_payloads_declared),
            "attempted": bool(negative_results),
            "total_declared": len(negative_payloads_declared) if isinstance(negative_payloads_declared, list) else 0,
            "total": len(negative_results),
            "passed": bool(negative_results) and all(result.get("passed") is True for result in negative_results),
            "results": negative_results,
        },
        "metamorphic": {
            "available": bool(metamorphic_payloads_declared),
            "attempted": bool(metamorphic_results),
            "total_declared": len(metamorphic_payloads_declared) if isinstance(metamorphic_payloads_declared, list) else 0,
            "total": len(metamorphic_results),
            "passed": bool(metamorphic_results) and all(result.get("passed") is True for result in metamorphic_results),
            "relation": str(((exploit_oracle.get("metamorphic") or {}) if isinstance(exploit_oracle.get("metamorphic"), dict) else {}).get("relation") or "").strip() or None,
            "results": metamorphic_results,
        },
        "forbidden_success": {
            "markers": forbidden_markers,
            "passed": forbidden_pass,
        },
    }
    payload["parity"] = _oracle_execution_parity(payload["negative_controls"], payload["metamorphic"])
    path = run_dir / ORACLE_EXECUTION_FILENAME
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def _sidecar_runtime_kind(entry: Dict[str, Any]) -> str | None:
    raw_candidates = [
        entry.get("type"),
        entry.get("name"),
        entry.get("image"),
    ]
    for raw in raw_candidates:
        token = str(raw or "").strip().lower()
        if not token:
            continue
        token = token.split("/")[-1]
        token = token.split(":")[0]
        if token in {"mysql", "mariadb", "postgres", "postgresql"}:
            return token
        if token.startswith("mysql"):
            return "mysql"
        if token.startswith("mariadb"):
            return "mariadb"
        if token.startswith("postgres"):
            return "postgres"
    return None


def _sql_seed_files(execution_surface: Dict[str, Any]) -> List[str]:
    normalized = _normalize_seed_files(execution_surface.get("seed_files"))
    return [item for item in normalized if item.lower().endswith(".sql")]


def _sidecar_seed_mount_target(
    entry: Dict[str, Any],
    execution_surface: Dict[str, Any],
    workspace: Path | None,
) -> str | None:
    if workspace is None:
        return None
    sidecar_name = str(entry.get("name") or "").strip().lower()
    volume_contract = execution_surface.get("volume_contract") if isinstance(execution_surface.get("volume_contract"), list) else []
    if sidecar_name and volume_contract:
        for contract_entry in volume_contract:
            if not isinstance(contract_entry, dict):
                continue
            scope = str(contract_entry.get("scope") or "").strip().lower()
            target = str(contract_entry.get("target") or "").strip()
            source = str(contract_entry.get("source") or "").strip().lower() or "workspace"
            mode = str(contract_entry.get("mode") or "").strip().lower() or "rw"
            if scope == f"sidecar:{sidecar_name}" and target.startswith("/") and source == "workspace" and mode == "ro":
                return target
    seed_strategy = str(execution_surface.get("seed_strategy") or "").strip().lower()
    if seed_strategy and seed_strategy != "sidecar_sql_apply":
        return None
    if not _sql_seed_files(execution_surface):
        return None
    if _sidecar_runtime_kind(entry) in {"mysql", "mariadb", "postgres", "postgresql"}:
        return "/seed-input"
    return None


def _should_mount_seed_input(
    entry: Dict[str, Any],
    execution_surface: Dict[str, Any],
    workspace: Path | None,
) -> bool:
    return _sidecar_seed_mount_target(entry, execution_surface, workspace) is not None


def _apply_mysql_seed_file(
    *,
    entry: Dict[str, Any],
    container_name: str,
    seed_file: str,
    seed_mount_target: str,
    execution_surface: Dict[str, Any],
    log_path: Path,
) -> None:
    env = entry.get("env") if isinstance(entry.get("env"), dict) else {}
    service_env = execution_surface.get("service_env") if isinstance(execution_surface.get("service_env"), dict) else {}
    user = str(env.get("MYSQL_USER") or service_env.get("DB_USER") or "root").strip() or "root"
    password = str(env.get("MYSQL_PASSWORD") or env.get("MYSQL_ROOT_PASSWORD") or service_env.get("DB_PASSWORD") or "").strip()
    database = str(env.get("MYSQL_DATABASE") or service_env.get("DB_NAME") or user).strip() or user
    seed_path = f"{seed_mount_target.rstrip('/')}/{seed_file}"
    parts: List[str] = []
    if password:
        parts.append(f"MYSQL_PWD={shlex.quote(password)}")
    parts.append(
        "mysql "
        f"-h {shlex.quote('127.0.0.1')} "
        f"-u {shlex.quote(user)} "
        f"{shlex.quote(database)} < {shlex.quote(seed_path)}"
    )
    run_command(
        [
            DOCKER_BIN,
            "exec",
            container_name,
            "sh",
            "-lc",
            " ".join(parts),
        ],
        log_path,
    )


def _apply_postgres_seed_file(
    *,
    entry: Dict[str, Any],
    container_name: str,
    seed_file: str,
    seed_mount_target: str,
    execution_surface: Dict[str, Any],
    log_path: Path,
) -> None:
    env = entry.get("env") if isinstance(entry.get("env"), dict) else {}
    service_env = execution_surface.get("service_env") if isinstance(execution_surface.get("service_env"), dict) else {}
    user = str(env.get("POSTGRES_USER") or service_env.get("DB_USER") or "postgres").strip() or "postgres"
    password = str(env.get("POSTGRES_PASSWORD") or service_env.get("DB_PASSWORD") or "").strip()
    database = str(env.get("POSTGRES_DB") or service_env.get("DB_NAME") or user).strip() or user
    port = str(service_env.get("DB_PORT") or env.get("POSTGRES_PORT") or "5432").strip() or "5432"
    seed_path = f"{seed_mount_target.rstrip('/')}/{seed_file}"
    parts: List[str] = []
    if password:
        parts.append(f"PGPASSWORD={shlex.quote(password)}")
    parts.append(
        "psql "
        f"-h {shlex.quote('127.0.0.1')} "
        f"-p {shlex.quote(port)} "
        f"-U {shlex.quote(user)} "
        f"-d {shlex.quote(database)} "
        f"-f {shlex.quote(seed_path)}"
    )
    run_command(
        [
            DOCKER_BIN,
            "exec",
            container_name,
            "sh",
            "-lc",
            " ".join(parts),
        ],
        log_path,
    )


def _apply_sidecar_seed_files(
    *,
    entry: Dict[str, Any],
    container_name: str,
    execution_surface: Dict[str, Any],
    workspace: Path | None,
    log_path: Path,
) -> List[str]:
    if workspace is None:
        return []
    seed_strategy = str(execution_surface.get("seed_strategy") or "").strip().lower()
    if seed_strategy and seed_strategy != "sidecar_sql_apply":
        return []
    sidecar_kind = _sidecar_runtime_kind(entry)
    if sidecar_kind not in {"mysql", "mariadb", "postgres", "postgresql"}:
        return []
    seed_mount_target = _sidecar_seed_mount_target(entry, execution_surface, workspace)
    if not seed_mount_target:
        return []
    applied: List[str] = []
    for relative_path in _sql_seed_files(execution_surface):
        if not (workspace / relative_path).exists():
            raise ExecutorError(f"Declared seed file missing during sidecar seed apply: {relative_path}")
        if sidecar_kind in {"mysql", "mariadb"}:
            _apply_mysql_seed_file(
                entry=entry,
                container_name=container_name,
                seed_file=relative_path,
                seed_mount_target=seed_mount_target,
                execution_surface=execution_surface,
                log_path=log_path,
            )
        else:
            _apply_postgres_seed_file(
                entry=entry,
                container_name=container_name,
                seed_file=relative_path,
                seed_mount_target=seed_mount_target,
                execution_surface=execution_surface,
                log_path=log_path,
            )
        applied.append(relative_path)
    return applied


def _seed_apply_observation(
    execution_surface: Dict[str, Any],
    sidecars: List[Dict[str, Any]],
) -> Dict[str, Any]:
    strategy = str(execution_surface.get("seed_strategy") or "").strip().lower()
    sql_seed_files = _sql_seed_files(execution_surface)
    attempted = bool(strategy == "sidecar_sql_apply" and sql_seed_files and sidecars)
    applied_total = 0
    seed_mount_targets: List[str] = []
    for entry in sidecars:
        applied = entry.get("seed_files_applied") if isinstance(entry, dict) and isinstance(entry.get("seed_files_applied"), list) else []
        applied_total += len(applied)
        mount_target = str(entry.get("seed_mount_target") or "").strip() if isinstance(entry, dict) else ""
        if mount_target and mount_target not in seed_mount_targets:
            seed_mount_targets.append(mount_target)
    return {
        "seed_apply_attempted": attempted,
        "seed_apply_completed": bool(attempted and applied_total > 0),
        "seed_files_applied_total": applied_total,
        "seed_mount_targets": seed_mount_targets,
    }


def _ordered_sidecars(
    sidecars_cfg: List[Dict[str, Any]],
    start_order: List[str],
) -> List[Dict[str, Any]]:
    if not sidecars_cfg or not start_order:
        return sidecars_cfg
    order_index = {
        str(name).strip(): idx
        for idx, name in enumerate(start_order)
        if isinstance(name, str) and str(name).strip()
    }
    if not order_index:
        return sidecars_cfg
    enumerated = list(enumerate(sidecars_cfg))
    enumerated.sort(
        key=lambda item: (
            order_index.get(str((item[1] or {}).get("name") or "").strip(), len(order_index)),
            item[0],
        )
    )
    return [entry for _, entry in enumerated]


def _start_sidecars(
    sid: str,
    bundle: VulnBundle,
    execution_surface: Dict[str, Any],
    workspace: Path | None,
    run_dir: Path,
    network_alias: "NetworkHandle",
) -> List[Dict[str, Any]]:
    sidecars_cfg = execution_surface.get("sidecars") or []
    sidecar_start_order = (
        execution_surface.get("sidecar_start_order")
        if isinstance(execution_surface.get("sidecar_start_order"), list)
        else []
    )
    sidecars_cfg = _ordered_sidecars(sidecars_cfg, sidecar_start_order)
    if not sidecars_cfg:
        target_sidecars_hint = execution_surface.get("target_sidecars_hint") or []
        hint_suffix = ""
        if isinstance(target_sidecars_hint, list):
            compact = [str(item).strip() for item in target_sidecars_hint if isinstance(item, str) and str(item).strip()]
            if compact:
                hint_suffix = f"; target sidecars hint={','.join(compact)}"
        raise ExecutorError(
            f"Bundle {bundle.slug} requires external DB/service, but resolved sidecar plan is empty "
            f"(executor_plan.sidecars and policy.executor.sidecars are empty{hint_suffix})"
        )
    if DOCKER_BIN is None:
        raise ExecutorError("Docker binary not available for sidecars")
    if network_alias.mode in {"none"}:
        raise ExecutorError(
            f"Bundle {bundle.slug} requires sidecars, but executor network is disabled "
            "(set policy.executor.allow_network=true and choose a non-none network_mode)"
        )
    run_log = run_dir / "run.log"
    records: List[Dict[str, str]] = []
    for order_index, entry in enumerate(sidecars_cfg, start=1):
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
        seed_mount_target = _sidecar_seed_mount_target(entry, execution_surface, workspace)
        if seed_mount_target and workspace is not None:
            cmd.extend(["-v", f"{workspace.resolve()}:{seed_mount_target}:ro"])
        env = entry.get("env") or {}
        for key, value in env.items():
            cmd.extend(["-e", f"{key}={value}"])
        aliases = entry.get("aliases") or []
        for alias in aliases:
            cmd.extend(["--network-alias", alias])
        cmd.append(image)
        run_command(cmd, run_log)
        _wait_for_sidecar(entry, container_name, run_log)
        applied_seed_files = _apply_sidecar_seed_files(
            entry=entry,
            container_name=container_name,
            execution_surface=execution_surface,
            workspace=workspace,
            log_path=run_log,
        )
        records.append(
            {
                "name": name,
                "type": str(entry.get("type") or "").strip() or None,
                "container": container_name,
                "image": image,
                "aliases": [str(alias).strip() for alias in aliases if isinstance(alias, str) and str(alias).strip()],
                "start_order_index": order_index,
                "seed_mount_target": seed_mount_target,
                "seed_files_applied": applied_seed_files,
            }
        )
    return records


def _wait_for_sidecar(entry: Dict[str, Any], container_name: str, log_path: Path) -> None:
    probe = entry.get("ready_probe") or {}
    probe_type = (probe.get("type") or "").strip().lower()
    if probe_type == "mysql":
        _probe_mysql_sidecar(entry, container_name, log_path, probe)
        return
    if probe_type == "postgres":
        _probe_postgres_sidecar(entry, container_name, log_path, probe)
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


def _probe_postgres_sidecar(
    entry: Dict[str, Any], container_name: str, log_path: Path, probe: Dict[str, Any]
) -> None:
    if DOCKER_BIN is None:
        raise ExecutorError("Docker binary not available for postgres probes")
    env = entry.get("env") or {}
    user = probe.get("user") or env.get("POSTGRES_USER") or "postgres"
    password = probe.get("password") or env.get("POSTGRES_PASSWORD") or ""
    database = probe.get("database") or env.get("POSTGRES_DB") or user
    host = probe.get("host") or "127.0.0.1"
    port = str(probe.get("port") or env.get("POSTGRES_PORT") or "5432")
    retries = int(probe.get("retries", 10))
    interval = float(probe.get("interval", 2.0))
    command = [DOCKER_BIN, "exec"]
    if password:
        command.extend(["-e", f"PGPASSWORD={password}"])
    command.extend(
        [
            container_name,
            "pg_isready",
            "-h",
            host,
            "-p",
            port,
            "-U",
            str(user),
            "-d",
            str(database),
        ]
    )
    for _ in range(1, retries + 1):
        proc = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if proc.returncode == 0:
            return
        time.sleep(interval)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"postgres readiness probe failed for {container_name}\n")
    raise ExecutorError(f"postgres sidecar did not become ready: {container_name}")


def _wait_for_app_ready(
    container_name: str,
    log_path: Path,
    *,
    port: int,
    health_path: str | None = None,
    healthchecks: Optional[List[Dict[str, Any]]] = None,
    retries: int = 10,
    delay: float = 1.5,
) -> None:
    if DOCKER_BIN is None:
        raise ExecutorError("Docker binary not available for app readiness probe")
    host = "127.0.0.1"
    urls = _app_readiness_urls(port=port, health_path=health_path, healthchecks=healthchecks)
    http_strategies: List[List[str]] = []
    for url in urls:
        http_strategies.extend(
            [
                ["sh", "-c", f"curl --max-time 1 -sS -o /dev/null {shlex.quote(url)}"],
                ["sh", "-c", f"wget -qO- --timeout=1 {shlex.quote(url)} >/dev/null"],
            ]
        )
    py_script = (
        "import socket,sys;"
        "s=socket.socket();"
        "s.settimeout(1);"
        f"s.connect(('{host}', int(sys.argv[1])));"
        "s.close()"
    )
    bash_tcp = f"cat < /dev/null > /dev/tcp/{host}/{port}"
    nc_tcp = f"nc -z -w1 {shlex.quote(host)} {port}"
    busybox_tcp = f"busybox nc -z -w1 {shlex.quote(host)} {port}"
    strategies: List[List[str]] = list(http_strategies)
    strategies.extend(
        [
        ["python", "-c", py_script, str(port)],
        ["python3", "-c", py_script, str(port)],
        ["bash", "-lc", bash_tcp],
        ["sh", "-c", nc_tcp],
        ["sh", "-c", busybox_tcp],
        ]
    )
    for attempt in range(1, retries + 1):
        for strategy in strategies:
            proc = subprocess.run(
                [DOCKER_BIN, "exec", container_name, *strategy],
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


def _app_readiness_urls(
    *,
    port: int,
    health_path: str | None,
    healthchecks: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
    host = "127.0.0.1"
    urls: List[str] = []
    for entry in healthchecks or []:
        if not isinstance(entry, dict):
            continue
        transport = str(entry.get("transport") or "").strip().lower() or "http"
        if transport not in {"http", "https"}:
            continue
        path = str(entry.get("path") or "").strip()
        if not path:
            continue
        if not path.startswith("/"):
            path = "/" + path
        probe_port = entry.get("port")
        if not isinstance(probe_port, int) or probe_port <= 0:
            probe_port = port
        candidate = f"{transport}://{host}:{probe_port}{path}"
        if candidate not in urls:
            urls.append(candidate)
    normalized_health_path = str(health_path or "").strip()
    if normalized_health_path:
        if not normalized_health_path.startswith("/"):
            normalized_health_path = "/" + normalized_health_path
        candidate = f"http://{host}:{port}{normalized_health_path}"
        if candidate not in urls:
            urls.append(candidate)
    root_url = f"http://{host}:{port}/"
    if root_url not in urls:
        urls.append(root_url)
    return urls


def _stop_sidecars(sidecars: List[Dict[str, str]]) -> None:
    if not sidecars:
        return
    for entry in reversed(sidecars):
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
        self._ephemeral_network: str | None = None
        self.mode = self._resolve_mode()

    def acquire(self, bundle: VulnBundle, policy_override: Optional[Dict[str, Any]] = None) -> NetworkHandle:
        mode = self._resolve_mode_for_policy(policy_override if isinstance(policy_override, dict) else self.policy)
        return NetworkHandle(mode)

    def release(self, handle: NetworkHandle) -> None:
        # No-op: network lifecycle is managed per executor run via close().
        # In multi-vuln mode we reuse the same network across bundles; removing
        # it after each bundle breaks subsequent docker runs.
        return

    def close(self) -> None:
        if DOCKER_BIN is None:
            return
        if not self._ephemeral_network:
            return
        subprocess.run(
            [DOCKER_BIN, "network", "rm", self._ephemeral_network],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    def _resolve_mode(self) -> str:
        return self._resolve_mode_for_policy(self.policy)

    def _resolve_mode_for_policy(self, policy: Dict[str, Any]) -> str:
        allow_network = bool(policy.get("allow_network"))
        sidecars = policy.get("sidecars") or []
        explicit_name = (policy.get("network_name") or "").strip() or None
        if not allow_network:
            return "none"
        if explicit_name:
            self._ensure_network(explicit_name)
            return explicit_name
        if any(isinstance(entry, dict) and entry.get("aliases") for entry in sidecars):
            name = f"{self.sid}-net"
            self._ephemeral_network = name
            self._ensure_network(name)
            return name
        return policy.get("network_mode") or "bridge"

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
