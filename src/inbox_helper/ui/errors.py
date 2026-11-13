"""Safe user-facing messages for known application failures."""

from inbox_helper.core.exceptions import (
    ClassificationError,
    ConfigurationError,
    DraftStateError,
    DraftValidationError,
    ExportError,
    IngestionError,
    LLMProviderError,
    RepositoryError,
    ReplyGenerationError,
)


def safe_error_message(error: Exception, provider: str = "mock") -> str:
    """Describe a failure without exposing exception details or input data."""
    if isinstance(error, ConfigurationError):
        return "Configuration is invalid. Review the local application settings."
    if isinstance(error, IngestionError):
        return "CSV import failed. Check the file format and required fields."
    if isinstance(error, ClassificationError):
        return "The provider response was not a valid classification."
    if isinstance(error, ReplyGenerationError):
        return "The provider response was not a valid reply draft."
    if isinstance(error, LLMProviderError):
        if provider == "ollama":
            return (
                "Ollama could not complete this request. Check that the local "
                "Ollama service is running and the configured model is available."
            )
        return "The configured mock provider could not complete this request."
    if isinstance(error, DraftValidationError):
        return "The draft text is invalid. Enter a non-empty reply."
    if isinstance(error, DraftStateError):
        return "This draft is no longer pending and cannot be changed."
    if isinstance(error, ExportError):
        return "The approved-reply export could not be created."
    if isinstance(error, RepositoryError):
        return "The local database operation failed. No success is assumed."
    return "The operation could not be completed."
