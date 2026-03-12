"""Researcher agent entry point."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.researcher import ResearcherService
from common.contracts import (
    can_resolve_without_remote_research_for_requirement,
    load_semantic_profile,
    requires_semantic_support,
)
from common.logging import get_logger
from common.paths import ensure_dir, get_metadata_dir
from common.plan import load_plan
from common.run_matrix import bundle_requirement, load_vuln_bundles

LOGGER = get_logger(__name__)


def _name_only_mode(policy: dict[str, object] | object) -> str:
    if not isinstance(policy, dict):
        return "compatibility"
    token = str(policy.get("name_only_mode") or "").strip().lower()
    if token in {"dynamic", "strict_dynamic"}:
        return token
    return "compatibility"


def _preseeded_semantic_fail_closed_reason(bundle, profile: dict[str, object]) -> tuple[str, str] | None:
    vuln_id = str(getattr(bundle, "vuln_id", "") or "").strip()
    if not vuln_id or not vuln_id.upper().startswith("NAME-"):
        return None
    if not requires_semantic_support(vuln_id):
        return None
    support_level = str(profile.get("support_level") or "").strip().lower()
    compiler_supported = profile.get("compiler_supported")
    if support_level != "unsupported" or compiler_supported is not False:
        return None
    compiler_reason = str(profile.get("compiler_reason") or "").strip()
    reason = (
        f"Semantic profile marks unsupported free-form family before generation: "
        f"{bundle.slug} ({vuln_id}) support_level={support_level}"
    )
    if compiler_reason:
        reason += f", compiler_reason={compiler_reason}"
    fix_hint = "Add compiler-backed support for this family or keep the request in inspection-only / negative regression mode."
    return reason, fix_hint


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Researcher agent")
    parser.add_argument("--sid", required=True, help="Scenario ID to research")
    parser.add_argument("--mode", default="deterministic", help="Decoding profile override")
    parser.add_argument("--search-limit", type=int, default=3, help="Results per query")
    return parser.parse_args()


def _should_skip_bundle_research(
    *,
    plan: dict[str, object],
    requirement_view: dict[str, object],
    bundle,
    force_run: bool,
) -> bool:
    if force_run:
        return False
    plan_policy = plan.get("policy") if isinstance(plan, dict) else {}
    bundle_policy = requirement_view.get("policy") if isinstance(requirement_view.get("policy"), dict) else {}
    effective_policy = bundle_policy if isinstance(bundle_policy, dict) and bundle_policy else plan_policy
    request_identity = (
        requirement_view.get("request_identity")
        if isinstance(requirement_view.get("request_identity"), dict)
        else {}
    )
    name_driven = bool((request_identity or {}).get("name_driven")) or str(getattr(bundle, "vuln_id", "") or "").upper().startswith("NAME-")
    mode = _name_only_mode(effective_policy)
    dynamic_eval = bool(effective_policy.get("dynamic_eval")) if isinstance(effective_policy, dict) else False
    open_world_strict = bool(effective_policy.get("open_world_strict")) if isinstance(effective_policy, dict) else False
    if name_driven and mode in {"dynamic", "strict_dynamic"}:
        dynamic_eval = True
    if name_driven and mode == "strict_dynamic":
        open_world_strict = True
    if dynamic_eval:
        return False
    if open_world_strict and name_driven:
        return False
    return can_resolve_without_remote_research_for_requirement(bundle.vuln_id, requirement_view)


def main() -> None:
    args = parse_args()
    plan = load_plan(args.sid)
    bundles = load_vuln_bundles(plan)
    reports = []
    had_failure = False
    requirement = plan.get("requirement") if isinstance(plan, dict) else {}
    researcher_cfg = requirement.get("researcher") if isinstance(requirement, dict) else {}
    force_run = bool((researcher_cfg or {}).get("force_run")) if isinstance(researcher_cfg, dict) else False
    for bundle in bundles:
        service = ResearcherService(
            args.sid,
            mode=args.mode,
            search_limit=args.search_limit,
            plan=plan,
            bundle=bundle,
        )
        requirement_view = bundle_requirement(requirement, bundle) if isinstance(requirement, dict) else {}
        semantic_profile = load_semantic_profile(service.metadata_dir) or {}
        fail_closed = (
            _preseeded_semantic_fail_closed_reason(bundle, semantic_profile)
            if isinstance(semantic_profile, dict)
            else None
        )
        if fail_closed is not None:
            had_failure = True
            reason, fix_hint = fail_closed
            path = service.write_fail_closed_report(
                reason=reason,
                terminal_failure_class="semantic_support_missing",
                fix_hint=fix_hint,
            )
            reports.append(
                {
                    "vuln_id": bundle.vuln_id,
                    "slug": bundle.slug,
                    "report_path": str(path),
                    "status": "failed",
                    "error": reason,
                }
            )
            LOGGER.info("Researcher fail-closed for %s (%s): %s", args.sid, bundle.vuln_id, reason)
            continue
        if _should_skip_bundle_research(
            plan=plan,
            requirement_view=requirement_view,
            bundle=bundle,
            force_run=force_run,
        ):
            reason = "researcher skipped: compiler/static supported bundle"
            path = service.write_skip_report(reason)
            reports.append(
                {
                    "vuln_id": bundle.vuln_id,
                    "slug": bundle.slug,
                    "report_path": str(path),
                    "status": "skipped",
                    "error": None,
                }
            )
            LOGGER.info("Researcher skipped for %s (%s)", args.sid, bundle.vuln_id)
            continue
        try:
            path = service.run()
        except Exception as exc:
            had_failure = True
            path = service.metadata_dir / "researcher_report.json"
            LOGGER.error("Researcher failed for %s (%s): %s", args.sid, bundle.vuln_id, exc)
            reports.append(
                {
                    "vuln_id": bundle.vuln_id,
                    "slug": bundle.slug,
                    "report_path": str(path) if path.exists() else None,
                    "status": "failed",
                    "error": str(exc),
                }
            )
            continue
        reports.append(
            {
                "vuln_id": bundle.vuln_id,
                "slug": bundle.slug,
                "report_path": str(path),
                "status": "success",
                "error": None,
            }
        )
        LOGGER.info("Researcher finished for %s (%s)", args.sid, bundle.vuln_id)
    _write_index(args.sid, reports)
    if had_failure:
        raise SystemExit(1)


def _write_index(sid: str, reports: list[dict]) -> None:
    metadata_dir = ensure_dir(get_metadata_dir(sid))
    index_path = metadata_dir / "researcher_reports.json"
    payload = {"sid": sid, "reports": reports}
    index_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    LOGGER.info("Researcher index updated at %s", index_path)


if __name__ == "__main__":
    main()
