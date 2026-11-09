"""Core application exceptions for Inbox Helper."""


class InboxHelperError(Exception):
    """Base exception for all Inbox Helper domain and infrastructure errors."""
    pass


class ConfigurationError(InboxHelperError):
    """Raised when application configuration is missing, malformed, or invalid."""
    pass


class ValidationError(InboxHelperError):
    """Base exception for input or domain validation failures."""
    pass


class EmailValidationError(ValidationError):
    """Raised when an email entity or input row fails validation constraints."""

    def __init__(self, message: str, field: str | None = None, raw_value: object = None) -> None:
        super().__init__(message)
        self.field = field
        self.raw_value = raw_value


class IngestionError(InboxHelperError):
    """Raised when CSV or data ingestion encounters an unrecoverable failure."""
    pass


class RepositoryError(InboxHelperError):
    """Base exception for database and persistence operations."""
    pass


class EntityNotFoundError(RepositoryError):
    """Raised when an entity with a specified identifier cannot be found."""

    def __init__(self, entity_name: str, entity_id: str) -> None:
        super().__init__(f"{entity_name} with ID '{entity_id}' was not found.")
        self.entity_name = entity_name
        self.entity_id = entity_id
