"""Local Ollama HTTP adapter for provider-neutral completion and health checks."""

from __future__ import annotations

import json
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from inbox_helper.application.ports.llm_health_check import LLMHealthCheck
from inbox_helper.application.ports.llm_provider import LLMProvider
from inbox_helper.core.config import AppConfig
from inbox_helper.core.exceptions import (
    LLMProviderError,
    LLMProviderTimeoutError,
    TransientLLMProviderError,
)


class OllamaLLMProvider(LLMProvider, LLMHealthCheck):
    """Call Ollama's non-streaming generation and tags health endpoints."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float,
        temperature: float,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._temperature = temperature

    @classmethod
    def from_config(cls, config: AppConfig) -> OllamaLLMProvider:
        """Build the adapter from validated application configuration."""
        return cls(
            base_url=config.ollama_base_url,
            model=config.llm_model,
            timeout=config.llm_timeout,
            temperature=config.llm_temperature,
        )

    def complete(self, prompt: str) -> str:
        """Return Ollama's generated text or raise a classified provider error."""
        payload = json.dumps(
            {
                "model": self._model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": self._temperature},
            }
        ).encode("utf-8")
        request = Request(
            f"{self._base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout) as response:
                body = response.read()
        except HTTPError as error:
            self._raise_http_error(error.code)
        except (socket.timeout, TimeoutError) as error:
            raise LLMProviderTimeoutError(
                "Ollama request exceeded the configured timeout."
            ) from error
        except URLError as error:
            if isinstance(error.reason, (socket.timeout, TimeoutError)):
                raise LLMProviderTimeoutError(
                    "Ollama request exceeded the configured timeout."
                ) from error
            raise TransientLLMProviderError(
                "Could not connect to the configured Ollama service."
            ) from error
        except OSError as error:
            if isinstance(error, (socket.timeout, TimeoutError)):
                raise LLMProviderTimeoutError(
                    "Ollama request exceeded the configured timeout."
                ) from error
            raise TransientLLMProviderError(
                "Could not communicate with the configured Ollama service."
            ) from error

        try:
            envelope = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise LLMProviderError(
                "Ollama returned a malformed response envelope."
            ) from error
        if not isinstance(envelope, dict):
            raise LLMProviderError(
                "Ollama returned a malformed response envelope."
            )
        generated = envelope.get("response")
        if not isinstance(generated, str) or not generated.strip():
            raise LLMProviderError(
                "Ollama response did not contain generated text."
            )
        return generated

    def check_health(self) -> bool:
        """Check Ollama service reachability without running model inference."""
        request = Request(f"{self._base_url}/api/tags", method="GET")
        try:
            with urlopen(request, timeout=self._timeout) as response:
                return 200 <= response.status < 300
        except (HTTPError, URLError, OSError, TimeoutError, ValueError):
            return False

    @staticmethod
    def _raise_http_error(status_code: int) -> None:
        if status_code >= 500 or status_code in {408, 429}:
            raise TransientLLMProviderError(
                "Ollama returned a temporary server error."
            )
        raise LLMProviderError("Ollama rejected the request.")
