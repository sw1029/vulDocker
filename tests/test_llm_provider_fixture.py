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
    last_summary = client.execution_summary()
    observed_summary = client.execution_summary(observed=True)
    assert last_summary["path_class"] == "fixture"
    assert last_summary["fixture_path"] == str(fixture_path)
    assert last_summary["model"] == "gpt-5.2"
    assert last_summary["decoding_profile"]["mode"] == "deterministic"
    assert last_summary["cache_mode"] == "fixture_file"
    assert observed_summary["path_class"] == "fixture"
    assert observed_summary["fixture_used"] is True


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
    observed_summary = client.execution_summary(observed=True)
    assert observed_summary["path_class"] == "degraded"
    assert observed_summary["provider_attempted"] is True
    assert observed_summary["provider_succeeded"] is True
    assert observed_summary["stub_fallback"] is True
    assert observed_summary["cache_mode"] == "none"


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
    observed_summary = client.execution_summary(observed=True)
    assert observed_summary["path_class"] == "degraded"
    assert observed_summary["last_error_class"] == "quota_exhausted"
    assert observed_summary["last_error_retryable"] is False
    assert observed_summary["cache_mode"] == "none"


def test_llm_client_surfaces_configured_timeout_budget(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("VUL_LLM_TIMEOUT_S", "12.5")

    captured = {}

    def _fake_completion(**kwargs):
        captured.update(kwargs)
        return {"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 1}}

    monkeypatch.setattr(provider_mod, "litellm_completion", _fake_completion)

    client = LLMClient(
        "gpt-5.2",
        DecodingProfile(mode="deterministic", temperature=0.0, top_p=1.0),
    )
    response = client.generate([{"role": "user", "content": "hello"}])

    assert response == "ok"
    assert captured["timeout"] == 12.5
    assert client.execution_summary()["timeout_budget"]["llm_request_timeout_s"] == 12.5


def test_llm_client_surfaces_cost_budget_and_usage_tokens(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("VUL_LLM_COST_BUDGET_USD", "0.25")

    calls = {"count": 0}

    def _fake_completion(**kwargs):
        calls["count"] += 1
        return {
            "choices": [{"message": {"content": f"ok-{calls['count']}"}}],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }

    monkeypatch.setattr(provider_mod, "litellm_completion", _fake_completion)

    client = LLMClient(
        "gpt-5.2",
        DecodingProfile(mode="deterministic", temperature=0.0, top_p=1.0),
    )
    first = client.generate([{"role": "user", "content": "hello"}])
    second = client.generate([{"role": "user", "content": "world"}])

    assert first == "ok-1"
    assert second == "ok-2"
    last_summary = client.execution_summary()
    observed_summary = client.execution_summary(observed=True)
    assert last_summary["cost_budget"]["configured_cost_budget_usd"] == 0.25
    assert last_summary["cost_budget"]["usage_tokens"] == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }
    assert last_summary["cost_budget"]["usage_scope"] == "last_call"
    assert last_summary["cost_budget"]["pricing_model"] == "gpt-5"
    assert last_summary["cost_budget"]["pricing_basis"] == "alias"
    assert round(last_summary["cost_budget"]["estimated_cost_usd"], 7) == 0.0000625
    assert observed_summary["cost_budget"]["usage_tokens"] == {
        "prompt_tokens": 20,
        "completion_tokens": 10,
        "total_tokens": 30,
    }
    assert observed_summary["cost_budget"]["usage_scope"] == "observed"
    assert round(observed_summary["cost_budget"]["estimated_cost_usd"], 6) == 0.000125
