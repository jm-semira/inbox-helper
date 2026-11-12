"""Configuration-driven LLM provider construction."""

from inbox_helper.application.ports.llm_health_check import LLMHealthCheck
from inbox_helper.application.ports.llm_provider import LLMProvider
from inbox_helper.core.config import AppConfig, get_config
from inbox_helper.core.exceptions import ConfigurationError
from inbox_helper.infrastructure.llm.mock import MockLLMProvider
from inbox_helper.infrastructure.llm.retrying import RetryingLLMProvider


def _create_raw_provider(config: AppConfig) -> LLMProvider:
    if config.llm_provider == "mock":
        return MockLLMProvider()
    raise ConfigurationError(
        f"LLM provider '{config.llm_provider}' is configured but not implemented."
    )


def create_llm_provider(config: AppConfig | None = None) -> LLMProvider:
    """Construct the configured provider with bounded transient retries."""
    return RetryingLLMProvider(_create_raw_provider(config or get_config()))


def create_llm_health_check(
    config: AppConfig | None = None,
) -> LLMHealthCheck:
    """Construct the separate health-check capability without retry wrapping."""
    provider = _create_raw_provider(config or get_config())
    if not isinstance(provider, LLMHealthCheck):
        raise ConfigurationError(
            f"LLM provider '{(config or get_config()).llm_provider}' "
            "does not support health checks."
        )
    return provider
