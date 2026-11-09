"""Provider-neutral language model boundary."""

from typing import Protocol


class LLMProvider(Protocol):
    """Minimal interface consumed by future application use cases."""

    def complete(self, prompt: str) -> str:
        """Return generated text for the supplied prompt."""
