#!/usr/bin/env python3
"""LLM-assisted stdlib alias bootstrapper.

This utility prompts the configured LLM to emit JSON containing stdlib modules,
alias/installation hints, and default package versions. The output is written to
``prototypes/stdlib/<language>-<version>.json`` so core guard logic can load it
deterministically without depending on the LLM at runtime.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from common.config import get_decoding_profile
from common.llm import LLMClient
from common.logging import get_logger
from common.paths import get_repo_root

LOGGER = get_logger(__name__)

SYSTEM_PROMPT = """
You are a language tooling assistant. You must emit compact JSON describing the
standard library modules and dependency aliases for the requested language.
Do not add commentary. The JSON schema is:
{
  "language": "python",
  "version": "3.11",
  "stdlib_modules": ["module"...],
  "aliases": [{"module": "sqlite3", "package": "pysqlite3-binary"}],
  "default_versions": {"package": "version"},
  "auto_patch_denylist": ["module"]
}
Only include modules/packages that are accurate for the specified language and
version. Use lowercase names and pinned versions when possible.
""".strip()


def _extract_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = raw[start : end + 1]
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                return {}
        return {}


def _write_output(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    LOGGER.info("Stdlib spec written to %s", path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap stdlib metadata via LLM")
    parser.add_argument("--language", default="python", help="Target language (default: python)")
    parser.add_argument("--version", default="3.11", help="Language/runtime version tag")
    parser.add_argument("--model", default="gpt-4.1-mini", help="LLM model name")
    parser.add_argument("--mode", default="deterministic", help="Decoding profile name")
    parser.add_argument(
        "--output",
        type=Path,
        help="Override output path (defaults to prototypes/stdlib/<lang>-<ver>.json)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    profile = get_decoding_profile(args.mode)
    client = LLMClient(args.model, profile)
    repo_root = get_repo_root()
    default_path = repo_root / "prototypes" / "stdlib" / f"{args.language.lower()}-{args.version}.json"
    output_path = args.output or default_path

    user_prompt = (
        "Language: {lang}\nVersion: {ver}. Return JSON matching the schema.".format(
            lang=args.language, ver=args.version
        )
    )
    response = client.generate(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
    )
    data = _extract_json(response)
    if not data:
        raise RuntimeError("LLM did not return valid JSON. Response: %s" % response)
    _write_output(data, output_path)


if __name__ == "__main__":
    main()
