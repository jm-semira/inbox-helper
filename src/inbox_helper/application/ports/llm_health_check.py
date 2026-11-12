"""Separate provider-neutral capability for checking provider availability."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMHealthCheck(Protocol):
    """Provider health probe, separate from prompt completion and its retries."""

    def check_health(self) -> bool:
        """Return whether the provider reports itself healthy."""
