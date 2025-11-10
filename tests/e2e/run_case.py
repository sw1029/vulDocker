"""선언형 E2E 회귀 케이스를 실행하는 도우미.

각 케이스 디렉터리는 요구 블루프린트, 선택적 런타임 자산(규칙/템플릿),
검증·리뷰 기대치를 정의한다. 이 실행기는 해당 요구를 실체화한 뒤
전체 파이프라인(`plan -> researcher -> generator -> executor -> verifier -> reviewer -> pack`)
을 수행하고, 생성된 manifest를 기대치와 비교한다.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:  # pragma: no cover - YAML 모듈 부재 시 JSON으로 대체
    import yaml
except Exception:  # pragma: no cover
    yaml = None

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.schema import normalize_requirement
from orchestrator import plan as plan_module


class CaseError(RuntimeError):
    """케이스 정의나 실행이 실패했을 때 사용하는 예외."""


@dataclass
class CaseSpec:
    name: str
    requirement: Dict[str, Any]
    runtime_assets: Dict[str, List[Path]]
    options: Dict[str, Any]


def _read_yaml(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise CaseError("PyYAML is required to load requirement blueprints")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # pragma: no cover - YAML 파서 상세 예외
        raise CaseError(f"failed to parse YAML: {path}") from exc


def _deep_merge(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_case_spec(case_dir: Path, requirement_path: Optional[Path] = None) -> CaseSpec:
    spec_path = requirement_path or (case_dir / "requirement.yml")
    if not spec_path.exists():
        raise CaseError(f"case requirement not found: {spec_path}")
    raw = _read_yaml(spec_path)
    runtime_assets = raw.pop("runtime_assets", {}) or {}
    options = raw.pop("options", {}) or {}
    requirement: Dict[str, Any]
    if "base_requirement" in raw or "overrides" in raw:
        base_path_value = raw.get("base_requirement")
        if not base_path_value:
            raise CaseError("'base_requirement' must be provided when overrides are present")
        base_path = (REPO_ROOT / str(base_path_value)).resolve()
        if not base_path.exists():
            raise CaseError(f"base requirement does not exist: {base_path}")
        base_payload = _read_yaml(base_path)
        overrides = raw.get("overrides", {}) or {}
        requirement = _deep_merge(base_payload, overrides)
    else:
        requirement = raw
    normalized_assets: Dict[str, List[Path]] = {}
    for key in ("rules", "templates"):
        entries = runtime_assets.get(key) or []
        resolved: List[Path] = []
        for entry in entries:
            candidate = (REPO_ROOT / str(entry)).resolve()
            if not candidate.exists():
                raise CaseError(f"runtime asset missing: {candidate}")
            resolved.append(candidate)
        if resolved:
            normalized_assets[key] = resolved
    return CaseSpec(name=case_dir.name, requirement=requirement, runtime_assets=normalized_assets, options=options)


def _cleanup_sid_dirs(sid: str) -> None:
    for root_name in ("metadata", "artifacts", "workspaces"):
        target = REPO_ROOT / root_name / sid
        if target.exists():
            shutil.rmtree(target)


def _write_plan(requirement: Dict[str, Any], *, multi_vuln_opt_in: bool) -> Dict[str, Any]:
    normalization = normalize_requirement(requirement, multi_vuln_opt_in=multi_vuln_opt_in)
    plan = plan_module.build_plan(normalization)
    sid = plan["sid"]
    _cleanup_sid_dirs(sid)
    plan_module.write_plan(plan)
    return plan


def _copy_asset(source: Path, destination_dir: Path) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination_dir / source.name, dirs_exist_ok=True)
    else:
        shutil.copy2(source, destination_dir / source.name)


def _materialize_runtime_assets(sid: str, runtime_assets: Dict[str, List[Path]]) -> None:
    if not runtime_assets:
        return
    metadata_root = REPO_ROOT / "metadata" / sid
    for kind, entries in runtime_assets.items():
        if kind == "rules":
            dest_root = metadata_root / "runtime_rules"
        elif kind == "templates":
            dest_root = metadata_root / "runtime_templates"
        else:
            continue
        for entry in entries:
            _copy_asset(entry, dest_root)


def _ensure_docker_ready(env: Dict[str, str]) -> None:
    if os.environ.get("VULD_E2E_SKIP_DOCKER_CHECK"):
        return
    if shutil.which("docker") is None:
        raise CaseError("docker binary not found in PATH")
    try:
        subprocess.run(["docker", "info"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    except subprocess.CalledProcessError as exc:
        raise CaseError("docker daemon is not reachable") from exc


def _run_command(command: Sequence[str], env: Dict[str, str]) -> None:
    subprocess.run(command, cwd=REPO_ROOT, env=env, check=True)


def _execute_pipeline(sid: str, mode: str, env: Dict[str, str]) -> None:
    steps = [
        [sys.executable, "agents/researcher/main.py", "--sid", sid, "--mode", mode],
        [sys.executable, "agents/generator/main.py", "--sid", sid, "--mode", mode],
        [sys.executable, "executor/runtime/docker_local.py", "--sid", sid, "--build"],
        [sys.executable, "executor/runtime/docker_local.py", "--sid", sid, "--run"],
        [sys.executable, "evals/poc_verifier/main.py", "--sid", sid],
        [sys.executable, "agents/reviewer/main.py", "--sid", sid, "--mode", mode],
        [sys.executable, "evals/diversity_metrics.py", "--sid", sid],
    ]
    for step in steps:
        _run_command(step, env)
    plan_path = REPO_ROOT / "metadata" / sid / "plan.json"
    allow_intentional = False
    if plan_path.exists():
        try:
            plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
            allow_intentional = bool((plan_data.get("policy") or {}).get("allow_intentional_vuln"))
        except json.JSONDecodeError:  # pragma: no cover - plan 파일은 정상이어야 함
            allow_intentional = False
    pack_cmd = [sys.executable, "orchestrator/pack.py", "--sid", sid]
    if allow_intentional:
        pack_cmd.append("--allow-intentional-vuln")
    _run_command(pack_cmd, env)


def _load_manifest_summary(sid: str) -> Dict[str, Any]:
    manifest_path = REPO_ROOT / "metadata" / sid / "manifest.json"
    if not manifest_path.exists():
        raise CaseError(f"manifest not found for SID {sid}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    reports = (manifest.get("reports") or {}).get("evals") or {}
    reviewer_path = REPO_ROOT / "metadata" / sid / "reviewer_report.json"
    reviewer = json.loads(reviewer_path.read_text(encoding="utf-8")) if reviewer_path.exists() else {}
    bundles: List[Dict[str, Any]] = []
    for bundle in manifest.get("bundles", []):
        artifacts = bundle.get("artifacts") or {}
        eval_result = artifacts.get("eval_result") or {}
        run_summary = artifacts.get("run_summary") or {}
        bundles.append(
            {
                "slug": bundle.get("slug"),
                "vuln_id": bundle.get("vuln_id"),
                "verify_pass": eval_result.get("verify_pass"),
                "evidence": eval_result.get("evidence") or "",
                "run_passed": run_summary.get("run_passed"),
                "exit_code": run_summary.get("exit_code"),
                "run_log": run_summary.get("run_log"),
                "rule": eval_result.get("rule"),
            }
        )
    return {
        "sid": sid,
        "overall_pass": reports.get("overall_pass"),
        "bundles": bundles,
        "reviewer": {
            "blocking_bundles": reviewer.get("blocking_bundles") or [],
            "issues_sample": reviewer.get("issues_sample") or [],
        },
        "manifest_path": str(manifest_path),
        "reviewer_path": str(reviewer_path) if reviewer_path.exists() else None,
    }


def _bundle_index(summary: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    for bundle in summary.get("bundles", []):
        slug = (bundle.get("slug") or "").lower()
        if slug:
            index[slug] = bundle
        vuln = (bundle.get("vuln_id") or "").lower()
        if vuln and vuln not in index:
            index[vuln] = bundle
    return index


def _validate_expectations(summary: Dict[str, Any], expectations: Dict[str, Any]) -> None:
    errors: List[str] = []
    manifest_expect = expectations.get("manifest") or {}
    if "overall_pass" in manifest_expect:
        actual = bool(summary.get("overall_pass"))
        if actual != bool(manifest_expect["overall_pass"]):
            errors.append(
                f"overall_pass expected {manifest_expect['overall_pass']!r} but observed {summary.get('overall_pass')!r}"
            )
    bundle_index = _bundle_index(summary)
    for entry in expectations.get("evals", []):
        key = (entry.get("slug") or entry.get("vuln_id") or "").lower()
        if not key or key not in bundle_index:
            errors.append(f"missing bundle entry for expectation: {entry}")
            continue
        bundle = bundle_index[key]
        if "verify_pass" in entry and bool(bundle.get("verify_pass")) != bool(entry["verify_pass"]):
            errors.append(
                f"bundle {bundle['slug']}: verify_pass expected {entry['verify_pass']} but was {bundle.get('verify_pass')}"
            )
        if "run_passed" in entry and bool(bundle.get("run_passed")) != bool(entry["run_passed"]):
            errors.append(
                f"bundle {bundle['slug']}: run_passed expected {entry['run_passed']} but was {bundle.get('run_passed')}"
            )
        if "exit_code" in entry and bundle.get("exit_code") != entry["exit_code"]:
            errors.append(
                f"bundle {bundle['slug']}: exit_code expected {entry['exit_code']} but was {bundle.get('exit_code')}"
            )
        evidence = bundle.get("evidence") or ""
        for token in entry.get("evidence_contains", []):
            if token not in evidence:
                errors.append(f"bundle {bundle['slug']}: evidence missing substring '{token}'")
    reviewer_expect = expectations.get("reviewer") or {}
    reviewer = summary.get("reviewer") or {}
    if "blocking_bundles" in reviewer_expect:
        expected = sorted(reviewer_expect.get("blocking_bundles") or [])
        actual = sorted(reviewer.get("blocking_bundles") or [])
        if actual != expected:
            errors.append(f"blocking bundles mismatch. expected={expected}, actual={actual}")
    snippets = reviewer_expect.get("issue_snippets") or []
    if snippets:
        issues = reviewer.get("issues_sample") or []
        texts = [issue.get("issue", "") for issue in issues]
        for snippet in snippets:
            if not any(snippet in text for text in texts):
                errors.append(f"reviewer issues missing snippet '{snippet}'")
    if errors:
        raise CaseError("; ".join(errors))


def _write_summary(summary: Dict[str, Any], requirement: Dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    if yaml is not None:
        (output_dir / "requirement.resolved.yml").write_text(
            yaml.safe_dump(requirement, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
    return summary_path


def _snapshot_outputs(sid: str, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for root_name in ("metadata", "artifacts"):
        source = REPO_ROOT / root_name / sid
        if not source.exists():
            continue
        target = destination / root_name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target, dirs_exist_ok=True)


def execute_case(case_dir: Path, *, requirement_path: Optional[Path], expectations_path: Optional[Path], mode: str, snapshot: bool, output_dir: Optional[Path]) -> Dict[str, Any]:
    case_spec = _load_case_spec(case_dir, requirement_path)
    plan = _write_plan(case_spec.requirement, multi_vuln_opt_in=bool(case_spec.options.get("multi_vuln_opt_in", False)))
    sid = plan["sid"]
    env = os.environ.copy()
    env["SID"] = sid
    custom_env = case_spec.options.get("env") or {}
    for key, value in custom_env.items():
        env[str(key)] = str(value)
    _materialize_runtime_assets(sid, case_spec.runtime_assets)
    _ensure_docker_ready(env)
    _execute_pipeline(sid, mode, env)
    summary = _load_manifest_summary(sid)
    destination = output_dir or (case_dir / "outputs" / sid)
    summary_path = _write_summary(summary, plan.get("requirement", case_spec.requirement), destination)
    if snapshot:
        _snapshot_outputs(sid, destination)
    expectations_data: Optional[Dict[str, Any]] = None
    resolved_expectations_path = expectations_path or (case_dir / "expectations.json")
    if resolved_expectations_path and resolved_expectations_path.exists():
        expectations_data = json.loads(resolved_expectations_path.read_text(encoding="utf-8"))
        _validate_expectations(summary, expectations_data)
    print(f"[E2E] Summary written to {summary_path}")
    if expectations_data:
        print(f"[E2E] Expectations satisfied for {case_spec.name}")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a single E2E case")
    parser.add_argument("--case", type=Path, required=True, help="Path to the case directory")
    parser.add_argument("--mode", default="deterministic", help="LLM decoding mode (deterministic|diverse)")
    parser.add_argument("--requirement", type=Path, help="Override requirement YAML path")
    parser.add_argument("--expectations", type=Path, help="Override expectations JSON path")
    parser.add_argument("--output-dir", type=Path, help="Directory to store summary/snapshots")
    parser.add_argument("--no-snapshot", action="store_true", help="Skip copying metadata/artifacts to the outputs directory")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    case_dir = args.case.resolve()
    if not case_dir.exists():
        raise SystemExit(f"case directory not found: {case_dir}")
    snapshot = not args.no_snapshot
    try:
        execute_case(
            case_dir,
            requirement_path=args.requirement.resolve() if args.requirement else None,
            expectations_path=args.expectations.resolve() if args.expectations else None,
            mode=args.mode,
            snapshot=snapshot,
            output_dir=args.output_dir.resolve() if args.output_dir else None,
        )
    except CaseError as exc:
        print(f"[E2E] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
