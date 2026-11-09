import io
import logging
from collections.abc import Iterator

import pytest

from inbox_helper.core.logging import SensitiveDataFilter, configure_logging


@pytest.fixture
def isolated_inbox_logger() -> Iterator[logging.Logger]:
    logger = logging.getLogger("inbox_helper")
    original_handlers = logger.handlers[:]
    original_level = logger.level
    original_propagate = logger.propagate
    for handler in original_handlers:
        logger.removeHandler(handler)
    logger.propagate = False

    yield logger

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        if handler not in original_handlers:
            handler.close()
    for handler in original_handlers:
        logger.addHandler(handler)
    logger.setLevel(original_level)
    logger.propagate = original_propagate


def test_emitted_records_redact_common_credentials_and_preserve_messages(
    isolated_inbox_logger: logging.Logger,
) -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    isolated_inbox_logger.addHandler(handler)
    logger = configure_logging("INFO")

    openai_key = "sk-" + "A" * 24
    google_key = "AIza" + "B" * 35
    github_token = "ghp_" + "C" * 30
    bearer_token = "D" * 32
    logger.info(
        "api_key=%s openai=%s google=%s github=%s Authorization: Bearer %s",
        "key-value-123",
        openai_key,
        google_key,
        github_token,
        bearer_token,
    )
    logger.info(
        "token=%(token)s status=%(status)s",
        {"token": "mapped-secret-value", "status": "ready"},
    )
    logger.info("Import completed for %s", "mailbox-7")

    output = stream.getvalue()
    for secret in (
        "key-value-123",
        openai_key,
        google_key,
        github_token,
        bearer_token,
        "mapped-secret-value",
    ):
        assert secret not in output
    assert output.count("[REDACTED]") == 6
    assert "api_key=[REDACTED]" in output
    assert "Authorization: Bearer [REDACTED]" in output
    assert "status=ready" in output
    assert "Import completed for mailbox-7" in output
    assert any(
        isinstance(log_filter, SensitiveDataFilter)
        for log_filter in handler.filters
    )


def test_configure_logging_adds_filter_to_existing_handlers(
    isolated_inbox_logger: logging.Logger,
) -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    isolated_inbox_logger.addHandler(handler)

    logger = configure_logging("INFO")
    logger.warning("password=%s", "existing-handler-secret")

    assert "existing-handler-secret" not in stream.getvalue()
    assert "[REDACTED]" in stream.getvalue()
    assert any(
        isinstance(log_filter, SensitiveDataFilter)
        for log_filter in handler.filters
    )
