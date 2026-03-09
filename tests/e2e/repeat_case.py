"""Repeatability gate runner for E2E cases."""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # pragma: no cover - optional dependency mirrors run_case.py
    import yaml
except Exception:  # pragma: no cover
    yaml = None

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.e2e.run_case import (
    _ensure_docker_ready,
    _execute_pipeline,
    _load_case_spec,
    _load_manifest_summary,
    _materialize_runtime_assets,
    _snapshot_outputs,
    _validate_expectations,
    _write_plan,
)


def _safe_read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _load_expectations(path: Optional[Path]) -> Dict[str, Any]:
    if path is None or not path.exists():
        return {}
    data = _safe_read_json(path)
    return data if isinstance(data, dict) else {}


def _load_latest_generator_failure(metadata_root: Path) -> Dict[str, Any]:
    candidate_paths = [metadata_root / "generator_failures.jsonl"]
    bundles_dir = metadata_root / "bundles"
    if bundles_dir.exists():
        candidate_paths.extend(sorted(bundles_dir.glob("*/generator_failures.jsonl")))
    latest: Dict[str, Any] = {}
    latest_ts = ""
    for path in candidate_paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            timestamp = str(payload.get("timestamp") or "")
            if timestamp >= latest_ts:
                latest = dict(payload)
                latest_ts = timestamp
                latest["_failure_path"] = str(path)
    return latest


def _load_loop_tail(metadata_root: Path) -> Dict[str, Any]:
    payload = _safe_read_json(metadata_root / "loop_state.json")
    history = payload.get("history")
    if not isinstance(history, list) or not history:
        return {}
    tail = history[-1]
    return tail if isinstance(tail, dict) else {}


def _infer_failure_stage(error: str, loop_tail: Dict[str, Any], latest_failure: Dict[str, Any]) -> str:
    stage = str(latest_failure.get("stage") or "").strip()
    if stage:
        return stage
    if isinstance(loop_tail, dict) and loop_tail.get("success") is False:
        stage = str(loop_tail.get("stage") or "").strip()
        if stage:
            return stage
    lowered = str(error or "").strip().lower()
    markers = [
        ("agents/researcher/main.py", "RESEARCH"),
        ("agents/generator/main.py", "GENERATOR"),
        ("executor/runtime/docker_local.py", "EXECUTOR"),
        ("evals/poc_verifier/main.py", "VERIFY"),
        ("agents/reviewer/main.py", "REVIEW"),
        ("orchestrator/pack.py", "PACK"),
    ]
    for marker, inferred in markers:
        if marker in lowered:
            return inferred
    return ""


def summarize_repeat_attempt(
    *,
    attempt: int,
    sid: str,
    summary: Dict[str, Any],
    error: str,
    latest_failure: Dict[str, Any],
    loop_tail: Dict[str, Any],
    attempt_dir: Path,
) -> Dict[str, Any]:
    success = not error
    bundles = summary.get("bundles") if isinstance(summary.get("bundles"), list) else []
    reviewer = summary.get("reviewer") if isinstance(summary.get("reviewer"), dict) else {}
    guard_mismatches: List[Dict[str, Any]] = []
    for bundle in bundles:
        if not isinstance(bundle, dict):
            continue
        evidence = str(bundle.get("evidence") or "")
        if "guard mismatch:" not in evidence.lower():
            continue
        guard_mismatches.append(
            {
                "slug": bundle.get("slug"),
                "vuln_id": bundle.get("vuln_id"),
                "evidence": evidence,
            }
        )
    if not guard_mismatches:
        violations = latest_failure.get("guard_violations")
        if isinstance(violations, list) and violations:
            guard_mismatches.append(
                {
                    "slug": latest_failure.get("slug"),
                    "vuln_id": latest_failure.get("vuln_id"),
                    "evidence": "; ".join(str(item) for item in violations if item),
                }
            )

    has_failure_signal = bool(error) or bool(latest_failure)
    failure_stage = _infer_failure_stage(error, loop_tail, latest_failure) if has_failure_signal else ""
    failure_fingerprint = str(latest_failure.get("failure_fingerprint") or "").strip() if has_failure_signal else ""
    guard_error_code = str(latest_failure.get("guard_error_code") or "").strip() if has_failure_signal else ""
    return {
        "attempt": attempt,
        "sid": sid,
        "success": success,
        "overall_pass": summary.get("overall_pass"),
        "failure_stage": failure_stage or None,
        "failure_fingerprint": failure_fingerprint or None,
        "guard_error_code": guard_error_code or None,
        "blocking_bundles": reviewer.get("blocking_bundles") or [],
        "guard_mismatches": guard_mismatches,
        "bundles": bundles,
        "latest_failure": latest_failure or None,
        "loop_tail": loop_tail or None,
        "error": error or None,
        "output_dir": str(attempt_dir),
        "summary_path": str(attempt_dir / "summary.json") if (attempt_dir / "summary.json").exists() else None,
    }


def aggregate_repeat_results(case_name: str, attempts: List[Dict[str, Any]]) -> Dict[str, Any]:
    fingerprint_counts = Counter(
        str(item.get("failure_fingerprint") or "").strip()
        for item in attempts
        if str(item.get("failure_fingerprint") or "").strip()
    )
    stage_counts = Counter(
        str(item.get("failure_stage") or "").strip()
        for item in attempts
        if str(item.get("failure_stage") or "").strip()
    )
    guard_error_counts = Counter(
        str(item.get("guard_error_code") or "").strip()
        for item in attempts
        if str(item.get("guard_error_code") or "").strip()
    )
    report = {
        "case": case_name,
        "attempt_count": len(attempts),
        "success_count": sum(1 for item in attempts if item.get("success")),
        "failure_count": sum(1 for item in attempts if not item.get("success")),
        "passed": all(bool(item.get("success")) for item in attempts) if attempts else False,
        "failure_fingerprints": [
            {"fingerprint": fingerprint, "count": count}
            for fingerprint, count in sorted(fingerprint_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "failure_stages": [
            {"stage": stage, "count": count}
            for stage, count in sorted(stage_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "guard_error_codes": [
            {"guard_error_code": code, "count": count}
            for code, count in sorted(guard_error_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "attempts": attempts,
    }
    return report


def _write_attempt_summary(attempt_dir: Path, summary: Dict[str, Any], resolved_requirement: Dict[str, Any]) -> None:
    if not summary:
        return
    attempt_dir.mkdir(parents=True, exist_ok=True)
    (attempt_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    if yaml is not None:
        (attempt_dir / "requirement.resolved.yml").write_text(
            yaml.safe_dump(resolved_requirement, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )


def _build_attempt_env(sid: str, custom_env: Dict[str, Any]) -> Dict[str, str]:
    env = os.environ.copy()
    env["SID"] = sid
    for key, value in custom_env.items():
        env[str(key)] = str(value)
    return env


def execute_repeat_gate(
    case_dir: Path,
    *,
    attempts: int,
    mode: str,
    snapshot: bool,
    output_dir: Path,
    requirement_path: Optional[Path] = None,
    expectations_path: Optional[Path] = None,
) -> Dict[str, Any]:
    case_spec = _load_case_spec(case_dir, requirement_path)
    expectations = _load_expectations(expectations_path or (case_dir / "expectations.json"))
    output_dir.mkdir(parents=True, exist_ok=True)
    attempt_reports: List[Dict[str, Any]] = []

    for attempt_index in range(1, max(1, attempts) + 1):
        plan = _write_plan(
            case_spec.requirement,
            multi_vuln_opt_in=bool(case_spec.options.get("multi_vuln_opt_in", False)),
        )
        sid = plan["sid"]
        env = _build_attempt_env(sid, case_spec.options.get("env") or {})
        metadata_root = REPO_ROOT / "metadata" / sid
        summary: Dict[str, Any] = {}
        error = ""
        pipeline_returncode: Optional[int] = None
        attempt_dir = output_dir / f"attempt-{attempt_index:02d}"
        attempt_dir.mkdir(parents=True, exist_ok=True)

        try:
            _materialize_runtime_assets(sid, case_spec.runtime_assets)
            _ensure_docker_ready(env)
            proc = _execute_pipeline(sid, mode, env)
            pipeline_returncode = int(proc.returncode)
            summary = _load_manifest_summary(sid, pipeline_returncode=pipeline_returncode)
            if expectations:
                _validate_expectations(summary, expectations)
        except Exception as exc:  # pragma: no cover - exercised in live E2E only
            error = f"{type(exc).__name__}: {exc}"
            try:
                summary = _load_manifest_summary(sid, pipeline_returncode=pipeline_returncode)
            except Exception:
                summary = {}
        finally:
            _write_attempt_summary(attempt_dir, summary, plan.get("requirement", case_spec.requirement))
            if snapshot:
                _snapshot_outputs(sid, attempt_dir)

        latest_failure = _load_latest_generator_failure(metadata_root)
        loop_tail = _load_loop_tail(metadata_root)
        attempt_report = summarize_repeat_attempt(
            attempt=attempt_index,
            sid=sid,
            summary=summary,
            error=error,
            latest_failure=latest_failure,
            loop_tail=loop_tail,
            attempt_dir=attempt_dir,
        )
        (attempt_dir / "attempt.json").write_text(
            json.dumps(attempt_report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        attempt_reports.append(attempt_report)

    report = aggregate_repeat_results(case_dir.name, attempt_reports)
    report_path = output_dir / "repeatability_report.json"
    report["report_path"] = str(report_path)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an E2E case repeatedly and aggregate failures")
    parser.add_argument("--case", type=Path, required=True, help="Path to the case directory")
    parser.add_argument("--attempts", type=int, default=3, help="Number of repeated attempts")
    parser.add_argument("--mode", default="deterministic", help="LLM decoding mode")
    parser.add_argument("--requirement", type=Path, help="Override requirement YAML path")
    parser.add_argument("--expectations", type=Path, help="Override expectations JSON path")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory to store repeatability outputs")
    parser.add_argument("--no-snapshot", action="store_true", help="Skip copying metadata/artifacts snapshots")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    case_dir = args.case.resolve()
    if not case_dir.exists():
        raise SystemExit(f"case directory not found: {case_dir}")
    report = execute_repeat_gate(
        case_dir,
        attempts=max(1, int(args.attempts)),
        mode=args.mode,
        snapshot=not args.no_snapshot,
        output_dir=args.output_dir.resolve(),
        requirement_path=args.requirement.resolve() if args.requirement else None,
        expectations_path=args.expectations.resolve() if args.expectations else None,
    )
    print(f"[E2E] Repeatability report written to {report['report_path']}")
    if not report.get("passed"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
