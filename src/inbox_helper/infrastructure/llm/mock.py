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


class DemoMockLLMProvider(MockLLMProvider):
    """Provide predefined, schema-valid outputs for an explicit demo workflow."""

    mode_label = "Demo Mode"
    mode_description = (
        "Responses are predefined mock outputs, not actual AI-generated results."
    )
    _CLASSIFICATION_RESPONSE = (
        '{"intent":"general_inquiry","urgency":"normal","confidence":0.95,'
        '"explanation":"Predefined demo classification for an email inquiry."}'
    )
    _REPLY_RESPONSE = (
        '{"reply_text":"Thank you for reaching out. We appreciate your '
        'message.","requires_human_input":false,'
        '"human_input_reason":null}'
    )

    def complete(self, prompt: str) -> str:
        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        if prompt.startswith("Classify the email using only evidence"):
            return self._CLASSIFICATION_RESPONSE
        if prompt.startswith(
            "Write a professional, relevant, concise suggested reply"
        ):
            return self._REPLY_RESPONSE
        return "Demo Mode: predefined mock response."
