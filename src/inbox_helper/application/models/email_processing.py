"""Provider-neutral outcomes for processing imported emails."""

from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, ConfigDict

from inbox_helper.domain.models.classification import EmailClassification


class EmailProcessingStatus(str, Enum):
    """Persisted lifecycle for one email's classification and draft workflow."""

    PROCESSING = "processing"
    CLASSIFICATION_FAILED = "classification_failed"
    DRAFT_GENERATION_FAILED = "draft_generation_failed"
    COMPLETED = "completed"


class EmailProcessingError(str, Enum):
    """Safe, provider-neutral failure categories suitable for persistence."""

    TRANSIENT_PROVIDER = "transient_provider"
    PERMANENT_PROVIDER = "permanent_provider"
    INVALID_CLASSIFICATION = "invalid_classification"
    INVALID_REPLY = "invalid_reply"


class EmailProcessingOutcome(BaseModel):
    """Persisted processing state without raw provider errors or email content."""

    model_config = ConfigDict(frozen=True)

    email_id: str
    status: EmailProcessingStatus
    classification: EmailClassification | None = None
    error: EmailProcessingError | None = None
    retryable: bool = False
    draft_created: bool = False
    updated_at: datetime

    @property
    def error_message(self) -> str | None:
        """Return a safe user-facing message for a recorded processing failure."""
        messages = {
            EmailProcessingError.TRANSIENT_PROVIDER: (
                "The provider is temporarily unavailable. Retry this email."
            ),
            EmailProcessingError.PERMANENT_PROVIDER: (
                "The provider rejected the request. Check its configuration."
            ),
            EmailProcessingError.INVALID_CLASSIFICATION: (
                "The provider returned an invalid classification. No draft was generated."
            ),
            EmailProcessingError.INVALID_REPLY: (
                "The provider returned an invalid reply draft. The classification was saved."
            ),
        }
        return messages.get(self.error) if self.error is not None else None


@dataclass(frozen=True)
class EmailProcessingBatch:
    """Aggregate counts and per-email outcomes for one upload or retry."""

    emails_processed: int
    classified: int
    drafted: int
    failed: int
    outcomes: tuple[EmailProcessingOutcome, ...]
