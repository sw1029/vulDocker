#!/usr/bin/env python3
"""End-to-end MVP SQLi loop runner."""
import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = os.environ.get("PYTHON", "python3")


def run_plan(requirement_path: Path) -> str:
    data = json.loads(requirement_path.read_text(encoding='utf-8'))
    sid = data.get('scenario_id')
    if not sid:
        raise SystemExit('scenario_id must be defined in requirement for MVP run')
    cmd = [PYTHON, str(ROOT / 'orchestrator' / 'plan.py'), '--input', str(requirement_path)]
    subprocess.run(cmd, check=True)
    return sid


def run_generator(sid: str) -> None:
    cmd = [PYTHON, str(ROOT / 'agents' / 'generator' / 'main.py'), '--sid', sid]
    subprocess.run(cmd, check=True)


def build_stage(sid: str) -> Path:
    workspace = ROOT / 'workspaces' / sid
    artifacts_dir = ROOT / 'artifacts' / sid
    build_dir = artifacts_dir / 'build'
    build_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir = build_dir / 'source_snapshot'
    if snapshot_dir.exists():
        shutil.rmtree(snapshot_dir)
    shutil.copytree(workspace, snapshot_dir)
    sbom = {
        'sid': sid,
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'components': [
            {'name': 'python', 'version': '3.x'},
            {'name': 'sqlite3', 'version': 'builtin'},
        ],
    }
    sbom_path = build_dir / 'sbom.spdx.json'
    sbom_path.write_text(json.dumps(sbom, indent=2, ensure_ascii=False), encoding='utf-8')
    return sbom_path


def run_stage(sid: str) -> Path:
    workspace = ROOT / 'workspaces' / sid
    artifacts_dir = ROOT / 'artifacts' / sid
    run_dir = artifacts_dir / 'run'
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / 'poc_log.json'
    env = os.environ.copy()
    env['PYTHONPATH'] = str(workspace / 'app') + os.pathsep + env.get('PYTHONPATH', '')
    cmd = [PYTHON, str(workspace / 'poc' / 'poc.py'), '--log', str(log_path)]
    subprocess.run(cmd, check=True, cwd=workspace, env=env)
    return log_path


def verify_stage(log_path: Path) -> bool:
    cmd = [PYTHON, str(ROOT / 'evals' / 'poc_verifier' / 'mvp_sqli.py'), '--log', str(log_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout.strip())
    if result.returncode != 0:
        print(result.stderr.strip())
        return False
    return True


def pack_stage(sid: str, sbom_path: Path, log_path: Path, verify_pass: bool) -> None:
    artifacts_dir = ROOT / 'artifacts' / sid
    reports_dir = artifacts_dir / 'reports'
    reports_dir.mkdir(parents=True, exist_ok=True)
    report = {
        'sid': sid,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'sbom': str(sbom_path),
        'poc_log': str(log_path),
        'verify_pass': verify_pass,
    }
    (reports_dir / 'summary.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"[PACK] Summary written to {reports_dir / 'summary.json'}")


def main() -> None:
    parser = argparse.ArgumentParser(description='Run MVP SQLi loop')
    parser.add_argument('--input', default='inputs/mvp_sqli.yml', help='Requirement file path')
    args = parser.parse_args()
    requirement_path = (ROOT / args.input).resolve()

    sid = run_plan(requirement_path)
    run_generator(sid)
    sbom_path = build_stage(sid)
    log_path = run_stage(sid)
    verify_pass = verify_stage(log_path)
    pack_stage(sid, sbom_path, log_path, verify_pass)
    print(f"[DONE] SID={sid} verify={verify_pass}")


if __name__ == '__main__':
    main()
