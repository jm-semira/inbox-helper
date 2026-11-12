"""Provider health-check use case."""

from inbox_helper.application.ports.llm_health_check import LLMHealthCheck


class ProviderHealthService:
    """Expose the configured provider's separate health-check capability."""

    def __init__(self, health_check: LLMHealthCheck) -> None:
        self._health_check = health_check

    def check(self) -> bool:
        """Return the provider's health status without issuing a completion."""
        return self._health_check.check_health()
