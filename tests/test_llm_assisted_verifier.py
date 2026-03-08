from __future__ import annotations

from pathlib import Path

import evals.poc_verifier.llm_assisted as llm_assisted


class _DummyClient:
    def __init__(self, model: str, decoding) -> None:  # pragma: no cover - constructor shape only
        self.model = model
        self.decoding = decoding

    def generate(self, prompt) -> str:
        return (
            '{"verify_pass": true, "rationale": "matched log", '
            '"proposed_assertions": [{"op": "contains", "string": "FLAG{OK}"}]}'
        )


def test_llm_assisted_verify_runs_assertion_program(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "run.log"
    log_path.write_text("FLAG{OK}\n", encoding="utf-8")
    monkeypatch.setattr(llm_assisted, "LLMClient", _DummyClient)

    result = llm_assisted.llm_assisted_verify(
        "CWE-9999",
        log_path,
        requirement={"vuln_id": "CWE-9999"},
        policy={"llm_assist": True, "assertion_budget": 1},
    )

    assert result is not None
    assert result["verify_pass"] is True
    assert "[PASS::contains]" in result["evidence"]
