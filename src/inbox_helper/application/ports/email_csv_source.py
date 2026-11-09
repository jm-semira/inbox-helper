"""Input boundary for validated email CSV records."""

from pathlib import Path
from typing import Protocol

from inbox_helper.domain.models.email import Email


class EmailCsvSource(Protocol):
    """Read and validate a CSV file into domain emails."""

    def read(self, path: str | Path) -> list[Email]:
        """Return all validated records or raise an ingestion error."""
