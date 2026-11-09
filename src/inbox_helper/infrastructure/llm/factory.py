"""Configuration-driven LLM provider construction."""

from inbox_helper.application.ports.llm_provider import LLMProvider
from inbox_helper.core.config import AppConfig, get_config
from inbox_helper.core.exceptions import ConfigurationError
from inbox_helper.infrastructure.llm.mock import MockLLMProvider


def create_llm_provider(config: AppConfig | None = None) -> LLMProvider:
    """Construct the configured adapter if it is implemented."""
    active_config = config or get_config()
    if active_config.llm_provider == "mock":
        return MockLLMProvider()
    raise ConfigurationError(
        f"LLM provider '{active_config.llm_provider}' is configured but not implemented."
    )
