"""Persistence contract used by application services."""

from typing import Protocol

from inbox_helper.domain.models.email import Email


class EmailRepository(Protocol):
    """Storage interface for imported emails."""

    def save_many(self, emails: list[Email]) -> None:
        """Persist a group of emails atomically."""
