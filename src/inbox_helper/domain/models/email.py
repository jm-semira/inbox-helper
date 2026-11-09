"""Email domain model."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class Email(BaseModel):
    """Validated email data imported into Inbox Helper."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    sender: str
    subject: str
    body: str
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("id", "sender", mode="before")
    @classmethod
    def require_nonempty(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("received_at")
    @classmethod
    def normalize_received_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
