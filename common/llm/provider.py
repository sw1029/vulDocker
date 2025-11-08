"""Light-weight LLM client abstraction for the MVP.

The implementation prefers a real ``litellm`` backend so that the generator
and reviewer can call an actual hosted model.  When an API key or the
package itself is unavailable the client transparently falls back to a
stub that keeps the rest of the pipeline runnable for dry-runs/tests.
"""
from __future__ import annotations

import logging
import os
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
        self._last_usage: Optional[Dict[str, Any]] = None

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
            else:  # pragma: no cover - configuration error path
                raise LLMConfigError(msg)

    @property
    def last_usage(self) -> Optional[Dict[str, Any]]:
        """Return SDK usage metadata from the previous call."""

        return self._last_usage

    def generate(self, messages: List[Dict[str, str]], *, tools: Optional[List[Dict[str, Any]]] = None) -> str:
        """Generate a response from the underlying model or stub."""

        if self.use_stub:
            return self._stub_response(messages)

        assert litellm_completion is not None  # for type-checkers
        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            **self.decoding.to_kwargs(),
        }
        if tools:
            payload["tools"] = tools

        LOGGER.debug("Invoking litellm with payload keys: %s", list(payload))
        response = litellm_completion(**payload)  # pragma: no cover - network call
        self._last_usage = getattr(response, "usage", None)
        return response["choices"][0]["message"]["content"]

    def _stub_response(self, messages: List[Dict[str, str]]) -> str:
        """Return a deterministic stub when the real model is unavailable."""

        prompt_echo = "\n---\n".join(m.get("content", "") for m in messages)
        return (
            "[llm-stub-response]\n"
            "The real LLM backend is not configured. "
            "Use this deterministic plan as guidance."\
            "\n\n"
            f"Prompt digest (truncated):\n{prompt_echo[:400]}..."
        )
