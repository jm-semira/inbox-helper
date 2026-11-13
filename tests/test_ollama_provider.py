import json
import socket
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from inbox_helper.application.services.email_classifier import EmailClassifier
from inbox_helper.application.services.reply_draft_service import ReplyDraftService
from inbox_helper.core.config import AppConfig
from inbox_helper.core.exceptions import (
    ClassificationError,
    ConfigurationError,
    LLMProviderError,
    LLMProviderTimeoutError,
    TransientLLMProviderError,
)
from inbox_helper.domain.models.classification import (
    EmailClassification,
    EmailIntent,
    EmailUrgency,
)
from inbox_helper.domain.models.email import Email
from inbox_helper.infrastructure.llm.factory import (
    create_llm_health_check,
    create_llm_provider,
)
from inbox_helper.infrastructure.llm.ollama import OllamaLLMProvider
from inbox_helper.infrastructure.llm.retrying import RetryingLLMProvider
from inbox_helper.infrastructure.persistence.sqlite_email_repository import (
    SqliteEmailRepository,
)
from inbox_helper.infrastructure.persistence.sqlite_reply_draft_repository import (
    SqliteReplyDraftRepository,
)


class FakeResponse:
    def __init__(self, body: bytes = b"", status: int = 200) -> None:
        self._body = BytesIO(body)
        self.status = status

    def read(self) -> bytes:
        return self._body.read()

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_: object) -> None:
        return None


def _provider(**overrides: object) -> OllamaLLMProvider:
    config = AppConfig(
        llm_provider="ollama",
        ollama_base_url="http://localhost:11434/",
        llm_model="qwen2.5:3b",
        llm_timeout=7.5,
        llm_temperature=0.4,
        **overrides,
    )
    return OllamaLLMProvider.from_config(config)


def _http_error(status: int) -> HTTPError:
    return HTTPError(
        "http://localhost:11434/api/generate",
        status,
        "sensitive server message",
        hdrs=None,
        fp=BytesIO(b"private body"),
    )


def test_complete_sends_non_streaming_json_mode_options_and_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: dict[str, object] = {}

    def fake_urlopen(request: Request, timeout: float):
        received["request"] = request
        received["timeout"] = timeout
        return FakeResponse(b'{"response":"{\\"intent\\":\\"other\\"}"}')

    monkeypatch.setattr("inbox_helper.infrastructure.llm.ollama.urlopen", fake_urlopen)
    prompt = "private email prompt"

    result = _provider().complete(prompt)

    request = received["request"]
    assert isinstance(request, Request)
    assert request.full_url == "http://localhost:11434/api/generate"
    assert request.get_method() == "POST"
    assert received["timeout"] == 7.5
    payload = json.loads(request.data)
    assert payload == {
        "model": "qwen2.5:3b",
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.4},
    }
    assert result == '{"intent":"other"}'


@pytest.mark.parametrize(
    "response",
    [
        b'{"response":"{\\"intent\\":\\"other\\",\\"urgency\\":\\"normal\\",'
        b'\\"confidence\\":0.8,\\"explanation\\":\\"A normal message.\\"}"}',
        b'{"response":"{\\"reply_text\\":\\"Thank you.\\",'
        b'\\"requires_human_input\\":false,\\"human_input_reason\\":null}"}',
    ],
)
def test_provider_output_flows_through_classification_and_reply_validation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    response: bytes,
) -> None:
    monkeypatch.setattr(
        "inbox_helper.infrastructure.llm.ollama.urlopen",
        lambda request, timeout: FakeResponse(response),
    )
    provider = RetryingLLMProvider(_provider())
    email = Email(
        id="ollama-email",
        sender="candidate",
        subject="Question",
        body="I would like to know more.",
    )

    if b"intent" in response:
        classification = EmailClassifier(provider).classify(email)
        assert classification.intent is EmailIntent.OTHER
        assert classification.urgency is EmailUrgency.NORMAL
        return

    classification = EmailClassification(
        intent=EmailIntent.GENERAL_INQUIRY,
        urgency=EmailUrgency.NORMAL,
        confidence=0.8,
        explanation="A general inquiry.",
    )
    db_path = tmp_path / "inbox.db"
    with SqliteEmailRepository(db_path) as emails:
        emails.save_many([email])
    with SqliteReplyDraftRepository(db_path) as drafts:
        result = ReplyDraftService(provider, drafts).generate_draft(
            email, classification
        )
        assert result.current_text == "Thank you."


def test_invalid_model_output_is_returned_for_application_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "inbox_helper.infrastructure.llm.ollama.urlopen",
        lambda request, timeout: FakeResponse(b'{"response":"not json"}'),
    )

    with pytest.raises(ClassificationError):
        EmailClassifier(RetryingLLMProvider(_provider())).classify(
            Email(id="email", sender="sender", subject="subject", body="body")
        )


def test_malformed_provider_envelope_is_not_retried_or_exposed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def malformed(request: Request, timeout: float):
        nonlocal calls
        calls += 1
        return FakeResponse(b"not-json")

    monkeypatch.setattr("inbox_helper.infrastructure.llm.ollama.urlopen", malformed)
    with pytest.raises(LLMProviderError) as error:
        RetryingLLMProvider(_provider()).complete("private prompt")

    assert str(error.value) == "Ollama returned a malformed response envelope."
    assert calls == 1


@pytest.mark.parametrize("body", [b"{}", b'{"response":""}', b'{"response":null}'])
def test_missing_generated_response_is_permanent_provider_error(
    monkeypatch: pytest.MonkeyPatch, body: bytes
) -> None:
    monkeypatch.setattr(
        "inbox_helper.infrastructure.llm.ollama.urlopen",
        lambda request, timeout: FakeResponse(body),
    )

    with pytest.raises(LLMProviderError, match="did not contain generated text"):
        _provider().complete("prompt")


def test_timeout_is_classified_and_retried_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def timeout(request: Request, timeout: float):
        nonlocal calls
        calls += 1
        raise socket.timeout("secret detail")

    monkeypatch.setattr("inbox_helper.infrastructure.llm.ollama.urlopen", timeout)
    with pytest.raises(LLMProviderTimeoutError) as error:
        RetryingLLMProvider(_provider()).complete("private prompt")

    assert calls == 2
    assert "secret" not in str(error.value)


def test_connection_failure_is_transient_and_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "inbox_helper.infrastructure.llm.ollama.urlopen",
        lambda request, timeout: (_ for _ in ()).throw(
            URLError("private connection detail")
        ),
    )

    with pytest.raises(TransientLLMProviderError) as error:
        _provider().complete("private prompt")

    assert "private" not in str(error.value)


@pytest.mark.parametrize(
    ("status", "expected_error"),
    [
        (400, LLMProviderError),
        (401, LLMProviderError),
        (500, TransientLLMProviderError),
        (503, TransientLLMProviderError),
    ],
)
def test_http_errors_are_classified_without_provider_content(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    expected_error: type[Exception],
) -> None:
    monkeypatch.setattr(
        "inbox_helper.infrastructure.llm.ollama.urlopen",
        lambda request, timeout: (_ for _ in ()).throw(_http_error(status)),
    )

    with pytest.raises(expected_error) as error:
        _provider().complete("private prompt")

    assert "sensitive" not in str(error.value)
    assert "private" not in str(error.value)


def test_transient_http_failure_uses_existing_bounded_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def unavailable(request: Request, timeout: float):
        nonlocal calls
        calls += 1
        raise _http_error(503)

    monkeypatch.setattr("inbox_helper.infrastructure.llm.ollama.urlopen", unavailable)
    with pytest.raises(TransientLLMProviderError):
        RetryingLLMProvider(_provider()).complete("prompt")

    assert calls == 2


def test_health_check_uses_tags_endpoint_timeout_and_no_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: dict[str, object] = {}

    def healthy(request: Request, timeout: float):
        received["request"] = request
        received["timeout"] = timeout
        return FakeResponse(b'{"models":[]}')

    monkeypatch.setattr("inbox_helper.infrastructure.llm.ollama.urlopen", healthy)
    provider = _provider()

    assert provider.check_health() is True
    request = received["request"]
    assert isinstance(request, Request)
    assert request.full_url == "http://localhost:11434/api/tags"
    assert request.get_method() == "GET"
    assert received["timeout"] == 7.5


@pytest.mark.parametrize(
    "failure",
    [
        socket.timeout("private timeout"),
        URLError("private connection"),
        _http_error(503),
    ],
)
def test_health_check_returns_false_on_unavailability(
    monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    monkeypatch.setattr(
        "inbox_helper.infrastructure.llm.ollama.urlopen",
        lambda request, timeout: (_ for _ in ()).throw(failure),
    )

    assert _provider().check_health() is False


def test_factory_selects_ollama_provider_and_health_check() -> None:
    config = AppConfig(llm_provider="ollama")

    provider = create_llm_provider(config)
    health = create_llm_health_check(config)

    assert isinstance(provider, RetryingLLMProvider)
    assert isinstance(provider._provider, OllamaLLMProvider)
    assert isinstance(health, OllamaLLMProvider)


def test_ollama_configuration_uses_model_default_and_validates_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INBOX_HELPER_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("INBOX_HELPER_DEMO_MODE", "false")
    monkeypatch.delenv("INBOX_HELPER_LLM_MODEL", raising=False)
    config = AppConfig.from_env()

    assert config.llm_model == "llama3.2"
    assert config.llm_provider == "ollama"


@pytest.mark.parametrize(
    "base_url",
    [
        "not-a-url",
        "ftp://localhost:11434",
        "http://user:password@localhost:11434",
        "http://localhost:11434?token=secret",
    ],
)
def test_ollama_configuration_rejects_unsafe_or_invalid_base_url(
    base_url: str,
) -> None:
    with pytest.raises(ConfigurationError, match="OLLAMA_BASE_URL"):
        AppConfig(llm_provider="ollama", ollama_base_url=base_url)


def test_ollama_mode_rejects_demo_flag() -> None:
    with pytest.raises(ConfigurationError, match="Demo Mode"):
        create_llm_provider(AppConfig(llm_provider="ollama", demo_mode=True))
