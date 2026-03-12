"""Light-weight LLM client abstraction for the MVP.

The implementation prefers a real ``litellm`` backend so that the generator
and reviewer can call an actual hosted model.  When an API key or the
package itself is unavailable the client transparently falls back to a
stub that keeps the rest of the pipeline runnable for dry-runs/tests.
"""
from __future__ import annotations

import logging
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from common.config import DecodingProfile, get_openai_api_key

try:  # pragma: no cover - optional dependency
    from litellm import completion as litellm_completion
except Exception:  # pragma: no cover - optional dependency
    litellm_completion = None


LOGGER = logging.getLogger("common.llm")


class LLMConfigError(RuntimeError):
    """Raised when a real LLM call is requested but not properly configured."""


class LLMClient:
    """Small wrapper over litellm with a deterministic fallback."""

    def __init__(
        self,
        model_name: str,
        decoding: DecodingProfile,
        use_stub_when_unavailable: bool = True,
    ) -> None:
        self.model_name = model_name
        self.decoding = decoding
        self.use_stub = False
        self.fixture_used = False
        self.last_fixture_path: Optional[str] = None
        self._fallback_on_error = use_stub_when_unavailable
        self._last_usage: Optional[Dict[str, Any]] = None
        self.last_error_class: Optional[str] = None
        self.last_error_message: Optional[str] = None
        self.last_error_retryable: Optional[bool] = None
        self.last_used_stub: bool = False
        self.last_provider_attempted: bool = False
        self.last_provider_succeeded: bool = False
        self.observed_stub_fallback: bool = False
        self.observed_fixture_used: bool = False
        self.observed_provider_attempted: bool = False
        self.observed_provider_succeeded: bool = False
        forced_stub_reason = str(os.environ.get("VUL_FORCE_LLM_STUB_REASON") or "").strip().lower()
        if os.environ.get("VUL_FORCE_LLM_STUB"):
            self.use_stub = True
            self.last_error_class = forced_stub_reason or "provider_disabled"
            self.last_error_message = "Remote LLM provider disabled by pipeline circuit breaker."
            self.last_error_retryable = False

        api_key = (
            get_openai_api_key()
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("VUL_LLM_API_KEY")
        )
        if api_key and not os.environ.get("OPENAI_API_KEY"):
            # litellm defaults to OPENAI_API_KEY for OpenAI-compatible endpoints.
            os.environ["OPENAI_API_KEY"] = api_key

        if litellm_completion is None or not api_key:
            msg = "litellm or VUL_LLM_API_KEY is missing; falling back to stub"
            if use_stub_when_unavailable:
                LOGGER.warning(msg)
                self.use_stub = True
                self.last_error_class = "llm_unavailable"
                self.last_error_message = msg
                self.last_error_retryable = False
            else:  # pragma: no cover - configuration error path
                raise LLMConfigError(msg)

    @property
    def last_usage(self) -> Optional[Dict[str, Any]]:
        """Return SDK usage metadata from the previous call."""

        return self._last_usage

    def generate(self, messages: List[Dict[str, str]], *, tools: Optional[List[Dict[str, Any]]] = None) -> str:
        """Generate a response from the underlying model or stub."""

        self._reset_last_execution_state()
        self.fixture_used = False
        self.last_fixture_path = None
        fixture_response = self._fixture_response(messages)
        if fixture_response is not None:
            self.last_error_class = None
            self.last_error_message = None
            self.last_error_retryable = None
            self._last_usage = None
            self.observed_fixture_used = True
            return fixture_response

        if self.use_stub:
            self.last_used_stub = True
            self.observed_stub_fallback = True
            return self._stub_response(messages)

        self.last_error_class = None
        self.last_error_message = None
        self.last_error_retryable = None

        assert litellm_completion is not None  # for type-checkers
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            **self.decoding.to_kwargs(),
        }
        if self._model_disallows_sampling_params(self.model_name):
            payload.pop("temperature", None)
            payload.pop("top_p", None)
        if tools:
            payload["tools"] = tools

        LOGGER.debug("Invoking litellm with payload keys: %s", list(payload))
        self.last_provider_attempted = True
        self.observed_provider_attempted = True
        try:
            response = litellm_completion(**payload)  # pragma: no cover - network call
        except Exception as exc:  # pragma: no cover - provider compatibility retry
            if self._is_unsupported_params_error(exc):
                retry_payload = dict(payload)
                retry_payload.pop("top_p", None)
                retry_payload.pop("temperature", None)
                LOGGER.info(
                    "Retrying LLM call without sampling params for model=%s due to unsupported parameter",
                    self.model_name,
                )
                response = litellm_completion(**retry_payload)
            else:
                if not self._fallback_on_error:
                    self._record_error(exc)
                    raise
                LOGGER.warning("LLM call failed (%s); falling back to stub output", exc)
                self._record_error(exc)
                self.last_used_stub = True
                self.observed_stub_fallback = True
                return self._stub_response(messages)
        try:
            self._last_usage = getattr(response, "usage", None)
            self.last_provider_succeeded = True
            self.observed_provider_succeeded = True
            return response["choices"][0]["message"]["content"]
        except Exception as exc:  # pragma: no cover - network failure fallback
            if not self._fallback_on_error:
                self._record_error(exc)
                raise
            LOGGER.warning("LLM call failed (%s); falling back to stub output", exc)
            self._record_error(exc)
            self.last_used_stub = True
            self.observed_stub_fallback = True
            return self._stub_response(messages)

    def _reset_last_execution_state(self) -> None:
        self.last_used_stub = False
        self.last_provider_attempted = False
        self.last_provider_succeeded = False

    @staticmethod
    def _is_unsupported_params_error(exc: Exception) -> bool:
        text = str(exc or "")
        lowered = text.lower()
        return "unsupportedparamserror" in lowered

    @staticmethod
    def _model_disallows_sampling_params(model_name: str) -> bool:
        token = (model_name or "").strip().lower()
        return token.startswith("gpt-5")

    def _record_error(self, exc: Exception) -> None:
        token = str(exc or "").strip()
        lowered = token.lower()
        error_class = "llm_error"
        retryable = False

        if "quota" in lowered or ("rate limit" in lowered and "billing" in lowered):
            error_class = "quota_exhausted"
        elif "rate limit" in lowered or "429" in lowered:
            error_class = "rate_limited"
            retryable = True
        elif "unauthorized" in lowered or "401" in lowered or "invalid api key" in lowered or "authentication" in lowered:
            error_class = "auth_failure"
        elif "timeout" in lowered or "connection" in lowered or "dns" in lowered or "temporarily unavailable" in lowered:
            error_class = "network_transient"
            retryable = True
        elif "503" in lowered or "service unavailable" in lowered or "provider unavailable" in lowered or "overloaded" in lowered:
            error_class = "provider_unavailable"
            retryable = True

        self.last_error_class = error_class
        self.last_error_message = token[:500] if token else None
        self.last_error_retryable = retryable
        if error_class in {"quota_exhausted", "auth_failure"}:
            # Non-transient provider failures should not be paid repeatedly
            # within the same researcher/generator/reviewer run.
            self.use_stub = True

    def _fixture_response(self, messages: List[Dict[str, str]]) -> Optional[str]:
        prompt_echo = "\n---\n".join(m.get("content", "") for m in messages if m.get("content"))
        lowered = prompt_echo.lower()
        fixture_specs = [
            (
                "VUL_LLM_FIXTURE_GENERATOR_MANIFEST",
                ("generator_manifest", "produce only compact json"),
            ),
        ]
        for env_key, markers in fixture_specs:
            raw_path = str(os.environ.get(env_key) or "").strip()
            if not raw_path:
                continue
            if not all(marker in lowered for marker in markers):
                continue
            fixture_path = Path(raw_path)
            if not fixture_path.is_absolute():
                fixture_path = Path.cwd() / fixture_path
            if not fixture_path.exists():
                raise LLMConfigError(f"LLM fixture file does not exist: {fixture_path}")
            self.fixture_used = True
            self.last_fixture_path = str(fixture_path)
            return fixture_path.read_text(encoding="utf-8")
        return None

    def _stub_response(self, messages: List[Dict[str, str]]) -> str:
        """Return a deterministic stub when the real model is unavailable."""

        prompt_echo = "\n---\n".join(m.get("content", "") for m in messages if m.get("content"))
        lowered = prompt_echo.lower()

        # Some call sites require strict JSON (Researcher / LLM verifier).
        if "researcher_report" in lowered and "produce only compact json" in lowered:
            payload = {
                "vuln_id": "UNKNOWN",
                "intent": "llm stub: offline researcher report",
                "preconditions": [],
                "tech_stack_candidates": [],
                "minimal_repro_steps": [],
                "references": [],
                "pocs": [],
                "deps": [],
                "risks": [],
                "verification_spec": {
                    "success_mode": "text",
                    "success_text_markers": ["Exploit SUCCESS"],
                    "flag_mode": "none",
                    "assertion_program": [{"op": "contains", "string": "Exploit SUCCESS"}],
                },
                "notes": "This report was generated by the built-in LLM stub due to unavailable network/keys.",
            }
            return json.dumps(payload, ensure_ascii=False)

        if "generator_manifest" in lowered and "produce only compact json" in lowered:
            # Synthesis callers already implement their own deterministic fallback
            # manifest builder. Return a non-JSON stub without curly braces so
            # the downstream parser reliably triggers that fallback.
            return "[llm-stub-synthesis] LLM unavailable; using deterministic fallback manifest."

        if "verification analyst" in lowered and "reply with strict json" in lowered:
            payload = {
                "verify_pass": False,
                "confidence": "low",
                "rationale": "LLM stub: unable to reach configured model endpoint.",
                "proposed_assertions": [],
                "extracted_evidence": [],
                "metamorphic": None,
            }
            return json.dumps(payload, ensure_ascii=False)

        return (
            "[llm-stub-response]\n"
            "The real LLM backend is not available (network/config). "
            "Returning deterministic guidance output.\n\n"
            f"Prompt digest (truncated):\n{prompt_echo[:400]}..."
        )
