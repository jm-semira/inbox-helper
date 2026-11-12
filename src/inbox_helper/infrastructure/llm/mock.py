"""Deterministic local LLM adapter for development and tests."""

from inbox_helper.application.ports.llm_health_check import LLMHealthCheck


class MockLLMProvider(LLMHealthCheck):
    """Return a configured response without contacting an external service."""

    def __init__(self, response: str = "Mock response") -> None:
        self._response = response

    def complete(self, prompt: str) -> str:
        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        return self._response

    def check_health(self) -> bool:
        """Report healthy because the local deterministic mock is available."""
        return True
