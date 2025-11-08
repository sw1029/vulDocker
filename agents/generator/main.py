"""Generator agent entry point for TODO 13 MVP."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Dict

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.config import get_decoding_profile
from common.llm import LLMClient
from common.logging import get_logger
from common.paths import ensure_dir, get_metadata_dir, get_workspace_dir
from common.prompts import build_generator_prompt
from rag import load_static_context

from agents.generator import templates

LOGGER = get_logger(__name__)


def load_plan(sid: str) -> Dict[str, object]:
    plan_path = get_metadata_dir(sid) / "plan.json"
    if not plan_path.exists():
        raise FileNotFoundError(f"Plan not found for {sid}")
    return json.loads(plan_path.read_text(encoding="utf-8"))


class GeneratorAgent:
    def __init__(self, sid: str, mode: str) -> None:
        self.sid = sid
        self.plan = load_plan(sid)
        self.requirement = self.plan["requirement"]
        self.workspace = ensure_dir(Path(self.plan["paths"]["workspace"]))
        self.metadata_dir = ensure_dir(Path(self.plan["paths"]["metadata"]))
        profile = get_decoding_profile(mode)
        model = self.requirement.get("model_version", "gpt-4.1-mini")
        self.llm = LLMClient(model, profile)

    def run(self) -> None:
        snapshot = self.requirement.get("rag_snapshot", "mvp-sample")
        context = load_static_context(snapshot)
        messages = build_generator_prompt(self.requirement, context)
        llm_notes = self.llm.generate(messages)
        notes_path = self.metadata_dir / "generator_llm_plan.md"
        notes_path.write_text(llm_notes, encoding="utf-8")
        LOGGER.info("LLM guidance saved to %s", notes_path)
        self._materialize_app()

    def _materialize_app(self) -> None:
        files = {
            "app.py": templates.render_app_py(),
            "schema.sql": templates.render_schema_sql(),
            "Dockerfile": templates.render_dockerfile(),
            "requirements.txt": templates.render_requirements(),
            "poc.py": templates.render_poc_py(),
            "README.md": templates.render_readme(self.requirement.get("requirement_id", self.sid)),
        }
        for relative, content in files.items():
            path = self.workspace / relative
            path.write_text(content, encoding="utf-8")
            LOGGER.info("Wrote %s", path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generator agent")
    parser.add_argument("--sid", required=True)
    parser.add_argument("--mode", default="deterministic")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    agent = GeneratorAgent(args.sid, args.mode)
    agent.run()


if __name__ == "__main__":
    main()
