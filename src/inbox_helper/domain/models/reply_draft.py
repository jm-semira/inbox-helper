"""Reply generation output and human-review draft models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from inbox_helper.domain.models.classification import EmailClassification


class DraftStatus(str, Enum):
    """Lifecycle state for a reply draft."""

    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReplyGenerationOutput(BaseModel):
    """Validated structured output returned by the LLM."""

    model_config = ConfigDict(extra="forbid", strict=True)

    reply_text: str = Field(min_length=1)
    requires_human_input: bool
    human_input_reason: str | None

    @model_validator(mode="after")
    def validate_reply_content(self) -> ReplyGenerationOutput:
        if not self.reply_text.strip():
            raise ValueError("reply_text must not be empty")
        if self.requires_human_input:
            if self.human_input_reason is None or not self.human_input_reason.strip():
                raise ValueError(
                    "human_input_reason is required when human input is needed"
                )
        elif self.human_input_reason is not None:
            raise ValueError(
                "human_input_reason must be null when human input is not needed"
            )
        return self


class ReplyDraft(BaseModel):
    """Persisted draft with immutable generated text and editable current text."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str
    source_email_id: str
    original_generated_text: str = Field(min_length=1)
    current_text: str = Field(min_length=1)
    requires_human_input: bool
    human_input_reason: str | None
    classification: EmailClassification | None = None
    status: DraftStatus = DraftStatus.DRAFT
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    decided_at: datetime | None = None

    @model_validator(mode="after")
    def validate_lifecycle_data(self) -> ReplyDraft:
        if not self.id.strip() or not self.source_email_id.strip():
            raise ValueError("draft and source email IDs must not be empty")
        if not self.original_generated_text.strip() or not self.current_text.strip():
            raise ValueError("draft text must not be empty")
        if self.requires_human_input:
            if self.human_input_reason is None or not self.human_input_reason.strip():
                raise ValueError(
                    "human_input_reason is required when human input is needed"
                )
        elif self.human_input_reason is not None:
            raise ValueError(
                "human_input_reason must be null when human input is not needed"
            )
        if self.status is DraftStatus.DRAFT and self.decided_at is not None:
            raise ValueError("draft status cannot have a decision timestamp")
        if self.status is not DraftStatus.DRAFT and self.decided_at is None:
            raise ValueError("decided drafts require a decision timestamp")
        return self
