from __future__ import annotations

from pathlib import Path

from common.config import DecodingProfile
import common.llm.provider as provider_mod
from common.llm.provider import LLMClient


def test_llm_client_uses_generator_manifest_fixture_before_stub(monkeypatch, tmp_path: Path) -> None:
    fixture_path = tmp_path / "generator_manifest.json"
    fixture_path.write_text('{"intent":"fixture-manifest"}', encoding="utf-8")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("VUL_LLM_API_KEY", raising=False)
    monkeypatch.setenv("VUL_LLM_FIXTURE_GENERATOR_MANIFEST", str(fixture_path))

    client = LLMClient(
        "gpt-5.2",
        DecodingProfile(mode="deterministic", temperature=0.0, top_p=1.0),
    )
    response = client.generate(
        [
            {"role": "system", "content": "produce ONLY compact JSON matching the generator_manifest section."},
            {"role": "user", "content": "generator_manifest candidate"},
        ]
    )

    assert response == '{"intent":"fixture-manifest"}'
    assert client.fixture_used is True
    assert client.last_fixture_path == str(fixture_path)
    assert client.last_used_stub is False
    assert client.last_provider_attempted is False
    assert client.last_provider_succeeded is False
    assert client.observed_fixture_used is True
    assert client.last_error_class is None


def test_llm_client_does_not_latch_stub_mode_after_transient_provider_error(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("VUL_LLM_API_KEY", raising=False)
    monkeypatch.delenv("VUL_LLM_FIXTURE_GENERATOR_MANIFEST", raising=False)

    calls = {"count": 0}

    def _fake_completion(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("429 rate limit")
        return {"choices": [{"message": {"content": "real-provider-response"}}], "usage": {"total_tokens": 1}}

    monkeypatch.setattr(provider_mod, "litellm_completion", _fake_completion)

    client = LLMClient(
        "gpt-5.2",
        DecodingProfile(mode="deterministic", temperature=0.0, top_p=1.0),
    )
    first = client.generate([{"role": "user", "content": "hello"}])
    second = client.generate([{"role": "user", "content": "hello again"}])

    assert "[llm-stub-response]" in first
    assert client.last_used_stub is False
    assert second == "real-provider-response"
    assert client.use_stub is False
    assert client.observed_provider_attempted is True
    assert client.observed_provider_succeeded is True
    assert client.observed_stub_fallback is True
    assert client.last_error_class is None


def test_llm_client_latches_stub_mode_after_quota_error(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("VUL_LLM_API_KEY", raising=False)
    monkeypatch.delenv("VUL_LLM_FIXTURE_GENERATOR_MANIFEST", raising=False)

    calls = {"count": 0}

    def _fake_completion(**kwargs):
        calls["count"] += 1
        raise RuntimeError("429 rate limit - check billing quota")

    monkeypatch.setattr(provider_mod, "litellm_completion", _fake_completion)

    client = LLMClient(
        "gpt-5.2",
        DecodingProfile(mode="deterministic", temperature=0.0, top_p=1.0),
    )
    first = client.generate([{"role": "user", "content": "hello"}])
    second = client.generate([{"role": "user", "content": "hello again"}])

    assert "[llm-stub-response]" in first
    assert "[llm-stub-response]" in second
    assert client.use_stub is True
    assert calls["count"] == 1
