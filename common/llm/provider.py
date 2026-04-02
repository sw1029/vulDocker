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
    from litellm import cost_per_token as litellm_cost_per_token
except Exception:  # pragma: no cover - optional dependency
    litellm_completion = None
    litellm_cost_per_token = None


LOGGER = logging.getLogger("common.llm")


class LLMConfigError(RuntimeError):
    """Raised when a real LLM call is requested but not properly configured."""


def _safe_timeout_seconds(value: Any) -> Optional[float]:
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        return None
    if timeout <= 0:
        return None
    return timeout


def _safe_nonnegative_float(value: Any) -> Optional[float]:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    if amount < 0:
        return None
    return amount


def _safe_nonnegative_int(value: Any) -> Optional[int]:
    try:
        amount = int(value)
    except (TypeError, ValueError):
        return None
    if amount < 0:
        return None
    return amount


def _normalize_usage_payload(usage: Any) -> Dict[str, int]:
    if usage is None:
        return {}
    if isinstance(usage, dict):
        mapping = usage
    else:
        mapping = {}
        for key in ("prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens"):
            value = getattr(usage, key, None)
            if value is not None:
                mapping[key] = value
        details = getattr(usage, "completion_tokens_details", None)
        if details is not None:
            reasoning = getattr(details, "reasoning_tokens", None)
            if reasoning is not None and "reasoning_tokens" not in mapping:
                mapping["reasoning_tokens"] = reasoning
    payload: Dict[str, int] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "reasoning_tokens"):
        value = _safe_nonnegative_int(mapping.get(key))
        if value is not None:
            payload[key] = value
    return payload


def _pricing_model_candidates(model_name: Optional[str]) -> List[tuple[str, str]]:
    token = str(model_name or "").strip().lower()
    if not token:
        return []
    candidates: List[tuple[str, str]] = []
    if token.startswith("gpt-5") and token != "gpt-5":
        candidates.append(("gpt-5", "alias"))
    candidates.append((token, "exact"))
    return candidates


def _estimate_cost_budget(
    *,
    model_name: Optional[str],
    usage_tokens: Dict[str, int],
) -> Dict[str, Any]:
    if not usage_tokens or litellm_cost_per_token is None:
        return {}
    prompt_tokens = int(usage_tokens.get("prompt_tokens") or 0)
    completion_tokens = int(usage_tokens.get("completion_tokens") or 0)
    if prompt_tokens <= 0 and completion_tokens <= 0:
        return {}
    for candidate, basis in _pricing_model_candidates(model_name):
        try:
            prompt_cost, completion_cost = litellm_cost_per_token(
                model=candidate,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        except Exception:
            continue
        total = float(prompt_cost or 0.0) + float(completion_cost or 0.0)
        return {
            "estimated_cost_usd": total,
            "estimated_prompt_cost_usd": float(prompt_cost or 0.0),
            "estimated_completion_cost_usd": float(completion_cost or 0.0),
            "pricing_model": candidate,
            "pricing_basis": basis,
            "pricing_source": "litellm_cost_map",
        }
    return {}


class LLMClient:
    """Small wrapper over litellm with a deterministic fallback."""

    def __init__(
        self,
        model_name: str,
        decoding: DecodingProfile,
        use_stub_when_unavailable: bool = True,
        request_timeout_s: Optional[float] = None,
        configured_cost_budget_usd: Optional[float] = None,
    ) -> None:
        self.model_name = model_name
        self.decoding = decoding
        self.request_timeout_s = _safe_timeout_seconds(request_timeout_s)
        if self.request_timeout_s is None:
            self.request_timeout_s = _safe_timeout_seconds(os.environ.get("VUL_LLM_TIMEOUT_S"))
        self.configured_cost_budget_usd = _safe_nonnegative_float(configured_cost_budget_usd)
        if self.configured_cost_budget_usd is None:
            self.configured_cost_budget_usd = _safe_nonnegative_float(os.environ.get("VUL_LLM_COST_BUDGET_USD"))
        self.use_stub = False
        self.fixture_used = False
        self.last_fixture_path: Optional[str] = None
        self._fallback_on_error = use_stub_when_unavailable
        self._last_usage: Optional[Dict[str, Any]] = None
        self._observed_usage_totals: Dict[str, int] = {}
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

    def execution_summary(
        self,
        *,
        observed: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Return a machine-readable summary of the current LLM execution path."""

        return _build_execution_summary_payload(
            model_name=self.model_name,
            decoding=self.decoding,
            provider_backend="litellm" if litellm_completion is not None else "stub_only",
            provider_attempted=(
                self.observed_provider_attempted if observed else self.last_provider_attempted
            ),
            provider_succeeded=(
                self.observed_provider_succeeded if observed else self.last_provider_succeeded
            ),
            stub_fallback=(
                self.observed_stub_fallback if observed else self.last_used_stub
            ),
            fixture_used=(
                self.observed_fixture_used if observed else self.fixture_used
            ),
            last_error_class=self.last_error_class,
            last_error_message=self.last_error_message,
            last_error_retryable=self.last_error_retryable,
            fixture_path=self.last_fixture_path,
            attempt_scope="observed" if observed else "last_call",
            fallback_on_error=self._fallback_on_error,
            stub_mode_enabled=self.use_stub,
            metadata={
                **(metadata or {}),
                "llm_request_timeout_s": self.request_timeout_s,
                "llm_cost_budget_usd": self.configured_cost_budget_usd,
                "llm_usage_tokens": self._observed_usage_totals if observed else self._last_usage,
                "usage_scope": "observed" if observed else "last_call",
            },
        )

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
        if self.request_timeout_s is not None:
            payload["timeout"] = self.request_timeout_s
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
            usage_payload = getattr(response, "usage", None)
            if usage_payload is None and isinstance(response, dict):
                usage_payload = response.get("usage")
            self._last_usage = _normalize_usage_payload(usage_payload)
            for key, value in (self._last_usage or {}).items():
                self._observed_usage_totals[key] = int(self._observed_usage_totals.get(key) or 0) + int(value)
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


def _decoding_profile_payload(decoding: Any) -> Dict[str, Any]:
    if decoding is None:
        return {}
    payload: Dict[str, Any] = {}
    for key in ("mode", "temperature", "top_p", "self_consistency_k"):
        value = getattr(decoding, key, None)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            payload[key] = float(value) if key in {"temperature", "top_p"} else int(value)
        elif isinstance(value, str) and value.strip():
            payload[key] = value.strip()
    return payload


def _execution_path_class(
    *,
    provider_attempted: bool,
    provider_succeeded: bool,
    stub_fallback: bool,
    fixture_used: bool,
) -> str:
    if fixture_used:
        return "fixture"
    if provider_succeeded and not stub_fallback:
        return "live"
    if stub_fallback and provider_attempted:
        return "degraded"
    if stub_fallback:
        return "stub"
    return "not_executed"


def _build_execution_summary_payload(
    *,
    model_name: Optional[str],
    decoding: Any,
    provider_backend: Optional[str],
    provider_attempted: bool,
    provider_succeeded: bool,
    stub_fallback: bool,
    fixture_used: bool,
    last_error_class: Optional[str],
    last_error_message: Optional[str],
    last_error_retryable: Optional[bool],
    fixture_path: Optional[str],
    attempt_scope: str,
    fallback_on_error: Optional[bool],
    stub_mode_enabled: Optional[bool],
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "attempt_scope": attempt_scope,
        "provider_attempted": bool(provider_attempted),
        "provider_succeeded": bool(provider_succeeded),
        "stub_fallback": bool(stub_fallback),
        "fixture_used": bool(fixture_used),
        "path_class": _execution_path_class(
            provider_attempted=bool(provider_attempted),
            provider_succeeded=bool(provider_succeeded),
            stub_fallback=bool(stub_fallback),
            fixture_used=bool(fixture_used),
        ),
        "cache_mode": "fixture_file" if bool(fixture_used) else "none",
    }
    if isinstance(provider_backend, str) and provider_backend.strip():
        payload["provider_backend"] = provider_backend.strip()
    if isinstance(model_name, str) and model_name.strip():
        payload["model"] = model_name.strip()
    decoding_payload = _decoding_profile_payload(decoding)
    if decoding_payload:
        payload["decoding_profile"] = decoding_payload
    if isinstance(fallback_on_error, bool):
        payload["fallback_on_error"] = fallback_on_error
    if isinstance(stub_mode_enabled, bool):
        payload["stub_mode_enabled"] = stub_mode_enabled
    if bool(fixture_used) and isinstance(fixture_path, str) and fixture_path.strip():
        payload["fixture_path"] = fixture_path.strip()
    if isinstance(last_error_class, str) and last_error_class.strip():
        payload["last_error_class"] = last_error_class.strip()
    if isinstance(last_error_message, str) and last_error_message.strip():
        payload["last_error_message"] = last_error_message.strip()
    if isinstance(last_error_retryable, bool):
        payload["last_error_retryable"] = last_error_retryable
    timeout_budget: Dict[str, Any] = {}
    request_timeout_s = _safe_timeout_seconds(getattr(decoding, "request_timeout_s", None))
    if request_timeout_s is None and metadata is not None:
        request_timeout_s = _safe_timeout_seconds((metadata or {}).get("llm_request_timeout_s"))
    if request_timeout_s is not None:
        timeout_budget["llm_request_timeout_s"] = request_timeout_s
    if timeout_budget:
        payload["timeout_budget"] = timeout_budget
    cost_budget: Dict[str, Any] = {}
    configured_cost_budget_usd = _safe_nonnegative_float(
        metadata.get("llm_cost_budget_usd") if isinstance(metadata, dict) else None
    )
    if configured_cost_budget_usd is not None:
        cost_budget["configured_cost_budget_usd"] = configured_cost_budget_usd
    usage_tokens = _normalize_usage_payload(
        metadata.get("llm_usage_tokens") if isinstance(metadata, dict) else None
    )
    if usage_tokens:
        cost_budget["usage_tokens"] = usage_tokens
    usage_scope = metadata.get("usage_scope") if isinstance(metadata, dict) else None
    if usage_tokens and isinstance(usage_scope, str) and usage_scope.strip():
        cost_budget["usage_scope"] = usage_scope.strip()
    cost_budget.update(
        _estimate_cost_budget(
            model_name=model_name,
            usage_tokens=usage_tokens,
        )
    )
    if cost_budget:
        payload["cost_budget"] = cost_budget
    if isinstance(metadata, dict):
        for key, value in metadata.items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            if isinstance(value, dict) and not value:
                continue
            if isinstance(value, list) and not value:
                continue
            normalized = json.loads(json.dumps(value, ensure_ascii=False))
            if isinstance(normalized, dict) and isinstance(payload.get(key), dict):
                merged = dict(payload.get(key) or {})
                merged.update(normalized)
                payload[key] = merged
                continue
            payload[key] = normalized
    return payload


def llm_execution_summary(
    llm: Any,
    *,
    observed: bool = False,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Collect a normalized LLM execution summary from real or fake clients."""

    if llm is None:
        return {}
    method = getattr(llm, "execution_summary", None)
    if callable(method):
        try:
            payload = method(observed=observed, metadata=metadata)
        except TypeError:
            try:
                payload = method(observed=observed)
            except TypeError:
                payload = method()
        if isinstance(payload, dict) and payload:
            return payload
    attempted_attr = "observed_provider_attempted" if observed else "last_provider_attempted"
    succeeded_attr = "observed_provider_succeeded" if observed else "last_provider_succeeded"
    stub_attr = "observed_stub_fallback" if observed else "last_used_stub"
    fixture_attr = "observed_fixture_used" if observed else "fixture_used"
    return _build_execution_summary_payload(
        model_name=getattr(llm, "model_name", None),
        decoding=getattr(llm, "decoding", None),
        provider_backend=None,
        provider_attempted=bool(getattr(llm, attempted_attr, False)),
        provider_succeeded=bool(getattr(llm, succeeded_attr, False)),
        stub_fallback=bool(getattr(llm, stub_attr, False)),
        fixture_used=bool(getattr(llm, fixture_attr, False)),
        last_error_class=getattr(llm, "last_error_class", None),
        last_error_message=getattr(llm, "last_error_message", None),
        last_error_retryable=getattr(llm, "last_error_retryable", None),
        fixture_path=getattr(llm, "last_fixture_path", None),
        attempt_scope="observed" if observed else "last_call",
        fallback_on_error=getattr(llm, "_fallback_on_error", None),
        stub_mode_enabled=getattr(llm, "use_stub", None),
        metadata={
            **(metadata or {}),
            "llm_request_timeout_s": getattr(llm, "request_timeout_s", None),
            "llm_cost_budget_usd": getattr(llm, "configured_cost_budget_usd", None),
            "llm_usage_tokens": (
                getattr(llm, "_observed_usage_totals", None)
                if observed
                else getattr(llm, "_last_usage", None)
            ),
            "usage_scope": "observed" if observed else "last_call",
        },
    )
