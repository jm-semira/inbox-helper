"""Bounded retry wrapper for transient provider completion errors."""

import logging
import time

from inbox_helper.application.ports.llm_provider import LLMProvider
from inbox_helper.core.exceptions import TransientLLMProviderError
from inbox_helper.core.logging import get_logger


class RetryingLLMProvider:
    """Retry explicit transient failures once, preserving the final exception."""

    MAX_ATTEMPTS = 2
    BACKOFF_SECONDS = 0.05

    def __init__(
        self,
        provider: LLMProvider,
        logger: logging.Logger | None = None,
    ) -> None:
        self._provider = provider
        self._logger = logger or get_logger("llm.retry")

    def complete(self, prompt: str) -> str:
        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                return self._provider.complete(prompt)
            except TransientLLMProviderError:
                if attempt == self.MAX_ATTEMPTS:
                    self._logger.warning(
                        "LLM completion failed after %s attempts (error_type=%s)",
                        attempt,
                        "transient_provider_error",
                    )
                    raise
                self._logger.warning(
                    "LLM completion transient failure; retrying (attempt=%s)",
                    attempt,
                )
                time.sleep(self.BACKOFF_SECONDS)
        raise AssertionError("unreachable retry state")
