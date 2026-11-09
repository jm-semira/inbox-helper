"""Deterministic local LLM adapter for development and tests."""


class MockLLMProvider:
    """Return a configured response without contacting an external service."""

    def __init__(self, response: str = "Mock response") -> None:
        self._response = response

    def complete(self, prompt: str) -> str:
        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        return self._response
