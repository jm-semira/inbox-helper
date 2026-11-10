"""Provider-neutral language model boundary."""

from typing import Protocol

from inbox_helper.core.exceptions import LLMProviderError


class LLMProvider(Protocol):
    """Minimal interface consumed by future application use cases."""

    def complete(self, prompt: str) -> str:
        """Return generated text or raise LLMProviderError on provider failure."""
