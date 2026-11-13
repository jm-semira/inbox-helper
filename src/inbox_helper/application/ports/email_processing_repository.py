"""Persistence contract for per-email workflow outcomes."""

from datetime import datetime
from typing import Protocol

from inbox_helper.application.models.email_processing import (
    EmailProcessingError,
    EmailProcessingOutcome,
    EmailProcessingStatus,
)
from inbox_helper.domain.models.classification import EmailClassification


class EmailProcessingRepository(Protocol):
    """Store recoverable progress independently for each imported email."""

    def claim(self, email_id: str, retry: bool, now: datetime) -> bool:
        """Atomically claim an email for processing or an explicit retry."""

    def get(self, email_id: str) -> EmailProcessingOutcome | None:
        """Return one email's persisted processing outcome."""

    def list_all(self) -> list[EmailProcessingOutcome]:
        """Return persisted outcomes in update order."""

    def save_classification(
        self, email_id: str, classification: EmailClassification, now: datetime
    ) -> None:
        """Persist validated classification before reply generation."""

    def fail(
        self,
        email_id: str,
        status: EmailProcessingStatus,
        error: EmailProcessingError,
        retryable: bool,
        now: datetime,
    ) -> None:
        """Record a safe failure category while preserving successful work."""

    def complete(
        self,
        email_id: str,
        classification: EmailClassification | None,
        draft_created: bool,
        now: datetime,
    ) -> None:
        """Mark processing complete without changing draft lifecycle state."""

