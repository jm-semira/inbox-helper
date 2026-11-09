"""CSV email ingestion use case."""

from pathlib import Path

from inbox_helper.application.ports.email_csv_source import EmailCsvSource
from inbox_helper.application.ports.email_repository import EmailRepository
from inbox_helper.core.exceptions import IngestionError


class EmailIngestionService:
    """Validate a CSV file and persist its emails as one operation."""

    def __init__(
        self, reader: EmailCsvSource, repository: EmailRepository
    ) -> None:
        self._reader = reader
        self._repository = repository

    def ingest_csv(self, path: str | Path) -> int:
        emails = self._reader.read(path)
        if not emails:
            raise IngestionError("CSV contains no email records.")
        self._repository.save_many(emails)
        return len(emails)
