"""Application queries for browsing imported emails."""

from inbox_helper.application.ports.email_repository import EmailRepository
from inbox_helper.domain.models.email import Email


class EmailQueryService:
    """Expose email retrieval without exposing persistence details."""

    def __init__(self, repository: EmailRepository) -> None:
        self._repository = repository

    def list_emails(self) -> list[Email]:
        """Return imported emails in repository order."""
        return self._repository.list_all()

    def get_email(self, email_id: str) -> Email:
        """Return one imported email by identifier."""
        return self._repository.get_by_id(email_id)
