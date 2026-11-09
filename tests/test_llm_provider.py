import pytest

from inbox_helper.core.config import AppConfig
from inbox_helper.core.exceptions import ConfigurationError
from inbox_helper.infrastructure.llm.factory import create_llm_provider
from inbox_helper.infrastructure.llm.mock import MockLLMProvider


def test_factory_creates_mock_provider() -> None:
    provider = create_llm_provider(AppConfig())

    assert isinstance(provider, MockLLMProvider)
    assert provider.complete("hello") == "Mock response"


def test_factory_rejects_unimplemented_provider() -> None:
    config = AppConfig(llm_provider="openai")

    with pytest.raises(ConfigurationError, match="not implemented"):
        create_llm_provider(config)


def test_mock_rejects_empty_prompt() -> None:
    with pytest.raises(ValueError, match="prompt"):
        MockLLMProvider().complete(" ")
