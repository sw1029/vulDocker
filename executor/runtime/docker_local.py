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
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.logging import get_logger
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

LOGGER = get_logger(__name__)
DOCKER_BIN = shutil.which("docker")
SYFT_BIN = shutil.which("syft")
DEFAULT_APP_PORT = 5000
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
    service_port = _resolve_service_port(metadata_dir, workspace)
    base_url = _resolve_base_url(executor_policy, service_port)
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
        image_tag,
    ]
    last_exit_code = None
    try:
        run_command(start_cmd, run_log)
        time.sleep(1)
        logs_cmd = [DOCKER_BIN, "logs", container_name]
        try:
            _wait_for_app_ready(container_name, run_log, port=service_port)
        except ExecutorError:
            run_command(logs_cmd, run_log, check=False)
            raise
        try:
            poc_container_path = _push_poc_script(
                workspace,
                metadata_dir,
                container_name,
                run_log,
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
        run_command(logs_cmd, run_log, check=False)
        return last_exit_code if last_exit_code is not None else 0
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
        "service_port": None,
        "service_base_url": None,
        "poc_cmd": None,
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
            service_port = _resolve_service_port(metadata_dir_for_bundle(plan, bundle), workspace)
            summary["service_port"] = service_port
            summary["service_base_url"] = _resolve_base_url(executor_policy, service_port)
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
                metadata_dir_for_bundle(plan, bundle),
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


def _resolve_base_url(executor_policy: Dict[str, Any], port: int) -> str:
    """Resolve base URL for PoC scripts executed *inside* the container."""
    override = (executor_policy or {}).get("base_url")
    if isinstance(override, str) and override.strip():
        return override.strip()
    return f"http://127.0.0.1:{port}"


def _resolve_service_port(metadata_dir: Path, workspace: Path) -> int:
    """Resolve service port from generator metadata, manifest, or Dockerfile."""
    contract = _load_generator_contract(metadata_dir)
    if isinstance(contract, dict):
        try:
            value = int(contract.get("service_port"))
        except Exception:
            value = None
        if value:
            return value
    port = _port_from_generator_template(metadata_dir)
    if port:
        return port
    port = _port_from_generator_manifest(metadata_dir)
    if port:
        return port
    port = _port_from_dockerfile(workspace)
    if port:
        return port
    return DEFAULT_APP_PORT


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
    contract = _load_generator_contract(metadata_dir)
    if isinstance(contract, dict):
        poc_entry = contract.get("poc_entry")
        if isinstance(poc_entry, str) and poc_entry.strip():
            return poc_entry.strip()
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
                        return path.strip()
    template = _load_json(metadata_dir / "generator_template.json")
    if isinstance(template, dict):
        poc_entry = template.get("poc_entry")
        if isinstance(poc_entry, str) and poc_entry.strip():
            return poc_entry.strip()
    return "poc.py"


def _push_poc_script(
    workspace: Path,
    metadata_dir: Path,
    container_name: str,
    log_path: Path,
    *,
    executor_policy: Dict[str, Any] | None = None,
) -> str:
    if DOCKER_BIN is None:
        raise ExecutorError("Docker binary not available for copying PoC script")
    rel = _resolve_poc_entry_relpath(metadata_dir)
    rel_path = Path(rel)
    if rel_path.is_absolute() or ".." in rel_path.parts:
        raise ExecutorError(f"Invalid poc_entry path: {rel}")
    source_path = workspace / rel_path
    if not source_path.exists():
        raise ExecutorError(f"PoC script missing at {source_path}")
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
    payload: str | None,
) -> List[str]:
    exec_prefix = [DOCKER_BIN, "exec", "-w", "/app", "-e", "PYTHONPATH=/app", container_name]
    cmd = _resolve_poc_cmd(metadata_dir)
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
        if payload is not None and "{{payload}}" in token:
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
    contract = _load_generator_contract(metadata_dir)
    if isinstance(contract, dict):
        cmd = contract.get("poc_cmd")
        if isinstance(cmd, str) and cmd.strip():
            return cmd.strip()
    payload = _load_json(metadata_dir / "generator_manifest.json")
    if isinstance(payload, dict):
        manifest = payload.get("manifest")
        if isinstance(manifest, dict):
            poc = manifest.get("poc")
            if isinstance(poc, dict):
                cmd = poc.get("cmd")
                if isinstance(cmd, str) and cmd.strip():
                    return cmd.strip()
    return None


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


def _wait_for_app_ready(
    container_name: str,
    log_path: Path,
    *,
    port: int,
    retries: int = 10,
    delay: float = 1.5,
) -> None:
    if DOCKER_BIN is None:
        raise ExecutorError("Docker binary not available for app readiness probe")
    host = "127.0.0.1"
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
    url = f"http://{host}:{port}/"
    curl_http = f"curl --max-time 1 -sS -o /dev/null {shlex.quote(url)}"
    wget_http = f"wget -qO- --timeout=1 {shlex.quote(url)} >/dev/null"
    strategies: List[List[str]] = [
        ["python", "-c", py_script, str(port)],
        ["python3", "-c", py_script, str(port)],
        ["bash", "-lc", bash_tcp],
        ["sh", "-c", nc_tcp],
        ["sh", "-c", busybox_tcp],
        ["sh", "-c", curl_http],
        ["sh", "-c", wget_http],
    ]
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
        self._ephemeral_network: str | None = None
        self.mode = self._resolve_mode()

    def acquire(self, bundle: VulnBundle) -> NetworkHandle:
        return NetworkHandle(self.mode)

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
        if not self.allow_network:
            return "none"
        if self.explicit_name:
            self._ensure_network(self.explicit_name)
            return self.explicit_name
        if any(entry.get("aliases") for entry in self.sidecars):
            name = f"{self.sid}-net"
            self._ephemeral_network = name
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
