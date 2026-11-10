"""Application composition root and resource lifecycle."""

from collections.abc import Iterator
from contextlib import contextmanager

from inbox_helper.application.services.email_classifier import EmailClassifier
from inbox_helper.application.services.email_ingestion import EmailIngestionService
from inbox_helper.core.config import AppConfig, get_config
from inbox_helper.core.logging import configure_logging
from inbox_helper.infrastructure.csv.email_csv_reader import EmailCsvReader
from inbox_helper.infrastructure.llm.factory import create_llm_provider
from inbox_helper.infrastructure.persistence.sqlite_email_repository import (
    SqliteEmailRepository,
)


def create_classification_service(
    config: AppConfig | None = None,
) -> EmailClassifier:
    """Build the classification service without creating ingestion resources."""
    active_config = config or get_config()
    return EmailClassifier(create_llm_provider(active_config))


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
