import logging

import pytest

from inbox_helper.application.services.email_classifier import EmailClassifier
from inbox_helper.core.config import AppConfig
from inbox_helper.core.exceptions import (
    ClassificationError,
    ConfigurationError,
    LLMProviderError,
    LLMProviderTimeoutError,
    TransientLLMProviderError,
)
from inbox_helper.domain.models.email import Email
from inbox_helper.infrastructure.llm.factory import (
    create_llm_health_check,
    create_llm_provider,
)
from inbox_helper.infrastructure.llm.mock import MockLLMProvider
from inbox_helper.infrastructure.llm.retrying import RetryingLLMProvider


class SequenceProvider:
    def __init__(self, results: list[str | Exception]) -> None:
        self.results = results
        self.calls = 0

    def complete(self, prompt: str) -> str:
        result = self.results[self.calls]
        self.calls += 1
        if isinstance(result, Exception):
            raise result
        return result


def test_retry_wrapper_retries_explicit_transient_failure_once() -> None:
    provider = SequenceProvider(
        [TransientLLMProviderError("temporary"), "ok"]
    )

    assert RetryingLLMProvider(provider).complete("safe prompt") == "ok"
    assert provider.calls == 2


def test_retry_wrapper_preserves_final_transient_exception() -> None:
    first = TransientLLMProviderError("first transient")
    final = TransientLLMProviderError("final meaningful failure")
    provider = SequenceProvider([first, final])

    with pytest.raises(TransientLLMProviderError) as error:
        RetryingLLMProvider(provider).complete("safe prompt")

    assert error.value is final
    assert provider.calls == 2


def test_timeout_errors_use_bounded_transient_retry() -> None:
    timeout = LLMProviderTimeoutError("timeout")
    provider = SequenceProvider([timeout, "recovered"])

    assert RetryingLLMProvider(provider).complete("safe prompt") == "recovered"
    assert provider.calls == 2


def test_retry_wrapper_does_not_retry_permanent_provider_failure() -> None:
    error = LLMProviderError("permanent failure")
    provider = SequenceProvider([error, "should not be used"])

    with pytest.raises(LLMProviderError) as raised:
        RetryingLLMProvider(provider).complete("safe prompt")

    assert raised.value is error
    assert provider.calls == 1


def test_invalid_classification_output_is_not_retried() -> None:
    provider = SequenceProvider(["not json", '{"valid":"later"}'])
    classifier = EmailClassifier(RetryingLLMProvider(provider))

    with pytest.raises(ClassificationError):
        classifier.classify(
            Email(id="email", sender="sender", subject="subject", body="body")
        )

    assert provider.calls == 1


def test_health_check_is_separate_from_completion_retry_behavior() -> None:
    raw_provider = MockLLMProvider()
    retrying_provider = RetryingLLMProvider(raw_provider)

    health_check = create_llm_health_check(AppConfig())

    assert health_check.check_health() is True
    assert retrying_provider.complete("prompt") == "Mock response"
    assert isinstance(create_llm_provider(AppConfig()), RetryingLLMProvider)


@pytest.mark.parametrize("timeout", ["nan", "inf", "0", "-1", "301"])
def test_configuration_rejects_invalid_or_unbounded_timeout(
    monkeypatch: pytest.MonkeyPatch, timeout: str
) -> None:
    monkeypatch.setenv("INBOX_HELPER_LLM_TIMEOUT", timeout)

    with pytest.raises(ConfigurationError, match="between 0 and 300"):
        AppConfig.from_env()


def test_configuration_accepts_positive_timeout_at_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for timeout in ("0.01", "300"):
        monkeypatch.setenv("INBOX_HELPER_LLM_TIMEOUT", timeout)
        assert AppConfig.from_env().llm_timeout == float(timeout)


def test_direct_config_rejects_nonfinite_timeout() -> None:
    with pytest.raises(ConfigurationError, match="between 0 and 300"):
        AppConfig(llm_timeout=float("inf"))


def test_retry_logs_do_not_include_prompt_or_provider_exception_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sensitive_prompt = "email body and reply secret"
    provider = SequenceProvider(
        [
            TransientLLMProviderError("provider detail with private text"),
            TransientLLMProviderError("final private text"),
        ]
    )
    with caplog.at_level(logging.WARNING, logger="inbox_helper.llm.retry"):
        with pytest.raises(TransientLLMProviderError):
            RetryingLLMProvider(provider).complete(sensitive_prompt)

    assert sensitive_prompt not in caplog.text
    assert "private text" not in caplog.text
    assert "transient_provider_error" in caplog.text
