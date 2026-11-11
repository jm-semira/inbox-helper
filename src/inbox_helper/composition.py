"""Application composition root and resource lifecycle."""

from collections.abc import Iterator
from contextlib import contextmanager

from inbox_helper.application.services.email_classifier import EmailClassifier
from inbox_helper.application.services.email_ingestion import EmailIngestionService
from inbox_helper.application.services.reply_draft_service import ReplyDraftService
from inbox_helper.core.config import AppConfig, get_config
from inbox_helper.core.logging import configure_logging
from inbox_helper.infrastructure.csv.email_csv_reader import EmailCsvReader
from inbox_helper.infrastructure.llm.factory import create_llm_provider
from inbox_helper.infrastructure.persistence.sqlite_email_repository import (
    SqliteEmailRepository,
)
from inbox_helper.infrastructure.persistence.sqlite_reply_draft_repository import (
    SqliteReplyDraftRepository,
)


def create_classification_service(
    config: AppConfig | None = None,
) -> EmailClassifier:
    """Build the classification service without creating ingestion resources."""
    active_config = config or get_config()
    return EmailClassifier(create_llm_provider(active_config))


@contextmanager
def create_reply_draft_service(
    config: AppConfig | None = None,
) -> Iterator[ReplyDraftService]:
    """Build the reply-draft service and own its SQLite repository lifecycle."""
    active_config = config or get_config()
    configure_logging(active_config.log_level)
    email_repository = SqliteEmailRepository(active_config.db_path)
    email_repository.close()
    repository = SqliteReplyDraftRepository(active_config.db_path)
    try:
        service = ReplyDraftService(
            create_llm_provider(active_config),
            repository,
        )
        yield service
    finally:
        repository.close()


@contextmanager
def create_application(
    config: AppConfig | None = None,
) -> Iterator[EmailIngestionService]:
    """Build the Day 1 application and close its database resource on exit."""
    active_config = config or get_config()
    configure_logging(active_config.log_level)
    repository = SqliteEmailRepository(active_config.db_path)
    try:
        reader = EmailCsvReader()
        service = EmailIngestionService(reader, repository)
        yield service
    finally:
        repository.close()
