"""Application projections for the pending reply review queue."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from inbox_helper.domain.models.classification import EmailIntent
from inbox_helper.domain.models.reply_draft import ReplyDraft


class ReviewQueueItem(BaseModel):
    """Pending draft with the source-email and ordering data needed for review."""

    model_config = ConfigDict(frozen=True)

    draft: ReplyDraft
    sender: str
    subject: str
    received_at: datetime
    intent: EmailIntent | None
    urgency: str | None
    body: str = ""


class ReviewQueueGroup(BaseModel):
    """Non-empty queue group for one existing intent or unclassified drafts."""

    model_config = ConfigDict(frozen=True)

    intent: EmailIntent | None
    items: tuple[ReviewQueueItem, ...]
