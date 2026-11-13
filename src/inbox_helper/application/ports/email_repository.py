"""Persistence contract used by application services."""

from typing import Protocol

from inbox_helper.domain.models.email import Email


class EmailRepository(Protocol):
    """Storage interface for imported emails."""

    def save_many(self, emails: list[Email]) -> None:
        """Persist a group of emails atomically."""

    def get_by_id(self, email_id: str) -> Email:
        """Retrieve an imported email."""

    def list_all(self) -> list[Email]:
        """List imported emails in repository order."""

    def count_emails(self) -> int:
        """Return the number of imported emails."""
